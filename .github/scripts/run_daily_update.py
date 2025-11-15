#!/usr/bin/env python3
"""Run daily update for yesterday's data."""
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

def main():
    # Get DB path from environment
    db_path = os.environ.get('DB_PATH')
    if not db_path:
        logger.error('DB_PATH environment variable not set')
        sys.exit(1)

    # Calculate yesterday (S3 Vision has T+1 availability)
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    logger.info(f'Starting daily update for {yesterday}')

    try:
        # Probe all perpetual symbols for yesterday
        logger.info('Initializing BatchProber with 150 workers')
        prober = BatchProber(max_workers=150)

        logger.info(f'Probing all perpetual symbols for {yesterday}')
        results = prober.probe_all_symbols(date=yesterday, contract_type="perpetual")

        # Insert results into database
        logger.info(f'Inserting {len(results)} probe results into database')
        db = AvailabilityDatabase(db_path=Path(db_path))
        db.insert_batch(results)
        db.close()

        # Log summary
        available_count = sum(1 for r in results if r["available"])
        unavailable_count = len(results) - available_count
        logger.info(
            f'Daily update completed successfully: '
            f'{len(results)} symbols probed, '
            f'{available_count} available, '
            f'{unavailable_count} unavailable'
        )

        sys.exit(0)

    except Exception as e:
        logger.error(f'Daily update failed: {e}', exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
