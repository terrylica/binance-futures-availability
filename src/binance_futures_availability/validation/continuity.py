"""Continuity validation: Detect missing dates in database coverage.

See: docs/schema/query-patterns.schema.json (category: validation)
"""

import datetime
from pathlib import Path

from binance_futures_availability.database.availability_db import AvailabilityDatabase


class ContinuityValidator:
    """
    Detect gaps in date coverage.

    SLO: No missing dates between 2019-09-25 and yesterday
    See: docs/development/plan/v1.0.0-implementation-plan.yaml (success_criteria.functional)
    """

    def __init__(self, db_path: Path | None = None) -> None:
        """
        Initialize continuity validator.

        Args:
            db_path: Custom database path (default: ~/.cache/binance-futures/availability.duckdb)
        """
        self.db = AvailabilityDatabase(db_path=db_path)

    def check_continuity(
        self,
        start_date: datetime.date | str | None = None,
        end_date: datetime.date | str | None = None,
    ) -> list[datetime.date]:
        """
        Detect missing dates in database coverage.

        Args:
            start_date: Expected coverage start (default: 2019-09-25, first UM-futures launch)
            end_date: Expected coverage end (default: yesterday)

        Returns:
            List of missing dates (empty list = no gaps)

        Raises:
            RuntimeError: If continuity check fails

        Example:
            >>> validator = ContinuityValidator()
            >>> missing_dates = validator.check_continuity()
            >>> len(missing_dates)
            0  # Success: no gaps

        Query:
            WITH date_range AS (
                SELECT unnest(generate_series(?, ?, INTERVAL '1 day')::DATE[]) AS expected_date
            )
            SELECT expected_date
            FROM date_range
            WHERE expected_date NOT IN (SELECT DISTINCT date FROM daily_availability)
            ORDER BY expected_date
        """
        # Default date range: 2019-09-25 (first UM-futures) to yesterday
        if start_date is None:
            start_date = datetime.date(2019, 9, 25)
        elif isinstance(start_date, str):
            start_date = datetime.date.fromisoformat(start_date)

        if end_date is None:
            end_date = datetime.date.today() - datetime.timedelta(days=1)
        elif isinstance(end_date, str):
            end_date = datetime.date.fromisoformat(end_date)

        try:
            rows = self.db.query(
                """
                WITH date_range AS (
                    SELECT unnest(generate_series(?, ?, INTERVAL '1 day')::DATE[]) AS expected_date
                )
                SELECT expected_date
                FROM date_range
                WHERE expected_date NOT IN (SELECT DISTINCT date FROM daily_availability)
                ORDER BY expected_date
                """,
                [start_date, end_date],
            )

            return [row[0] for row in rows]

        except Exception as e:
            raise RuntimeError(
                f"Continuity check failed for range {start_date} to {end_date}: {e}"
            ) from e

    def validate_continuity(
        self,
        start_date: datetime.date | str | None = None,
        end_date: datetime.date | str | None = None,
    ) -> bool:
        """
        Validate that no dates are missing (assertion-style check).

        Args:
            start_date: Expected coverage start (default: 2019-09-25)
            end_date: Expected coverage end (default: yesterday)

        Returns:
            True if no gaps found, False otherwise

        Raises:
            RuntimeError: If continuity check query fails

        Example:
            >>> validator = ContinuityValidator()
            >>> validator.validate_continuity()
            True  # Success: complete coverage
        """
        missing_dates = self.check_continuity(start_date=start_date, end_date=end_date)
        return len(missing_dates) == 0

    def close(self) -> None:
        """Close database connection."""
        self.db.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit (auto-close connection)."""
        self.close()
