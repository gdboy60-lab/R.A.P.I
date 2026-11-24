"""체험 계정과 프로젝트 만들기 (FR-01~04, FR-32)."""
from __future__ import annotations

import sqlite3

from .engine.clock_store import load_days

INITIAL_CASH = 10_000_000


class ProjectError(Exception):
    pass


def create_guest(conn) -> int:
    cur = conn.execute("INSERT INTO users (nickname, is_guest) VALUES ('체험 사용자', 1)")
    return cur.lastrowid


def create_project(conn, user_id: int, period_id: int) -> int:
    """리플레이 기간을 골라 프로젝트와 1,000만 원 계좌를 만든다. 1일차 장 시작 전 상태로 시작."""
    days = load_days(conn, period_id)
    if len(days) < 10:
        raise ProjectError("리플레이 기간의 개장일이 10일보다 적어요")
    try:
        cur = conn.execute(
            """INSERT INTO projects
                   (user_id, period_id, start_date, end_date, total_trading_days,
                    baseline_end_date, sim_now)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, period_id, days[0].date.isoformat(), days[-1].date.isoformat(),
             len(days), days[4].date.isoformat(), days[0].open_at.isoformat()),
        )
    except sqlite3.IntegrityError as e:
        if "uq_one_live_project" in str(e) or "projects.user_id" in str(e):
            raise ProjectError("이미 진행 중인 프로젝트가 있어요") from e
        raise
    project_id = cur.lastrowid
    conn.execute("INSERT INTO accounts (project_id, cash) VALUES (?, ?)", (project_id, INITIAL_CASH))
    return project_id
