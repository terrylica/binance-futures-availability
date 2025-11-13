#!/usr/bin/env python3
"""
Start APScheduler daemon for daily updates.

Schedule: Daily at 2:00 AM UTC
Target: Probe yesterday's data (T+1 availability)

Usage:
    python scripts/start_scheduler.py
    python scripts/start_scheduler.py --stop
"""

import argparse
import logging
import os
import signal
import sys
import time
from pathlib import Path

from binance_futures_availability.scheduler.daily_update import DailyUpdateScheduler
from binance_futures_availability.scheduler.notifications import setup_scheduler_logging


def write_pid_file(pid_path: Path) -> None:
    """Write PID file for process tracking."""
    pid_path.parent.mkdir(parents=True, exist_ok=True)
    pid_path.write_text(str(os.getpid()))


def read_pid_file(pid_path: Path) -> int | None:
    """Read PID from file."""
    if pid_path.exists():
        try:
            return int(pid_path.read_text().strip())
        except ValueError:
            return None
    return None


def remove_pid_file(pid_path: Path) -> None:
    """Remove PID file."""
    if pid_path.exists():
        pid_path.unlink()


def main() -> int:
    """
    Start or stop APScheduler daemon.

    Returns:
        Exit code (0=success, non-zero=failure)
    """
    parser = argparse.ArgumentParser(description="APScheduler daemon control")

    parser.add_argument(
        "--stop",
        action="store_true",
        help="Stop running scheduler",
    )

    args = parser.parse_args()

    # PID file location
    cache_dir = Path.home() / ".cache" / "binance-futures"
    cache_dir.mkdir(parents=True, exist_ok=True)
    pid_path = cache_dir / "scheduler.pid"

    if args.stop:
        # Stop scheduler
        pid = read_pid_file(pid_path)
        if pid is None:
            print("No scheduler PID found")
            return 1

        try:
            os.kill(pid, signal.SIGTERM)
            print(f"Scheduler stopped (PID: {pid})")
            remove_pid_file(pid_path)
            return 0
        except ProcessLookupError:
            print(f"Process {pid} not found (stale PID file)")
            remove_pid_file(pid_path)
            return 1

    # Start scheduler
    logger = setup_scheduler_logging(level=logging.INFO)

    logger.info("=" * 60)
    logger.info("Binance Futures Availability - APScheduler Daemon")
    logger.info("=" * 60)
    logger.info(f"Schedule: Daily at 2:00 AM UTC")
    logger.info(f"Target: Probe yesterday's data (T+1 availability)")
    logger.info(f"PID: {os.getpid()}")
    logger.info("=" * 60)

    # Write PID file
    write_pid_file(pid_path)

    # Signal handler for graceful shutdown
    scheduler = DailyUpdateScheduler()

    def signal_handler(signum, frame):
        logger.info("Received shutdown signal, stopping scheduler...")
        scheduler.stop(wait=True)
        remove_pid_file(pid_path)
        logger.info("Scheduler stopped gracefully")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Start scheduler
        scheduler.start()
        logger.info("Scheduler started successfully")
        logger.info("Press Ctrl+C to stop, or run: python scripts/start_scheduler.py --stop")

        # Keep process alive
        while True:
            time.sleep(1)

    except Exception as e:
        logger.error(f"Scheduler failed: {e}", exc_info=True)
        remove_pid_file(pid_path)
        return 1


if __name__ == "__main__":
    sys.exit(main())
