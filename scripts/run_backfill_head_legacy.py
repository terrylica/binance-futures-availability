#!/usr/bin/env python3
"""
Run historical backfill from 2019-09-25 to yesterday.

Estimated time: 4-6 hours for ~2240 days × 708 symbols

Usage:
    python scripts/run_backfill.py
    python scripts/run_backfill.py --start-date 2024-01-01
    python scripts/run_backfill.py --no-resume  # Disable checkpoint resume
"""

import argparse
import datetime
import logging
import sys

from binance_futures_availability.scheduler.backfill import BackfillScheduler
from binance_futures_availability.scheduler.notifications import setup_scheduler_logging


def main() -> int:
    """
    Run historical backfill.

    Returns:
        Exit code (0=success, non-zero=failure)
    """
    parser = argparse.ArgumentParser(description="Run historical backfill")

    parser.add_argument(
        "--start-date",
        type=str,
        help="Backfill start date (YYYY-MM-DD, default: 2019-09-25)",
    )

    parser.add_argument(
        "--end-date",
        type=str,
        help="Backfill end date (YYYY-MM-DD, default: yesterday)",
    )

    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Disable checkpoint resume",
    )

    parser.add_argument(
        "--workers",
        type=int,
        default=10,
        help="Number of parallel workers (default: 10)",
    )

    args = parser.parse_args()

    # Setup logging
    logger = setup_scheduler_logging(level=logging.INFO)

    # Parse dates
    start_date = (
        datetime.date.fromisoformat(args.start_date)
        if args.start_date
        else datetime.date(2019, 9, 25)
    )

    end_date = (
        datetime.date.fromisoformat(args.end_date)
        if args.end_date
        else datetime.date.today() - datetime.timedelta(days=1)
    )

    resume = not args.no_resume

    logger.info("=" * 60)
    logger.info("Binance Futures Availability - Historical Backfill")
    logger.info("=" * 60)
    logger.info(f"Date range: {start_date} to {end_date}")
    logger.info(f"Resume from checkpoint: {resume}")
    logger.info(f"Parallel workers: {args.workers}")
    logger.info("=" * 60)

    try:
        backfill = BackfillScheduler(max_workers=args.workers)
        backfill.run_backfill(
            start_date=start_date,
            end_date=end_date,
            resume_from_checkpoint=resume,
        )

        logger.info("=" * 60)
        logger.info("Backfill completed successfully!")
        logger.info("=" * 60)

        return 0

    except KeyboardInterrupt:
        logger.info("\nBackfill interrupted by user")
        logger.info("Resume with: python scripts/run_backfill.py")
        return 130

    except Exception as e:
        logger.error(f"Backfill failed: {e}", exc_info=True)
        logger.info("Resume with: python scripts/run_backfill.py")
        return 1


if __name__ == "__main__":
    sys.exit(main())
