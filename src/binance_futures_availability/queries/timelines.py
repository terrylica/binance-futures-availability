"""Timeline queries: Get availability history for specific symbols.

See: docs/schema/query-patterns.schema.json (category: timeline)
"""

import datetime
from pathlib import Path
from typing import Any

from binance_futures_availability.database.availability_db import AvailabilityDatabase


class TimelineQueries:
    """
    Timeline queries for symbol availability history.

    Performance target: <10ms per query (idx_symbol_date index)
    """

    def __init__(self, db_path: Path | None = None) -> None:
        """
        Initialize timeline queries.

        Args:
            db_path: Custom database path (default: ~/.cache/binance-futures/availability.duckdb)
        """
        self.db = AvailabilityDatabase(db_path=db_path)

    def get_symbol_availability_timeline(self, symbol: str) -> list[dict[str, Any]]:
        """
        Get complete availability timeline for a single symbol.

        Args:
            symbol: Futures symbol (e.g., BTCUSDT)

        Returns:
            List of dicts with keys: date, available, file_size_bytes, status_code
            Sorted chronologically from earliest to latest date

        Example:
            >>> queries = TimelineQueries()
            >>> timeline = queries.get_symbol_availability_timeline('BTCUSDT')
            >>> len(timeline)
            2240  # 2019-09-25 to present
            >>> timeline[0]
            {'date': '2019-09-25', 'available': True, 'file_size_bytes': 7845123, 'status_code': 200}

        Query:
            SELECT date, available, file_size_bytes, status_code
            FROM daily_availability
            WHERE symbol = ?
            ORDER BY date
        """
        rows = self.db.query(
            """
            SELECT date, available, file_size_bytes, status_code
            FROM daily_availability
            WHERE symbol = ?
            ORDER BY date
            """,
            [symbol],
        )

        return [
            {
                "date": str(row[0]),
                "available": row[1],
                "file_size_bytes": row[2],
                "status_code": row[3],
            }
            for row in rows
        ]

    def get_symbol_first_listing_date(self, symbol: str) -> datetime.date | None:
        """
        Get the first date a symbol became available.

        Args:
            symbol: Futures symbol (e.g., BTCUSDT)

        Returns:
            First available date, or None if symbol never listed

        Example:
            >>> queries = TimelineQueries()
            >>> queries.get_symbol_first_listing_date('BTCUSDT')
            datetime.date(2019, 9, 25)

        Query:
            SELECT MIN(date)
            FROM daily_availability
            WHERE symbol = ? AND available = true
        """
        rows = self.db.query(
            """
            SELECT MIN(date)
            FROM daily_availability
            WHERE symbol = ? AND available = true
            """,
            [symbol],
        )

        if rows and rows[0][0]:
            return rows[0][0]
        return None

    def get_symbol_last_available_date(self, symbol: str) -> datetime.date | None:
        """
        Get the last date a symbol was available (for detecting delistings).

        Args:
            symbol: Futures symbol

        Returns:
            Last available date, or None if symbol never listed

        Example:
            >>> queries = TimelineQueries()
            >>> queries.get_symbol_last_available_date('BTCUSDT')
            datetime.date(2025, 11, 11)  # Still listed
            >>> queries.get_symbol_last_available_date('OLDCOINUSDT')
            datetime.date(2024, 1, 14)  # Delisted

        Query:
            SELECT MAX(date)
            FROM daily_availability
            WHERE symbol = ? AND available = true
        """
        rows = self.db.query(
            """
            SELECT MAX(date)
            FROM daily_availability
            WHERE symbol = ? AND available = true
            """,
            [symbol],
        )

        if rows and rows[0][0]:
            return rows[0][0]
        return None

    def close(self) -> None:
        """Close database connection."""
        self.db.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit (auto-close connection)."""
        self.close()
