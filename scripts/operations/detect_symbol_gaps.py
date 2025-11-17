#!/usr/bin/env python3
"""
Detect symbol gaps between symbols.json and database.

Compares discovered symbols (symbols.json) against database contents
to identify new symbols that need historical backfill.

Usage:
    uv run python scripts/operations/detect_symbol_gaps.py
    uv run python scripts/operations/detect_symbol_gaps.py --verbose

Output:
    JSON array of new symbol names (e.g., ["NEWUSDT", "OTHERUSDT"])
    Empty array if no gaps: []

Exit Codes:
    0 - Gaps detected (new symbols found) - triggers backfill in workflow
    1 - No gaps detected (all symbols already in database)

Behavior (ADR-0012):
- Gap detection failure → raises immediately → fails workflow (strict mode)
- New symbols → output JSON array + exit 0
- No new symbols → output empty array + exit 1
- Error handling: Follows ADR-0003 (raise+propagate, no retry)

See: docs/decisions/0012-auto-backfill-new-symbols.md
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from binance_futures_availability.database import AvailabilityDatabase


def load_discovered_symbols() -> set[str]:
    """
    Load perpetual symbols from symbols.json.

    Returns:
        Set of symbol names from symbols.json

    Raises:
        RuntimeError: If symbols.json not found or invalid JSON
    """
    # Locate symbols.json relative to script location
    project_root = Path(__file__).parent.parent.parent
    symbols_file = project_root / "src/binance_futures_availability/data/symbols.json"

    try:
        data = json.loads(symbols_file.read_text())
        perpetual_symbols = set(data.get("perpetual_symbols", []))

        if not perpetual_symbols:
            raise RuntimeError("symbols.json contains no perpetual_symbols")

        return perpetual_symbols

    except FileNotFoundError as e:
        raise RuntimeError(f"symbols.json not found at {symbols_file}") from e
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid JSON in symbols.json: {e}") from e


def query_database_symbols() -> set[str]:
    """
    Query all symbols ever probed from database.

    Returns:
        Set of distinct symbol names from daily_availability table

    Raises:
        RuntimeError: On database query failure
    """
    try:
        db = AvailabilityDatabase()
        rows = db.query("SELECT DISTINCT symbol FROM daily_availability")
        db.close()

        # Extract symbol from each row tuple
        database_symbols = {row[0] for row in rows}
        return database_symbols

    except Exception as e:
        raise RuntimeError(f"Failed to query database symbols: {e}") from e


def detect_gaps(verbose: bool = False) -> list[str]:
    """
    Detect symbols in symbols.json that are not in database.

    Args:
        verbose: Enable verbose logging

    Returns:
        Sorted list of new symbol names (empty if no gaps)

    Raises:
        RuntimeError: On any failure (ADR-0003: strict error policy)
    """
    logger = logging.getLogger(__name__)

    # Load discovered symbols from symbols.json
    logger.info("Loading symbols from symbols.json...")
    discovered_symbols = load_discovered_symbols()
    logger.info(f"Discovered symbols: {len(discovered_symbols)}")

    # Query database for all symbols ever probed
    logger.info("Querying database for historical symbols...")
    database_symbols = query_database_symbols()
    logger.info(f"Database symbols: {len(database_symbols)}")

    # Find new symbols (discovered but not in database)
    new_symbols = discovered_symbols - database_symbols

    if new_symbols:
        logger.info(f"GAP DETECTED: {len(new_symbols)} new symbols found")
        if verbose:
            for symbol in sorted(new_symbols):
                logger.info(f"  + {symbol}")
    else:
        logger.info("No gaps detected (all symbols already in database)")

    return sorted(new_symbols)


def main() -> int:
    """
    Main gap detection execution.

    Returns:
        0 if gaps found (triggers backfill)
        1 if no gaps (skips backfill)
    """
    parser = argparse.ArgumentParser(
        description="Detect symbol gaps for auto-backfill (ADR-0012)"
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
    logger.info("Symbol Gap Detection (ADR-0012)")
    logger.info("=" * 70)
    logger.info("")

    # Detect gaps (raises on failure - strict mode per ADR-0003)
    try:
        new_symbols = detect_gaps(verbose=args.verbose)

    except Exception as e:
        logger.error(f"Gap detection failed: {e}", exc_info=args.verbose)
        logger.error("=" * 70)
        # Output empty array on error (workflow will fail anyway)
        print("[]")
        return 1

    # Output JSON array of new symbols
    output = json.dumps(new_symbols)
    print(output)

    logger.info("")
    logger.info("=" * 70)

    if new_symbols:
        logger.info(f"GAPS DETECTED: {len(new_symbols)} new symbols")
        logger.info("Output: gaps_detected=true (triggers auto-backfill)")
        logger.info("=" * 70)
        return 0
    else:
        logger.info("NO GAPS: All symbols already in database")
        logger.info("Output: gaps_detected=false (skips auto-backfill)")
        logger.info("=" * 70)
        return 0  # Always exit 0 (success) - use JSON output for conditional logic


if __name__ == "__main__":
    sys.exit(main())
