"""S3 Vision file existence probing via HTTP HEAD requests.

Copied and adapted from: scratch/vision-futures-explorer/historical_probe.py
See: docs/architecture/decisions/0003-error-handling-strict-policy.md
See: docs/architecture/decisions/0019-performance-optimization-strategy.md (HTTP pooling)
"""

import datetime
import urllib.parse
from typing import TypedDict

import urllib3  # ADR-0019: HTTP connection pooling

# ADR-0019: Global HTTP connection pool (reuses SSL/TLS connections)
# Default pool size: 10 connections, sufficient for parallel probing
HTTP_POOL = urllib3.PoolManager(
    num_pools=1,  # Single pool for all requests
    maxsize=10,   # Max connections per pool
    timeout=urllib3.Timeout(connect=5.0, read=10.0),  # Connect + read timeouts
    retries=False,  # ADR-0003: No automatic retries
)


class ProbeResult(TypedDict):
    """Result of probing a single symbol on a specific date."""

    symbol: str
    date: datetime.date
    available: bool
    file_size_bytes: int | None
    last_modified: datetime.datetime | None
    url: str
    status_code: int
    probe_timestamp: datetime.datetime


def check_symbol_availability(
    symbol: str, date: datetime.date, timeout: int = 10
) -> ProbeResult:
    """
    Check if a symbol's 1m klines file exists on Binance Vision S3.

    Uses HTTP HEAD request to check file existence without downloading.

    Args:
        symbol: Futures symbol (e.g., BTCUSDT)
        date: Trading date to check (UTC)
        timeout: Request timeout in seconds (default: 10)

    Returns:
        ProbeResult with availability status and metadata

    Raises:
        RuntimeError: On any network or HTTP error (ADR-0003: NO RETRY)

    Example:
        >>> result = check_symbol_availability('BTCUSDT', datetime.date(2024, 1, 15))
        >>> result['available']
        True
        >>> result['file_size_bytes']
        8421945

    URL Pattern:
        https://data.binance.vision/data/futures/um/daily/klines/{symbol}/1m/{symbol}-1m-{YYYY-MM-DD}.zip
    """
    # Construct S3 Vision URL (with proper URL encoding for Unicode symbols)
    date_str = date.strftime("%Y-%m-%d")
    # URL-encode symbol to handle non-ASCII characters (e.g., 币安人生USDT)
    # safe='' ensures all non-ASCII chars are percent-encoded
    encoded_symbol = urllib.parse.quote(symbol, safe='')
    url = (
        f"https://data.binance.vision/data/futures/um/daily/klines/"
        f"{encoded_symbol}/1m/{encoded_symbol}-1m-{date_str}.zip"
    )

    probe_timestamp = datetime.datetime.now(datetime.timezone.utc)

    try:
        # ADR-0019: Use connection pool for HTTP HEAD request
        response = HTTP_POOL.request("HEAD", url, timeout=timeout)

        if response.status == 200:
            # File exists (200 OK)
            file_size = int(response.headers.get("Content-Length", 0))
            last_modified_str = response.headers.get("Last-Modified")

            # Parse Last-Modified header (RFC 2822 format)
            last_modified = None
            if last_modified_str:
                try:
                    from email.utils import parsedate_to_datetime

                    last_modified = parsedate_to_datetime(last_modified_str)
                except Exception:
                    pass  # Skip parsing errors

            return ProbeResult(
                symbol=symbol,
                date=date,
                available=True,
                file_size_bytes=file_size,
                last_modified=last_modified,
                url=url,
                status_code=200,
                probe_timestamp=probe_timestamp,
            )

        elif response.status == 404:
            # File not found (symbol not available on this date)
            return ProbeResult(
                symbol=symbol,
                date=date,
                available=False,
                file_size_bytes=None,
                last_modified=None,
                url=url,
                status_code=404,
                probe_timestamp=probe_timestamp,
            )

        else:
            # Other HTTP errors (403, 500, etc.) - raise immediately (ADR-0003)
            raise RuntimeError(
                f"S3 probe failed for {symbol} on {date}: HTTP {response.status}"
            )

    except urllib3.exceptions.TimeoutError as e:
        # Timeout - raise immediately (ADR-0003)
        raise RuntimeError(f"Timeout probing {symbol} on {date}: {e}") from e

    except urllib3.exceptions.HTTPError as e:
        # Network error (DNS failure, connection error, etc.) - raise immediately (ADR-0003)
        raise RuntimeError(f"Network error probing {symbol} on {date}: {e}") from e

    except Exception as e:
        # Unexpected error - raise immediately (ADR-0003)
        raise RuntimeError(f"Unexpected error probing {symbol} on {date}: {e}") from e
