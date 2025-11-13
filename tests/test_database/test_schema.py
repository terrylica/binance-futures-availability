"""Tests for database schema creation."""

import pytest

from binance_futures_availability.database.schema import create_schema


def test_create_schema(db):
    """Test schema creation creates table and indexes."""
    # Schema already created by db fixture, verify it exists
    result = db.conn.execute(
        """
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='daily_availability'
        """
    ).fetchone()

    assert result is not None
    assert result[0] == "daily_availability"


def test_schema_has_correct_columns(db):
    """Test daily_availability table has all required columns."""
    result = db.conn.execute("PRAGMA table_info(daily_availability)").fetchall()
    column_names = [row[1] for row in result]

    expected_columns = [
        "date",
        "symbol",
        "available",
        "file_size_bytes",
        "last_modified",
        "url",
        "status_code",
        "probe_timestamp",
    ]

    for col in expected_columns:
        assert col in column_names, f"Column {col} not found in schema"


def test_schema_has_primary_key(db):
    """Test daily_availability has composite primary key (date, symbol)."""
    result = db.conn.execute("PRAGMA table_info(daily_availability)").fetchall()

    # Check primary key columns
    pk_columns = [row[1] for row in result if row[5] > 0]  # row[5] is pk flag

    assert "date" in pk_columns
    assert "symbol" in pk_columns


def test_schema_idempotent(db):
    """Test create_schema can be called multiple times without error."""
    # Schema already created by fixture
    create_schema(db.conn)  # Should not raise error
    create_schema(db.conn)  # Second call should also work

    # Verify table still exists
    result = db.conn.execute(
        """
        SELECT COUNT(*) FROM sqlite_master
        WHERE type='table' AND name='daily_availability'
        """
    ).fetchone()

    assert result[0] == 1  # Only one table (no duplicates)
