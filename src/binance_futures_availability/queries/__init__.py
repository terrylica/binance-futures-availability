"""High-level query interface for availability database."""

from binance_futures_availability.queries.analytics import AnalyticsQueries
from binance_futures_availability.queries.snapshots import SnapshotQueries
from binance_futures_availability.queries.timelines import TimelineQueries
from binance_futures_availability.queries.volume import VolumeQueries

__all__ = ["SnapshotQueries", "TimelineQueries", "AnalyticsQueries", "VolumeQueries"]
