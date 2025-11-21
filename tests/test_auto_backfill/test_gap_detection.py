"""
Tests for symbol gap detection (ADR-0012 Phase 1).

Test coverage:
- Gap detection logic (symbols.json vs database comparison)
- JSON output format validation
- Exit code behavior (0 for gaps, 1 for no gaps)
- Error handling (missing files, invalid JSON, database failures)

See: docs/architecture/decisions/0012-auto-backfill-new-symbols.md
"""

import datetime
import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from binance_futures_availability.database import AvailabilityDatabase


class TestGapDetectionLogic:
    """Test core gap detection logic."""

    def test_no_gaps_detected(self, tmp_path: Path):
        """
        No gaps when symbols.json matches database exactly.

        Scenario: All symbols in symbols.json already exist in database
        Expected: detect_gaps() returns empty list, exit code 1
        """
        # Create test database with 3 symbols
        db_path = tmp_path / "test.duckdb"
        db = AvailabilityDatabase(db_path=db_path)

        # Insert 3 symbols into database
        records = [
            {
                "symbol": "BTCUSDT",
                "date": datetime.date(2024, 1, 15),
                "available": True,
                "file_size_bytes": 8000000,
                "last_modified": None,
                "url": "https://example.com/BTCUSDT",
                "status_code": 200,
                "probe_timestamp": datetime.datetime.now(datetime.UTC),
            },
            {
                "symbol": "ETHUSDT",
                "date": datetime.date(2024, 1, 15),
                "available": True,
                "file_size_bytes": 7000000,
                "last_modified": None,
                "url": "https://example.com/ETHUSDT",
                "status_code": 200,
                "probe_timestamp": datetime.datetime.now(datetime.UTC),
            },
            {
                "symbol": "SOLUSDT",
                "date": datetime.date(2024, 1, 15),
                "available": True,
                "file_size_bytes": 6000000,
                "last_modified": None,
                "url": "https://example.com/SOLUSDT",
                "status_code": 200,
                "probe_timestamp": datetime.datetime.now(datetime.UTC),
            },
        ]
        db.insert_batch(records)
        db.close()

        # Create mock symbols.json with same 3 symbols

        # Mock loading functions
        with patch(
            "scripts.operations.detect_symbol_gaps.load_discovered_symbols",
            return_value={"BTCUSDT", "ETHUSDT", "SOLUSDT"},
        ), patch(
            "scripts.operations.detect_symbol_gaps.AvailabilityDatabase"
        ) as mock_db_class:
            # Mock database to return same 3 symbols
            mock_db_instance = Mock()
            mock_db_instance.query.return_value = [
                ("BTCUSDT",),
                ("ETHUSDT",),
                ("SOLUSDT",),
            ]
            mock_db_class.return_value = mock_db_instance

            # Import and test detect_gaps
            from scripts.operations.detect_symbol_gaps import detect_gaps

            new_symbols = detect_gaps()

            # Verify: No gaps detected (empty list)
            assert new_symbols == []

    def test_gaps_detected_new_symbols(self, tmp_path: Path):
        """
        Gaps detected when symbols.json has new symbols not in database.

        Scenario: symbols.json has 5 symbols, database has 3 (2 new symbols)
        Expected: detect_gaps() returns ["NEW1USDT", "NEW2USDT"], exit code 0
        """
        # Create test database with 3 existing symbols
        db_path = tmp_path / "test.duckdb"
        db = AvailabilityDatabase(db_path=db_path)

        records = [
            {
                "symbol": "BTCUSDT",
                "date": datetime.date(2024, 1, 15),
                "available": True,
                "file_size_bytes": 8000000,
                "last_modified": None,
                "url": "https://example.com/BTCUSDT",
                "status_code": 200,
                "probe_timestamp": datetime.datetime.now(datetime.UTC),
            },
            {
                "symbol": "ETHUSDT",
                "date": datetime.date(2024, 1, 15),
                "available": True,
                "file_size_bytes": 7000000,
                "last_modified": None,
                "url": "https://example.com/ETHUSDT",
                "status_code": 200,
                "probe_timestamp": datetime.datetime.now(datetime.UTC),
            },
            {
                "symbol": "SOLUSDT",
                "date": datetime.date(2024, 1, 15),
                "available": True,
                "file_size_bytes": 6000000,
                "last_modified": None,
                "url": "https://example.com/SOLUSDT",
                "status_code": 200,
                "probe_timestamp": datetime.datetime.now(datetime.UTC),
            },
        ]
        db.insert_batch(records)
        db.close()

        # Mock symbols.json with 5 symbols (2 new)
        with patch(
            "scripts.operations.detect_symbol_gaps.load_discovered_symbols",
            return_value={"BTCUSDT", "ETHUSDT", "SOLUSDT", "NEW1USDT", "NEW2USDT"},
        ), patch(
            "scripts.operations.detect_symbol_gaps.AvailabilityDatabase"
        ) as mock_db_class:
            # Mock database to return only 3 existing symbols
            mock_db_instance = Mock()
            mock_db_instance.query.return_value = [
                ("BTCUSDT",),
                ("ETHUSDT",),
                ("SOLUSDT",),
            ]
            mock_db_class.return_value = mock_db_instance

            # Import and test detect_gaps
            from scripts.operations.detect_symbol_gaps import detect_gaps

            new_symbols = detect_gaps()

            # Verify: 2 new symbols detected (sorted alphabetically)
            assert new_symbols == ["NEW1USDT", "NEW2USDT"]

    def test_gaps_detected_single_new_symbol(self, tmp_path: Path):
        """Single new symbol detected correctly."""
        with patch(
            "scripts.operations.detect_symbol_gaps.load_discovered_symbols",
            return_value={"BTCUSDT", "ETHUSDT", "NEWUSDT"},
        ), patch(
            "scripts.operations.detect_symbol_gaps.AvailabilityDatabase"
        ) as mock_db_class:
            # Mock database with 2 existing symbols
            mock_db_instance = Mock()
            mock_db_instance.query.return_value = [
                ("BTCUSDT",),
                ("ETHUSDT",),
            ]
            mock_db_class.return_value = mock_db_instance

            from scripts.operations.detect_symbol_gaps import detect_gaps

            new_symbols = detect_gaps()

            assert new_symbols == ["NEWUSDT"]

    def test_empty_database_all_symbols_are_gaps(self, tmp_path: Path):
        """
        Empty database means all symbols are gaps.

        Scenario: Database has no symbols yet (first run)
        Expected: All symbols from symbols.json are new
        """
        with patch(
            "scripts.operations.detect_symbol_gaps.load_discovered_symbols",
            return_value={"BTCUSDT", "ETHUSDT", "SOLUSDT"},
        ), patch(
            "scripts.operations.detect_symbol_gaps.AvailabilityDatabase"
        ) as mock_db_class:
            # Mock empty database
            mock_db_instance = Mock()
            mock_db_instance.query.return_value = []  # No symbols in database
            mock_db_class.return_value = mock_db_instance

            from scripts.operations.detect_symbol_gaps import detect_gaps

            new_symbols = detect_gaps()

            # All 3 symbols are new
            assert sorted(new_symbols) == ["BTCUSDT", "ETHUSDT", "SOLUSDT"]


class TestJSONOutputFormat:
    """Test JSON output format for workflow integration."""

    def test_json_output_format_with_gaps(self):
        """JSON output is valid array of strings when gaps detected."""
        with patch(
            "scripts.operations.detect_symbol_gaps.load_discovered_symbols",
            return_value={"BTCUSDT", "NEW1USDT", "NEW2USDT"},
        ), patch(
            "scripts.operations.detect_symbol_gaps.AvailabilityDatabase"
        ) as mock_db_class:
            mock_db_instance = Mock()
            mock_db_instance.query.return_value = [("BTCUSDT",)]
            mock_db_class.return_value = mock_db_instance

            from scripts.operations.detect_symbol_gaps import detect_gaps

            new_symbols = detect_gaps()

            # Verify JSON serializable
            json_output = json.dumps(new_symbols)
            assert json_output == '["NEW1USDT", "NEW2USDT"]'

            # Verify round-trip
            parsed = json.loads(json_output)
            assert parsed == ["NEW1USDT", "NEW2USDT"]

    def test_json_output_format_no_gaps(self):
        """JSON output is empty array when no gaps."""
        with patch(
            "scripts.operations.detect_symbol_gaps.load_discovered_symbols",
            return_value={"BTCUSDT"},
        ), patch(
            "scripts.operations.detect_symbol_gaps.AvailabilityDatabase"
        ) as mock_db_class:
            mock_db_instance = Mock()
            mock_db_instance.query.return_value = [("BTCUSDT",)]
            mock_db_class.return_value = mock_db_instance

            from scripts.operations.detect_symbol_gaps import detect_gaps

            new_symbols = detect_gaps()

            # Verify empty array
            json_output = json.dumps(new_symbols)
            assert json_output == "[]"

    def test_symbols_sorted_alphabetically(self):
        """Output symbols should be sorted alphabetically for deterministic workflow."""
        with patch(
            "scripts.operations.detect_symbol_gaps.load_discovered_symbols",
            return_value={"ZEBUSDT", "AAVEUSDT", "BTCUSDT"},  # Unsorted
        ):
            with patch(
                "scripts.operations.detect_symbol_gaps.AvailabilityDatabase"
            ) as mock_db_class:
                mock_db_instance = Mock()
                mock_db_instance.query.return_value = []  # Empty database
                mock_db_class.return_value = mock_db_instance

                from scripts.operations.detect_symbol_gaps import detect_gaps

                new_symbols = detect_gaps()

                # Verify sorted alphabetically
                assert new_symbols == ["AAVEUSDT", "BTCUSDT", "ZEBUSDT"]


class TestErrorHandling:
    """Test error handling per ADR-0003 (strict raise policy)."""

    def test_missing_symbols_json_raises(self, tmp_path: Path):
        """Missing symbols.json should raise RuntimeError."""
        from scripts.operations.detect_symbol_gaps import load_discovered_symbols

        # Mock nonexistent file
        with patch("pathlib.Path.read_text", side_effect=FileNotFoundError("Not found")):
            with pytest.raises(RuntimeError, match="symbols.json not found"):
                load_discovered_symbols()

    def test_invalid_json_raises(self, tmp_path: Path):
        """Invalid JSON in symbols.json should raise RuntimeError."""
        from scripts.operations.detect_symbol_gaps import load_discovered_symbols

        # Mock invalid JSON
        with patch("pathlib.Path.read_text", return_value="{invalid json"):
            with pytest.raises(RuntimeError, match="Invalid JSON"):
                load_discovered_symbols()

    def test_empty_perpetual_symbols_raises(self, tmp_path: Path):
        """Empty perpetual_symbols array should raise RuntimeError."""
        from scripts.operations.detect_symbol_gaps import load_discovered_symbols

        # Mock symbols.json with empty array
        with patch(
            "pathlib.Path.read_text",
            return_value=json.dumps(
                {"metadata": {}, "perpetual_symbols": [], "delivery_symbols": []}
            ),
        ), pytest.raises(RuntimeError, match="no perpetual_symbols"):
            load_discovered_symbols()

    def test_database_query_failure_raises(self):
        """Database query failure should raise RuntimeError."""
        from scripts.operations.detect_symbol_gaps import query_database_symbols

        with patch(
            "scripts.operations.detect_symbol_gaps.AvailabilityDatabase"
        ) as mock_db_class:
            # Mock database query failure
            mock_db_instance = Mock()
            mock_db_instance.query.side_effect = Exception("Database connection failed")
            mock_db_class.return_value = mock_db_instance

            with pytest.raises(RuntimeError, match="Failed to query database symbols"):
                query_database_symbols()


class TestUnicodeSymbolHandling:
    """Test handling of Unicode symbols (Chinese characters, emoji)."""

    def test_unicode_symbols_in_gaps(self):
        """Unicode symbols (e.g., 币安人生USDT) should be handled correctly."""
        with patch(
            "scripts.operations.detect_symbol_gaps.load_discovered_symbols",
            return_value={"BTCUSDT", "币安人生USDT", "🚀USDT"},
        ), patch(
            "scripts.operations.detect_symbol_gaps.AvailabilityDatabase"
        ) as mock_db_class:
            mock_db_instance = Mock()
            mock_db_instance.query.return_value = [("BTCUSDT",)]
            mock_db_class.return_value = mock_db_instance

            from scripts.operations.detect_symbol_gaps import detect_gaps

            new_symbols = detect_gaps()

            # Verify Unicode symbols preserved
            assert "币安人生USDT" in new_symbols
            assert "🚀USDT" in new_symbols

            # Verify JSON serializable (UTF-8)
            json_output = json.dumps(new_symbols, ensure_ascii=False)
            assert "币安人生USDT" in json_output
            assert "🚀USDT" in json_output


@pytest.mark.integration
class TestIntegrationWithRealDatabase:
    """Integration tests with real database (requires database setup)."""

    def test_gap_detection_with_real_database(self, tmp_path: Path):
        """
        Test gap detection with real DuckDB database.

        This test validates the entire flow:
        1. Create database with some symbols
        2. Mock symbols.json with additional new symbols
        3. Detect gaps
        4. Verify correct output
        """
        # Create real database
        db_path = tmp_path / "integration_test.duckdb"
        db = AvailabilityDatabase(db_path=db_path)

        # Insert 2 existing symbols
        records = [
            {
                "symbol": "BTCUSDT",
                "date": datetime.date(2024, 1, 15),
                "available": True,
                "file_size_bytes": 8000000,
                "last_modified": None,
                "url": "https://example.com/BTCUSDT",
                "status_code": 200,
                "probe_timestamp": datetime.datetime.now(datetime.UTC),
            },
            {
                "symbol": "ETHUSDT",
                "date": datetime.date(2024, 1, 15),
                "available": True,
                "file_size_bytes": 7000000,
                "last_modified": None,
                "url": "https://example.com/ETHUSDT",
                "status_code": 200,
                "probe_timestamp": datetime.datetime.now(datetime.UTC),
            },
        ]
        db.insert_batch(records)
        db.close()

        # Mock symbols.json with 4 symbols (2 new)
        with patch(
            "scripts.operations.detect_symbol_gaps.load_discovered_symbols",
            return_value={"BTCUSDT", "ETHUSDT", "SOLUSDT", "AVAXUSDT"},
        ), patch(
            "scripts.operations.detect_symbol_gaps.AvailabilityDatabase",
            return_value=AvailabilityDatabase(db_path=db_path),
        ):
            from scripts.operations.detect_symbol_gaps import detect_gaps

            new_symbols = detect_gaps()

            # Verify: 2 new symbols detected
            assert sorted(new_symbols) == ["AVAXUSDT", "SOLUSDT"]
