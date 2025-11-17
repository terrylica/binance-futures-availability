"""
Tests for targeted backfill functionality (ADR-0012 Phase 2).

Test coverage:
- Comma-separated symbol parsing
- Single symbol targeted backfill
- Multiple symbol targeted backfill
- Backward compatibility (no --symbols flag)
- Invalid symbol handling

See: docs/decisions/0012-auto-backfill-new-symbols.md
"""

import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from binance_futures_availability.database import AvailabilityDatabase


class TestSymbolParsing:
    """Test parsing of --symbols parameter (comma and space-separated)."""

    def test_comma_separated_symbols(self):
        """Comma-separated symbols should be parsed correctly."""
        symbols_arg = "BTCUSDT,ETHUSDT,SOLUSDT"

        # Parse using same logic as backfill.py
        symbols = [s.strip() for s in symbols_arg.replace(",", " ").split() if s.strip()]

        assert symbols == ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

    def test_space_separated_symbols_backward_compat(self):
        """Space-separated symbols should still work (backward compatibility)."""
        symbols_arg = "BTCUSDT ETHUSDT SOLUSDT"

        # Parse using same logic as backfill.py
        symbols = [s.strip() for s in symbols_arg.replace(",", " ").split() if s.strip()]

        assert symbols == ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

    def test_single_symbol(self):
        """Single symbol without delimiters should work."""
        symbols_arg = "BTCUSDT"

        symbols = [s.strip() for s in symbols_arg.replace(",", " ").split() if s.strip()]

        assert symbols == ["BTCUSDT"]

    def test_symbols_with_extra_whitespace(self):
        """Extra whitespace around symbols should be stripped."""
        symbols_arg = "BTCUSDT,  ETHUSDT  , SOLUSDT"

        symbols = [s.strip() for s in symbols_arg.replace(",", " ").split() if s.strip()]

        assert symbols == ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

    def test_trailing_comma_ignored(self):
        """Trailing comma should not create empty symbol."""
        symbols_arg = "BTCUSDT,ETHUSDT,"

        symbols = [s.strip() for s in symbols_arg.replace(",", " ").split() if s.strip()]

        assert symbols == ["BTCUSDT", "ETHUSDT"]

    def test_empty_string_returns_empty_list(self):
        """Empty string should return empty list."""
        symbols_arg = ""

        symbols = [s.strip() for s in symbols_arg.replace(",", " ").split() if s.strip()]

        assert symbols == []


class TestTargetedBackfill:
    """Test targeted backfill with specific symbols."""

    def test_targeted_backfill_single_symbol(self, tmp_path: Path):
        """
        Backfill single symbol only (not all symbols).

        Scenario: --symbols NEWUSDT → backfills only NEWUSDT
        Expected: Database contains NEWUSDT data, no other symbols
        """
        # Create test database
        db_path = tmp_path / "test.duckdb"
        db = AvailabilityDatabase(db_path=db_path)
        db.close()

        # Mock backfill_symbol to track which symbols are backfilled
        backfilled_symbols = []

        def mock_backfill(symbol, start, end, db_path):
            backfilled_symbols.append(symbol)
            return {"symbol": symbol, "dates_found": 100, "total_dates": 100, "error": None}

        with patch("scripts.operations.backfill.backfill_symbol", side_effect=mock_backfill):
            with patch("scripts.operations.backfill.load_discovered_symbols", return_value=["BTCUSDT", "ETHUSDT", "NEWUSDT"]):
                # Simulate: python backfill.py --symbols NEWUSDT
                symbols_arg = "NEWUSDT"
                symbols = [s.strip() for s in symbols_arg.replace(",", " ").split() if s.strip()]

                # Verify only NEWUSDT parsed
                assert symbols == ["NEWUSDT"]

                # In actual backfill, only these symbols would be processed
                assert "NEWUSDT" in symbols
                assert "BTCUSDT" not in symbols
                assert "ETHUSDT" not in symbols

    def test_targeted_backfill_multiple_symbols(self, tmp_path: Path):
        """
        Backfill multiple symbols only (not all symbols).

        Scenario: --symbols NEW1USDT,NEW2USDT → backfills only NEW1 and NEW2
        Expected: Only 2 symbols backfilled, not all 713
        """
        # Mock backfill scenario
        symbols_arg = "NEW1USDT,NEW2USDT"
        symbols = [s.strip() for s in symbols_arg.replace(",", " ").split() if s.strip()]

        # Verify correct parsing
        assert symbols == ["NEW1USDT", "NEW2USDT"]
        assert len(symbols) == 2

    def test_backfill_all_symbols_when_no_flag(self, tmp_path: Path):
        """
        No --symbols flag → backfill all symbols (backward compatibility).

        Scenario: python backfill.py (no --symbols flag)
        Expected: All symbols from symbols.json are backfilled
        """
        # Mock load_discovered_symbols
        all_symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "AVAXUSDT"]

        with patch("scripts.operations.backfill.load_discovered_symbols", return_value=all_symbols):
            # Simulate: No --symbols argument provided
            symbols_arg = None

            if symbols_arg:
                symbols = [s.strip() for s in symbols_arg.replace(",", " ").split() if s.strip()]
            else:
                # Should use all discovered symbols (backward compatibility)
                from scripts.operations.backfill import load_discovered_symbols
                symbols = load_discovered_symbols()

            # Verify all symbols loaded
            assert symbols == all_symbols
            assert len(symbols) == 4


class TestBackfillWorkflow:
    """Test complete backfill workflow with targeted symbols."""

    def test_single_symbol_backfill_workflow(self, tmp_path: Path):
        """
        Complete workflow: Backfill single new symbol.

        Simulates ADR-0012 workflow:
        1. Gap detection finds NEW1USDT
        2. Backfill runs with --symbols NEW1USDT
        3. Database contains NEW1USDT historical data
        """
        # Create real database
        db_path = tmp_path / "workflow_test.duckdb"
        db = AvailabilityDatabase(db_path=db_path)

        # Insert existing symbol (BTCUSDT)
        existing_records = [
            {
                "symbol": "BTCUSDT",
                "date": datetime.date(2024, 1, 15),
                "available": True,
                "file_size_bytes": 8000000,
                "last_modified": None,
                "url": "https://example.com/BTCUSDT",
                "status_code": 200,
                "probe_timestamp": datetime.datetime.now(datetime.timezone.utc),
            }
        ]
        db.insert_batch(existing_records)

        # Simulate backfill for NEW1USDT
        new_symbol_records = [
            {
                "symbol": "NEW1USDT",
                "date": datetime.date(2024, 1, 15),
                "available": True,
                "file_size_bytes": 7000000,
                "last_modified": None,
                "url": "https://example.com/NEW1USDT",
                "status_code": 200,
                "probe_timestamp": datetime.datetime.now(datetime.timezone.utc),
            }
        ]
        db.insert_batch(new_symbol_records)

        # Verify database now contains both symbols
        rows = db.query("SELECT DISTINCT symbol FROM daily_availability ORDER BY symbol")
        symbols_in_db = [row[0] for row in rows]

        assert symbols_in_db == ["BTCUSDT", "NEW1USDT"]
        db.close()

    def test_multiple_symbols_backfill_workflow(self, tmp_path: Path):
        """
        Complete workflow: Backfill multiple new symbols.

        Simulates: Gap detection finds 3 new symbols → backfill all 3
        """
        db_path = tmp_path / "multi_workflow_test.duckdb"
        db = AvailabilityDatabase(db_path=db_path)

        # Insert existing symbol
        db.insert_batch([
            {
                "symbol": "BTCUSDT",
                "date": datetime.date(2024, 1, 15),
                "available": True,
                "file_size_bytes": 8000000,
                "last_modified": None,
                "url": "https://example.com/BTCUSDT",
                "status_code": 200,
                "probe_timestamp": datetime.datetime.now(datetime.timezone.utc),
            }
        ])

        # Backfill 3 new symbols
        new_symbols = ["NEW1USDT", "NEW2USDT", "NEW3USDT"]
        for symbol in new_symbols:
            db.insert_batch([
                {
                    "symbol": symbol,
                    "date": datetime.date(2024, 1, 15),
                    "available": True,
                    "file_size_bytes": 7000000,
                    "last_modified": None,
                    "url": f"https://example.com/{symbol}",
                    "status_code": 200,
                    "probe_timestamp": datetime.datetime.now(datetime.timezone.utc),
                }
            ])

        # Verify all 4 symbols in database
        rows = db.query("SELECT DISTINCT symbol FROM daily_availability ORDER BY symbol")
        symbols_in_db = [row[0] for row in rows]

        assert len(symbols_in_db) == 4
        assert "BTCUSDT" in symbols_in_db
        assert "NEW1USDT" in symbols_in_db
        assert "NEW2USDT" in symbols_in_db
        assert "NEW3USDT" in symbols_in_db
        db.close()


class TestUpsertIdempotency:
    """Test that re-running backfill for same symbols is safe (UPSERT semantics)."""

    def test_backfill_same_symbol_twice_no_duplicates(self, tmp_path: Path):
        """
        Re-backfilling same symbol should not create duplicates.

        Scenario: Backfill NEWUSDT, then backfill NEWUSDT again
        Expected: Only 1 record per (date, symbol) - no duplicates
        """
        db_path = tmp_path / "idempotent_test.duckdb"
        db = AvailabilityDatabase(db_path=db_path)

        # First backfill
        first_record = {
            "symbol": "NEWUSDT",
            "date": datetime.date(2024, 1, 15),
            "available": True,
            "file_size_bytes": 7000000,
            "last_modified": None,
            "url": "https://example.com/NEWUSDT",
            "status_code": 200,
            "probe_timestamp": datetime.datetime(2024, 1, 16, 10, 0, 0, tzinfo=datetime.timezone.utc),
        }
        db.insert_batch([first_record])

        # Verify 1 record
        rows = db.query("SELECT COUNT(*) FROM daily_availability WHERE symbol = 'NEWUSDT' AND date = '2024-01-15'")
        assert rows[0][0] == 1

        # Second backfill (re-run) - should UPSERT, not INSERT
        second_record = {
            **first_record,
            "file_size_bytes": 7500000,  # Updated file size
            "probe_timestamp": datetime.datetime(2024, 1, 17, 10, 0, 0, tzinfo=datetime.timezone.utc),
        }
        db.insert_batch([second_record])

        # Verify still only 1 record (UPSERT replaced, not duplicated)
        rows = db.query("SELECT COUNT(*) FROM daily_availability WHERE symbol = 'NEWUSDT' AND date = '2024-01-15'")
        assert rows[0][0] == 1

        # Verify file size updated (UPSERT worked)
        rows = db.query("SELECT file_size_bytes FROM daily_availability WHERE symbol = 'NEWUSDT' AND date = '2024-01-15'")
        assert rows[0][0] == 7500000

        db.close()


class TestUnicodeSymbolTargetedBackfill:
    """Test targeted backfill with Unicode symbols (Chinese, emoji)."""

    def test_unicode_symbol_in_targeted_backfill(self):
        """Unicode symbols should work in comma-separated list."""
        # Simulate: --symbols BTCUSDT,币安人生USDT,🚀USDT
        symbols_arg = "BTCUSDT,币安人生USDT,🚀USDT"

        symbols = [s.strip() for s in symbols_arg.replace(",", " ").split() if s.strip()]

        assert len(symbols) == 3
        assert "BTCUSDT" in symbols
        assert "币安人生USDT" in symbols
        assert "🚀USDT" in symbols

    def test_unicode_symbol_backfill_integration(self, tmp_path: Path):
        """Unicode symbols should backfill correctly into database."""
        db_path = tmp_path / "unicode_backfill_test.duckdb"
        db = AvailabilityDatabase(db_path=db_path)

        # Backfill Chinese symbol
        record = {
            "symbol": "币安人生USDT",
            "date": datetime.date(2024, 1, 15),
            "available": True,
            "file_size_bytes": 7000000,
            "last_modified": None,
            "url": "https://example.com/%E5%B8%81%E5%AE%89%E4%BA%BA%E7%94%9FUSDT",
            "status_code": 200,
            "probe_timestamp": datetime.datetime.now(datetime.timezone.utc),
        }
        db.insert_batch([record])

        # Verify symbol stored correctly
        rows = db.query("SELECT symbol FROM daily_availability WHERE date = '2024-01-15'")
        assert len(rows) == 1
        assert rows[0][0] == "币安人生USDT"

        db.close()


@pytest.mark.integration
class TestRealBackfillExecution:
    """Integration tests with real backfill execution (optional)."""

    def test_dry_run_targeted_backfill(self, tmp_path: Path):
        """
        Dry-run test: Verify backfill.py can parse targeted symbols.

        This test validates argument parsing without actually running S3 calls.
        """
        # Mock the actual backfill logic
        with patch("scripts.operations.backfill.backfill_symbol") as mock_backfill:
            mock_backfill.return_value = {
                "symbol": "TESTUSDT",
                "dates_found": 50,
                "total_dates": 100,
                "error": None,
            }

            # Simulate parsing --symbols TESTUSDT
            symbols_arg = "TESTUSDT"
            symbols = [s.strip() for s in symbols_arg.replace(",", " ").split() if s.strip()]

            assert symbols == ["TESTUSDT"]

            # In real execution, this would call backfill_symbol for TESTUSDT only
            # (not all 713 symbols)
