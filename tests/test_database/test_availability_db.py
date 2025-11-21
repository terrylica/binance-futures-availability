"""Tests for AvailabilityDatabase CRUD operations."""

import datetime


def test_insert_availability(db, sample_probe_result):
    """Test inserting a single availability record."""
    db.insert_availability(**sample_probe_result)

    # Verify insertion
    result = db.query(
        "SELECT symbol, date, available FROM daily_availability WHERE symbol = ?",
        [sample_probe_result["symbol"]],
    )

    assert len(result) == 1
    assert result[0][0] == "BTCUSDT"
    assert result[0][1] == datetime.date(2024, 1, 15)
    assert result[0][2] is True


def test_insert_batch(db, sample_probe_result, sample_unavailable_result):
    """Test batch insertion of multiple records."""
    records = [sample_probe_result, sample_unavailable_result]

    db.insert_batch(records)

    # Verify both records inserted
    result = db.query("SELECT COUNT(*) FROM daily_availability")
    assert result[0][0] == 2


def test_upsert_replaces_existing(db, sample_probe_result):
    """Test UPSERT behavior: insert then replace."""
    # Insert initial record
    db.insert_availability(**sample_probe_result)

    # Modify and re-insert (should replace)
    modified = sample_probe_result.copy()
    modified["file_size_bytes"] = 9999999

    db.insert_availability(**modified)

    # Verify only one record exists with updated value
    result = db.query(
        "SELECT file_size_bytes FROM daily_availability WHERE symbol = ? AND date = ?",
        [sample_probe_result["symbol"], sample_probe_result["date"]],
    )

    assert len(result) == 1
    assert result[0][0] == 9999999


def test_query_custom_sql(populated_db):
    """Test arbitrary SQL query execution."""
    result = populated_db.query(
        "SELECT symbol FROM daily_availability WHERE date = ? ORDER BY symbol",
        [datetime.date(2024, 1, 15)],
    )

    symbols = [row[0] for row in result]
    assert symbols == ["BTCUSDT", "ETHUSDT", "SOLUSDT"]


def test_context_manager(temp_db_path):
    """Test AvailabilityDatabase as context manager."""
    from binance_futures_availability.database.availability_db import AvailabilityDatabase

    with AvailabilityDatabase(db_path=temp_db_path) as db:
        # Insert record
        db.insert_availability(
            date=datetime.date(2024, 1, 15),
            symbol="BTCUSDT",
            available=True,
            file_size_bytes=8421945,
            last_modified=None,
            url="https://example.com/file.zip",
            status_code=200,
            probe_timestamp=datetime.datetime.now(datetime.UTC),
        )

    # Connection should be closed after exiting context


def test_insert_batch_empty_list(db):
    """Test insert_batch with empty list (should not raise error)."""
    db.insert_batch([])

    # Verify no records inserted
    result = db.query("SELECT COUNT(*) FROM daily_availability")
    assert result[0][0] == 0
