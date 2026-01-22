from src.smart_selector.scorer import composite_score


def test_composite_score_basic():
    issue = {
        "days_open": 10,
        "priority_level": 0,  # P0
        "cost_impact": 500.0,
        "blocker_count": 0,
        "team_velocity": 0.8,
    }
    score = composite_score(issue)
    assert score > 0
    assert score <= 100
