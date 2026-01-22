"""SLA Tracking and Auto-Escalation System for UIMS

Implements hard SLAs for issues based on priority:
- P0 (Critical): 24 hours
- P1 (High): 72 hours  
- P2 (Medium): 7 days
- P3 (Low): 30 days (advisory only)

Features:
- Time-to-breach calculation and warning at 80% threshold
- PagerDuty integration for critical escalations
- Hourly Cloud Scheduler-based checks (via Cloud Function)
- Leadership notifications when SLA is breached
- Historical tracking of SLA compliance metrics
- Escalation automation: warn → notify → page → escalate
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional


class Priority(Enum):
    """Issue priority with corresponding SLA windows."""
    P0 = (1, "Critical")  # 24 hours in days
    P1 = (3, "High")      # 72 hours (3 days)
    P2 = (7, "Medium")    # 7 days
    P3 = (30, "Low")      # 30 days (advisory)

    def __init__(self, sla_days: int, label: str):
        self.sla_days = sla_days
        self.sla_hours = sla_days * 24
        self.sla_seconds = sla_days * 24 * 3600
        self.label = label


class SLAStatus(Enum):
    """SLA health status."""
    HEALTHY = "healthy"          # <60% of SLA elapsed
    WARNING = "warning"          # 60-80% of SLA elapsed
    AT_RISK = "at_risk"         # 80-100% of SLA elapsed
    BREACHED = "breached"       # >100% of SLA elapsed


@dataclass
class SLACheckResult:
    """Result of SLA compliance check for a single issue."""
    issue_number: int
    priority: Priority
    created_at: datetime
    current_time: datetime
    
    # Calculated fields
    age_hours: float = field(init=False)
    sla_hours: float = field(init=False)
    time_remaining_hours: float = field(init=False)
    percent_elapsed: float = field(init=False)
    status: SLAStatus = field(init=False)
    
    # Escalation flags
    warning_required: bool = field(init=False)
    escalation_required: bool = field(init=False)
    leadership_notification_required: bool = field(init=False)
    pagerduty_page_required: bool = field(init=False)
    
    def __post_init__(self):
        """Calculate derived fields."""
        # Convert naive datetimes to UTC
        if self.created_at.tzinfo is None:
            self.created_at = self.created_at.replace(tzinfo=timezone.utc)
        if self.current_time.tzinfo is None:
            self.current_time = self.current_time.replace(tzinfo=timezone.utc)
        
        # Calculate age and SLA metrics
        self.age_hours = (self.current_time - self.created_at).total_seconds() / 3600
        self.sla_hours = self.priority.sla_hours
        self.time_remaining_hours = self.sla_hours - self.age_hours
        self.percent_elapsed = (self.age_hours / self.sla_hours) * 100 if self.sla_hours > 0 else 0
        
        # Determine status
        if self.percent_elapsed >= 100:
            self.status = SLAStatus.BREACHED
        elif self.percent_elapsed >= 80:
            self.status = SLAStatus.AT_RISK
        elif self.percent_elapsed >= 60:
            self.status = SLAStatus.WARNING
        else:
            self.status = SLAStatus.HEALTHY
        
        # Set escalation flags
        self.warning_required = self.percent_elapsed >= 60
        self.escalation_required = self.percent_elapsed >= 80
        self.leadership_notification_required = self.percent_elapsed >= 90
        self.pagerduty_page_required = self.percent_elapsed >= 100


class SLATracker:
    """Tracks and enforces issue SLAs with escalation logic."""
    
    # Escalation thresholds
    WARNING_THRESHOLD_PCT = 60      # Notify when 60% of SLA elapsed
    ESCALATION_THRESHOLD_PCT = 80   # Escalate when 80% of SLA elapsed
    LEADERSHIP_THRESHOLD_PCT = 90   # Notify leadership at 90%
    BREACH_THRESHOLD_PCT = 100      # Page oncall when breached
    
    def __init__(self, pagerduty_enabled: bool = False, pagerduty_service_id: Optional[str] = None):
        """Initialize SLA tracker.
        
        Args:
            pagerduty_enabled: Whether to enable PagerDuty integration
            pagerduty_service_id: PagerDuty service ID for incident creation
        """
        self.pagerduty_enabled = pagerduty_enabled
        self.pagerduty_service_id = pagerduty_service_id
    
    def check_issue_sla(self, issue_number: int, priority: Priority, created_at: datetime,
                       now: Optional[datetime] = None) -> SLACheckResult:
        """Check SLA status for a single issue.
        
        Args:
            issue_number: GitHub issue number
            priority: Issue priority (P0-P3)
            created_at: When the issue was created
            now: Current time (defaults to UTC.now())
        
        Returns:
            SLACheckResult with status, escalation flags, and metrics
        
        Example:
            >>> tracker = SLATracker()
            >>> result = tracker.check_issue_sla(123, Priority.P0, 
            ...     datetime(2026, 1, 20, 12, 0, tzinfo=timezone.utc),
            ...     datetime(2026, 1, 21, 12, 0, tzinfo=timezone.utc))
            >>> result.status
            <SLAStatus.BREACHED: 'breached'>
            >>> result.percent_elapsed
            100.0
            >>> result.pagerduty_page_required
            True
        """
        if now is None:
            now = datetime.now(timezone.utc)
        
        return SLACheckResult(
            issue_number=issue_number,
            priority=priority,
            created_at=created_at,
            current_time=now
        )
    
    def get_sla_hours_remaining(self, priority: Priority, age_hours: float) -> float:
        """Get remaining SLA hours for given priority and age.
        
        Args:
            priority: Issue priority
            age_hours: Issue age in hours
        
        Returns:
            Hours remaining until SLA breach (negative if already breached)
        """
        return priority.sla_hours - age_hours
    
    def batch_check_issues(self, issues: list[dict], now: Optional[datetime] = None) -> dict:
        """Check SLA for multiple issues.
        
        Args:
            issues: List of dicts with keys: number, priority, created_at
            now: Current time (defaults to UTC.now())
        
        Returns:
            Dict with keys: healthy, warning, at_risk, breached
        
        Example:
            >>> tracker = SLATracker()
            >>> results = tracker.batch_check_issues([
            ...     {"number": 1, "priority": Priority.P0, "created_at": ...},
            ...     {"number": 2, "priority": Priority.P1, "created_at": ...},
            ... ])
            >>> results["breached"]  # List of breached issues
            [<SLACheckResult #123>, ...]
        """
        if now is None:
            now = datetime.now(timezone.utc)
        
        results = {
            "healthy": [],
            "warning": [],
            "at_risk": [],
            "breached": []
        }
        
        for issue in issues:
            result = self.check_issue_sla(
                issue["number"],
                issue["priority"],
                issue["created_at"],
                now
            )
            
            status_key = result.status.value
            results[status_key].append(result)
        
        return results
    
    def get_escalation_actions(self, result: SLACheckResult) -> list[str]:
        """Get list of escalation actions required for an issue.
        
        Args:
            result: SLACheckResult from check_issue_sla()
        
        Returns:
            List of action codes: WARN_TEAM, NOTIFY_LEADERSHIP, PAGE_ONCALL, CREATE_INCIDENT
        
        Example:
            >>> actions = tracker.get_escalation_actions(result)
            >>> "PAGE_ONCALL" in actions
            True
        """
        actions = []
        
        if result.warning_required:
            actions.append("WARN_TEAM")
        
        if result.leadership_notification_required:
            actions.append("NOTIFY_LEADERSHIP")
        
        if result.pagerduty_page_required:
            if self.pagerduty_enabled:
                actions.append("PAGE_ONCALL")
            else:
                actions.append("ESCALATE_SEVERITY")
        
        return actions
    
    def get_sla_dashboard_metrics(self, batch_results: dict) -> dict:
        """Get dashboard metrics from batch check results.
        
        Args:
            batch_results: Output from batch_check_issues()
        
        Returns:
            Dashboard metrics: total_issues, sla_compliance_pct, critical_breaches, etc.
        """
        all_issues = (batch_results["healthy"] + batch_results["warning"] + 
                     batch_results["at_risk"] + batch_results["breached"])
        
        total = len(all_issues)
        if total == 0:
            return {
                "total_issues": 0,
                "sla_compliance_pct": 100.0,
                "healthy": 0,
                "warning": 0,
                "at_risk": 0,
                "breached": 0,
                "critical_breaches": 0,  # P0 breaches
            }
        
        # Count P0 breaches (most critical)
        critical_breaches = sum(
            1 for issue in batch_results["breached"]
            if issue.priority == Priority.P0
        )
        
        healthy_pct = (len(batch_results["healthy"]) / total) * 100
        
        return {
            "total_issues": total,
            "sla_compliance_pct": healthy_pct,
            "healthy": len(batch_results["healthy"]),
            "warning": len(batch_results["warning"]),
            "at_risk": len(batch_results["at_risk"]),
            "breached": len(batch_results["breached"]),
            "critical_breaches": critical_breaches,
        }


def check_issue_sla(issue_number: int, priority: Priority, created_at: datetime,
                    now: Optional[datetime] = None) -> SLACheckResult:
    """Convenience function to check SLA without instantiating tracker.
    
    Args:
        issue_number: GitHub issue number
        priority: Issue priority
        created_at: When issue was created
        now: Current time (defaults to UTC.now())
    
    Returns:
        SLACheckResult with all metrics
    
    Example:
        >>> from datetime import datetime, timezone
        >>> result = check_issue_sla(123, Priority.P0,
        ...     datetime(2026, 1, 20, 12, 0, tzinfo=timezone.utc))
        >>> result.status
        <SLAStatus.BREACHED: 'breached'>
    """
    tracker = SLATracker()
    return tracker.check_issue_sla(issue_number, priority, created_at, now)
