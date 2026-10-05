#!/usr/bin/env python3
"""
Run daily update with configurable lookback window.

Features:
- LOOKBACK_DAYS environment variable controls date range (default: 1 day)
- Rolling window: re-probes last N days on every run (ADR-0011)
- UPSERT semantics: safe to re-probe same dates (no duplicates)
- Volume metrics (ADR-0007): fills 1d-kline volume for available rows in the window that
  lack it; VOLUME_START_DATE (YYYY-MM-DD) widens that window for a one-time catch-up

See: docs/architecture/decisions/0011-20day-lookback-reliability.md
"""

import datetime
import logging
import os
import sys
from pathlib import Path

from binance_futures_availability.database import AvailabilityDatabase
from binance_futures_availability.probing.batch_prober import BatchProber
from binance_futures_availability.probing.volume_fetcher import collect_missing_volume

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    # Get configuration from environment
    db_path = os.environ.get("DB_PATH")
    if not db_path:
        logger.error("DB_PATH environment variable not set")
        sys.exit(1)

    # Feature flag: Lookback days (ADR-0011)
    lookback_days = int(os.environ.get("LOOKBACK_DAYS", "1"))
    logger.info(f"Lookback configuration: {lookback_days} days")

    # Calculate date range
    # End: yesterday (S3 Vision has T+1 availability)
    # Start: yesterday - (lookback_days - 1)
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    start_date = yesterday - datetime.timedelta(days=lookback_days - 1)

    logger.info(f"Starting daily update: {start_date} to {yesterday} ({lookback_days} days)")

    try:
        # Initialize BatchProber
        prober = BatchProber()

        # Probe date range (uses existing probe_date_range method)
        if lookback_days == 1:
            # Optimize single-date case (backward compatibility)
            logger.info(f"Probing single date: {yesterday}")
            results = prober.probe_all_symbols(date=yesterday, contract_type="perpetual")
        else:
            # Multi-day lookback (ADR-0011)
            logger.info(f"Probing date range: {start_date} to {yesterday}")
            results = prober.probe_date_range(
                start_date=start_date, end_date=yesterday, contract_type="perpetual"
            )

        # Insert results into database (UPSERT semantics handle duplicates)
        logger.info(f"Inserting {len(results)} probe results into database")
        db = AvailabilityDatabase(db_path=Path(db_path))
        db.insert_batch(results)

        # ADR-0007: volume for available rows lacking it (re-probes keep existing volume).
        # Volume is supplementary enrichment: a failed fetch is logged as an ERROR but does not
        # block publishing availability. Failed rows stay NULL and are retried on the next run.
        # (Integrity violations, by contrast, fail the workflow in validate.py.)
        volume_start = os.environ.get("VOLUME_START_DATE") or str(start_date)
        try:
            volume = collect_missing_volume(
                db, datetime.date.fromisoformat(volume_start), yesterday
            )
        except RuntimeError as e:
            logger.error(f"VOLUME INCOMPLETE (retried next run): {e}")
            volume = {"filled": "partial", "missing": "unknown"}
        db.close()

        # Log summary
        available_count = sum(1 for r in results if r["available"])
        unavailable_count = len(results) - available_count

        logger.info(
            f"Daily update completed successfully: "
            f"{len(results)} total records, "
            f"{available_count} available, "
            f"{unavailable_count} unavailable, "
            f"{volume['filled']} volume filled ({volume['missing']} 1d files not yet published), "
            f"Date range: {start_date} to {yesterday}"
        )

        sys.exit(0)

    except Exception as e:
        logger.error(f"Daily update failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
