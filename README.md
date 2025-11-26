# binance-futures-availability

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
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

## Usage

### Python API

```python
from binance_futures_availability.queries import SnapshotQueries, TimelineQueries

# Query symbols available on a specific date
with SnapshotQueries() as q:
    symbols = q.get_available_symbols_on_date('<DATE>')

# Query availability timeline for a symbol
with TimelineQueries() as q:
    timeline = q.get_symbol_availability_timeline('<SYMBOL>')
```

### CLI

```bash
binance-futures-availability query snapshot <DATE>
binance-futures-availability query timeline <SYMBOL>
binance-futures-availability query range <START_DATE> <END_DATE>
```

## Data Source

**Source**: [Binance Vision S3](https://data.binance.vision/data/futures/um/daily/klines/)

**Coverage**: UM-futures inception to present (daily granularity)

## Database Schema

**Table**: `daily_availability`

| Column | Type | Description |
| ------ | ---- | ----------- |
| date | DATE | Trading date |
| symbol | VARCHAR | Futures symbol |
| available | BOOLEAN | Data availability flag |
| file_size_bytes | BIGINT | ZIP file size from S3 |
| last_modified | TIMESTAMP | S3 upload timestamp |
| quote_volume_usdt | DOUBLE | Daily USDT trading volume |
| trade_count | BIGINT | Number of trades |
| open/high/low/close_price | DOUBLE | OHLC prices |

**Primary Key**: (date, symbol)

Full schema: [availability-database.schema.json](https://github.com/terrylica/binance-futures-availability/blob/main/docs/schema/availability-database.schema.json)

## GitHub Releases

Pre-built database and volume rankings published to GitHub Releases:

```bash
gh release download latest --pattern "availability.duckdb.gz"
gh release download latest --pattern "volume-rankings-timeseries.parquet"
```

## Architecture Decisions

| ADR | Decision |
| --- | -------- |
| [0001](https://github.com/terrylica/binance-futures-availability/blob/main/docs/architecture/decisions/0001-schema-design-daily-table.md) | Daily table pattern |
| [0002](https://github.com/terrylica/binance-futures-availability/blob/main/docs/architecture/decisions/0002-storage-technology-duckdb.md) | DuckDB storage |
| [0003](https://github.com/terrylica/binance-futures-availability/blob/main/docs/architecture/decisions/0003-error-handling-strict-policy.md) | Strict error handling |
| [0005](https://github.com/terrylica/binance-futures-availability/blob/main/docs/architecture/decisions/0005-aws-cli-bulk-operations.md) | AWS CLI bulk operations |
| [0007](https://github.com/terrylica/binance-futures-availability/blob/main/docs/architecture/decisions/0007-trading-volume-metrics.md) | Volume metrics collection |
| [0009](https://github.com/terrylica/binance-futures-availability/blob/main/docs/architecture/decisions/0009-github-actions-automation.md) | GitHub Actions automation |
| [0010](https://github.com/terrylica/binance-futures-availability/blob/main/docs/architecture/decisions/0010-dynamic-symbol-discovery.md) | Dynamic symbol discovery |
| [0013](https://github.com/terrylica/binance-futures-availability/blob/main/docs/architecture/decisions/0013-volume-rankings-timeseries.md) | Volume rankings archive |

## Documentation

- [Architecture Overview](https://github.com/terrylica/binance-futures-availability/blob/main/docs/architecture/ARCHITECTURE.md)
- [Quick Start Guide](https://github.com/terrylica/binance-futures-availability/blob/main/docs/guides/QUICKSTART.md)
- [Query Examples](https://github.com/terrylica/binance-futures-availability/blob/main/docs/guides/QUERY_EXAMPLES.md)
- [Troubleshooting](https://github.com/terrylica/binance-futures-availability/blob/main/docs/guides/TROUBLESHOOTING.md)

## Development

```bash
pytest -m "not integration"
pytest --cov --cov-fail-under=80
ruff check src/ tests/
```

## License

[MIT](https://github.com/terrylica/binance-futures-availability/blob/main/LICENSE)
