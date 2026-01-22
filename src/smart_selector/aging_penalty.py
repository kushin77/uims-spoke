"""
Aging Penalty System - FAANG-Grade Issue Priority Management

Implements exponential aging penalties to prevent technical debt accumulation.
Ancient issues get exponentially higher scores to force resolution.

Tiers:
- 0-7 days: 1.0x (baseline - fresh issues)
- 8-14 days: 1.5x (gentle reminder)
- 15-30 days: 3.0x (yellow zone - needs attention)
- 31-60 days: 10.0x (red zone - serious debt)
- 61-90 days: 50.0x (crisis - auto-escalate to leadership)
- 90+ days: 100.0x (postmortem required)

Auto-escalation rules:
- 30+ day P0 issues → Page oncall immediately
- 60+ day issues → Notify leadership (any priority)
- 90+ day issues → Create postmortem issue automatically
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class AgingTier(Enum):
    """Aging tier classification with exponential multipliers."""
    FRESH = (0, 7, 1.0, "Fresh")           # 0-7 days
    REMINDER = (8, 14, 1.5, "Reminder")    # 8-14 days
    YELLOW = (15, 30, 3.0, "Yellow Zone")  # 15-30 days
    RED = (31, 60, 10.0, "Red Zone")       # 31-60 days
    CRISIS = (61, 90, 50.0, "Crisis")      # 61-90 days
    POSTMORTEM = (91, float('inf'), 100.0, "Postmortem Required")  # 90+ days

    def __init__(self, min_days: int, max_days: float, multiplier: float, label: str):
        self.min_days = min_days
        self.max_days = max_days
        self.multiplier = multiplier
        self.label = label

    @classmethod
    def from_age_days(cls, age_days: int) -> "AgingTier":
        """Get aging tier for given age in days."""
        for tier in cls:
            if tier.min_days <= age_days <= tier.max_days:
                return tier
        return cls.POSTMORTEM  # Default for very old issues


@dataclass
class AgingPenaltyResult:
    """Result of aging penalty calculation."""
    age_days: int
    tier: AgingTier
    multiplier: float
    base_score: float
    aged_score: float
    escalation_required: bool
    escalation_action: Optional[str] = None
    postmortem_required: bool = False


class AgingPenaltyCalculator:
    """
    Calculates exponential aging penalties for issue prioritization.
    
    Features:
    - Exponential tier-based multipliers (1x → 100x)
    - Auto-escalation triggers (30d P0, 60d any, 90d postmortem)
    - Priority-aware escalation (P0 issues escalate faster)
    - Dashboard-ready metrics
    """

    # Escalation thresholds (in days)
    P0_ONCALL_THRESHOLD = 30  # Page oncall for P0 issues older than 30 days
    LEADERSHIP_NOTIFICATION_THRESHOLD = 60  # Notify leadership for any issue 60+ days
    POSTMORTEM_THRESHOLD = 90  # Create postmortem for 90+ day issues

    def __init__(self):
        """Initialize aging penalty calculator."""
        pass

    def calculate(
        self,
        created_at: datetime,
        base_score: float,
        priority: str = "P2",
        now: Optional[datetime] = None
    ) -> AgingPenaltyResult:
        """
        Calculate aging penalty for an issue.

        Args:
            created_at: Issue creation timestamp (timezone-aware)
            base_score: Base priority score before aging
            priority: Issue priority (P0, P1, P2, P3)
            now: Current time (defaults to now, used for testing)

        Returns:
            AgingPenaltyResult with multiplier and escalation flags

        Example:
            >>> calc = AgingPenaltyCalculator()
            >>> created_at = datetime(2025, 10, 15, tzinfo=timezone.utc)
            >>> now = datetime(2026, 1, 22, tzinfo=timezone.utc)
            >>> result = calc.calculate(created_at, base_score=10.0, priority="P1", now=now)
            >>> result.tier
            <AgingTier.POSTMORTEM: ...>
            >>> result.multiplier
            100.0
            >>> result.aged_score
            1000.0
        """
        if now is None:
            now = datetime.now(timezone.utc)

        # Ensure both datetimes are timezone-aware
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        # Calculate age in days
        age_delta = now - created_at
        age_days = age_delta.days

        # Get aging tier and multiplier
        tier = AgingTier.from_age_days(age_days)
        multiplier = tier.multiplier

        # Calculate aged score
        aged_score = base_score * multiplier

        # Determine escalation requirements
        escalation_required, escalation_action = self._check_escalation(
            age_days, priority
        )
        postmortem_required = age_days >= self.POSTMORTEM_THRESHOLD

        return AgingPenaltyResult(
            age_days=age_days,
            tier=tier,
            multiplier=multiplier,
            base_score=base_score,
            aged_score=aged_score,
            escalation_required=escalation_required,
            escalation_action=escalation_action,
            postmortem_required=postmortem_required
        )

    def _check_escalation(self, age_days: int, priority: str) -> tuple[bool, Optional[str]]:
        """
        Check if escalation is required based on age and priority.

        Returns:
            (escalation_required, escalation_action)
        """
        # P0 issues: Page oncall at 30 days
        if priority == "P0" and age_days >= self.P0_ONCALL_THRESHOLD:
            return True, f"PAGE_ONCALL (P0 issue {age_days} days old)"

        # Any priority: Notify leadership at 60 days
        if age_days >= self.LEADERSHIP_NOTIFICATION_THRESHOLD:
            return True, f"NOTIFY_LEADERSHIP ({priority} issue {age_days} days old)"

        return False, None

    def get_aging_distribution(self, issues: list[dict]) -> dict[str, int]:
        """
        Calculate distribution of issues across aging tiers.

        Args:
            issues: List of issue dicts with 'created_at' field

        Returns:
            Dict mapping tier labels to issue counts

        Example:
            >>> calc = AgingPenaltyCalculator()
            >>> issues = [
            ...     {"created_at": datetime(2026, 1, 15, tzinfo=timezone.utc)},  # 7 days
            ...     {"created_at": datetime(2025, 12, 1, tzinfo=timezone.utc)},  # 52 days
            ... ]
            >>> distribution = calc.get_aging_distribution(issues)
            >>> distribution
            {'Fresh': 1, 'Red Zone': 1, ...}
        """
        now = datetime.now(timezone.utc)
        distribution = {tier.label: 0 for tier in AgingTier}

        for issue in issues:
            created_at = issue.get("created_at")
            if created_at:
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                age_days = (now - created_at).days
                tier = AgingTier.from_age_days(age_days)
                distribution[tier.label] += 1

        return distribution


def calculate_aging_penalty(
    created_at: datetime,
    base_score: float,
    priority: str = "P2"
) -> float:
    """
    Convenience function to calculate aged score.

    Args:
        created_at: Issue creation timestamp
        base_score: Base priority score
        priority: Issue priority (P0, P1, P2, P3)

    Returns:
        Aged score with multiplier applied

    Example:
        >>> from datetime import datetime, timezone
        >>> created_at = datetime(2025, 10, 1, tzinfo=timezone.utc)
        >>> aged_score = calculate_aging_penalty(created_at, base_score=10.0)
        >>> aged_score > 100.0  # 100+ days old = 100x multiplier
        True
    """
    calculator = AgingPenaltyCalculator()
    result = calculator.calculate(created_at, base_score, priority)
    return result.aged_score
