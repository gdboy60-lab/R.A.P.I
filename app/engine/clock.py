"""시뮬레이션 시계 (명세서 10-1).

- 프로젝트마다 시계가 하나씩 있다.
- 장중에는 배속(기본 10배속)으로 흐르고, 일시정지·건너뛰기·다음 거래일 진행을 지원한다.
- 앱을 닫으면 시계가 멈춘다: 화면이 주기적으로 시계를 불러 진행시키는데,
  한 번에 진행시킬 수 있는 실제 시간을 MAX_REAL_GAP 으로 제한하기 때문이다.
  화면이 닫혀 호출이 끊기면 그 사이 시간은 흐르지 않는다.
- 판정은 모두 시뮬레이션 시각 기준이다. 체결 엔진·규칙 엔진은 on_second 콜백으로
  시뮬레이션 1초마다 불려서 지정가 체결, 손절·목표가 도달을 검사한다.

이 모듈은 데이터베이스를 모른다. 상태를 받아 계산만 하고, 저장은 호출한 쪽이 한다.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Callable, Optional

MAX_REAL_GAP = timedelta(seconds=5)   # 한 번의 진행에서 인정하는 최대 실제 경과 시간
DEFAULT_SPEED = 10

PRE_OPEN, RUNNING, PAUSED, CLOSED = "pre_open", "running", "paused", "closed"

OnSecond = Optional[Callable[[datetime], None]]


@dataclass(frozen=True)
class TradingDay:
    date: date
    open_time: time = time(9, 0)
    close_time: time = time(15, 30)

    @property
    def open_at(self) -> datetime:
        return datetime.combine(self.date, self.open_time)

    @property
    def close_at(self) -> datetime:
        return datetime.combine(self.date, self.close_time)


class ClockError(Exception):
    """지금 상태에서 할 수 없는 조작."""


@dataclass
class SimClock:
    days: list[TradingDay]            # 리플레이 기간의 개장일 (순서대로)
    day_index: int = 0                # 0 = 1일차
    status: str = PRE_OPEN
    sim_now: Optional[datetime] = None
    speed: int = DEFAULT_SPEED
    last_real_tick: Optional[datetime] = None

    def __post_init__(self) -> None:
        if not self.days:
            raise ValueError("개장일이 하나도 없어요")
        if self.sim_now is None:
            self.sim_now = self.today.open_at

    # ---------- 조회 ----------
    @property
    def today(self) -> TradingDay:
        return self.days[self.day_index]

    @property
    def day_number(self) -> int:
        """화면에 보이는 'N일차'."""
        return self.day_index + 1

    @property
    def is_last_day(self) -> bool:
        return self.day_index == len(self.days) - 1

    def elapsed_ratio(self) -> float:
        """장 경과 시간 ÷ 전체 장 시간 (MC-02)."""
        total = (self.today.close_at - self.today.open_at).total_seconds()
        done = (self.sim_now - self.today.open_at).total_seconds()
        return max(0.0, min(1.0, done / total))

    # ---------- 조작 ----------
    def open_market(self, real_now: datetime) -> None:
        """장 시작 전 → 장중."""
        self._require(PRE_OPEN)
        self.sim_now = self.today.open_at
        self.status = RUNNING
        self.last_real_tick = real_now

    def advance(self, real_now: datetime, on_second: OnSecond = None) -> bool:
        """실제 경과 시간 × 배속만큼 진행한다. 장 마감에 닿으면 True."""
        if self.status != RUNNING:
            return False
        real_gap = min(real_now - self.last_real_tick, MAX_REAL_GAP)
        self.last_real_tick = real_now
        if real_gap <= timedelta(0):
            return False
        return self._run_to(self.sim_now + real_gap * self.speed, on_second)

    def pause(self, real_now: datetime, on_second: OnSecond = None) -> None:
        self._require(RUNNING)
        self.advance(real_now, on_second)
        if self.status == RUNNING:
            self.status = PAUSED

    def resume(self, real_now: datetime) -> None:
        self._require(PAUSED)
        self.status = RUNNING
        self.last_real_tick = real_now

    def set_speed(self, speed: int, real_now: datetime, on_second: OnSecond = None) -> None:
        if speed <= 0:
            raise ValueError("속도는 1 이상이어야 해요")
        if self.status == RUNNING:
            self.advance(real_now, on_second)   # 바꾸기 전까지는 이전 속도로 계산
        self.speed = speed

    def skip_to_close(self, on_second: OnSecond = None) -> None:
        """남은 장 시간을 1초씩 고속 처리한다 (바로 점프하지 않음, 명세서 10-1)."""
        if self.status not in (RUNNING, PAUSED):
            raise ClockError(f"장중이 아니라 건너뛸 수 없어요 (현재: {self.status})")
        self._run_to(self.today.close_at, on_second)

    def next_day(self) -> None:
        """장 마감 결과 화면에서만 호출. 다음 개장일의 장 시작 전으로 간다."""
        self._require(CLOSED)
        if self.is_last_day:
            raise ClockError("마지막 거래일이에요. 최종 리포트로 넘어가야 해요")
        self.day_index += 1
        self.sim_now = self.today.open_at
        self.status = PRE_OPEN
        self.last_real_tick = None

    # ---------- 내부 ----------
    def _run_to(self, target: datetime, on_second: OnSecond) -> bool:
        close_at = self.today.close_at
        target = min(target, close_at)
        if on_second is not None:
            # sim_now 다음의 정수 초부터 target 까지 1초 단위로 콜백
            t = self.sim_now.replace(microsecond=0) + timedelta(seconds=1)
            while t <= target:
                on_second(t)
                t += timedelta(seconds=1)
        self.sim_now = target
        if target >= close_at:
            self.status = CLOSED
            return True
        return False

    def _require(self, status: str) -> None:
        if self.status != status:
            raise ClockError(f"'{status}' 상태에서만 할 수 있어요 (현재: {self.status})")
