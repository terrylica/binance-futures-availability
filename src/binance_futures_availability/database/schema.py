"""Database schema definition and creation."""

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

    See: docs/schema/availability-database.schema.json
    See: docs/architecture/decisions/0001-schema-design-daily-table.md
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_availability (
            date DATE NOT NULL,
            symbol VARCHAR NOT NULL,
            available BOOLEAN NOT NULL,
            file_size_bytes BIGINT,
            last_modified TIMESTAMP,
            url VARCHAR NOT NULL,
            status_code INTEGER NOT NULL,
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
