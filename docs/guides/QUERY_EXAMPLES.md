# Query Examples

Common query patterns for the Binance Futures Availability database.

See also: [Query Patterns Schema](../schema/query-patterns.schema.json)

## Snapshot Queries

### Get All Available Symbols on Specific Date

**Use case**: "Which symbols were available on 2024-01-15?"

**Performance**: <1ms (idx_available_date index)

**CLI**:

```bash
uv run binance-futures-availability query snapshot 2024-01-15 --json > snapshot.json
```

**Python**:

```python
from binance_futures_availability.queries import SnapshotQueries

with SnapshotQueries() as q:
    results = q.get_available_symbols_on_date('2024-01-15')

    print(f"Available symbols: {len(results)}")

    for r in results[:5]:
        print(f"  {r['symbol']}: {r['file_size_bytes']:,} bytes")
```

**Output**:

```
Available symbols: 708
  BTCUSDT: 8,421,945 bytes
  ETHUSDT: 5,123,456 bytes
  ...
```

### Get Symbols in Date Range

**Use case**: "Which symbols were available at any point in Q1 2024?"

**Performance**: <100ms (90 days × 708 symbols)

**Python**:

```python
from binance_futures_availability.queries import SnapshotQueries

with SnapshotQueries() as q:
    symbols = q.get_symbols_in_date_range('2024-01-01', '2024-03-31')

    print(f"Symbols available in Q1 2024: {len(symbols)}")
    print(symbols[:10])
```

## Timeline Queries

### Get Complete Availability Timeline for Symbol

**Use case**: "When was BTCUSDT available?"

**Performance**: <10ms (idx_symbol_date index, ~2240 rows)

**CLI**:

```bash
uv run binance-futures-availability query timeline BTCUSDT --json > btcusdt_timeline.json
```

**Python**:

```python
from binance_futures_availability.queries import TimelineQueries

with TimelineQueries() as q:
    timeline = q.get_symbol_availability_timeline('BTCUSDT')

    print(f"Total days: {len(timeline)}")
    print(f"First available: {timeline[0]['date']}")
    print(f"Last available: {timeline[-1]['date']}")

    # Count available days
    available_days = sum(1 for day in timeline if day['available'])
    print(f"Available days: {available_days}/{len(timeline)}")
```

### Get First and Last Listing Dates

**Use case**: "When was SOLUSDT first listed? Is it still listed?"

**Python**:

```python
from binance_futures_availability.queries import TimelineQueries

with TimelineQueries() as q:
    first = q.get_symbol_first_listing_date('SOLUSDT')
    last = q.get_symbol_last_available_date('SOLUSDT')

    print(f"SOLUSDT first listed: {first}")
    print(f"SOLUSDT last available: {last}")

    from datetime import date, timedelta
    yesterday = date.today() - timedelta(days=1)

    if last == yesterday:
        print("Status: Still listed")
    else:
        print(f"Status: Delisted on {last}")
```

## Analytics Queries

### Detect New Listings

**Use case**: "Which symbols were newly listed on 2024-01-15?"

**Performance**: <50ms (NOT IN subquery)

**CLI**:

```bash
uv run binance-futures-availability query analytics new-listings 2024-01-15
```

**Python**:

```python
from binance_futures_availability.queries import AnalyticsQueries

with AnalyticsQueries() as q:
    new_symbols = q.detect_new_listings('2024-01-15')

    print(f"New listings on 2024-01-15: {len(new_symbols)}")
    for symbol in new_symbols:
        print(f"  - {symbol}")
```

### Detect Delistings

**Use case**: "Which symbols were delisted on 2024-01-15?"

**Performance**: <50ms

**CLI**:

```bash
uv run binance-futures-availability query analytics delistings 2024-01-15
```

**Python**:

```python
from binance_futures_availability.queries import AnalyticsQueries

with AnalyticsQueries() as q:
    delisted = q.detect_delistings('2024-01-15')

    print(f"Delistings on 2024-01-15: {len(delisted)}")
    for symbol in delisted:
        print(f"  - {symbol}")
```

### Get Availability Summary (Growth Over Time)

**Use case**: "How has the number of available symbols grown over time?"

**Performance**: <50ms (aggregates ~2240 days)

**CLI**:

```bash
uv run binance-futures-availability query analytics summary --json > summary.json
```

**Python**:

```python
from binance_futures_availability.queries import AnalyticsQueries

with AnalyticsQueries() as q:
    summary = q.get_availability_summary()

    print(f"First day: {summary[0]['date']} - {summary[0]['available_count']} symbols")
    print(f"Last day: {summary[-1]['date']} - {summary[-1]['available_count']} symbols")

    # Plot growth (requires matplotlib)
    import matplotlib.pyplot as plt

    dates = [s['date'] for s in summary]
    counts = [s['available_count'] for s in summary]

    plt.plot(dates[::30], counts[::30])  # Plot every 30th day
    plt.xlabel('Date')
    plt.ylabel('Available Symbols')
    plt.title('Binance Futures Availability Growth')
    plt.savefig('availability_growth.png')
```

### Get Recent Symbol Counts

**Use case**: "What are the symbol counts for the last 7 days?"

**Python**:

```python
from binance_futures_availability.validation import CompletenessValidator

with CompletenessValidator() as v:
    summary = v.get_symbol_counts_summary(days=7)

    for item in summary:
        print(f"{item['date']}: {item['symbol_count']} symbols")
```

## Direct SQL Queries

For advanced use cases, use `AvailabilityDatabase.query()` directly:

```python
from binance_futures_availability.database import AvailabilityDatabase

with AvailabilityDatabase() as db:
    # Custom aggregation: Average file size by symbol
    result = db.query("""
        SELECT
            symbol,
            AVG(file_size_bytes) as avg_size_bytes,
            COUNT(*) as days_available
        FROM daily_availability
        WHERE available = true
        GROUP BY symbol
        ORDER BY avg_size_bytes DESC
        LIMIT 10
    """)

    print("Top 10 symbols by average file size:")
    for row in result:
        symbol, avg_size, days = row
        print(f"  {symbol}: {avg_size:,.0f} bytes ({days} days)")
```

## Export to CSV/Parquet

Export query results for analysis in other tools:

```python
from binance_futures_availability.database import AvailabilityDatabase

db = AvailabilityDatabase()

# Export to CSV
db.conn.execute("""
    COPY (
        SELECT * FROM daily_availability
        WHERE date >= '2024-01-01'
    ) TO 'availability_2024.csv' (HEADER, DELIMITER ',')
""")

# Export to Parquet (smaller, faster)
db.conn.execute("""
    COPY (
        SELECT * FROM daily_availability
    ) TO 'availability_full.parquet' (FORMAT PARQUET)
""")

db.close()
```

## Performance Tips

1. **Use indexes**: Queries on `date` and `symbol` are optimized
2. **Filter early**: Add `WHERE` clauses before `GROUP BY`
3. **Limit results**: Use `LIMIT` for large result sets
4. **Column pruning**: Select only needed columns
5. **Batch queries**: Use context managers to reuse connections

Example of optimized query:

```python
# Good: Filter first, then aggregate
SELECT date, COUNT(*) FROM daily_availability
WHERE available = true AND date >= '2024-01-01'
GROUP BY date

# Bad: Aggregate first, then filter
SELECT date, COUNT(*) FROM daily_availability
GROUP BY date
HAVING date >= '2024-01-01'
```

## Next Steps

- **[Troubleshooting](TROUBLESHOOTING.md)**: Common issues
- **[Schema Documentation](../schema/query-patterns.schema.json)**: Query pattern specifications
