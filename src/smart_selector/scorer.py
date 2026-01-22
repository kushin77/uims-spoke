import math

# Example normalized composite scorer used by smart_selector service.
# We normalize signals to [0,1] and combine with weights stored in env/Secret Manager.

DEFAULT_WEIGHTS = {
    "age": 0.25,
    "priority": 0.35,
    "impact": 0.20,
    "blocker": 0.10,
    "velocity": 0.10,
}


def normalize_age(days_open: int) -> float:
    return min(days_open / 90.0, 1.0)


def normalize_priority(priority_level: int) -> float:
    # Assume priority_level: 0 (P0) .. 3 (P3) -> invert so 0 -> 1.0
    return max(0.0, (4 - priority_level) / 4.0)


def normalize_impact(cost_usd: float) -> float:
    # Cap at $10k
    return min(cost_usd / 10000.0, 1.0)


def blocker_penalty(blocker_count: int) -> float:
    return 1.0 / (1.0 + blocker_count)


def velocity_score(velocity_percentile: float) -> float:
    # Expect 0..1 value; higher means team clears issues faster
    return max(0.0, min(1.0, velocity_percentile))


def composite_score(issue: dict, weights: dict = None) -> float:
    w = weights or DEFAULT_WEIGHTS
    a = normalize_age(issue.get("days_open", 0))
    p = normalize_priority(issue.get("priority_level", 3))
    i = normalize_impact(issue.get("cost_impact", 0.0))
    b = blocker_penalty(issue.get("blocker_count", 0))
    v = velocity_score(issue.get("team_velocity", 0.5))

    score = (
        w["age"] * a
        + w["priority"] * p
        + w["impact"] * i
        + w["blocker"] * b
        + w["velocity"] * v
    )
    # normalize to 0..100
    return round(score * 100, 2)
