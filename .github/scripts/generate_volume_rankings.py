#!/usr/bin/env python3
"""
Generate volume rankings time-series Parquet archive.

Calculates daily volume rankings for all symbols using quote_volume_usdt metric,
tracks rank changes over 1-day, 7-day, 14-day, and 30-day windows, and outputs
single cumulative Parquet file for analytical database consumption.

Always regenerated in full from the database (~1s): rankings are a derived view, so
volume that arrives late (T+1 lag, catch-up backfills) is reflected on the next run, and
LAG()-based rank changes always see full history.

Usage:
    uv run python .github/scripts/generate_volume_rankings.py \\
        --db-path ~/.cache/binance-futures/availability.duckdb \\
        --output volume-rankings-timeseries.parquet

See: docs/architecture/decisions/0013-volume-rankings-timeseries.md
"""

import argparse
import logging
import sys
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
# Note: DuckDB returns signed integers (SMALLINT=int16, BIGINT=int64, TINYINT=int8)
# even though these values are semantically unsigned (ranks, counts, days).
# We use signed types to match DuckDB's output and avoid casting overhead.
RANKINGS_SCHEMA = pa.schema(
    [
        ("date", pa.date32()),
        ("symbol", pa.string()),
        ("rank", pa.int16()),  # DuckDB SMALLINT (signed)
        ("quote_volume_usdt", pa.float64()),
        ("trade_count", pa.int64()),  # DuckDB BIGINT (signed)
        ("rank_change_1d", pa.int16()),
        ("rank_change_7d", pa.int16()),
        ("rank_change_14d", pa.int16()),
        ("rank_change_30d", pa.int16()),
        ("percentile", pa.float32()),
        ("market_share_pct", pa.float32()),
        ("days_available", pa.int8()),  # DuckDB TINYINT (signed)
        ("generation_timestamp", pa.timestamp("us")),  # Allow timezone from CURRENT_TIMESTAMP
    ]
)


def generate_rankings_sql() -> str:
    """
    Generate SQL query for volume rankings with rank change tracking.

    Uses DENSE_RANK() for consistent rankings (no gaps when ties exist).
    Calculates rank changes over 1d, 7d, 14d, 30d windows using LAG().

    Returns:
        SQL query string
    """
    return """
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
        CAST(CURRENT_TIMESTAMP AS TIMESTAMP) as generation_timestamp
    FROM daily_ranks dr
    JOIN rank_changes rc ON dr.date = rc.date AND dr.symbol = rc.symbol
    LEFT JOIN trailing_availability ta ON dr.date = ta.date AND dr.symbol = ta.symbol
    ORDER BY dr.date, dr.rank
    """


def query_rankings(db_path: Path, logger: logging.Logger | None = None) -> pa.Table:
    """
    Query database for volume rankings.

    Args:
        db_path: Path to DuckDB database
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

        sql = generate_rankings_sql()
        if logger:
            logger.info("Querying rankings (full history)")

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
        raise ValueError(f"Schema mismatch:\nExpected: {RANKINGS_SCHEMA}\nActual: {table.schema}")

    # Check row count reasonable
    if len(table) == 0:
        raise ValueError("Rankings table is empty (no rows)")

    if logger and len(table) > 2_000_000:  # Sanity check: ~2.5K dates × ~800 symbols
        logger.warning(f"Unexpectedly large table: {len(table):,} rows")

    # Check ranks are positive
    ranks = table["rank"].to_pylist()
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
            compression="snappy",
            use_dictionary=True,
            version="2.6",  # Modern Parquet format
        )

        file_size_mb = output_path.stat().st_size / 1024 / 1024
        if logger:
            logger.info(f"✅ Wrote Parquet: {output_path} ({file_size_mb:.1f} MB)")

    except Exception as e:
        raise RuntimeError(f"Failed to write Parquet: {e}") from e


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
        final_table = query_rankings(args.db_path, logger)

        # Validate final table
        validate_rankings_table(final_table, logger)

        # Write Parquet file
        write_parquet(final_table, args.output, logger)

        # Print summary (using PyArrow compute, no pandas dependency)
        import pyarrow.compute as pc

        date_col = final_table["date"]
        min_date = pc.min(date_col).as_py()
        max_date = pc.max(date_col).as_py()
        unique_dates = pc.count_distinct(date_col).as_py()

        logger.info("")
        logger.info("=" * 70)
        logger.info("SUMMARY")
        logger.info("=" * 70)
        logger.info(f"Total rows: {len(final_table):,}")
        logger.info(f"Date range: {min_date} to {max_date}")
        logger.info(f"Unique dates: {unique_dates:,}")
        logger.info(f"Output file: {args.output}")
        logger.info("=" * 70)

        return 0

    except Exception as e:
        logger.error(f"Rankings generation failed: {e}", exc_info=args.verbose)
        logger.error("=" * 70)
        return 1


if __name__ == "__main__":
    sys.exit(main())
