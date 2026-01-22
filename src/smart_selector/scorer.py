"""Smart Selector scoring with Phase 1 enhancements.

Composites signals from:
- Aging penalty (exponential multiplier for old issues)
- SLA tracking (urgency based on priority SLA window)
- Dependency graph (blocked/blocking status)
- Original signals: age, priority, impact, blockers, velocity

All normalized to [0,1] and combined with configurable weights.
"""

import math
from datetime import datetime, timezone
from typing import Optional, Dict
from src.smart_selector.aging_penalty import AgingPenaltyCalculator
from src.sla_tracker.tracker import SLATracker, Priority as SLAPriority

# Example normalized composite scorer used by smart_selector service.
# We normalize signals to [0,1] and combine with weights stored in env/Secret Manager.

DEFAULT_WEIGHTS = {
    "age": 0.15,           # Reduced from 0.25 (aging penalty replaces some age scoring)
    "priority": 0.25,
    "impact": 0.15,
    "blocker": 0.10,
    "velocity": 0.10,
    "aging_penalty": 0.15,  # NEW: Exponential penalty for very old issues
    "sla_urgency": 0.10,    # NEW: How close to SLA breach
}


def normalize_age(days_open: int) -> float:
    """Normalize age to [0, 1], capped at 90 days."""
    return min(days_open / 90.0, 1.0)


def normalize_priority(priority_level: int) -> float:
    """Normalize priority: 0 (P0) .. 3 (P3) -> invert so 0 -> 1.0"""
    return max(0.0, (4 - priority_level) / 4.0)


def normalize_impact(cost_usd: float) -> float:
    """Normalize cost impact, cap at $10k."""
    return min(cost_usd / 10000.0, 1.0)


def blocker_penalty(blocker_count: int) -> float:
    """Penalty for blocked issues (can't be assigned)."""
    return 1.0 / (1.0 + blocker_count)


def velocity_score(velocity_percentile: float) -> float:
    """Expect 0..1 value; higher means team clears issues faster."""
    return max(0.0, min(1.0, velocity_percentile))


def aging_penalty_score(issue: dict, now: Optional[datetime] = None) -> tuple:
    """Calculate aging penalty boost score.
    
    Args:
        issue: Issue dict with 'created_at' and optional 'priority' (0-3)
        now: Current time (defaults to UTC now)
    
    Returns:
        Tuple of (multiplier, normalized_score)
    """
    if "created_at" not in issue:
        return 1.0, 0.0  # No created date = no penalty
    
    if now is None:
        now = datetime.now(timezone.utc)
    
    created_at = issue["created_at"]
    if isinstance(created_at, str):
        created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    
    priority_str = ["P0", "P1", "P2", "P3"][issue.get("priority", 2)]
    
    calculator = AgingPenaltyCalculator()
    result = calculator.calculate(
        created_at=created_at,
        base_score=1.0,
        priority=priority_str,
        now=now
    )
    
    # Normalize multiplier to [0, 1]
    normalized = min(1.0, (result.multiplier - 1.0) / 99.0)
    
    return result.multiplier, normalized


def sla_urgency_score(issue: dict, now: Optional[datetime] = None) -> float:
    """Calculate SLA urgency score based on time remaining."""
    if "created_at" not in issue:
        return 0.0
    
    if now is None:
        now = datetime.now(timezone.utc)
    
    created_at = issue["created_at"]
    if isinstance(created_at, str):
        created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    
    sla_priority_map = {0: SLAPriority.P0, 1: SLAPriority.P1, 2: SLAPriority.P2, 3: SLAPriority.P3}
    sla_priority = sla_priority_map.get(issue.get("priority", 2), SLAPriority.P2)
    
    tracker = SLATracker()
    result = tracker.check_issue_sla(
        issue_number=issue.get("number", 0),
        priority=sla_priority,
        created_at=created_at,
        now=now
    )
    
    # Convert percent_elapsed to urgency: 0% -> 0.0, 100% -> 1.0
    urgency = min(1.0, result.percent_elapsed / 100.0)
    
    return urgency


def blocking_status_score(issue: dict) -> tuple:
    """Score based on blocking/blocked status."""
    is_blocked = issue.get("is_blocked", False)
    blocks_count = issue.get("blocks_count", 0)
    
    can_assign = not is_blocked
    penalty = 1.0 / (1.0 + blocks_count)
    
    return penalty, can_assign


def composite_score(issue: dict, weights: dict = None, now: Optional[datetime] = None) -> float:
    """Compute composite UIMS score with Phase 1 enhancements."""
    w = weights or DEFAULT_WEIGHTS
    if now is None:
        now = datetime.now(timezone.utc)
    
    # Original signals
    a = normalize_age(issue.get("days_open", 0))
    p = normalize_priority(issue.get("priority", 3))
    i = normalize_impact(issue.get("cost_impact", 0.0))
    b = blocker_penalty(issue.get("blocker_count", 0))
    v = velocity_score(issue.get("team_velocity", 0.5))
    
    # Phase 1 signals
    aging_mult, ap = aging_penalty_score(issue, now)
    su = sla_urgency_score(issue, now)
    block_penalty, can_assign = blocking_status_score(issue)
    
    # If blocked, reduce score significantly
    if not can_assign:
        block_penalty = 0.2
    
    score = (
        w.get("age", 0.15) * a
        + w.get("priority", 0.25) * p
        + w.get("impact", 0.15) * i
        + w.get("blocker", 0.10) * block_penalty
        + w.get("velocity", 0.10) * v
        + w.get("aging_penalty", 0.15) * ap
        + w.get("sla_urgency", 0.10) * su
    )
    
    # Normalize to 0..100
    normalized_score = round(score * 100, 2)
    return min(100.0, max(0.0, normalized_score))
