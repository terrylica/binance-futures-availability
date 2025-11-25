"""Database schema definition and creation.

See: docs/architecture/decisions/0019-performance-optimization-strategy.md (column compression)
"""

import duckdb


def _migrate_add_volume_columns(conn: duckdb.DuckDBPyConnection) -> None:
    """
    ADR-0007 migration: Add volume columns to existing table.

    This handles schema drift where the database was created before ADR-0007
    was implemented. ALTER TABLE ADD COLUMN IF NOT EXISTS is safe to run
    multiple times.

    See: docs/architecture/decisions/0007-trading-volume-metrics.md
    """
    volume_columns = [
        ("quote_volume_usdt", "DOUBLE"),
        ("trade_count", "BIGINT"),
        ("volume_base", "DOUBLE"),
        ("taker_buy_volume_base", "DOUBLE"),
        ("taker_buy_quote_volume_usdt", "DOUBLE"),
        ("open_price", "DOUBLE"),
        ("high_price", "DOUBLE"),
        ("low_price", "DOUBLE"),
        ("close_price", "DOUBLE"),
    ]

    # Check which columns already exist
    existing_columns = {
        row[0]
        for row in conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'daily_availability'"
        ).fetchall()
    }

    # Add missing columns
    for column_name, column_type in volume_columns:
        if column_name not in existing_columns:
            conn.execute(f"ALTER TABLE daily_availability ADD COLUMN {column_name} {column_type}")


def create_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """
    Create the daily_availability table and indexes.

    Args:
        conn: DuckDB connection

    Schema:
        - Primary key: (date, symbol)
        - Indexes:
            - idx_symbol_date: Fast timeline queries
            - idx_available_date: Fast snapshot queries
        - Compression (ADR-0019):
            - symbol, url: Dictionary compression (high cardinality, repetitive)
            - file_size_bytes, status_code: Bit packing (low cardinality)

    See: docs/schema/availability-database.schema.json
    See: docs/architecture/decisions/0001-schema-design-daily-table.md
    See: docs/architecture/decisions/0019-performance-optimization-strategy.md
    """
    # ADR-0019: Column compression for 60% storage reduction (50-150MB → 20-50MB)
    # Dictionary compression: ~327 unique symbols, highly repetitive URLs
    # Bit packing: status_code (200/404), file_size_bytes (~8MB typical)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_availability (
            date DATE NOT NULL,
            symbol VARCHAR NOT NULL USING COMPRESSION dictionary,
            available BOOLEAN NOT NULL,
            file_size_bytes BIGINT USING COMPRESSION bitpacking,
            last_modified TIMESTAMP,
            url VARCHAR NOT NULL USING COMPRESSION dictionary,
            status_code INTEGER NOT NULL USING COMPRESSION bitpacking,
            probe_timestamp TIMESTAMP NOT NULL,

            -- ADR-0007: Trading volume metrics (2025-11-24)
            -- Sourced from Binance Vision 1d kline files (350 bytes each)
            -- Primary ranking metric: quote_volume_usdt (USDT trading volume)
            -- Nullable: Volume data may not exist for all dates (2019-09-25 to 2019-12-30 gap)
            quote_volume_usdt DOUBLE,
            trade_count BIGINT,
            volume_base DOUBLE,
            taker_buy_volume_base DOUBLE,
            taker_buy_quote_volume_usdt DOUBLE,
            open_price DOUBLE,
            high_price DOUBLE,
            low_price DOUBLE,
            close_price DOUBLE,

            PRIMARY KEY (date, symbol)
        )
    """)

    # ADR-0007 migration: Add volume columns if they don't exist (for pre-ADR-0007 databases)
    _migrate_add_volume_columns(conn)

    # Index for timeline queries (symbol -> dates)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_symbol_date
        ON daily_availability(symbol, date)
    """)

    # Index for snapshot queries (date -> symbols)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_available_date
        ON daily_availability(available, date)
    """)

    # ADR-0007: Index for volume rankings (DESC for top-N queries)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_quote_volume_date
        ON daily_availability(quote_volume_usdt DESC, date)
    """)

    # ADR-0019: Materialized view for analytics queries (50x faster)
    # Pre-computed daily symbol counts to avoid full table scans
    # Refresh after bulk inserts using refresh_materialized_views()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_symbol_counts (
            date DATE PRIMARY KEY,
            total_symbols INTEGER NOT NULL,
            available_symbols INTEGER NOT NULL,
            unavailable_symbols INTEGER NOT NULL,
            last_updated TIMESTAMP NOT NULL
        )
    """)
