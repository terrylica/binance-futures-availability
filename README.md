# Binance Futures Availability Database

**Track daily availability of ALL USDT perpetual futures from Binance Vision (2019-09-25 to present)**

_Symbol count is dynamic (~327 currently) - we discover and track all perpetual instruments available on each historical date._

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Coverage](https://img.shields.io/badge/coverage-80%25-green.svg)]()
[![License](https://img.shields.io/badge/license-MIT-blue.svg)]()

## Overview

Standalone DuckDB database tracking historical availability of Binance USDT-Margined (UM) perpetual futures contracts from Binance Vision S3 repository. Provides sub-second queries for "which symbols were available on date X?" with automated daily updates and volume metrics.

### Key Features

- **Complete Historical Data**: 2019-09-25 (first UM-futures launch) to present (~2240 days)
- **Dynamic Symbol Discovery**: ✅ **Auto-updated daily** - Tracks all perpetual USDT contracts (~327 currently, varies by date)
- **Fast Queries**: <1ms snapshot queries, <10ms timelines
- **Volume Metrics**: Track file size growth and S3 freshness over time
- **Small Footprint**: 50-150MB database (compressed columnar)
- **Automated Updates**: ✅ **GitHub Actions** - daily 3AM UTC, zero infrastructure
- **High Reliability**: Strict error handling, comprehensive validation checks

## Quick Start

### Option 1: GitHub Actions (Recommended) ✅

**Production-ready automated updates with zero infrastructure overhead.**

#### 1. Initial Database Creation

```bash
# Trigger historical backfill via GitHub Actions (one-time setup)
gh workflow run update-database.yml \
  --field update_mode=backfill \
  --field start_date=2019-09-25 \
  --field end_date=$(date -d "yesterday" +%Y-%m-%d)

# Monitor progress (estimated 25-60 minutes)
gh run watch

# Verify database created
gh release view latest
```

#### 2. Download Database

```bash
# Download from GitHub Releases
gh release download latest --pattern "availability.duckdb.gz"
gunzip availability.duckdb.gz
```

#### 3. Automated Daily Updates

**No action needed** - workflow runs automatically daily at 3:00 AM UTC. Download latest database anytime from GitHub Releases.

### Option 2: Local Development

```bash
# Install package
cd ~/eon/binance-futures-availability
uv pip install -e ".[dev]"

# Run local backfill
uv run python scripts/operations/backfill.py
```

### Query Database

```bash
# CLI queries
uv run binance-futures-availability query snapshot 2024-01-15
uv run binance-futures-availability query timeline BTCUSDT
uv run binance-futures-availability query range 2024-01-01 2024-03-31

# Python API
python -c "
from binance_futures_availability.queries import AvailabilityQueries
q = AvailabilityQueries()
print(q.get_available_symbols_on_date('2024-01-15'))
"
```

## Architecture

### Database Schema

Single table with volume metrics (ADR-0006):

`daily_availability(date, symbol, available, file_size_bytes, last_modified, url, status_code, probe_timestamp)`

**Primary Key**: (date, symbol)
**Indexes**:

- idx_symbol_date (symbol, date) - fast timeline queries
- idx_available_date (available, date) - fast symbol listings

**Volume Metrics**:

- `file_size_bytes`: ZIP file size from S3 (enables trend analysis)
- `last_modified`: S3 upload timestamp (enables freshness monitoring)

**Storage**: `~/.cache/binance-futures/availability.duckdb`

### Data Collection (Hybrid Strategy)

**Binance Vision S3**: `https://data.binance.vision/data/futures/um/daily/klines/`

**Historical Backfill** (Bulk Operations):

- Method: AWS CLI S3 listing (`aws s3 ls --no-sign-request`)
- Performance: 327 symbols × 4.5 sec = ~25 minutes
- Use case: One-time historical data collection

**Daily Updates** (Incremental Operations):

- Method: HTTP HEAD requests (parallel batch probing)
- Performance: ~327 symbols in ~1.5 seconds (150 parallel workers, empirically optimized)
- Use case: Automated daily updates via GitHub Actions (3 AM UTC)
- Benchmark: [Worker Count Optimization](docs/benchmarks/worker-count-benchmark-2025-11-15.md)

**See**: [ADR-0005: AWS CLI for Bulk Operations](docs/decisions/0005-aws-cli-bulk-operations.md)

### Error Handling

**Policy**: Strict raise-on-failure (ADR-0003)

- No retries (workflow retries next scheduled cycle)
- No fallbacks (no default values)
- No silent failures (all errors logged)

## Documentation

**Project Memory**: [CLAUDE.md](CLAUDE.md) - AI context and patterns
**SSoT Plan**: [docs/plans/v1.0.0-implementation-plan.yaml](docs/plans/v1.0.0-implementation-plan.yaml)
**Schema**: [docs/schema/availability-database.schema.json](docs/schema/availability-database.schema.json)
**MADRs**: [docs/decisions/](docs/decisions/)

**Guides**:

- [Quick Start](docs/guides/QUICKSTART.md)
- [Query Examples](docs/guides/QUERY_EXAMPLES.md)
- [Troubleshooting](docs/guides/TROUBLESHOOTING.md)

**Operations**:

- [Automation Setup](docs/operations/AUTOMATION.md)
- [Backup & Restore](docs/operations/BACKUP_RESTORE.md)
- [Monitoring](docs/operations/MONITORING.md)

## Development

### Run Tests

```bash
# Unit tests only (fast, no network)
pytest -m "not integration"

# All tests including integration (slow, requires network)
pytest

# With coverage report
pytest --cov --cov-report=html
open htmlcov/index.html
```

### Linting & Formatting

```bash
# Format code
ruff format src/ tests/

# Check linting
ruff check src/ tests/

# Fix auto-fixable issues
ruff check --fix src/ tests/
```

## Architecture Decisions

All decisions documented as MADRs:

- **[ADR-0001](docs/decisions/0001-schema-design-daily-table.md)**: Daily table pattern (not range table)
- **[ADR-0002](docs/decisions/0002-storage-technology-duckdb.md)**: DuckDB for storage
- **[ADR-0003](docs/decisions/0003-error-handling-strict-policy.md)**: Strict error handling
- **[ADR-0004](docs/decisions/0004-automation-apscheduler.md)**: APScheduler for automation (superseded by ADR-0009)
- **[ADR-0005](docs/decisions/0005-aws-cli-bulk-operations.md)**: AWS CLI for bulk operations
- **[ADR-0006](docs/decisions/0006-volume-metrics-collection.md)**: Volume metrics collection
- **[ADR-0009](docs/decisions/0009-github-actions-automation.md)**: ✅ **GitHub Actions automation** (production)
- **[ADR-0010](docs/decisions/0010-dynamic-symbol-discovery.md)**: ✅ **Dynamic symbol discovery** (daily S3 auto-update)

## SLOs (Service Level Objectives)

**Availability**: 95% of daily updates complete successfully
**Correctness**: >95% match with Binance exchangeInfo API
**Observability**: All failures logged with full context
**Maintainability**: 80%+ test coverage, all functions documented

## Related Projects

- **[gapless-crypto-data](https://github.com/terrylica/gapless-crypto-data)**: Spot OHLCV collection (similar ValidationStorage pattern)
- **[vision-futures-explorer](../gapless-crypto-data/scratch/vision-futures-explorer/)**: Initial futures discovery (source of probe functions)

## License

MIT License

## Contributing

This is a specialized internal tool. For major changes, please open an issue first to discuss what you would like to change.

Ensure tests pass and coverage remains ≥80%:

```bash
pytest --cov --cov-fail-under=80
```

## Support

**Documentation**: See [CLAUDE.md](CLAUDE.md) for complete project context
**Issues**: File issues in project repository
**Questions**: Consult docs/guides/ for common scenarios
