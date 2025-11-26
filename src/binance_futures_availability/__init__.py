"""
Binance Futures Availability Database

Track daily availability of USDT perpetual futures from Binance Vision S3 repository.
Symbol count is dynamic (~327 currently) as instruments are listed/delisted over time.

Quick Start:
    >>> from binance_futures_availability.queries import SnapshotQueries
    >>> q = SnapshotQueries()
    >>> symbols = q.get_available_symbols_on_date('2024-01-15')

    >>> from binance_futures_availability.queries import TimelineQueries
    >>> t = TimelineQueries()
    >>> timeline = t.get_symbol_availability_timeline('BTCUSDT')

For more information, see: https://github.com/terrylica/binance-futures-availability
"""

from binance_futures_availability.__version__ import __version__
from binance_futures_availability.database.availability_db import AvailabilityDatabase
from binance_futures_availability.queries.snapshots import SnapshotQueries
from binance_futures_availability.queries.timelines import TimelineQueries

__all__ = [
    "__version__",
    "AvailabilityDatabase",
    "SnapshotQueries",
    "TimelineQueries",
]
