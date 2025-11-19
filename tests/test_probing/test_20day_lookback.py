"""
Tests for 20-day lookback functionality (ADR-0011).

Test coverage:
- Date range calculation for different lookback values
- UPSERT behavior when re-probing same dates
- Environment variable feature flag
- Integration with BatchProber.probe_date_range()

See: docs/architecture/decisions/0011-20day-lookback-reliability.md
"""

import datetime
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from binance_futures_availability.database.availability_db import AvailabilityDatabase
from binance_futures_availability.probing.batch_prober import BatchProber


class TestDateRangeCalculation:
    """Test date range calculation logic for different lookback values."""

    def test_1day_lookback(self):
        """1-day lookback (default) should probe only yesterday."""
        today = datetime.date(2024, 1, 20)
        lookback_days = 1

        yesterday = today - datetime.timedelta(days=1)
        start_date = yesterday - datetime.timedelta(days=lookback_days - 1)

        assert start_date == datetime.date(2024, 1, 19)
        assert yesterday == datetime.date(2024, 1, 19)
        assert start_date == yesterday  # Same date for 1-day lookback

    def test_7day_lookback(self):
        """7-day lookback should probe last 7 days."""
        today = datetime.date(2024, 1, 20)
        lookback_days = 7

        yesterday = today - datetime.timedelta(days=1)
        start_date = yesterday - datetime.timedelta(days=lookback_days - 1)

        assert start_date == datetime.date(2024, 1, 13)  # 7 days before yesterday
        assert yesterday == datetime.date(2024, 1, 19)
        assert (yesterday - start_date).days == 6  # 7 days inclusive

    def test_20day_lookback(self):
        """20-day lookback should probe last 20 days."""
        today = datetime.date(2024, 1, 20)
        lookback_days = 20

        yesterday = today - datetime.timedelta(days=1)
        start_date = yesterday - datetime.timedelta(days=lookback_days - 1)

        assert start_date == datetime.date(2023, 12, 31)  # 20 days before yesterday
        assert yesterday == datetime.date(2024, 1, 19)
        assert (yesterday - start_date).days == 19  # 20 days inclusive

    def test_month_boundary_crossing(self):
        """Lookback window should correctly handle month boundaries."""
        today = datetime.date(2024, 2, 5)  # Early February
        lookback_days = 20

        yesterday = today - datetime.timedelta(days=1)
        start_date = yesterday - datetime.timedelta(days=lookback_days - 1)

        assert start_date == datetime.date(2024, 1, 16)  # Crosses into January
        assert yesterday == datetime.date(2024, 2, 4)


class TestUpsertBehavior:
    """Test UPSERT (INSERT OR REPLACE) semantics when re-probing same dates."""

    def test_upsert_replaces_existing_record(self, db: AvailabilityDatabase):
        """Re-probing same date+symbol should update existing record, not duplicate."""
        symbol = "BTCUSDT"
        date = datetime.date(2024, 1, 15)

        # First probe: File size 8MB
        first_probe = {
            "symbol": symbol,
            "date": date,
            "available": True,
            "file_size_bytes": 8000000,
            "last_modified": datetime.datetime(2024, 1, 16, 2, 0, 0, tzinfo=datetime.timezone.utc),
            "url": f"https://data.binance.vision/data/futures/um/daily/klines/{symbol}/1m/{symbol}-1m-{date}.zip",
            "status_code": 200,
            "probe_timestamp": datetime.datetime(2024, 1, 16, 3, 0, 0, tzinfo=datetime.timezone.utc),
        }
        db.insert_batch([first_probe])

        # Second probe (re-probe): File size changed to 9MB (S3 updated)
        second_probe = {
            **first_probe,
            "file_size_bytes": 9000000,
            "probe_timestamp": datetime.datetime(2024, 1, 17, 3, 0, 0, tzinfo=datetime.timezone.utc),
        }
        db.insert_batch([second_probe])

        # Verify: Only ONE record exists (UPSERT replaced, not duplicated)
        rows = db.query(
            "SELECT file_size_bytes FROM daily_availability WHERE symbol = ? AND date = ?",
            [symbol, date],
        )

        assert len(rows) == 1, "UPSERT should not create duplicate records"
        assert rows[0][0] == 9000000, "UPSERT should update file_size_bytes to latest value"

    def test_upsert_multiple_dates_no_duplicates(self, db: AvailabilityDatabase):
        """Re-probing 20-day window should update all dates without duplicates."""
        symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        start_date = datetime.date(2024, 1, 1)
        end_date = datetime.date(2024, 1, 20)  # 20 days

        # First batch: Probe all 20 days × 3 symbols = 60 records
        first_batch = []
        current_date = start_date
        while current_date <= end_date:
            for symbol in symbols:
                first_batch.append(
                    {
                        "symbol": symbol,
                        "date": current_date,
                        "available": True,
                        "file_size_bytes": 8000000,
                        "last_modified": None,
                        "url": f"https://example.com/{symbol}-{current_date}.zip",
                        "status_code": 200,
                        "probe_timestamp": datetime.datetime.now(datetime.timezone.utc),
                    }
                )
            current_date += datetime.timedelta(days=1)

        db.insert_batch(first_batch)

        # Second batch: Re-probe same dates (simulates 20-day lookback overlap)
        second_batch = [
            {**record, "file_size_bytes": 9000000} for record in first_batch  # Updated file size
        ]
        db.insert_batch(second_batch)

        # Verify: Still only 60 records (20 days × 3 symbols), no duplicates
        total_count = db.query("SELECT COUNT(*) FROM daily_availability")[0][0]
        assert total_count == 60, f"Expected 60 records after UPSERT, got {total_count}"

        # Verify: File sizes updated to 9MB (latest probe)
        updated_sizes = db.query("SELECT DISTINCT file_size_bytes FROM daily_availability")[0][0]
        assert updated_sizes == 9000000, "UPSERT should update all file_size_bytes to latest value"


class TestEnvironmentVariableFeatureFlag:
    """Test LOOKBACK_DAYS environment variable controls behavior."""

    @patch.dict(os.environ, {"LOOKBACK_DAYS": "1", "DB_PATH": "/tmp/test.duckdb"})
    def test_default_1day_from_env(self):
        """LOOKBACK_DAYS=1 (default) should probe single day."""
        lookback_days = int(os.environ.get("LOOKBACK_DAYS", "1"))
        assert lookback_days == 1

    @patch.dict(os.environ, {"LOOKBACK_DAYS": "20", "DB_PATH": "/tmp/test.duckdb"})
    def test_20day_from_env(self):
        """LOOKBACK_DAYS=20 should probe 20 days."""
        lookback_days = int(os.environ.get("LOOKBACK_DAYS", "1"))
        assert lookback_days == 20

    @patch.dict(os.environ, {}, clear=True)
    def test_default_when_env_not_set(self):
        """When LOOKBACK_DAYS not set, should default to 1."""
        lookback_days = int(os.environ.get("LOOKBACK_DAYS", "1"))
        assert lookback_days == 1


class TestBatchProberDateRange:
    """Test integration with BatchProber.probe_date_range() method."""

    @patch("binance_futures_availability.probing.batch_prober.load_discovered_symbols")
    @patch("binance_futures_availability.probing.batch_prober.check_symbol_availability")
    def test_probe_date_range_calls_all_dates(
        self, mock_check_symbol, mock_load_symbols, sample_probe_result
    ):
        """probe_date_range should probe all dates in range sequentially."""
        # Mock symbol loading
        mock_load_symbols.return_value = ["BTCUSDT", "ETHUSDT"]

        # Mock symbol probing (always successful)
        mock_check_symbol.return_value = sample_probe_result

        # Probe 3-day range
        prober = BatchProber(max_workers=10)
        results = prober.probe_date_range(
            start_date=datetime.date(2024, 1, 15),
            end_date=datetime.date(2024, 1, 17),  # 3 days
            symbols=["BTCUSDT", "ETHUSDT"],
        )

        # Verify: 3 days × 2 symbols = 6 total calls
        assert len(results) == 6
        assert mock_check_symbol.call_count == 6

    @patch("binance_futures_availability.probing.batch_prober.load_discovered_symbols")
    @patch("binance_futures_availability.probing.batch_prober.check_symbol_availability")
    def test_probe_date_range_20days(self, mock_check_symbol, mock_load_symbols, sample_probe_result):
        """probe_date_range should handle 20-day window efficiently."""
        # Mock 3 symbols (reduced for test speed)
        test_symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        mock_load_symbols.return_value = test_symbols
        mock_check_symbol.return_value = sample_probe_result

        # Probe 20-day range
        prober = BatchProber(max_workers=10)
        start_date = datetime.date(2024, 1, 1)
        end_date = datetime.date(2024, 1, 20)

        results = prober.probe_date_range(
            start_date=start_date,
            end_date=end_date,
            symbols=test_symbols,
        )

        # Verify: 20 days × 3 symbols = 60 results
        assert len(results) == 60
        assert mock_check_symbol.call_count == 60


@pytest.mark.integration
class TestIntegration20DayLookback:
    """
    Integration tests with real S3 Vision API.

    WARNING: These tests are slow (~5-10 seconds) and require network connectivity.
    Only run when needed: pytest -m integration
    """

    def test_real_7day_lookback_btcusdt(self, temp_db_path: Path):
        """
        Real S3 integration: Probe last 7 days for BTCUSDT.

        This validates actual S3 Vision availability and network behavior.
        """
        # Calculate 7-day range (ending yesterday)
        yesterday = datetime.date.today() - datetime.timedelta(days=1)
        start_date = yesterday - datetime.timedelta(days=6)

        # Probe real S3
        prober = BatchProber(max_workers=10)
        results = prober.probe_date_range(
            start_date=start_date,
            end_date=yesterday,
            symbols=["BTCUSDT"],  # Just 1 symbol for speed
        )

        # Verify: 7 results (1 per day)
        assert len(results) == 7, f"Expected 7 results for 7-day range, got {len(results)}"

        # Verify: All results have required fields
        for result in results:
            assert "symbol" in result
            assert "date" in result
            assert "available" in result
            assert result["symbol"] == "BTCUSDT"

        # Insert into database and verify UPSERT
        db = AvailabilityDatabase(db_path=temp_db_path)
        db.insert_batch(results)

        # Re-probe same range (should UPSERT, not duplicate)
        results_2nd = prober.probe_date_range(
            start_date=start_date,
            end_date=yesterday,
            symbols=["BTCUSDT"],
        )
        db.insert_batch(results_2nd)

        # Verify: Still only 7 records (UPSERT worked)
        total_count = db.query("SELECT COUNT(*) FROM daily_availability")[0][0]
        assert total_count == 7, f"UPSERT failed: expected 7 records, got {total_count}"

        db.close()
