"""Historical backfill scheduler with checkpoint resume.

See: docs/decisions/0003-error-handling-strict-policy.md (checkpoint handling)
"""

import datetime
import logging
from pathlib import Path

from binance_futures_availability.database.availability_db import AvailabilityDatabase
from binance_futures_availability.probing.batch_prober import BatchProber

logger = logging.getLogger(__name__)


class BackfillScheduler:
    """
    Historical backfill with checkpoint-based resume.

    Date range: 2019-09-25 (first UM-futures) to yesterday
    Checkpoint: Saves progress to file for resume after failures

    Estimated time: 4-6 hours for ~2240 days × 708 symbols
    """

    def __init__(
        self,
        db_path: Path | None = None,
        checkpoint_path: Path | None = None,
        max_workers: int = 10,
    ) -> None:
        """
        Initialize backfill scheduler.

        Args:
            db_path: Custom database path (default: ~/.cache/binance-futures/availability.duckdb)
            checkpoint_path: Checkpoint file (default: ~/.cache/binance-futures/backfill_checkpoint.txt)
            max_workers: Parallel probe workers (default: 10)
        """
        self.db_path = db_path
        self.max_workers = max_workers

        # Checkpoint file for resume
        if checkpoint_path is None:
            cache_dir = Path.home() / ".cache" / "binance-futures"
            cache_dir.mkdir(parents=True, exist_ok=True)
            checkpoint_path = cache_dir / "backfill_checkpoint.txt"

        self.checkpoint_path = Path(checkpoint_path)

    def save_checkpoint(self, last_completed_date: datetime.date) -> None:
        """
        Save checkpoint for resume.

        Args:
            last_completed_date: Last successfully processed date
        """
        self.checkpoint_path.write_text(str(last_completed_date))
        logger.info(f"Checkpoint saved: {last_completed_date}")

    def load_checkpoint(self) -> datetime.date | None:
        """
        Load checkpoint from file.

        Returns:
            Last completed date, or None if no checkpoint exists
        """
        if self.checkpoint_path.exists():
            date_str = self.checkpoint_path.read_text().strip()
            checkpoint_date = datetime.date.fromisoformat(date_str)
            logger.info(f"Checkpoint loaded: {checkpoint_date}")
            return checkpoint_date
        return None

    def clear_checkpoint(self) -> None:
        """Clear checkpoint file after successful backfill."""
        if self.checkpoint_path.exists():
            self.checkpoint_path.unlink()
            logger.info("Checkpoint cleared")

    def run_backfill(
        self,
        start_date: datetime.date | None = None,
        end_date: datetime.date | None = None,
        resume_from_checkpoint: bool = True,
    ) -> None:
        """
        Run historical backfill with checkpoint resume.

        Args:
            start_date: Backfill start (default: 2019-09-25, first UM-futures)
            end_date: Backfill end (default: yesterday)
            resume_from_checkpoint: Resume from checkpoint if exists (default: True)

        Raises:
            RuntimeError: On probe or database failure (ADR-0003: strict raise policy)

        Example:
            >>> backfill = BackfillScheduler()
            >>> backfill.run_backfill()  # Full historical backfill
            Backfill starting: 2019-09-25 to 2025-11-11 (2240 days)
            [Progress logs...]
            Backfill completed: 1,586,720 records inserted

        Estimated time: 4-6 hours for full backfill (2240 days × 708 symbols)
        """
        # Default date range: 2019-09-25 to yesterday
        if start_date is None:
            start_date = datetime.date(2019, 9, 25)

        if end_date is None:
            end_date = datetime.date.today() - datetime.timedelta(days=1)

        # Resume from checkpoint if requested
        if resume_from_checkpoint:
            checkpoint = self.load_checkpoint()
            if checkpoint:
                start_date = checkpoint + datetime.timedelta(days=1)
                logger.info(f"Resuming from checkpoint: {start_date}")

        # Calculate total days
        total_days = (end_date - start_date).days + 1
        logger.info(f"Backfill starting: {start_date} to {end_date} ({total_days} days)")

        # Initialize components
        db = AvailabilityDatabase(db_path=self.db_path)
        prober = BatchProber(max_workers=self.max_workers)

        # Checkpoint callback
        def checkpoint_callback(date: datetime.date, results: list) -> None:
            """Save checkpoint after each successful date."""
            self.save_checkpoint(date)
            logger.info(
                f"Progress: {date} completed "
                f"({sum(1 for r in results if r['available'])}/{len(results)} available)"
            )

        try:
            # Run backfill with checkpoint callback
            all_results = prober.probe_date_range(
                start_date=start_date,
                end_date=end_date,
                contract_type="perpetual",
                checkpoint_callback=checkpoint_callback,
            )

            # Insert all results
            logger.info(f"Inserting {len(all_results)} records into database...")
            db.insert_batch(all_results)

            # Clear checkpoint on success
            self.clear_checkpoint()

            logger.info(
                f"Backfill completed: {len(all_results)} records inserted "
                f"({start_date} to {end_date})"
            )

        except Exception as e:
            logger.error(f"Backfill failed: {e}", exc_info=True)
            logger.info(
                f"Checkpoint saved at: {self.checkpoint_path}. "
                f"Resume with resume_from_checkpoint=True"
            )
            raise

        finally:
            db.close()
