"""Tests for S3 Vision probing.

Unit tests: Mock urllib responses (fast)
Integration tests: Real S3 Vision API (slow, marked with @pytest.mark.integration)
"""

import datetime

import pytest

from binance_futures_availability.probing.s3_vision import check_symbol_availability


def test_check_symbol_availability_success(mock_urlopen_success):
    """Test successful probe (200 OK)."""
    result = check_symbol_availability("BTCUSDT", datetime.date(2024, 1, 15))

    assert result["symbol"] == "BTCUSDT"
    assert result["date"] == datetime.date(2024, 1, 15)
    assert result["available"] is True
    assert result["status_code"] == 200
    assert result["file_size_bytes"] == 8421945
    assert result["url"].endswith("BTCUSDT-1m-2024-01-15.zip")


def test_check_symbol_availability_404(mock_urlopen_404):
    """Test unavailable symbol (404 Not Found)."""
    result = check_symbol_availability("NEWCOINUSDT", datetime.date(2024, 1, 15))

    assert result["symbol"] == "NEWCOINUSDT"
    assert result["available"] is False
    assert result["status_code"] == 404
    assert result["file_size_bytes"] is None
    assert result["last_modified"] is None


def test_check_symbol_availability_network_error(mock_urlopen_network_error):
    """Test network error raises RuntimeError (ADR-0003: strict policy)."""
    with pytest.raises(RuntimeError, match="Network error"):
        check_symbol_availability("BTCUSDT", datetime.date(2024, 1, 15))


@pytest.mark.integration
def test_check_symbol_availability_live_btcusdt():
    """Integration test: Probe BTCUSDT on 2024-01-15 (known available)."""
    result = check_symbol_availability("BTCUSDT", datetime.date(2024, 1, 15))

    assert result["available"] is True
    assert result["status_code"] == 200
    assert result["file_size_bytes"] > 0


@pytest.mark.integration
def test_check_symbol_availability_live_unavailable():
    """Integration test: Probe symbol on date before it was listed."""
    # SOLUSDT was not available on 2019-09-25 (first UM-futures day)
    result = check_symbol_availability("SOLUSDT", datetime.date(2019, 9, 25))

    assert result["available"] is False
    assert result["status_code"] == 404
