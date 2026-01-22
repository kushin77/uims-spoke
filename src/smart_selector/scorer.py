"""Smart Selector scoring with Phase 1 & 2 enhancements.

Composites signals from:
- Phase 1: Aging penalty, SLA tracking, Dependency graph
- Phase 2: Semantic clustering (duplicate detection)
- Original signals: age, priority, impact, blockers, velocity

All normalized to [0,1] and combined with configurable weights.
"""

import math
from datetime import datetime, timezone
from typing import Optional, Dict
from src.smart_selector.aging_penalty import AgingPenaltyCalculator
from src.sla_tracker.tracker import SLATracker, Priority as SLAPriority

# Updated weights with clustering (0.10 for cluster_score)
DEFAULT_WEIGHTS = {
    "age": 0.15,           # Age of issue
    "priority": 0.25,      # Issue priority level
    "impact": 0.15,        # Cost impact
    "blocker": 0.10,       # Blocking/blocked status
    "velocity": 0.10,      # Team velocity
    "aging_penalty": 0.10, # Exponential penalty for old issues
    "sla_urgency": 0.10,   # SLA breach urgency
    "clustering": 0.05,    # Duplicate/cluster membership (NEW)
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


def cluster_score(issue: dict, cluster_info: Optional[Dict] = None) -> float:
    """Calculate clustering score based on duplicate cluster membership.
    
    Small clusters (1-2 members, unique issues) = higher score (1.0-0.8)
    Large clusters (10+ members, likely duplicates) = lower score (0.3-0.0)
    
    Rationale:
    - Unique issues (cluster_size=1) should be prioritized
    - Duplicate issues should be deprioritized in favor of primary
    
    Args:
        issue: Issue dict
        cluster_info: Optional {cluster_id, members_count, is_primary}
    
    Returns:
        Float in [0, 1]
    """
    if cluster_info is None:
        return 0.5  # Default: no cluster info = neutral score
    
    members_count = cluster_info.get("members_count", 1)
    is_primary = cluster_info.get("is_primary", True)
    
    # If issue is in a cluster and not primary, lower score
    if not is_primary and members_count > 1:
        # Duplicate: scale down significantly
        return max(0.0, 0.4 - (members_count / 50.0))
    
    # Primary or small cluster: scale up
    if members_count <= 1:
        return 1.0  # Unique issue, highest priority
    elif members_count <= 3:
        return 0.8  # Small cluster, mostly unique
    elif members_count <= 10:
        return 0.5  # Medium cluster
    else:
        return 0.3  # Large cluster (likely all similar)


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


def composite_score(
    issue: dict,
    weights: dict = None,
    now: Optional[datetime] = None,
    cluster_info: Optional[Dict] = None
) -> float:
    """Compute composite UIMS score with Phase 1 & 2 enhancements.
    
    Args:
        issue: Issue dict with all fields
        weights: Custom weights dict (uses DEFAULT_WEIGHTS if None)
        now: Current time (defaults to UTC now)
        cluster_info: Optional clustering metadata {cluster_id, members_count, is_primary}
    
    Returns:
        Score normalized to [0, 100]
    """
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
    
    # Phase 2 signals
    cs = cluster_score(issue, cluster_info)
    
    # If blocked, reduce score significantly
    if not can_assign:
        block_penalty = 0.2
    
    score = (
        w.get("age", 0.15) * a
        + w.get("priority", 0.25) * p
        + w.get("impact", 0.15) * i
        + w.get("blocker", 0.10) * block_penalty
        + w.get("velocity", 0.10) * v
        + w.get("aging_penalty", 0.10) * ap
        + w.get("sla_urgency", 0.10) * su
        + w.get("clustering", 0.05) * cs
    )
    
    # Normalize to 0..100
    normalized_score = round(score * 100, 2)
    return min(100.0, max(0.0, normalized_score))
