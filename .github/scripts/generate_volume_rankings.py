#!/usr/bin/env python3
"""
Generate volume rankings time-series Parquet archive.

Calculates daily volume rankings for all symbols using quote_volume_usdt metric,
tracks rank changes over 1-day, 7-day, 14-day, and 30-day windows, and outputs
single cumulative Parquet file for analytical database consumption.

Usage:
    uv run python .github/scripts/generate_volume_rankings.py \\
        --db-path ~/.cache/binance-futures/availability.duckdb \\
        --existing-file volume-rankings-timeseries.parquet \\
        --output volume-rankings-timeseries.parquet

See: docs/decisions/0013-volume-rankings-timeseries.md
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

try:
    import duckdb
    import pyarrow as pa
    import pyarrow.parquet as pq
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Install with: uv pip install pyarrow duckdb")
    sys.exit(1)


# Schema definition (ADR-0013)
RANKINGS_SCHEMA = pa.schema([
    ('date', pa.date32()),
    ('symbol', pa.string()),
    ('rank', pa.uint16()),
    ('quote_volume_usdt', pa.float64()),
    ('trade_count', pa.uint64()),
    ('rank_change_1d', pa.int16()),
    ('rank_change_7d', pa.int16()),
    ('rank_change_14d', pa.int16()),
    ('rank_change_30d', pa.int16()),
    ('percentile', pa.float32()),
    ('market_share_pct', pa.float32()),
    ('days_available', pa.uint8()),
    ('generation_timestamp', pa.timestamp('us')),
])


def get_latest_date_from_parquet(parquet_file: Path) -> str | None:
    """
    Extract latest date from existing Parquet file for incremental append.

    Args:
        parquet_file: Path to existing Parquet file

    Returns:
        Latest date as YYYY-MM-DD string, or None if file doesn't exist
    """
    if not parquet_file.exists():
        return None

    try:
        table = pq.read_table(parquet_file, columns=['date'])
        max_date = table['date'].to_pandas().max()
        return max_date.strftime('%Y-%m-%d')
    except Exception as e:
        logging.warning(f"Could not read existing Parquet: {e}")
        return None


def generate_rankings_sql(start_date: str | None) -> str:
    """
    Generate SQL query for volume rankings with rank change tracking.

    Uses DENSE_RANK() for consistent rankings (no gaps when ties exist).
    Calculates rank changes over 1d, 7d, 14d, 30d windows using LAG().

    Args:
        start_date: Optional start date (YYYY-MM-DD) for incremental append.
                   If None, queries all historical dates.

    Returns:
        SQL query string
    """
    date_filter = f"AND date > '{start_date}'" if start_date else ""

    return f"""
    WITH daily_ranks AS (
        SELECT
            date,
            symbol,
            quote_volume_usdt,
            trade_count,
            DENSE_RANK() OVER (PARTITION BY date ORDER BY quote_volume_usdt DESC) as rank,
            PERCENT_RANK() OVER (PARTITION BY date ORDER BY quote_volume_usdt DESC) * 100 as percentile,
            quote_volume_usdt / NULLIF(SUM(quote_volume_usdt) OVER (PARTITION BY date), 0) * 100 as market_share_pct
        FROM daily_availability
        WHERE available = TRUE
          AND quote_volume_usdt IS NOT NULL
          {date_filter}
    ),
    trailing_availability AS (
        SELECT
            symbol,
            date,
            COUNT(*) OVER (
                PARTITION BY symbol
                ORDER BY date
                ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
            ) as days_available_30d
        FROM daily_availability
        WHERE available = TRUE
          AND quote_volume_usdt IS NOT NULL
          {date_filter}
    ),
    rank_changes AS (
        SELECT
            date,
            symbol,
            rank as current_rank,
            LAG(rank, 1) OVER (PARTITION BY symbol ORDER BY date) as rank_1d_ago,
            LAG(rank, 7) OVER (PARTITION BY symbol ORDER BY date) as rank_7d_ago,
            LAG(rank, 14) OVER (PARTITION BY symbol ORDER BY date) as rank_14d_ago,
            LAG(rank, 30) OVER (PARTITION BY symbol ORDER BY date) as rank_30d_ago
        FROM daily_ranks
    )
    SELECT
        dr.date,
        dr.symbol,
        CAST(dr.rank AS SMALLINT) as rank,
        dr.quote_volume_usdt,
        dr.trade_count,
        CAST(rc.current_rank - rc.rank_1d_ago AS SMALLINT) as rank_change_1d,
        CAST(rc.current_rank - rc.rank_7d_ago AS SMALLINT) as rank_change_7d,
        CAST(rc.current_rank - rc.rank_14d_ago AS SMALLINT) as rank_change_14d,
        CAST(rc.current_rank - rc.rank_30d_ago AS SMALLINT) as rank_change_30d,
        CAST(dr.percentile AS FLOAT) as percentile,
        CAST(dr.market_share_pct AS FLOAT) as market_share_pct,
        CAST(COALESCE(ta.days_available_30d, 0) AS TINYINT) as days_available,
        CURRENT_TIMESTAMP as generation_timestamp
    FROM daily_ranks dr
    JOIN rank_changes rc ON dr.date = rc.date AND dr.symbol = rc.symbol
    LEFT JOIN trailing_availability ta ON dr.date = ta.date AND dr.symbol = ta.symbol
    ORDER BY dr.date, dr.rank
    """


def query_rankings(db_path: Path, start_date: str | None, logger: logging.Logger | None = None) -> pa.Table:
    """
    Query database for volume rankings.

    Args:
        db_path: Path to DuckDB database
        start_date: Optional start date for incremental append
        logger: Logger instance (optional, defaults to None for testing)

    Returns:
        PyArrow Table with rankings data

    Raises:
        RuntimeError: If database query fails
    """
    if not db_path.exists():
        raise RuntimeError(f"Database not found: {db_path}")

    try:
        if logger:
            logger.info(f"Connecting to database: {db_path}")
        conn = duckdb.connect(str(db_path), read_only=True)

        sql = generate_rankings_sql(start_date)
        if logger:
            logger.info(f"Querying rankings (start_date={start_date or 'all history'})")

        # Execute query and convert to PyArrow
        result = conn.execute(sql).fetch_arrow_table()

        if logger:
            logger.info(f"Query returned {len(result):,} rows")

        conn.close()
        return result

    except Exception as e:
        raise RuntimeError(f"Rankings query failed: {e}") from e


def validate_rankings_table(table: pa.Table, logger: logging.Logger | None = None) -> None:
    """
    Validate rankings table schema and data quality.

    Args:
        table: PyArrow table to validate
        logger: Logger instance (optional, defaults to None for testing)

    Raises:
        ValueError: If validation fails
    """
    # Check schema matches specification
    if not table.schema.equals(RANKINGS_SCHEMA):
        raise ValueError(
            f"Schema mismatch:\nExpected: {RANKINGS_SCHEMA}\nActual: {table.schema}"
        )

    # Check row count reasonable
    if len(table) == 0:
        raise ValueError("Rankings table is empty (no rows)")

    if len(table) > 2_000_000:  # Sanity check: ~2K dates × 700 symbols = 1.4M rows
        if logger:
            logger.warning(f"Unexpectedly large table: {len(table):,} rows")

    # Check ranks are positive
    ranks = table['rank'].to_pylist()
    if any(r is None or r < 1 for r in ranks):
        raise ValueError("Invalid ranks found (NULL or <1)")

    if logger:
        logger.info("✅ Table validation passed")


def write_parquet(table: pa.Table, output_path: Path, logger: logging.Logger | None = None) -> None:
    """
    Write rankings table to Parquet file with compression.

    Args:
        table: PyArrow table to write
        output_path: Output Parquet file path
        logger: Logger instance (optional, defaults to None for testing)

    Raises:
        RuntimeError: If write fails
    """
    try:
        pq.write_table(
            table,
            output_path,
            compression='snappy',
            use_dictionary=True,
            version='2.6',  # Modern Parquet format
        )

        file_size_mb = output_path.stat().st_size / 1024 / 1024
        if logger:
            logger.info(f"✅ Wrote Parquet: {output_path} ({file_size_mb:.1f} MB)")

    except Exception as e:
        raise RuntimeError(f"Failed to write Parquet: {e}") from e


def merge_tables(existing_table: pa.Table, new_table: pa.Table, logger: logging.Logger | None = None) -> pa.Table:
    """
    Merge existing and new rankings tables (append new rows).

    Args:
        existing_table: Existing historical rankings
        new_table: New rankings to append
        logger: Logger instance (optional, defaults to None for testing)

    Returns:
        Merged PyArrow table

    Raises:
        ValueError: If tables have duplicate dates
    """
    # Check for overlapping dates
    existing_dates = set(existing_table['date'].to_pylist())
    new_dates = set(new_table['date'].to_pylist())

    overlap = existing_dates & new_dates
    if overlap:
        raise ValueError(
            f"Duplicate dates found (cannot append): {sorted(overlap)[:5]}..."
        )

    # Concatenate tables
    merged = pa.concat_tables([existing_table, new_table])

    if logger:
        logger.info(
            f"Merged tables: {len(existing_table):,} existing + "
            f"{len(new_table):,} new = {len(merged):,} total rows"
        )

    return merged


def main() -> int:
    """
    Main ranking generation execution.

    Returns:
        0 on success, 1 on failure
    """
    parser = argparse.ArgumentParser(
        description="Generate volume rankings time-series Parquet archive (ADR-0013)"
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        required=True,
        help="Path to DuckDB database (availability.duckdb)",
    )
    parser.add_argument(
        "--existing-file",
        type=Path,
        help="Path to existing Parquet file (for incremental append)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output Parquet file path",
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
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger(__name__)

    logger.info("=" * 70)
    logger.info("Volume Rankings Time-Series Generation (ADR-0013)")
    logger.info("=" * 70)
    logger.info("")

    try:
        # Determine if incremental append or full generation
        start_date = None
        existing_table = None

        if args.existing_file and args.existing_file.exists():
            logger.info(f"Existing file found: {args.existing_file}")
            start_date = get_latest_date_from_parquet(args.existing_file)

            if start_date:
                logger.info(f"Latest date in existing file: {start_date}")
                logger.info("Mode: INCREMENTAL APPEND")

                # Load existing table for merging
                existing_table = pq.read_table(args.existing_file)
                logger.info(f"Existing table: {len(existing_table):,} rows")
            else:
                logger.info("Could not determine latest date, falling back to full generation")
        else:
            logger.info("No existing file found")
            logger.info("Mode: FULL HISTORICAL GENERATION")

        # Query new rankings from database
        new_table = query_rankings(args.db_path, start_date, logger)

        if len(new_table) == 0:
            logger.info("No new rankings to add (database up to date)")
            return 0

        # Merge with existing if applicable
        if existing_table is not None:
            final_table = merge_tables(existing_table, new_table, logger)
        else:
            final_table = new_table

        # Validate final table
        validate_rankings_table(final_table, logger)

        # Write Parquet file
        write_parquet(final_table, args.output, logger)

        # Print summary
        dates = final_table['date'].to_pandas()
        logger.info("")
        logger.info("=" * 70)
        logger.info("SUMMARY")
        logger.info("=" * 70)
        logger.info(f"Total rows: {len(final_table):,}")
        logger.info(f"Date range: {dates.min()} to {dates.max()}")
        logger.info(f"Unique dates: {dates.nunique():,}")
        logger.info(f"Output file: {args.output}")
        logger.info("=" * 70)

        return 0

    except Exception as e:
        logger.error(f"Rankings generation failed: {e}", exc_info=args.verbose)
        logger.error("=" * 70)
        return 1


if __name__ == "__main__":
    sys.exit(main())
