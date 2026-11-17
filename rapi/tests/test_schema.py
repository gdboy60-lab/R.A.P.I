"""데이터베이스 제약(NFR-03)이 실제로 막아주는지 확인."""
import sqlite3
import pytest
from app.projects import ProjectError, create_guest, create_project


def test_20_tables(conn):
    n = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
    assert n == 20


def test_project_starts_pre_open_with_10m(conn, period_id):
    pid = create_project(conn, create_guest(conn), period_id)
    p = conn.execute("SELECT * FROM projects WHERE project_id=?", (pid,)).fetchone()
    assert p["clock_status"] == "pre_open" and p["current_day"] == 1
    assert p["sim_now"] == "2024-03-04T09:00:00"
    assert p["baseline_end_date"] == "2024-03-08"          # 5번째 개장일
    assert conn.execute("SELECT cash FROM accounts WHERE project_id=?", (pid,)).fetchone()[0] == 10_000_000


def test_only_one_live_project(conn, period_id):
    uid = create_guest(conn)
    first = create_project(conn, uid, period_id)
    with pytest.raises(ProjectError):
        create_project(conn, uid, period_id)
    conn.execute("UPDATE projects SET status='finished' WHERE project_id=?", (first,))
    create_project(conn, uid, period_id)                   # 끝난 뒤에는 새로 만들 수 있음


def _project(conn, period_id):
    return create_project(conn, create_guest(conn), period_id)


def test_watchlist_max_20(conn, period_id):
    pid = _project(conn, period_id)
    for i in range(20):
        conn.execute("INSERT INTO watchlist (project_id, stock_code, added_at) VALUES (?,?,?)",
                     (pid, f"S{i:03d}", "2024-03-04T08:50:00"))
    with pytest.raises(sqlite3.IntegrityError, match="watchlist_limit_20"):
        conn.execute("INSERT INTO watchlist (project_id, stock_code, added_at) VALUES (?, 'S999', 'x')", (pid,))
    # 하나 빼면 다시 추가 가능
    conn.execute("UPDATE watchlist SET removed_at='y' WHERE stock_code='S000'")
    conn.execute("INSERT INTO watchlist (project_id, stock_code, added_at) VALUES (?, 'S999', 'x')", (pid,))


def test_no_duplicate_penalty(conn, period_id):
    pid = _project(conn, period_id)
    ins = ("INSERT INTO rule_evaluations (project_id, rule_id, area, target_date, result, penalty, evaluated_at) "
           "VALUES (?, 'BC-03', 'BC', '2024-03-05', 'violation', 15, 't')")
    conn.execute(ins, (pid,))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(ins, (pid,))                           # 같은 날 BC-03 두 번은 불가


def test_violation_needs_penalty(conn, period_id):
    pid = _project(conn, period_id)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO rule_evaluations (project_id, rule_id, area, target_date, result, penalty, evaluated_at) "
                     "VALUES (?, 'BC-01', 'BC', '2024-03-05', 'hold', 20, 't')", (pid,))


def test_server_creates_db_when_missing(tmp_path):
    import importlib.util, sys
    if importlib.util.find_spec("fastapi") is None:
        # FastAPI 없이도 ensure_db 만 따로 검사
        src = (__import__("pathlib").Path(__file__).parent.parent / "app" / "main.py").read_text(encoding="utf-8")
        assert "ensure_db()" in src
        from app.db import connect, init_db
        from app.seed_dev import seed
        db = tmp_path / "new.db"
        c = connect(db); init_db(c); seed(c)
        assert c.execute("SELECT COUNT(*) FROM replay_periods").fetchone()[0] == 1
        return
    from app.main import ensure_db
    db = tmp_path / "new.db"
    assert ensure_db(db) is True and db.exists()
    assert ensure_db(db) is False          # 이미 있으면 건드리지 않음
