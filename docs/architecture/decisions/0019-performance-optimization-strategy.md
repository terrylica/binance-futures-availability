# ADR-0019: Performance Optimization Strategy

**Status**: Accepted

**Date**: 2025-11-20

**Deciders**: Performance Engineer, System Architect

**Technical Story**: Implement targeted performance optimizations (HTTP connection pooling, DNS caching, DuckDB compression, materialized views) delivering 9-15% faster execution and 60% storage reduction with zero complexity trade-offs.

## Context and Problem Statement

Current performance baseline (established in ADR-0005, ADR-0009):

- **Daily update time**: 1.48s ± 0.07s (150 workers, 327 symbols)
- **Database size**: 50-150 MB (2,240+ days, uncompressed)
- **Query performance**: <1ms snapshots, <10ms timelines, <100ms analytics
- **Network bottleneck**: Probe phase = 0.95s (64% of total runtime)

While already excellent, research identified **proven optimizations** with high ROI:

1. **HTTP Connection Pooling**: 7% faster (eliminate SSL/TLS handshake overhead)
2. **DNS Cache Warming**: 3% faster on cold start
3. **Column Compression**: 60% storage reduction (transparent to queries)
4. **Materialized Views**: 50x faster analytics queries (50-100ms → 1-2ms)

All optimizations validated via empirical benchmarks with **zero complexity trade-offs** (no new algorithms, no distributed systems, no caching layers).

## Decision Drivers

- **Maintainability SLO**: Optimizations must not increase code complexity
- **Correctness SLO**: Compression must be transparent (no data loss)
- **Observability SLO**: Connection pooling must not hide network errors
- **Availability SLO**: Optimizations must not introduce new failure modes
- **Proven Techniques**: Use mature libraries (urllib3, DuckDB features)
- **Measurable Impact**: Empirical benchmarks show 9-15% improvement + 60% storage reduction

## Considered Options

### Option 1: Status Quo (No Optimizations)

Keep current implementation:

- Plain urllib requests (new connection per probe)
- No DNS caching
- No DuckDB compression
- No materialized views

**Pros**:

- Zero effort
- No risk of regressions

**Cons**:

- Missing **free improvements** (2 hours work for 60% storage reduction)
- Network overhead (SSL handshake every request)
- Storage growth (150MB → 300MB+ as data accumulates)
- Slow analytics queries (100ms GROUP BY operations)

### Option 2: Targeted Low-Hanging Fruit (CHOSEN)

Implement 4 proven optimizations with zero complexity trade-offs:

**Phase 1: Network Optimizations** (1.5 hours)

1. **HTTP Connection Pooling** (15 min):

   ```python
   # Before: New connection per request
   urllib.request.urlopen(url)

   # After: Reuse pooled connections
   urllib3.PoolManager().request('HEAD', url)
   ```

   **Impact**: 7% faster (200-300ms savings from SSL/TLS reuse)

2. **DNS Cache Warming** (5 min):

   ```python
   # Warm DNS cache once before batch
   socket.gethostbyname('data.binance.vision')
   ```

   **Impact**: 3% faster on cold start (50ms DNS lookup avoided)

3. **Column Compression** (10 min):
   ```sql
   CREATE TABLE daily_availability (
       symbol VARCHAR USING COMPRESSION dict,
       file_size_bytes BIGINT USING COMPRESSION bitpacking,
       ...
   )
   ```
   **Impact**: 60% storage reduction (50-150MB → 20-50MB), zero query overhead

**Phase 2: Query Acceleration** (30 min)

4. **Materialized Views** (30 min):
   ```sql
   CREATE TABLE daily_symbol_counts (
       date DATE PRIMARY KEY,
       available_count INTEGER
   )
   -- Refresh after daily inserts
   ```
   **Impact**: 50x faster analytics (50-100ms → 1-2ms)

**Pros**:

- **High ROI**: 2 hours work for 9-15% performance + 60% storage reduction
- **Zero Complexity**: Uses proven library features (urllib3, DuckDB)
- **Low Risk**: All changes backward-compatible, rollback trivial
- **Measurable**: Benchmarks validate improvements
- **Transparent**: Compression/pooling invisible to queries

**Cons**:

- Testing effort (2 hours implementation + validation)
- HTTP pooling requires urllib3 dependency (already used transitively)

### Option 3: Aggressive Optimizations

Add Redis caching, move to TimescaleDB, implement custom connection manager.

**Pros**:

- Potential for larger improvements

**Cons**:

- **HIGH COMPLEXITY**: Distributed systems, operational overhead
- **HIGH RISK**: New failure modes (cache staleness, Redis outage)
- **Not Justified**: Current performance already excellent (1.48s daily updates)
- **Research explicitly recommends against this**

## Decision Outcome

**Chosen option**: **Option 2: Targeted Low-Hanging Fruit**

### Rationale

1. **Proven ROI**: Performance Optimization Report (16KB, 530 lines) shows validated benchmarks:
   - HTTP pooling: 7% faster (urllib3 production-tested)
   - DNS caching: 3% faster (Python stdlib, thread-safe)
   - Compression: 60% storage reduction (DuckDB standard feature)
   - Materialized views: 50x analytics speedup (SQL pattern)

2. **Zero Complexity Trade-offs**:
   - No new algorithms or data structures
   - No distributed systems or external services
   - No caching layers or async code
   - Just leveraging existing library features

3. **Low Risk**:
   - urllib3 is production-tested (powers `requests` library)
   - DuckDB compression is transparent (automatic decompression)
   - Materialized views are standard SQL (refresh in transaction)
   - Full rollback available (disable compression, remove views)

4. **Addresses Current Bottleneck**:
   - Network I/O = 64% of runtime (pooling directly targets this)
   - Storage growth trajectory (compression prevents future issues)
   - Analytics queries bottleneck (materialized views eliminate GROUP BY)

### Implementation Strategy

**Phase 1: HTTP Connection Pooling** (15 min)

**File**: `src/binance_futures_availability/probing/s3_vision.py`

```python
import urllib3

# Module-level pool (reused across probes)
HTTP_POOL = urllib3.PoolManager(
    num_pools=1,
    headers={'User-Agent': 'binance-futures-availability/1.0'}
)

def check_symbol_availability(symbol: str, date: date) -> dict:
    """Probe S3 Vision for symbol availability using pooled connections."""
    url = construct_url(symbol, date)
    response = HTTP_POOL.request('HEAD', url, timeout=10)
    # ... rest unchanged
```

**Phase 2: DNS Cache Warming** (5 min)

**File**: `src/binance_futures_availability/probing/batch_prober.py`

```python
import socket

class BatchProber:
    def __init__(self):
        # Warm DNS cache once
        try:
            socket.gethostbyname('data.binance.vision')
        except:
            pass  # Continue if DNS fails
```

**Phase 3: Column Compression** (10 min)

**File**: `src/binance_futures_availability/database/schema.py`

```python
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS daily_availability (
    date DATE NOT NULL,
    symbol VARCHAR NOT NULL USING COMPRESSION dict,
    available BOOLEAN NOT NULL,
    file_size_bytes BIGINT USING COMPRESSION bitpacking,
    last_modified VARCHAR USING COMPRESSION dict,
    url VARCHAR NOT NULL USING COMPRESSION dict,
    status_code INTEGER NOT NULL USING COMPRESSION bitpacking,
    probe_timestamp TIMESTAMP NOT NULL,
    PRIMARY KEY (date, symbol)
)
"""
```

**Phase 4: Materialized View** (30 min)

**File**: `src/binance_futures_availability/database/availability_db.py`

```python
def create_daily_counts_view(self):
    """Create materialized view for daily symbol counts."""
    self.conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_symbol_counts (
            date DATE PRIMARY KEY,
            available_count INTEGER NOT NULL
        )
    """)

def refresh_daily_counts(self):
    """Refresh materialized view after daily inserts."""
    self.conn.execute("""
        DELETE FROM daily_symbol_counts;
        INSERT INTO daily_symbol_counts
        SELECT date, COUNT(*) as available_count
        FROM daily_availability
        WHERE available = true
        GROUP BY date
    """)
```

### Validation Criteria

✅ HTTP pooling: 7% faster daily updates (benchmark before/after)
✅ DNS caching: 3% faster cold start (measure first run)
✅ Compression: 50-70% storage reduction (check .duckdb file size)
✅ Materialized views: <2ms analytics queries (time SELECT from view)
✅ All tests pass (pytest)
✅ Database validation >95% match with API
✅ No data loss (validate row counts unchanged)

## Consequences

### Positive

- **Performance**: 9-15% faster daily updates (1.48s → 1.35s cumulative)
- **Storage**: 60% reduction (50-150MB → 20-50MB)
- **Analytics**: 50x faster queries (50-100ms → 1-2ms)
- **Scalability**: Storage efficiency prevents future growth issues
- **Foundation**: Enables larger feature expansion (funding rates, OI) without bloat

### Negative

- **Implementation Effort**: 2 hours (minimal for benefits gained)
- **DuckDB Compression**: Requires DuckDB 1.4+ (addressed by ADR-0018)
- **Materialized View Maintenance**: Must refresh after inserts (5ms overhead)

### Neutral

- **urllib3 Dependency**: Already used transitively by pytest/httpx
- **Query Performance**: Compression transparent (zero overhead after decompression)
- **Connection Pool Size**: Single pool sufficient for 150 workers

## Compliance

### SLOs Addressed

- ✅ **Availability**: Connection pooling reduces SSL handshake failures
- ✅ **Correctness**: Compression verified lossless (DuckDB guarantee)
- ✅ **Observability**: Pooling preserves error visibility (urllib3 logs)
- ✅ **Maintainability**: Zero complexity increase (uses library features)

### Error Handling

Optimizations follow ADR-0003 strict raise policy:

- ✅ HTTP pooling errors raise immediately (urllib3.exceptions)
- ✅ DNS cache failures continue (graceful degradation, not critical path)
- ✅ Compression errors abort table creation (DuckDB validation)
- ✅ Materialized view refresh errors propagate (transaction rollback)

### Documentation Standards

- ✅ **No promotional language**: Focus on bottleneck analysis, not "faster is better"
- ✅ **Abstractions over implementation**: Explain "why pooling helps" not "how urllib3 works"
- ✅ **Intent over implementation**: Document decision drivers (scalability, efficiency), not just code

## Links

- **Research**: `docs/research/2025-week1-sprint/PERFORMANCE_OPTIMIZATION_REPORT.md` (16KB, empirical benchmarks)
- **urllib3 Documentation**: https://urllib3.readthedocs.io/en/stable/
- **DuckDB Compression**: https://duckdb.org/docs/sql/statements/create_table#compression
- **Related ADRs**:
  - ADR-0002: Storage Technology - DuckDB (compression features)
  - ADR-0005: AWS CLI for Bulk Operations (HTTP HEAD request optimization)
  - ADR-0018: Technology Stack Upgrade 2025 (enables DuckDB compression)

## Notes

This optimization strategy is part of Week 1-2 Sprint (comprehensive infrastructure improvements). Associated plan: `docs/development/plan/0019-performance-optimization/plan.md` with `adr-id=0019`.

**Benchmark Methodology**: Performance Engineer sub-agent ran empirical tests with 119,355 records (327 symbols × 365 days), measuring before/after latency and storage. Full benchmark script: `docs/research/2025-week1-sprint/duckdb_micro_benchmarks.py`.
