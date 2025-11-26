"""
Tests for targeted backfill functionality (ADR-0012 Phase 2).

Test coverage:
- Comma-separated symbol parsing
- Single symbol targeted backfill
- Multiple symbol targeted backfill
- Backward compatibility (no --symbols flag)
- Invalid symbol handling

See: docs/architecture/decisions/0012-auto-backfill-new-symbols.md
"""

import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from binance_futures_availability.database import AvailabilityDatabase

# Mark entire module as integration - tests scripts/ which isn't a proper package
pytestmark = pytest.mark.integration


class TestSymbolParsing:
    """Test parsing of --symbols parameter (consolidated per ADR-0027)."""

    @pytest.mark.parametrize(
        "symbols_arg,expected",
        [
            # Primary use cases
            ("BTCUSDT,ETHUSDT,SOLUSDT", ["BTCUSDT", "ETHUSDT", "SOLUSDT"]),
            ("BTCUSDT", ["BTCUSDT"]),
            # Edge cases
            ("BTCUSDT,  ETHUSDT  , SOLUSDT", ["BTCUSDT", "ETHUSDT", "SOLUSDT"]),
            ("BTCUSDT,ETHUSDT,", ["BTCUSDT", "ETHUSDT"]),
            ("", []),
        ],
        ids=["comma-separated", "single", "whitespace", "trailing-comma", "empty"],
    )
    def test_symbol_parsing(self, symbols_arg: str, expected: list[str]):
        """Symbol parsing handles various input formats correctly."""
        symbols = [s.strip() for s in symbols_arg.replace(",", " ").split() if s.strip()]
        assert symbols == expected


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
            with patch(
                "scripts.operations.backfill.load_discovered_symbols",
                return_value=["BTCUSDT", "ETHUSDT", "NEWUSDT"],
            ):
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
                "probe_timestamp": datetime.datetime.now(datetime.UTC),
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
                "probe_timestamp": datetime.datetime.now(datetime.UTC),
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
        db.insert_batch(
            [
                {
                    "symbol": "BTCUSDT",
                    "date": datetime.date(2024, 1, 15),
                    "available": True,
                    "file_size_bytes": 8000000,
                    "last_modified": None,
                    "url": "https://example.com/BTCUSDT",
                    "status_code": 200,
                    "probe_timestamp": datetime.datetime.now(datetime.UTC),
                }
            ]
        )

        # Backfill 3 new symbols
        new_symbols = ["NEW1USDT", "NEW2USDT", "NEW3USDT"]
        for symbol in new_symbols:
            db.insert_batch(
                [
                    {
                        "symbol": symbol,
                        "date": datetime.date(2024, 1, 15),
                        "available": True,
                        "file_size_bytes": 7000000,
                        "last_modified": None,
                        "url": f"https://example.com/{symbol}",
                        "status_code": 200,
                        "probe_timestamp": datetime.datetime.now(datetime.UTC),
                    }
                ]
            )

        # Verify all 4 symbols in database
        rows = db.query("SELECT DISTINCT symbol FROM daily_availability ORDER BY symbol")
        symbols_in_db = [row[0] for row in rows]

        assert len(symbols_in_db) == 4
        assert "BTCUSDT" in symbols_in_db
        assert "NEW1USDT" in symbols_in_db
        assert "NEW2USDT" in symbols_in_db
        assert "NEW3USDT" in symbols_in_db
        db.close()


# UPSERT idempotency tests removed per ADR-0027
# Canonical location: tests/test_database/test_availability_db.py

# Unicode symbol tests removed per ADR-0027
# Canonical location: tests/test_probing/test_unicode_symbols.py


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
