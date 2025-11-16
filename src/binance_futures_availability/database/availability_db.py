"""Core database operations for availability storage."""

import datetime
from pathlib import Path
from typing import Any

import duckdb

from binance_futures_availability.database.schema import create_schema


class AvailabilityDatabase:
    """
    DuckDB-backed storage for daily futures availability data.

    Database location: ~/.cache/binance-futures/availability.duckdb

    Pattern: Similar to ValidationStorage from gapless-crypto-data
    See: docs/decisions/0002-storage-technology-duckdb.md
    """

    def __init__(self, db_path: Path | None = None) -> None:
        """
        Initialize database connection and create schema if needed.

        Args:
            db_path: Custom database path (default: DB_PATH env var or ~/.cache/binance-futures/availability.duckdb)
        """
        if db_path is None:
            # Check environment variable first (critical for GitHub Actions)
            import os
            db_path_env = os.environ.get('DB_PATH')
            if db_path_env:
                db_path = Path(db_path_env)
            else:
                cache_dir = Path.home() / ".cache" / "binance-futures"
                cache_dir.mkdir(parents=True, exist_ok=True)
                db_path = cache_dir / "availability.duckdb"

        self.db_path = Path(db_path)
        self.conn = duckdb.connect(str(self.db_path))
        create_schema(self.conn)

    def insert_availability(
        self,
        date: datetime.date,
        symbol: str,
        available: bool,
        file_size_bytes: int | None,
        last_modified: datetime.datetime | None,
        url: str,
        status_code: int,
        probe_timestamp: datetime.datetime,
    ) -> None:
        """
        Insert or update a single availability record (UPSERT).

        Args:
            date: Trading date (UTC)
            symbol: Futures symbol (e.g., BTCUSDT)
            available: Whether file exists (true=200 OK, false=404)
            file_size_bytes: File size from Content-Length header (None if unavailable)
            last_modified: S3 Last-Modified timestamp (None if unavailable)
            url: Full S3 URL probed
            status_code: HTTP status code (200, 404, etc.)
            probe_timestamp: UTC timestamp when probe was executed

        Raises:
            RuntimeError: On database error (ADR-0003: strict raise policy)
        """
        try:
            self.conn.execute(
                """
                INSERT OR REPLACE INTO daily_availability
                (date, symbol, available, file_size_bytes, last_modified, url, status_code, probe_timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    date,
                    symbol,
                    available,
                    file_size_bytes,
                    last_modified,
                    url,
                    status_code,
                    probe_timestamp,
                ],
            )
        except Exception as e:
            raise RuntimeError(
                f"Failed to insert availability for {symbol} on {date}: {e}"
            ) from e

    def insert_batch(self, records: list[dict[str, Any]]) -> None:
        """
        Insert multiple availability records in a single transaction.

        Args:
            records: List of dicts with keys matching insert_availability() parameters

        Raises:
            RuntimeError: On database error (ADR-0003: strict raise policy)

        Example:
            >>> db = AvailabilityDatabase()
            >>> records = [
            ...     {
            ...         'date': datetime.date(2024, 1, 15),
            ...         'symbol': 'BTCUSDT',
            ...         'available': True,
            ...         'file_size_bytes': 8421945,
            ...         'last_modified': datetime.datetime(2024, 1, 16, 2, 15, 32),
            ...         'url': 'https://data.binance.vision/...',
            ...         'status_code': 200,
            ...         'probe_timestamp': datetime.datetime.now(datetime.timezone.utc)
            ...     }
            ... ]
            >>> db.insert_batch(records)
        """
        if not records:
            return

        try:
            self.conn.executemany(
                """
                INSERT OR REPLACE INTO daily_availability
                (date, symbol, available, file_size_bytes, last_modified, url, status_code, probe_timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        r["date"],
                        r["symbol"],
                        r["available"],
                        r.get("file_size_bytes"),
                        r.get("last_modified"),
                        r["url"],
                        r["status_code"],
                        r["probe_timestamp"],
                    )
                    for r in records
                ],
            )
        except Exception as e:
            raise RuntimeError(f"Failed to insert batch of {len(records)} records: {e}") from e

    def query(self, sql: str, params: list[Any] | None = None) -> list[tuple]:
        """
        Execute arbitrary SQL query.

        Args:
            sql: SQL query string
            params: Query parameters

        Returns:
            List of result tuples

        Raises:
            RuntimeError: On query execution error (ADR-0003: strict raise policy)
        """
        try:
            result = self.conn.execute(sql, params or [])
            return result.fetchall()
        except Exception as e:
            raise RuntimeError(f"Query execution failed: {e}") from e

    def close(self) -> None:
        """
        Close database connection.

        Explicitly commits any pending transactions before closing to ensure
        all writes are flushed to disk. Critical for parallel worker threads.
        """
        if self.conn:
            self.conn.commit()  # Flush pending writes to disk (REQUIRED for parallel workers)
            self.conn.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit (auto-close connection)."""
        self.close()
