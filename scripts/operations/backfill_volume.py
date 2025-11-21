#!/usr/bin/env python
"""
Historical backfill script for trading volume metrics.

Updates existing daily_availability records with volume metrics from 1d kline files.
Follows ADR-0007 implementation plan Phase 3.

Usage:
    # Backfill all available dates with missing volume data (10 workers, ~4x speedup)
    uv run python scripts/operations/backfill_volume.py

    # Backfill with 20 concurrent workers (may be faster/slower depending on network)
    uv run python scripts/operations/backfill_volume.py --workers 20

    # Sequential processing (1 worker, original behavior)
    uv run python scripts/operations/backfill_volume.py --workers 1

    # Backfill specific date range
    uv run python scripts/operations/backfill_volume.py --start-date 2024-01-01 --end-date 2024-01-31

    # Backfill specific symbols
    uv run python scripts/operations/backfill_volume.py --symbols BTCUSDT ETHUSDT

    # Dry run (no database writes)
    uv run python scripts/operations/backfill_volume.py --dry-run

Performance:
    - Sequential (--workers 1): ~3.35 files/second (baseline)
    - Parallel (--workers 10): ~13.47 files/second (4.02x speedup) [RECOMMENDED]
    - Parallel (--workers 20): ~6.82 files/second (2.04x speedup)

    Estimated full backfill time (355,029 records):
    - Sequential: ~29.5 hours (1.2 days)
    - Parallel (10 workers): ~7.3 hours [RECOMMENDED]
    - Parallel (20 workers): ~14.5 hours
"""

import argparse
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from binance_futures_availability.database import AvailabilityDatabase
from binance_futures_availability.probing.aws_s3_lister import AWSS3Lister

# Thread-safe progress tracking
progress_lock = threading.Lock()


def get_records_needing_volume(
    db: AvailabilityDatabase,
    start_date: date | None = None,
    end_date: date | None = None,
    symbols: list[str] | None = None,
) -> list[tuple[str, date]]:
    """
    Get all (symbol, date) pairs that need volume data.

    Returns records where:
    - available = True (1m kline exists)
    - quote_volume_usdt IS NULL (volume not yet collected)

    Args:
        db: Database connection
        start_date: Optional start date filter
        end_date: Optional end date filter
        symbols: Optional symbol filter

    Returns:
        List of (symbol, date) tuples needing volume data
    """
    sql = """
        SELECT symbol, date
        FROM daily_availability
        WHERE available = TRUE
          AND quote_volume_usdt IS NULL
    """

    conditions = []
    params = []

    if start_date:
        conditions.append("date >= ?")
        params.append(start_date)

    if end_date:
        conditions.append("date <= ?")
        params.append(end_date)

    if symbols:
        placeholders = ",".join("?" * len(symbols))
        conditions.append(f"symbol IN ({placeholders})")
        params.extend(symbols)

    if conditions:
        sql += " AND " + " AND ".join(conditions)

    sql += " ORDER BY symbol, date"

    result = db.query(sql, params)
    return [(row[0], row[1]) for row in result]


def update_volume_metrics(
    db: AvailabilityDatabase,
    symbol: str,
    target_date: date,
    volume_data: dict,
) -> None:
    """
    Update volume metrics for a specific (symbol, date) record.

    Args:
        db: Database connection
        symbol: Trading pair symbol
        target_date: Date to update
        volume_data: Dict with 9 volume/price metrics

    Raises:
        RuntimeError: If update fails
    """
    sql = """
        UPDATE daily_availability
        SET quote_volume_usdt = ?,
            trade_count = ?,
            volume_base = ?,
            taker_buy_volume_base = ?,
            taker_buy_quote_volume_usdt = ?,
            open_price = ?,
            high_price = ?,
            low_price = ?,
            close_price = ?
        WHERE symbol = ? AND date = ?
    """

    params = [
        volume_data["quote_volume_usdt"],
        volume_data["trade_count"],
        volume_data["volume_base"],
        volume_data["taker_buy_volume_base"],
        volume_data["taker_buy_quote_volume_usdt"],
        volume_data["open_price"],
        volume_data["high_price"],
        volume_data["low_price"],
        volume_data["close_price"],
        symbol,
        target_date,
    ]

    try:
        db.conn.execute(sql, params)
    except Exception as e:
        raise RuntimeError(
            f"Failed to update volume metrics for {symbol} {target_date}: {e}"
        ) from e


def process_record(
    record_data: tuple[int, int, str, date, AWSS3Lister, AvailabilityDatabase]
) -> dict:
    """
    Process a single record: download 1d kline and update database.

    Args:
        record_data: Tuple of (idx, total, symbol, target_date, lister, db)

    Returns:
        Dict with status: "success", "missing", or "error"
    """
    idx, total, symbol, target_date, lister, db = record_data

    try:
        # Download and parse 1d kline
        volume_data = lister.download_1d_kline(symbol, target_date)

        if volume_data is None:
            # 1d kline file doesn't exist (expected for some dates)
            return {
                "status": "missing",
                "symbol": symbol,
                "date": target_date,
                "idx": idx,
                "total": total,
            }

        # Update database
        update_volume_metrics(db, symbol, target_date, volume_data)

        return {
            "status": "success",
            "symbol": symbol,
            "date": target_date,
            "volume_data": volume_data,
            "idx": idx,
            "total": total,
        }

    except Exception as e:
        return {
            "status": "error",
            "symbol": symbol,
            "date": target_date,
            "error": str(e),
            "idx": idx,
            "total": total,
        }


def main():
    parser = argparse.ArgumentParser(
        description="Backfill trading volume metrics from 1d kline files"
    )
    parser.add_argument(
        "--start-date",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(),
        help="Start date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end-date",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(),
        help="End date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--symbols",
        nargs="+",
        help="Specific symbols to backfill (default: all)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without writing to database",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of records to process (for testing)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=10,
        help="Number of concurrent workers (default: 10, use 1 for sequential)",
    )

    args = parser.parse_args()

    print("=== Volume Metrics Backfill ===\n")

    # Initialize components
    db = AvailabilityDatabase()
    lister = AWSS3Lister()

    # Get records needing volume data
    print("Querying database for records needing volume data...")
    records = get_records_needing_volume(
        db,
        start_date=args.start_date,
        end_date=args.end_date,
        symbols=args.symbols,
    )

    if args.limit:
        records = records[: args.limit]

    total = len(records)
    print(f"Found {total:,} records needing volume metrics\n")

    if total == 0:
        print("✅ All available records already have volume data!")
        return 0

    if args.dry_run:
        print("DRY RUN - No database writes will occur\n")
        print("Sample records to process:")
        for symbol, dt in records[:10]:
            print(f"  - {symbol} {dt}")
        if total > 10:
            print(f"  ... and {total - 10:,} more")
        return 0

    # Process records
    success_count = 0
    error_count = 0
    missing_count = 0
    processed_count = 0

    print(f"Using {args.workers} concurrent worker(s)...\n")

    if args.workers == 1:
        # Sequential processing (original logic)
        for idx, (symbol, target_date) in enumerate(records, 1):
            record_data = (idx, total, symbol, target_date, lister, db)
            result = process_record(record_data)

            # Update counters
            if result["status"] == "success":
                success_count += 1
                if idx % 100 == 0:
                    volume_data = result["volume_data"]
                    print(
                        f"[{idx}/{total}] ✅ {result['symbol']} {result['date']}: "
                        f"${volume_data['quote_volume_usdt']:,.0f} volume, "
                        f"{volume_data['trade_count']:,} trades"
                    )
            elif result["status"] == "missing":
                missing_count += 1
                print(
                    f"[{idx}/{total}] ⚠️  {result['symbol']} {result['date']}: "
                    f"1d kline not found (skipped)"
                )
            else:  # error
                error_count += 1
                print(
                    f"[{idx}/{total}] ❌ {result['symbol']} {result['date']}: "
                    f"{result['error']}"
                )

    else:
        # Parallel processing with ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            # Submit all tasks
            futures = {
                executor.submit(
                    process_record,
                    (idx, total, symbol, target_date, lister, db)
                ): (idx, symbol, target_date)
                for idx, (symbol, target_date) in enumerate(records, 1)
            }

            # Process results as they complete
            for future in as_completed(futures):
                result = future.result()
                processed_count += 1

                # Update counters with thread-safe print
                with progress_lock:
                    if result["status"] == "success":
                        success_count += 1
                        # Progress report every 100 records or at the end
                        if processed_count % 100 == 0 or processed_count == total:
                            volume_data = result["volume_data"]
                            print(
                                f"[{processed_count}/{total}] ✅ {result['symbol']} {result['date']}: "
                                f"${volume_data['quote_volume_usdt']:,.0f} volume, "
                                f"{volume_data['trade_count']:,} trades"
                            )
                    elif result["status"] == "missing":
                        missing_count += 1
                        # Only print first few missing to avoid spam
                        if missing_count <= 10:
                            print(
                                f"[{processed_count}/{total}] ⚠️  {result['symbol']} {result['date']}: "
                                f"1d kline not found (skipped)"
                            )
                    else:  # error
                        error_count += 1
                        print(
                            f"[{processed_count}/{total}] ❌ {result['symbol']} {result['date']}: "
                            f"{result['error']}"
                        )

    # Summary
    print("\n=== Backfill Complete ===")
    print(f"Total records processed: {total:,}")
    print(f"✅ Success: {success_count:,}")
    print(f"⚠️  Missing 1d klines: {missing_count:,}")
    print(f"❌ Errors: {error_count:,}")

    # Validation query
    print("\n=== Validation ===")
    result = db.query(
        "SELECT COUNT(*) FROM daily_availability WHERE quote_volume_usdt IS NOT NULL"
    )
    rows_with_volume = result[0][0]
    print(f"Total rows with volume data: {rows_with_volume:,}")

    # Sample validation
    sample = db.query(
        """
        SELECT symbol, date, quote_volume_usdt, trade_count
        FROM daily_availability
        WHERE quote_volume_usdt IS NOT NULL
        ORDER BY quote_volume_usdt DESC
        LIMIT 5
        """
    )
    print("\nTop 5 by volume:")
    for row in sample:
        print(
            f"  {row[0]} {row[1]}: ${row[2]:,.0f} volume, {row[3]:,} trades"
        )

    return 1 if error_count > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
