"""Update commands: Manual updates, backfill, and scheduler control.

Commands:
    - update manual: Manual update for specific date
    - update backfill: Historical backfill
    - update scheduler-start: Start APScheduler daemon
    - update scheduler-stop: Stop APScheduler daemon
"""

import argparse
import datetime
import logging

from binance_futures_availability.scheduler.backfill import BackfillScheduler
from binance_futures_availability.scheduler.daily_update import DailyUpdateScheduler

logger = logging.getLogger(__name__)


def add_update_commands(subparsers) -> None:
    """
    Add update commands to CLI parser.

    Args:
        subparsers: argparse subparsers object
    """
    update_parser = subparsers.add_parser(
        "update",
        help="Manual updates, backfill, and scheduler control",
    )

    update_subparsers = update_parser.add_subparsers(dest="update_command")

    # Manual update command
    manual_parser = update_subparsers.add_parser(
        "manual",
        help="Run manual update for specific date",
    )
    manual_parser.add_argument(
        "--date",
        type=str,
        help="Date to update (YYYY-MM-DD, default: yesterday)",
    )
    manual_parser.set_defaults(func=cmd_manual_update)

    # Backfill command
    backfill_parser = update_subparsers.add_parser(
        "backfill",
        help="Run historical backfill (2019-09-25 to yesterday)",
    )
    backfill_parser.add_argument(
        "--start-date",
        type=str,
        help="Backfill start date (YYYY-MM-DD, default: 2019-09-25)",
    )
    backfill_parser.add_argument(
        "--end-date",
        type=str,
        help="Backfill end date (YYYY-MM-DD, default: yesterday)",
    )
    backfill_parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Disable checkpoint resume",
    )
    backfill_parser.set_defaults(func=cmd_backfill)

    # Scheduler start command
    scheduler_start_parser = update_subparsers.add_parser(
        "scheduler-start",
        help="Start APScheduler daemon (daily updates at 2 AM UTC)",
    )
    scheduler_start_parser.set_defaults(func=cmd_scheduler_start)

    # Scheduler stop command
    scheduler_stop_parser = update_subparsers.add_parser(
        "scheduler-stop",
        help="Stop APScheduler daemon",
    )
    scheduler_stop_parser.set_defaults(func=cmd_scheduler_stop)


def cmd_manual_update(args: argparse.Namespace) -> int:
    """
    Execute manual update command.

    Args:
        args: Parsed arguments

    Returns:
        Exit code (0=success, non-zero=failure)
    """
    # Parse date
    if args.date:
        date = datetime.date.fromisoformat(args.date)
    else:
        date = datetime.date.today() - datetime.timedelta(days=1)

    logger.info(f"Running manual update for {date}")

    try:
        scheduler = DailyUpdateScheduler()
        scheduler.run_manual_update(date=date)
        logger.info(f"Manual update completed for {date}")
        return 0

    except Exception as e:
        logger.error(f"Manual update failed: {e}", exc_info=True)
        return 1


def cmd_backfill(args: argparse.Namespace) -> int:
    """
    Execute backfill command.

    Args:
        args: Parsed arguments

    Returns:
        Exit code (0=success, non-zero=failure)
    """
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

    logger.info(f"Starting backfill: {start_date} to {end_date} (resume={resume})")

    try:
        backfill = BackfillScheduler()
        backfill.run_backfill(
            start_date=start_date, end_date=end_date, resume_from_checkpoint=resume
        )
        logger.info("Backfill completed successfully")
        return 0

    except Exception as e:
        logger.error(f"Backfill failed: {e}", exc_info=True)
        return 1


def cmd_scheduler_start(args: argparse.Namespace) -> int:
    """
    Execute scheduler start command.

    Args:
        args: Parsed arguments

    Returns:
        Exit code (0=success, non-zero=failure)
    """
    logger.info("Starting APScheduler daemon...")

    try:
        import signal
        import time

        scheduler = DailyUpdateScheduler()
        scheduler.start()

        logger.info("APScheduler daemon started (daily updates at 2:00 AM UTC)")
        logger.info("Press Ctrl+C to stop")

        # Signal handler for graceful shutdown
        def signal_handler(signum, frame):
            logger.info("Stopping scheduler...")
            scheduler.stop(wait=True)
            logger.info("Scheduler stopped")
            raise SystemExit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Keep process alive
        while True:
            time.sleep(1)

    except SystemExit:
        return 0

    except Exception as e:
        logger.error(f"Scheduler failed: {e}", exc_info=True)
        return 1


def cmd_scheduler_stop(args: argparse.Namespace) -> int:
    """
    Execute scheduler stop command.

    Args:
        args: Parsed arguments

    Returns:
        Exit code (0=success, non-zero=failure)
    """
    logger.info("Stopping APScheduler daemon...")

    # NOTE: This requires PID tracking in a future enhancement
    # For now, user must use Ctrl+C or kill command
    logger.warning(
        "Use Ctrl+C to stop scheduler, or find PID with: "
        "ps aux | grep binance-futures-availability"
    )

    return 1
