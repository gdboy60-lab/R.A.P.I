"""시뮬레이션 시계를 projects 테이블에서 읽고 저장한다."""
from __future__ import annotations

from datetime import date, datetime, time

from .clock import SimClock, TradingDay


def load_days(conn, period_id: int) -> list[TradingDay]:
    rows = conn.execute(
        """SELECT c.date, c.open_time, c.close_time
             FROM replay_periods p
             JOIN market_calendar c ON c.date BETWEEN p.start_date AND p.end_date
            WHERE p.period_id = ? AND c.is_open = 1
            ORDER BY c.date""",
        (period_id,),
    ).fetchall()
    return [TradingDay(date.fromisoformat(r[0]), time.fromisoformat(r[1]), time.fromisoformat(r[2]))
            for r in rows]


def load_clock(conn, project_id: int) -> SimClock:
    p = conn.execute(
        """SELECT period_id, current_day, clock_status, sim_now, playback_speed, last_real_tick
             FROM projects WHERE project_id = ?""",
        (project_id,),
    ).fetchone()
    if p is None:
        raise KeyError(f"프로젝트 {project_id} 가 없어요")
    return SimClock(
        days=load_days(conn, p["period_id"]),
        day_index=p["current_day"] - 1,
        status=p["clock_status"],
        sim_now=datetime.fromisoformat(p["sim_now"]),
        speed=p["playback_speed"],
        last_real_tick=datetime.fromisoformat(p["last_real_tick"]) if p["last_real_tick"] else None,
    )


def save_clock(conn, project_id: int, clock: SimClock) -> None:
    conn.execute(
        """UPDATE projects
              SET current_day = ?, clock_status = ?, sim_now = ?, playback_speed = ?, last_real_tick = ?
            WHERE project_id = ?""",
        (clock.day_number, clock.status, clock.sim_now.isoformat(), clock.speed,
         clock.last_real_tick.isoformat() if clock.last_real_tick else None, project_id),
    )


def clock_view(clock: SimClock, hide_dates: bool = True) -> dict:
    """화면 상단 시계 바에 보낼 값."""
    return {
        "day": clock.day_number,
        "total_days": len(clock.days),
        "date": None if hide_dates else clock.today.date.isoformat(),
        "time": clock.sim_now.strftime("%H:%M"),
        "status": clock.status,
        "speed": clock.speed,
        "is_last_day": clock.is_last_day,
    }
