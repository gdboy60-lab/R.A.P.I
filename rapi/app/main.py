"""R.A.P.I 웹 서버 (FastAPI).

실행:  uvicorn app.main:app --reload
지금 있는 화면: 로그인 → 프로젝트 시작(기간 선택) → 홈(시계 바만 동작)
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .db import DEFAULT_DB_PATH, connect, init_db
from .engine.clock import ClockError
from .engine.clock_store import clock_view, load_clock, save_clock
from .projects import ProjectError, create_guest, create_project
from .rules.catalog import scores_for_project

BASE = Path(__file__).resolve().parent


def ensure_db(db_path=DEFAULT_DB_PATH) -> bool:
    """rapi.db 가 없으면 테이블을 만들고 개발용 예시 기간을 넣는다.

    rapi.db 는 재배포 금지 때문에 깃허브에 올리지 않으므로, 저장소를 새로 받은 직후에도
    서버가 바로 켜지게 하려는 것이다. 이미 있으면 아무것도 하지 않는다.
    """
    if Path(db_path).exists():
        return False
    from .seed_dev import seed
    conn = connect(db_path)
    try:
        init_db(conn)
        seed(conn)
    finally:
        conn.close()
    return True


ensure_db()
app = FastAPI(title="R.A.P.I")
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
templates = Jinja2Templates(directory=BASE / "templates")

COOKIE = "rapi_project"   # 체험 계정: 이 기기(브라우저)에서만 이어보기 (FR-32). 시연용 단순 방식.


def get_conn():
    conn = connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def current_project(request: Request) -> int:
    pid = request.cookies.get(COOKIE)
    if not pid:
        raise HTTPException(status_code=401, detail="로그인이 필요해요")
    return int(pid)


def engine_tick(conn, project_id: int):
    """시뮬레이션 1초마다 불리는 콜백. 2주차에 체결 엔진(지정가 체결, 손절·목표가 도달)을 연결한다."""
    def on_second(t: datetime) -> None:
        pass
    return on_second


# ---------- 화면 ----------
@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    if request.cookies.get(COOKIE):
        return RedirectResponse("/home", status_code=303)
    return templates.TemplateResponse(request, "login.html")


@app.post("/guest")
def start_as_guest(conn=Depends(get_conn)):
    user_id = create_guest(conn)
    resp = RedirectResponse("/start", status_code=303)
    resp.set_cookie("rapi_user", str(user_id), max_age=60 * 60 * 24 * 60)
    return resp


@app.get("/start", response_class=HTMLResponse)
def choose_period(request: Request, conn=Depends(get_conn)):
    periods = conn.execute(
        "SELECT p.period_id, p.label, p.trading_days, COUNT(s.stock_code) AS n_stocks "
        "FROM replay_periods p LEFT JOIN replay_stocks s USING (period_id) "
        "GROUP BY p.period_id ORDER BY p.period_id"
    ).fetchall()
    return templates.TemplateResponse(request, "start.html", {"periods": periods})


@app.post("/start/{period_id}")
def start_project(period_id: int, request: Request, conn=Depends(get_conn)):
    user_id = request.cookies.get("rapi_user")
    if not user_id:
        return RedirectResponse("/", status_code=303)
    try:
        project_id = create_project(conn, int(user_id), period_id)
    except ProjectError as e:
        raise HTTPException(status_code=409, detail=str(e))
    resp = RedirectResponse("/home", status_code=303)
    resp.set_cookie(COOKIE, str(project_id), max_age=60 * 60 * 24 * 60)
    return resp


@app.get("/home", response_class=HTMLResponse)
def home(request: Request, conn=Depends(get_conn), project_id: int = Depends(current_project)):
    clock = load_clock(conn, project_id)
    scores = scores_for_project(conn, project_id, published_only=True)   # 장중에는 공개된 감점만
    cash = conn.execute("SELECT cash FROM accounts WHERE project_id = ?", (project_id,)).fetchone()[0]
    return templates.TemplateResponse(request, "home.html", {
        "clock": clock_view(clock), "scores": scores, "cash": cash,
    })


# ---------- 시계 API (상단 시계 바가 1초마다 호출) ----------
@app.get("/api/clock")
def get_clock(conn=Depends(get_conn), project_id: int = Depends(current_project)):
    clock = load_clock(conn, project_id)
    clock.advance(datetime.now(), engine_tick(conn, project_id))
    save_clock(conn, project_id, clock)
    return clock_view(clock)


@app.post("/api/clock/{action}")
def control_clock(action: str, speed: int | None = None,
                  conn=Depends(get_conn), project_id: int = Depends(current_project)):
    clock = load_clock(conn, project_id)
    now, tick = datetime.now(), engine_tick(conn, project_id)
    try:
        if action == "open":
            clock.open_market(now)
        elif action == "pause":
            clock.pause(now, tick)
        elif action == "resume":
            clock.resume(now)
        elif action == "speed" and speed:
            clock.set_speed(speed, now, tick)
        elif action == "skip":
            clock.skip_to_close(tick)
        elif action == "next":
            clock.next_day()
        else:
            raise HTTPException(status_code=400, detail=f"알 수 없는 조작: {action}")
    except ClockError as e:
        return JSONResponse({"error": str(e)}, status_code=409)
    save_clock(conn, project_id, clock)
    # 장 마감에 닿았다면 3주차에 '장 마감 처리 순서'(명세서 10-2)를 여기서 실행한다.
    return clock_view(clock)
