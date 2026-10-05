# Volume Metrics Collection

**Version**: v1.1.0
**ADR**: [0007-trading-volume-metrics](../architecture/decisions/0007-trading-volume-metrics.md)
**Status**: Implemented

## Overview

The database now tracks 9 trading volume metrics from Binance Vision 1d kline files, enabling volume-based ranking and market activity analysis.

## Features

### Volume Metrics Collected

From 1d kline files (`s3://data.binance.vision/.../1d/`):

- **quote_volume_usdt**: Total daily volume in USDT (primary ranking metric)
- **trade_count**: Number of trades
- **volume_base**: Total volume in base currency
- **taker_buy_volume_base**: Taker buy volume (base)
- **taker_buy_quote_volume_usdt**: Taker buy volume (USDT)

### Price Metrics (OHLC)

- **open_price**, **high_price**, **low_price**, **close_price**

## Usage Examples

### Top Symbols by Volume

```python
from binance_futures_availability.queries import VolumeQueries
from datetime import date

vq = VolumeQueries()

# Get top 10 by volume for specific date
top10 = vq.get_top_by_volume(date(2024, 1, 15), limit=10)

for rank, symbol_data in enumerate(top10, 1):
    print(f"{rank}. {symbol_data['symbol']}: "
          f"${symbol_data['quote_volume_usdt']:,.0f} "
          f"({symbol_data['market_share_pct']}% market share)")
```

### Volume Percentile Ranking

```python
# Check where BTCUSDT ranks
pct = vq.get_volume_percentile('BTCUSDT', date(2024, 1, 15))
print(f"BTCUSDT is in top {100 - pct['percentile']:.1f}% by volume")
# Output: BTCUSDT is in top 0.4% by volume
```

### Average Volume Over Time

```python
# Get 30-day average volume
avg = vq.get_average_volume('ETHUSDT',
                             date(2024, 1, 1),
                             date(2024, 1, 31))
print(f"Avg daily volume: ${avg['avg_volume_usdt']:,.0f}")
print(f"Avg daily trades: {avg['avg_trade_count']:,}")
```

### Market Summary

```python
# Overall market stats for a date
summary = vq.get_market_summary(date(2024, 1, 15))
print(f"Total market volume: ${summary['total_volume_usdt']:,.0f}")
print(f"Active symbols: {summary['symbol_count']}")
```

## Database Schema

Extended `daily_availability` table with 9 new columns (all nullable for backward compatibility):

```sql
ALTER TABLE daily_availability ADD COLUMN quote_volume_usdt DOUBLE;
ALTER TABLE daily_availability ADD COLUMN trade_count BIGINT;
-- ... 7 more columns
```

## Data Collection

### Daily Collection

The daily update fills volume for every available row in its 20-day lookback window that lacks it (`probing/volume_fetcher.py`: one ~350-byte 1d-kline GET per row over the shared HTTP pool). A 1d file not yet published is retried by the next run; a re-probe never wipes collected volume (`COALESCE` on conflict).

### Backfill Historical Data

```bash
uv run python scripts/operations/backfill_volume.py --start-date 2025-11-01
uv run python scripts/operations/backfill_volume.py --start-date 2024-01-01 --end-date 2024-01-31
```

In CI, a one-time catch-up runs by dispatching the workflow with `volume_start_date`.

## Query Performance

Columnar scan with date zone-map pruning (no index on volume columns, which broke upserts on DuckDB 1.4.x):

- **Top 100 by volume**: <10ms
- **Volume ranking**: <5ms
- **Market summary**: <15ms

## Validation

```python
from binance_futures_availability.database import AvailabilityDatabase

db = AvailabilityDatabase()

# Check volume data coverage
result = db.query("""
    SELECT COUNT(*)
    FROM daily_availability
    WHERE quote_volume_usdt IS NOT NULL
""")
print(f"Rows with volume data: {result[0][0]:,}")

# Sample validation (BTCUSDT 2024-01-15)
result = db.query("""
    SELECT quote_volume_usdt, trade_count
    FROM daily_availability
    WHERE symbol = 'BTCUSDT' AND date = '2024-01-15'
""")
# Expected: ~$10.24B volume, ~3.39M trades
```

## References

- **ADR**: [docs/architecture/decisions/0007-trading-volume-metrics.md](../architecture/decisions/0007-trading-volume-metrics.md)
- **Plan**: [docs/development/plan/0007-trading-volume-metrics/plan.yaml](https://github.com/terrylica/binance-futures-availability/blob/v1.4.0/docs/development/plan/0007-trading-volume-metrics/plan.yaml) (v1.4.0)
- **API Docs**: [VolumeQueries](../../src/binance_futures_availability/queries/volume.py)
