"""Daily update scheduler using APScheduler.

See: docs/decisions/0004-automation-apscheduler.md
"""

import datetime
import logging
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from binance_futures_availability.database.availability_db import AvailabilityDatabase
from binance_futures_availability.probing.batch_prober import BatchProber

logger = logging.getLogger(__name__)


class DailyUpdateScheduler:
    """
    APScheduler-based daily updates for futures availability.

    Schedule: Daily at 2:00 AM UTC
    Target: Probe yesterday's data (T+1 availability from S3 Vision)

    See: docs/decisions/0004-automation-apscheduler.md
    """

    def __init__(
        self,
        db_path: Path | None = None,
        scheduler_db_path: Path | None = None,
        max_workers: int = 10,
    ) -> None:
        """
        Initialize daily update scheduler.

        Args:
            db_path: Custom database path (default: ~/.cache/binance-futures/availability.duckdb)
            scheduler_db_path: Scheduler state DB (default: ~/.cache/binance-futures/scheduler.db)
            max_workers: Parallel probe workers (default: 10)
        """
        self.db_path = db_path
        self.max_workers = max_workers

        # Scheduler state persistence
        if scheduler_db_path is None:
            cache_dir = Path.home() / ".cache" / "binance-futures"
            cache_dir.mkdir(parents=True, exist_ok=True)
            scheduler_db_path = cache_dir / "scheduler.db"

        # Configure APScheduler with SQLite job store
        from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

        jobstores = {"default": SQLAlchemyJobStore(url=f"sqlite:///{scheduler_db_path}")}

        self.scheduler = BackgroundScheduler(jobstores=jobstores, timezone="UTC")

    def daily_update_job(self) -> None:
        """
        Probe yesterday's data for all symbols (T+1 availability).

        Raises:
            RuntimeError: On probe or database failure (ADR-0003: strict raise policy)
        """
        yesterday = datetime.date.today() - datetime.timedelta(days=1)

        logger.info(f"Starting daily update for {yesterday}")

        try:
            # Probe all symbols
            prober = BatchProber(max_workers=self.max_workers)
            results = prober.probe_all_symbols(date=yesterday, contract_type="perpetual")

            # Insert into database
            db = AvailabilityDatabase(db_path=self.db_path)
            db.insert_batch(results)
            db.close()

            available_count = sum(1 for r in results if r["available"])
            logger.info(
                f"Daily update completed for {yesterday}: "
                f"{len(results)} symbols probed, {available_count} available"
            )

        except Exception as e:
            logger.error(f"Daily update failed for {yesterday}: {e}", exc_info=True)
            raise  # Re-raise for APScheduler to log failure

    def start(self) -> None:
        """
        Start the scheduler daemon.

        Schedule: Daily at 2:00 AM UTC
        Job ID: daily_availability_update
        Max instances: 1 (prevent overlapping executions)
        """
        # Add daily job
        self.scheduler.add_job(
            func=self.daily_update_job,
            trigger=CronTrigger(hour=2, minute=0, timezone="UTC"),
            id="daily_availability_update",
            name="Probe yesterday's futures availability",
            replace_existing=True,
            max_instances=1,
        )

        # Start scheduler
        self.scheduler.start()
        logger.info("Daily update scheduler started (2:00 AM UTC)")

    def stop(self, wait: bool = True) -> None:
        """
        Stop the scheduler gracefully.

        Args:
            wait: Wait for running jobs to complete (default: True)
        """
        if self.scheduler.running:
            self.scheduler.shutdown(wait=wait)
            logger.info("Daily update scheduler stopped")

    def run_manual_update(self, date: datetime.date | None = None) -> None:
        """
        Run manual update for a specific date (bypass scheduler).

        Args:
            date: Date to update (default: yesterday)

        Raises:
            RuntimeError: On probe or database failure
        """
        if date is None:
            date = datetime.date.today() - datetime.timedelta(days=1)

        logger.info(f"Running manual update for {date}")

        # Probe all symbols
        prober = BatchProber(max_workers=self.max_workers)
        results = prober.probe_all_symbols(date=date, contract_type="perpetual")

        # Insert into database
        db = AvailabilityDatabase(db_path=self.db_path)
        db.insert_batch(results)
        db.close()

        available_count = sum(1 for r in results if r["available"])
        logger.info(
            f"Manual update completed for {date}: "
            f"{len(results)} symbols probed, {available_count} available"
        )
