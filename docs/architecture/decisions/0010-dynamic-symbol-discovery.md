# ADR-0010: Dynamic Symbol Discovery

**Status**: Implemented

**Date**: 2025-11-15

**Deciders**: Terry Li, Claude Code

**Related**: ADR-0009 (GitHub Actions), ADR-0003 (Error Handling), ADR-0005 (AWS CLI)

## Context

Static symbol list (`symbols.json` last updated 2025-11-12) becomes stale as Binance lists new perpetual futures contracts (~1-2 new symbols per week). Missing new symbols means incomplete historical data collection.

**User Request**: "This is not the best approach because newly available symbols before the probe will not be discovered. So I would suggest we probe every time."

**Clarified Requirements**:

- Discovery frequency: Daily (at 3AM UTC, same schedule as data updates)
- Discovery method: S3 XML API (proven 0.51s performance from vision-futures-explorer)
- Storage: Auto-update symbols.json + git auto-commit
- Backfill: Manual trigger (new symbols probed going forward, backfilled on next manual run)
- Delisting: Never remove symbols (probe forever per user decision)
- Failure handling: Fail workflow if discovery fails (strict consistency)

## Decision

Implement automated daily symbol discovery using S3 XML API, integrated into GitHub Actions workflow.

### Architecture

**Discovery Module**: `src/binance_futures_availability/probing/s3_symbol_discovery.py`

- Ported from `vision-futures-explorer/futures_discovery.py`
- S3 XML bucket listing (no AWS credentials required)
- Performance: ~0.51s for ~369 symbols

**Discovery Script**: `scripts/operations/discover_symbols.py`

- Calls `discover_all_futures_symbols()`
- Updates `symbols.json` when changes detected
- Logs new/removed symbols

**Workflow Integration**: `.github/workflows/update-database.yml`

- Runs BEFORE data collection (daily + backfill modes)
- Git auto-commit when symbols.json changes
- Fails workflow on discovery errors (strict mode)

### Behavior

**New Symbols Detected**:

1. Update symbols.json immediately
2. Git auto-commit with `[skip ci]` tag
3. New symbols probed going forward
4. Historical backfill: Manual trigger via `workflow_dispatch`

**No Changes**: Exit cleanly, no file write, no commit

**Discovery Failure**: Raise immediately → fail workflow → retry next scheduled cycle

**Removed Symbols**: Log warning but NEVER remove from list (probe forever)

## Rationale

**Daily vs Every-Run**: User initially requested "every time" but clarified to daily (3AM UTC) during Q&A. Daily discovery balances freshness (new symbols within 24h) with efficiency (365 calls/year vs 730+ for twice-daily).

**S3 XML vs AWS CLI**: S3 XML API is faster (0.51s vs ~1-2s), no AWS CLI dependency, pure Python implementation.

**S3 XML vs exchangeInfo API**: S3 is canonical source for historical data. exchangeInfo only shows currently listed symbols, missing delisted symbols needed for historical backfill.

**Auto-commit vs PR**: Direct commit to main enables zero-friction automation. Symbol changes are low-risk (additive only, never remove).

**Strict Failure Mode**: Discovery failure indicates potential S3 outage or network issues. Failing workflow ensures symbol list freshness over availability (data consistency prioritized).

## Consequences

### Positive (SLO-Aligned)

**Availability SLO**: "Discovery failure fails workflow"

- Strict consistency over availability
- Clear failure signals in GitHub Actions UI
- Automatic retry next scheduled cycle

**Correctness SLO**: "S3 XML API canonical source"

- All symbols from Vision S3 bucket
- Validated against exchangeInfo in existing cross-check
- Git history provides full audit trail

**Observability SLO**: "All changes logged"

- New symbols logged to workflow output
- Git commits show exact changes with timestamps
- GitHub Actions artifacts preserve snapshots

**Maintainability SLO**: "Reuse proven code"

- Copied from vision-futures-explorer (battle-tested)
- Minimal custom logic (180 lines total)
- Standard logging, error handling

### Negative

**Discovery Overhead**: +0.51s daily (365 calls/year)

- Mitigation: Sub-second performance, negligible impact

**Git Commit Noise**: Auto-commits when symbols change

- Mitigation: `[skip ci]` prevents workflow loops, meaningful commit messages

**Delayed Backfill**: New symbols not historically backfilled automatically

- Mitigation: User controls backfill timing, explicit workflow trigger

## Compliance

### ADR-0003: Error Handling

- Discovery errors raise immediately (no retry, no fallback)
- Workflow fails on discovery failure (strict mode)
- All errors logged with full context

### ADR-0005: AWS CLI for Bulk Operations

- Discovery uses S3 XML API (not AWS CLI)
- Complements AWS CLI backfill strategy
- Consistent error handling patterns

### ADR-0009: GitHub Actions Automation

- Integrates into existing workflow
- Reuses git auto-commit pattern
- Daily schedule (3AM UTC) matches data collection

## Alternatives Considered

**Alt 1: Every-run discovery** (user's initial suggestion)

- Pro: Zero staleness, always current
- Con: +0.51s overhead every run (730+ calls/year for twice-daily)
- Rejected: User clarified daily is sufficient during Q&A

**Alt 2: Weekly discovery**

- Pro: Minimal overhead (52 calls/year)
- Con: Up to 7-day lag for new symbols
- Rejected: Too slow for typical listing frequency

**Alt 3: Manual-only discovery**

- Pro: Zero automation overhead
- Con: Defeats purpose of automation
- Rejected: User explicitly wants automated discovery

**Alt 4: AWS CLI directory listing**

- Pro: Consistent with backfill infrastructure
- Con: Slower (~1-2s), AWS CLI dependency
- Rejected: S3 XML faster and simpler

**Alt 5: exchangeInfo API**

- Pro: Official Binance API, simple
- Con: Misses delisted symbols (breaks historical backfill)
- Rejected: Incomplete for historical use case

## Implementation Notes

**Deployment**: 2025-11-15

**Files Modified**:

- Created: `src/binance_futures_availability/probing/s3_symbol_discovery.py` (180 lines)
- Created: `scripts/operations/discover_symbols.py` (150 lines)
- Modified: `.github/workflows/update-database.yml` (added discovery + auto-commit steps)

**Testing**:

- Local test: `uv run python scripts/operations/discover_symbols.py`
- Workflow test: Manual trigger via `workflow_dispatch`
- Monitor: First scheduled run at 3AM UTC

**Performance**: Validated 0.51s discovery time (consistent with vision-futures-explorer benchmark)

## References

- vision-futures-explorer: Source of discovery code
- ADR-0003: Error handling policy
- ADR-0005: AWS CLI bulk operations
- ADR-0009: GitHub Actions automation
