"""공공데이터포털 '금융위원회_주식시세정보' 일봉을 받아 DB에 넣는다 (1주차 B 작업).

하는 일
1. 설정 파일(periods.json)에 적힌 리플레이 기간과 종목마다, 기간 시작 전 약 400일부터 기간 끝까지 일봉을 받는다.
   (MC 지표에 직전 250개장일이 필요해서 넉넉히 받는다)
2. daily_prices 에 저장한다.
3. 일봉이 있는 날짜를 개장일로 market_calendar 에 넣는다 (기본 09:00~15:30, 설정에서 날짜별로 바꿀 수 있음).
4. replay_periods, replay_stocks 를 만든다.
5. 종목마다 기간 앞 개장일이 250일 이상인지 검사해서 알려준다.

이용 조건 (반드시 지킬 것)
- 공식 오픈 API로만 받는다. 웹 페이지를 긁어오지 않는다.
- 받은 데이터 파일(rapi.db, CSV)을 깃허브 등에 올려 공유하지 않는다.
- 화면에 출처를 표시한다: "출처: 금융위원회, 공공데이터포털".

실행
    set DATA_GO_KR_KEY=발급받은_일반_인증키      (Windows PowerShell: $env:DATA_GO_KR_KEY="...")
    python -m app.data.load_prices periods.json
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

from ..db import DEFAULT_DB_PATH, connect, init_db

API_URL = "https://apis.data.go.kr/1160100/service/GetStockSecuritiesInfoService/getStockPriceInfo"
LOOKBACK_CALENDAR_DAYS = 400      # 약 270개장일
MIN_LOOKBACK_TRADING_DAYS = 250
SOURCE_NOTE = "출처: 금융위원회, 공공데이터포털"


# ---------------------------------------------------------------- 받기
def fetch_daily(service_key: str, stock_code: str, begin: date, end: date,
                page_size: int = 1000) -> list[dict]:
    """한 종목의 일봉을 API에서 받아 원본 행(dict) 목록으로 돌려준다."""
    rows, page = [], 1
    while True:
        params = {
            "serviceKey": service_key,
            "resultType": "json",
            "numOfRows": page_size,
            "pageNo": page,
            "likeSrtnCd": stock_code,
            "beginBasDt": begin.strftime("%Y%m%d"),
            "endBasDt": end.strftime("%Y%m%d"),
        }
        # 인증키에 이미 %가 들어 있으면(인코딩 키) 다시 인코딩하지 않는다
        query = urllib.parse.urlencode(params, safe="%")
        with urllib.request.urlopen(f"{API_URL}?{query}", timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        body = payload.get("response", {}).get("body")
        if body is None:
            raise RuntimeError(f"API 응답이 이상해요: {str(payload)[:300]}")
        items = body.get("items") or {}
        batch = items.get("item", []) if isinstance(items, dict) else []
        if isinstance(batch, dict):
            batch = [batch]
        rows += batch
        if page * page_size >= int(body.get("totalCount", 0)) or not batch:
            return rows
        page += 1
        time.sleep(0.2)


def normalize(raw: list[dict], stock_code: str) -> list[tuple]:
    """API 원본 행 → daily_prices 한 줄 (stock_code, date, open, high, low, close, volume).

    likeSrtnCd 는 '포함' 검색이라 다른 종목이 섞일 수 있어서 단축코드가 정확히 같은 행만 남긴다.
    거래정지일처럼 시가가 0인 날은 개장일 판정과 지표 계산을 망치므로 뺀다.
    """
    out = {}
    for r in raw:
        if str(r.get("srtnCd", "")).strip() != stock_code:
            continue
        d = str(r["basDt"])
        o, h, l, c, v = (int(float(r[k])) for k in ("mkp", "hipr", "lopr", "clpr", "trqu"))
        if o <= 0 or c <= 0:
            continue
        out[d] = (stock_code, f"{d[:4]}-{d[4:6]}-{d[6:]}", o, h, l, c, v)
    return [out[k] for k in sorted(out)]


# ---------------------------------------------------------------- 저장
def save_prices(conn, rows: list[tuple]) -> None:
    conn.executemany(
        "INSERT OR REPLACE INTO daily_prices (stock_code, date, open, high, low, close, volume) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        rows,
    )


def build_calendar(conn, overrides: dict[str, list[str]] | None = None) -> int:
    """일봉이 하나라도 있는 날짜를 개장일로 넣는다.

    overrides: {"2023-11-16": ["10:00:00", "16:30:00"]} 처럼 장 시간이 다른 날 (수능일, 연초 첫날 등).
    """
    overrides = overrides or {}
    dates = [r[0] for r in conn.execute("SELECT DISTINCT date FROM daily_prices ORDER BY date")]
    for d in dates:
        open_t, close_t = overrides.get(d, ["09:00:00", "15:30:00"])
        conn.execute(
            "INSERT OR REPLACE INTO market_calendar (date, is_open, open_time, close_time) VALUES (?, 1, ?, ?)",
            (d, open_t, close_t),
        )
    return len(dates)


def create_period(conn, label: str, start: str, end: str, stocks: dict[str, str],
                  description: str = "") -> int:
    days = conn.execute(
        "SELECT COUNT(*) FROM market_calendar WHERE is_open = 1 AND date BETWEEN ? AND ?", (start, end)
    ).fetchone()[0]
    if days < 10:
        raise ValueError(f"'{label}' 기간의 개장일이 {days}일이에요. 10일 이상이어야 해요")
    cur = conn.execute(
        "INSERT INTO replay_periods (label, start_date, end_date, trading_days, description) VALUES (?, ?, ?, ?, ?)",
        (label, start, end, days, description),
    )
    pid = cur.lastrowid
    conn.executemany(
        "INSERT INTO replay_stocks (period_id, stock_code, display_name) VALUES (?, ?, ?)",
        [(pid, code, name) for code, name in stocks.items()],
    )
    return pid


def check_lookback(conn, start: str, stocks: dict[str, str]) -> list[str]:
    """기간 앞 개장일이 250일보다 적은 종목을 찾는다 (MC 지표가 불완전해짐)."""
    problems = []
    for code, name in stocks.items():
        n = conn.execute(
            "SELECT COUNT(*) FROM daily_prices WHERE stock_code = ? AND date < ?", (code, start)
        ).fetchone()[0]
        if n < MIN_LOOKBACK_TRADING_DAYS:
            problems.append(f"{name}({code}): 기간 앞 일봉 {n}일 (250일 필요)")
    return problems


# ---------------------------------------------------------------- 실행
def run(config_path: str, db_path=DEFAULT_DB_PATH, fetch=fetch_daily) -> None:
    cfg = json.loads(Path(config_path).read_text(encoding="utf-8"))
    key = os.environ.get("DATA_GO_KR_KEY", "")
    if not key:
        raise SystemExit("환경 변수 DATA_GO_KR_KEY 에 공공데이터포털 인증키를 넣어주세요")

    fresh = not Path(db_path).exists()
    conn = connect(db_path)
    if fresh:
        init_db(conn)

    for p in cfg["periods"]:
        start, end = date.fromisoformat(p["start"]), date.fromisoformat(p["end"])
        begin = start - timedelta(days=LOOKBACK_CALENDAR_DAYS)
        for code, name in p["stocks"].items():
            rows = normalize(fetch(key, code, begin, end), code)
            save_prices(conn, rows)
            print(f"  {name}({code}): 일봉 {len(rows)}일")
        conn.commit()

    n_days = build_calendar(conn, cfg.get("special_hours"))
    print(f"개장일 {n_days}일을 달력에 넣었어요")

    for p in cfg["periods"]:
        pid = create_period(conn, p["label"], p["start"], p["end"], p["stocks"], p.get("memo", ""))
        print(f"리플레이 기간 {pid}번 '{p['label']}' ({p['start']} ~ {p['end']}, {len(p['stocks'])}종목)")
        for msg in check_lookback(conn, p["start"], p["stocks"]):
            print("  주의:", msg)
    conn.commit()
    print(SOURCE_NOTE)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("사용법: python -m app.data.load_prices periods.json")
    run(sys.argv[1])
