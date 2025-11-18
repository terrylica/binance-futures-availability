# ADR-0013: Volume Rankings Time-Series Archive

**Status**: Proposed
**Date**: 2025-11-17
**Deciders**: Terry Li, Claude Code
**Related**: ADR-0007 (Trading Volume Metrics), ADR-0009 (GitHub Actions), ADR-0012 (Auto-Backfill)

## Context

Database contains comprehensive volume metrics (`quote_volume_usdt`, `trade_count`) for all 327 perpetual futures symbols from 2019-09-25 onwards (ADR-0007 implemented). Users need ranked volume snapshots to:

- Identify top liquid markets for portfolio selection
- Track rank changes over time (momentum analysis)
- Filter symbol universe by volume percentiles
- Analyze market share shifts across symbols

**Current Gap**: No persistent archive of historical volume rankings. Users must re-query database and recalculate rankings for each analysis. No easy way to track rank changes or identify trending symbols.

**Requirements** (from user):
- Single cumulative file (not daily snapshots)
- All symbols (no filtering by minimum availability)
- Complete historical coverage (2019-2025, grows daily)
- Machine-optimized format (DuckDB/QuestDB parseable)
- Rank change tracking (1-day, 7-day, 14-day, 30-day windows)
- Forever retention (complete archive)
- Zero manual maintenance (fully automated)

## Decision

Create single **cumulative Parquet time-series archive** containing daily volume rankings for all symbols across all historical dates, updated automatically via GitHub Actions.

### Architecture

**File**: `volume-rankings-timeseries.parquet` (published to GitHub Releases "latest")

**Structure**: Time-series dataset with one row per (date, symbol) combination
- **Rows**: ~733,000 (2,242 dates × 327 symbols)
- **Columns**: 13 (date, symbol, rank, volume metrics, 4 rank change windows, metadata)
- **Size**: ~20 MB compressed Parquet (vs 85 MB CSV, 220 MB if uncompressed)
- **Growth**: +50 KB daily (~327 new rows appended)

**Update Strategy**: Incremental append
- Download existing file from GitHub Release
- Query database for dates newer than file's latest date
- Calculate rankings and append new rows
- Upload updated file to same release

### Schema

```
date: DATE                      # Trading date (UTC)
symbol: STRING                  # Futures symbol
rank: UINT16                    # Daily volume rank (1=highest, DENSE_RANK)
quote_volume_usdt: DOUBLE       # USDT trading volume
trade_count: UINT64             # Number of trades
rank_change_1d: INT16           # Rank Δ vs 1 day ago (NULL if N/A)
rank_change_7d: INT16           # Rank Δ vs 7 days ago (NULL if N/A)
rank_change_14d: INT16          # Rank Δ vs 14 days ago (NULL if N/A)
rank_change_30d: INT16          # Rank Δ vs 30 days ago (NULL if N/A)
percentile: FLOAT32             # Percentile rank (0-100, 0=top)
market_share_pct: FLOAT32       # % of total market volume
days_available: UINT8           # Days available in trailing 30 days
generation_timestamp: TIMESTAMP # When ranking was calculated
```

### Ranking Algorithm

**Metric**: `quote_volume_usdt` (USDT-denominated trading volume)
**Function**: `DENSE_RANK() OVER (PARTITION BY date ORDER BY quote_volume_usdt DESC)`
**Tie-breaking**: Alphabetical by symbol (display only, tied symbols get same rank)
**Cohort**: All symbols with `available=TRUE` and `quote_volume_usdt IS NOT NULL` on that date
**Sign convention**: Negative rank_change = improvement (moved up), positive = decline (moved down)

### Workflow Integration

Add step to `.github/workflows/update-database.yml` after database validation:
1. Download existing `volume-rankings-timeseries.parquet` from latest release
2. Run `.github/scripts/generate_volume_rankings.py` (incremental append)
3. Validate Parquet schema and row count
4. Upload updated file to same "latest" release

**Failure handling** (ADR-0003): Rankings failure does NOT block database publication. Log error, skip rankings update, retry next cycle.

## Consequences

### Positive

**Single source of truth**: One file contains complete ranking history (no need to download 2,000+ daily snapshots)

**Query performance**: Parquet columnar format enables fast filtered queries
- `SELECT * WHERE date='2025-11-13'` → <10ms (row group filtering)
- `SELECT * WHERE symbol='BTCUSDT'` → <50ms (column projection)

**Machine-optimized**: DuckDB/QuestDB native Parquet support (no CSV parsing overhead)

**Storage efficient**: 20 MB for 733K rows (vs 85 MB CSV) with typed columns and compression

**Automated maintenance**: GitHub Actions appends daily, zero manual intervention

**Complete history**: Forever retention enables long-term trend analysis and backtesting

### Negative

**Large file size**: 20 MB (vs 8 KB for daily snapshots). Download time: ~2-5 seconds on typical connection. Mitigated by: DuckDB can stream-read Parquet from URL without full download.

**Append-only complexity**: Cannot edit historical rankings (immutable). Mitigation: Regenerate entire file if schema changes (rare).

**Parquet dependency**: Requires pyarrow library. Mitigation: Already available in Python ecosystem, minimal dependency.

### Neutral

**No filtering**: Includes all symbols even with 0 volume days. Alternative would be filtered cohorts (adds complexity). Current design provides complete snapshot for user-side filtering.

**No aggregations**: File contains daily ranks, not pre-computed rolling averages. Users query for their desired aggregation window. Keeps file focused on raw rankings.

## Implementation

### Phase 1: Script Development
- Create `.github/scripts/generate_volume_rankings.py`
- Implement SQL ranking query with window functions
- Add Parquet serialization with proper schema
- Support incremental append (detect existing file's latest date)

### Phase 2: Workflow Integration
- Add rankings generation step to `update-database.yml`
- Download existing file from release before generation
- Upload updated file after validation
- Add rankings stats to workflow summary

### Phase 3: Testing & Validation
- Unit tests for ranking calculation
- Schema validation tests
- Incremental append tests
- Integration test with sample database

### Phase 4: Documentation
- Usage guide (DuckDB query examples)
- Schema reference
- Performance benchmarks

## Success Criteria

- ✅ Parquet file generated with correct schema (13 columns)
- ✅ All historical dates included (2019-09-25 to present)
- ✅ Ranks calculated correctly (highest volume = rank 1)
- ✅ Rank changes match manual calculation
- ✅ File size <50 MB for current data (~733K rows)
- ✅ Incremental append works (no duplicate dates)
- ✅ DuckDB can query latest date in <10ms
- ✅ Workflow adds <3 minutes to total runtime

## References

- ADR-0007: Trading Volume Metrics (source of quote_volume_usdt data)
- ADR-0009: GitHub Actions Automation (deployment platform)
- ADR-0003: Error Handling (strict raise policy applies)
- Plan: `docs/plans/0013-volume-rankings/plan.yaml`
