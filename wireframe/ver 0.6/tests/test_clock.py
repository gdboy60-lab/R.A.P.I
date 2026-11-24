"""시뮬레이션 시계 (명세서 10-1)."""
from datetime import date, datetime, timedelta
import pytest
from app.engine.clock import CLOSED, PAUSED, PRE_OPEN, RUNNING, ClockError, SimClock, TradingDay
from app.engine.clock_store import load_clock, save_clock
from app.projects import create_guest, create_project

T0 = datetime(2026, 11, 17, 10, 0, 0)          # 실제 시각
DAYS = [TradingDay(date(2024, 3, 4 + i)) for i in range(5)] + \
       [TradingDay(date(2024, 3, 11 + i)) for i in range(5)]


def opened():
    c = SimClock(days=DAYS)
    c.open_market(T0)
    return c


def test_10x_speed():
    c = opened()
    c.advance(T0 + timedelta(seconds=1))
    assert c.sim_now == datetime(2024, 3, 4, 9, 0, 10)   # 실제 1초 = 시뮬레이션 10초


def test_closed_app_stops_clock():
    c = opened()
    c.advance(T0 + timedelta(hours=1))                     # 1시간 동안 호출 없음
    assert c.sim_now == datetime(2024, 3, 4, 9, 0, 50)     # 최대 5초 × 10배만 인정


def test_pause_stops_time():
    c = opened()
    c.pause(T0 + timedelta(seconds=1))
    c.advance(T0 + timedelta(seconds=3))
    assert c.status == PAUSED and c.sim_now == datetime(2024, 3, 4, 9, 0, 10)
    c.resume(T0 + timedelta(seconds=60))
    c.advance(T0 + timedelta(seconds=61))
    assert c.sim_now == datetime(2024, 3, 4, 9, 0, 20)     # 멈춘 동안은 흐르지 않음


def test_skip_processes_every_second():
    c = opened()
    seen = []
    c.skip_to_close(seen.append)
    assert c.status == CLOSED
    assert len(seen) == 6 * 3600 + 30 * 60                 # 09:00:01 ~ 15:30:00, 23,400초
    assert seen[-1] == datetime(2024, 3, 4, 15, 30)


def test_advance_stops_at_close():
    c = opened()
    c.sim_now = datetime(2024, 3, 4, 15, 29, 55)
    assert c.advance(T0 + timedelta(seconds=1)) is True
    assert c.status == CLOSED and c.sim_now == datetime(2024, 3, 4, 15, 30)


def test_next_day_only_after_close_and_not_on_last_day():
    c = opened()
    with pytest.raises(ClockError):
        c.next_day()
    c.skip_to_close()
    c.next_day()
    assert c.day_number == 2 and c.status == PRE_OPEN and c.sim_now == datetime(2024, 3, 5, 9, 0)
    c.day_index = 9
    c.status = CLOSED
    with pytest.raises(ClockError):
        c.next_day()


def test_round_trip_through_db(conn, period_id):
    pid = create_project(conn, create_guest(conn), period_id)
    c = load_clock(conn, pid)
    c.open_market(T0)
    c.advance(T0 + timedelta(seconds=2))
    save_clock(conn, pid, c)
    again = load_clock(conn, pid)
    assert again.status == RUNNING and again.sim_now == datetime(2024, 3, 4, 9, 0, 20)
    assert len(again.days) == 10
