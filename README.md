# Binance Futures Availability Database

**Track daily availability of 708 USDT perpetual futures from Binance Vision (2019-09-25 to present)**

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Coverage](https://img.shields.io/badge/coverage-80%25-green.svg)]()
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## Overview

Standalone DuckDB database tracking historical availability of Binance USDT-Margined (UM) perpetual futures contracts from Binance Vision S3 repository. Provides sub-second queries for "which symbols were available on date X?" with automated daily updates.

### Key Features

- **Complete Historical Data**: 2019-09-25 (first UM-futures launch) to present (~2240 days)
- **All Perpetual Futures**: 708 USDT perpetual contracts tracked
- **Fast Queries**: <1ms snapshot queries, <10ms timelines
- **Small Footprint**: 50-150MB database (compressed columnar)
- **Automated Updates**: APScheduler daemon for daily 2AM UTC updates
- **High Reliability**: 80%+ test coverage, strict error handling

## Quick Start

### Installation

```bash
cd ~/eon/binance-futures-availability

# Install package
uv pip install -e .

# Install development dependencies
uv pip install -e ".[dev]"
```

### Run Historical Backfill

```bash
# One-time backfill from 2019-09-25 to yesterday (~25 minutes with AWS CLI)
uv run python scripts/run_backfill_aws.py
```

### Start Automated Updates

```bash
# Start scheduler daemon (daily updates at 2 AM UTC)
uv run python scripts/start_scheduler.py --daemon

# Check scheduler status
ps aux | grep start_scheduler

# Stop scheduler
uv run python scripts/start_scheduler.py --stop
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

Single table: `daily_availability(date, symbol, available, file_size_bytes, last_modified, url, status_code, probe_timestamp)`

**Primary Key**: (date, symbol)
**Indexes**:

- idx_symbol_date (symbol, date) - fast timeline queries
- idx_available_date (available, date) - fast symbol listings

**Storage**: `~/.cache/binance-futures/availability.duckdb`

### Data Collection (Hybrid Strategy)

**Binance Vision S3**: `https://data.binance.vision/data/futures/um/daily/klines/`

**Historical Backfill** (Bulk Operations):

- Method: AWS CLI S3 listing (`aws s3 ls --no-sign-request`)
- Performance: 327 symbols × 4.5 sec = ~25 minutes
- Use case: One-time historical data collection

**Daily Updates** (Incremental Operations):

- Method: HTTP HEAD requests (parallel batch probing)
- Performance: 708 symbols in ~5 seconds
- Use case: Automated daily updates at 2 AM UTC

**See**: [ADR-0005: AWS CLI for Bulk Operations](docs/decisions/0005-aws-cli-bulk-operations.md)

### Error Handling

**Policy**: Strict raise-on-failure (ADR-0003)

- No retries (scheduler retries next cycle)
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
- **[ADR-0004](docs/decisions/0004-automation-apscheduler.md)**: APScheduler for automation
- **[ADR-0005](docs/decisions/0005-aws-cli-bulk-operations.md)**: AWS CLI for bulk operations

## SLOs (Service Level Objectives)

**Availability**: 95% of daily updates complete successfully
**Correctness**: >95% match with Binance exchangeInfo API
**Observability**: All failures logged with full context
**Maintainability**: 80%+ test coverage, all functions documented

## Related Projects

- **[gapless-crypto-data](https://github.com/terrylica/gapless-crypto-data)**: Spot OHLCV collection (similar ValidationStorage pattern)
- **[vision-futures-explorer](../gapless-crypto-data/scratch/vision-futures-explorer/)**: Initial futures discovery (source of probe functions)

## License

MIT License - see [LICENSE](LICENSE) file for details

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
