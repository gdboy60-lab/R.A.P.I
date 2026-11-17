"""14개 규칙 목록과 점수 계산 (명세서 1장, 3~6장).

각 규칙의 판정 로직은 2~3주차에 rules/ 아래 파일로 하나씩 추가한다.
여기에는 모든 규칙이 공통으로 쓰는 정보(영역, 감점, 판정 단위, 판정 시점)만 둔다.
"""
from __future__ import annotations

from dataclasses import dataclass

AREAS = ("RM", "PA", "BC", "MC")


@dataclass(frozen=True)
class Rule:
    rule_id: str
    area: str
    name: str
    penalty: int
    target: str      # 'trade' = 거래 단위, 'day' = 하루 단위
    when: str        # 판정 시점 (명세서 10-2)


RULES: dict[str, Rule] = {r.rule_id: r for r in [
    Rule("RM-01", "RM", "단일 종목 집중 투자", 15, "trade", "buy_fill"),
    Rule("RM-02", "RM", "올인 매수", 30, "trade", "buy_fill"),
    Rule("RM-03", "RM", "손절 기준 미준수", 20, "trade", "market_close"),
    Rule("RM-04", "RM", "한 번에 목표 수량 매수", 10, "trade", "buy_fill"),
    Rule("PA-01", "PA", "매매 계획 누락", 30, "trade", "buy_fill"),
    Rule("PA-02", "PA", "목표가 도달 전 조기 매도", 15, "trade", "trade_close"),
    Rule("PA-03", "PA", "손절 기준 도달 후 추가 매수", 25, "trade", "buy_fill"),
    Rule("PA-04", "PA", "계획 외 급등 종목 매수", 20, "trade", "buy_fill"),
    Rule("BC-01", "BC", "평소보다 과도한 거래", 20, "day", "market_close"),
    Rule("BC-02", "BC", "연속 손실 후 재매수", 25, "trade", "buy_fill"),
    Rule("BC-03", "BC", "짧은 시간 내 반복 매매", 15, "day", "trade_close"),
    Rule("MC-01", "MC", "과매수 구간 진입", 25, "trade", "buy_fill"),
    Rule("MC-02", "MC", "거래량 부족", 10, "trade", "buy_fill"),
    Rule("MC-03", "MC", "이동평균선 대비 과도한 상승", 20, "trade", "buy_fill"),
]}

assert len(RULES) == 14


def area_scores(penalties: list[tuple[str, int]]) -> dict[str, float]:
    """(영역, 감점) 목록 → 영역별 점수와 전체 점수.

    영역 점수 = max(0, 100 - 감점 합계), 전체 = 네 영역 산술평균.
    판정 기록에서 result='violation' 인 행만 넘긴다.
    """
    totals = {a: 0 for a in AREAS}
    for area, penalty in penalties:
        totals[area] += penalty
    scores: dict[str, float] = {a: float(max(0, 100 - totals[a])) for a in AREAS}
    scores["overall"] = sum(scores[a] for a in AREAS) / len(AREAS)
    return scores


def scores_for_project(conn, project_id: int, published_only: bool = False) -> dict[str, float]:
    """rule_evaluations 에서 점수를 계산한다 (판정 기록이 유일한 원본).

    published_only=True 이면 장 마감에 공개된 감점만 반영한다 (장중 화면용, 명세서 10-3).
    """
    sql = ("SELECT area, penalty FROM rule_evaluations "
           "WHERE project_id = ? AND result = 'violation'")
    if published_only:
        sql += " AND published = 1"
    rows = conn.execute(sql, (project_id,)).fetchall()
    return area_scores([(r[0], r[1]) for r in rows])
