"""Dependency Graph and Issue Blocking System for UIMS

Implements a dependency tracking system for issues with:
- Regex parsing of 'depends on #X' patterns in issue bodies
- Directed acyclic graph (DAG) representation
- Blocking rules: can't assign/close an issue if dependencies are open
- Auto-notification when blocking issues are resolved
- Orphan dependency detection

Example issue body patterns:
```
Depends on #123
Blocked by #456
Requires #789 to be resolved first
```
"""

from dataclasses import dataclass, field
from typing import Optional, Set, Dict, List
import re
from enum import Enum


class DependencyType(Enum):
    """Types of issue dependencies."""
    BLOCKS = "blocks"          # This issue blocks another
    BLOCKED_BY = "blocked_by"  # This issue is blocked by another
    RELATED = "related"        # Loosely related


@dataclass
class IssueNode:
    """Represents an issue in the dependency graph."""
    number: int
    title: str
    state: str  # open, closed, draft
    
    depends_on: Set[int] = field(default_factory=set)      # Issues this depends on
    blocks: Set[int] = field(default_factory=set)          # Issues this blocks
    related_to: Set[int] = field(default_factory=set)      # Loosely related issues
    
    can_assign: bool = field(init=False, default=True)     # Can assign if no open deps
    can_close: bool = field(init=False, default=True)      # Can close if no open deps
    blocking_issues: List[int] = field(init=False, default_factory=list)  # Open issues blocking this


@dataclass
class DependencyCheckResult:
    """Result of dependency analysis for an issue."""
    issue_number: int
    can_assign: bool
    can_close: bool
    blocking_dependencies: List[int]  # Open issues this depends on
    blocked_by_issues: List[int]      # Open issues blocked by this
    total_dependency_chain_length: int  # Length of longest dependency path
    circular_dependency_detected: bool
    orphaned_dependencies: List[int]   # References to closed/missing issues


class DependencyParser:
    """Parses issue bodies for dependency declarations."""
    
    # Regex patterns to match dependency declarations
    PATTERNS = [
        r'(?:depends on|depends on:)\s*#(\d+)',     # Depends on #123
        r'(?:blocked by|blocked by:)\s*#(\d+)',     # Blocked by #123
        r'(?:requires|requires:)\s*#(\d+)',         # Requires #123
        r'(?:relates to|relates to:)\s*#(\d+)',     # Relates to #123
        r'(?:related to|related to:)\s*#(\d+)',     # Related to #123
    ]
    
    @classmethod
    def parse_dependencies(cls, text: str) -> Set[int]:
        """Extract all issue numbers from dependency text.
        
        Args:
            text: Issue body or description text
        
        Returns:
            Set of issue numbers referenced as dependencies
        
        Example:
            >>> text = "Depends on #123 and #456. Blocked by #789."
            >>> deps = DependencyParser.parse_dependencies(text)
            >>> sorted(deps)
            [123, 456, 789]
        """
        dependencies = set()
        
        for pattern in cls.PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                dependencies.add(int(match.group(1)))
        
        return dependencies
    
    @classmethod
    def parse_dependency_type(cls, text: str, target_issue: int) -> DependencyType:
        """Determine the type of dependency relationship.
        
        Args:
            text: Issue body text
            target_issue: The issue number we're checking relationship for
        
        Returns:
            DependencyType indicating the relationship
        
        Example:
            >>> text = "Depends on #456"
            >>> DependencyParser.parse_dependency_type(text, 456)
            <DependencyType.BLOCKED_BY: 'blocked_by'>
        """
        # Check what type of dependency this is
        blocked_patterns = [r'blocked by.*#' + str(target_issue)]
        depends_patterns = [r'depends on.*#' + str(target_issue)]
        
        for pattern in blocked_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return DependencyType.BLOCKED_BY
        
        for pattern in depends_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return DependencyType.BLOCKS
        
        return DependencyType.RELATED


class DependencyGraph:
    """Directed acyclic graph for issue dependencies."""
    
    def __init__(self):
        """Initialize empty dependency graph."""
        self.nodes: Dict[int, IssueNode] = {}
    
    def add_issue(self, number: int, title: str, state: str = "open"):
        """Add or update an issue node in the graph.
        
        Args:
            number: Issue number
            title: Issue title
            state: Issue state (open, closed, draft)
        """
        if number not in self.nodes:
            self.nodes[number] = IssueNode(number, title, state)
        else:
            self.nodes[number].title = title
            self.nodes[number].state = state
    
    def add_dependency(self, source: int, target: int, dep_type: DependencyType = DependencyType.BLOCKED_BY):
        """Add a dependency relationship between two issues.
        
        Args:
            source: The issue that depends on or is blocked by target
            target: The issue that is depended on or blocks source
            dep_type: Type of dependency relationship
        
        Raises:
            ValueError: If adding would create a circular dependency
        """
        # Ensure both nodes exist
        if source not in self.nodes:
            self.add_issue(source, f"Issue #{source}")
        if target not in self.nodes:
            self.add_issue(target, f"Issue #{target}")
        
        # Determine actual dependency direction
        depends_on_from = source
        depends_on_to = target
        
        if dep_type == DependencyType.BLOCKS:
            # If source blocks target, then target depends on source
            depends_on_from = target
            depends_on_to = source
        
        # Check for circular dependencies BEFORE adding
        if self._would_create_cycle(depends_on_from, depends_on_to):
            raise ValueError(f"Adding dependency {depends_on_from}→{depends_on_to} would create circular dependency")
        
        # Now add the edges
        if dep_type == DependencyType.BLOCKED_BY:
            self.nodes[source].depends_on.add(target)
            self.nodes[target].blocks.add(source)
        elif dep_type == DependencyType.BLOCKS:
            self.nodes[target].depends_on.add(source)
            self.nodes[source].blocks.add(target)
        else:  # RELATED
            self.nodes[source].related_to.add(target)
            self.nodes[target].related_to.add(source)
    
    def check_issue(self, issue_number: int, open_issues: Set[int]) -> DependencyCheckResult:
        """Check if an issue can be assigned/closed based on dependencies.
        
        Args:
            issue_number: Issue to check
            open_issues: Set of currently open issue numbers
        
        Returns:
            DependencyCheckResult with blocking status
        
        Example:
            >>> graph = DependencyGraph()
            >>> graph.add_issue(1, "Task 1")
            >>> graph.add_issue(2, "Task 2")
            >>> graph.add_dependency(1, 2)
            >>> result = graph.check_issue(1, {1, 2})
            >>> result.can_assign
            False
            >>> result.blocking_dependencies
            [2]
        """
        if issue_number not in self.nodes:
            return DependencyCheckResult(
                issue_number=issue_number,
                can_assign=True,
                can_close=True,
                blocking_dependencies=[],
                blocked_by_issues=[],
                total_dependency_chain_length=1,
                circular_dependency_detected=False,
                orphaned_dependencies=[]
            )
        
        node = self.nodes[issue_number]
        
        # Find open issues blocking this one
        blocking = [dep for dep in node.depends_on if dep in open_issues]
        
        # Find open issues blocked by this one
        blocked_by = [dep for dep in node.blocks if dep in open_issues]
        
        # Find orphaned dependencies (closed or missing)
        orphaned = [dep for dep in node.depends_on if dep not in open_issues and dep in self.nodes]
        
        # Can only assign/close if no open dependencies
        can_assign = len(blocking) == 0
        can_close = len(blocking) == 0 and len(blocked_by) == 0
        
        # Calculate dependency chain length
        chain_length = self._get_dependency_chain_length(issue_number)
        
        return DependencyCheckResult(
            issue_number=issue_number,
            can_assign=can_assign,
            can_close=can_close,
            blocking_dependencies=sorted(blocking),
            blocked_by_issues=sorted(blocked_by),
            total_dependency_chain_length=chain_length,
            circular_dependency_detected=False,
            orphaned_dependencies=sorted(orphaned)
        )
    
    def get_issues_to_notify(self, closed_issue: int) -> List[int]:
        """Get list of issues to notify when an issue is resolved.
        
        Args:
            closed_issue: The issue that was just closed
        
        Returns:
            List of issue numbers that were waiting on this one
        
        Example:
            >>> graph = DependencyGraph()
            >>> graph.add_issue(1, "Task 1")
            >>> graph.add_issue(2, "Task 2")
            >>> graph.add_dependency(1, 2)  # 1 depends on 2
            >>> graph.get_issues_to_notify(2)  # 2 was closed
            [1]  # Notify issue 1
        """
        if closed_issue not in self.nodes:
            return []
        
        # Return issues that were blocked by this one
        return sorted(list(self.nodes[closed_issue].blocks))
    
    def _would_create_cycle(self, source: int, target: int) -> bool:
        """Check if adding edge source→target would create a cycle.
        
        Args:
            source: Source issue
            target: Target issue
        
        Returns:
            True if adding this edge would create a cycle
        """
        # Use DFS to check if target can reach source
        visited = set()
        return self._has_path(target, source, visited)
    
    def _has_path(self, start: int, end: int, visited: Set[int]) -> bool:
        """DFS to check if path exists from start to end."""
        if start == end:
            return True
        
        if start in visited:
            return False
        
        visited.add(start)
        
        if start in self.nodes:
            for neighbor in self.nodes[start].depends_on:
                if self._has_path(neighbor, end, visited):
                    return True
        
        return False
    
    def _get_dependency_chain_length(self, issue: int, visited: Optional[Set[int]] = None) -> int:
        """Calculate longest dependency chain from this issue."""
        if visited is None:
            visited = set()
        
        if issue in visited or issue not in self.nodes:
            return 1
        
        visited.add(issue)
        
        deps = self.nodes[issue].depends_on
        if not deps:
            return 1
        
        max_length = 0
        for dep in deps:
            length = self._get_dependency_chain_length(dep, visited.copy())
            max_length = max(max_length, length)
        
        return max_length + 1


def check_dependencies(issue_number: int, issue_body: str, 
                      all_issues: Dict[int, Dict]) -> DependencyCheckResult:
    """Convenience function to check dependencies for an issue.
    
    Args:
        issue_number: Issue to check
        issue_body: Issue description text
        all_issues: Dict mapping issue numbers to {title, state}
    
    Returns:
        DependencyCheckResult
    
    Example:
        >>> deps = check_dependencies(1, "Depends on #2", 
        ...     {1: {"title": "Task 1", "state": "open"},
        ...      2: {"title": "Task 2", "state": "open"}})
        >>> deps.can_assign
        False
    """
    # Parse dependencies from body
    dep_numbers = DependencyParser.parse_dependencies(issue_body)
    
    # Build graph
    graph = DependencyGraph()
    for issue_num, issue_data in all_issues.items():
        graph.add_issue(issue_num, issue_data["title"], issue_data["state"])
    
    # Add dependencies
    for dep_num in dep_numbers:
        graph.add_dependency(issue_number, dep_num)
    
    # Get open issues
    open_issues = {num for num, data in all_issues.items() if data["state"] == "open"}
    
    return graph.check_issue(issue_number, open_issues)
