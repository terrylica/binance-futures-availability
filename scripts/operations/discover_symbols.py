#!/usr/bin/env python3
"""
Discover futures symbols from Binance Vision S3 and update symbols.json.

Runs daily via GitHub Actions workflow to catch new listings automatically.
Updates symbols.json when changes detected, which triggers git auto-commit.

Usage:
    uv run python scripts/operations/discover_symbols.py
    uv run python scripts/operations/discover_symbols.py --verbose

Performance: ~0.51s for ~369 symbols (S3 XML API listing)

Behavior (ADR-0010):
- Discovery failure → raises immediately → fails workflow (strict mode)
- New symbols → update symbols.json + log changes
- No changes → exits cleanly (no file write)
- Error handling: Follows ADR-0003 (raise+propagate, no retry)

Returns:
    Exit code 0 on success, 1 on failure
"""

import argparse
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

from binance_futures_availability.probing.s3_symbol_discovery import (
    discover_all_futures_symbols,
)


def main() -> int:
    """
    Main discovery execution.

    Returns:
        0 on success, 1 on failure
    """
    parser = argparse.ArgumentParser(
        description="Discover futures symbols from S3 and update symbols.json"
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging (DEBUG level)",
    )

    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    logger = logging.getLogger(__name__)

    logger.info("=" * 70)
    logger.info("Binance Futures Symbol Discovery")
    logger.info("=" * 70)
    logger.info("")

    # Discover symbols from S3 (raises on failure - strict mode per ADR-0010)
    try:
        logger.info("Discovering symbols from Binance Vision S3...")
        discovered = discover_all_futures_symbols(market_type="um", granularity="daily")

        perpetual = discovered["perpetual"]
        delivery = discovered["delivery"]

        logger.info("Discovery complete:")
        logger.info(f"  Perpetual contracts: {len(perpetual)}")
        logger.info(f"  Delivery contracts: {len(delivery)}")
        logger.info(f"  Total symbols: {len(perpetual) + len(delivery)}")
        logger.info("")

    except Exception as e:
        logger.error(f"Symbol discovery failed: {e}", exc_info=args.verbose)
        logger.error("=" * 70)
        return 1

    # Load current symbols.json
    project_root = Path(__file__).parent.parent.parent
    symbols_file = project_root / "src/binance_futures_availability/data/symbols.json"

    try:
        current = json.loads(symbols_file.read_text())
    except FileNotFoundError:
        logger.error(f"symbols.json not found at: {symbols_file}")
        return 1
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse symbols.json: {e}")
        return 1

    # Compare with current state
    current_perpetual = set(current.get("perpetual_symbols", []))
    current_delivery = set(current.get("delivery_symbols", []))

    new_perpetual = set(perpetual) - current_perpetual
    new_delivery = set(delivery) - current_delivery

    removed_perpetual = current_perpetual - set(perpetual)
    removed_delivery = current_delivery - set(delivery)

    # Log changes
    if new_perpetual or new_delivery:
        logger.info("NEW SYMBOLS DISCOVERED:")
        if new_perpetual:
            logger.info(f"  Perpetual: {len(new_perpetual)} new")
            for symbol in sorted(new_perpetual):
                logger.info(f"    + {symbol}")
        if new_delivery:
            logger.info(f"  Delivery: {len(new_delivery)} new")
            for symbol in sorted(new_delivery):
                logger.info(f"    + {symbol}")
        logger.info("")
    else:
        logger.info("No new symbols discovered")

    # Note: We never remove symbols per ADR-0010 (user decision: "probe forever")
    # But we log if any disappeared from S3 (could indicate S3 issue)
    if removed_perpetual or removed_delivery:
        logger.warning("SYMBOLS MISSING FROM S3 (NOT REMOVED FROM LIST):")
        if removed_perpetual:
            logger.warning(f"  Perpetual: {len(removed_perpetual)} missing")
            for symbol in sorted(removed_perpetual)[:10]:
                logger.warning(f"    - {symbol}")
            if len(removed_perpetual) > 10:
                logger.warning(f"    ... and {len(removed_perpetual) - 10} more")
        if removed_delivery:
            logger.warning(f"  Delivery: {len(removed_delivery)} missing")
            for symbol in sorted(removed_delivery)[:10]:
                logger.warning(f"    - {symbol}")
            if len(removed_delivery) > 10:
                logger.warning(f"    ... and {len(removed_delivery) - 10} more")
        logger.warning("Note: Symbols retained in list (ADR-0010: never remove, probe forever)")
        logger.info("")

    # Update metadata
    updated = {
        "metadata": {
            "discovery_date": datetime.now(UTC).strftime("%Y-%m-%d"),
            "last_discovery": datetime.now(UTC).isoformat(),
            "source": "S3 Vision bucket: s3://data.binance.vision/data/futures/um/daily/klines/",
            "discovery_method": "S3 XML API",
            "note": "Symbols with historical data availability on S3 Vision (auto-updated daily)",
            "total_perpetual": len(perpetual),
            "total_delivery": len(delivery),
            "total_all": len(perpetual) + len(delivery),
        },
        "perpetual_symbols": sorted(perpetual),
        "delivery_symbols": sorted(delivery),
    }

    # Write updated symbols.json (atomic write)
    try:
        # Write to temp file first
        temp_file = symbols_file.with_suffix(".json.tmp")
        temp_file.write_text(json.dumps(updated, indent=2) + "\n")

        # Atomic rename
        temp_file.replace(symbols_file)

        logger.info(f"Updated: {symbols_file}")
        logger.info("")

    except Exception as e:
        logger.error(f"Failed to write symbols.json: {e}")
        return 1

    # Summary
    logger.info("=" * 70)
    logger.info("DISCOVERY COMPLETE")
    logger.info("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
