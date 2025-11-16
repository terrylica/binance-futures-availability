# Binance Futures Availability Database

**Version**: v1.0.0
**Created**: 2025-11-12
**Updated**: 2025-11-15
**Status**: Production-ready (GitHub Actions automation enabled)
**Pattern**: Follows `ValidationStorage` pattern from gapless-crypto-data
**Purpose**: Track daily availability of ALL USDT perpetual futures from Binance Vision (2019-09-25 to present)

**Note**: Symbol count is dynamic - we discover and probe all perpetual instruments available on each date. Current count: ~327 active symbols, but historical dates may have different counts as instruments are listed/delisted over time.

## Quick Links

- **SSoT Plan**: [`docs/plans/v1.0.0-implementation-plan.yaml`](docs/plans/v1.0.0-implementation-plan.yaml)
- **Schema**: [`docs/schema/availability-database.schema.json`](docs/schema/availability-database.schema.json)
- **MADRs**: [`docs/decisions/`](docs/decisions/)
- **Guides**: [`docs/guides/`](docs/guides/)

## Architecture Decisions

All architectural decisions documented as MADRs in `docs/decisions/`:

### [0001: Schema Design - Daily Table Pattern](docs/decisions/0001-schema-design-daily-table.md)

**Decision**: Use daily availability table (not range table) for simple append-only updates
**Rationale**: Idempotent inserts, point-in-time accuracy, future-proof for suspensions/relistings

### [0002: Storage Technology - DuckDB](docs/decisions/0002-storage-technology-duckdb.md)

**Decision**: DuckDB for single-file columnar storage
**Rationale**: 50-150MB database, sub-second analytical queries, no server overhead

### [0003: Error Handling - Strict Raise Policy](docs/decisions/0003-error-handling-strict-policy.md)

**Decision**: Raise+propagate all errors immediately, no retries/fallbacks
**Rationale**: Fail fast, workflow retries next scheduled cycle, explicit error visibility

### [0004: Automation - APScheduler](docs/decisions/0004-automation-apscheduler.md)

**Status**: ⚠️ SUPERSEDED by ADR-0009 (GitHub Actions automation)

### [0005: AWS CLI for Bulk Operations](docs/decisions/0005-aws-cli-bulk-operations.md)

**Decision**: Hybrid approach - AWS CLI for historical backfill, HTTP HEAD for daily updates
**Rationale**: AWS CLI is 7.2x faster for bulk operations (25 min vs 3 hours), HEAD requests simpler for incremental updates

### [0006: Volume Metrics Collection](docs/decisions/0006-volume-metrics-collection.md)

**Decision**: Collect file_size_bytes and last_modified from both collection methods
**Rationale**: Zero marginal cost, enables volume analytics and audit trails, minimal storage overhead (25 MB)

## Core Principles

### Error Handling

**Policy**: Raise and propagate all errors immediately
**No retries**: Network failures raise immediately, workflow retries next scheduled cycle
**No fallbacks**: No default values or silent handling
**No silent failures**: All errors logged with full context

### Dependencies

**OSS libraries only**: DuckDB, urllib3, AWS CLI
**Avoid custom implementations**: Use proven libraries, not custom code
**Hybrid tooling**: Right tool for each job (AWS CLI for bulk, HEAD requests for incremental)
**Automation**: GitHub Actions (zero infrastructure overhead, 99.9% SLA)

### SLOs (Service Level Objectives)

Focus on 4 dimensions (explicitly **not** speed/performance/security):

**Availability**:

- Target: 95% of daily updates complete successfully
- Measurement: Monitor GitHub Actions workflow logs for completion rate

**Correctness**:

- Target: >95% match with Binance exchangeInfo API for current date
- Measurement: Daily validation cross-check

**Observability**:

- Target: All failures logged with full context (symbol, date, HTTP status, error message)
- Measurement: Structured logs with timestamp, level, component, error details

**Maintainability**:

- Target: 80%+ test coverage, all public functions documented
- Measurement: pytest --cov, docstring coverage check

## Database Schema

### Table: `daily_availability`

Primary table storing daily symbol availability checks with volume metrics:

```sql
CREATE TABLE daily_availability (
    date DATE NOT NULL,
    symbol VARCHAR NOT NULL,
    available BOOLEAN NOT NULL,
    file_size_bytes BIGINT,              -- Volume metrics (ADR-0006)
    last_modified TIMESTAMP,             -- S3 freshness tracking (ADR-0006)
    url VARCHAR NOT NULL,
    status_code INTEGER NOT NULL,
    probe_timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (date, symbol)
);
```

**Volume Metrics** (ADR-0006):

- `file_size_bytes`: ZIP file size from S3 (NULL for unavailable files)
- `last_modified`: S3 upload timestamp (NULL for unavailable files or missing headers)
- **Use Cases**: Volume trend analysis, data freshness monitoring, audit trails
- **Collection**: Extracted from AWS CLI listings (backfill) and HTTP headers (daily updates)

### Indexes

**PRIMARY KEY (date, symbol)**: Fast snapshot queries (~1ms for 708 symbols)
**idx_symbol_date (symbol, date)**: Fast timeline queries (~10ms for 2240 days)
**idx_available_date (available, date)**: Fast symbol listing queries

### Storage

**Location**: `~/.cache/binance-futures/availability.duckdb`
**Size**: 50-150 MB (compressed columnar storage, includes volume metrics)
**Growth**: ~50 MB/year

## Data Collection

### Source

**Binance Vision S3**: `https://data.binance.vision/data/futures/um/daily/klines/`
**URL Pattern**: `{base}/{symbol}/1m/{symbol}-1m-{YYYY-MM-DD}.zip`

### Hybrid Collection Strategy (ADR-0005)

**Historical Backfill** (Bulk Operations):

- **Method**: AWS CLI S3 listing (`aws s3 ls --no-sign-request`)
- **Module**: `probing/aws_s3_lister.py`
- **Script**: `scripts/operations/backfill.py`
- **Performance**: 327 symbols × 4.5 sec = ~25 minutes for full history
- **Use Case**: One-time bulk data collection (2019-09-25 to present)

**Daily Updates** (Incremental Operations):

- **Method**: HTTP HEAD requests (parallel batch probing)
- **Modules**: `probing/s3_vision.py`, `probing/batch_prober.py`
- **Workflow**: `.github/workflows/update-database.yml` (GitHub Actions automation)
- **Performance**: 327 symbols in ~1.5 seconds (150 parallel workers, empirically optimized)
- **Use Case**: Automated daily updates at 3:00 AM UTC
- **Benchmark**: See `docs/benchmarks/worker-count-benchmark-2025-11-15.md`

### Symbol Discovery

**Dynamic Discovery** (ADR-0010 - Implemented 2025-11-15):

- **Method**: S3 XML API bucket enumeration
- **Schedule**: Daily at 3:00 AM UTC (GitHub Actions workflow)
- **Performance**: ~0.51 seconds (proven benchmark from vision-futures-explorer)
- **Count**: ~327 perpetual USDT futures (varies as new symbols listed)
- **Auto-Update**: symbols.json automatically updated and committed when changes detected
- **Module**: `probing/s3_symbol_discovery.py` (ported from vision-futures-explorer)
- **Script**: `scripts/operations/discover_symbols.py`

**Backfill Behavior**:

- **New symbols**: Probed going forward from discovery date
- **Historical backfill**: User triggers manually via workflow_dispatch
- **Delisted symbols**: Never removed, continue probing forever (ADR-0010 decision)
- **Failure handling**: Discovery failure fails workflow (strict consistency per ADR-0003)

## Automation

### Primary: GitHub Actions (ADR-0009) - **PRODUCTION-READY**

**Technology**: GitHub Actions with GitHub Releases distribution
**Status**: ✅ Deployed and operational (as of 2025-11-15)
**Frequency**: Daily at 3:00 AM UTC (automated via cron schedule)
**Job**: Update yesterday's data (S3 Vision has T+1 availability)
**Distribution**: Automated publishing to GitHub Releases (gzip compressed)
**Cost**: $0/month (public repos: unlimited Actions minutes + storage)
**SLA**: 99.9% (GitHub Actions platform guarantee)

**Workflow**: `.github/workflows/update-database.yml`
**First Run**: Manual backfill required to create initial database (see Quick Start)
**Monitoring**: GitHub Actions UI → Workflow runs page

### Update Logic

1. Check if yesterday already processed (skip if yes - idempotent)
2. Probe all perpetual symbols via S3 HEAD requests (currently ~327, dynamically discovered)
3. Bulk insert results into DuckDB (UPSERT on conflict)
4. Run validation checks (continuity, symbol count, cross-check)
5. Log results (success/failure with details)
6. (GitHub Actions only) Compress and upload to GitHub Releases

### Error Handling

**On probe failure**: Raise immediately, log error with full context
**GitHub Actions**: Fail workflow, retry on next scheduled cycle (daily at 3 AM UTC)
**Notification**: GitHub Actions UI (built-in), optional email/Slack webhooks
**Geo-blocking (HTTP 451)**: Validation skips cross-check gracefully, logs warning

## Testing

### Coverage Requirements

**Target**: 80%+ test coverage (enforced by pytest-cov)
**Unit tests**: Mock S3 responses, test database operations
**Integration tests**: Hit live S3 Vision API (marked with `@pytest.mark.integration`)

### Running Tests

```bash
# Unit tests only (fast, no network)
pytest -m "not integration"

# All tests including integration (slow, requires network)
pytest

# With coverage report
pytest --cov=src/binance_futures_availability --cov-report=html
```

## Key Dependencies

### Required

- **duckdb>=1.0.0**: Columnar database engine
- **urllib3>=2.0.0**: HTTP client for S3 HEAD requests

### Development

- **pytest>=8.0.0**: Testing framework
- **pytest-cov>=5.0.0**: Coverage reporting
- **pytest-mock>=3.14.0**: Mocking for unit tests
- **ruff>=0.4.0**: Linting and formatting

## Quick Start

### Installation

```bash
# Clone or navigate to project
cd ~/eon/binance-futures-availability

# Install package in development mode
uv pip install -e .

# Install development dependencies
uv pip install -e ".[dev]"
```

### Run Historical Backfill

```bash
# Backfill from 2019-09-25 (first UM-futures) to yesterday
uv run python scripts/operations/backfill.py

# Estimated time: ~25 minutes (AWS CLI bulk listing)
# Database size after: 50-150 MB
```

### Production: GitHub Actions Automation (ADR-0009) ✅

**Status**: Production-ready and operational (automated daily updates at 3:00 AM UTC)

#### First-Time Setup: Run Historical Backfill

```bash
# Trigger manual backfill via GitHub Actions (creates initial database)
gh workflow run update-database.yml \
  --field update_mode=backfill \
  --field start_date=2019-09-25 \
  --field end_date=$(date -d "yesterday" +%Y-%m-%d)

# Monitor progress (estimated 25-60 minutes)
gh run watch

# Verify database created
gh release view latest
```

#### Trigger Manual Daily Update

```bash
# Run manual update for yesterday
gh workflow run update-database.yml --field update_mode=daily

# Monitor execution (~20 seconds)
gh run watch
```

#### Download Latest Database

```bash
# Download compressed database from GitHub Releases
gh release download latest --pattern "availability.duckdb.gz"
gunzip availability.duckdb.gz

# Query locally
duckdb availability.duckdb "SELECT COUNT(*) FROM daily_availability"
```

**Automated Execution**: Runs automatically daily at 3:00 AM UTC (no manual intervention needed)

### Query Database

```bash
# CLI query interface
uv run binance-futures-availability query snapshot 2024-01-15
uv run binance-futures-availability query timeline BTCUSDT
uv run binance-futures-availability query range 2024-01-01 2024-03-31

# Python API - Basic availability queries
python -c "
from binance_futures_availability.queries import AvailabilityQueries
q = AvailabilityQueries()
print(q.get_available_symbols_on_date('2024-01-15'))
"

# Volume metrics queries (ADR-0006)
python -c "
from binance_futures_availability.database import AvailabilityDatabase

db = AvailabilityDatabase()

# Average file size growth over time
growth = db.query('''
    SELECT date, AVG(file_size_bytes) as avg_size
    FROM daily_availability
    WHERE available
    GROUP BY date
    ORDER BY date
''')

# Find symbols with abnormal volume spikes
spikes = db.query('''
    SELECT symbol, date, file_size_bytes
    FROM daily_availability
    WHERE file_size_bytes > 20000000  -- > 20MB
    ORDER BY file_size_bytes DESC
    LIMIT 10
''')
"
```

### Validate Database

```bash
# Run all validation checks
uv run python scripts/validate_database.py

# Checks:
# - Date continuity (no missing dates)
# - Symbol count per date (should be 100-700)
# - Cross-check with Binance exchangeInfo API (>95% match)
```

## Related Projects

### gapless-crypto-data

Spot OHLCV data collection with ValidationStorage pattern (this project follows same pattern)

### vision-futures-explorer

Initial futures discovery exploration (source of probe functions)

**Location**: `gapless-crypto-data/scratch/vision-futures-explorer/`
**Files copied**:

- `historical_probe.py` → `src/binance_futures_availability/probing/s3_vision.py`
- `futures_discovery.py` → `src/binance_futures_availability/probing/symbol_discovery.py`

## SSoT Documentation

All specification documents follow SSoT principles:

### Implementation Plan

**File**: `docs/plans/v1.0.0-implementation-plan.yaml`
**Format**: YAML with OpenAPI-style structure
**Version**: Semantic versioning (currently 1.0.0)
**Content**: Phases, deliverables, SLOs, dependencies, risks, success criteria

### Schema Specification

**File**: `docs/schema/availability-database.schema.json`
**Format**: JSON Schema Draft 7
**Content**: Table definitions, indexes, data types, constraints, SLOs

### Query Patterns

**File**: `docs/schema/query-patterns.schema.json`
**Format**: JSON Schema Draft 7
**Content**: Common query patterns, performance targets, example code

## Project Structure

```
binance-futures-availability/
├── CLAUDE.md                      # This file (project memory)
├── README.md                      # User-facing documentation
├── pyproject.toml                 # Package configuration
│
├── docs/
│   ├── decisions/                 # MADR decision records
│   ├── schema/                    # JSON Schema specifications
│   ├── plans/                     # SSoT implementation plans
│   ├── guides/                    # User guides
│   └── operations/                # Operations documentation
│
├── src/
│   └── binance_futures_availability/
│       ├── database/              # DuckDB operations
│       ├── probing/               # S3 Vision probing
│       ├── queries/               # Query helpers
│       ├── validation/            # Data validation
│       └── cli/                   # CLI interface
│
├── tests/                         # pytest test suite
├── scripts/                       # Operational scripts
└── .cache/                        # Runtime data (database, logs)
```

## Common Operations

### Check Database Status

```python
from binance_futures_availability.database import AvailabilityDatabase

db = AvailabilityDatabase()
last_update = db.get_last_update_date()
print(f"Last updated: {last_update}")
```

### Validation After Update

```python
from binance_futures_availability.validation import AvailabilityValidator

validator = AvailabilityValidator()
report = validator.run_all_validations()

if report['validation_passed']:
    print("✅ All validation checks passed")
else:
    print(f"❌ Validation failed: {report}")
```

## Troubleshooting

### Database File Not Found

**Error**: `FileNotFoundError: availability.duckdb`
**Solution**: Run backfill first: `uv run python scripts/operations/backfill.py`

### S3 Probe Failures

**Error**: `HTTPError: 403 Forbidden`
**Cause**: Rate limiting from S3
**Solution**: Reduce probe rate in code (currently 2 req/sec)

### Low Symbol Count

**Error**: Validation reports <100 symbols for a date
**Cause**: Incomplete probe (network failure mid-run)
**Solution**: Re-run update for that date (idempotent)

## Development Workflow

### Make Changes

```bash
# Edit source files
vim src/binance_futures_availability/database/availability_db.py

# Run tests
pytest tests/test_database/test_availability_db.py

# Check coverage
pytest --cov --cov-report=html
open htmlcov/index.html
```

### Run Linting

```bash
# Format code
ruff format src/ tests/

# Check linting
ruff check src/ tests/

# Fix auto-fixable issues
ruff check --fix src/ tests/
```

### Update Documentation

When making changes:

1. Update relevant MADR if architecture changes
2. Update SSoT plan if phases/SLOs change
3. Update JSON Schema if database schema changes
4. Update CLAUDE.md if core principles change

## Support & References

### Binance Vision Documentation

- **Data Repository**: https://data.binance.vision/
- **GitHub**: https://github.com/binance/binance-public-data
- **API Docs**: https://binance-docs.github.io/apidocs/futures/en/

### DuckDB Documentation

- **Official Docs**: https://duckdb.org/docs/
- **Python API**: https://duckdb.org/docs/api/python/overview
- **Performance**: https://duckdb.org/why_duckdb

## Version History

### v1.0.0 (2025-11-12)

- Initial implementation
- Historical backfill (2019-09-25 to present)
- Automated daily updates (APScheduler, later migrated to GitHub Actions per ADR-0009)
- All 6 MADRs documented and approved
- 80%+ test coverage achieved
- Volume metrics collection (file_size_bytes, last_modified)
