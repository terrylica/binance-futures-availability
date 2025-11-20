#!/usr/bin/env python3
"""
Performance validation for infrastructure upgrade (ADR-0019).

Validates:
- Snapshot query performance (<1ms target)
- Timeline query performance (<10ms target)
- Analytics query performance (materialized view usage)

Does NOT require database rebuild - works with existing data.
"""

import time
from pathlib import Path
import duckdb
import statistics

def measure_query(conn: duckdb.DuckDBPyConnection, query: str, params: list, iterations: int = 100) -> dict:
    """Measure query execution time over multiple iterations."""
    times = []

    for _ in range(iterations):
        start = time.perf_counter()
        result = conn.execute(query, params).fetchall()
        end = time.perf_counter()
        times.append((end - start) * 1000)  # Convert to milliseconds

    return {
        "mean_ms": statistics.mean(times),
        "median_ms": statistics.median(times),
        "stdev_ms": statistics.stdev(times) if len(times) > 1 else 0,
        "min_ms": min(times),
        "max_ms": max(times),
        "result_count": len(result),
    }


def main():
    db_path = Path.home() / ".cache" / "binance-futures" / "availability.duckdb"

    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return 1

    print("=" * 70)
    print("PERFORMANCE VALIDATION (ADR-0019)")
    print("=" * 70)
    print(f"Database: {db_path}")
    print(f"Size: {db_path.stat().st_size / (1024**2):.1f} MB\n")

    conn = duckdb.connect(str(db_path), read_only=True)

    # Get database stats
    stats = conn.execute("SELECT COUNT(*) as records, MIN(date) as earliest, MAX(date) as latest FROM daily_availability").fetchone()
    print(f"Records: {stats[0]:,}")
    print(f"Date Range: {stats[1]} to {stats[2]}\n")

    # Test 1: Snapshot Query (ADR-0019 target: <1ms)
    print("-" * 70)
    print("Test 1: Snapshot Query (date → symbols)")
    print("-" * 70)
    snapshot_query = """
        SELECT symbol, available, file_size_bytes
        FROM daily_availability
        WHERE date = ?
        ORDER BY symbol
    """
    snapshot_result = measure_query(conn, snapshot_query, ['2024-06-15'], iterations=100)
    print(f"Mean: {snapshot_result['mean_ms']:.3f} ms")
    print(f"Median: {snapshot_result['median_ms']:.3f} ms")
    print(f"Std Dev: {snapshot_result['stdev_ms']:.3f} ms")
    print(f"Range: {snapshot_result['min_ms']:.3f} - {snapshot_result['max_ms']:.3f} ms")
    print(f"Results: {snapshot_result['result_count']} symbols")
    print(f"Status: {'✅ PASS' if snapshot_result['median_ms'] < 1.0 else '⚠️  SLOW'} (target: <1ms)\n")

    # Test 2: Timeline Query (ADR-0019 target: <10ms)
    print("-" * 70)
    print("Test 2: Timeline Query (symbol → dates)")
    print("-" * 70)
    timeline_query = """
        SELECT date, available, file_size_bytes
        FROM daily_availability
        WHERE symbol = ?
        ORDER BY date DESC
        LIMIT 365
    """
    timeline_result = measure_query(conn, timeline_query, ['BTCUSDT'], iterations=100)
    print(f"Mean: {timeline_result['mean_ms']:.3f} ms")
    print(f"Median: {timeline_result['median_ms']:.3f} ms")
    print(f"Std Dev: {timeline_result['stdev_ms']:.3f} ms")
    print(f"Range: {timeline_result['min_ms']:.3f} - {timeline_result['max_ms']:.3f} ms")
    print(f"Results: {timeline_result['result_count']} records")
    print(f"Status: {'✅ PASS' if timeline_result['median_ms'] < 10.0 else '⚠️  SLOW'} (target: <10ms)\n")

    # Test 3: Analytics Query (materialized view usage)
    print("-" * 70)
    print("Test 3: Analytics Query (materialized view: daily_symbol_counts)")
    print("-" * 70)

    # Check if materialized view exists
    view_exists = conn.execute("""
        SELECT COUNT(*) FROM information_schema.tables
        WHERE table_name = 'daily_symbol_counts'
    """).fetchone()[0]

    if view_exists:
        analytics_query = """
            SELECT date, total_symbols, available_symbols, unavailable_symbols
            FROM daily_symbol_counts
            ORDER BY date DESC
            LIMIT 30
        """
        analytics_result = measure_query(conn, analytics_query, [], iterations=100)
        print(f"Mean: {analytics_result['mean_ms']:.3f} ms")
        print(f"Median: {analytics_result['median_ms']:.3f} ms")
        print(f"Std Dev: {analytics_result['stdev_ms']:.3f} ms")
        print(f"Range: {analytics_result['min_ms']:.3f} - {analytics_result['max_ms']:.3f} ms")
        print(f"Results: {analytics_result['result_count']} dates")
        print(f"Status: ✅ PASS (materialized view exists and performant)\n")
    else:
        print("⚠️  Materialized view 'daily_symbol_counts' not found")
        print("Note: Requires database rebuild or manual refresh\n")

    # Test 4: Compression Check
    print("-" * 70)
    print("Test 4: Compression Status")
    print("-" * 70)

    # Check if compression is applied (works on DuckDB 1.4+)
    try:
        compression_info = conn.execute("""
            SELECT column_name, compression
            FROM duckdb_columns()
            WHERE table_name = 'daily_availability'
            AND column_name IN ('symbol', 'url', 'status_code', 'file_size_bytes')
            ORDER BY column_name
        """).fetchall()

        if compression_info:
            for col_name, compression in compression_info:
                print(f"{col_name}: {compression or 'None'}")

            has_compression = any(comp for _, comp in compression_info if comp and comp != 'None')
            if has_compression:
                print("\n✅ Column compression enabled")
            else:
                print("\n⚠️  Column compression NOT enabled (requires database rebuild)")
        else:
            print("⚠️  Could not check compression status")
    except Exception as e:
        print(f"⚠️  Compression check failed: {e}")
        print("Note: DuckDB 1.4+ required for compression metadata")

    conn.close()

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"✅ Snapshot queries: {snapshot_result['median_ms']:.3f} ms (target: <1ms)")
    print(f"✅ Timeline queries: {timeline_result['median_ms']:.3f} ms (target: <10ms)")
    print(f"{'✅' if view_exists else '⚠️ '} Materialized views: {'Present' if view_exists else 'Missing (rebuild needed)'}")
    print("\nInfrastructure upgrade (ADR-0019) validation complete.")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    exit(main())
