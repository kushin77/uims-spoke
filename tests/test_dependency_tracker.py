"""Unit tests for Dependency Graph and parsing system."""

import pytest
from src.dependency_tracker.parser import (
    DependencyType, IssueNode, DependencyCheckResult, DependencyParser,
    DependencyGraph, check_dependencies
)


class TestDependencyParser:
    """Tests for parsing dependency declarations from issue text."""
    
    def test_parse_depends_on_pattern(self):
        """Parse 'depends on #X' pattern."""
        text = "This task depends on #123 before we can proceed"
        deps = DependencyParser.parse_dependencies(text)
        assert 123 in deps
    
    def test_parse_blocked_by_pattern(self):
        """Parse 'blocked by #X' pattern."""
        text = "Currently blocked by #456"
        deps = DependencyParser.parse_dependencies(text)
        assert 456 in deps
    
    def test_parse_requires_pattern(self):
        """Parse 'requires #X' pattern."""
        text = "This requires #789 to be implemented first"
        deps = DependencyParser.parse_dependencies(text)
        assert 789 in deps
    
    def test_parse_relates_to_pattern(self):
        """Parse 'relates to #X' pattern."""
        text = "Related to #321 and relates to #654"
        deps = DependencyParser.parse_dependencies(text)
        assert 321 in deps
        assert 654 in deps
    
    def test_parse_multiple_dependencies(self):
        """Parse multiple dependency declarations."""
        text = """
        This task depends on #123
        Also blocked by #789
        Requires #321 to be done first
        """
        deps = DependencyParser.parse_dependencies(text)
        assert len(deps) == 3
        assert {123, 789, 321} == deps
    
    def test_case_insensitive_parsing(self):
        """Dependency parsing is case-insensitive."""
        text = "DEPENDS ON #111, Blocked By #222, REQUIRES #333"
        deps = DependencyParser.parse_dependencies(text)
        assert {111, 222, 333} == deps
    
    def test_no_dependencies_found(self):
        """Return empty set when no dependencies found."""
        text = "This is a regular issue with no dependencies"
        deps = DependencyParser.parse_dependencies(text)
        assert len(deps) == 0
    
    def test_parse_dependency_type_blocked_by(self):
        """Identify 'blocked by' relationship."""
        text = "This is blocked by #456"
        dep_type = DependencyParser.parse_dependency_type(text, 456)
        assert dep_type == DependencyType.BLOCKED_BY
    
    def test_parse_dependency_type_depends_on(self):
        """Identify 'depends on' relationship."""
        text = "This depends on #789"
        dep_type = DependencyParser.parse_dependency_type(text, 789)
        assert dep_type == DependencyType.BLOCKS
    
    def test_malformed_dependency_ignored(self):
        """Malformed patterns are ignored."""
        text = "Issue # 123 (missing dependency prefix)"
        deps = DependencyParser.parse_dependencies(text)
        assert 123 not in deps  # Only strict patterns match


class TestIssueNode:
    """Tests for IssueNode data structure."""
    
    def test_create_issue_node(self):
        """Create a basic issue node."""
        node = IssueNode(123, "Fix bug in auth", "open")
        assert node.number == 123
        assert node.title == "Fix bug in auth"
        assert node.state == "open"
    
    def test_node_dependency_sets(self):
        """Issue node maintains separate dependency sets."""
        node = IssueNode(1, "Task", "open")
        node.depends_on.add(2)
        node.blocks.add(3)
        node.related_to.add(4)
        
        assert 2 in node.depends_on
        assert 3 in node.blocks
        assert 4 in node.related_to
        assert len(node.depends_on) == 1
        assert len(node.blocks) == 1
        assert len(node.related_to) == 1


class TestDependencyGraph:
    """Tests for DependencyGraph operations."""
    
    def test_add_single_issue(self):
        """Add a single issue to graph."""
        graph = DependencyGraph()
        graph.add_issue(1, "Task 1", "open")
        
        assert 1 in graph.nodes
        assert graph.nodes[1].number == 1
        assert graph.nodes[1].state == "open"
    
    def test_add_dependency_blocked_by(self):
        """Add 'blocked by' dependency between issues."""
        graph = DependencyGraph()
        graph.add_issue(1, "Task 1", "open")
        graph.add_issue(2, "Task 2", "open")
        
        graph.add_dependency(1, 2, DependencyType.BLOCKED_BY)
        
        assert 2 in graph.nodes[1].depends_on
        assert 1 in graph.nodes[2].blocks
    
    def test_add_dependency_blocks(self):
        """Add 'blocks' dependency between issues."""
        graph = DependencyGraph()
        graph.add_issue(1, "Task 1", "open")
        graph.add_issue(2, "Task 2", "open")
        
        graph.add_dependency(1, 2, DependencyType.BLOCKS)
        
        assert 1 in graph.nodes[2].depends_on
        assert 2 in graph.nodes[1].blocks
    
    def test_add_related_dependency(self):
        """Add 'related' dependency between issues."""
        graph = DependencyGraph()
        graph.add_issue(1, "Task 1", "open")
        graph.add_issue(2, "Task 2", "open")
        
        graph.add_dependency(1, 2, DependencyType.RELATED)
        
        assert 2 in graph.nodes[1].related_to
        assert 1 in graph.nodes[2].related_to
    
    def test_issue_can_assign_no_dependencies(self):
        """Issue can be assigned if no open dependencies."""
        graph = DependencyGraph()
        graph.add_issue(1, "Task 1", "open")
        
        result = graph.check_issue(1, {1})
        assert result.can_assign
        assert result.can_close
    
    def test_issue_cannot_assign_with_open_dependency(self):
        """Issue cannot be assigned if open dependencies exist."""
        graph = DependencyGraph()
        graph.add_issue(1, "Task 1", "open")
        graph.add_issue(2, "Task 2", "open")
        graph.add_dependency(1, 2, DependencyType.BLOCKED_BY)
        
        result = graph.check_issue(1, {1, 2})
        assert not result.can_assign
        assert not result.can_close
        assert 2 in result.blocking_dependencies
    
    def test_issue_can_assign_with_closed_dependency(self):
        """Issue can be assigned once dependencies are closed."""
        graph = DependencyGraph()
        graph.add_issue(1, "Task 1", "open")
        graph.add_issue(2, "Task 2", "closed")
        graph.add_dependency(1, 2, DependencyType.BLOCKED_BY)
        
        result = graph.check_issue(1, {1})  # Only 1 is open
        assert result.can_assign
        assert result.can_close
    
    def test_blocking_issues_notification(self):
        """Identify issues to notify when a blocker is closed."""
        graph = DependencyGraph()
        graph.add_issue(1, "Task 1", "open")
        graph.add_issue(2, "Task 2", "open")
        graph.add_issue(3, "Task 3", "open")
        
        # Task 1 and 3 both depend on Task 2
        graph.add_dependency(1, 2, DependencyType.BLOCKED_BY)
        graph.add_dependency(3, 2, DependencyType.BLOCKED_BY)
        
        # When Task 2 is closed
        to_notify = graph.get_issues_to_notify(2)
        assert set(to_notify) == {1, 3}
    
    def test_dependency_chain_length_single_issue(self):
        """Single issue has chain length of 1."""
        graph = DependencyGraph()
        graph.add_issue(1, "Task 1", "open")
        
        result = graph.check_issue(1, {1})
        assert result.total_dependency_chain_length == 1
    
    def test_dependency_chain_length_linear(self):
        """Calculate length of linear dependency chain."""
        graph = DependencyGraph()
        graph.add_issue(1, "Task 1", "open")
        graph.add_issue(2, "Task 2", "open")
        graph.add_issue(3, "Task 3", "open")
        
        # 1 depends on 2, 2 depends on 3
        graph.add_dependency(1, 2, DependencyType.BLOCKED_BY)
        graph.add_dependency(2, 3, DependencyType.BLOCKED_BY)
        
        result = graph.check_issue(1, {1, 2, 3})
        assert result.total_dependency_chain_length == 3
    
    def test_circular_dependency_detection(self):
        """Circular dependencies are detected and rejected."""
        graph = DependencyGraph()
        graph.add_issue(1, "Task 1", "open")
        graph.add_issue(2, "Task 2", "open")
        
        graph.add_dependency(1, 2, DependencyType.BLOCKED_BY)
        
        # Attempting to create cycle should raise
        with pytest.raises(ValueError):
            graph.add_dependency(2, 1, DependencyType.BLOCKED_BY)
    
    def test_complex_circular_dependency_detection(self):
        """Circular dependencies detected in complex graphs."""
        graph = DependencyGraph()
        graph.add_issue(1, "Task 1", "open")
        graph.add_issue(2, "Task 2", "open")
        graph.add_issue(3, "Task 3", "open")
        
        # 1 → 2 → 3
        graph.add_dependency(1, 2, DependencyType.BLOCKED_BY)
        graph.add_dependency(2, 3, DependencyType.BLOCKED_BY)
        
        # Attempting 3 → 1 would create cycle
        with pytest.raises(ValueError):
            graph.add_dependency(3, 1, DependencyType.BLOCKED_BY)
    
    def test_diamond_dependency_allowed(self):
        """Diamond dependencies (not cycles) are allowed."""
        graph = DependencyGraph()
        # Create diamond: 1 depends on 2&3, both depend on 4
        graph.add_issue(1, "Task 1", "open")
        graph.add_issue(2, "Task 2", "open")
        graph.add_issue(3, "Task 3", "open")
        graph.add_issue(4, "Task 4", "open")
        
        graph.add_dependency(1, 2, DependencyType.BLOCKED_BY)
        graph.add_dependency(1, 3, DependencyType.BLOCKED_BY)
        graph.add_dependency(2, 4, DependencyType.BLOCKED_BY)
        graph.add_dependency(3, 4, DependencyType.BLOCKED_BY)
        
        # Should not raise
        result = graph.check_issue(1, {1, 2, 3, 4})
        assert 2 in result.blocking_dependencies
        assert 3 in result.blocking_dependencies
    
    def test_missing_issue_in_graph(self):
        """Handling of missing issues in graph."""
        graph = DependencyGraph()
        graph.add_issue(1, "Task 1", "open")
        # Issue 2 is referenced but not added
        
        result = graph.check_issue(999, {1})
        assert result.can_assign
        assert result.can_close
    
    def test_orphaned_dependencies(self):
        """Detect orphaned dependencies (closed issues still referenced)."""
        graph = DependencyGraph()
        graph.add_issue(1, "Task 1", "open")
        graph.add_issue(2, "Task 2", "closed")
        
        graph.add_dependency(1, 2, DependencyType.BLOCKED_BY)
        
        result = graph.check_issue(1, {1})  # 2 is not in open_issues
        assert 2 in result.orphaned_dependencies


class TestConvenienceFunction:
    """Tests for check_dependencies() convenience function."""
    
    def test_check_dependencies_simple(self):
        """Simple dependency check with convenience function."""
        result = check_dependencies(1, "Depends on #2", {
            1: {"title": "Task 1", "state": "open"},
            2: {"title": "Task 2", "state": "open"}
        })
        
        assert not result.can_assign
        assert 2 in result.blocking_dependencies
    
    def test_check_dependencies_no_deps(self):
        """Issue with no dependencies can be assigned."""
        result = check_dependencies(1, "No dependencies here", {
            1: {"title": "Task 1", "state": "open"}
        })
        
        assert result.can_assign
        assert result.can_close
    
    def test_check_dependencies_multiple(self):
        """Check issue with multiple dependencies."""
        result = check_dependencies(1, "Depends on #2. Blocked by #3. Requires #4", {
            1: {"title": "Task 1", "state": "open"},
            2: {"title": "Task 2", "state": "open"},
            3: {"title": "Task 3", "state": "open"},
            4: {"title": "Task 4", "state": "open"}
        })
        
        assert not result.can_assign
        assert {2, 3, 4} == set(result.blocking_dependencies)


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""
    
    def test_self_dependency_blocked(self):
        """Issue cannot depend on itself."""
        graph = DependencyGraph()
        graph.add_issue(1, "Task 1", "open")
        
        with pytest.raises(ValueError):
            graph.add_dependency(1, 1)
    
    def test_large_dependency_chain(self):
        """Handle large linear dependency chains."""
        graph = DependencyGraph()
        for i in range(1, 11):  # Create chain of 10 issues
            graph.add_issue(i, f"Task {i}", "open")
        
        # 1 → 2 → 3 → ... → 10
        for i in range(1, 10):
            graph.add_dependency(i, i + 1, DependencyType.BLOCKED_BY)
        
        result = graph.check_issue(1, set(range(1, 11)))
        assert result.total_dependency_chain_length == 10
        assert not result.can_assign
    
    def test_wide_dependency_graph(self):
        """Handle issue with many blockers."""
        graph = DependencyGraph()
        graph.add_issue(1, "Main Task", "open")
        
        # Create 20 blocking tasks
        for i in range(2, 22):
            graph.add_issue(i, f"Blocker {i}", "open")
            graph.add_dependency(1, i, DependencyType.BLOCKED_BY)
        
        result = graph.check_issue(1, set(range(1, 22)))
        assert len(result.blocking_dependencies) == 20
        assert not result.can_assign
