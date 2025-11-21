"""Completeness validation: Verify expected symbol counts.

See: docs/schema/query-patterns.schema.json (category: validation)
"""

import datetime
from pathlib import Path
from typing import Any

from binance_futures_availability.database.availability_db import AvailabilityDatabase


class CompletenessValidator:
    """
    Verify expected symbol counts for data completeness.

    SLO: Recent dates should have ~708 symbols (allowing for delistings)
    See: docs/development/plan/v1.0.0-implementation-plan.yaml (success_criteria.functional)
    """

    def __init__(self, db_path: Path | None = None) -> None:
        """
        Initialize completeness validator.

        Args:
            db_path: Custom database path (default: ~/.cache/binance-futures/availability.duckdb)
        """
        self.db = AvailabilityDatabase(db_path=db_path)

    def check_completeness(
        self,
        start_date: datetime.date | str | None = None,
        min_symbol_count: int = 700,
    ) -> list[dict[str, Any]]:
        """
        Identify dates with unexpectedly low symbol counts.

        Args:
            start_date: Start date for check (default: 90 days ago)
            min_symbol_count: Minimum expected symbols (default: 700)

        Returns:
            List of dicts with keys: date, symbol_count
            Empty list = all dates have sufficient symbols

        Raises:
            RuntimeError: If completeness check fails

        Example:
            >>> validator = CompletenessValidator()
            >>> incomplete_dates = validator.check_completeness(min_symbol_count=700)
            >>> len(incomplete_dates)
            0  # Success: all dates have ≥700 symbols

        Query:
            SELECT date, COUNT(*) as symbol_count
            FROM daily_availability
            WHERE date >= ? AND available = true
            GROUP BY date
            HAVING COUNT(*) < ?
            ORDER BY date
        """
        # Default: check last 90 days
        if start_date is None:
            start_date = datetime.date.today() - datetime.timedelta(days=90)
        elif isinstance(start_date, str):
            start_date = datetime.date.fromisoformat(start_date)

        try:
            rows = self.db.query(
                """
                SELECT date, COUNT(*) as symbol_count
                FROM daily_availability
                WHERE date >= ? AND available = true
                GROUP BY date
                HAVING COUNT(*) < ?
                ORDER BY date
                """,
                [start_date, min_symbol_count],
            )

            return [{"date": str(row[0]), "symbol_count": row[1]} for row in rows]

        except Exception as e:
            raise RuntimeError(
                f"Completeness check failed for dates >= {start_date}: {e}"
            ) from e

    def validate_completeness(
        self,
        start_date: datetime.date | str | None = None,
        min_symbol_count: int = 700,
    ) -> bool:
        """
        Validate that all dates have sufficient symbol counts (assertion-style check).

        Args:
            start_date: Start date for check (default: 90 days ago)
            min_symbol_count: Minimum expected symbols (default: 700)

        Returns:
            True if all dates have ≥min_symbol_count, False otherwise

        Raises:
            RuntimeError: If completeness check query fails

        Example:
            >>> validator = CompletenessValidator()
            >>> validator.validate_completeness(min_symbol_count=700)
            True  # Success: all recent dates have ≥700 symbols
        """
        incomplete_dates = self.check_completeness(
            start_date=start_date, min_symbol_count=min_symbol_count
        )
        return len(incomplete_dates) == 0

    def get_symbol_counts_summary(
        self, days: int = 30
    ) -> list[dict[str, Any]]:
        """
        Get daily symbol counts for recent dates (summary view).

        Args:
            days: Number of recent days to summarize (default: 30)

        Returns:
            List of dicts with keys: date, symbol_count
            Sorted chronologically

        Example:
            >>> validator = CompletenessValidator()
            >>> summary = validator.get_symbol_counts_summary(days=7)
            >>> summary
            [
                {'date': '2025-11-05', 'symbol_count': 708},
                {'date': '2025-11-06', 'symbol_count': 708},
                ...
            ]

        Query:
            SELECT date, COUNT(*) as symbol_count
            FROM daily_availability
            WHERE date >= (CURRENT_DATE - INTERVAL '? days') AND available = true
            GROUP BY date
            ORDER BY date
        """
        start_date = datetime.date.today() - datetime.timedelta(days=days)

        try:
            rows = self.db.query(
                """
                SELECT date, COUNT(*) as symbol_count
                FROM daily_availability
                WHERE date >= ? AND available = true
                GROUP BY date
                ORDER BY date
                """,
                [start_date],
            )

            return [{"date": str(row[0]), "symbol_count": row[1]} for row in rows]

        except Exception as e:
            raise RuntimeError(f"Failed to get symbol counts summary: {e}") from e

    def close(self) -> None:
        """Close database connection."""
        self.db.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit (auto-close connection)."""
        self.close()
