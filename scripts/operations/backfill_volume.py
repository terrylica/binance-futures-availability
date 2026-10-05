#!/usr/bin/env python3
"""
Backfill trading volume metrics (ADR-0007) for available rows that lack them.

Thin CLI over probing.volume_fetcher.collect_missing_volume (the same code path the daily
update uses for its lookback window). One ~350-byte GET per row over the shared HTTP pool.

Usage:
    uv run python scripts/operations/backfill_volume.py --start-date 2025-11-01
    uv run python scripts/operations/backfill_volume.py --start-date 2024-01-01 --end-date 2024-01-31
"""

import argparse
import datetime
import logging
import sys

from binance_futures_availability.database import AvailabilityDatabase
from binance_futures_availability.probing.s3_vision import MAX_WORKERS
from binance_futures_availability.probing.volume_fetcher import collect_missing_volume


def _date(value: str) -> datetime.date:
    return datetime.date.fromisoformat(value)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0].strip())
    parser.add_argument("--start-date", type=_date, required=True, help="YYYY-MM-DD")
    parser.add_argument(
        "--end-date",
        type=_date,
        default=datetime.datetime.now(datetime.UTC).date() - datetime.timedelta(days=1),
        help="YYYY-MM-DD (default: yesterday UTC)",
    )
    parser.add_argument("--workers", type=int, default=MAX_WORKERS)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
    with AvailabilityDatabase() as db:
        stats = collect_missing_volume(db, args.start_date, args.end_date, args.workers)
    print(stats)
    return 0


if __name__ == "__main__":
    sys.exit(main())
