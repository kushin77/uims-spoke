"""Unit tests for SLA Tracking system."""

import pytest
from datetime import datetime, timedelta, timezone
from src.sla_tracker.tracker import (
    Priority, SLAStatus, SLACheckResult, SLATracker, check_issue_sla
)


@pytest.fixture
def tracker():
    """Create SLA tracker instance."""
    return SLATracker(pagerduty_enabled=True, pagerduty_service_id="svc-123")


@pytest.fixture
def now():
    """Fixed current time for testing."""
    return datetime(2026, 1, 22, 12, 0, 0, tzinfo=timezone.utc)


class TestPriority:
    """Tests for Priority enum."""
    
    def test_p0_24_hour_sla(self):
        """P0 has 24-hour SLA."""
        assert Priority.P0.sla_days == 1
        assert Priority.P0.sla_hours == 24
        assert Priority.P0.sla_seconds == 86400
        assert Priority.P0.label == "Critical"
    
    def test_p1_72_hour_sla(self):
        """P1 has 72-hour SLA."""
        assert Priority.P1.sla_days == 3
        assert Priority.P1.sla_hours == 72
        assert Priority.P1.label == "High"
    
    def test_p2_7_day_sla(self):
        """P2 has 7-day SLA."""
        assert Priority.P2.sla_days == 7
        assert Priority.P2.sla_hours == 168
        assert Priority.P2.label == "Medium"
    
    def test_p3_advisory_sla(self):
        """P3 is advisory (30 days)."""
        assert Priority.P3.sla_days == 30
        assert Priority.P3.label == "Low"


class TestSLACheckResult:
    """Tests for SLA check results."""
    
    def test_healthy_p0_less_than_60_percent(self, now):
        """P0 issue < 14 hours old is HEALTHY."""
        created_at = now - timedelta(hours=12)
        result = SLACheckResult(123, Priority.P0, created_at, now)
        
        assert result.age_hours == 12
        assert result.sla_hours == 24
        assert result.status == SLAStatus.HEALTHY
        assert result.percent_elapsed == 50.0
        assert not result.warning_required
    
    def test_warning_p0_60_to_80_percent(self, now):
        """P0 issue 14-19 hours old is WARNING."""
        created_at = now - timedelta(hours=16)
        result = SLACheckResult(123, Priority.P0, created_at, now)
        
        assert result.status == SLAStatus.WARNING
        assert result.percent_elapsed == pytest.approx(66.67, abs=0.1)
        assert result.warning_required
        assert not result.escalation_required
    
    def test_at_risk_p0_80_to_100_percent(self, now):
        """P0 issue 19-24 hours old is AT_RISK."""
        created_at = now - timedelta(hours=20)
        result = SLACheckResult(123, Priority.P0, created_at, now)
        
        assert result.status == SLAStatus.AT_RISK
        assert result.percent_elapsed == pytest.approx(83.33, abs=0.1)
        assert result.escalation_required
        assert not result.pagerduty_page_required
    
    def test_breached_p0_over_100_percent(self, now):
        """P0 issue > 24 hours old is BREACHED."""
        created_at = now - timedelta(hours=25)
        result = SLACheckResult(123, Priority.P0, created_at, now)
        
        assert result.status == SLAStatus.BREACHED
        assert result.percent_elapsed > 100
        assert result.pagerduty_page_required
        assert result.leadership_notification_required
    
    def test_p1_breached_after_72_hours(self, now):
        """P1 issue > 72 hours old is BREACHED."""
        created_at = now - timedelta(hours=73)
        result = SLACheckResult(456, Priority.P1, created_at, now)
        
        assert result.status == SLAStatus.BREACHED
        assert result.pagerduty_page_required
    
    def test_p2_healthy_under_7_days(self, now):
        """P2 issue < 7 days old is HEALTHY."""
        created_at = now - timedelta(days=3)
        result = SLACheckResult(789, Priority.P2, created_at, now)
        
        assert result.age_hours == pytest.approx(72, abs=1)
        assert result.status == SLAStatus.HEALTHY
    
    def test_naive_datetime_converted_to_utc(self, now):
        """Naive datetimes are converted to UTC."""
        naive_created = datetime(2026, 1, 22, 0, 0, 0)  # No timezone
        naive_now = datetime(2026, 1, 22, 12, 0, 0)     # No timezone
        
        result = SLACheckResult(123, Priority.P0, naive_created, naive_now)
        
        assert result.created_at.tzinfo is not None
        assert result.current_time.tzinfo is not None
        assert result.age_hours == 12
    
    def test_time_remaining_calculation(self, now):
        """Time remaining is correctly calculated."""
        created_at = now - timedelta(hours=18)
        result = SLACheckResult(123, Priority.P0, created_at, now)
        
        assert result.age_hours == 18
        assert result.time_remaining_hours == pytest.approx(6, abs=0.1)
    
    def test_leadership_notification_at_90_percent(self, now):
        """Leadership notification triggered at 90% SLA elapsed."""
        created_at = now - timedelta(hours=21.6)  # 90% of 24h
        result = SLACheckResult(123, Priority.P0, created_at, now)
        
        assert result.percent_elapsed >= 90
        assert result.leadership_notification_required


class TestSLATracker:
    """Tests for SLATracker class."""
    
    def test_check_issue_sla_p0_healthy(self, tracker, now):
        """Tracker correctly identifies healthy P0 issue."""
        created_at = now - timedelta(hours=10)
        result = tracker.check_issue_sla(123, Priority.P0, created_at, now)
        
        assert result.status == SLAStatus.HEALTHY
        assert not result.escalation_required
    
    def test_check_issue_sla_p0_breached(self, tracker, now):
        """Tracker correctly identifies breached P0 issue."""
        created_at = now - timedelta(hours=25)
        result = tracker.check_issue_sla(123, Priority.P0, created_at, now)
        
        assert result.status == SLAStatus.BREACHED
        assert result.pagerduty_page_required
    
    def test_get_sla_hours_remaining(self, tracker):
        """Calculate hours remaining for given age."""
        remaining = tracker.get_sla_hours_remaining(Priority.P0, 12)
        assert remaining == 12
        
        remaining = tracker.get_sla_hours_remaining(Priority.P0, 30)
        assert remaining == -6  # Breached by 6 hours
    
    def test_batch_check_issues(self, tracker, now):
        """Batch check multiple issues and categorize by status."""
        issues = [
            {"number": 1, "priority": Priority.P0, "created_at": now - timedelta(hours=10)},
            {"number": 2, "priority": Priority.P0, "created_at": now - timedelta(hours=25)},
            {"number": 3, "priority": Priority.P1, "created_at": now - timedelta(hours=60)},
            {"number": 4, "priority": Priority.P2, "created_at": now - timedelta(days=3)},
        ]
        
        results = tracker.batch_check_issues(issues, now)
        
        assert len(results["healthy"]) >= 1  # Issue 1, 4
        assert len(results["breached"]) >= 1  # Issue 2
        assert results["healthy"][0].issue_number in [1, 4]
        assert results["breached"][0].issue_number == 2
    
    def test_get_escalation_actions_warn_team(self, tracker, now):
        """WARN_TEAM action for 60% SLA elapsed."""
        created_at = now - timedelta(hours=15)
        result = tracker.check_issue_sla(123, Priority.P0, created_at, now)
        actions = tracker.get_escalation_actions(result)
        
        assert "WARN_TEAM" in actions
    
    def test_get_escalation_actions_notify_leadership(self, tracker, now):
        """NOTIFY_LEADERSHIP action for 90% SLA elapsed."""
        created_at = now - timedelta(hours=21.6)
        result = tracker.check_issue_sla(123, Priority.P0, created_at, now)
        actions = tracker.get_escalation_actions(result)
        
        assert "NOTIFY_LEADERSHIP" in actions
    
    def test_get_escalation_actions_page_oncall(self, tracker, now):
        """PAGE_ONCALL action for breached SLA."""
        created_at = now - timedelta(hours=25)
        result = tracker.check_issue_sla(123, Priority.P0, created_at, now)
        actions = tracker.get_escalation_actions(result)
        
        assert "PAGE_ONCALL" in actions
    
    def test_get_escalation_actions_escalate_severity_no_pagerduty(self, now):
        """ESCALATE_SEVERITY when PagerDuty disabled."""
        tracker = SLATracker(pagerduty_enabled=False)
        created_at = now - timedelta(hours=25)
        result = tracker.check_issue_sla(123, Priority.P0, created_at, now)
        actions = tracker.get_escalation_actions(result)
        
        assert "ESCALATE_SEVERITY" in actions
        assert "PAGE_ONCALL" not in actions
    
    def test_get_sla_dashboard_metrics_empty(self, tracker):
        """Dashboard metrics with no issues."""
        results = tracker.batch_check_issues([], None)
        metrics = tracker.get_sla_dashboard_metrics(results)
        
        assert metrics["total_issues"] == 0
        assert metrics["sla_compliance_pct"] == 100.0
        assert metrics["breached"] == 0
    
    def test_get_sla_dashboard_metrics_mixed_status(self, tracker, now):
        """Dashboard metrics aggregates status counts."""
        issues = [
            {"number": 1, "priority": Priority.P0, "created_at": now - timedelta(hours=10)},
            {"number": 2, "priority": Priority.P0, "created_at": now - timedelta(hours=25)},
            {"number": 3, "priority": Priority.P1, "created_at": now - timedelta(hours=50)},
            {"number": 4, "priority": Priority.P2, "created_at": now - timedelta(days=10)},
        ]
        
        results = tracker.batch_check_issues(issues, now)
        metrics = tracker.get_sla_dashboard_metrics(results)
        
        assert metrics["total_issues"] == 4
        assert metrics["breached"] >= 1
        assert metrics["critical_breaches"] >= 1  # P0 breach
    
    def test_get_sla_dashboard_metrics_critical_breaches(self, tracker, now):
        """Dashboard tracks critical (P0) breaches separately."""
        issues = [
            {"number": 1, "priority": Priority.P0, "created_at": now - timedelta(hours=25)},
            {"number": 2, "priority": Priority.P0, "created_at": now - timedelta(hours=26)},
            {"number": 3, "priority": Priority.P1, "created_at": now - timedelta(hours=75)},
        ]
        
        results = tracker.batch_check_issues(issues, now)
        metrics = tracker.get_sla_dashboard_metrics(results)
        
        assert metrics["critical_breaches"] == 2


class TestConvenienceFunction:
    """Tests for check_issue_sla() convenience function."""
    
    def test_returns_sla_check_result(self, now):
        """Convenience function returns SLACheckResult."""
        result = check_issue_sla(123, Priority.P0,
            now - timedelta(hours=10), now)
        
        assert isinstance(result, SLACheckResult)
        assert result.issue_number == 123
    
    def test_convenience_function_calculates_correctly(self, now):
        """Convenience function produces same result as tracker."""
        created_at = now - timedelta(hours=25)
        
        result1 = check_issue_sla(123, Priority.P0, created_at, now)
        
        tracker = SLATracker()
        result2 = tracker.check_issue_sla(123, Priority.P0, created_at, now)
        
        assert result1.status == result2.status
        assert result1.percent_elapsed == result2.percent_elapsed


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""
    
    def test_exactly_at_sla_boundary(self, now):
        """Issue exactly at SLA boundary is breached."""
        created_at = now - timedelta(hours=24)
        result = SLACheckResult(123, Priority.P0, created_at, now)
        
        assert result.age_hours == 24
        assert result.percent_elapsed == 100.0
        assert result.status == SLAStatus.BREACHED
    
    def test_one_second_before_breach(self, now):
        """Issue one second before breach is still at-risk."""
        created_at = now - timedelta(hours=24, seconds=-1)
        result = SLACheckResult(123, Priority.P0, created_at, now)
        
        assert result.percent_elapsed < 100
        assert result.status != SLAStatus.BREACHED
    
    def test_very_old_issue(self, now):
        """Very old issues have correct metrics."""
        created_at = now - timedelta(days=365)
        result = SLACheckResult(123, Priority.P0, created_at, now)
        
        assert result.percent_elapsed > 8500  # Way over 100%
        assert result.status == SLAStatus.BREACHED
    
    def test_future_created_date(self, now):
        """Issue created in future has negative age."""
        created_at = now + timedelta(hours=1)
        result = SLACheckResult(123, Priority.P0, created_at, now)
        
        assert result.age_hours < 0
        assert result.time_remaining_hours > 24
        assert result.status == SLAStatus.HEALTHY
    
    def test_different_priorities_same_age(self, now):
        """Same age different priorities have different statuses."""
        created_at = now - timedelta(hours=50)
        
        p0_result = SLACheckResult(1, Priority.P0, created_at, now)
        p1_result = SLACheckResult(2, Priority.P1, created_at, now)
        p2_result = SLACheckResult(3, Priority.P2, created_at, now)
        
        assert p0_result.status == SLAStatus.BREACHED
        assert p1_result.status == SLAStatus.WARNING
        assert p2_result.status == SLAStatus.HEALTHY
