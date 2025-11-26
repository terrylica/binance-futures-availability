# binance-futures-availability

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![PyPI version](https://badge.fury.io/py/binance-futures-availability.svg)](https://pypi.org/project/binance-futures-availability/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![CI Status](https://github.com/terrylica/binance-futures-availability/actions/workflows/update-database.yml/badge.svg)](https://github.com/terrylica/binance-futures-availability/actions/workflows/update-database.yml)

DuckDB-based availability tracker for Binance USDT-Margined perpetual futures from Binance Vision S3.

## Installation

```bash
pip install binance-futures-availability
```

**Development installation:**

```bash
git clone https://github.com/terrylica/binance-futures-availability.git
cd binance-futures-availability
pip install -e ".[dev]"
```

## Requirements

- Python ≥3.12
- DuckDB ≥1.4.0
- urllib3 ≥2.5.0
- pyarrow ≥22.0.0 (for Parquet support)

## Usage

### Query Available Symbols

```python
from binance_futures_availability.queries import SnapshotQueries

with SnapshotQueries() as q:
    symbols = q.get_available_symbols_on_date('2024-01-15')
    print(f"Available: {len(symbols)} symbols")
```

### Query Symbol Timeline

```python
from binance_futures_availability.queries import TimelineQueries

with TimelineQueries() as q:
    timeline = q.get_symbol_availability_timeline('BTCUSDT')
    print(f"First available: {timeline[0]['date']}")
```

### CLI Interface

```bash
binance-futures-availability query snapshot 2024-01-15
binance-futures-availability query timeline BTCUSDT
binance-futures-availability query range 2024-01-01 2024-03-31
```

## Data Source

**Source**: [Binance Vision S3](https://data.binance.vision/data/futures/um/daily/klines/)

**Coverage**: From UM-futures inception to present (daily granularity)

**Collection Methods**:

| Method | Use Case | Implementation |
|--------|----------|----------------|
| AWS CLI S3 listing | Historical backfill | Bulk enumeration |
| HTTP HEAD requests | Daily incremental | Parallel probing |

## Database Schema

**Table**: `daily_availability`

| Column | Type | Description |
|--------|------|-------------|
| date | DATE | Trading date |
| symbol | VARCHAR | Futures symbol (e.g., BTCUSDT) |
| available | BOOLEAN | Data availability flag |
| file_size_bytes | BIGINT | ZIP file size from S3 |
| last_modified | TIMESTAMP | S3 upload timestamp |

**Primary Key**: (date, symbol)

**Indexes**: `idx_symbol_date`, `idx_available_date`

**Storage Path**: `~/.cache/binance-futures/availability.duckdb`

## Volume Rankings Archive

Parquet file with daily symbol rankings by trading volume.

**Asset**: `volume-rankings-timeseries.parquet` (published to GitHub Releases)

```python
import duckdb

url = "https://github.com/terrylica/binance-futures-availability/releases/download/latest/volume-rankings-timeseries.parquet"

result = duckdb.execute(f"""
    SELECT symbol, rank, quote_volume_usdt
    FROM '{url}'
    WHERE date = (SELECT MAX(date) FROM '{url}')
    ORDER BY rank LIMIT 10
""").fetchdf()
```

**Schema**: See [ADR-0013](https://github.com/terrylica/binance-futures-availability/blob/main/docs/architecture/decisions/0013-volume-rankings-timeseries.md)

## GitHub Releases Distribution

Pre-built database available from GitHub Releases:

```bash
gh release download latest --pattern "availability.duckdb.gz"
gunzip availability.duckdb.gz
```

**Automation**: Daily updates via GitHub Actions (see [ADR-0009](https://github.com/terrylica/binance-futures-availability/blob/main/docs/architecture/decisions/0009-github-actions-automation.md))

## Architecture Decisions

| ADR | Decision |
|-----|----------|
| [0001](https://github.com/terrylica/binance-futures-availability/blob/main/docs/architecture/decisions/0001-schema-design-daily-table.md) | Daily table pattern |
| [0002](https://github.com/terrylica/binance-futures-availability/blob/main/docs/architecture/decisions/0002-storage-technology-duckdb.md) | DuckDB storage |
| [0003](https://github.com/terrylica/binance-futures-availability/blob/main/docs/architecture/decisions/0003-error-handling-strict-policy.md) | Strict error handling |
| [0005](https://github.com/terrylica/binance-futures-availability/blob/main/docs/architecture/decisions/0005-aws-cli-bulk-operations.md) | AWS CLI bulk operations |
| [0009](https://github.com/terrylica/binance-futures-availability/blob/main/docs/architecture/decisions/0009-github-actions-automation.md) | GitHub Actions automation |
| [0010](https://github.com/terrylica/binance-futures-availability/blob/main/docs/architecture/decisions/0010-dynamic-symbol-discovery.md) | Dynamic symbol discovery |
| [0013](https://github.com/terrylica/binance-futures-availability/blob/main/docs/architecture/decisions/0013-volume-rankings-timeseries.md) | Volume rankings archive |

## Documentation

- [Architecture Overview](https://github.com/terrylica/binance-futures-availability/blob/main/docs/architecture/ARCHITECTURE.md)
- [Quick Start Guide](https://github.com/terrylica/binance-futures-availability/blob/main/docs/guides/QUICKSTART.md)
- [Query Examples](https://github.com/terrylica/binance-futures-availability/blob/main/docs/guides/QUERY_EXAMPLES.md)
- [Troubleshooting](https://github.com/terrylica/binance-futures-availability/blob/main/docs/guides/TROUBLESHOOTING.md)
- [GitHub Actions Operations](https://github.com/terrylica/binance-futures-availability/blob/main/docs/operations/GITHUB_ACTIONS.md)
- [Database Schema (JSON)](https://github.com/terrylica/binance-futures-availability/blob/main/docs/schema/availability-database.schema.json)

## Development

```bash
# Run tests
pytest -m "not integration"

# Run with coverage
pytest --cov --cov-fail-under=80

# Lint and format
ruff check src/ tests/
ruff format src/ tests/
```

## License

[MIT](https://github.com/terrylica/binance-futures-availability/blob/main/LICENSE)

## Related

- [gapless-crypto-data](https://github.com/terrylica/gapless-crypto-data) - Spot OHLCV collection
