"""데이터베이스 연결과 초기화.

schema.sql 이 테이블 정의의 원본이다. 테이블을 바꿀 때는 schema.sql 을 고친다.
"""
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schema.sql"
DEFAULT_DB_PATH = ROOT / "rapi.db"


def connect(db_path=DEFAULT_DB_PATH) -> sqlite3.Connection:
    """외래 키 검사를 켠 연결을 돌려준다. 행은 dict 처럼 열 이름으로 읽을 수 있다."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """빈 데이터베이스에 20개 테이블을 만든다."""
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()


if __name__ == "__main__":
    # python -m app.db  →  rapi.db 새로 만들기
    if DEFAULT_DB_PATH.exists():
        raise SystemExit(f"{DEFAULT_DB_PATH} 가 이미 있어요. 새로 만들려면 먼저 지우세요.")
    c = connect()
    init_db(c)
    n = c.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
    print(f"테이블 {n}개 생성: {DEFAULT_DB_PATH}")
