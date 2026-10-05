"""
Tests for Unicode symbol handling in S3 probing.

Test coverage:
- Chinese characters (币安人生USDT)
- Emoji and special Unicode characters
- URL encoding verification
- HTTP request handling with non-ASCII symbols

See: https://github.com/terrylica/binance-futures-availability/actions/runs/19418274775
Root cause: ASCII encoding error for newly discovered Chinese symbol
"""

import datetime
from unittest.mock import Mock, patch

import pytest
import urllib3

from binance_futures_availability.probing import s3_vision
from binance_futures_availability.probing.s3_vision import check_symbol_availability

POOL_REQUEST = (s3_vision.HTTP_POOL, "request")


class TestUnicodeSymbolHandling:
    """Test probing symbols with non-ASCII characters."""

    def test_chinese_symbol_url_encoding(self):
        """Chinese characters in symbol names should be properly URL-encoded."""
        symbol = "币安人生USDT"
        date = datetime.date(2024, 1, 15)

        # Mock successful response
        mock_response = Mock()
        mock_response.status = 200
        mock_response.headers = {
            "Content-Length": "8000000",
            "Last-Modified": "Mon, 15 Jan 2024 02:00:00 GMT",
        }

        with patch.object(*POOL_REQUEST, return_value=mock_response) as mock_request:
            result = check_symbol_availability(symbol, date)

            # Verify result contains original symbol (not encoded)
            assert result["symbol"] == "币安人生USDT"
            assert result["available"] is True

            # Verify URL was properly percent-encoded
            expected_encoded = "%E5%B8%81%E5%AE%89%E4%BA%BA%E7%94%9FUSDT"
            assert expected_encoded in result["url"]

            # Verify the request was made (encoding worked, no ASCII error)
            assert mock_request.called

    def test_emoji_symbol_url_encoding(self):
        """Emoji characters in symbol names should be properly URL-encoded."""
        symbol = "🚀USDT"
        date = datetime.date(2024, 1, 15)

        mock_response = Mock()
        mock_response.status = 200
        mock_response.headers = {"Content-Length": "8000000"}

        with patch.object(*POOL_REQUEST, return_value=mock_response):
            result = check_symbol_availability(symbol, date)

            assert result["symbol"] == "🚀USDT"
            assert result["available"] is True
            # Emoji rocket: U+1F680 → %F0%9F%9A%80
            assert "%F0%9F%9A%80" in result["url"]

    def test_mixed_unicode_symbol(self):
        """Symbols with mixed ASCII and Unicode should encode only non-ASCII parts."""
        symbol = "TEST币安USDT"
        date = datetime.date(2024, 1, 15)

        mock_response = Mock()
        mock_response.status = 200
        mock_response.headers = {"Content-Length": "8000000"}

        with patch.object(*POOL_REQUEST, return_value=mock_response):
            result = check_symbol_availability(symbol, date)

            assert result["symbol"] == "TEST币安USDT"
            # ASCII parts stay as-is, Unicode parts encoded
            assert "TEST" in result["url"]
            assert "USDT" in result["url"]
            assert "%E5%B8%81%E5%AE%89" in result["url"]  # 币安 encoded

    def test_ascii_symbol_unchanged(self):
        """Regular ASCII symbols should work without encoding changes."""
        symbol = "BTCUSDT"
        date = datetime.date(2024, 1, 15)

        mock_response = Mock()
        mock_response.status = 200
        mock_response.headers = {"Content-Length": "8000000"}

        with patch.object(*POOL_REQUEST, return_value=mock_response):
            result = check_symbol_availability(symbol, date)

            assert result["symbol"] == "BTCUSDT"
            # ASCII symbols remain unchanged in URL
            assert "BTCUSDT" in result["url"]
            assert "%" not in result["url"]  # No percent-encoding for ASCII

    def test_unicode_symbol_404_handling(self):
        """404 responses should work correctly for Unicode symbols."""
        symbol = "币安人生USDT"
        date = datetime.date(2024, 1, 15)

        with patch.object(*POOL_REQUEST, return_value=Mock(status=404, headers={})):
            result = check_symbol_availability(symbol, date)

            assert result["symbol"] == "币安人生USDT"
            assert result["available"] is False
            assert result["status_code"] == 404
            assert result["file_size_bytes"] is None

    def test_unicode_symbol_network_error_raises(self):
        """Network errors should raise for Unicode symbols (ADR-0003: strict policy)."""
        symbol = "币安人生USDT"
        date = datetime.date(2024, 1, 15)

        with patch.object(
            *POOL_REQUEST, side_effect=urllib3.exceptions.HTTPError("Network timeout")
        ):
            with pytest.raises(RuntimeError, match="Network error probing 币安人生USDT"):
                check_symbol_availability(symbol, date)


@pytest.mark.integration
class TestUnicodeIntegration:
    """
    Integration tests with real S3 (if Chinese symbols actually exist).

    WARNING: These tests hit real S3 Vision API and may fail if symbols don't exist.
    """

    def test_real_chinese_symbol_probe(self):
        """
        Attempt to probe real Chinese symbol if it exists on S3.

        This test may fail if the symbol doesn't have historical data,
        but it validates that the URL encoding works with real S3.
        """
        symbol = "币安人生USDT"
        yesterday = datetime.date.today() - datetime.timedelta(days=1)

        # This will either:
        # 1. Return available=True if file exists
        # 2. Return available=False if 404
        # 3. Raise RuntimeError for other errors
        #
        # All outcomes validate that Unicode encoding works (no ASCII error)
        try:
            result = check_symbol_availability(symbol, yesterday)
            # If we got here, encoding worked (no ASCII codec error)
            assert result["symbol"] == "币安人生USDT"
            assert "available" in result
            # URL should be percent-encoded
            assert "%" in result["url"]
        except RuntimeError as e:
            # If it raised, should NOT be ASCII encoding error
            assert "ascii" not in str(e).lower()
            assert "encode" not in str(e).lower()
