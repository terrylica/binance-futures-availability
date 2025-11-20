"""Database schema definition and creation.

See: docs/architecture/decisions/0019-performance-optimization-strategy.md (column compression)
"""

import duckdb


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
            PRIMARY KEY (date, symbol)
        )
    """)

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
