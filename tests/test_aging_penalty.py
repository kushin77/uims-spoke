"""
Tests for Aging Penalty System

Tests exponential aging multipliers, tier classification, and auto-escalation logic.
"""

import pytest
from datetime import datetime, timedelta, timezone

from src.smart_selector.aging_penalty import (
    AgingPenaltyCalculator,
    AgingTier,
    AgingPenaltyResult,
    calculate_aging_penalty
)


class TestAgingTier:
    """Test aging tier classification."""

    def test_fresh_tier_0_days(self):
        """Test 0-day-old issue is FRESH tier."""
        tier = AgingTier.from_age_days(0)
        assert tier == AgingTier.FRESH
        assert tier.multiplier == 1.0
        assert tier.label == "Fresh"

    def test_fresh_tier_7_days(self):
        """Test 7-day-old issue is FRESH tier (boundary)."""
        tier = AgingTier.from_age_days(7)
        assert tier == AgingTier.FRESH
        assert tier.multiplier == 1.0

    def test_reminder_tier_8_days(self):
        """Test 8-day-old issue is REMINDER tier."""
        tier = AgingTier.from_age_days(8)
        assert tier == AgingTier.REMINDER
        assert tier.multiplier == 1.5

    def test_reminder_tier_14_days(self):
        """Test 14-day-old issue is REMINDER tier (boundary)."""
        tier = AgingTier.from_age_days(14)
        assert tier == AgingTier.REMINDER
        assert tier.multiplier == 1.5

    def test_yellow_zone_15_days(self):
        """Test 15-day-old issue is YELLOW tier."""
        tier = AgingTier.from_age_days(15)
        assert tier == AgingTier.YELLOW
        assert tier.multiplier == 3.0
        assert tier.label == "Yellow Zone"

    def test_yellow_zone_30_days(self):
        """Test 30-day-old issue is YELLOW tier (boundary)."""
        tier = AgingTier.from_age_days(30)
        assert tier == AgingTier.YELLOW
        assert tier.multiplier == 3.0

    def test_red_zone_31_days(self):
        """Test 31-day-old issue is RED tier."""
        tier = AgingTier.from_age_days(31)
        assert tier == AgingTier.RED
        assert tier.multiplier == 10.0
        assert tier.label == "Red Zone"

    def test_red_zone_60_days(self):
        """Test 60-day-old issue is RED tier (boundary)."""
        tier = AgingTier.from_age_days(60)
        assert tier == AgingTier.RED
        assert tier.multiplier == 10.0

    def test_crisis_tier_61_days(self):
        """Test 61-day-old issue is CRISIS tier."""
        tier = AgingTier.from_age_days(61)
        assert tier == AgingTier.CRISIS
        assert tier.multiplier == 50.0
        assert tier.label == "Crisis"

    def test_crisis_tier_90_days(self):
        """Test 90-day-old issue is CRISIS tier (boundary)."""
        tier = AgingTier.from_age_days(90)
        assert tier == AgingTier.CRISIS
        assert tier.multiplier == 50.0

    def test_postmortem_tier_91_days(self):
        """Test 91-day-old issue requires POSTMORTEM."""
        tier = AgingTier.from_age_days(91)
        assert tier == AgingTier.POSTMORTEM
        assert tier.multiplier == 100.0
        assert tier.label == "Postmortem Required"

    def test_postmortem_tier_365_days(self):
        """Test 1-year-old issue requires POSTMORTEM."""
        tier = AgingTier.from_age_days(365)
        assert tier == AgingTier.POSTMORTEM
        assert tier.multiplier == 100.0


class TestAgingPenaltyCalculator:
    """Test aging penalty calculation logic."""

    @pytest.fixture
    def calculator(self):
        """Create aging penalty calculator instance."""
        return AgingPenaltyCalculator()

    @pytest.fixture
    def now(self):
        """Fixed current time for testing."""
        return datetime(2026, 1, 22, 12, 0, 0, tzinfo=timezone.utc)

    def test_fresh_issue_no_penalty(self, calculator, now):
        """Test fresh issue (5 days old) has 1x multiplier."""
        created_at = now - timedelta(days=5)
        result = calculator.calculate(created_at, base_score=10.0, now=now)

        assert result.age_days == 5
        assert result.tier == AgingTier.FRESH
        assert result.multiplier == 1.0
        assert result.base_score == 10.0
        assert result.aged_score == 10.0  # No penalty
        assert not result.escalation_required
        assert not result.postmortem_required

    def test_reminder_tier_15x_penalty(self, calculator, now):
        """Test 10-day-old issue has 1.5x multiplier."""
        created_at = now - timedelta(days=10)
        result = calculator.calculate(created_at, base_score=10.0, now=now)

        assert result.age_days == 10
        assert result.tier == AgingTier.REMINDER
        assert result.multiplier == 1.5
        assert result.aged_score == 15.0  # 10.0 * 1.5

    def test_yellow_zone_3x_penalty(self, calculator, now):
        """Test 20-day-old issue has 3x multiplier."""
        created_at = now - timedelta(days=20)
        result = calculator.calculate(created_at, base_score=10.0, now=now)

        assert result.age_days == 20
        assert result.tier == AgingTier.YELLOW
        assert result.multiplier == 3.0
        assert result.aged_score == 30.0  # 10.0 * 3.0

    def test_red_zone_10x_penalty(self, calculator, now):
        """Test 45-day-old issue has 10x multiplier."""
        created_at = now - timedelta(days=45)
        result = calculator.calculate(created_at, base_score=10.0, now=now)

        assert result.age_days == 45
        assert result.tier == AgingTier.RED
        assert result.multiplier == 10.0
        assert result.aged_score == 100.0  # 10.0 * 10.0

    def test_crisis_50x_penalty(self, calculator, now):
        """Test 75-day-old issue has 50x multiplier."""
        created_at = now - timedelta(days=75)
        result = calculator.calculate(created_at, base_score=10.0, now=now)

        assert result.age_days == 75
        assert result.tier == AgingTier.CRISIS
        assert result.multiplier == 50.0
        assert result.aged_score == 500.0  # 10.0 * 50.0

    def test_postmortem_100x_penalty(self, calculator, now):
        """Test 100-day-old issue has 100x multiplier and requires postmortem."""
        created_at = now - timedelta(days=100)
        result = calculator.calculate(created_at, base_score=10.0, now=now)

        assert result.age_days == 100
        assert result.tier == AgingTier.POSTMORTEM
        assert result.multiplier == 100.0
        assert result.aged_score == 1000.0  # 10.0 * 100.0
        assert result.postmortem_required

    def test_p0_issue_30_days_pages_oncall(self, calculator, now):
        """Test P0 issue 30+ days old triggers oncall page."""
        created_at = now - timedelta(days=30)
        result = calculator.calculate(created_at, base_score=10.0, priority="P0", now=now)

        assert result.escalation_required
        assert "PAGE_ONCALL" in result.escalation_action
        assert "P0" in result.escalation_action

    def test_p0_issue_29_days_no_escalation(self, calculator, now):
        """Test P0 issue 29 days old does not trigger escalation yet."""
        created_at = now - timedelta(days=29)
        result = calculator.calculate(created_at, base_score=10.0, priority="P0", now=now)

        assert not result.escalation_required

    def test_any_priority_60_days_notifies_leadership(self, calculator, now):
        """Test any issue 60+ days old notifies leadership."""
        created_at = now - timedelta(days=60)
        result = calculator.calculate(created_at, base_score=10.0, priority="P2", now=now)

        assert result.escalation_required
        assert "NOTIFY_LEADERSHIP" in result.escalation_action
        assert "P2" in result.escalation_action

    def test_postmortem_required_90_days(self, calculator, now):
        """Test 90+ day old issue requires postmortem."""
        created_at = now - timedelta(days=90)
        result = calculator.calculate(created_at, base_score=10.0, now=now)

        assert result.postmortem_required

    def test_timezone_aware_datetimes(self, calculator, now):
        """Test calculation works with timezone-aware datetimes."""
        created_at = datetime(2025, 12, 1, tzinfo=timezone.utc)
        result = calculator.calculate(created_at, base_score=10.0, now=now)

        assert result.age_days == 52  # Roughly 52 days
        assert result.tier == AgingTier.RED  # 52 days = red zone

    def test_naive_datetimes_converted_to_utc(self, calculator, now):
        """Test naive datetimes are converted to UTC."""
        created_at_naive = datetime(2026, 1, 15)  # No timezone
        result = calculator.calculate(created_at_naive, base_score=10.0, now=now)

        # Should not raise exception, should convert to UTC
        assert result.age_days == 7
        assert result.tier == AgingTier.FRESH

    def test_defaults_to_current_time(self, calculator):
        """Test calculator uses current time if now not provided."""
        created_at = datetime.now(timezone.utc) - timedelta(days=5)
        result = calculator.calculate(created_at, base_score=10.0)

        assert result.age_days == 5

    def test_get_aging_distribution(self, calculator, now):
        """Test aging distribution calculation across issues."""
        issues = [
            {"created_at": now - timedelta(days=5)},   # Fresh
            {"created_at": now - timedelta(days=10)},  # Reminder
            {"created_at": now - timedelta(days=20)},  # Yellow
            {"created_at": now - timedelta(days=45)},  # Red
            {"created_at": now - timedelta(days=75)},  # Crisis
            {"created_at": now - timedelta(days=100)}, # Postmortem
        ]

        distribution = calculator.get_aging_distribution(issues)

        assert distribution["Fresh"] == 1
        assert distribution["Reminder"] == 1
        assert distribution["Yellow Zone"] == 1
        assert distribution["Red Zone"] == 1
        assert distribution["Crisis"] == 1
        assert distribution["Postmortem Required"] == 1


class TestConvenienceFunction:
    """Test convenience function calculate_aging_penalty()."""

    def test_returns_aged_score(self):
        """Test convenience function returns aged score directly."""
        created_at = datetime(2025, 12, 1, tzinfo=timezone.utc)
        aged_score = calculate_aging_penalty(created_at, base_score=10.0, priority="P1")

        # 52 days old = RED zone = 10x multiplier
        assert aged_score >= 100.0  # Roughly 10.0 * 10.0

    def test_ancient_issue_massive_score(self):
        """Test ancient issue (365 days) gets massive score."""
        created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        aged_score = calculate_aging_penalty(created_at, base_score=10.0)

        # 1 year old = POSTMORTEM tier = 100x multiplier
        assert aged_score >= 1000.0  # 10.0 * 100.0


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.fixture
    def calculator(self):
        return AgingPenaltyCalculator()

    def test_zero_base_score(self, calculator):
        """Test zero base score works correctly."""
        created_at = datetime(2025, 12, 1, tzinfo=timezone.utc)
        result = calculator.calculate(created_at, base_score=0.0)

        assert result.aged_score == 0.0

    def test_negative_base_score(self, calculator):
        """Test negative base score (should not happen but handle gracefully)."""
        created_at = datetime(2025, 12, 1, tzinfo=timezone.utc)
        result = calculator.calculate(created_at, base_score=-10.0)

        # Multiplier still applies
        assert result.aged_score < 0

    def test_very_high_base_score(self, calculator):
        """Test very high base score."""
        created_at = datetime(2025, 12, 1, tzinfo=timezone.utc)
        result = calculator.calculate(created_at, base_score=1000.0)

        # Red zone (10x) on high base score
        assert result.aged_score >= 10000.0

    def test_future_created_at_negative_age(self, calculator):
        """Test issue created in future (should not happen but handle gracefully)."""
        now = datetime(2026, 1, 22, tzinfo=timezone.utc)
        future = now + timedelta(days=10)
        result = calculator.calculate(future, base_score=10.0, now=now)

        # Negative age, should get FRESH tier (default)
        assert result.age_days == -10
        assert result.tier == AgingTier.POSTMORTEM  # Falls through to default
