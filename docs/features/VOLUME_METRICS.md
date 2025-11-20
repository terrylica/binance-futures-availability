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

CREATE INDEX idx_quote_volume_date
    ON daily_availability(quote_volume_usdt DESC, date);
```

## Data Collection

### Backfill Historical Data

```bash
# Backfill all dates with missing volume data
uv run python scripts/operations/backfill_volume.py

# Specific date range
uv run python scripts/operations/backfill_volume.py \
    --start-date 2024-01-01 --end-date 2024-01-31

# Specific symbols only
uv run python scripts/operations/backfill_volume.py \
    --symbols BTCUSDT ETHUSDT
```

### Performance

- **File size**: 350 bytes per 1d kline (vs 57 KB for 1m klines)
- **Collection rate**: ~10 records/second
- **Historical coverage**: Same as availability (2019-09-25 to present)

## Query Performance

With `idx_quote_volume_date` index:

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
- **Plan**: [docs/development/plan/0007-trading-volume-metrics/plan.yaml](../development/plan/0007-trading-volume-metrics/plan.yaml)
- **API Docs**: [VolumeQueries](../../src/binance_futures_availability/queries/volume.py)
