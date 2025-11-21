"""Query commands: Snapshot, timeline, and analytics queries.

Commands:
    - query snapshot: Get available symbols on a specific date
    - query timeline: Get availability timeline for a symbol
    - query range: Get symbols in a date range
    - query analytics: Run analytics queries (new listings, delistings, summary)
"""

import argparse
import json
import logging

from binance_futures_availability.queries.analytics import AnalyticsQueries
from binance_futures_availability.queries.snapshots import SnapshotQueries
from binance_futures_availability.queries.timelines import TimelineQueries

logger = logging.getLogger(__name__)


def add_query_commands(subparsers) -> None:
    """
    Add query commands to CLI parser.

    Args:
        subparsers: argparse subparsers object
    """
    query_parser = subparsers.add_parser(
        "query",
        help="Query availability database",
    )

    query_subparsers = query_parser.add_subparsers(dest="query_command")

    # Snapshot query
    snapshot_parser = query_subparsers.add_parser(
        "snapshot",
        help="Get available symbols on a specific date",
    )
    snapshot_parser.add_argument(
        "date",
        type=str,
        help="Date to query (YYYY-MM-DD)",
    )
    snapshot_parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )
    snapshot_parser.set_defaults(func=cmd_snapshot)

    # Timeline query
    timeline_parser = query_subparsers.add_parser(
        "timeline",
        help="Get availability timeline for a symbol",
    )
    timeline_parser.add_argument(
        "symbol",
        type=str,
        help="Symbol to query (e.g., BTCUSDT)",
    )
    timeline_parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )
    timeline_parser.set_defaults(func=cmd_timeline)

    # Range query
    range_parser = query_subparsers.add_parser(
        "range",
        help="Get symbols available in a date range",
    )
    range_parser.add_argument(
        "start_date",
        type=str,
        help="Start date (YYYY-MM-DD)",
    )
    range_parser.add_argument(
        "end_date",
        type=str,
        help="End date (YYYY-MM-DD)",
    )
    range_parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )
    range_parser.set_defaults(func=cmd_range)

    # Analytics query
    analytics_parser = query_subparsers.add_parser(
        "analytics",
        help="Run analytics queries (new listings, delistings, summary)",
    )
    analytics_subparsers = analytics_parser.add_subparsers(dest="analytics_command")

    # New listings
    new_listings_parser = analytics_subparsers.add_parser(
        "new-listings",
        help="Detect new listings on a specific date",
    )
    new_listings_parser.add_argument(
        "date",
        type=str,
        help="Date to check (YYYY-MM-DD)",
    )
    new_listings_parser.set_defaults(func=cmd_new_listings)

    # Delistings
    delistings_parser = analytics_subparsers.add_parser(
        "delistings",
        help="Detect delistings on a specific date",
    )
    delistings_parser.add_argument(
        "date",
        type=str,
        help="Date to check (YYYY-MM-DD)",
    )
    delistings_parser.set_defaults(func=cmd_delistings)

    # Summary
    summary_parser = analytics_subparsers.add_parser(
        "summary",
        help="Get availability summary (daily symbol counts)",
    )
    summary_parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )
    summary_parser.set_defaults(func=cmd_summary)


def cmd_snapshot(args: argparse.Namespace) -> int:
    """Execute snapshot query command."""
    try:
        queries = SnapshotQueries()
        results = queries.get_available_symbols_on_date(args.date)

        if args.json:
            print(json.dumps(results, indent=2, default=str))
        else:
            print(f"Available symbols on {args.date}: {len(results)}")
            for r in results[:10]:  # Show first 10
                print(f"  - {r['symbol']} ({r['file_size_bytes']} bytes)")
            if len(results) > 10:
                print(f"  ... and {len(results) - 10} more")

        queries.close()
        return 0

    except Exception as e:
        logger.error(f"Snapshot query failed: {e}", exc_info=True)
        return 1


def cmd_timeline(args: argparse.Namespace) -> int:
    """Execute timeline query command."""
    try:
        queries = TimelineQueries()
        timeline = queries.get_symbol_availability_timeline(args.symbol)

        if args.json:
            print(json.dumps(timeline, indent=2, default=str))
        else:
            print(f"Availability timeline for {args.symbol}: {len(timeline)} days")
            first_date = queries.get_symbol_first_listing_date(args.symbol)
            last_date = queries.get_symbol_last_available_date(args.symbol)
            print(f"  First available: {first_date}")
            print(f"  Last available: {last_date}")
            print(f"  Total days: {len(timeline)}")

        queries.close()
        return 0

    except Exception as e:
        logger.error(f"Timeline query failed: {e}", exc_info=True)
        return 1


def cmd_range(args: argparse.Namespace) -> int:
    """Execute range query command."""
    try:
        queries = SnapshotQueries()
        symbols = queries.get_symbols_in_date_range(args.start_date, args.end_date)

        if args.json:
            print(json.dumps(symbols, indent=2))
        else:
            print(f"Symbols available {args.start_date} to {args.end_date}: {len(symbols)}")
            for symbol in symbols[:20]:  # Show first 20
                print(f"  - {symbol}")
            if len(symbols) > 20:
                print(f"  ... and {len(symbols) - 20} more")

        queries.close()
        return 0

    except Exception as e:
        logger.error(f"Range query failed: {e}", exc_info=True)
        return 1


def cmd_new_listings(args: argparse.Namespace) -> int:
    """Execute new listings analytics command."""
    try:
        queries = AnalyticsQueries()
        new_symbols = queries.detect_new_listings(args.date)

        print(f"New listings on {args.date}: {len(new_symbols)}")
        for symbol in new_symbols:
            print(f"  - {symbol}")

        queries.close()
        return 0

    except Exception as e:
        logger.error(f"New listings query failed: {e}", exc_info=True)
        return 1


def cmd_delistings(args: argparse.Namespace) -> int:
    """Execute delistings analytics command."""
    try:
        queries = AnalyticsQueries()
        delisted = queries.detect_delistings(args.date)

        print(f"Delistings on {args.date}: {len(delisted)}")
        for symbol in delisted:
            print(f"  - {symbol}")

        queries.close()
        return 0

    except Exception as e:
        logger.error(f"Delistings query failed: {e}", exc_info=True)
        return 1


def cmd_summary(args: argparse.Namespace) -> int:
    """Execute summary analytics command."""
    try:
        queries = AnalyticsQueries()
        summary = queries.get_availability_summary()

        if args.json:
            print(json.dumps(summary, indent=2, default=str))
        else:
            print(f"Availability summary: {len(summary)} days")
            print(f"  First day: {summary[0]['date']} ({summary[0]['available_count']} symbols)")
            print(f"  Last day: {summary[-1]['date']} ({summary[-1]['available_count']} symbols)")

        queries.close()
        return 0

    except Exception as e:
        logger.error(f"Summary query failed: {e}", exc_info=True)
        return 1
