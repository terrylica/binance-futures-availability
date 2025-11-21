"""Tests for continuity validation."""

import datetime

from binance_futures_availability.validation.continuity import ContinuityValidator


def test_check_continuity_no_gaps(populated_db, temp_db_path):
    """Test continuity check with complete coverage (no gaps)."""
    validator = ContinuityValidator(db_path=temp_db_path)

    # Check only the range we populated (2024-01-15 to 2024-01-17)
    missing_dates = validator.check_continuity(
        start_date=datetime.date(2024, 1, 15), end_date=datetime.date(2024, 1, 17)
    )

    assert len(missing_dates) == 0

    validator.close()


def test_check_continuity_with_gap(db, temp_db_path):
    """Test continuity check detects missing date."""
    # Insert only 2024-01-15 and 2024-01-17 (missing 2024-01-16)
    db.insert_availability(
        date=datetime.date(2024, 1, 15),
        symbol="BTCUSDT",
        available=True,
        file_size_bytes=8000000,
        last_modified=None,
        url="https://example.com/file.zip",
        status_code=200,
        probe_timestamp=datetime.datetime.now(datetime.UTC),
    )

    db.insert_availability(
        date=datetime.date(2024, 1, 17),
        symbol="BTCUSDT",
        available=True,
        file_size_bytes=8000000,
        last_modified=None,
        url="https://example.com/file.zip",
        status_code=200,
        probe_timestamp=datetime.datetime.now(datetime.UTC),
    )

    validator = ContinuityValidator(db_path=temp_db_path)
    missing_dates = validator.check_continuity(
        start_date=datetime.date(2024, 1, 15), end_date=datetime.date(2024, 1, 17)
    )

    assert len(missing_dates) == 1
    assert datetime.date(2024, 1, 16) in missing_dates

    validator.close()


def test_validate_continuity(populated_db, temp_db_path):
    """Test validate_continuity returns boolean."""
    validator = ContinuityValidator(db_path=temp_db_path)

    result = validator.validate_continuity(
        start_date=datetime.date(2024, 1, 15), end_date=datetime.date(2024, 1, 17)
    )

    assert result is True

    validator.close()
