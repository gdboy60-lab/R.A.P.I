"""개발용 예시 데이터. 실제 리플레이 데이터가 들어오기 전에 화면과 시계를 개발하기 위한 것.

- 리플레이 기간 1개 (평일 10일, 09:00~15:30)
- 가상 종목 6개 (시안과 같은 가상 이름, 일봉은 없음)

실행:  python -m app.seed_dev
B가 공공데이터를 적재하면 이 데이터는 쓰지 않는다.
"""
from __future__ import annotations

from datetime import date, timedelta

from .db import DEFAULT_DB_PATH, connect, init_db

DEV_STOCKS = [
    ("DEV001", "한빛전자"), ("DEV002", "누리소프트"), ("DEV003", "바다물산"),
    ("DEV004", "새벽에너지"), ("DEV005", "푸른제약"), ("DEV006", "한길건설"),
]


def seed(conn, start: date = date(2024, 3, 4), n_days: int = 10) -> int:
    days, d = [], start
    while len(days) < n_days:
        if d.weekday() < 5:
            days.append(d)
        d += timedelta(days=1)
    conn.executemany(
        "INSERT OR IGNORE INTO market_calendar (date, is_open, open_time, close_time) "
        "VALUES (?, 1, '09:00:00', '15:30:00')",
        [(x.isoformat(),) for x in days],
    )
    cur = conn.execute(
        "INSERT INTO replay_periods (label, start_date, end_date, trading_days, description) "
        "VALUES ('개발용 예시 기간', ?, ?, ?, '화면·시계 개발용. 일봉 없음')",
        (days[0].isoformat(), days[-1].isoformat(), n_days),
    )
    period_id = cur.lastrowid
    conn.executemany(
        "INSERT INTO replay_stocks (period_id, stock_code, display_name) VALUES (?, ?, ?)",
        [(period_id, code, name) for code, name in DEV_STOCKS],
    )
    conn.commit()
    return period_id


if __name__ == "__main__":
    fresh = not DEFAULT_DB_PATH.exists()
    c = connect()
    if fresh:
        init_db(c)
    pid = seed(c)
    print(f"개발용 리플레이 기간 {pid}번을 넣었어요: {DEFAULT_DB_PATH}")
