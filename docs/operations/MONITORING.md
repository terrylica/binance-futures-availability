# Monitoring GitHub Actions Automation

**Status**: Production-ready (ADR-0009)
**Automation**: GitHub Actions (daily 3AM UTC)
**Distribution**: GitHub Releases

## Quick Health Check

```bash
# Check recent workflow runs
gh run list --workflow=update-database.yml --limit 7

# View latest run status
gh run view $(gh run list --workflow=update-database.yml --limit 1 --json databaseId --jq '.[0].databaseId')

# Check database freshness
gh release view latest --json publishedAt --jq '.publishedAt'
```

## SLO Monitoring

### Availability SLO: ≥95% Success Rate (Last 7 Days)

```bash
# Count successful runs
gh run list --workflow=update-database.yml --limit 7 --json conclusion | \
  jq '[.[] | select(.conclusion == "success")] | length'

# Target: 7/7 (100%), Minimum: 7/7 (≥95%)
```

### Correctness SLO: >95% Match with Binance exchangeInfo

```bash
# Check latest validation results
gh run view $(gh run list --workflow=update-database.yml --status=completed --limit 1 --json databaseId --jq '.[0].databaseId') --log | \
  grep "Cross-check"
```

**Note**: Validation may skip cross-check due to HTTP 451 geo-blocking (GitHub Actions runners blocked by Binance). This is expected and does not indicate data quality issues. Continuity + completeness checks provide sufficient validation.

### Observability SLO: All Failures Logged

```bash
# View failed run logs
gh run list --workflow=update-database.yml --status=failure --limit 1 --json databaseId | \
  jq -r '.[0].databaseId' | \
  xargs gh run view --log
```

## Monitoring Workflow Failures

### Common Failure Causes

1. **HTTP 451 Geo-blocking**: Binance API blocks GitHub Actions runners
   - **Impact**: Cross-check validation skipped (graceful degradation)
   - **Mitigation**: Continuity + completeness checks sufficient
   - **Action**: No action required (expected behavior)

2. **Symbol Discovery Failures**: S3 XML API timeout or network error
   - **Impact**: Workflow fails, no database update
   - **Mitigation**: Automatic retry next scheduled cycle (daily 3AM UTC)
   - **Action**: Check S3 Vision status

3. **Validation Failures**: Missing dates or low symbol counts
   - **Impact**: Database not published to releases
   - **Mitigation**: Manual trigger with backfill mode
   - **Action**: Investigate data gaps, run backfill if needed

### Manual Intervention

**Trigger immediate update**:

```bash
gh workflow run update-database.yml --field update_mode=daily
```

**Backfill specific date range**:

```bash
gh workflow run update-database.yml \
  --field update_mode=backfill \
  --field start_date=2025-11-01 \
  --field end_date=2025-11-15
```

## Alert Configuration

### GitHub Actions Notifications

1. Navigate to repository → Settings → Notifications
2. Enable "Actions" notifications
3. Choose notification channels:
   - Email (default)
   - Slack (via GitHub Slack app)
   - Custom webhooks

### Email Alerts (Personal)

```bash
# Configure GitHub CLI notifications
gh config set prompt enabled

# Test notification
gh run list --workflow=update-database.yml --status=failure --limit 1
```

## Database Freshness Monitoring

```bash
# Check time since last update
LAST_UPDATE=$(gh release view latest --json publishedAt --jq '.publishedAt')
echo "Last update: $LAST_UPDATE"

# Expected: Within last 24 hours (daily 3AM UTC)
```

## Legacy APScheduler Monitoring

**Status**: Deprecated (ADR-0004 superseded by ADR-0009)

APScheduler daemon monitoring (systemd, cron, Prometheus) is no longer applicable. See git history before commit 5c3a9d3 for historical reference.

## References

- [ADR-0009: GitHub Actions Automation](../architecture/decisions/0009-github-actions-automation.md)
- [GitHub Actions Workflow](../../.github/workflows/update-database.yml)
- [TROUBLESHOOTING.md](../guides/TROUBLESHOOTING.md) - Workflow debugging
