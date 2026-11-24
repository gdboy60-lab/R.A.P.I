"""일봉 적재 (네트워크 없이 가짜 API 응답으로 검사)."""
import json
from datetime import date, timedelta
import pytest
from app.data.load_prices import build_calendar, check_lookback, create_period, normalize, run, save_prices


def fake_rows(code, start, n, extra_code=None):
    rows, d, days = [], start, 0
    while days < n:
        if d.weekday() < 5:
            days += 1
            for c in [code] + ([extra_code] if extra_code else []):
                rows.append({"basDt": d.strftime("%Y%m%d"), "srtnCd": c, "itmsNm": "x",
                             "mkp": "1000", "hipr": "1100", "lopr": "950", "clpr": "1050", "trqu": "12345"})
        d += timedelta(days=1)
    return rows


def test_normalize_keeps_exact_code_and_skips_halted():
    raw = fake_rows("005930", date(2023, 6, 1), 3, extra_code="0059300")   # 포함 검색으로 섞인 종목
    raw.append({"basDt": "20230607", "srtnCd": "005930", "mkp": "0", "hipr": "0", "lopr": "0", "clpr": "0", "trqu": "0"})
    rows = normalize(raw, "005930")
    assert [r[1] for r in rows] == ["2023-06-01", "2023-06-02", "2023-06-05"]
    assert rows[0] == ("005930", "2023-06-01", 1000, 1100, 950, 1050, 12345)


def test_calendar_period_and_lookback(conn):
    save_prices(conn, normalize(fake_rows("A", date(2023, 1, 2), 120), "A"))
    n = build_calendar(conn, {"2023-01-02": ["10:00:00", "15:30:00"]})
    assert n == 120
    assert conn.execute("SELECT open_time FROM market_calendar WHERE date='2023-01-02'").fetchone()[0] == "10:00:00"
    pid = create_period(conn, "테스트", "2023-05-01", "2023-05-31", {"A": "가상"})
    assert conn.execute("SELECT trading_days FROM replay_periods WHERE period_id=?", (pid,)).fetchone()[0] >= 10
    assert check_lookback(conn, "2023-05-01", {"A": "가상"})          # 앞 일봉이 250일보다 적음 → 경고
    with pytest.raises(ValueError):
        create_period(conn, "짧음", "2023-05-01", "2023-05-05", {"A": "가상"})


def test_run_end_to_end(tmp_path, monkeypatch):
    cfg = {"periods": [{"label": "기간", "start": "2024-06-03", "end": "2024-06-14", "stocks": {"005930": "삼성전자"}}]}
    path = tmp_path / "periods.json"
    path.write_text(json.dumps(cfg), encoding="utf-8")
    monkeypatch.setenv("DATA_GO_KR_KEY", "test")

    def fake_fetch(key, code, begin, end):
        return [r for r in fake_rows(code, begin, 400) if r["basDt"] <= end.strftime("%Y%m%d")]

    db = tmp_path / "r.db"
    run(str(path), db_path=db, fetch=fake_fetch)
    from app.db import connect
    from app.projects import create_guest, create_project
    c = connect(db)
    pid = c.execute("SELECT period_id FROM replay_periods").fetchone()[0]
    project = create_project(c, create_guest(c), pid)                 # 실제 데이터로 프로젝트 생성 가능
    assert c.execute("SELECT total_trading_days FROM projects WHERE project_id=?", (project,)).fetchone()[0] == 10
