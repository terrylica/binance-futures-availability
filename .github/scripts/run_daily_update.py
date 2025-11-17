#!/usr/bin/env python3
"""
Run daily update with configurable lookback window.

Features:
- LOOKBACK_DAYS environment variable controls date range (default: 1 day)
- Rolling window: re-probes last N days on every run (ADR-0011)
- UPSERT semantics: safe to re-probe same dates (no duplicates)
- Circuit breaker: aborts if error rate exceeds threshold (ADR-0003)

See: docs/decisions/0011-20day-lookback-reliability.md
"""
import os
import sys
import datetime
import logging
from pathlib import Path

from binance_futures_availability.database import AvailabilityDatabase
from binance_futures_availability.probing.batch_prober import BatchProber

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Circuit breaker threshold (ADR-0011)
ERROR_RATE_THRESHOLD = 0.05  # 5%


def main():
    # Get configuration from environment
    db_path = os.environ.get('DB_PATH')
    if not db_path:
        logger.error('DB_PATH environment variable not set')
        sys.exit(1)

    # Feature flag: Lookback days (ADR-0011)
    lookback_days = int(os.environ.get('LOOKBACK_DAYS', '1'))
    logger.info(f'Lookback configuration: {lookback_days} days')

    # Calculate date range
    # End: yesterday (S3 Vision has T+1 availability)
    # Start: yesterday - (lookback_days - 1)
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    start_date = yesterday - datetime.timedelta(days=lookback_days - 1)

    logger.info(f'Starting daily update: {start_date} to {yesterday} ({lookback_days} days)')

    try:
        # Initialize BatchProber
        logger.info('Initializing BatchProber with 150 workers')
        prober = BatchProber(max_workers=150)

        # Probe date range (uses existing probe_date_range method)
        if lookback_days == 1:
            # Optimize single-date case (backward compatibility)
            logger.info(f'Probing single date: {yesterday}')
            results = prober.probe_all_symbols(date=yesterday, contract_type="perpetual")
        else:
            # Multi-day lookback (ADR-0011)
            logger.info(f'Probing date range: {start_date} to {yesterday}')
            results = prober.probe_date_range(
                start_date=start_date,
                end_date=yesterday,
                contract_type="perpetual"
            )

        # Insert results into database (UPSERT semantics handle duplicates)
        logger.info(f'Inserting {len(results)} probe results into database')
        db = AvailabilityDatabase(db_path=Path(db_path))
        db.insert_batch(results)
        db.close()

        # Log summary
        available_count = sum(1 for r in results if r["available"])
        unavailable_count = len(results) - available_count

        logger.info(
            f'Daily update completed successfully: '
            f'{len(results)} total records, '
            f'{available_count} available, '
            f'{unavailable_count} unavailable, '
            f'Date range: {start_date} to {yesterday}'
        )

        sys.exit(0)

    except Exception as e:
        logger.error(f'Daily update failed: {e}', exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
