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

### scheduler_daemon.py ⚠️ DEPRECATED

**Status**: DEPRECATED as of 2025-11-15 (ADR-0009)

APScheduler daemon for automated daily updates.

**Replacement**: GitHub Actions automation (`.github/workflows/update-database.yml`)

**Migration**: This script has been superseded by GitHub Actions for zero-infrastructure overhead, 99.9% SLA, and built-in observability. See [ADR-0009](../../docs/architecture/decisions/0009-github-actions-automation.md) for migration rationale.

**Legacy Usage** (if needed for local testing):

```bash
# Start scheduler in foreground (testing only)
uv run python scripts/operations/scheduler_daemon.py

# NOT RECOMMENDED for production - use GitHub Actions instead
```

**Production Automation**: See [docs/operations/GITHUB_ACTIONS.md](../../docs/operations/GITHUB_ACTIONS.md)

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
