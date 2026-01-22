#!/bin/bash
# UIMS Prompt Dispatcher - Clear separation for different work modes
# Enforces FAANG-grade git project controls
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Git project controls configuration
GIT_REQUIRED_BRANCH_PREFIX="feat/uims-spoke/"
GIT_COMMIT_SIGNING_REQUIRED=true
GIT_ATOMIC_COMMIT_MAX_FILES=5
GIT_ENFORCE_LINEAR_HISTORY=true
GIT_SESSION_LOG_PATH="$PROJECT_ROOT/docs/management/SESSION_LOGS.md"

# Firestore issue state cache
FIRESTORE_PROJECT_ID="${FIRESTORE_PROJECT_ID:-}"
FIRESTORE_COLLECTION="issue_state"

# ============================================================================
# Git Project Controls (FAANG-Grade)
# ============================================================================

check_git_status() {
    echo -e "${BLUE}🔍 Checking Git status...${NC}"
    
    # Must be in git repo
    if ! git rev-parse --git-dir > /dev/null 2>&1; then
        echo -e "${RED}❌ Not in a git repository${NC}"
        exit 1
    fi
    
    # Check current branch
    CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
    if [[ ! "$CURRENT_BRANCH" =~ ^$GIT_REQUIRED_BRANCH_PREFIX ]]; then
        echo -e "${YELLOW}⚠️  Not on a feature branch (${GIT_REQUIRED_BRANCH_PREFIX}*)${NC}"
        echo -e "${CYAN}Current branch: $CURRENT_BRANCH${NC}"
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
    
    # Check for uncommitted changes
    if ! git diff-index --quiet HEAD --; then
        echo -e "${YELLOW}⚠️  Uncommitted changes detected:${NC}"
        git status --short
        echo
    fi
    
    # Check commit signature (last 5 commits)
    if [ "$GIT_COMMIT_SIGNING_REQUIRED" = true ]; then
        echo -e "${BLUE}🔐 Verifying commit signatures...${NC}"
        UNSIGNED=$(git log -5 --pretty=format:"%h %G?" | grep -v "G" || true)
        if [ -n "$UNSIGNED" ]; then
            echo -e "${RED}❌ Unsigned commits found:${NC}"
            echo "$UNSIGNED"
            echo -e "${YELLOW}All commits must be GPG/SSH signed${NC}"
        else
            echo -e "${GREEN}✅ All recent commits signed${NC}"
        fi
    fi
    
    # Check for merge commits (enforce linear history)
    if [ "$GIT_ENFORCE_LINEAR_HISTORY" = true ]; then
        MERGE_COMMITS=$(git log --merges --oneline -10 || true)
        if [ -n "$MERGE_COMMITS" ]; then
            echo -e "${YELLOW}⚠️  Merge commits detected (prefer rebase):${NC}"
            echo "$MERGE_COMMITS"
        fi
    fi
    
    echo -e "${GREEN}✅ Git status check complete${NC}"
    echo
}

atomic_commit_check() {
    local FILES_CHANGED=$1
    
    if [ "$FILES_CHANGED" -gt "$GIT_ATOMIC_COMMIT_MAX_FILES" ]; then
        echo -e "${RED}❌ Atomic commit violation: $FILES_CHANGED files changed${NC}"
        echo -e "${YELLOW}Max allowed: $GIT_ATOMIC_COMMIT_MAX_FILES files per commit${NC}"
        echo -e "${CYAN}Break into smaller, logical commits${NC}"
        return 1
    fi
    
    echo -e "${GREEN}✅ Atomic commit size OK ($FILES_CHANGED files)${NC}"
    return 0
}

session_log_entry() {
    local MODE=$1
    local TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S")
    local SESSION_ID=$(date +"%Y%m%d-%H%M%S")
    
    mkdir -p "$(dirname "$GIT_SESSION_LOG_PATH")"
    
    cat >> "$GIT_SESSION_LOG_PATH" << EOF

## Session: $SESSION_ID
**Timestamp:** $TIMESTAMP  
**Mode:** $MODE  
**Branch:** $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "N/A")  
**User:** $(git config user.email 2>/dev/null || echo "unknown")  

EOF
    
    echo -e "${GREEN}✅ Session logged: $SESSION_ID${NC}"
}

# ============================================================================
# Mode 1: Start Oldest Issues (Aging Penalty Enforced)
# ============================================================================

mode_oldest_issues() {
    echo -e "${MAGENTA}═══════════════════════════════════════════════════════${NC}"
    echo -e "${MAGENTA}  MODE: START OLDEST ISSUES (Aging Penalty Priority)${NC}"
    echo -e "${MAGENTA}═══════════════════════════════════════════════════════${NC}"
    echo
    
    check_git_status
    session_log_entry "oldest-issues"
    
    echo -e "${CYAN}🎯 Strategy: Tackle ancient technical debt first${NC}"
    echo -e "${CYAN}Priority: 90+ day issues → 60+ day issues → 30+ day issues${NC}"
    echo
    
    # Query Firestore for oldest issues
    if [ -n "$FIRESTORE_PROJECT_ID" ]; then
        echo -e "${BLUE}📊 Fetching oldest issues from Firestore...${NC}"
        
        # Use gcloud to query (requires gcloud CLI)
        gcloud firestore query "$FIRESTORE_COLLECTION" \
            --project="$FIRESTORE_PROJECT_ID" \
            --order-by="created_at" \
            --limit=10 \
            --format="table(issue_id, repo, issue_number, title, created_at, priority_score)" \
            2>/dev/null || {
                echo -e "${YELLOW}⚠️  Firestore query failed. Using GitHub API fallback...${NC}"
                github_oldest_fallback
            }
    else
        echo -e "${YELLOW}⚠️  FIRESTORE_PROJECT_ID not set. Using GitHub API...${NC}"
        github_oldest_fallback
    fi
    
    echo
    echo -e "${GREEN}🚀 Ready to claim oldest issue?${NC}"
    read -p "Issue number to claim: " ISSUE_NUM
    
    if [ -n "$ISSUE_NUM" ]; then
        claim_issue "$ISSUE_NUM" "oldest-first"
    fi
}

github_oldest_fallback() {
    echo -e "${BLUE}🔍 Querying GitHub for oldest open issues...${NC}"
    
    gh issue list \
        --repo "kushin77/GCP-landing-zone" \
        --state open \
        --limit 10 \
        --json number,title,createdAt,labels \
        --jq '.[] | select(.labels[].name == "uims-spoke") | "\(.number)\t\(.title)\t\(.createdAt)"' \
        | sort -t$'\t' -k3 \
        | column -t -s $'\t'
}

# ============================================================================
# Mode 2: Start Most Important Issues (Priority-First)
# ============================================================================

mode_important_issues() {
    echo -e "${RED}═══════════════════════════════════════════════════════${NC}"
    echo -e "${RED}  MODE: START MOST IMPORTANT ISSUES (Priority-First)${NC}"
    echo -e "${RED}═══════════════════════════════════════════════════════${NC}"
    echo
    
    check_git_status
    session_log_entry "important-issues"
    
    echo -e "${CYAN}🎯 Strategy: Critical path, SLA-driven work${NC}"
    echo -e "${CYAN}Priority: P0 (24h SLA) → P1 (72h SLA) → P2 (7d SLA)${NC}"
    echo
    
    # Query Firestore for highest priority
    if [ -n "$FIRESTORE_PROJECT_ID" ]; then
        echo -e "${BLUE}📊 Fetching highest priority issues from Firestore...${NC}"
        
        gcloud firestore query "$FIRESTORE_COLLECTION" \
            --project="$FIRESTORE_PROJECT_ID" \
            --order-by="priority_score DESC" \
            --limit=10 \
            --format="table(issue_id, repo, issue_number, title, priority_score, created_at)" \
            2>/dev/null || {
                echo -e "${YELLOW}⚠️  Firestore query failed. Using GitHub API fallback...${NC}"
                github_priority_fallback
            }
    else
        echo -e "${YELLOW}⚠️  FIRESTORE_PROJECT_ID not set. Using GitHub API...${NC}"
        github_priority_fallback
    fi
    
    echo
    echo -e "${GREEN}🚀 Ready to claim high-priority issue?${NC}"
    read -p "Issue number to claim: " ISSUE_NUM
    
    if [ -n "$ISSUE_NUM" ]; then
        claim_issue "$ISSUE_NUM" "priority-first"
    fi
}

github_priority_fallback() {
    echo -e "${BLUE}🔍 Querying GitHub for P0/P1 issues...${NC}"
    
    gh issue list \
        --repo "kushin77/GCP-landing-zone" \
        --state open \
        --label "priority-p0,priority-p1" \
        --limit 10 \
        --json number,title,labels,createdAt \
        --jq '.[] | "\(.number)\t\(.labels | map(.name) | join(","))\t\(.title)\t\(.createdAt)"' \
        | column -t -s $'\t'
}

# ============================================================================
# Mode 3: Start Project (Context-Driven, Scoped Work)
# ============================================================================

mode_start_project() {
    echo -e "${CYAN}═══════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  MODE: START PROJECT (Epic/Feature Development)${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════${NC}"
    echo
    
    check_git_status
    session_log_entry "start-project"
    
    echo -e "${MAGENTA}🎯 Strategy: Focused epic/project work with dependencies${NC}"
    echo -e "${MAGENTA}Scope: Multi-issue coordinated effort${NC}"
    echo
    
    # List available epics/projects
    echo -e "${BLUE}📋 Active epics/projects:${NC}"
    gh issue list \
        --repo "kushin77/GCP-landing-zone" \
        --state open \
        --label "epic,uims-spoke" \
        --limit 10 \
        --json number,title,labels \
        --jq '.[] | "\(.number)\t\(.title)\t\(.labels | map(.name) | join(","))"' \
        | column -t -s $'\t'
    
    echo
    read -p "Epic/Project number to start: " EPIC_NUM
    
    if [ -n "$EPIC_NUM" ]; then
        echo
        echo -e "${BLUE}📊 Fetching linked issues for epic #$EPIC_NUM...${NC}"
        
        # Get epic details and find dependent issues
        gh issue view "$EPIC_NUM" --repo "kushin77/GCP-landing-zone" --json body | \
            jq -r '.body' | \
            grep -oP '#\d+' | \
            tr -d '#' | \
            sort -u | \
            while read -r ISSUE; do
                gh issue view "$ISSUE" --repo "kushin77/GCP-landing-zone" --json number,title,state --jq '"\(.number)\t\(.state)\t\(.title)"'
            done | column -t -s $'\t'
        
        echo
        read -p "Issue number to claim from this epic: " ISSUE_NUM
        
        if [ -n "$ISSUE_NUM" ]; then
            claim_issue "$ISSUE_NUM" "project-$EPIC_NUM"
        fi
    fi
}

# ============================================================================
# Issue Claiming & Git Workflow
# ============================================================================

claim_issue() {
    local ISSUE_NUM=$1
    local CONTEXT=$2
    
    echo
    echo -e "${BLUE}🔒 Claiming issue #$ISSUE_NUM...${NC}"
    
    # Add in-progress label
    gh issue edit "$ISSUE_NUM" --repo "kushin77/GCP-landing-zone" --add-label "in-progress" 2>/dev/null || true
    
    # Add comment with context
    gh issue comment "$ISSUE_NUM" --repo "kushin77/GCP-landing-zone" --body "🚀 **Starting work on this issue**

**Session:** $(date +%Y%m%d-%H%M%S)
**Context:** $CONTEXT
**Branch:** $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "N/A")
**Mode:** $([ "$CONTEXT" = "oldest-first" ] && echo "Oldest Issues" || [ "$CONTEXT" = "priority-first" ] && echo "Most Important" || echo "Project Work")

---
_Auto-claimed by UIMS dispatcher_" 2>/dev/null || {
        echo -e "${YELLOW}⚠️  Failed to add comment (check gh auth)${NC}"
    }
    
    # Create local branch if needed
    BRANCH_NAME="feat/uims-spoke/issue-$ISSUE_NUM"
    CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
    
    if [ "$CURRENT_BRANCH" != "$BRANCH_NAME" ]; then
        echo -e "${CYAN}🌿 Creating branch: $BRANCH_NAME${NC}"
        git checkout -b "$BRANCH_NAME" 2>/dev/null || git checkout "$BRANCH_NAME"
    fi
    
    echo
    echo -e "${GREEN}✅ Issue #$ISSUE_NUM claimed successfully${NC}"
    echo -e "${CYAN}Next steps:${NC}"
    echo -e "  1. Make changes in atomic commits (max $GIT_ATOMIC_COMMIT_MAX_FILES files)"
    echo -e "  2. Sign all commits: git commit -S -m 'message'"
    echo -e "  3. Push frequently: every 30-45 minutes"
    echo -e "  4. Update issue with progress comments"
    echo
}

# ============================================================================
# Advanced Git Operations
# ============================================================================

mode_git_controls() {
    echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  ADVANCED GIT PROJECT CONTROLS${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
    echo
    
    echo "1. Verify commit signatures (last 50 commits)"
    echo "2. Check atomic commit compliance"
    echo "3. Audit git history for secrets"
    echo "4. Enforce linear history (rebase check)"
    echo "5. View session logs"
    echo "6. Clean orphaned branches"
    echo "7. Pre-push validation"
    echo "8. Back"
    echo
    
    read -p "Select option: " GIT_OPTION
    
    case $GIT_OPTION in
        1)
            git_verify_signatures
            ;;
        2)
            git_check_atomic
            ;;
        3)
            git_audit_secrets
            ;;
        4)
            git_check_linear
            ;;
        5)
            git_view_session_logs
            ;;
        6)
            git_clean_branches
            ;;
        7)
            git_pre_push_validation
            ;;
        *)
            return
            ;;
    esac
}

git_verify_signatures() {
    echo -e "${BLUE}🔐 Verifying last 50 commits...${NC}"
    
    UNSIGNED=$(git log -50 --pretty=format:"%h %G? %an %s" | grep -v "^.* G " || true)
    
    if [ -n "$UNSIGNED" ]; then
        echo -e "${RED}❌ Unsigned commits found:${NC}"
        echo "$UNSIGNED"
        exit 1
    else
        echo -e "${GREEN}✅ All 50 commits are GPG/SSH signed${NC}"
    fi
}

git_check_atomic() {
    echo -e "${BLUE}📊 Checking last 10 commits for atomic compliance...${NC}"
    
    git log -10 --pretty=format:"%h" | while read -r COMMIT; do
        FILES=$(git show --name-only --format="" "$COMMIT" | wc -l)
        
        if [ "$FILES" -gt "$GIT_ATOMIC_COMMIT_MAX_FILES" ]; then
            echo -e "${RED}❌ $COMMIT: $FILES files (exceeds $GIT_ATOMIC_COMMIT_MAX_FILES)${NC}"
        else
            echo -e "${GREEN}✅ $COMMIT: $FILES files${NC}"
        fi
    done
}

git_audit_secrets() {
    echo -e "${BLUE}🔍 Auditing git history for secrets...${NC}"
    
    if command -v gitleaks &> /dev/null; then
        gitleaks detect --source="$PROJECT_ROOT" --verbose
    else
        echo -e "${YELLOW}⚠️  gitleaks not installed. Install: brew install gitleaks${NC}"
        echo
        echo -e "${CYAN}Manual check for common patterns:${NC}"
        git log --all -p | grep -E "(password|api_key|secret|token|aws_|gcp_)" || echo "None found"
    fi
}

git_check_linear() {
    echo -e "${BLUE}📈 Checking for merge commits (linear history enforcement)...${NC}"
    
    MERGE_COUNT=$(git log --merges --oneline | wc -l)
    
    if [ "$MERGE_COUNT" -gt 0 ]; then
        echo -e "${YELLOW}⚠️  Found $MERGE_COUNT merge commits${NC}"
        git log --merges --oneline --graph -10
        echo
        echo -e "${CYAN}To fix: git rebase -i origin/main${NC}"
    else
        echo -e "${GREEN}✅ Linear history maintained (no merge commits)${NC}"
    fi
}

git_view_session_logs() {
    if [ -f "$GIT_SESSION_LOG_PATH" ]; then
        tail -50 "$GIT_SESSION_LOG_PATH"
    else
        echo -e "${YELLOW}No session logs found${NC}"
    fi
}

git_clean_branches() {
    echo -e "${BLUE}🧹 Finding orphaned branches...${NC}"
    
    git branch --merged | grep -v "\*" | grep -v "main" | grep -v "develop" || echo "None found"
    
    echo
    read -p "Delete merged branches? (y/N): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        git branch --merged | grep -v "\*" | grep -v "main" | grep -v "develop" | xargs -r git branch -d
        echo -e "${GREEN}✅ Cleaned merged branches${NC}"
    fi
}

git_pre_push_validation() {
    echo -e "${BLUE}✅ Running pre-push validation...${NC}"
    echo
    
    # Check 1: Unsigned commits
    git_verify_signatures
    
    # Check 2: Uncommitted changes
    if ! git diff-index --quiet HEAD --; then
        echo -e "${RED}❌ Uncommitted changes detected${NC}"
        git status --short
        exit 1
    fi
    
    # Check 3: Tests pass
    if [ -f "$PROJECT_ROOT/Makefile" ]; then
        echo -e "${BLUE}🧪 Running tests...${NC}"
        cd "$PROJECT_ROOT" && make test
    fi
    
    # Check 4: Linting
    if [ -f "$PROJECT_ROOT/Makefile" ]; then
        echo -e "${BLUE}🔍 Running linters...${NC}"
        cd "$PROJECT_ROOT" && make lint || true
    fi
    
    echo
    echo -e "${GREEN}✅ Pre-push validation complete${NC}"
}

# ============================================================================
# Main Menu
# ============================================================================

main_menu() {
    clear
    echo -e "${CYAN}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║  UIMS Prompt Dispatcher - FAANG-Grade Issue Manager   ║${NC}"
    echo -e "${CYAN}╚════════════════════════════════════════════════════════╝${NC}"
    echo
    echo -e "${MAGENTA}WORK MODES:${NC}"
    echo -e "  ${MAGENTA}1.${NC} Start Oldest Issues       (Aging penalty priority)"
    echo -e "  ${RED}2.${NC} Start Most Important     (SLA-driven, P0/P1 first)"
    echo -e "  ${CYAN}3.${NC} Start Project            (Epic/feature development)"
    echo
    echo -e "${GREEN}TOOLS:${NC}"
    echo -e "  ${GREEN}4.${NC} Advanced Git Controls    (Signatures, atomic, audit)"
    echo -e "  5. Session Analytics"
    echo -e "  6. Exit"
    echo
    
    read -p "Select mode: " MODE
    
    case $MODE in
        1)
            mode_oldest_issues
            ;;
        2)
            mode_important_issues
            ;;
        3)
            mode_start_project
            ;;
        4)
            mode_git_controls
            ;;
        5)
            session_analytics
            ;;
        6)
            echo -e "${GREEN}✅ Goodbye${NC}"
            exit 0
            ;;
        *)
            echo -e "${RED}Invalid option${NC}"
            sleep 1
            main_menu
            ;;
    esac
    
    echo
    read -p "Press Enter to return to main menu..."
    main_menu
}

session_analytics() {
    echo -e "${BLUE}📊 Session Analytics${NC}"
    echo
    
    if [ -f "$GIT_SESSION_LOG_PATH" ]; then
        echo "Total sessions: $(grep "^## Session:" "$GIT_SESSION_LOG_PATH" | wc -l)"
        echo
        echo "Recent sessions:"
        grep "^## Session:" "$GIT_SESSION_LOG_PATH" | tail -5
    else
        echo -e "${YELLOW}No session logs found${NC}"
    fi
}

# ============================================================================
# Entry Point
# ============================================================================

main_menu
