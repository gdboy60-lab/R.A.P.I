from app.rules.catalog import RULES, area_scores


def test_14_rules_and_areas():
    assert len(RULES) == 14
    assert sum(r.area == "BC" for r in RULES.values()) == 3


def test_scores_floor_and_average():
    # 시안 예시: RM-03 -20, PA-04 -20 → RM 80, PA 80
    s = area_scores([("RM", 20), ("PA", 20)])
    assert s["RM"] == 80 and s["PA"] == 80 and s["overall"] == 90
    assert area_scores([("MC", 25)] * 5)["MC"] == 0          # 0점 아래로 내려가지 않음
