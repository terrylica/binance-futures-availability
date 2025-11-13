"""Snapshot queries: Get all symbols available on a specific date.

See: docs/schema/query-patterns.schema.json (category: snapshot)
"""

import datetime
from pathlib import Path
from typing import Any

from binance_futures_availability.database.availability_db import AvailabilityDatabase


class SnapshotQueries:
    """
    Snapshot queries for point-in-time availability.

    Performance target: <1ms per query (idx_available_date index)
    """

    def __init__(self, db_path: Path | None = None) -> None:
        """
        Initialize snapshot queries.

        Args:
            db_path: Custom database path (default: ~/.cache/binance-futures/availability.duckdb)
        """
        self.db = AvailabilityDatabase(db_path=db_path)

    def get_available_symbols_on_date(self, date: datetime.date | str) -> list[dict[str, Any]]:
        """
        Get all symbols available on a specific date.

        Args:
            date: Target date (datetime.date or 'YYYY-MM-DD' string)

        Returns:
            List of dicts with keys: symbol, file_size_bytes, last_modified

        Example:
            >>> queries = SnapshotQueries()
            >>> results = queries.get_available_symbols_on_date('2024-01-15')
            >>> len(results)
            708
            >>> results[0]
            {'symbol': 'BTCUSDT', 'file_size_bytes': 8421945, 'last_modified': '2024-01-16T02:15:32Z'}

        Query:
            SELECT symbol, file_size_bytes, last_modified
            FROM daily_availability
            WHERE date = ? AND available = true
            ORDER BY symbol
        """
        if isinstance(date, str):
            date = datetime.date.fromisoformat(date)

        rows = self.db.query(
            """
            SELECT symbol, file_size_bytes, last_modified
            FROM daily_availability
            WHERE date = ? AND available = true
            ORDER BY symbol
            """,
            [date],
        )

        return [
            {"symbol": row[0], "file_size_bytes": row[1], "last_modified": row[2]} for row in rows
        ]

    def get_symbols_in_date_range(
        self, start_date: datetime.date | str, end_date: datetime.date | str
    ) -> list[str]:
        """
        Get all symbols that were available at any point in a date range.

        Args:
            start_date: Range start (inclusive)
            end_date: Range end (inclusive)

        Returns:
            List of unique symbol strings

        Example:
            >>> queries = SnapshotQueries()
            >>> symbols = queries.get_symbols_in_date_range('2024-01-01', '2024-03-31')
            >>> len(symbols)
            708

        Query:
            SELECT DISTINCT symbol
            FROM daily_availability
            WHERE date BETWEEN ? AND ? AND available = true
            ORDER BY symbol
        """
        if isinstance(start_date, str):
            start_date = datetime.date.fromisoformat(start_date)
        if isinstance(end_date, str):
            end_date = datetime.date.fromisoformat(end_date)

        rows = self.db.query(
            """
            SELECT DISTINCT symbol
            FROM daily_availability
            WHERE date BETWEEN ? AND ? AND available = true
            ORDER BY symbol
            """,
            [start_date, end_date],
        )

        return [row[0] for row in rows]

    def close(self) -> None:
        """Close database connection."""
        self.db.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit (auto-close connection)."""
        self.close()
