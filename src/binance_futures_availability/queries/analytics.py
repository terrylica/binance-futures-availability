"""Analytics queries: Aggregations and trend analysis.

See: docs/schema/query-patterns.schema.json (category: analytics)
"""

import datetime
from pathlib import Path
from typing import Any

from binance_futures_availability.database.availability_db import AvailabilityDatabase


class AnalyticsQueries:
    """
    Analytics queries for aggregations and trend analysis.

    Performance target: <50-100ms per query (columnar aggregation)
    """

    def __init__(self, db_path: Path | None = None) -> None:
        """
        Initialize analytics queries.

        Args:
            db_path: Custom database path (default: ~/.cache/binance-futures/availability.duckdb)
        """
        self.db = AvailabilityDatabase(db_path=db_path)

    def get_availability_summary(self) -> list[dict[str, Any]]:
        """
        Get daily symbol count over time (availability trend).

        Returns:
            List of dicts with keys: date, available_count
            Sorted chronologically

        Example:
            >>> queries = AnalyticsQueries()
            >>> summary = queries.get_availability_summary()
            >>> summary[0]
            {'date': '2019-09-25', 'available_count': 1}
            >>> summary[-1]
            {'date': '2025-11-11', 'available_count': 708}

        Query:
            SELECT date, COUNT(*) as available_count
            FROM daily_availability
            WHERE available = true
            GROUP BY date
            ORDER BY date
        """
        rows = self.db.query(
            """
            SELECT date, COUNT(*) as available_count
            FROM daily_availability
            WHERE available = true
            GROUP BY date
            ORDER BY date
            """
        )

        return [{"date": str(row[0]), "available_count": row[1]} for row in rows]

    def detect_new_listings(self, date: datetime.date | str) -> list[str]:
        """
        Identify symbols that became available on a specific date (first appearance).

        Args:
            date: Date to check for new listings

        Returns:
            List of newly listed symbol strings

        Example:
            >>> queries = AnalyticsQueries()
            >>> new_symbols = queries.detect_new_listings('2024-01-15')
            >>> new_symbols
            ['NEWCOINUSDT', 'ANOTHERCOINUSDT']

        Query:
            SELECT symbol
            FROM daily_availability
            WHERE available = true
              AND date = ?
              AND symbol NOT IN (
                  SELECT DISTINCT symbol
                  FROM daily_availability
                  WHERE date < ? AND available = true
              )
        """
        if isinstance(date, str):
            date = datetime.date.fromisoformat(date)

        rows = self.db.query(
            """
            SELECT symbol
            FROM daily_availability
            WHERE available = true
              AND date = ?
              AND symbol NOT IN (
                  SELECT DISTINCT symbol
                  FROM daily_availability
                  WHERE date < ? AND available = true
              )
            ORDER BY symbol
            """,
            [date, date],
        )

        return [row[0] for row in rows]

    def detect_delistings(self, date: datetime.date | str) -> list[str]:
        """
        Identify symbols that became unavailable on a specific date (last appearance was yesterday).

        Args:
            date: Date to check for delistings (first date unavailable)

        Returns:
            List of delisted symbol strings

        Example:
            >>> queries = AnalyticsQueries()
            >>> delisted = queries.detect_delistings('2024-01-15')
            >>> delisted
            ['OLDCOINUSDT']

        Query:
            SELECT symbol
            FROM daily_availability
            WHERE available = true
              AND date = (? - INTERVAL '1 day')
              AND symbol NOT IN (
                  SELECT DISTINCT symbol
                  FROM daily_availability
                  WHERE date = ? AND available = true
              )
        """
        if isinstance(date, str):
            date = datetime.date.fromisoformat(date)

        rows = self.db.query(
            """
            SELECT symbol
            FROM daily_availability
            WHERE available = true
              AND date = (? - INTERVAL '1 day')
              AND symbol NOT IN (
                  SELECT DISTINCT symbol
                  FROM daily_availability
                  WHERE date = ? AND available = true
              )
            ORDER BY symbol
            """,
            [date, date],
        )

        return [row[0] for row in rows]

    def get_symbol_count_by_date_range(
        self, start_date: datetime.date | str, end_date: datetime.date | str
    ) -> list[dict[str, Any]]:
        """
        Get daily symbol counts within a date range.

        Args:
            start_date: Range start (inclusive)
            end_date: Range end (inclusive)

        Returns:
            List of dicts with keys: date, available_count

        Example:
            >>> queries = AnalyticsQueries()
            >>> counts = queries.get_symbol_count_by_date_range('2024-01-01', '2024-01-07')
            >>> counts
            [
                {'date': '2024-01-01', 'available_count': 708},
                {'date': '2024-01-02', 'available_count': 708},
                ...
            ]

        Query:
            SELECT date, COUNT(*) as available_count
            FROM daily_availability
            WHERE date BETWEEN ? AND ? AND available = true
            GROUP BY date
            ORDER BY date
        """
        if isinstance(start_date, str):
            start_date = datetime.date.fromisoformat(start_date)
        if isinstance(end_date, str):
            end_date = datetime.date.fromisoformat(end_date)

        rows = self.db.query(
            """
            SELECT date, COUNT(*) as available_count
            FROM daily_availability
            WHERE date BETWEEN ? AND ? AND available = true
            GROUP BY date
            ORDER BY date
            """,
            [start_date, end_date],
        )

        return [{"date": str(row[0]), "available_count": row[1]} for row in rows]

    def close(self) -> None:
        """Close database connection."""
        self.db.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit (auto-close connection)."""
        self.close()
