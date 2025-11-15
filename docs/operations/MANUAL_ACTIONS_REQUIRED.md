# Manual Actions Required (ADR-0009 Phase 3-4)

**Status**: Automation code complete, awaiting user execution
**Implementation Plan**: `docs/plans/0009-github-actions-automation/plan.yaml`
**Deployment Guide**: `docs/operations/DEPLOYMENT_GUIDE.md`

## Overview

ADR-0009 implementation is **complete** for automated portions (Phases 1-2). The following manual actions are required to complete deployment (Phase 3) and migration (Phase 4).

**Current State**:
- ✅ Phase 1 (Preparation): Complete
- ✅ Phase 2 (Testing): Complete
- ⏳ Phase 3 (Deployment): Awaiting manual actions
- ⏳ Phase 4 (Migration): Awaiting manual actions

**Automated Deliverables Ready**:
- GitHub Actions workflow: `.github/workflows/update-database.yml`
- Validation scripts: `scripts/validate-workflow-deployment.sh`
- Consistency verification: `scripts/verify-database-consistency.py`
- Monitoring dashboard: `scripts/monitor-workflow-metrics.sh`
- Complete documentation: `docs/operations/GITHUB_ACTIONS.md`, `DEPLOYMENT_GUIDE.md`

## Phase 3: Deployment (15 minutes)

### Action 1: Configure Repository Permissions ⚠️ REQUIRED

**Why**: GitHub Actions needs write permissions to create releases and upload database files.

**Steps**:
1. Navigate to: https://github.com/terrylica/binance-futures-availability/settings/actions
2. Scroll to **"Workflow permissions"** section
3. Select: **"Read and write permissions"**
4. Click **"Save"**

**Validation**:
```bash
# Check permissions (requires admin access)
gh api repos/:owner/:repo/actions/permissions

# Should show: "enabled": true
```

**Error if skipped**: Workflow will fail with "Resource not accessible by integration"

---

### Action 2: Trigger First Manual Run ⚠️ REQUIRED

**Why**: Validate workflow executes successfully before relying on scheduled runs.

**Steps**:
```bash
# Trigger daily update mode
gh workflow run update-database.yml --field update_mode=daily

# Get the run ID
RUN_ID=$(gh run list --workflow=update-database.yml --limit 1 --json databaseId --jq '.[0].databaseId')

# Watch execution in real-time
gh run watch $RUN_ID

# Or view in browser
gh run view $RUN_ID --web
```

**Expected Duration**: 5-10 minutes

**Success Criteria**:
- ✅ All jobs complete with green checkmarks
- ✅ Database uploaded to GitHub Releases as "latest"
- ✅ Validation checks pass (visible in workflow logs)

**Troubleshooting**:
```bash
# If workflow fails, view logs
gh run view $RUN_ID --log

# Check for common issues
./scripts/validate-workflow-deployment.sh
```

---

### Action 3: Verify Release Created ⚠️ REQUIRED

**Why**: Confirm database is publicly accessible via GitHub Releases.

**Steps**:
```bash
# List recent releases
gh release list --limit 5

# Expected output includes:
# latest    Latest Release    ...

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

**Expected**: Database with 700K+ records

**Success Criteria**:
- ✅ "latest" release tag exists
- ✅ Database file `availability.duckdb.zst` is downloadable (~41 MB)
- ✅ Decompressed database is valid DuckDB file

---

**Phase 3 Complete When**:
- ✅ Repository permissions configured
- ✅ First manual run completed successfully
- ✅ Database published to GitHub Releases

**Estimated Time**: 15 minutes

---

## Phase 4: Migration and Monitoring (1 week)

### Action 4: Parallel Operation (Days 1-3) ℹ️ RECOMMENDED

**Why**: Validate consistency between APScheduler and GitHub Actions before deprecation.

**Steps**:

**Keep APScheduler Running** (if currently running):
```bash
# Check if APScheduler daemon is running
ps aux | grep start_scheduler

# If not running, start it (optional - for comparison only)
uv run python scripts/start_scheduler.py --daemon
```

**Monitor Both Systems**:
```bash
# Daily consistency check (run each morning)
uv run python scripts/verify-database-consistency.py --detailed

# Expected output:
# ✅ Databases are CONSISTENT
```

**Validation Script** (automated):
- Compares local APScheduler database with GitHub Actions database
- Reports differences in record counts, date ranges, volume data
- Performs row-by-row comparison for yesterday's data

**Success Criteria**:
- ✅ 3 consecutive days of consistent databases
- ✅ Both systems produce identical results

---

### Action 5: Monitor GitHub Actions (Days 1-7) ℹ️ RECOMMENDED

**Why**: Track SLO metrics to ensure reliability before full migration.

**Steps**:
```bash
# Daily monitoring dashboard
./scripts/monitor-workflow-metrics.sh --days 7

# Expected output:
# ✅ Availability SLO: MET (100% ≥ 95%)
# ✅ Duration SLO: MET (max 8.5 min ≤ 15 min)
# ✅ Observability SLO: MET
# ✅ Maintainability SLO: MET
```

**Key Metrics** (from plan.yaml):
- **Availability**: Success rate ≥95% (target: 100%)
- **Duration**: Average 5-10 minutes, max <15 minutes
- **Scheduled runs**: Daily at 3:00 AM UTC
- **Validation pass rate**: 100%

**SLO Dashboard**:
- Total runs: 7 (1 per day)
- Success rate: 100%
- Average duration: ~6 minutes
- Failures: 0

---

### Action 6: Deprecate APScheduler (Day 7+) ⚠️ REQUIRED

**Criteria** (all must be true):
- ✅ 3+ consecutive successful GitHub Actions runs
- ✅ Database consistency verified (identical results)
- ✅ No validation failures
- ✅ Workflow duration within expected range (5-10 minutes)

**Steps**:
```bash
# 1. Stop APScheduler daemon
uv run python scripts/start_scheduler.py --stop

# 2. Verify daemon stopped
ps aux | grep start_scheduler
# Expected: No processes found

# 3. (Optional) Remove from autostart
# If configured in cron/systemd/launchd, remove entry

# 4. Keep APScheduler code (rollback path available)
# DO NOT delete scheduler/ directory
```

**Validation**:
```bash
# Confirm only GitHub Actions is updating database
gh run list --workflow=update-database.yml --limit 5

# All runs should show "success"
```

---

### Action 7: Update Documentation (30 minutes) ℹ️ OPTIONAL

**Why**: Ensure all documentation reflects GitHub Actions as primary automation.

**Files Already Updated**:
- ✅ `CLAUDE.md` - GitHub Actions marked as primary (APScheduler deprecated)
- ✅ `docs/operations/DEPLOYMENT_GUIDE.md` - Complete deployment guide
- ✅ `docs/decisions/0009-github-actions-automation.md` - ADR accepted

**Remaining Updates** (optional):
- `README.md` - Update Quick Start section (replace APScheduler commands)
- `docs/guides/QUICKSTART.md` - Update automation section

**Changes**:
```diff
- # Start APScheduler daemon
- uv run python scripts/start_scheduler.py --daemon
+ # Database updates automated via GitHub Actions
+ # Download latest: gh release download latest --pattern "availability.duckdb.zst"
```

---

**Phase 4 Complete When**:
- ✅ 3+ consecutive successful GitHub Actions runs
- ✅ Database consistency validated
- ✅ APScheduler daemon stopped
- ✅ SLO metrics tracked and met (95% success rate, 5-10 min duration)

**Estimated Time**: 1 week (passive monitoring)

---

## Quick Reference Checklist

### Phase 3 (15 minutes - Active)
- [ ] Configure repository permissions (Settings → Actions)
- [ ] Trigger first manual run (`gh workflow run`)
- [ ] Verify release created (`gh release list`)
- [ ] Download and validate database

### Phase 4 (1 week - Passive)
- [ ] Day 1: Run consistency check (`scripts/verify-database-consistency.py`)
- [ ] Day 2: Run consistency check
- [ ] Day 3: Run consistency check
- [ ] Day 1-7: Monitor metrics (`scripts/monitor-workflow-metrics.sh`)
- [ ] Day 7+: Stop APScheduler daemon (if 3+ successful runs)
- [ ] Optional: Update remaining documentation

---

## Validation Scripts

**Workflow Deployment Validation**:
```bash
./scripts/validate-workflow-deployment.sh
# Checks: files exist, ADR↔plan sync, workflow syntax, GitHub registration
```

**Database Consistency Verification**:
```bash
uv run python scripts/verify-database-consistency.py --detailed
# Compares: local vs GitHub databases, reports differences
```

**Metrics Monitoring Dashboard**:
```bash
./scripts/monitor-workflow-metrics.sh --days 7
# Tracks: success rate, duration, SLO compliance
```

---

## Rollback Plan

**If GitHub Actions proves unsuitable**, revert to APScheduler:

```bash
# 1. Restart APScheduler daemon
uv run python scripts/start_scheduler.py --daemon

# 2. Disable GitHub Actions workflow
gh workflow disable update-database.yml

# 3. Update documentation (revert CLAUDE.md changes)
```

**Data Loss**: None (database snapshots retained in GitHub Releases for 30 days)

---

## Support

**Documentation**:
- Detailed deployment: `docs/operations/DEPLOYMENT_GUIDE.md`
- Architecture decision: `docs/decisions/0009-github-actions-automation.md`
- Implementation plan: `docs/plans/0009-github-actions-automation/plan.yaml`
- Setup guide: `docs/operations/GITHUB_ACTIONS.md`
- Risk analysis: `docs/operations/GITHUB_ACTIONS_RISKS.md`

**Troubleshooting**:
- Workflow validation: `./scripts/validate-workflow-deployment.sh`
- View workflow logs: `gh run view <run-id> --log`
- Check SLO metrics: `./scripts/monitor-workflow-metrics.sh`

**Contact**: See repository issues for support

---

## Status Tracking

**Current Phase**: 3 (Deployment - Awaiting User Action)

**Next Action**: Configure repository permissions (5 minutes)

**Automation Complete**: Yes (all code delivered)

**User Action Required**: Yes (manual GitHub UI configuration)
