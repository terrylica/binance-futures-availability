"""Core database operations for availability storage."""

import datetime
from pathlib import Path
from typing import Any

import duckdb

from binance_futures_availability.database.schema import (
    create_schema,
    refresh_daily_symbol_counts,
)

_PROBE_COLUMNS = (
    "available",
    "file_size_bytes",
    "last_modified",
    "url",
    "status_code",
    "probe_timestamp",
)
# ADR-0007 volume metrics. Nullable, and kept on conflict when the new row carries none, so an
# availability-only re-probe never wipes volume collected earlier.
VOLUME_COLUMNS = (
    "quote_volume_usdt",
    "trade_count",
    "volume_base",
    "taker_buy_volume_base",
    "taker_buy_quote_volume_usdt",
    "open_price",
    "high_price",
    "low_price",
    "close_price",
)
_ALL_COLUMNS = ("date", "symbol", *_PROBE_COLUMNS, *VOLUME_COLUMNS)

# Explicit ON CONFLICT, never INSERT OR REPLACE: DuckDB 1.4.x's OR REPLACE skipped indexed
# non-key columns (see schema._UPSERT_BREAKING_INDEXES), corrupting `available` for ~10 months.
_UPSERT_SQL = (
    f"INSERT INTO daily_availability ({', '.join(_ALL_COLUMNS)}) "
    f"VALUES ({', '.join('?' * len(_ALL_COLUMNS))}) "
    "ON CONFLICT (date, symbol) DO UPDATE SET "
    + ", ".join(
        [f"{c} = excluded.{c}" for c in _PROBE_COLUMNS]
        + [f"{c} = COALESCE(excluded.{c}, daily_availability.{c})" for c in VOLUME_COLUMNS]
    )
)


class AvailabilityDatabase:
    """
    DuckDB-backed storage for daily futures availability data.

    Database location: ~/.cache/binance-futures/availability.duckdb

    Pattern: Similar to ValidationStorage from gapless-crypto-data
    See: docs/architecture/decisions/0002-storage-technology-duckdb.md
    """

    def __init__(
        self, db_path: Path | None = None, skip_materialized_refresh: bool = False
    ) -> None:
        """
        Initialize database connection and create schema if needed.

        Args:
            db_path: Custom database path (default: DB_PATH env var or ~/.cache/binance-futures/availability.duckdb)
            skip_materialized_refresh: Skip auto-refresh of materialized views after batch insert (for parallel operations)
        """
        if db_path is None:
            # Check environment variable first (critical for GitHub Actions)
            import os

            db_path_env = os.environ.get("DB_PATH")
            if db_path_env:
                db_path = Path(db_path_env)
            else:
                cache_dir = Path.home() / ".cache" / "binance-futures"
                cache_dir.mkdir(parents=True, exist_ok=True)
                db_path = cache_dir / "availability.duckdb"

        self.db_path = Path(db_path)
        self.skip_materialized_refresh = skip_materialized_refresh
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
        quote_volume_usdt: float | None = None,
        trade_count: int | None = None,
        volume_base: float | None = None,
        taker_buy_volume_base: float | None = None,
        taker_buy_quote_volume_usdt: float | None = None,
        open_price: float | None = None,
        high_price: float | None = None,
        low_price: float | None = None,
        close_price: float | None = None,
    ) -> None:
        """
        Insert or update a single availability record (UPSERT via insert_batch).

        Args:
            date: Trading date (UTC)
            symbol: Futures symbol (e.g., BTCUSDT)
            available: Whether file exists (true=200 OK, false=404)
            file_size_bytes: File size from Content-Length header (None if unavailable)
            last_modified: S3 Last-Modified timestamp (None if unavailable)
            url: Full S3 URL probed
            status_code: HTTP status code (200, 404, etc.)
            probe_timestamp: UTC timestamp when probe was executed
            quote_volume_usdt: ADR-0007: USDT trading volume (None if unavailable)
            trade_count: ADR-0007: Number of trades (None if unavailable)
            volume_base: ADR-0007: Base asset volume (None if unavailable)
            taker_buy_volume_base: ADR-0007: Taker buy base volume (None if unavailable)
            taker_buy_quote_volume_usdt: ADR-0007: Taker buy USDT volume (None if unavailable)
            open_price: ADR-0007: Opening price (None if unavailable)
            high_price: ADR-0007: Highest price (None if unavailable)
            low_price: ADR-0007: Lowest price (None if unavailable)
            close_price: ADR-0007: Closing price (None if unavailable)

        Raises:
            RuntimeError: On database error (ADR-0003: strict raise policy)
        """
        self.insert_batch(
            [
                {
                    "date": date,
                    "symbol": symbol,
                    "available": available,
                    "file_size_bytes": file_size_bytes,
                    "last_modified": last_modified,
                    "url": url,
                    "status_code": status_code,
                    "probe_timestamp": probe_timestamp,
                    "quote_volume_usdt": quote_volume_usdt,
                    "trade_count": trade_count,
                    "volume_base": volume_base,
                    "taker_buy_volume_base": taker_buy_volume_base,
                    "taker_buy_quote_volume_usdt": taker_buy_quote_volume_usdt,
                    "open_price": open_price,
                    "high_price": high_price,
                    "low_price": low_price,
                    "close_price": close_price,
                }
            ]
        )

    def insert_batch(self, records: list[dict[str, Any]]) -> None:
        """
        Insert multiple availability records in a single transaction.

        Args:
            records: List of dicts with keys matching insert_availability() parameters
                     (8 required fields + 9 optional ADR-0007 volume fields)

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
            ...         'probe_timestamp': datetime.datetime.now(datetime.timezone.utc),
            ...         # ADR-0007: Optional volume metrics
            ...         'quote_volume_usdt': 123456789.12,
            ...         'trade_count': 987654
            ...     }
            ... ]
            >>> db.insert_batch(records)
        """
        if not records:
            return

        try:
            self.conn.executemany(
                _UPSERT_SQL, [tuple(r.get(c) for c in _ALL_COLUMNS) for r in records]
            )
            # ADR-0019: Auto-refresh materialized views after batch insert
            # Skip if disabled (for parallel operations to avoid concurrent conflicts)
            if not self.skip_materialized_refresh:
                self.refresh_materialized_views()
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

    def refresh_materialized_views(self) -> None:
        """
        Refresh materialized views with latest data.

        ADR-0019: Pre-compute daily symbol counts for 50x faster analytics.
        Called automatically after insert_batch() for incremental updates.

        Raises:
            RuntimeError: On refresh error (ADR-0003: strict raise policy)
        """
        try:
            refresh_daily_symbol_counts(self.conn)
        except Exception as e:
            raise RuntimeError(f"Failed to refresh materialized views: {e}") from e

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
