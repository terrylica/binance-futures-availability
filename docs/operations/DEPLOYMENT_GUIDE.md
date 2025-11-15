# GitHub Actions Deployment Guide (ADR-0009)

**Implementation Plan**: `docs/plans/0009-github-actions-automation/plan.yaml`
**Architecture Decision**: `docs/decisions/0009-github-actions-automation.md`
**Status**: Phase 1-2 Complete, Phase 3-4 Require User Action

## Overview

This guide walks through deploying the GitHub Actions workflow for automated database updates. The workflow is production-ready and validated.

**Completed Phases**:
- ✅ Phase 1: Preparation (workflow, docs, test script copied)
- ✅ Phase 2: Testing (all module references validated)

**Pending Phases** (require user action):
- ⏳ Phase 3: Deployment (push to GitHub, configure permissions)
- ⏳ Phase 4: Migration and Monitoring (parallel operation, deprecate APScheduler)

## Phase 3: Deployment (15 minutes)

### Prerequisites

- GitHub repository with admin access
- `gh` CLI authenticated
- Git remote configured

### Step 1: Push Workflow to GitHub (2 minutes)

```bash
# Verify all files are staged
git status

# Push to main branch
git push origin main

# Verify workflow appears in GitHub
gh workflow list
```

**Expected output**:
```
Update Binance Futures Availability Database  active  update-database.yml
```

### Step 2: Configure Repository Permissions (5 minutes)

**Required**: Grant GitHub Actions write permissions for Releases.

**Via GitHub Web UI**:
1. Navigate to repository: https://github.com/YOUR_USERNAME/binance-futures-availability
2. Go to **Settings** → **Actions** → **General**
3. Scroll to **Workflow permissions**
4. Select: **"Read and write permissions"**
5. Check: **"Allow GitHub Actions to create and approve pull requests"** (optional)
6. Click **Save**

**Validation**:
```bash
# Check repository settings
gh api repos/:owner/:repo/actions/permissions
```

Expected JSON output should include:
```json
{
  "enabled": true,
  "allowed_actions": "all",
  "selected_actions_url": "..."
}
```

### Step 3: Trigger First Manual Run (5 minutes)

**Test the workflow** with a manual trigger before relying on scheduled runs.

```bash
# Trigger daily update mode (yesterday's data)
gh workflow run update-database.yml \
  --field update_mode=daily

# Get the run ID
RUN_ID=$(gh run list --workflow=update-database.yml --limit 1 --json databaseId --jq '.[0].databaseId')

# Watch the run in real-time
gh run watch $RUN_ID

# Or view in browser
gh run view $RUN_ID --web
```

**Expected Duration**: 5-10 minutes

**Success Indicators**:
1. All jobs complete with green checkmarks
2. Database uploaded to GitHub Releases as "latest"
3. Validation checks pass (logged in workflow output)

**Common Issues**:

| Error | Cause | Solution |
|-------|-------|----------|
| "Resource not accessible by integration" | Missing write permissions | Complete Step 2 (repository permissions) |
| "No database found in releases" | First run | Expected - workflow creates new database |
| "Validation failed: API cross-check" | S3 Vision data not yet available | Re-run workflow after 2 AM UTC |

### Step 4: Verify Release Created (3 minutes)

```bash
# List recent releases
gh release list --limit 5

# Download and verify database
gh release download latest --pattern "availability.duckdb.zst"
zstd -d availability.duckdb.zst

# Quick verification
uv run python -c "
import duckdb
conn = duckdb.connect('availability.duckdb', read_only=True)
result = conn.execute('SELECT COUNT(*) FROM daily_availability').fetchone()
print(f'Total records: {result[0]:,}')
conn.close()
"
```

**Expected**: Database with 700K+ records.

## Phase 4: Migration and Monitoring (1 week)

### Step 1: Parallel Operation (Days 1-3)

Run **both** APScheduler daemon and GitHub Actions in parallel to validate consistency.

**APScheduler** (keep running):
```bash
# Check if already running
ps aux | grep start_scheduler

# If not running, start it
uv run python scripts/start_scheduler.py --daemon
```

**GitHub Actions** (automatic):
- Runs daily at 3:00 AM UTC
- Check results: `gh run list --workflow=update-database.yml --limit 5`

**Validation Script** (run daily):
```bash
#!/bin/bash
# Compare databases from both sources

# Download GitHub Actions database
gh release download latest --pattern "availability.duckdb.zst" --clobber
zstd -d availability.duckdb.zst -o /tmp/gh-actions-db.duckdb

# Compare with local APScheduler database
uv run python -c "
import duckdb

local_db = duckdb.connect('~/.cache/binance-futures/availability.duckdb', read_only=True)
gh_db = duckdb.connect('/tmp/gh-actions-db.duckdb', read_only=True)

local_count = local_db.execute('SELECT COUNT(*) FROM daily_availability').fetchone()[0]
gh_count = gh_db.execute('SELECT COUNT(*) FROM daily_availability').fetchone()[0]

print(f'Local (APScheduler): {local_count:,} records')
print(f'GitHub Actions: {gh_count:,} records')
print(f'Difference: {abs(local_count - gh_count)} records')

if local_count == gh_count:
    print('✅ Databases are consistent')
else:
    print('⚠️  Databases differ - investigate')

local_db.close()
gh_db.close()
"
```

### Step 2: Monitor GitHub Actions (Days 1-7)

**Key Metrics**:
```bash
# Success rate (last 7 runs)
gh run list --workflow=update-database.yml --limit 7 --json conclusion \
  | jq '[.[] | select(.conclusion == "success")] | length'

# Average duration
gh run list --workflow=update-database.yml --limit 7 --json startedAt,updatedAt \
  | jq '[.[] | (((.updatedAt | fromdateiso8601) - (.startedAt | fromdateiso8601)) / 60)] | add / length'

# Check for failures
gh run list --workflow=update-database.yml --status failure --limit 5
```

**SLO Targets** (from plan.yaml):
- Success rate: **≥95%** (expected: 100%)
- Workflow duration: **5-10 minutes** (alert if >15 minutes)
- Validation pass rate: **100%**

### Step 3: Deprecate APScheduler (Day 7+)

**Criteria for deprecation** (all must be true):
- ✅ 3+ consecutive successful GitHub Actions runs
- ✅ Database consistency verified (byte-identical or logically equivalent)
- ✅ No validation failures
- ✅ Workflow duration within expected range (5-10 minutes)

**Deprecation Steps**:
```bash
# 1. Stop APScheduler daemon
uv run python scripts/start_scheduler.py --stop

# 2. Verify daemon stopped
ps aux | grep start_scheduler
# Expected: No processes found

# 3. (Optional) Disable autostart if configured
# Remove from cron/systemd/launchd

# 4. Keep APScheduler code (rollback path)
# Do NOT delete scheduler/ directory
```

### Step 4: Update Documentation (30 minutes)

Update all references from APScheduler to GitHub Actions:

**Files to update**:
1. `CLAUDE.md` (lines 246-262: Scheduler section)
2. `README.md` (Quick Start section)
3. `docs/guides/QUICKSTART.md`

**Changes**:
- Replace "APScheduler daemon" with "GitHub Actions workflow"
- Update command examples from `uv run python scripts/start_scheduler.py` to `gh workflow run`
- Add link to GitHub Releases for database downloads

**Validation**:
```bash
# Check for remaining APScheduler references
grep -r "APScheduler" docs/ CLAUDE.md README.md \
  | grep -v "ADR-0004" \
  | grep -v "deprecated" \
  | grep -v "fallback"

# Expected: Only historical references and rollback documentation
```

## Monitoring and Alerts

### Daily Checks (automated)

**GitHub Actions**:
- Navigate to: https://github.com/YOUR_USERNAME/binance-futures-availability/actions
- Check latest run status
- Review validation output

**Releases**:
- Navigate to: https://github.com/YOUR_USERNAME/binance-futures-availability/releases
- Verify "latest" tag updated daily
- Check database file size (expected: ~41 MB compressed)

### Alerts (optional)

**Email Notifications**:
```yaml
# Add to .github/workflows/update-database.yml
# At end of file, add failure notification job:

notify-failure:
  runs-on: ubuntu-latest
  if: failure()
  needs: [update-database]
  steps:
    - name: Send email notification
      uses: dawidd6/action-send-mail@v3
      with:
        server_address: smtp.gmail.com
        server_port: 465
        username: ${{ secrets.EMAIL_USERNAME }}
        password: ${{ secrets.EMAIL_PASSWORD }}
        subject: "❌ Database update failed"
        body: "Workflow run failed: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}"
        to: your-email@example.com
        from: GitHub Actions
```

**Slack Notifications** (via webhook):
```yaml
- name: Slack notification
  if: failure()
  uses: slackapi/slack-github-action@v1
  with:
    payload: |
      {
        "text": "Database update failed: <${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}|View Run>"
      }
  env:
    SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
```

## Rollback Plan

**Scenario**: GitHub Actions becomes unsuitable (outages, pricing changes, policy violations)

**Recovery Steps** (15 minutes):
```bash
# 1. Restart APScheduler daemon
uv run python scripts/start_scheduler.py --daemon

# 2. Verify daemon running
ps aux | grep start_scheduler

# 3. Disable GitHub Actions workflow (via UI or CLI)
gh workflow disable update-database.yml

# 4. Update documentation
# Revert CLAUDE.md and README.md changes

# 5. (Optional) Delete GitHub Releases
gh release list | grep "daily-" | cut -f1 | xargs -I {} gh release delete {} --yes
```

**Data Loss**: None (database snapshots retained in GitHub Releases for 30 days)

## Multi-Daily Updates (Optional Enhancement)

**To run 2-3x per day**, edit workflow schedule:

```yaml
# .github/workflows/update-database.yml
on:
  schedule:
    - cron: '0 3 * * *'   # 3:00 AM UTC (existing)
    - cron: '0 11 * * *'  # 11:00 AM UTC (add for 2x daily)
    - cron: '0 19 * * *'  # 7:00 PM UTC (add for 3x daily)
```

**Commit and push**:
```bash
git add .github/workflows/update-database.yml
git commit -m "feat(ci): increase update frequency to 3x daily"
git push
```

**Expected behavior**:
- Each run updates yesterday's data (idempotent)
- Multiple runs same day = same result (no duplicates)
- Storage impact: None (replaces existing "latest" release)

## Success Criteria

**Deployment Complete** when:
- ✅ Workflow appears in GitHub Actions UI
- ✅ Repository permissions configured (read+write)
- ✅ First manual run completes successfully
- ✅ Database published to GitHub Releases

**Migration Complete** when:
- ✅ 3+ consecutive successful GitHub Actions runs
- ✅ Database consistency validated (local vs GitHub)
- ✅ APScheduler daemon stopped
- ✅ Documentation updated

## Support and Troubleshooting

**Documentation**:
- Architecture: `docs/decisions/0009-github-actions-automation.md`
- Detailed setup: `docs/operations/GITHUB_ACTIONS.md`
- Risk analysis: `docs/operations/GITHUB_ACTIONS_RISKS.md`

**Workflow Debugging**:
```bash
# View logs for specific run
gh run view <run-id> --log

# Download logs locally
gh run download <run-id>

# Re-run failed workflow
gh run rerun <run-id>
```

**Common Issues**: See `docs/operations/GITHUB_ACTIONS.md` Section 8 (Troubleshooting)

## Summary

**Phases**:
1. ✅ **Preparation**: Workflow, docs, scripts created
2. ✅ **Testing**: All references validated
3. ⏳ **Deployment**: Push to GitHub, configure, test run ← **YOU ARE HERE**
4. ⏳ **Migration**: Parallel operation, deprecate APScheduler

**Next Action**: Execute Phase 3 (push to GitHub and configure permissions)

**Estimated Time**: 15 minutes for Phase 3, 1 week for Phase 4
