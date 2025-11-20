# Using Volume Rankings Archive

**ADR**: [0013-volume-rankings-timeseries](../architecture/decisions/0013-volume-rankings-timeseries.md)
**Format**: Parquet (columnar, SNAPPY compressed)
**Update Frequency**: Daily at 3:00 AM UTC
**Retention**: Complete historical archive (2019-09-25 to present)

## Quick Start

Get top 10 symbols by volume in 30 seconds:

```python
# Install DuckDB (one-time)
# pip install duckdb

import duckdb

# Query directly from GitHub Releases (zero download, zero local storage)
url = "https://github.com/terryli/binance-futures-availability/releases/download/latest/volume-rankings-timeseries.parquet"

result = duckdb.execute(f"""
    SELECT symbol, rank, quote_volume_usdt, rank_change_7d
    FROM '{url}'
    WHERE date = '2025-11-16'  -- Replace with desired date
    ORDER BY rank
    LIMIT 10
""").fetchdf()

print(result)
```

**Output Example**:

```
    symbol  rank  quote_volume_usdt  rank_change_7d
0   BTCUSDT     1     45123456789.12            None
1   ETHUSDT     2     23456789012.34              -1
2   SOLUSDT     3      5678901234.56               2
...
```

**Latest Data**: Updated daily at 3:00 AM UTC (includes up to yesterday's rankings)

**Performance**: Remote queries complete in 1-3 seconds (DuckDB uses HTTP range requests, downloads only needed data)

## Prerequisites

**Python**: 3.12 or higher

**Required Library**:

```bash
pip install duckdb>=1.0.0
# or with uv
uv pip install duckdb>=1.0.0
```

**Optional Libraries** (for alternative tools):

```bash
pip install polars>=1.0.0  # Fast dataframe operations
pip install pandas>=2.0.0 pyarrow>=18.0.0  # Traditional data analysis
```

## Overview

The volume rankings archive is a single cumulative Parquet file containing daily rankings of all Binance USDT perpetual futures symbols, ordered by 24-hour trading volume (quote_volume_usdt). Each row represents one symbol's ranking for one date, with rank change tracking across 1-day, 7-day, 14-day, and 30-day windows.

**Use Cases**:

- Portfolio universe selection (top N by volume)
- Trend analysis (rank changes over time)
- Survivorship bias elimination (historical rankings include delisted symbols)
- Market share analysis (percentage of total volume)
- Symbol discovery (newly listed symbols appear in rankings)

## Download

**Option 1: Remote Query (Recommended)** - No download required, query directly from GitHub:

```python
import duckdb

url = "https://github.com/terryli/binance-futures-availability/releases/download/latest/volume-rankings-timeseries.parquet"
result = duckdb.execute(f"SELECT * FROM '{url}' LIMIT 10").fetchdf()
```

**Option 2: Local Download** - For offline use or repeated queries:

```bash
wget https://github.com/terryli/binance-futures-availability/releases/download/latest/volume-rankings-timeseries.parquet
```

**File Size**: ~20 MB (733,000 rows for 2,242 dates × 327 symbols)
**Growth**: +50 KB daily (~327 new rows)

## Schema

**13 Columns** (date, symbol) grain:

| Column                 | Type          | Description                | Example             |
| ---------------------- | ------------- | -------------------------- | ------------------- |
| `date`                 | date32        | Trading date (UTC)         | 2024-01-15          |
| `symbol`               | string        | Perpetual futures symbol   | BTCUSDT             |
| `rank`                 | uint16        | Volume rank (1=highest)    | 1                   |
| `quote_volume_usdt`    | float64       | 24h trading volume (USDT)  | 45123456789.12      |
| `trade_count`          | uint64        | Number of trades           | 8245123             |
| `rank_change_1d`       | int16         | Rank delta vs 1 day ago    | -2                  |
| `rank_change_7d`       | int16         | Rank delta vs 7 days ago   | 5                   |
| `rank_change_14d`      | int16         | Rank delta vs 14 days ago  | -1                  |
| `rank_change_30d`      | int16         | Rank delta vs 30 days ago  | 12                  |
| `percentile`           | float32       | Volume percentile (0-100)  | 0.5                 |
| `market_share_pct`     | float32       | % of total market volume   | 15.3                |
| `days_available`       | uint8         | Days available in last 30d | 30                  |
| `generation_timestamp` | timestamp[us] | File generation time       | 2024-01-16T03:15:22 |

**Ranking Algorithm**: DENSE_RANK() (no gaps when ties exist)
**Tie-Breaking**: Alphabetical by symbol (display only, tied symbols get same rank)
**Rank Changes**: Negative = rank improved (moved up), Positive = rank declined (moved down), NULL = insufficient history

## Query Examples

### DuckDB (Recommended)

**Top 10 Symbols by Volume (Latest Date)**:

```python
import duckdb

conn = duckdb.connect()
result = conn.execute("""
    SELECT date, symbol, rank, quote_volume_usdt, rank_change_1d
    FROM read_parquet('volume-rankings-timeseries.parquet')
    WHERE date = (SELECT MAX(date) FROM read_parquet('volume-rankings-timeseries.parquet'))
    ORDER BY rank
    LIMIT 10
""").fetchall()

for row in result:
    print(f"{row[0]} | {row[1]:10s} | Rank {row[2]:3d} | Volume ${row[3]:,.0f}")
```

**Symbol Rank Timeline (Last 30 Days)**:

```python
symbol = 'BTCUSDT'
result = conn.execute("""
    SELECT date, rank, quote_volume_usdt, rank_change_1d
    FROM read_parquet('volume-rankings-timeseries.parquet')
    WHERE symbol = ?
      AND date >= CURRENT_DATE - INTERVAL '30 days'
    ORDER BY date DESC
""", [symbol]).fetchdf()

print(result)
```

**Biggest Rank Movers (7-Day Window)**:

```python
result = conn.execute("""
    SELECT date, symbol, rank, rank_change_7d, quote_volume_usdt
    FROM read_parquet('volume-rankings-timeseries.parquet')
    WHERE date = (SELECT MAX(date) FROM read_parquet('volume-rankings-timeseries.parquet'))
      AND rank_change_7d IS NOT NULL
    ORDER BY rank_change_7d ASC  -- Most improved ranks (negative values)
    LIMIT 10
""").fetchall()

print("Top 10 Rank Climbers (7-day):")
for row in result:
    print(f"{row[1]:10s} | Rank {row[2]:3d} | Change: {row[3]:+3d}")
```

**Market Share Analysis (Top 20)**:

```python
result = conn.execute("""
    SELECT symbol, rank, market_share_pct, quote_volume_usdt
    FROM read_parquet('volume-rankings-timeseries.parquet')
    WHERE date = (SELECT MAX(date) FROM read_parquet('volume-rankings-timeseries.parquet'))
      AND rank <= 20
    ORDER BY rank
""").fetchdf()

print(f"Top 20 symbols control {result['market_share_pct'].sum():.1f}% of market volume")
```

**Newly Listed Symbols (Appeared in Last 30 Days)**:

```python
result = conn.execute("""
    WITH first_appearances AS (
        SELECT symbol, MIN(date) as first_date
        FROM read_parquet('volume-rankings-timeseries.parquet')
        GROUP BY symbol
    )
    SELECT symbol, first_date, CURRENT_DATE - first_date as days_since_listing
    FROM first_appearances
    WHERE first_date >= CURRENT_DATE - INTERVAL '30 days'
    ORDER BY first_date DESC
""").fetchall()
```

### Remote Queries (No Download Required)

DuckDB can query Parquet files directly from GitHub Releases via HTTPS, using HTTP range requests to download only needed data.

**Advantages**:

- ✅ Zero local storage (no file download)
- ✅ Always latest data (no stale local copies)
- ✅ Efficient (DuckDB downloads only needed row groups/columns)
- ✅ Fast (column/row pruning, 1-3 second queries)

**Trade-offs**:

- ⚠️ Requires internet connection
- ⚠️ Slightly slower than local file for full table scans
- ⚠️ GitHub rate limits apply (5,000 requests/hour authenticated)

**Basic Remote Query**:

```python
import duckdb

url = "https://github.com/terryli/binance-futures-availability/releases/download/latest/volume-rankings-timeseries.parquet"

# Top 10 symbols (latest date)
result = duckdb.execute(f"""
    SELECT symbol, rank, quote_volume_usdt, rank_change_7d
    FROM '{url}'
    WHERE date = (SELECT MAX(date) FROM '{url}')
    ORDER BY rank
    LIMIT 10
""").fetchdf()

print(result)
```

**Filtered Query (Efficient - Only Downloads Needed Data)**:

```python
# Specific date query (fast, minimal data transfer)
result = duckdb.execute(f"""
    SELECT symbol, rank, quote_volume_usdt
    FROM '{url}'
    WHERE date = '2025-11-16'
      AND rank <= 20
    ORDER BY rank
""").fetchdf()
```

**Symbol Timeline (Remote)**:

```python
# 30-day rank history for BTCUSDT
symbol = 'BTCUSDT'
result = duckdb.execute(f"""
    SELECT date, rank, quote_volume_usdt, rank_change_1d
    FROM '{url}'
    WHERE symbol = '{symbol}'
      AND date >= CURRENT_DATE - INTERVAL '30 days'
    ORDER BY date DESC
""").fetchdf()
```

**Performance Tips**:

- Use `WHERE` filters to minimize data transfer (DuckDB pushes predicates down)
- Select specific columns instead of `SELECT *` (column pruning)
- Cache frequently accessed date ranges locally if needed

**When to Download Locally Instead**:

- Offline analysis required
- Repeated full table scans
- Network unreliable or slow
- Query latency critical (<100ms)

### Polars

**Load and Filter**:

```python
import polars as pl

df = pl.read_parquet('volume-rankings-timeseries.parquet')

# Top 50 symbols on latest date
latest_date = df['date'].max()
top_50 = df.filter(
    (pl.col('date') == latest_date) & (pl.col('rank') <= 50)
).sort('rank')

print(top_50.select(['symbol', 'rank', 'quote_volume_usdt', 'rank_change_7d']))
```

**Rank Volatility (Standard Deviation)**:

```python
# Symbols with most volatile rankings (last 30 days)
volatility = df.filter(
    pl.col('date') >= (pl.col('date').max() - pl.duration(days=30))
).groupby('symbol').agg([
    pl.col('rank').std().alias('rank_std'),
    pl.col('rank').mean().alias('rank_mean'),
    pl.col('rank').count().alias('days_ranked')
]).filter(
    pl.col('days_ranked') >= 20  # At least 20 days of data
).sort('rank_std', descending=True)

print(volatility.head(10))
```

### Pandas

**Load Entire Dataset**:

```python
import pandas as pd

df = pd.read_parquet('volume-rankings-timeseries.parquet')

# Basic stats
print(f"Date range: {df['date'].min()} to {df['date'].max()}")
print(f"Total symbols: {df['symbol'].nunique()}")
print(f"Total rows: {len(df):,}")
```

**Portfolio Selection (Top 30 by Average Rank)**:

```python
# Select symbols consistently in top 30 (last 90 days)
recent = df[df['date'] >= (df['date'].max() - pd.Timedelta(days=90))]

portfolio = recent.groupby('symbol').agg({
    'rank': ['mean', 'min', 'max'],
    'quote_volume_usdt': 'mean',
    'days_available': 'sum'
}).reset_index()

portfolio.columns = ['symbol', 'avg_rank', 'best_rank', 'worst_rank', 'avg_volume', 'days_available']
portfolio = portfolio[
    (portfolio['avg_rank'] <= 30) & (portfolio['days_available'] >= 80)
].sort_values('avg_rank')

print(portfolio.head(30))
```

### QuestDB Import

**Create Table**:

```sql
CREATE TABLE volume_rankings (
    date TIMESTAMP,
    symbol SYMBOL,
    rank INT,
    quote_volume_usdt DOUBLE,
    trade_count LONG,
    rank_change_1d INT,
    rank_change_7d INT,
    rank_change_14d INT,
    rank_change_30d INT,
    percentile FLOAT,
    market_share_pct FLOAT,
    days_available INT,
    generation_timestamp TIMESTAMP
) TIMESTAMP(date) PARTITION BY DAY;
```

**Import from Parquet** (via DuckDB):

```python
import duckdb

# Convert Parquet to CSV for QuestDB import
conn = duckdb.connect()
conn.execute("""
    COPY (
        SELECT * FROM read_parquet('volume-rankings-timeseries.parquet')
    ) TO 'volume-rankings.csv' (HEADER, DELIMITER ',')
""")
```

Then import CSV via QuestDB web console or REST API.

## Common Queries

### Top N by Volume

**Top 10 on specific date**:

```sql
SELECT symbol, rank, quote_volume_usdt, market_share_pct
FROM read_parquet('volume-rankings-timeseries.parquet')
WHERE date = '2024-01-15'
ORDER BY rank
LIMIT 10
```

### Rank Change Analysis

**Symbols that improved rank >10 positions in 7 days**:

```sql
SELECT symbol, rank, rank_change_7d, quote_volume_usdt
FROM read_parquet('volume-rankings-timeseries.parquet')
WHERE date = (SELECT MAX(date) FROM read_parquet('volume-rankings-timeseries.parquet'))
  AND rank_change_7d < -10  -- Negative = improvement
ORDER BY rank_change_7d
```

### Time-Series Queries

**Symbol ranking over time**:

```sql
SELECT date, rank, quote_volume_usdt, rank_change_1d
FROM read_parquet('volume-rankings-timeseries.parquet')
WHERE symbol = 'ETHUSDT'
  AND date BETWEEN '2024-01-01' AND '2024-01-31'
ORDER BY date
```

### Market Concentration

**Volume concentration in top 10 vs top 50**:

```sql
WITH daily_totals AS (
    SELECT
        date,
        SUM(CASE WHEN rank <= 10 THEN quote_volume_usdt ELSE 0 END) as top10_volume,
        SUM(CASE WHEN rank <= 50 THEN quote_volume_usdt ELSE 0 END) as top50_volume,
        SUM(quote_volume_usdt) as total_volume
    FROM read_parquet('volume-rankings-timeseries.parquet')
    WHERE date >= CURRENT_DATE - INTERVAL '30 days'
    GROUP BY date
)
SELECT
    date,
    (top10_volume / total_volume * 100) as top10_share_pct,
    (top50_volume / total_volume * 100) as top50_share_pct
FROM daily_totals
ORDER BY date DESC
```

## Performance Tips

**Query Performance**:

- Filter by `date` first (Parquet column pruning)
- Use `rank` filters for top-N queries (indexed in Parquet)
- Avoid full table scans when possible

**Memory Usage**:

- Full file load: ~150 MB RAM (uncompressed)
- Filtered queries: ~10-50 MB (DuckDB zero-copy)

**Storage**:

- Parquet compression: 4.4x smaller than CSV (20 MB vs 85 MB)
- Columnar format: fast column-oriented queries

## Updating

**Automated**:

- GitHub Actions updates daily at 3:00 AM UTC
- New rows appended automatically (incremental)
- Published to GitHub Releases "latest" tag

**Manual Regeneration** (if needed):

```bash
# Download database
wget https://github.com/YOUR_USERNAME/binance-futures-availability/releases/download/latest/availability.duckdb.gz
gunzip availability.duckdb.gz

# Generate rankings
uv run python .github/scripts/generate_volume_rankings.py \
    --db-path availability.duckdb \
    --output volume-rankings-timeseries.parquet
```

## Validation

**Check Latest Date**:

```python
import duckdb
conn = duckdb.connect()
result = conn.execute("""
    SELECT MAX(date) as latest_date, COUNT(*) as total_rows
    FROM read_parquet('volume-rankings-timeseries.parquet')
""").fetchone()

print(f"Latest date: {result[0]}, Total rows: {result[1]:,}")
```

**Verify Rank Continuity** (no gaps):

```python
# Check ranks are consecutive (DENSE_RANK property)
result = conn.execute("""
    WITH rank_gaps AS (
        SELECT date, rank, LAG(rank) OVER (PARTITION BY date ORDER BY rank) as prev_rank
        FROM read_parquet('volume-rankings-timeseries.parquet')
    )
    SELECT COUNT(*) as gaps
    FROM rank_gaps
    WHERE rank - prev_rank > 1 AND prev_rank IS NOT NULL
""").fetchone()

print(f"Rank gaps found: {result[0]}")  # Should be 0
```

**Cross-Check with Database**:

```python
import duckdb

db_conn = duckdb.connect('availability.duckdb', read_only=True)
parquet_conn = duckdb.connect()

# Compare rankings (should match 100%)
latest_date = parquet_conn.execute("""
    SELECT MAX(date) FROM read_parquet('volume-rankings-timeseries.parquet')
""").fetchone()[0]

db_ranks = db_conn.execute("""
    SELECT symbol, DENSE_RANK() OVER (ORDER BY quote_volume_usdt DESC) as rank
    FROM daily_availability
    WHERE date = ? AND available = TRUE AND quote_volume_usdt IS NOT NULL
    ORDER BY rank
""", [latest_date]).fetchdf()

parquet_ranks = parquet_conn.execute("""
    SELECT symbol, rank
    FROM read_parquet('volume-rankings-timeseries.parquet')
    WHERE date = ?
    ORDER BY rank
""", [latest_date]).fetchdf()

if db_ranks.equals(parquet_ranks):
    print("✅ Rankings match database")
else:
    print("❌ Rankings mismatch - investigate!")
```

## Troubleshooting

**File Not Found**:

- Check GitHub Releases "latest" tag
- Verify download URL (replace YOUR_USERNAME with actual repo owner)
- Ensure workflow has run at least once

**Schema Mismatch**:

- Re-download file (may be cached old version)
- Check Parquet version compatibility (requires 2.6+)
- Verify pyarrow>=18.0.0 installed

**Unexpected Ranks**:

- Verify ranking metric: quote_volume_usdt (not file_size_bytes)
- Check date filter (rankings are per-date)
- Confirm DENSE_RANK algorithm (ties get same rank, no gaps)

**Missing Rank Changes**:

- NULL values expected for insufficient history (<1/7/14/30 days)
- New symbols have NULL rank*change*\* until history accumulates
- Delisted symbols frozen at last available rank

## Related

- **ADR**: [0013-volume-rankings-timeseries](../architecture/decisions/0013-volume-rankings-timeseries.md) - Design rationale
- **Plan**: [0013-volume-rankings/plan.yaml](../development/plan/0013-volume-rankings/plan.yaml) - Implementation plan
- **Database Guide**: [QUERY_EXAMPLES.md](QUERY_EXAMPLES.md) - Availability database queries
- **Schema**: [availability-database.schema.json](../schema/availability-database.schema.json) - Source data schema
