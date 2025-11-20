#!/usr/bin/env python3
"""
Micro-benchmarks for DuckDB optimization opportunities.

Tests:
1. Compression impact on query performance
2. Index effectiveness for different query patterns
3. Bulk insert strategies
4. Column-specific compression
5. Write-to-read ratio with various configurations
"""

import datetime
import statistics
import sys
import time
from pathlib import Path
from typing import Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "binance-futures-availability" / "src"))

import duckdb

# Test data constants
NUM_SYMBOLS = 327
NUM_DAYS = 365
TOTAL_RECORDS = NUM_SYMBOLS * NUM_DAYS


def create_test_data(num_records: int) -> list[dict[str, Any]]:
    """Generate test records matching schema."""
    records = []
    symbols = [f"SYM{i:04d}USDT" for i in range(NUM_SYMBOLS)]

    for day in range(NUM_DAYS):
        for idx, symbol in enumerate(symbols):
            date = datetime.date(2024, 1, 1) + datetime.timedelta(days=day)
            records.append({
                'date': date,
                'symbol': symbol,
                'available': (idx + day) % 2 == 0,  # 50% available
                'file_size_bytes': 1000000 + (idx * 100),
                'last_modified': datetime.datetime(2024, 1, 1, 12, 0, 0),
                'url': f'https://data.binance.vision/{symbol}/{date}',
                'status_code': 200 if ((idx + day) % 2 == 0) else 404,
                'probe_timestamp': datetime.datetime.now(datetime.timezone.utc),
            })

    return records


def create_schema_standard(conn: duckdb.DuckDBPyConnection) -> None:
    """Create schema without compression."""
    conn.execute("""
        CREATE TABLE daily_availability_standard (
            date DATE NOT NULL,
            symbol VARCHAR NOT NULL,
            available BOOLEAN NOT NULL,
            file_size_bytes BIGINT,
            last_modified TIMESTAMP,
            url VARCHAR NOT NULL,
            status_code INTEGER NOT NULL,
            probe_timestamp TIMESTAMP NOT NULL,
            PRIMARY KEY (date, symbol)
        )
    """)
    conn.execute("CREATE INDEX idx_symbol_date_std ON daily_availability_standard(symbol, date)")
    conn.execute("CREATE INDEX idx_available_date_std ON daily_availability_standard(available, date)")


def create_schema_with_compression(conn: duckdb.DuckDBPyConnection) -> None:
    """Create schema with per-column compression."""
    conn.execute("""
        CREATE TABLE daily_availability_compressed (
            date DATE NOT NULL,
            symbol VARCHAR NOT NULL USING COMPRESSION dict,
            available BOOLEAN NOT NULL,
            file_size_bytes BIGINT USING COMPRESSION bitpacking,
            last_modified TIMESTAMP,
            url VARCHAR NOT NULL USING COMPRESSION dict,
            status_code INTEGER NOT NULL USING COMPRESSION bitpacking,
            probe_timestamp TIMESTAMP NOT NULL,
            PRIMARY KEY (date, symbol)
        )
    """)
    conn.execute("CREATE INDEX idx_symbol_date_comp ON daily_availability_compressed(symbol, date)")
    conn.execute("CREATE INDEX idx_available_date_comp ON daily_availability_compressed(available, date)")


def benchmark_insert_performance(
    conn: duckdb.DuckDBPyConnection,
    table_name: str,
    records: list[dict[str, Any]],
    batch_size: int = 1000,
) -> float:
    """
    Benchmark insertion performance.

    Returns: Time in seconds
    """
    start = time.perf_counter()

    # Bulk insert with transactions
    conn.execute("BEGIN TRANSACTION")
    for i in range(0, len(records), batch_size):
        batch = records[i:i+batch_size]
        conn.executemany(
            f"""
            INSERT OR REPLACE INTO {table_name}
            (date, symbol, available, file_size_bytes, last_modified, url, status_code, probe_timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    r['date'], r['symbol'], r['available'], r['file_size_bytes'],
                    r['last_modified'], r['url'], r['status_code'], r['probe_timestamp']
                )
                for r in batch
            ],
        )
    conn.execute("COMMIT")

    end = time.perf_counter()
    return end - start


def benchmark_snapshot_query(
    conn: duckdb.DuckDBPyConnection,
    table_name: str,
    date: datetime.date,
    trials: int = 5,
) -> tuple[float, float]:
    """
    Benchmark snapshot query (get all symbols on a date).

    Returns: (mean_time, std_dev)
    """
    times = []
    for _ in range(trials):
        start = time.perf_counter()
        result = conn.execute(
            f"""
            SELECT symbol, file_size_bytes, last_modified
            FROM {table_name}
            WHERE date = ? AND available = true
            ORDER BY symbol
            """,
            [date],
        ).fetchall()
        end = time.perf_counter()
        times.append(end - start)

    return (statistics.mean(times), statistics.stdev(times) if len(times) > 1 else 0.0)


def benchmark_timeline_query(
    conn: duckdb.DuckDBPyConnection,
    table_name: str,
    symbol: str,
    trials: int = 5,
) -> tuple[float, float]:
    """
    Benchmark timeline query (get all dates for a symbol).

    Returns: (mean_time, std_dev)
    """
    times = []
    for _ in range(trials):
        start = time.perf_counter()
        result = conn.execute(
            f"""
            SELECT date, available, file_size_bytes, status_code
            FROM {table_name}
            WHERE symbol = ?
            ORDER BY date
            """,
            [symbol],
        ).fetchall()
        end = time.perf_counter()
        times.append(end - start)

    return (statistics.mean(times), statistics.stdev(times) if len(times) > 1 else 0.0)


def benchmark_analytics_query(
    conn: duckdb.DuckDBPyConnection,
    table_name: str,
    trials: int = 5,
) -> tuple[float, float]:
    """
    Benchmark analytics query (count available symbols by date).

    Returns: (mean_time, std_dev)
    """
    times = []
    for _ in range(trials):
        start = time.perf_counter()
        result = conn.execute(
            f"""
            SELECT date, COUNT(*) as available_count
            FROM {table_name}
            WHERE available = true
            GROUP BY date
            ORDER BY date
            """
        ).fetchall()
        end = time.perf_counter()
        times.append(end - start)

    return (statistics.mean(times), statistics.stdev(times) if len(times) > 1 else 0.0)


def get_database_size(conn: duckdb.DuckDBPyConnection, table_name: str) -> int:
    """Get table size in bytes."""
    result = conn.execute(
        f"SELECT sum(memory_usage) FROM (SELECT * FROM duckdb_databases() WHERE database_name = 'memory')"
    ).fetchall()

    # Approximate: just count rows for this test
    rows = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchall()[0][0]
    return rows


def main():
    """Run all benchmarks."""
    print("="*70)
    print("DUCKDB MICRO-BENCHMARKS")
    print("="*70)
    print(f"Test Data: {NUM_SYMBOLS} symbols × {NUM_DAYS} days = {TOTAL_RECORDS} records")
    print()

    # Generate test data
    print("Generating test data...")
    records = create_test_data(TOTAL_RECORDS)

    # Test configurations
    configs = [
        ("Standard (No Compression)", create_schema_standard, "daily_availability_standard"),
        ("With Compression", create_schema_with_compression, "daily_availability_compressed"),
    ]

    results = {}

    for config_name, schema_func, table_name in configs:
        print(f"\n{'='*70}")
        print(f"Configuration: {config_name}")
        print(f"Table: {table_name}")
        print(f"{'='*70}")

        # Create fresh database for each config
        db_path = f"/tmp/benchmark_{table_name}.duckdb"
        Path(db_path).unlink(missing_ok=True)

        conn = duckdb.connect(db_path)
        try:
            # Create schema
            schema_func(conn)

            # Benchmark insert
            print(f"Inserting {TOTAL_RECORDS} records...", end=" ", flush=True)
            insert_time = benchmark_insert_performance(conn, table_name, records)
            print(f"DONE ({insert_time:.3f}s)")

            # Query benchmarks
            test_date = datetime.date(2024, 6, 15)
            test_symbol = "SYM0000USDT"

            print(f"Benchmarking snapshot query (date={test_date})...", end=" ", flush=True)
            snap_mean, snap_stdev = benchmark_snapshot_query(conn, table_name, test_date)
            print(f"DONE ({snap_mean*1000:.3f}ms ± {snap_stdev*1000:.3f}ms)")

            print(f"Benchmarking timeline query (symbol={test_symbol})...", end=" ", flush=True)
            tline_mean, tline_stdev = benchmark_timeline_query(conn, table_name, test_symbol)
            print(f"DONE ({tline_mean*1000:.3f}ms ± {tline_stdev*1000:.3f}ms)")

            print(f"Benchmarking analytics query...", end=" ", flush=True)
            analytics_mean, analytics_stdev = benchmark_analytics_query(conn, table_name)
            print(f"DONE ({analytics_mean*1000:.3f}ms ± {analytics_stdev*1000:.3f}ms)")

            # Store results
            results[config_name] = {
                'insert_time': insert_time,
                'snapshot_mean': snap_mean,
                'snapshot_stdev': snap_stdev,
                'timeline_mean': tline_mean,
                'timeline_stdev': tline_stdev,
                'analytics_mean': analytics_mean,
                'analytics_stdev': analytics_stdev,
            }

        finally:
            conn.close()
            Path(db_path).unlink(missing_ok=True)

    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}\n")

    print("| Configuration | Insert (s) | Snapshot (ms) | Timeline (ms) | Analytics (ms) |")
    print("|---|---|---|---|---|")
    for config_name, res in results.items():
        print(
            f"| {config_name} | "
            f"{res['insert_time']:.3f} | "
            f"{res['snapshot_mean']*1000:.3f} | "
            f"{res['timeline_mean']*1000:.3f} | "
            f"{res['analytics_mean']*1000:.3f} |"
        )

    # Performance impact analysis
    if len(results) > 1:
        standard = results["Standard (No Compression)"]
        compressed = results["With Compression"]

        print("\n" + "="*70)
        print("COMPRESSION IMPACT")
        print("="*70)

        insert_delta = ((compressed['insert_time'] - standard['insert_time']) / standard['insert_time']) * 100
        snapshot_delta = ((compressed['snapshot_mean'] - standard['snapshot_mean']) / standard['snapshot_mean']) * 100
        timeline_delta = ((compressed['timeline_mean'] - standard['timeline_mean']) / standard['timeline_mean']) * 100
        analytics_delta = ((compressed['analytics_mean'] - standard['analytics_mean']) / standard['analytics_mean']) * 100

        print(f"Insert Performance:   {insert_delta:+.1f}%")
        print(f"Snapshot Query:       {snapshot_delta:+.1f}%")
        print(f"Timeline Query:       {timeline_delta:+.1f}%")
        print(f"Analytics Query:      {analytics_delta:+.1f}%")


if __name__ == "__main__":
    main()
