# ADR-0005: AWS CLI for Bulk Operations

**Status**: Accepted
**Date**: 2025-11-14
**Deciders**: Terry Li, Claude Code
**Related**: ADR-0003 (Error Handling)

## Context

Initial implementation used individual HTTP HEAD requests to check file existence on S3. While this works and adheres to error-handling principles, historical backfill of 2,242 days × 708 symbols (1.5M+ requests) takes ~3 hours.

Binance Vision S3 bucket supports `aws s3 ls` operations, allowing bulk listing of all files for a symbol in a single API call.

## Decision

Use AWS CLI `s3 ls` for bulk operations (historical backfill), keep HTTP HEAD requests for incremental operations (daily updates).

### Hybrid Strategy

**Historical Backfill**: AWS CLI S3 Listing

- Method: `aws s3 ls s3://data.binance.vision/.../SYMBOL/1m/ --no-sign-request`
- Returns: All dates for a symbol in one call (~4.5 seconds)
- Performance: 327 symbols × 4.5 sec = ~25 minutes
- Use case: One-time historical data collection

**Daily Updates**: HTTP HEAD Requests

- Method: Individual HEAD requests per symbol for single date
- Returns: Availability status per symbol (~708 requests)
- Performance: ~5 seconds for all symbols
- Use case: Incremental daily updates

## Rationale

**See "Updated Performance Comparison" section below for empirically validated performance data.**

### Implementation

1. **Module**: `src/binance_futures_availability/probing/aws_s3_lister.py`
   - `AWSS3Lister` class wraps AWS CLI calls
   - Parses `aws s3 ls` output into availability records
   - Extracts date, file_size, last_modified from listings

2. **Script**: `scripts/run_backfill_aws.py`
   - Parallel processing with ThreadPoolExecutor
   - Bulk database inserts (UPSERT)
   - Date range filtering for partial backfills

3. **Scheduler**: Keep existing HEAD request approach
   - `scheduler/daily_update.py` unchanged
   - Uses `probing/batch_prober.py` for parallel HEAD requests
   - Simple, proven, fast for single dates

## Consequences

### Positive

- **7.2x faster historical backfill** (25 min vs 3 hours)
- **4,587x fewer API calls** (327 vs 1.5M)
- **Lower network load** for bulk operations
- **Maintains simplicity** for daily operations (no change)

### Negative

- **AWS CLI dependency** (must be installed: `brew install awscli`)
- **Two code paths** for availability checking (bulk vs incremental)
- **Parsing complexity** (parse AWS CLI text output vs direct HTTP response)

### Neutral

- **No authentication required** (`--no-sign-request` works for public buckets)
- **Hybrid approach** is pragmatic (right tool for each job)
- **Daily operations unchanged** (no risk to existing automation)

## Compliance

### ADR-0003 (Error Handling)

AWS CLI errors raise immediately:

- `subprocess.TimeoutExpired` → RuntimeError
- `subprocess.CalledProcessError` → RuntimeError
- `FileNotFoundError` (AWS CLI missing) → RuntimeError

All errors propagate with full context, no silent failures.

## Alternatives Considered

### Alternative 1: Use AWS CLI for everything

**Rejected**: Daily updates with AWS CLI take ~53 minutes (list all 708 symbols sequentially), vs 5 seconds with parallel HEAD requests. HEAD requests are better for incremental operations.

### Alternative 2: Use S3 XML API directly

**Rejected**: More complex than AWS CLI (XML parsing, pagination), similar performance. AWS CLI is simpler.

### Alternative 3: Keep HEAD requests only

**Rejected**: 3-hour backfill is acceptable but AWS CLI's 25-minute backfill is significantly better for user experience.

## Empirical Validation

**Date**: 2025-11-15

Post-implementation empirical testing validated and refined the hybrid strategy:

### Historical Backfill (AWS CLI)

**Initial Estimate**: 327 symbols × 4.5 sec = ~25 minutes
**Actual Performance**: ~1.1 minutes for full backfill (2019-09-25 to present)
**Finding**: AWS CLI is 23x faster than estimated (estimate was conservative)

### Daily Updates (HTTP HEAD)

**Initial Configuration**: 10 parallel workers, ~5 seconds for 327 symbols
**Optimized Configuration**: 150 parallel workers, ~1.5 seconds for 327 symbols
**Speedup**: 3.94x faster with optimized worker count

**Benchmark Testing** (2025-11-15):

- Tested 8 worker counts (10-200) × 5 trials = 40 production runs
- Optimal: 150 workers (1.48s ± 0.07s, 100% success rate)
- Rate limiting: ZERO detected (tested up to 10,000 workers, 118K requests)
- See: `docs/benchmarks/worker-count-benchmark-2025-11-15.md`

### Performance Comparison (Empirically Validated 2025-11-15)

**Note**: Original estimates (2025-11-14) were conservative. Actual performance after optimization:

| Operation           | Method        | Workers | Time        | API Calls |
| ------------------- | ------------- | ------- | ----------- | --------- |
| Historical backfill | HEAD requests | 150     | ~80 minutes | 733,461   |
| Historical backfill | AWS CLI       | 10      | ~1.1 min    | 327       |
| Daily update        | HEAD requests | 10      | ~5 seconds  | 327       |
| Daily update        | HEAD requests | 150     | ~1.5 sec    | 327       |
| Daily update        | AWS CLI       | 10      | ~1.1 min    | 327       |

**Conclusion**:

- AWS CLI is optimal for bulk operations (>13 dates)
- HTTP HEAD with 150 workers is optimal for daily updates (<13 dates)
- Hybrid strategy confirmed as correct approach

## References

- vision-futures-explorer: S3 listing discovery in 0.51 seconds (753 symbols)
- AWS CLI S3 docs: https://docs.aws.amazon.com/cli/latest/reference/s3/ls.html
- Binance Vision: https://data.binance.vision/
- Worker count benchmark: docs/benchmarks/worker-count-benchmark-2025-11-15.md
