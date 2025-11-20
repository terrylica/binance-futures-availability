# Troubleshooting Guide

Common issues and solutions for Binance Futures Availability Database.

## Installation Issues

### Problem: `uv pip install -e .` fails

**Symptoms**:

```
ERROR: Could not find a version that satisfies the requirement duckdb>=1.0.0
```

**Solution**:
Ensure Python 3.12+ is installed:

```bash
python --version  # Should be 3.12 or higher

# If using pyenv
pyenv install 3.12.0
pyenv local 3.12.0

# Retry installation
uv pip install -e .
```

### Problem: Import errors after installation

**Symptoms**:

```python
ImportError: No module named 'binance_futures_availability'
```

**Solution**:
Install in editable mode from project root:

```bash
cd ~/eon/binance-futures-availability
uv pip install -e .
```

## Backfill Issues

### Problem: Backfill interrupted (network timeout, Ctrl+C)

**Symptoms**:

```
RuntimeError: AWS CLI timeout for BTCUSDT
```

**Solution**:
Re-run AWS CLI backfill (idempotent - uses UPSERT):

```bash
# AWS CLI backfill automatically resumes
uv run python scripts/operations/backfill.py

# Or backfill specific date range
uv run python scripts/operations/backfill.py --start-date 2024-01-01
```

### Problem: Backfill takes too long

**Expected time**: ~25 minutes for full backfill (2240 days × 327 symbols with AWS CLI)

**Note**: Legacy HEAD request method (deprecated per ADR-0005) took ~3 hours

**Optimization**:

```bash
# Increase parallel workers (default: 10)
uv run python scripts/operations/backfill.py --workers 20

# Note: AWS CLI has much better throughput than HEAD requests
```

### Problem: AWS CLI not installed

**Symptoms**:

```
RuntimeError: AWS CLI not found. Install with: brew install awscli
```

**Solution**:
Install AWS CLI:

```bash
brew install awscli

# Verify installation
aws --version
```

### Problem: Backfill completes but validation fails

**Symptoms**:

```
[1/3] Continuity Check: FAILED: 10 missing dates found
```

**Solution**:
Re-run backfill for specific date range:

```bash
# Backfill only missing dates
uv run python scripts/operations/backfill.py --start-date 2024-01-01 --end-date 2024-01-10
```

## Query Issues

### Problem: Query returns empty results

**Symptoms**:

```python
results = q.get_available_symbols_on_date('2024-01-15')
# results = []
```

**Diagnosis**:
Check if date exists in database:

```python
from binance_futures_availability.database import AvailabilityDatabase

with AvailabilityDatabase() as db:
    result = db.query("SELECT COUNT(*) FROM daily_availability WHERE date = ?", ['2024-01-15'])
    print(f"Records for 2024-01-15: {result[0][0]}")
```

**Solution**:

- If count is 0, run manual update for that date:

```bash
uv run binance-futures-availability update manual --date 2024-01-15
```

### Problem: Query performance is slow

**Symptoms**:

- Snapshot query takes >1s (expected: <1ms)
- Timeline query takes >100ms (expected: <10ms)

**Diagnosis**:
Check database size and indexes:

```python
from binance_futures_availability.database import AvailabilityDatabase
import os

db = AvailabilityDatabase()
db_size_mb = os.path.getsize(db.db_path) / 1024 / 1024

print(f"Database size: {db_size_mb:.1f} MB")

# Check indexes exist
result = db.query("""
    SELECT name FROM sqlite_master
    WHERE type='index' AND tbl_name='daily_availability'
""")

print(f"Indexes: {[row[0] for row in result]}")
db.close()
```

**Solution**:

- Expected indexes: `idx_symbol_date`, `idx_available_date`
- If missing, recreate schema:

```python
from binance_futures_availability.database import AvailabilityDatabase, create_schema

db = AvailabilityDatabase()
create_schema(db.conn)  # Idempotent, won't duplicate indexes
db.close()
```

## Scheduler Issues

### Problem: Scheduler fails to start

**Symptoms**:

```
Address already in use
```

**Solution**:
Check for existing scheduler process:

```bash
# Find PID
ps aux | grep start_scheduler

# Kill existing process
kill <PID>

# Or use stop command
uv run python scripts/start_scheduler.py --stop

# Restart
uv run python scripts/start_scheduler.py
```

### Problem: Daily updates not running

**Diagnosis**:
Check scheduler logs:

```bash
tail -f ~/.cache/binance-futures/scheduler.log
```

**Solution**:

- Verify scheduler is running:

```bash
ps aux | grep start_scheduler
```

- Check system time is in UTC (schedule is 2:00 AM UTC):

```bash
date -u
```

- Manually trigger update to test:

```bash
uv run binance-futures-availability update manual
```

### Problem: Scheduler stops unexpectedly

**Solution**:
Run in background with nohup:

```bash
nohup uv run python scripts/start_scheduler.py > /dev/null 2>&1 &

# Or use screen/tmux
screen -S scheduler
uv run python scripts/start_scheduler.py
# Ctrl+A, D to detach
```

## Validation Issues

### Problem: Continuity check finds missing dates

**Symptoms**:

```
FAILED: 5 missing dates found
  - 2024-01-15
  - 2024-01-16
  ...
```

**Solution**:
Backfill missing dates:

```bash
uv run binance-futures-availability update manual --date 2024-01-15
uv run binance-futures-availability update manual --date 2024-01-16
```

Or use backfill script for range:

```bash
uv run python scripts/operations/backfill.py --start-date 2024-01-15 --end-date 2024-01-20
```

### Problem: Completeness check fails (low symbol counts)

**Symptoms**:

```
FAILED: 2 dates with <700 symbols
  - 2024-01-15: 650 symbols
```

**Diagnosis**:
This may be legitimate (e.g., early dates had fewer symbols).

Check expected count for that date:

```python
from binance_futures_availability.queries import AnalyticsQueries

with AnalyticsQueries() as q:
    summary = q.get_availability_summary()

    for s in summary:
        if s['date'] == '2024-01-15':
            print(f"{s['date']}: {s['available_count']} symbols")
```

**Solution**:

- If count is unexpectedly low, re-run update for that date
- Adjust `min_symbol_count` threshold if needed (default: 700)

### Problem: Cross-check fails (low match percentage)

**Symptoms**:

```
FAILED: 92.0% match (SLO: >95%)
Symbols only in DB: 30
Symbols only in API: 10
```

**Diagnosis**:

- "Only in DB": Possible delistings (symbol removed from API but still in historical data)
- "Only in API": New listings not yet in database

**Solution**:

- Run manual update for yesterday:

```bash
uv run binance-futures-availability update manual
```

- Verify discrepancies are expected (delistings vs database staleness)

## Database Issues

### Problem: Database file is missing

**Symptoms**:

```
FileNotFoundError: No such file or directory: '~/.cache/binance-futures/availability.duckdb'
```

**Solution**:
Database is created on first use. Run backfill to populate:

```bash
uv run python scripts/operations/backfill.py
```

### Problem: Database is corrupted

**Symptoms**:

```
duckdb.IOException: Catalog Error: Table "daily_availability" does not exist
```

**Solution**:
Recreate schema:

```python
from binance_futures_availability.database import AvailabilityDatabase, create_schema

db = AvailabilityDatabase()
create_schema(db.conn)
db.close()
```

If corruption persists, delete database and re-run backfill:

```bash
rm ~/.cache/binance-futures/availability.duckdb
uv run python scripts/operations/backfill.py
```

### Problem: Database size is too large

**Expected size**: 50-150 MB for full historical data

**Diagnosis**:

```bash
du -h ~/.cache/binance-futures/availability.duckdb
```

**Solution**:
If size is >200 MB, consider VACUUM (DuckDB auto-manages compression):

```python
from binance_futures_availability.database import AvailabilityDatabase

db = AvailabilityDatabase()
db.conn.execute("VACUUM")
db.close()
```

## API/Network Issues

### Problem: Binance API is down

**Symptoms**:

```
RuntimeError: Failed to fetch exchangeInfo from API: HTTP 503 - Service Unavailable
```

**Solution**:

- Cross-check validation will fail temporarily
- Binance Vision S3 and exchangeInfo API are separate services
- S3 Vision probing should still work

### Problem: Network timeout during probe

**Symptoms**:

```
RuntimeError: Network error probing BTCUSDT on 2024-01-15: timeout
```

**Solution**:
Increase timeout in `s3_vision.py` (default: 10 seconds):

```python
result = check_symbol_availability('BTCUSDT', date, timeout=30)
```

Or reduce parallel workers to avoid network congestion.

## Getting Help

**Still stuck?**

1. **Check logs**:

   ```bash
   tail -f ~/.cache/binance-futures/scheduler.log
   ```

2. **Run validation**:

   ```bash
   uv run python scripts/validate_database.py --verbose
   ```

3. **Check database state**:

   ```python
   from binance_futures_availability.database import AvailabilityDatabase

   with AvailabilityDatabase() as db:
       result = db.query("SELECT COUNT(*) FROM daily_availability")
       print(f"Total records: {result[0][0]:,}")

       result = db.query("SELECT MIN(date), MAX(date) FROM daily_availability")
       print(f"Date range: {result[0][0]} to {result[0][1]}")
   ```

4. **File an issue**: Include error logs, database size, and steps to reproduce

## See Also

- [Quick Start Guide](QUICKSTART.md)
- [Query Examples](QUERY_EXAMPLES.md)
- [GitHub Actions Automation](../operations/GITHUB_ACTIONS.md)
