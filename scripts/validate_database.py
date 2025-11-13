#!/usr/bin/env python3
"""
Run all validation checks on the availability database.

Validation layers:
    1. Continuity: Check for missing dates
    2. Completeness: Verify recent symbol counts
    3. Cross-check: Compare with Binance exchangeInfo API

Usage:
    python scripts/validate_database.py
    python scripts/validate_database.py --verbose
"""

import argparse
import datetime
import logging
import sys

from binance_futures_availability.validation.completeness import CompletenessValidator
from binance_futures_availability.validation.continuity import ContinuityValidator
from binance_futures_availability.validation.cross_check import CrossCheckValidator


def main() -> int:
    """
    Run all validation checks.

    Returns:
        Exit code (0=all passed, non-zero=failures)
    """
    parser = argparse.ArgumentParser(description="Validate availability database")

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    logger = logging.getLogger(__name__)

    logger.info("=" * 70)
    logger.info("Binance Futures Availability - Database Validation")
    logger.info("=" * 70)

    all_passed = True

    # 1. Continuity Check
    logger.info("\n[1/3] Continuity Check: Detecting missing dates...")
    try:
        validator = ContinuityValidator()
        missing_dates = validator.check_continuity()

        if missing_dates:
            logger.error(f"FAILED: {len(missing_dates)} missing dates found")
            for date in missing_dates[:10]:
                logger.error(f"  - {date}")
            if len(missing_dates) > 10:
                logger.error(f"  ... and {len(missing_dates) - 10} more")
            all_passed = False
        else:
            logger.info("PASSED: No missing dates (complete coverage)")

        validator.close()

    except Exception as e:
        logger.error(f"FAILED: Continuity check error: {e}")
        all_passed = False

    # 2. Completeness Check
    logger.info("\n[2/3] Completeness Check: Verifying symbol counts...")
    try:
        validator = CompletenessValidator()
        incomplete_dates = validator.check_completeness(min_symbol_count=700)

        if incomplete_dates:
            logger.error(f"FAILED: {len(incomplete_dates)} dates with <700 symbols")
            for item in incomplete_dates[:10]:
                logger.error(f"  - {item['date']}: {item['symbol_count']} symbols")
            if len(incomplete_dates) > 10:
                logger.error(f"  ... and {len(incomplete_dates) - 10} more")
            all_passed = False
        else:
            logger.info("PASSED: All recent dates have ≥700 symbols")

        # Show summary
        summary = validator.get_symbol_counts_summary(days=7)
        logger.info("Recent 7 days summary:")
        for item in summary:
            logger.info(f"  - {item['date']}: {item['symbol_count']} symbols")

        validator.close()

    except Exception as e:
        logger.error(f"FAILED: Completeness check error: {e}")
        all_passed = False

    # 3. Cross-check with API
    logger.info("\n[3/3] Cross-check: Comparing with Binance exchangeInfo API...")
    try:
        validator = CrossCheckValidator()
        result = validator.cross_check_current_date()

        logger.info(f"Database symbols: {result['db_symbol_count']}")
        logger.info(f"API symbols: {result['api_symbol_count']}")
        logger.info(f"Match count: {result['match_count']}")
        logger.info(f"Match percentage: {result['match_percentage']}%")

        if result["slo_met"]:
            logger.info(f"PASSED: {result['match_percentage']}% match (SLO: >95%)")
        else:
            logger.error(f"FAILED: {result['match_percentage']}% match (SLO: >95%)")
            all_passed = False

        # Show discrepancies
        if result["only_in_db"]:
            logger.info(f"Symbols only in DB: {len(result['only_in_db'])}")
            for symbol in result["only_in_db"][:5]:
                logger.info(f"  - {symbol}")

        if result["only_in_api"]:
            logger.info(f"Symbols only in API: {len(result['only_in_api'])}")
            for symbol in result["only_in_api"][:5]:
                logger.info(f"  - {symbol}")

        validator.close()

    except Exception as e:
        logger.error(f"FAILED: Cross-check error: {e}")
        all_passed = False

    # Summary
    logger.info("\n" + "=" * 70)
    if all_passed:
        logger.info("VALIDATION PASSED: All checks successful ✓")
        logger.info("=" * 70)
        return 0
    else:
        logger.error("VALIDATION FAILED: One or more checks failed ✗")
        logger.error("=" * 70)
        return 1


if __name__ == "__main__":
    sys.exit(main())
