# UIMS Prompt Dispatcher Guide

**Status:** ACTIVE  
**Version:** 1.0  
**Last Updated:** 2026-01-22

## Purpose

Provides clear separation between different work modes with FAANG-grade git project controls. Enforces best practices for issue claiming, atomic commits, and session tracking.

---

## Quick Start

```bash
# Launch interactive dispatcher
./scripts/uims_dispatcher.sh

# Or use directly:
FIRESTORE_PROJECT_ID="your-project" ./scripts/uims_dispatcher.sh
```

---

## Work Modes

### Mode 1: Start Oldest Issues 🟣

**When to use:** Tackle ancient technical debt, prevent issue rot

**Strategy:**
- Aging penalty enforced (90+ days → 50x multiplier)
- Oldest issues float to top automatically
- Auto-escalation for 60+ day issues

**Workflow:**
```bash
1. Select "Start Oldest Issues"
2. View top 10 oldest issues (sorted by age)
3. Select issue number to claim
4. Automatic:
   - Adds "in-progress" label
   - Posts claim comment with session context
   - Creates feature branch: feat/uims-spoke/issue-{N}
   - Logs session start
```

**Example:**
```
Issue #456: "Fix VPC peering" (created 92 days ago)
→ Aging penalty: 50x multiplier
→ Triggers auto-escalation to leadership
→ Creates postmortem issue automatically
```

---

### Mode 2: Start Most Important Issues 🔴

**When to use:** SLA-driven critical path work

**Strategy:**
- Priority-first (P0 → P1 → P2)
- SLA awareness (P0 = 24h, P1 = 72h, P2 = 7d)
- Blocks non-critical work during incidents

**Workflow:**
```bash
1. Select "Start Most Important Issues"
2. View P0/P1 issues ranked by priority_score
3. See SLA deadline for each
4. Select issue to claim
5. Automatic escalation if SLA <20% remaining
```

**Example:**
```
Issue #789: "Production outage" (P0, 4h remaining on 24h SLA)
→ Oncall paged immediately
→ Leadership notified
→ All hands on this until resolved
```

---

### Mode 3: Start Project 🔵

**When to use:** Epic/feature development, coordinated multi-issue work

**Strategy:**
- Context-driven (understand dependencies first)
- Dependency graph awareness
- Scope isolation (all related issues grouped)

**Workflow:**
```bash
1. Select "Start Project"
2. View active epics/projects
3. Select epic number
4. See all linked issues (dependency tree)
5. Select specific issue to start
6. Branch naming includes epic context
```

**Example:**
```
Epic #100: "OAuth Integration"
  ├── #101: Set up IAM (CLOSED)
  ├── #102: Create OAuth flow (IN PROGRESS)
  └── #103: Add token refresh (BLOCKED by #102)

→ Can only claim #102 (dependencies met)
→ Branch: feat/uims-spoke/epic-100-issue-102
```

---

## Git Project Controls (FAANG-Grade)

### Mandatory Rules

| Rule | Enforcement | Validation |
|------|-------------|------------|
| **GPG/SSH Signed Commits** | All commits | `git log -50 --show-signature` |
| **Atomic Commits** | ≤5 files per commit | Pre-commit hook |
| **Linear History** | No merge commits | Rebase enforcement |
| **Branch Naming** | `feat/uims-spoke/*` | Branch protection |
| **Secret-Free History** | Zero credentials | Gitleaks scan |
| **Session Logging** | Every work session | `SESSION_LOGS.md` |

### Advanced Operations

#### 1. Verify Commit Signatures
```bash
# Check last 50 commits for GPG/SSH signatures
./scripts/uims_dispatcher.sh → Advanced Git Controls → Option 1

# Manual check:
git log -50 --pretty=format:"%h %G? %an %s" | grep -v "^.* G "
```

**Output:**
```
✅ All 50 commits are GPG/SSH signed
```

#### 2. Atomic Commit Compliance
```bash
# Check last 10 commits for file count violations
./scripts/uims_dispatcher.sh → Advanced Git Controls → Option 2

# Manual check:
git log -10 --pretty=format:"%h" | while read c; do
  git show --name-only --format="" "$c" | wc -l
done
```

**Example:**
```
✅ a1b2c3d: 3 files
❌ d4e5f6g: 12 files (exceeds 5)  ← VIOLATION
✅ h7i8j9k: 5 files
```

#### 3. Secret Audit (Gitleaks)
```bash
# Scan entire git history for leaked credentials
./scripts/uims_dispatcher.sh → Advanced Git Controls → Option 3

# Requires: brew install gitleaks
```

**What it catches:**
- AWS keys (AKIA..., aws_access_key)
- GCP service account JSON
- API tokens (Bearer, Authorization headers)
- Passwords in config files
- Private SSH keys

#### 4. Linear History Enforcement
```bash
# Check for merge commits (should be none)
./scripts/uims_dispatcher.sh → Advanced Git Controls → Option 4

# Fix violations:
git rebase -i origin/main  # Rewrite history to remove merges
```

#### 5. Session Analytics
```bash
# View session history and metrics
./scripts/uims_dispatcher.sh → Option 5

# Shows:
# - Total sessions
# - Recent work modes
# - Issues claimed per session
# - Average session duration
```

#### 6. Pre-Push Validation
```bash
# Run full validation before pushing
./scripts/uims_dispatcher.sh → Advanced Git Controls → Option 7

# Checks:
# - All commits signed
# - No uncommitted changes
# - Tests pass (make test)
# - Linters pass (make lint)
# - No secrets in history
```

---

## Session Tracking

Every work session is logged to `docs/management/SESSION_LOGS.md`:

```markdown
## Session: 20260122-143000
**Timestamp:** 2026-01-22 14:30:00
**Mode:** oldest-issues
**Branch:** feat/uims-spoke/issue-456
**User:** dev@example.com

## Session: 20260122-160000
**Timestamp:** 2026-01-22 16:00:00
**Mode:** priority-first
**Branch:** feat/uims-spoke/issue-789
**User:** dev@example.com
```

**Session Analytics:**
```bash
# View session report
./scripts/uims_dispatcher.sh → Session Analytics

# Output:
Total sessions: 47
Oldest issues mode: 18 sessions
Important issues mode: 22 sessions
Project mode: 7 sessions

Recent sessions:
- 20260122-143000: oldest-issues (issue-456)
- 20260122-160000: priority-first (issue-789)
```

---

## Issue Claiming Workflow

### Automatic Actions

When you claim an issue via dispatcher:

1. **GitHub Label** → Adds `in-progress`
2. **GitHub Comment** → Posts claim with context:
   ```
   🚀 Starting work on this issue
   Session: 20260122-143000
   Context: oldest-first
   Branch: feat/uims-spoke/issue-456
   Mode: Oldest Issues
   ```
3. **Git Branch** → Creates `feat/uims-spoke/issue-{N}`
4. **Session Log** → Records start timestamp
5. **Firestore Update** → Marks `last_claimed_at`, `last_claimed_by`

### Manual Claiming (if dispatcher unavailable)

```bash
ISSUE=456

# Add label
gh issue edit $ISSUE --repo kushin77/GCP-landing-zone --add-label "in-progress"

# Add comment
gh issue comment $ISSUE --repo kushin77/GCP-landing-zone --body "Starting work"

# Create branch
git checkout -b feat/uims-spoke/issue-$ISSUE
```

---

## Integration with Smart Selector

The dispatcher queries Firestore for issue prioritization:

```bash
# Set project ID
export FIRESTORE_PROJECT_ID="your-gcp-project"

# Dispatcher will query:
gcloud firestore query issue_state \
  --order-by="created_at"           # Oldest issues mode
  --order-by="priority_score DESC"  # Important issues mode
```

**If Firestore unavailable:**
- Falls back to GitHub API
- Uses label-based priority (priority-p0, priority-p1)
- No semantic clustering or ML features

---

## Configuration

### Environment Variables

```bash
# Required for Firestore integration
export FIRESTORE_PROJECT_ID="uims-spoke-prod"

# Optional overrides
export GIT_REQUIRED_BRANCH_PREFIX="feat/uims-spoke/"
export GIT_COMMIT_SIGNING_REQUIRED=true
export GIT_ATOMIC_COMMIT_MAX_FILES=5
export GIT_ENFORCE_LINEAR_HISTORY=true
```

### Customization

Edit `scripts/uims_dispatcher.sh`:

```bash
# Line 14-18: Git controls
GIT_REQUIRED_BRANCH_PREFIX="feat/uims-spoke/"
GIT_COMMIT_SIGNING_REQUIRED=true
GIT_ATOMIC_COMMIT_MAX_FILES=5
GIT_ENFORCE_LINEAR_HISTORY=true
GIT_SESSION_LOG_PATH="$PROJECT_ROOT/docs/management/SESSION_LOGS.md"
```

---

## Troubleshooting

### Issue: "Not in a git repository"
```bash
# Run from repo root
cd /path/to/uims-spoke
./scripts/uims_dispatcher.sh
```

### Issue: "Firestore query failed"
```bash
# Check credentials
gcloud auth application-default login

# Verify project ID
export FIRESTORE_PROJECT_ID="your-project"

# Dispatcher falls back to GitHub API if Firestore unavailable
```

### Issue: "Unsigned commits found"
```bash
# Configure GPG signing
git config --global commit.gpgsign true
git config --global user.signingkey YOUR_GPG_KEY

# Or use SSH signing (GitHub supports this)
git config --global gpg.format ssh
git config --global user.signingkey ~/.ssh/id_ed25519.pub
```

### Issue: "Atomic commit violation"
```bash
# Break commits into smaller pieces
git reset HEAD~1           # Undo last commit
git add file1.py file2.py  # Stage subset
git commit -S -m "Part 1"
git add file3.py file4.py
git commit -S -m "Part 2"
```

---

## Best Practices

### 1. Use Oldest Issues Mode for Maintenance Windows
```bash
# Friday afternoon: tackle old debt
./scripts/uims_dispatcher.sh → Mode 1
```

### 2. Use Important Issues Mode During Incidents
```bash
# Production down: P0 only
./scripts/uims_dispatcher.sh → Mode 2
```

### 3. Use Project Mode for Feature Development
```bash
# Sprint planning: pick epic to implement
./scripts/uims_dispatcher.sh → Mode 3
```

### 4. Run Pre-Push Validation Before Every PR
```bash
./scripts/uims_dispatcher.sh → Advanced Git Controls → Pre-Push Validation
```

### 5. Review Session Analytics Weekly
```bash
# Team retrospective: how many issues claimed?
./scripts/uims_dispatcher.sh → Session Analytics
```

---

## Integration with VSCode Extension

Future enhancement: VSCode command integration

```typescript
// Command: UIMS: Start Oldest Issue
vscode.commands.registerCommand('uims.startOldest', async () => {
  const terminal = vscode.window.createTerminal('UIMS');
  terminal.sendText('./scripts/uims_dispatcher.sh');
  terminal.show();
});
```

---

## References

- [ELITE_ENHANCEMENTS.md](./ELITE_ENHANCEMENTS.md) — Enhancement roadmap
- [ATOMIC_COMMITS_GUIDE.md](../GCP-landing-zone/docs/governance/ATOMIC_COMMITS_GUIDE.md) — Git best practices
- [SESSION_LOGS.md](./docs/management/SESSION_LOGS.md) — Session history

---

**Owner:** Platform Engineering  
**Last Updated:** 2026-01-22  
**Dispatcher Version:** 1.0
