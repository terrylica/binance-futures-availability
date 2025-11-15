"""Main CLI entry point with argparse.

Entry point: binance-futures-availability (defined in pyproject.toml)
"""

import argparse
import logging
import sys

from binance_futures_availability.__version__ import __version__
from binance_futures_availability.cli.query import add_query_commands


def main() -> int:
    """
    Main CLI entry point.

    Returns:
        Exit code (0=success, non-zero=failure)

    Commands:
        - query: Query database

    Example:
        $ binance-futures-availability query snapshot 2024-01-15
        $ binance-futures-availability query timeline BTCUSDT

    Note:
        For data collection, use GitHub Actions workflow or scripts/operations/ directly.
    """
    parser = argparse.ArgumentParser(
        prog="binance-futures-availability",
        description="Binance Futures Availability Database - Track daily availability of USDT perpetuals",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--version", action="version", version=f"binance-futures-availability {__version__}"
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging (DEBUG level)",
    )

    # Create subparsers for commands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Add command groups
    add_query_commands(subparsers)

    # Parse arguments
    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Execute command
    if not args.command:
        parser.print_help()
        return 1

    try:
        # Call command handler
        return args.func(args)

    except Exception as e:
        logging.error(f"Command failed: {e}", exc_info=args.verbose)
        return 1


if __name__ == "__main__":
    sys.exit(main())
