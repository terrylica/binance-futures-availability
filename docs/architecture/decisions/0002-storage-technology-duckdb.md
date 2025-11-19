# ADR-0002: Storage Technology - DuckDB

**Status**: Accepted

**Date**: 2025-11-12

**Context**:

We need a storage solution for ~1.6M rows of daily availability data (708 symbols × 2240 days) with the following requirements:

- **Query performance**: Sub-second snapshot queries, <10ms timeline queries
- **Portability**: Single-file database for easy backup/restore
- **Compression**: Efficient storage for repetitive data
- **Zero-ops**: No separate database server required
- **Analytics**: Support for complex aggregation queries

Three technologies were evaluated:

1. **DuckDB**: Embedded columnar OLAP database
   - Single-file storage with 3-5x compression
   - Optimized for analytical queries
   - No server process required
   - Mature Python API (duckdb>=1.0.0)

2. **SQLite**: Embedded row-oriented database
   - Single-file storage, but no compression
   - Optimized for transactional workloads
   - Poor performance for analytical queries
   - Larger file size for our use case

3. **PostgreSQL/MySQL**: Client-server databases
   - Requires separate server process
   - Complex deployment and backup
   - Overkill for single-user local database

**Decision**:

We will use **DuckDB 1.0+** as the storage technology.

**Database location**: `~/.cache/binance-futures/availability.duckdb`

**Python integration**:

```python
import duckdb

class AvailabilityDatabase:
    def __init__(self, db_path=None):
        if db_path is None:
            cache_dir = Path.home() / ".cache" / "binance-futures"
            cache_dir.mkdir(parents=True, exist_ok=True)
            db_path = cache_dir / "availability.duckdb"

        self.db_path = db_path
        self.conn = duckdb.connect(str(db_path))
        self._create_schema()
```

**Consequences**:

**Positive**:

- **Columnar compression**: 50-150MB total size (vs 250-500MB uncompressed)
- **Fast analytical queries**: Column-oriented storage optimized for filtering/aggregation
- **Zero dependencies**: No server installation or configuration
- **Simple backup**: Single file copy (`cp ~/.cache/binance-futures/availability.duckdb backup/`)
- **Proven pattern**: Follows ValidationStorage from gapless-crypto-data project
- **Cross-platform**: Works on macOS, Linux, Windows

**Negative**:

- **Single writer**: No concurrent writes (not an issue for our use case)
- **Not a transactional database**: Optimized for analytics over ACID guarantees

**Performance validation**:

- Snapshot query (708 symbols for single date): <1ms
- Timeline query (2240 days for single symbol): <10ms
- Date range query (90 days × 708 symbols): <100ms

**Related Decisions**:

- ADR-0001: Daily table schema design
- ADR-0009: GitHub Actions automation (single-writer requirement)
