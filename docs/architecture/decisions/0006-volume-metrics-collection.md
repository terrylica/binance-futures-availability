# ADR-0006: Volume Metrics Collection

**Status**: Accepted
**Date**: 2025-11-14
**Deciders**: Terry Li, Claude Code
**Related**: ADR-0001 (Schema Design), ADR-0005 (AWS CLI)

## Context

The database schema includes `file_size_bytes` and `last_modified` columns alongside availability data. These fields were initially designed for audit trails but enable powerful analytics about data volume trends and S3 update patterns.

## Decision

Collect volume metrics (`file_size_bytes`, `last_modified`) from both collection methods (AWS CLI and HTTP HEAD) and expose them for analytical queries.

### Collection Strategy

**AWS CLI Method** (Historical Backfill):

- Extract file size and last modified from `aws s3 ls` output
- Format: `2022-03-21 01:58:10  56711 BTCUSDT-1m-2019-12-31.zip`
- Parsing: Direct extraction from listing columns

**HTTP HEAD Method** (Daily Updates):

- Extract from HTTP response headers
- `Content-Length` → `file_size_bytes`
- `Last-Modified` → `last_modified` (RFC 2822 format)
- Fallback: NULL if headers missing

## Rationale

### Use Cases Enabled

**Data Volume Analytics**:

- Track historical file size growth (e.g., "BTCUSDT grew from 50KB in 2019 to 8MB in 2024")
- Identify symbols with abnormal volume spikes (potential data quality issues)
- Estimate storage requirements for downstream pipelines

**Data Freshness Monitoring**:

- Detect stale data (last_modified significantly older than expected)
- Cross-check S3 upload times vs trading dates
- Validate T+1 availability assumptions

**Audit Trail**:

- Full provenance for each availability record
- Reconstruct historical S3 state at any point in time
- Debug data collection issues with precise timestamps

### Performance Impact

**Storage Overhead**:

- `file_size_bytes` (BIGINT): 8 bytes per row
- `last_modified` (TIMESTAMP): 8 bytes per row
- Total: 16 bytes × 1.6M rows = 25.6 MB (acceptable for 50-150MB database)

**Query Performance**:

- Both fields indexed via existing indexes (no additional indexes needed)
- Snapshot queries include file_size by default (<1ms)
- Timeline queries include file_size by default (<10ms)

### Nullability

Both fields are **NULLABLE**:

- 404 responses have no file (NULL values correct)
- Missing headers don't fail entire probe (partial data better than no data)
- Aligns with ADR-0003 strict error policy (errors raise, missing metadata does not)

## Implementation

### Database Schema

Already implemented (no changes needed):

```sql
CREATE TABLE daily_availability (
    -- ... other columns ...
    file_size_bytes BIGINT,           -- NULL for unavailable files
    last_modified TIMESTAMP,          -- NULL for unavailable files or missing header
    -- ... other columns ...
);
```

### Collection Modules

**aws_s3_lister.py**:

- `_parse_aws_output()` extracts size and timestamp from listing
- Returns: `{date, file_size_bytes, last_modified, url}`

**s3_vision.py**:

- `check_symbol_availability()` extracts from HTTP headers
- Returns: `AvailabilityCheck` TypedDict with both fields
- 404 responses: Set both to NULL

### Query API

**Snapshot Queries**:

```python
results = queries.get_available_symbols_on_date('2024-01-15')
# Returns: [{'symbol': 'BTCUSDT', 'file_size_bytes': 8421945, 'last_modified': '2024-01-16T02:15:32Z'}, ...]
```

**Timeline Queries**:

```python
timeline = queries.get_symbol_availability_timeline('BTCUSDT')
# Returns: [{'date': '2019-09-25', 'available': True, 'file_size_bytes': 7845123, 'status_code': 200}, ...]
```

**Volume Analytics** (Future):

```python
# Get file size growth over time
db.query("SELECT date, AVG(file_size_bytes) FROM daily_availability WHERE available GROUP BY date ORDER BY date")

# Detect abnormal volume spikes
db.query("SELECT symbol, date, file_size_bytes FROM daily_availability WHERE file_size_bytes > 20000000")
```

## Consequences

### Positive

- **Zero marginal cost**: Data already available in both collection methods
- **Rich analytics**: Enable volume trend analysis without additional data sources
- **Audit trail**: Full metadata for debugging and compliance
- **Future-proof**: Enables new analytical queries without schema changes

### Negative

- **Slight storage increase**: +25 MB for 1.6M rows (negligible in 50-150MB database)
- **Optional data**: NULL values require careful handling in analytics queries
- **No validation**: File sizes not cross-checked against actual downloads

### Neutral

- **Not SLO'd**: Volume metrics are informational, not service-level commitments
- **Best-effort collection**: Missing headers acceptable, don't block availability checks
- **No indexes needed**: Existing indexes sufficient for volume analytics

## Compliance

### ADR-0001 (Schema Design)

Volume metrics fit daily table pattern:

- Point-in-time snapshots: "File was 8MB on 2024-01-15"
- Append-only semantics: Historical metrics immutable
- Idempotent updates: UPSERT preserves most recent metrics

### ADR-0003 (Error Handling)

Error handling consistent:

- Missing headers → NULL (informational data, not critical)
- Parsing errors → NULL (skip malformed metadata)
- Collection errors → Raise (network failures still fail fast)

### ADR-0005 (AWS CLI)

Both collection methods extract volume metrics:

- AWS CLI: Parse from listing output (always available)
- HTTP HEAD: Extract from response headers (best-effort)

## Alternatives Considered

### Alternative 1: Store only file_size_bytes (not last_modified)

**Rejected**: `last_modified` enables freshness monitoring and is equally cheap to collect.

### Alternative 2: Make fields NOT NULL (require volume data)

**Rejected**: Violates ADR-0003 (strict error policy). Missing metadata shouldn't fail availability checks.

### Alternative 3: Store volume metrics in separate table

**Rejected**: Adds schema complexity, breaks point-in-time snapshot semantics (ADR-0001).

### Alternative 4: Don't collect volume metrics at all

**Rejected**: Data already available, storage overhead minimal, future analytics valuable.

## References

- Schema definition: `docs/schema/availability-database.schema.json`
- AWS CLI parser: `src/binance_futures_availability/probing/aws_s3_lister.py`
- HTTP HEAD probe: `src/binance_futures_availability/probing/s3_vision.py`
- Query examples: `docs/guides/QUERY_EXAMPLES.md`
