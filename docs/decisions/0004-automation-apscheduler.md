# ADR-0004: Automation - APScheduler

**Status**: Superseded by [ADR-0009: GitHub Actions Automation](0009-github-actions-automation.md)

**Date**: 2025-11-12
**Superseded Date**: 2025-11-15
**Code Removal**: Commit 5c3a9d3 (873 lines deleted)

> **Note**: This ADR documents the APScheduler-based automation that was implemented in v1.0.0 but replaced with GitHub Actions due to infrastructure overhead and cost. All APScheduler code has been removed from the codebase. This decision is preserved for historical context only.

## Historical Context

APScheduler-based automation was implemented for daily database updates (2AM UTC) but replaced with GitHub Actions due to:
- Infrastructure overhead (24/7 local server requirement)
- Manual distribution (no GitHub Releases integration)
- Cost ($5-20/month vs $0 for GitHub Actions)
- Platform lock-in (requires dedicated machine)

## Decision (Historical)

Use **APScheduler 3.10+** with SQLite job store for automated daily updates at 2:00 AM UTC.

**Approach**:
- Python BackgroundScheduler with CronTrigger
- SQLite job store for state persistence across restarts
- Daemon script for process management
- Pure Python implementation (cross-platform)

## Replacement

See [ADR-0009](0009-github-actions-automation.md) for current implementation:
- GitHub Actions with cron triggers (daily 3AM UTC)
- Automated GitHub Releases distribution
- Zero infrastructure overhead
- 99.9% SLA platform guarantee

## Implementation (Removed)

Full implementation details available in git history before commit 5c3a9d3. Key components removed:
- `scheduler/` module (APScheduler configuration)
- `scripts/start_scheduler.py` (daemon management)
- SQLite job store persistence
- APScheduler dependency from pyproject.toml

## References

- **Superseded By**: [ADR-0009: GitHub Actions Automation](0009-github-actions-automation.md)
- **Related**: [ADR-0003: Error Handling](0003-error-handling-strict-policy.md), [ADR-0005: AWS CLI](0005-aws-cli-bulk-operations.md)
