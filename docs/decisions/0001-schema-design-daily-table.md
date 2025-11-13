# ADR-0001: Schema Design - Daily Table Pattern

**Status**: Accepted

**Date**: 2025-11-12

**Context**:

We need to design a database schema to track the availability of Binance USDT perpetual futures contracts from the Binance Vision S3 repository. The primary use case is querying "which symbols were available on date X?" with sub-second response times.

Two main design patterns were considered:

1. **Daily table pattern**: One row per (date, symbol) combination
   - Example: `(2024-01-15, BTCUSDT, available=true)`
   - Append-only inserts for new dates
   - Simple queries with date filter

2. **Range table pattern**: One row per symbol with date ranges
   - Example: `(BTCUSDT, start_date=2019-09-25, end_date=NULL)`
   - Requires UPDATE operations when delisting occurs
   - Complex query logic for "available on date X"

**Decision**:

We will use the **daily table pattern** with the following schema:

```sql
CREATE TABLE daily_availability (
    date DATE NOT NULL,
    symbol VARCHAR NOT NULL,
    available BOOLEAN NOT NULL,
    file_size_bytes BIGINT,
    last_modified TIMESTAMP,
    url VARCHAR NOT NULL,
    status_code INTEGER NOT NULL,
    probe_timestamp TIMESTAMP NOT NULL,
    PRIMARY KEY (date, symbol)
);

CREATE INDEX idx_symbol_date ON daily_availability(symbol, date);
CREATE INDEX idx_available_date ON daily_availability(available, date);
```

**Consequences**:

**Positive**:
- **Append-only simplicity**: Daily updates only INSERT new rows (no UPDATE/DELETE)
- **Audit trail preservation**: Every probe result is permanently recorded
- **Simple query patterns**: Single WHERE clause for snapshot queries
- **DuckDB columnar compression**: Redundant data compressed efficiently (3-5x ratio)
- **Straightforward backfill**: Idempotent UPSERT for historical dates

**Negative**:
- **Higher row count**: 708 symbols × 2240 days = ~1.6M rows (vs ~708 rows for range pattern)
- **Storage overhead**: Mitigated by DuckDB compression (50-150MB total)

**Trade-offs**:
- Optimizes for **read simplicity** and **data immutability** over storage efficiency
- Estimated growth: ~50MB/year (708 rows/day × ~200 bytes/row compressed)
- Query performance target: <1ms for single-date snapshot (easily achievable with indexes)

**Related Decisions**:
- ADR-0002: Storage technology choice (DuckDB)
- ADR-0003: Error handling policy (strict raise)
