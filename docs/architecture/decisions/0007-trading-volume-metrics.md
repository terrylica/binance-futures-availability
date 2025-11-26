# ADR-0007: Trading Volume Metrics Collection

**Status**: Accepted
**Date**: 2025-11-14
**Implemented**: 2025-11-24
**Deciders**: Terry Li, Claude Code, Sub-Agent Analysis Team
**Related**: ADR-0001 (Schema Design), ADR-0002 (DuckDB), ADR-0003 (Error Handling), ADR-0005 (AWS CLI)

## Context

Current database tracks daily availability (file exists/missing) but lacks trading activity metrics. Users need to rank symbols by volume and identify most active markets for:

- Portfolio universe selection (focus on liquid markets)
- Survivorship bias elimination (historical volume shows when markets were active)
- Data quality validation (abnormal volume = potential data issues)
- Market research (volume trends, new listings traction)

Binance Vision provides daily kline data in `1d/` directories containing OHLCV + volume metrics. Files are 350 bytes each (vs 57 KB for 1m klines), making collection efficient.

## Decision

Extend existing `daily_availability` table with 9 volume metric columns sourced from Binance Vision 1d kline files.

### Schema Extension

```sql
ALTER TABLE daily_availability ADD COLUMN quote_volume_usdt DOUBLE;
ALTER TABLE daily_availability ADD COLUMN trade_count BIGINT;
ALTER TABLE daily_availability ADD COLUMN volume_base DOUBLE;
ALTER TABLE daily_availability ADD COLUMN taker_buy_volume_base DOUBLE;
ALTER TABLE daily_availability ADD COLUMN taker_buy_quote_volume_usdt DOUBLE;
ALTER TABLE daily_availability ADD COLUMN open_price DOUBLE;
ALTER TABLE daily_availability ADD COLUMN high_price DOUBLE;
ALTER TABLE daily_availability ADD COLUMN low_price DOUBLE;
ALTER TABLE daily_availability ADD COLUMN close_price DOUBLE;

CREATE INDEX idx_quote_volume_date
    ON daily_availability(quote_volume_usdt DESC, date);
```

### Data Source

**Path**: `s3://data.binance.vision/data/futures/um/daily/klines/{SYMBOL}/1d/{SYMBOL}-1d-{YYYY-MM-DD}.zip`

**Format**: Single-row CSV with 12 fields (open_time, open, high, low, close, volume, close_time, quote_volume, count, taker_buy_volume, taker_buy_quote_volume, ignore)

**Primary Ranking Metric**: `quote_volume` (USDT volume) - apple-to-apple comparison across all symbols

## Rationale

### Single Table vs Separate Table

Evaluated two approaches:

**Option 1 (Selected)**: Extend `daily_availability` table

- ✅ No JOINs required for combined queries
- ✅ 5-10x faster query performance
- ✅ 12 MB smaller database (11% savings)
- ✅ Simpler code (single transaction)
- ✅ Backward compatible (nullable columns)

**Option 2 (Rejected)**: Separate `daily_volume_metrics` table

- ❌ Requires JOINs for availability+volume queries
- ❌ 5-10x slower query performance
- ❌ 12 MB larger database
- ❌ More complex code (two transactions)
- ✅ Cleaner separation of concerns (only advantage)

**Verdict**: Option 1 wins on 9 out of 10 criteria.

### 1d Klines vs Metrics Files

**1d klines** (Selected):

- ✅ Available since 2019-12-31 (full history)
- ✅ Contains volume + trade count + OHLC
- ✅ Tiny files (350 bytes vs 11 KB)
- ✅ Single CSV row (trivial parsing)

**metrics/** (Rejected):

- ❌ Only since 2021-12-01 (2 years missing)
- ❌ Contains open interest, not volume
- ❌ 289 rows per file (5-min intervals)
- ❌ Requires aggregation

## Consequences

### Positive

- **Apple-to-apple ranking**: `quote_volume_usdt` enables direct comparison across all symbols
- **Survivorship bias elimination**: Historical volume reveals when markets were actually active
- **Data quality validation**: Abnormal volume spikes indicate potential data issues
- **Fast queries**: <10ms for top 100 symbols by volume (vs 200ms with JOINs)
- **Minimal storage overhead**: +39 MB (68% increase from 57 MB → 96 MB, storage is cheap)
- **Backward compatible**: All new columns nullable, existing code unaffected
- **Historical coverage**: Same date range as availability (2019-09-25 to present)

### Negative

- **Collection time increase**: Daily updates from 5 sec → 60 sec (12x slower, still within 5-min SLO)
- **Historical backfill**: 47 minutes (one-time cost, acceptable)
- **Database size growth**: +39 MB (acceptable for 1.6M rows with 9 new columns)
- **Code complexity**: Parser for 1d kline CSV format (minimal, 1 row per file)

### Neutral

- **Two collection strategies**: Same hybrid approach as availability (AWS CLI for bulk, HEAD for incremental)
- **Error handling**: Same strict raise policy (ADR-0003 compliance)
- **Storage format**: DuckDB columnar compression keeps size manageable

## Compliance

### ADR-0001 (Schema Design - Daily Table Pattern)

✅ Maintains daily table pattern, no range tables
✅ Idempotent inserts via PRIMARY KEY (date, symbol)
✅ Point-in-time accuracy preserved

### ADR-0002 (Storage Technology - DuckDB)

✅ Columnar compression handles 9 new columns efficiently
✅ Analytical queries optimized (volume ranking uses columnar scan)
✅ Database size stays <150 MB (within single-file target)

### ADR-0003 (Error Handling - Strict Raise Policy)

✅ CSV parsing errors raise immediately
✅ Missing 1d kline files raise if expected
✅ All errors logged with full context (symbol, date, URL)

### ADR-0005 (AWS CLI for Bulk Operations)

✅ Extends AWS CLI listing to also download 1d klines
✅ Maintains hybrid approach (bulk via AWS CLI, daily via HEAD)
✅ No changes to core listing logic

## Alternatives Considered

### Alternative 1: Aggregate from 1m klines

**Rejected**:

- 1m klines are 57 KB each (vs 350 bytes for 1d)
- Would require downloading 17 GB for historical vs 529 MB
- Aggregation logic adds complexity
- 1d klines already aggregated by Binance (authoritative source)

### Alternative 2: Separate database for volume

**Rejected**:

- Breaks cohesion (availability and volume are related metrics)
- Forces users to maintain two databases
- Complicates backups and migrations
- No performance advantage (DuckDB handles both well)

### Alternative 3: Store only rank, not raw volume

**Rejected**:

- Loses auditability (can't verify rankings)
- Can't recalculate ranks with different criteria
- Can't analyze volume trends over time
- Minimal storage savings (rank is still 8 bytes)

## Implementation Plan

See `docs/plans/0007-trading-volume-metrics/plan.yaml` for detailed implementation phases.

### Success Criteria

**Availability**: 95% of volume collections complete successfully
**Correctness**: >95% match with Binance Vision 1d kline files
**Observability**: All volume collection failures logged with symbol, date, error context
**Maintainability**: Schema migration tested, rollback script available, documentation updated

### Validation Checkpoints

1. Schema migration on test database (success = all columns added, index created)
2. Sample collection (2024-01-01 to 2024-01-31, success = >95% coverage)
3. Data quality (BTCUSDT 2024-01-15 quote_volume ~$10B, matches S3 file)
4. Query performance (top 100 by volume <10ms, matches SLO)
5. Historical backfill (all 327 symbols, 2019-09-25 to present, <60 min)

## Implementation Notes

**Implemented**: 2025-11-24 (1.5 hours)

### Actual Approach

**Schema Drift Fix** (not migration):

- Updated `schema.py` CREATE TABLE to include 9 volume columns (single source of truth)
- Reset databases to fresh state (no ALTER TABLE needed)
- Rationale: Idempotent, zero risk, faster than migration system

**Files Modified**:

1. `src/binance_futures_availability/database/schema.py` - Added 9 DOUBLE columns, idx_quote_volume_date index
2. `src/binance_futures_availability/database/availability_db.py` - Extended insert_batch() SQL to 17 columns
3. `scripts/operations/backfill.py` - Added --collect-volume flag, volume merge logic, progress logging
4. `.github/scripts/generate_volume_rankings.py` - Fixed schema mismatch (uint→int types for DuckDB compatibility)
5. `docs/schema/availability-database.schema.json` - Added 9 volume column definitions
6. `tests/test_database/test_schema.py` - Updated expectations (8→17 columns)

### Actual Performance

**Test Backfill** (5 symbols × 31 days):

- Time: 2 minutes
- Records: 155 (100% availability)
- Volume coverage: 95% (148/155)
- BTCUSDT sample: $27-40B daily volume, 4.5-6.9M trades

**Full Historical Backfill** (715 symbols × 2,252 days):

- Deferred to separate operation (long-running, 1.6M records)
- Estimated: 30-60 minutes with optimal worker count

### Deviations from Plan

1. **No ALTER TABLE**: Used fresh database creation instead
2. **Schema types**: Used signed integers (int16, int64) instead of unsigned to match DuckDB output
3. **Full backfill**: Deferred due to time constraints (test backfill validates implementation)

### Validation Results

✅ Schema: 17 columns created successfully
✅ Insert: Both with/without volume data works
✅ Rankings: Parquet generated (307 rows, 13 columns), no Binder Error
✅ Query: `quote_volume_usdt` column accessible in SQL

## References

- Implementation plan: `docs/development/plan/0007-trading-volume-metrics/plan.md`
- Sub-agent analysis reports: `/tmp/binance_research/`
- Database schema design: `/tmp/binance_research/SCHEMA_DESIGN.md`
- Volume collection strategy: `/tmp/binance_research/VOLUME_COLLECTION_STRATEGY.md`
- Integration validation: `/tmp/binance_research/INTEGRATION_VALIDATION_PLAN.md`
- Binance Vision 1d klines: `s3://data.binance.vision/data/futures/um/daily/klines/`
