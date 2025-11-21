"""Pytest fixtures and configuration for binance-futures-availability tests.

Test organization:
    - Unit tests: Fast, no network, mock S3 responses
    - Integration tests: Slow, require network, marked with @pytest.mark.integration

Coverage target: 80%+ (pyproject.toml: --cov-fail-under=80)
"""

import datetime
import tempfile
from pathlib import Path
from typing import Any

import pytest

from binance_futures_availability.database.availability_db import AvailabilityDatabase


@pytest.fixture
def temp_db_path() -> Path:
    """
    Create temporary database path for tests.

    Returns:
        Path to temporary .duckdb file (file not created, only path)
    """
    temp_dir = Path(tempfile.gettempdir())
    return temp_dir / f"test_{tempfile.mktemp(suffix='.duckdb').split('/')[-1]}"


@pytest.fixture
def db(temp_db_path: Path) -> AvailabilityDatabase:
    """
    Create test database instance with schema.

    Returns:
        AvailabilityDatabase instance with temp database
    """
    return AvailabilityDatabase(db_path=temp_db_path)


@pytest.fixture
def sample_probe_result() -> dict[str, Any]:
    """
    Sample probe result for testing.

    Returns:
        Dict matching ProbeResult TypedDict structure
    """
    return {
        "symbol": "BTCUSDT",
        "date": datetime.date(2024, 1, 15),
        "available": True,
        "file_size_bytes": 8421945,
        "last_modified": datetime.datetime(2024, 1, 16, 2, 15, 32, tzinfo=datetime.UTC),
        "url": "https://data.binance.vision/data/futures/um/daily/klines/BTCUSDT/1m/BTCUSDT-1m-2024-01-15.zip",
        "status_code": 200,
        "probe_timestamp": datetime.datetime(2024, 1, 16, 2, 0, 0, tzinfo=datetime.UTC),
    }


@pytest.fixture
def sample_unavailable_result() -> dict[str, Any]:
    """
    Sample unavailable probe result (404).

    Returns:
        Dict for unavailable symbol
    """
    return {
        "symbol": "NEWCOINUSDT",
        "date": datetime.date(2024, 1, 15),
        "available": False,
        "file_size_bytes": None,
        "last_modified": None,
        "url": "https://data.binance.vision/data/futures/um/daily/klines/NEWCOINUSDT/1m/NEWCOINUSDT-1m-2024-01-15.zip",
        "status_code": 404,
        "probe_timestamp": datetime.datetime(2024, 1, 16, 2, 0, 0, tzinfo=datetime.UTC),
    }


@pytest.fixture
def populated_db(db: AvailabilityDatabase) -> AvailabilityDatabase:
    """
    Database pre-populated with test data.

    Inserts 3 days × 3 symbols = 9 records:
        - 2024-01-15: BTCUSDT, ETHUSDT, SOLUSDT
        - 2024-01-16: BTCUSDT, ETHUSDT, SOLUSDT
        - 2024-01-17: BTCUSDT, ETHUSDT, SOLUSDT

    Returns:
        Populated AvailabilityDatabase instance
    """
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    dates = [
        datetime.date(2024, 1, 15),
        datetime.date(2024, 1, 16),
        datetime.date(2024, 1, 17),
    ]

    records = []
    for date in dates:
        for symbol in symbols:
            records.append(
                {
                    "symbol": symbol,
                    "date": date,
                    "available": True,
                    "file_size_bytes": 8000000 + len(symbol),
                    "last_modified": datetime.datetime(
                        date.year, date.month, date.day + 1, 2, 0, 0, tzinfo=datetime.UTC
                    ),
                    "url": f"https://data.binance.vision/data/futures/um/daily/klines/{symbol}/1m/{symbol}-1m-{date}.zip",
                    "status_code": 200,
                    "probe_timestamp": datetime.datetime.now(datetime.UTC),
                }
            )

    db.insert_batch(records)
    return db


@pytest.fixture
def mock_urlopen_success(mocker):
    """
    Mock urllib3.PoolManager.request for successful S3 HEAD request (200 OK).

    ADR-0019: Updated to mock urllib3 connection pooling

    Returns:
        Mock object with status=200, headers
    """
    mock_response = mocker.MagicMock()
    mock_response.status = 200
    mock_response.headers = {
        "Content-Length": "8421945",
        "Last-Modified": "Wed, 16 Jan 2024 02:15:32 GMT",
    }

    # Mock urllib3.PoolManager.request() method
    return mocker.patch(
        "binance_futures_availability.probing.s3_vision.HTTP_POOL.request",
        return_value=mock_response
    )


@pytest.fixture
def mock_urlopen_404(mocker):
    """
    Mock urllib3.PoolManager.request for 404 Not Found.

    ADR-0019: Updated to mock urllib3 connection pooling

    Returns:
        Mock that returns response with status=404
    """
    mock_response = mocker.MagicMock()
    mock_response.status = 404
    mock_response.headers = {}

    # Mock urllib3.PoolManager.request() to return 404 response
    return mocker.patch(
        "binance_futures_availability.probing.s3_vision.HTTP_POOL.request",
        return_value=mock_response
    )


@pytest.fixture
def mock_urlopen_network_error(mocker):
    """
    Mock urllib3.PoolManager.request for network error.

    ADR-0019: Updated to mock urllib3 connection pooling

    Returns:
        Mock that raises urllib3.exceptions.HTTPError
    """
    import urllib3.exceptions

    def raise_network_error(*args, **kwargs):
        raise urllib3.exceptions.HTTPError("Network timeout")

    # Mock urllib3.PoolManager.request() to raise network error
    return mocker.patch(
        "binance_futures_availability.probing.s3_vision.HTTP_POOL.request",
        side_effect=raise_network_error
    )
