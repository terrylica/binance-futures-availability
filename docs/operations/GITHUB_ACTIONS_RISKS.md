# Risks and Limitations Analysis

## Executive Summary

This document analyzes the risks and limitations of using GitHub Actions for automated DuckDB database updates, compared to the current APScheduler-based local scheduler approach.

**Overall Assessment**: ✅ **Feasible with acceptable tradeoffs**

**Key Benefits**:

- Zero infrastructure management (no servers to maintain)
- Built-in reliability and monitoring
- Free for public repositories
- Easy database distribution via GitHub Releases

**Key Risks**:

- Network dependency (S3 Vision API availability)
- GitHub Actions service availability
- Database size growth (may exceed free tier in distant future)
- No real-time updates (scheduled only)

---

## Risk Categories

### 1. Availability Risks

#### 1.1 GitHub Actions Service Outages

**Risk Level**: 🟡 MEDIUM

**Description**: GitHub Actions service may experience downtime, preventing scheduled updates.

**Impact**:

- Missed daily updates during outage window
- Database becomes stale (T+N where N = outage duration days)
- Users cannot download latest database

**Mitigation**:

- ✅ GitHub Actions has 99.9% uptime SLA ([status.github.com](https://www.githubstatus.com/))
- ✅ Workflow is idempotent - can re-run for missed dates
- ✅ Manual trigger available via `workflow_dispatch`
- ✅ Multiple update modes (daily + backfill) for gap-filling

**Probability**: Low (~0.1% downtime/month based on SLA)
**Severity**: Low (non-critical data, can backfill later)

**Acceptance Criteria**: ✅ Acceptable - SLA meets project needs

---

#### 1.2 S3 Vision API Unavailability

**Risk Level**: 🟡 MEDIUM

**Description**: Binance S3 Vision API may be temporarily unreachable or rate-limited.

**Impact**:

- Workflow fails during update phase
- No database published for that day
- Validation checks fail (cross-check with Binance API)

**Mitigation**:

- ✅ S3 Vision is public CDN with high availability
- ✅ Workflow uses parallel probing with retry logic (in code)
- ✅ Error handling: Workflow fails loudly (no silent failures)
- ✅ Next day's run will succeed (retries automatically)

**Probability**: Low (<1% based on historical observations)
**Severity**: Low (next run fixes issue)

**Acceptance Criteria**: ✅ Acceptable - network failures are expected and handled

---

#### 1.3 Database Download Failures

**Risk Level**: 🟢 LOW

**Description**: Users may fail to download database from GitHub Releases.

**Impact**:

- Users cannot access latest database
- Downstream applications stalled

**Mitigation**:

- ✅ GitHub CDN has global distribution (high availability)
- ✅ Multiple download methods (wget, gh CLI, browser)
- ✅ Both compressed and uncompressed files available
- ✅ Fallback: Users can clone repo and run backfill locally

**Probability**: Very Low (GitHub CDN is highly reliable)
**Severity**: Low (workarounds available)

**Acceptance Criteria**: ✅ Acceptable

---

### 2. Correctness Risks

#### 2.1 Data Quality Issues

**Risk Level**: 🟡 MEDIUM

**Description**: Database may contain incorrect or stale data due to:

- S3 Vision data not yet available at update time
- API inconsistencies
- Code bugs

**Impact**:

- Users download corrupted or incomplete database
- Downstream analytics produce wrong results
- Reputational damage

**Mitigation**:

- ✅ **Comprehensive validation** before publishing:
  - Continuity check (no missing dates)
  - Completeness check (≥700 symbols per date)
  - Cross-check with Binance API (>95% match SLO)
  - Test suite runs (≥80% coverage)
- ✅ **Workflow fails if validation fails** (no bad data published)
- ✅ **Versioned releases** (users can roll back if needed)
- ✅ **T+1 update window** (3 AM UTC = 1 hour after S3 Vision updates at 2 AM)

**Probability**: Very Low (multi-layer validation catches issues)
**Severity**: Medium (but prevented by validation gates)

**Acceptance Criteria**: ✅ Acceptable - validation prevents bad publishes

---

#### 2.2 Code Bugs in Workflow

**Risk Level**: 🟡 MEDIUM

**Description**: Bugs in workflow YAML or Python code may cause incorrect updates.

**Impact**:

- Wrong data inserted into database
- Workflow fails unexpectedly
- Silent failures (data looks correct but isn't)

**Mitigation**:

- ✅ **Test suite runs before publish** (catches regressions)
- ✅ **Version control** (workflow file in git, reviewable)
- ✅ **Manual testing** (dry-run script provided in SETUP.md)
- ✅ **Strict error handling** (ADR-0003: raise and propagate all errors)
- ✅ **Validation gates** (wrong data fails validation)

**Probability**: Low (test coverage + validation reduces risk)
**Severity**: Medium (validation prevents most issues)

**Acceptance Criteria**: ✅ Acceptable - testing + validation sufficient

---

### 3. Performance Risks

#### 3.1 Workflow Timeout

**Risk Level**: 🟢 LOW

**Description**: Workflow may exceed GitHub Actions timeout limits.

**Current Limits**:

- **Per-job timeout**: 6 hours (default), 360 hours (max)
- **Per-workflow timeout**: 72 hours (max)

**Expected Durations**:

- Daily update: 5-10 minutes
- Full backfill: 25-30 minutes
- Total workflow: <1 hour

**Impact**:

- Workflow cancelled mid-run
- Database not updated
- Resources wasted

**Mitigation**:

- ✅ **Ample headroom** (expected 1 hour vs 6 hour limit = 6x margin)
- ✅ **Parallel processing** (10 workers for probing)
- ✅ **AWS CLI bulk operations** (7.2x faster than HEAD requests)
- ✅ **Incremental updates** (daily mode only processes yesterday)

**Probability**: Very Low (5-10 min actual vs 360 min limit)
**Severity**: Low (retry next day)

**Acceptance Criteria**: ✅ Acceptable - large margin of safety

---

#### 3.2 Database Size Growth

**Risk Level**: 🟡 MEDIUM (Long-term)

**Description**: Database grows over time, may exceed GitHub Release asset limits or free tier storage.

**Current State**:

- Database size: 50-150 MB (as of 2024-11)
- Growth rate: ~50 MB/year
- GitHub limits:
  - **Release asset size**: 2 GB (hard limit)
  - **Free tier storage**: 500 MB (private repos)
  - **Free tier storage**: Unlimited (public repos)

**Projected Growth**:

- 2025: ~200 MB
- 2030: ~450 MB
- 2040: ~950 MB (still under 2 GB limit)

**Impact**:

- Slower downloads for users
- May exceed free tier (private repos only)
- Eventually hits 2 GB hard limit (decades away)

**Mitigation**:

- ✅ **Compression** (gzip reduces size by ~60-70%)
- ✅ **DuckDB columnar storage** (efficient compression)
- ✅ **Public repository** (unlimited storage on free tier)
- ✅ **Fallback options**:
  - Partition database by year (multiple files)
  - External storage (S3, R2, etc.) if needed
  - Database pruning (archive old data)

**Probability**: Medium (will happen eventually, but decades away)
**Severity**: Low (many solutions available)

**Acceptance Criteria**: ✅ Acceptable - decades of runway, easy fixes available

---

### 4. Cost Risks

#### 4.1 GitHub Actions Minutes Exhaustion

**Risk Level**: 🟢 LOW (Public) / 🟡 MEDIUM (Private)

**Description**: Workflow consumes GitHub Actions minutes, may exceed free tier.

**Free Tier Limits**:

- **Public repos**: Unlimited minutes
- **Private repos**: 2,000 minutes/month

**Expected Usage** (Private Repo):

- Daily update: 10 min/day × 30 days = 300 min/month
- Backfill (rare): 30 min/run × 2 runs/month = 60 min/month
- **Total**: ~360 min/month (18% of free tier)

**Impact**:

- Workflow disabled if minutes exhausted
- Must upgrade to paid plan ($4/month for 50,000 minutes)

**Mitigation**:

- ✅ **Public repository** (recommended, unlimited minutes)
- ✅ **Low usage** (360 min/month << 2,000 min/month free tier)
- ✅ **Usage monitoring** (GitHub provides alerts)
- ✅ **Cost acceptable** ($4/month if needed)

**Probability**: Very Low (public repos) / Low (private repos)
**Severity**: Very Low (cheap to upgrade)

**Acceptance Criteria**: ✅ Acceptable - free for public, cheap for private

---

#### 4.2 Storage Costs

**Risk Level**: 🟢 LOW (Public) / 🟡 MEDIUM (Private)

**Description**: Database storage in GitHub Releases may incur costs.

**Free Tier Limits**:

- **Public repos**: Unlimited storage
- **Private repos**: 500 MB

**Current Storage**:

- Uncompressed: 50-150 MB
- Compressed: 10-30 MB
- **Total**: ~200 MB (40% of private repo limit)

**Impact**:

- Storage overage charges ($0.25/GB/month)
- Must upgrade or delete old releases

**Mitigation**:

- ✅ **Public repository** (recommended, unlimited storage)
- ✅ **Well under limit** (200 MB << 500 MB)
- ✅ **Compression** (saves 60-70% space)
- ✅ **Single "latest" tag** (no historical releases stored)
- ✅ **Cheap overage** (even 1 GB extra = $0.25/month)

**Probability**: Very Low (public repos) / Low (private repos)
**Severity**: Very Low (negligible cost)

**Acceptance Criteria**: ✅ Acceptable

---

### 5. Operational Risks

#### 5.1 Workflow Misconfiguration

**Risk Level**: 🟡 MEDIUM

**Description**: Incorrect workflow configuration may cause silent failures or data corruption.

**Examples**:

- Wrong cron schedule (updates at wrong time)
- Missing permissions (can't create releases)
- Incorrect environment variables (wrong database path)
- Bad secrets configuration

**Impact**:

- Updates fail silently
- Database not published
- Wrong data inserted

**Mitigation**:

- ✅ **Comprehensive setup guide** (SETUP.md with examples)
- ✅ **Manual testing before enabling** (workflow_dispatch test)
- ✅ **Version control** (workflow changes reviewable)
- ✅ **Validation checks** (fail loudly on errors)
- ✅ **GitHub Actions summary** (visible status reports)

**Probability**: Medium (user error during setup)
**Severity**: Medium (but detectable via monitoring)

**Acceptance Criteria**: ✅ Acceptable - good documentation + testing reduces risk

---

#### 5.2 Dependency Failures

**Risk Level**: 🟡 MEDIUM

**Description**: Upstream dependencies (actions, packages) may break or become unavailable.

**Dependencies**:

- GitHub Actions: `actions/checkout@v4`, `actions/setup-python@v5`, `astral-sh/setup-uv@v5`
- Python packages: `duckdb`, `apscheduler`, `urllib3`
- System tools: AWS CLI

**Impact**:

- Workflow fails to run
- Cannot install dependencies
- Package compatibility issues

**Mitigation**:

- ✅ **Pinned action versions** (`@v4`, not `@latest`)
- ✅ **Locked dependencies** (pyproject.toml with versions)
- ✅ **Official actions only** (trusted sources)
- ✅ **Minimal dependencies** (4 OSS packages, no proprietary)
- ✅ **Dependabot** (automated updates for security)

**Probability**: Low (using stable, widely-used dependencies)
**Severity**: Medium (workflow broken until fixed)

**Acceptance Criteria**: ✅ Acceptable - stable dependencies + monitoring

---

### 6. Security Risks

#### 6.1 Supply Chain Attacks

**Risk Level**: 🟡 MEDIUM

**Description**: Compromised dependencies could inject malicious code.

**Attack Vectors**:

- Malicious GitHub Action
- Compromised PyPI package
- Malicious AWS CLI installer

**Impact**:

- Data exfiltration
- Database corruption
- Repository compromise

**Mitigation**:

- ✅ **Pinned action versions** (prevents auto-updates)
- ✅ **Official actions only** (actions/_, astral-sh/_)
- ✅ **Minimal permissions** (`GITHUB_TOKEN` with least privilege)
- ✅ **No custom secrets** (uses built-in token only)
- ✅ **Code review** (workflow changes require approval)
- ✅ **Dependabot alerts** (notifies of known vulnerabilities)

**Probability**: Low (using official, audited dependencies)
**Severity**: High (but probability very low)

**Acceptance Criteria**: ✅ Acceptable - industry-standard mitigations in place

---

#### 6.2 Token Leakage

**Risk Level**: 🟢 LOW

**Description**: `GITHUB_TOKEN` could be leaked in logs or artifacts.

**Impact**:

- Unauthorized access to repository
- Release manipulation
- Data exfiltration

**Mitigation**:

- ✅ **Automatic token masking** (GitHub redacts tokens in logs)
- ✅ **Short-lived tokens** (expires after workflow run)
- ✅ **Scoped permissions** (only `contents:write`, no admin)
- ✅ **No custom secrets** (minimal attack surface)
- ✅ **No log exposure** (tokens not printed explicitly)

**Probability**: Very Low (GitHub has strong protections)
**Severity**: Medium (but token is short-lived and scoped)

**Acceptance Criteria**: ✅ Acceptable - built-in protections sufficient

---

### 7. Limitations

#### 7.1 Not Real-Time

**Limitation**: Workflow runs on schedule, not triggered by S3 Vision updates.

**Impact**:

- Data is T+1 (yesterday's data updated today)
- Cannot provide "latest available" in real-time

**Workaround**: None (GitHub Actions doesn't support event-driven S3 triggers)

**Acceptance Criteria**: ✅ Acceptable - T+1 latency is acceptable for use case

---

#### 7.2 No Custom Runners

**Limitation**: GitHub-hosted runners only (cannot use self-hosted runners easily).

**Impact**:

- Cannot customize runner environment
- Limited to GitHub's runner specs (2 CPU, 7 GB RAM)
- No persistent local storage

**Workaround**:

- Use GitHub-hosted runners (sufficient for current workload)
- Self-hosted runners possible but require setup

**Acceptance Criteria**: ✅ Acceptable - GitHub-hosted runners meet needs

---

#### 7.3 Limited Debugging

**Limitation**: Cannot SSH into runner for debugging (unlike local scheduler).

**Impact**:

- Harder to debug issues
- Must rely on logs and local testing

**Workaround**:

- Use dry-run script for local testing
- Use `act` for local GitHub Actions emulation
- Enable debug logging in workflow

**Acceptance Criteria**: ✅ Acceptable - workarounds available

---

#### 7.4 Public Data Only

**Limitation**: Workflow designed for public S3 Vision data, not private APIs.

**Impact**:

- Cannot use for private data sources
- Cannot add authentication (without secrets)

**Workaround**: Add secrets if needed for private APIs

**Acceptance Criteria**: ✅ Acceptable - S3 Vision is public

---

## Comparison: GitHub Actions vs Local APScheduler

| Dimension         | GitHub Actions                  | Local APScheduler               | Winner            |
| ----------------- | ------------------------------- | ------------------------------- | ----------------- |
| **Availability**  | 99.9% SLA (GitHub)              | Depends on local infra          | 🟢 GitHub Actions |
| **Maintenance**   | Zero (managed service)          | Manual (OS updates, monitoring) | 🟢 GitHub Actions |
| **Cost**          | Free (public) / $4/mo (private) | Server cost (~$5-20/mo)         | 🟡 Tie            |
| **Reliability**   | Auto-restarts, monitoring       | Manual monitoring required      | 🟢 GitHub Actions |
| **Debugging**     | Logs only                       | Full SSH access                 | 🔴 APScheduler    |
| **Latency**       | T+1 (scheduled)                 | T+1 (scheduled)                 | 🟡 Tie            |
| **Scalability**   | Auto-scales                     | Limited by server               | 🟢 GitHub Actions |
| **Distribution**  | Built-in (Releases)             | Manual (S3, CDN)                | 🟢 GitHub Actions |
| **Customization** | Limited (workflow YAML)         | Full (Python code)              | 🔴 APScheduler    |
| **Security**      | Managed, audited                | DIY                             | 🟢 GitHub Actions |

**Overall**: 🟢 **GitHub Actions is superior for this use case**

---

## Decision Matrix

### Should You Use GitHub Actions?

**✅ YES if**:

- Public repository (unlimited free resources)
- T+1 latency acceptable (not real-time)
- Want zero infrastructure management
- Easy database distribution important
- Low operational overhead desired

**❌ NO if**:

- Need real-time updates (sub-hourly)
- Require custom runner environment
- Need extensive debugging (SSH access)
- Private data with complex auth (secrets management)
- Already have robust local infrastructure

---

## Recommendations

### Immediate Actions

1. ✅ **Start with GitHub Actions** (recommended)
   - Zero cost for public repos
   - Easier distribution via Releases
   - No infrastructure to maintain

2. ✅ **Run manual test** before enabling schedule

   ```bash
   gh workflow run update-database.yml --field update_mode=daily
   ```

3. ✅ **Monitor first 3 scheduled runs**
   - Check logs for errors
   - Verify database quality
   - Confirm release publishing

4. ✅ **Set up notifications** (optional but recommended)
   - Email or Slack on failure
   - Weekly summary reports

### Long-Term Planning

1. **Database Growth**: Monitor size, plan partitioning if >1 GB
2. **Cost Monitoring**: Track Actions minutes (if private repo)
3. **Validation SLOs**: Review quarterly, adjust thresholds if needed
4. **Dependency Updates**: Enable Dependabot for security patches

### Fallback Plan

If GitHub Actions becomes unsuitable:

1. **Migrate back to APScheduler**: Workflow is similar, easy to revert
2. **Use both**: GitHub Actions for backfill, APScheduler for daily updates
3. **External scheduler**: Airflow, Prefect, or other orchestration tools

---

## Conclusion

**Overall Risk Assessment**: 🟢 **LOW** (acceptable for production use)

**Key Strengths**:

- ✅ Free for public repositories
- ✅ Zero infrastructure management
- ✅ Built-in distribution (GitHub Releases)
- ✅ Comprehensive validation prevents bad data

**Key Weaknesses**:

- ⚠️ Network-dependent (S3 Vision + GitHub APIs)
- ⚠️ Limited debugging (no SSH access)
- ⚠️ Not real-time (scheduled updates only)

**Recommendation**: ✅ **PROCEED WITH GITHUB ACTIONS**

The benefits (zero maintenance, free hosting, easy distribution) significantly outweigh the risks (network dependency, limited debugging). The comprehensive validation gates prevent data quality issues, and the idempotent design allows easy recovery from failures.

**Next Steps**:

1. Test workflow manually (workflow_dispatch)
2. Enable scheduled runs
3. Monitor first week closely
4. Document any issues encountered
5. Iterate on workflow based on real-world usage
