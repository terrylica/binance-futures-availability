"""Tests for snapshot queries."""

import datetime

from binance_futures_availability.queries.snapshots import SnapshotQueries


def test_get_available_symbols_on_date(populated_db, temp_db_path):
    """Test snapshot query for specific date."""
    queries = SnapshotQueries(db_path=temp_db_path)
    results = queries.get_available_symbols_on_date(datetime.date(2024, 1, 15))

    assert len(results) == 3
    symbols = [r["symbol"] for r in results]
    assert "BTCUSDT" in symbols
    assert "ETHUSDT" in symbols
    assert "SOLUSDT" in symbols

    queries.close()


def test_get_available_symbols_on_date_string_input(populated_db, temp_db_path):
    """Test snapshot query with string date input."""
    queries = SnapshotQueries(db_path=temp_db_path)
    results = queries.get_available_symbols_on_date("2024-01-15")

    assert len(results) == 3

    queries.close()


def test_get_symbols_in_date_range(populated_db, temp_db_path):
    """Test range query for multiple dates."""
    queries = SnapshotQueries(db_path=temp_db_path)
    symbols = queries.get_symbols_in_date_range(
        datetime.date(2024, 1, 15), datetime.date(2024, 1, 17)
    )

    assert len(symbols) == 3
    assert "BTCUSDT" in symbols
    assert "ETHUSDT" in symbols
    assert "SOLUSDT" in symbols

    queries.close()


def test_get_symbols_in_date_range_string_input(populated_db, temp_db_path):
    """Test range query with string date inputs."""
    queries = SnapshotQueries(db_path=temp_db_path)
    symbols = queries.get_symbols_in_date_range("2024-01-15", "2024-01-17")

    assert len(symbols) == 3

    queries.close()


def test_context_manager(populated_db, temp_db_path):
    """Test SnapshotQueries as context manager."""
    with SnapshotQueries(db_path=temp_db_path) as queries:
        results = queries.get_available_symbols_on_date("2024-01-15")
        assert len(results) == 3


def test_get_available_symbols_empty_database(db, temp_db_path):
    """Test snapshot query on empty database returns empty list (ADR-0027)."""
    queries = SnapshotQueries(db_path=temp_db_path)
    results = queries.get_available_symbols_on_date(datetime.date(2024, 1, 15))

    assert results == []

    queries.close()


def test_get_available_symbols_future_date(populated_db, temp_db_path):
    """Test snapshot query for date with no data returns empty list (ADR-0027)."""
    queries = SnapshotQueries(db_path=temp_db_path)
    # Query date outside populated range (2024-01-15 to 2024-01-17)
    results = queries.get_available_symbols_on_date(datetime.date(2025, 12, 31))

    assert results == []

    queries.close()
