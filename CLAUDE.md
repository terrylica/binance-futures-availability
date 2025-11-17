# Binance Futures Availability Database

**Version**: v1.0.0
**Created**: 2025-11-12
**Updated**: 2025-11-17
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

### [0007: Trading Volume Metrics](docs/decisions/0007-trading-volume-metrics.md)

**Status**: ⚠️ PROPOSED (not yet implemented)
**Decision**: Extend daily_availability table with 9 OHLCV columns from Binance Vision 1d klines
**Rationale**: Portfolio universe selection, survivorship bias elimination, volume-based symbol ranking

### [0008: Workspace Organization](docs/decisions/0008-workspace-organization.md)

**Decision**: Cleanup legacy code, fix documentation drift, consolidate redundant guides
**Rationale**: 30+ broken script references, 70% doc overlap between CLAUDE.md and README.md

### [0009: GitHub Actions Automation](docs/decisions/0009-github-actions-automation.md)

**Decision**: Replace APScheduler daemon with GitHub Actions for daily updates and distribution
**Rationale**: Zero infrastructure overhead, 99.9% SLA, built-in observability, automated GitHub Releases publishing
**Supersedes**: ADR-0004 (APScheduler)

### [0010: Dynamic Symbol Discovery](docs/decisions/0010-dynamic-symbol-discovery.md)

**Decision**: Daily S3 XML API enumeration to auto-update symbols.json with git auto-commit
**Rationale**: Detect new symbol listings within 24 hours, eliminate manual symbol.json maintenance, never remove delisted symbols

### [0011: 20-Day Lookback Reliability](docs/decisions/0011-20day-lookback-reliability.md)

**Decision**: Probe last 20 days on each daily update (not just yesterday)
**Rationale**: Auto-repair gaps from previous failures, handle S3 publishing delays, update changed volume metrics, validate data continuity

### [0012: Auto-Backfill New Symbols](docs/decisions/0012-auto-backfill-new-symbols.md)

**Decision**: Conditional auto-backfill workflow step that detects symbol gaps and backfills historical data for new symbols only
**Rationale**: Zero manual intervention when Binance lists new symbols, complete historical coverage within 24 hours of discovery, zero overhead when no new symbols (99% of runs)

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

**SSoT**: See [`docs/schema/availability-database.schema.json`](docs/schema/availability-database.schema.json)

**Summary**:
- **Table**: `daily_availability` with PRIMARY KEY (date, symbol)
- **Volume Metrics** (ADR-0006): `file_size_bytes`, `last_modified` enable trend analysis
- **Indexes**: Optimized for snapshot (~1ms) and timeline (~10ms) queries
- **Storage**: `~/.cache/binance-futures/availability.duckdb` (50-150 MB compressed)

**See README.md for schema details and query examples**

## Data Collection

### Source

**Binance Vision S3**: `https://data.binance.vision/data/futures/um/daily/klines/`
**URL Pattern**: `{base}/{symbol}/1m/{symbol}-1m-{YYYY-MM-DD}.zip`

### Hybrid Collection Strategy (ADR-0005)

**Backfill**: AWS CLI S3 listing (~1.1 min for full history, 327 symbols)
**Daily Updates**: HTTP HEAD requests (~1.5 sec, 150 workers, GitHub Actions 3AM UTC)
**Details**: See [ADR-0005](docs/decisions/0005-aws-cli-bulk-operations.md) and [worker benchmark](docs/benchmarks/worker-count-benchmark-2025-11-15.md)

### Symbol Discovery

**Dynamic Discovery** (ADR-0010): S3 XML API enumeration (~327 symbols, daily 3AM UTC)
**Auto-Update**: symbols.json committed when changes detected
**Details**: See [ADR-0010](docs/decisions/0010-dynamic-symbol-discovery.md)

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
**Monitoring**: See [MONITORING.md](docs/operations/MONITORING.md)

**Error Handling**: Strict raise policy (ADR-0003), workflow retries next cycle on failure

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

**Status**: Production-ready (automated daily updates at 3:00 AM UTC)

**Complete setup instructions**: See [README.md Quick Start](README.md#quick-start)

**Key Points**:
- First-time setup: Manual backfill via `gh workflow run` (creates initial database)
- Automated execution: Daily at 3:00 AM UTC (zero manual intervention)
- Distribution: GitHub Releases with gzip compression
- Monitoring: `docs/operations/MONITORING.md`

### Query Database

**Complete examples**: See [docs/guides/QUERY_EXAMPLES.md](docs/guides/QUERY_EXAMPLES.md)

**Quick reference**:
```bash
# CLI queries
uv run binance-futures-availability query snapshot 2024-01-15
uv run binance-futures-availability query timeline BTCUSDT

# Python API
from binance_futures_availability.queries import AvailabilityQueries
```

**Volume metrics queries**: See ADR-0006 and QUERY_EXAMPLES.md

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

**See**: [README.md](README.md) for database status checks, validation, and query examples

## Troubleshooting

**See**: [TROUBLESHOOTING.md](docs/guides/TROUBLESHOOTING.md) for common issues (database not found, S3 probe failures, validation errors, workflow debugging)

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
