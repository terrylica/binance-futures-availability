# ADR-0011: 20-Day Lookback for Data Reliability

**Status**: Approved

**Date**: 2025-11-17

**Deciders**: Terry Li, Claude Code

**Related**: ADR-0003 (Error Handling), ADR-0005 (AWS CLI), ADR-0009 (GitHub Actions), ADR-0010 (Symbol Discovery)

## Context

Daily updates probe only yesterday's data (T-1), creating vulnerability to late-arriving data and transient failures. S3 Vision publishes data with variable latency (typically T+1 but occasionally delayed), and network/probe failures leave permanent gaps.

**Problem Statement**: Current 1-day lookback creates data gaps from:

1. S3 Vision publishing delays beyond expected T+1 availability
2. Network failures during daily probe (no automatic gap-filling)
3. Workflow failures (database corruption, validation threshold mismatches)
4. Symbol discovery lag (new symbols only probed from discovery date forward)

**Gap Analysis**: After fixing 6 sequential workflow failures, database has complete coverage but lacks mechanism to:

- Detect late-arriving S3 data
- Auto-repair gaps from previous failures
- Update volume metrics when S3 files change
- Validate recent data completeness beyond yesterday

**User Requirement**: "I would highly suggest we look for not just yesterday but last 20 days just to be sure."

## Decision

Extend daily update probing from 1-day (yesterday only) to 20-day rolling window (yesterday to T-20), re-probing all symbols for last 20 days on every scheduled run.

### Architecture

**Lookback Configuration**: Environment variable feature flag

- Variable: `LOOKBACK_DAYS` (default: 1, production: 20)
- Location: `.github/workflows/update-database.yml`
- Rollback: Change env var value, next run reverts to 1-day mode

**Probing Strategy**: Date range iteration with parallel symbol probing

- Method: Reuse existing `BatchProber.probe_all_symbols()` per date
- Workers: 150 parallel (empirically optimized, proven safe)
- Date loop: Sequential iteration over [T-20, T-1] range
- Idempotency: UPSERT semantics (`INSERT OR REPLACE`) handle re-probing

**Error Handling**: Circuit breaker pattern with strict failure propagation

- Abort if error rate exceeds 5% threshold within date range
- Raise immediately on circuit breaker activation (ADR-0003)
- Partial success committed to database before abort
- Workflow retry on next scheduled cycle

**Volume Metrics**: Automatic freshness updates

- Re-probe updates `file_size_bytes` if S3 file modified
- Updates `last_modified` timestamp when changed
- Enables detection of S3 re-uploads or corrections

### Behavior

**Daily Execution**: Each scheduled run (3AM UTC)

1. Calculate date range: `end_date = yesterday`, `start_date = yesterday - 19 days`
2. For each date in range (20 dates total):
   - Probe all discovered symbols (~713 perpetual currently)
   - Batch insert results with UPSERT
3. Validation checks continuity and completeness
4. Database published to GitHub Releases

**Overlapping Windows**: 19-day overlap between consecutive runs

- Today's run probes: `[T-20, T-1]`
- Tomorrow's run probes: `[T-19, tomorrow-1]`
- 19 dates re-probed daily (updates late arrivals, fills gaps)

**Gap Filling**: Automatic repair without explicit gap detection

- Missing dates from previous failures: Filled by next successful run
- Late-arriving S3 data: Updated within 20-day window
- Network errors: Recovered by subsequent runs

## Rationale

**20-Day Window Selection**:

- **Upper bound**: S3 Vision historical data rarely delayed >7 days
- **Safety margin**: 3x typical delay (7 days) provides reliability cushion
- **Validation alignment**: Weekly validation (ADR-0013) catches gaps beyond 20 days
- **Performance trade-off**: 20x S3 requests remains within tested capacity (6,540 vs 118,000 tested)

**Rolling Window vs Fixed Backfill**:

- Rolling window continuously validates recent data
- Fixed backfill misses late arrivals after backfill date
- Overlap ensures no data slips through gaps

**Feature Flag for Gradual Rollout**:

- Deploy code with `LOOKBACK_DAYS=1` (unchanged behavior)
- Manual testing with `LOOKBACK_DAYS=20` via workflow_dispatch
- Production deployment: Change env var value
- Instant rollback: Revert env var, no code changes

**UPSERT over Gap Detection**:

- Re-probing all dates simpler than gap detection logic
- UPSERT handles duplicates gracefully (PRIMARY KEY enforcement)
- Performance cost acceptable (30 seconds vs 2 seconds)
- Guaranteed complete coverage (no missed gaps from faulty detection)

## Consequences

### Positive (SLO-Aligned)

**Availability SLO**: "95% of daily updates complete successfully"

- Gap repair: Missed dates auto-filled by subsequent runs within 20 days
- Resilience: Single failure doesn't create permanent gaps
- Circuit breaker: Prevents cascade failures (abort at 5% error rate)

**Correctness SLO**: ">95% match with Binance exchangeInfo API"

- Late arrivals: S3 delays captured within 20-day window
- Volume updates: File size changes reflected in database
- Validation: Continuity checks cover 20-day recent history

**Observability SLO**: "All failures logged with full context"

- Workflow logs show exact date range probed
- Per-date success/failure visible in logs
- Circuit breaker activation clearly logged with error rate

**Maintainability SLO**: "80%+ test coverage, all functions documented"

- Reuses proven `BatchProber` infrastructure
- Feature flag enables testing without production impact
- Minimal code changes (modify date calculation only)

### Negative

**Runtime Increase**: +28 seconds per daily update

- Current: ~2 seconds (1 date × 713 symbols)
- New: ~30 seconds (20 dates × 713 symbols)
- Mitigation: Acceptable for 73-minute total workflow

**S3 Request Volume**: 20x increase (327 → 6,540 requests/day)

- Risk: Potential rate limiting
- Mitigation: Tested at 118,000 requests (18x safety margin)
- Evidence: ADR-0005 documents zero rate limiting at high volumes

**Database Write Overhead**: 20x UPSERT operations

- Additional writes: 19 dates × 713 symbols = 13,547 UPSERTs/day
- Mitigation: DuckDB columnar storage handles efficiently
- Impact: ~0.5s per batch insert (negligible)

## Compliance

### ADR-0003: Error Handling

- Circuit breaker raises on 5% error threshold (strict failure)
- No retries within single run (workflow retry next cycle)
- All probe failures logged with full context

### ADR-0005: AWS CLI for Bulk Operations

- Daily updates use HEAD requests (proven reliable)
- 20-day lookback within tested S3 capacity
- Consistent error handling patterns

### ADR-0009: GitHub Actions Automation

- Feature flag environment variable (standard pattern)
- Workflow retry on failure (built-in)
- Database publishing unchanged (compression + release)

### ADR-0010: Dynamic Symbol Discovery

- 20-day lookback probes all discovered symbols
- New symbols automatically included in rolling window
- Historical gaps addressed by auto-backfill (ADR-0012)

## Alternatives Considered

**Alt 1: Explicit gap detection + targeted backfill**

- Pro: Minimal S3 requests (probe only missing dates)
- Con: Complex gap detection logic, risk of missed gaps
- Rejected: Prefer reliability over optimization (user priority)

**Alt 2: Longer lookback window (30 or 60 days)**

- Pro: Even higher reliability margin
- Con: Linear increase in runtime and S3 requests
- Rejected: 20 days sufficient (3x typical delay), weekly validation covers beyond

**Alt 3: Exponential backoff lookback (T-1, T-3, T-7, T-14)**

- Pro: Reduced S3 requests vs full 20-day
- Con: Gaps between probe points, complex logic
- Rejected: Continuous coverage simpler and more reliable

**Alt 4: Daily gap detection without re-probing**

- Pro: Zero additional S3 requests
- Con: Requires separate backfill trigger, misses late arrivals
- Rejected: Automatic repair preferred over manual intervention

**Alt 5: Keep 1-day lookback, rely on weekly validation**

- Pro: No daily overhead
- Con: Up to 7-day gap repair delay
- Rejected: User explicitly requested daily 20-day lookback

## Implementation Notes

**Deployment**: Phased rollout over 2-3 weeks

**Phase 1: Local Testing** (2-3 days)

- Implement feature flag support in `run_daily_update.py`
- Write comprehensive unit tests (mock 20-day probing)
- Manual dry-run with test database
- Exit criteria: All tests pass, manual inspection confirms correctness

**Phase 2: Manual GitHub Actions** (3-5 days)

- Deploy code with `LOOKBACK_DAYS=1` (unchanged behavior)
- Manual workflow triggers with `LOOKBACK_DAYS=20`
- Validate 3 successful manual runs
- Exit criteria: Validation passes, no timeout/corruption

**Phase 3: Scheduled Production** (7-14 days)

- Change workflow env var: `LOOKBACK_DAYS: 20`
- Monitor 7 consecutive scheduled runs
- Exit criteria: ≥95% success rate, zero corruption incidents

**Files Modified**:

- `.github/scripts/run_daily_update.py`: Date range calculation + circuit breaker
- `.github/workflows/update-database.yml`: Add `LOOKBACK_DAYS` env var
- `tests/test_20day_lookback.py`: Unit tests (NEW)
- `tests/test_circuit_breaker.py`: Circuit breaker tests (NEW)

**Performance Validation**:

- Empirical measurement: Agent 1 analysis shows 1.48s per date
- Expected: 20 dates × 1.48s = 29.6 seconds
- Acceptable: Within 73-minute workflow budget

**Rollback Procedure**:

```yaml
# Instant rollback: Change env var and commit
env:
  LOOKBACK_DAYS: 1 # Revert from 20 to 1
```

## References

- Agent 1 Performance Analysis: 20-day lookback performance and cost assessment
- Agent 4 Regression Prevention: Testing strategy and safety mechanisms
- ADR-0003: Strict error handling policy
- ADR-0005: AWS CLI bulk operations (S3 capacity testing)
- ADR-0009: GitHub Actions automation framework
- User requirement: "look for not just yesterday but last 20 days"
