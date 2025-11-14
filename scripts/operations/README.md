# Operations Scripts

Production-ready operational scripts for binance-futures-availability.

## Scripts

### backfill.py

AWS CLI-based historical backfill script for bulk data collection.

**Usage:**

```bash
# Full backfill (all symbols, all dates)
uv run python scripts/operations/backfill.py

# Specific date range
uv run python scripts/operations/backfill.py --start-date 2024-01-01 --end-date 2024-12-31

# Specific symbols
uv run python scripts/operations/backfill.py --symbols BTCUSDT ETHUSDT
```

**Performance:** ~25 minutes for 327 symbols × 2,242 days (1.5M records)

### scheduler_daemon.py

APScheduler daemon for automated daily updates.

**Usage:**

```bash
# Start scheduler in foreground (testing)
uv run python scripts/operations/scheduler_daemon.py

# Start as background daemon (production)
uv run python scripts/operations/scheduler_daemon.py --daemon

# Stop daemon
uv run python scripts/operations/scheduler_daemon.py --stop
```

**Schedule:** Daily at 2:00 AM UTC, updates yesterday's data

### validate.py

Database validation and integrity checks.

**Usage:**

```bash
# Run all validation checks
uv run python scripts/operations/validate.py

# Specific validation
uv run python scripts/operations/validate.py --check continuity
```

**Checks:**

- Date continuity (no missing dates)
- Symbol count per date (100-700 range)
- Cross-check with Binance exchangeInfo API (>95% match)

## See Also

- Legacy scripts: `scripts/legacy/` (deprecated methods)
- Documentation: `docs/guides/QUICKSTART.md`
