#!/usr/bin/env python3
"""
AWS CLI-based historical backfill (MUCH FASTER than HEAD requests).

Uses aws s3 ls to list all files per symbol in one call, extracting
availability from filenames. 3.5x faster than individual HEAD requests.

Performance:
  - 708 symbols × 4.5 sec = ~53 minutes (vs 3 hours with HEAD requests)
  - Single API call per symbol gets ALL dates at once

Usage:
    python scripts/run_backfill_aws.py
    python scripts/run_backfill_aws.py --start-date 2024-01-01
    python scripts/run_backfill_aws.py --symbols BTCUSDT ETHUSDT  # Test subset
"""

import argparse
import datetime
import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List

from binance_futures_availability.database import AvailabilityDatabase
from binance_futures_availability.probing.aws_s3_lister import AWSS3Lister
from binance_futures_availability.probing.symbol_discovery import load_discovered_symbols


def backfill_symbol(
    symbol: str,
    start_date: datetime.date,
    end_date: datetime.date,
    db: AvailabilityDatabase,
) -> dict:
    """
    Backfill all availability data for a single symbol using AWS CLI.

    Args:
        symbol: Trading pair symbol
        start_date: Start of date range
        end_date: End of date range (inclusive)
        db: Database connection

    Returns:
        Dict with symbol, dates_found, error (if any)
    """
    lister = AWSS3Lister()

    try:
        # Get all available dates for this symbol
        availability = lister.get_symbol_availability(
            symbol, start_date=start_date, end_date=end_date
        )

        # Build records for ALL dates in range (available + unavailable)
        records = []
        probe_time = datetime.datetime.now(datetime.timezone.utc)
        current_date = start_date

        while current_date <= end_date:
            if current_date in availability:
                # Available: file exists
                meta = availability[current_date]
                records.append(
                    {
                        "date": current_date,
                        "symbol": symbol,
                        "available": True,
                        "file_size_bytes": meta["file_size_bytes"],
                        "last_modified": meta["last_modified"],
                        "url": meta["url"],
                        "status_code": 200,  # Inferred from file existence
                        "probe_timestamp": probe_time,
                    }
                )
            else:
                # Unavailable: file does not exist
                records.append(
                    {
                        "date": current_date,
                        "symbol": symbol,
                        "available": False,
                        "file_size_bytes": None,
                        "last_modified": None,
                        "url": f"https://data.binance.vision/data/futures/um/daily/klines/{symbol}/1m/{symbol}-1m-{current_date}.zip",
                        "status_code": 404,  # Inferred from absence
                        "probe_timestamp": probe_time,
                    }
                )

            current_date += datetime.timedelta(days=1)

        # Bulk insert into database (uses INSERT OR REPLACE for UPSERT)
        db.insert_batch(records)

        return {
            "symbol": symbol,
            "dates_found": len(availability),
            "total_dates": len(records),
            "error": None,
        }

    except Exception as e:
        return {"symbol": symbol, "dates_found": 0, "total_dates": 0, "error": str(e)}


def main() -> int:
    """Run AWS CLI-based historical backfill."""

    parser = argparse.ArgumentParser(
        description="AWS CLI-based historical backfill (3.5x faster)"
    )

    parser.add_argument(
        "--start-date",
        type=str,
        help="Backfill start date (YYYY-MM-DD, default: 2019-09-25)",
    )

    parser.add_argument(
        "--end-date",
        type=str,
        help="Backfill end date (YYYY-MM-DD, default: yesterday)",
    )

    parser.add_argument(
        "--symbols",
        nargs="+",
        help="Specific symbols to backfill (default: all 708 perpetuals)",
    )

    parser.add_argument(
        "--workers",
        type=int,
        default=10,
        help="Number of parallel workers (default: 10)",
    )

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger(__name__)

    # Parse dates
    start_date = (
        datetime.date.fromisoformat(args.start_date)
        if args.start_date
        else datetime.date(2019, 9, 25)
    )

    end_date = (
        datetime.date.fromisoformat(args.end_date)
        if args.end_date
        else datetime.date.today() - datetime.timedelta(days=1)
    )

    # Load symbols
    if args.symbols:
        symbols = args.symbols
        logger.info(f"Using {len(symbols)} specified symbols")
    else:
        symbols = load_discovered_symbols()
        logger.info(f"Using all {len(symbols)} perpetual USDT futures")

    total_days = (end_date - start_date).days + 1

    logger.info("=" * 60)
    logger.info("AWS CLI-Based Historical Backfill (3.5x Faster)")
    logger.info("=" * 60)
    logger.info(f"Date range: {start_date} to {end_date} ({total_days} days)")
    logger.info(f"Symbols: {len(symbols)}")
    logger.info(f"Parallel workers: {args.workers}")
    logger.info(f"Estimated time: ~{len(symbols) * 4.5 / 60:.0f} minutes")
    logger.info("=" * 60)

    # Connect to database (respect DB_PATH environment variable if set)
    db_path = os.environ.get('DB_PATH')
    if db_path:
        logger.info(f"Using database from DB_PATH: {db_path}")
        db = AvailabilityDatabase(db_path=Path(db_path))
    else:
        logger.info("Using default database path: ~/.cache/binance-futures/availability.duckdb")
        db = AvailabilityDatabase()

    # Process symbols in parallel
    results = []
    failed_symbols = []

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        # Submit all symbol backfill tasks
        future_to_symbol = {
            executor.submit(backfill_symbol, symbol, start_date, end_date, db): symbol
            for symbol in symbols
        }

        # Process results as they complete
        for i, future in enumerate(as_completed(future_to_symbol), 1):
            symbol = future_to_symbol[future]

            try:
                result = future.result()
                results.append(result)

                if result["error"]:
                    failed_symbols.append(symbol)
                    logger.error(
                        f"[{i}/{len(symbols)}] ❌ {symbol}: {result['error']}"
                    )
                else:
                    logger.info(
                        f"[{i}/{len(symbols)}] ✅ {symbol}: {result['dates_found']}/{result['total_dates']} dates available"
                    )

            except Exception as e:
                failed_symbols.append(symbol)
                logger.error(f"[{i}/{len(symbols)}] ❌ {symbol}: Unexpected error: {e}")

    # Summary
    total_records = sum(r["total_dates"] for r in results if not r["error"])
    available_count = sum(r["dates_found"] for r in results if not r["error"])

    logger.info("=" * 60)
    logger.info("Backfill Complete!")
    logger.info("=" * 60)
    logger.info(f"Symbols processed: {len(results) - len(failed_symbols)}/{len(symbols)}")
    logger.info(f"Records inserted: {total_records:,}")
    logger.info(f"Available: {available_count:,} ({available_count*100//total_records if total_records else 0}%)")
    logger.info(f"Unavailable: {total_records - available_count:,}")

    if failed_symbols:
        logger.warning(f"Failed symbols ({len(failed_symbols)}): {', '.join(failed_symbols[:10])}")
        if len(failed_symbols) > 10:
            logger.warning(f"... and {len(failed_symbols) - 10} more")
        return 1

    logger.info("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
