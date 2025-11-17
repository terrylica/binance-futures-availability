# Quick Start Guide

Get started with Binance Futures Availability Database in 10 steps.

## Installation

```bash
cd ~/eon/binance-futures-availability

# Install package
uv pip install -e .

# Install development dependencies (optional)
uv pip install -e ".[dev]"
```

## Initial Setup

### Step 1: Run Historical Backfill

Populate the database with historical data (2019-09-25 to yesterday):

```bash
# AWS CLI-based backfill (RECOMMENDED: 7.2x faster)
uv run python scripts/scripts/operations/backfill.py
```

**Estimated time**: ~25 minutes for ~2240 days × 327 symbols

**Method**: Uses `aws s3 ls` to list all files per symbol in one API call

**Progress tracking**: Real-time progress with per-symbol completion

**Expected output**:

```
====================================================
AWS CLI-Based Historical Backfill (3.5x Faster)
====================================================
Date range: 2019-09-25 to 2025-11-13 (2242 days)
Symbols: 327
Parallel workers: 10
Estimated time: ~25 minutes
====================================================
[1/327] ✅ BTCUSDT: 2145/2242 dates available
[2/327] ✅ ETHUSDT: 1998/2242 dates available
...
Backfill Complete! Records inserted: 732,534
```

**Alternative (Legacy)**: HEAD request backfill available in `scripts/scripts/legacy/backfill_head.py` (~3 hours)

### Step 2: Validate Database

Verify data quality after backfill:

```bash
uv run python scripts/validate_database.py
```

**Expected output**:

```
[1/3] Continuity Check: Detecting missing dates...
PASSED: No missing dates (complete coverage)

[2/3] Completeness Check: Verifying symbol counts...
PASSED: All recent dates have ≥700 symbols

[3/3] Cross-check: Comparing with Binance exchangeInfo API...
PASSED: 98.5% match (SLO: >95%)

VALIDATION PASSED: All checks successful ✓
```

### Step 3: Start Automated Updates

Enable daily updates at 2:00 AM UTC:

```bash
uv run python scripts/start_scheduler.py
```

**Keep this process running** (or run in background with nohup/screen).

## Basic Usage

### Query Available Symbols on Date

```bash
# CLI
uv run binance-futures-availability query snapshot 2024-01-15

# Python API
python -c "
from binance_futures_availability.queries import SnapshotQueries
q = SnapshotQueries()
results = q.get_available_symbols_on_date('2024-01-15')
print(f'Available symbols: {len(results)}')
q.close()
"
```

### Query Symbol Timeline

```bash
# CLI
uv run binance-futures-availability query timeline BTCUSDT

# Python API
python -c "
from binance_futures_availability.queries import TimelineQueries
q = TimelineQueries()
timeline = q.get_symbol_availability_timeline('BTCUSDT')
print(f'Timeline length: {len(timeline)} days')
q.close()
"
```

### Detect New Listings

```bash
# CLI
uv run binance-futures-availability query analytics new-listings 2024-01-15

# Python API
python -c "
from binance_futures_availability.queries import AnalyticsQueries
q = AnalyticsQueries()
new_symbols = q.detect_new_listings('2024-01-15')
print(f'New listings: {new_symbols}')
q.close()
"
```

## Database Location

Default database path: `~/.cache/binance-futures/availability.duckdb`

**Size**: 50-150 MB (compressed columnar storage)

**Growth rate**: ~50 MB/year (708 rows/day × ~200 bytes/row compressed)

## Next Steps

- **[Query Examples](QUERY_EXAMPLES.md)**: Common query patterns
- **[Troubleshooting](TROUBLESHOOTING.md)**: Common issues and solutions
- **[GitHub Actions Automation](../operations/GITHUB_ACTIONS.md)**: Automated daily updates and monitoring
- **[Backup & Restore](../operations/BACKUP_RESTORE.md)**: Database backup procedures

## Quick Reference

### File Locations

```
~/.cache/binance-futures/
├── availability.duckdb         # Main database
├── scheduler.db                # APScheduler state
├── scheduler.log               # Scheduler logs
├── scheduler.pid               # Scheduler process ID
└── backfill_checkpoint.txt     # Backfill progress
```

### Common Commands

```bash
# Manual update for specific date
uv run binance-futures-availability update manual --date 2024-01-15

# Run validation
uv run python scripts/validate_database.py

# View recent symbol counts
uv run binance-futures-availability query analytics summary

# Stop scheduler
uv run python scripts/start_scheduler.py --stop
```

## Troubleshooting

**Backfill interrupted?**

```bash
# AWS CLI backfill is idempotent - just re-run
uv run python scripts/scripts/operations/backfill.py

# For partial backfills
uv run python scripts/scripts/operations/backfill.py --start-date 2024-01-01
```

**Missing dates?**

```bash
# Check continuity
python -c "
from binance_futures_availability.validation import ContinuityValidator
v = ContinuityValidator()
missing = v.check_continuity()
print(f'Missing dates: {missing}')
"
```

**Scheduler not running?**

```bash
# Check process
ps aux | grep start_scheduler

# Check logs
tail -f ~/.cache/binance-futures/scheduler.log
```

For more detailed troubleshooting, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).
