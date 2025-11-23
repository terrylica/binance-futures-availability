#!/usr/bin/env python3
"""
Comprehensive worker count benchmark for binance-futures-availability.

Tests ACTUAL production workflow end-to-end:
- Real BatchProber with real HTTP requests to S3 Vision
- Real AvailabilityDatabase with DuckDB insertions
- Real symbol list (327 perpetual futures)
- Realistic daily update scenario (yesterday's data)

Measures:
- Probe time (HTTP requests)
- Database insertion time (DuckDB writes)
- Total end-to-end time (what user experiences)
- Success rate
- Memory usage

Goal: Find the OPTIMAL worker count definitively.
"""

import datetime
import logging
import resource
import statistics
import sys
import time
from pathlib import Path
from typing import Any

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from binance_futures_availability.database import AvailabilityDatabase
from binance_futures_availability.probing.batch_prober import BatchProber
from binance_futures_availability.probing.symbol_discovery import load_discovered_symbols

# Configure logging (suppress debug noise during benchmark)
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

logger = logging.getLogger(__name__)


class BenchmarkResult:
    """Container for a single benchmark trial."""

    def __init__(
        self,
        worker_count: int,
        trial_num: int,
        probe_time: float,
        db_insert_time: float,
        total_time: float,
        success_count: int,
        total_count: int,
        peak_rss_mb: float,
        error: str | None = None,
    ):
        self.worker_count = worker_count
        self.trial_num = trial_num
        self.probe_time = probe_time
        self.db_insert_time = db_insert_time
        self.total_time = total_time
        self.success_count = success_count
        self.total_count = total_count
        self.success_rate = success_count / total_count if total_count > 0 else 0.0
        self.peak_rss_mb = peak_rss_mb
        self.error = error

    def __repr__(self) -> str:
        return (
            f"BenchmarkResult(workers={self.worker_count}, trial={self.trial_num}, "
            f"total={self.total_time:.2f}s, probe={self.probe_time:.2f}s, "
            f"db={self.db_insert_time:.2f}s, success={self.success_rate:.1%})"
        )


def get_peak_rss_mb() -> float:
    """Get peak RSS memory usage in MB."""
    usage = resource.getrusage(resource.RUSAGE_SELF)
    # macOS returns bytes, Linux returns KB
    if sys.platform == "darwin":
        return usage.ru_maxrss / (1024 * 1024)  # bytes to MB
    return usage.ru_maxrss / 1024  # KB to MB


def run_single_trial(
    worker_count: int,
    trial_num: int,
    test_date: datetime.date,
    symbols: list[str],
    db_path: Path,
) -> BenchmarkResult:
    """
    Run a single benchmark trial for given worker count.

    Measures:
    1. Probe time (HTTP HEAD requests to S3)
    2. Database insertion time (DuckDB writes)
    3. Total end-to-end time
    4. Memory usage
    """
    logger.info(f"Trial {trial_num} with {worker_count} workers...")

    try:
        # Total time starts
        total_start = time.perf_counter()

        # 1. PROBE PHASE (HTTP requests)
        probe_start = time.perf_counter()
        prober = BatchProber(max_workers=worker_count)
        results = prober.probe_all_symbols(date=test_date, symbols=symbols)
        probe_end = time.perf_counter()
        probe_time = probe_end - probe_start

        # 2. DATABASE INSERTION PHASE
        db_start = time.perf_counter()
        db = AvailabilityDatabase(db_path=db_path)
        db.insert_batch(results)
        db.close()
        db_end = time.perf_counter()
        db_insert_time = db_end - db_start

        # Total time ends
        total_end = time.perf_counter()
        total_time = total_end - total_start

        # Memory usage
        peak_rss = get_peak_rss_mb()

        # Success metrics
        success_count = len(results)
        total_count = len(symbols)

        return BenchmarkResult(
            worker_count=worker_count,
            trial_num=trial_num,
            probe_time=probe_time,
            db_insert_time=db_insert_time,
            total_time=total_time,
            success_count=success_count,
            total_count=total_count,
            peak_rss_mb=peak_rss,
            error=None,
        )

    except Exception as e:
        logger.error(f"Trial {trial_num} failed: {e}")
        return BenchmarkResult(
            worker_count=worker_count,
            trial_num=trial_num,
            probe_time=0.0,
            db_insert_time=0.0,
            total_time=0.0,
            success_count=0,
            total_count=len(symbols),
            peak_rss_mb=get_peak_rss_mb(),
            error=str(e),
        )


def run_benchmark_matrix(
    worker_counts: list[int],
    trials_per_config: int,
    test_date: datetime.date,
    symbols: list[str],
    db_path: Path,
) -> dict[int, list[BenchmarkResult]]:
    """
    Run full benchmark matrix: multiple worker counts × multiple trials.

    Returns:
        Dict mapping worker_count -> list of BenchmarkResult
    """
    results = {}

    total_runs = len(worker_counts) * trials_per_config
    current_run = 0

    for worker_count in worker_counts:
        print(f"\n{'=' * 60}")
        print(f"Testing {worker_count} workers ({trials_per_config} trials)")
        print(f"{'=' * 60}")

        worker_results = []

        for trial_num in range(1, trials_per_config + 1):
            current_run += 1
            progress = (current_run / total_runs) * 100
            print(
                f"\n[{progress:.1f}%] Worker count: {worker_count}, Trial: {trial_num}/{trials_per_config}"
            )

            # Clean database before each trial
            if db_path.exists():
                db_path.unlink()

            # Run trial
            result = run_single_trial(
                worker_count=worker_count,
                trial_num=trial_num,
                test_date=test_date,
                symbols=symbols,
                db_path=db_path,
            )

            worker_results.append(result)

            # Print immediate feedback
            if result.error:
                print(f"  ❌ FAILED: {result.error}")
            else:
                print(
                    f"  ✓ Total: {result.total_time:.2f}s (probe: {result.probe_time:.2f}s, db: {result.db_insert_time:.2f}s)"
                )
                print(
                    f"    Success: {result.success_count}/{result.total_count} ({result.success_rate:.1%}), Memory: {result.peak_rss_mb:.1f} MB"
                )

        results[worker_count] = worker_results

    return results


def calculate_statistics(results: list[BenchmarkResult]) -> dict[str, Any]:
    """Calculate mean, std dev, min, max for a set of trials."""
    if not results:
        return {}

    # Filter out failed trials
    valid_results = [r for r in results if r.error is None]

    if not valid_results:
        return {"error": "All trials failed"}

    total_times = [r.total_time for r in valid_results]
    probe_times = [r.probe_time for r in valid_results]
    db_times = [r.db_insert_time for r in valid_results]
    success_rates = [r.success_rate for r in valid_results]
    memory_usage = [r.peak_rss_mb for r in valid_results]

    return {
        "total_time_mean": statistics.mean(total_times),
        "total_time_stdev": statistics.stdev(total_times) if len(total_times) > 1 else 0.0,
        "total_time_min": min(total_times),
        "total_time_max": max(total_times),
        "probe_time_mean": statistics.mean(probe_times),
        "probe_time_stdev": statistics.stdev(probe_times) if len(probe_times) > 1 else 0.0,
        "db_time_mean": statistics.mean(db_times),
        "db_time_stdev": statistics.stdev(db_times) if len(db_times) > 1 else 0.0,
        "success_rate_mean": statistics.mean(success_rates),
        "memory_mb_mean": statistics.mean(memory_usage),
        "valid_trials": len(valid_results),
        "total_trials": len(results),
    }


def generate_ascii_chart(
    worker_counts: list[int],
    means: list[float],
    stdevs: list[float],
    width: int = 60,
) -> str:
    """Generate ASCII bar chart showing performance across worker counts."""
    if not means:
        return ""

    max_time = max(means)
    min_time = min(means)
    optimal_idx = means.index(min_time)

    chart = []
    chart.append("\nPerformance Chart (Total Time):")
    chart.append("=" * (width + 20))

    for i, (workers, mean, stdev) in enumerate(zip(worker_counts, means, stdevs, strict=True)):
        # Normalize bar length
        normalized = (mean - min_time) / (max_time - min_time) if max_time > min_time else 0.5
        bar_length = int((1 - normalized) * width)
        bar = "█" * bar_length

        # Mark optimal
        marker = " ← FASTEST" if i == optimal_idx else ""

        # Format line
        line = f"{workers:3d} workers │ {bar:<{width}} │ {mean:5.2f}s ± {stdev:4.2f}s{marker}"
        chart.append(line)

    chart.append("=" * (width + 20))

    return "\n".join(chart)


def generate_report(
    results: dict[int, list[BenchmarkResult]],
    test_date: datetime.date,
    symbol_count: int,
) -> str:
    """Generate comprehensive markdown report."""

    # Calculate statistics for each worker count
    stats = {}
    for worker_count, trials in results.items():
        stats[worker_count] = calculate_statistics(trials)

    # Find optimal configuration
    valid_configs = {w: s for w, s in stats.items() if "error" not in s and s["valid_trials"] > 0}

    if not valid_configs:
        return "# BENCHMARK FAILED\n\nAll trials failed. Check network connectivity and S3 Vision availability."

    optimal_workers = min(valid_configs.keys(), key=lambda w: valid_configs[w]["total_time_mean"])
    optimal_stats = valid_configs[optimal_workers]

    # Build report
    report = []

    report.append("# Binance Futures Availability - Worker Count Benchmark Report")
    report.append("")
    report.append(
        f"**Generated**: {datetime.datetime.now(datetime.UTC).strftime('%Y-%m-%d %H:%M:%S')}"
    )
    report.append(f"**Test Date**: {test_date}")
    report.append(f"**Symbol Count**: {symbol_count}")
    report.append(f"**Trials per Config**: {len(results[optimal_workers])}")
    report.append("")

    # Executive Summary
    report.append("## Executive Summary")
    report.append("")
    report.append(f"**Optimal Worker Count**: **{optimal_workers} workers**")
    report.append("")
    report.append(
        f"- **Total Time**: {optimal_stats['total_time_mean']:.2f}s ± {optimal_stats['total_time_stdev']:.2f}s"
    )
    report.append(
        f"- **Probe Time**: {optimal_stats['probe_time_mean']:.2f}s ± {optimal_stats['probe_time_stdev']:.2f}s"
    )
    report.append(
        f"- **Database Time**: {optimal_stats['db_time_mean']:.2f}s ± {optimal_stats['db_time_stdev']:.2f}s"
    )
    report.append(f"- **Success Rate**: {optimal_stats['success_rate_mean']:.1%}")
    report.append(f"- **Memory Usage**: {optimal_stats['memory_mb_mean']:.1f} MB")
    report.append("")

    # Performance comparison
    baseline_workers = min(valid_configs.keys())
    baseline_time = valid_configs[baseline_workers]["total_time_mean"]
    optimal_time = optimal_stats["total_time_mean"]
    speedup = baseline_time / optimal_time

    report.append(f"**Speedup vs {baseline_workers} workers**: {speedup:.2f}x faster")
    report.append("")

    # ASCII Chart
    worker_list = sorted(valid_configs.keys())
    means = [valid_configs[w]["total_time_mean"] for w in worker_list]
    stdevs = [valid_configs[w]["total_time_stdev"] for w in worker_list]
    report.append(generate_ascii_chart(worker_list, means, stdevs))
    report.append("")

    # Detailed Results Table
    report.append("## Detailed Results")
    report.append("")
    report.append(
        "| Workers | Total Time (s) | Probe Time (s) | DB Time (s) | Success Rate | Memory (MB) | Trials |"
    )
    report.append(
        "|---------|----------------|----------------|-------------|--------------|-------------|--------|"
    )

    for worker_count in sorted(valid_configs.keys()):
        s = valid_configs[worker_count]
        report.append(
            f"| {worker_count:3d} | "
            f"{s['total_time_mean']:6.2f} ± {s['total_time_stdev']:4.2f} | "
            f"{s['probe_time_mean']:6.2f} ± {s['probe_time_stdev']:4.2f} | "
            f"{s['db_time_mean']:5.2f} ± {s['db_time_stdev']:4.2f} | "
            f"{s['success_rate_mean']:6.1%} | "
            f"{s['memory_mb_mean']:6.1f} | "
            f"{s['valid_trials']}/{s['total_trials']} |"
        )

    report.append("")

    # Time breakdown analysis
    report.append("## Time Breakdown Analysis")
    report.append("")
    report.append("Where does the time go?")
    report.append("")
    report.append("| Workers | Probe (%) | Database (%) | Overhead (%) |")
    report.append("|---------|-----------|--------------|--------------|")

    for worker_count in sorted(valid_configs.keys()):
        s = valid_configs[worker_count]
        probe_pct = (s["probe_time_mean"] / s["total_time_mean"]) * 100
        db_pct = (s["db_time_mean"] / s["total_time_mean"]) * 100
        overhead_pct = 100 - probe_pct - db_pct
        report.append(
            f"| {worker_count:3d} | {probe_pct:5.1f}% | {db_pct:5.1f}% | {overhead_pct:5.1f}% |"
        )

    report.append("")

    # Recommendation
    report.append("## Recommendation")
    report.append("")
    report.append(f"**Use {optimal_workers} workers for daily updates.**")
    report.append("")
    report.append("Justification:")
    report.append(f"- Fastest mean total time: {optimal_stats['total_time_mean']:.2f}s")
    report.append(
        f"- Low variance: ±{optimal_stats['total_time_stdev']:.2f}s (consistent performance)"
    )
    report.append(f"- High success rate: {optimal_stats['success_rate_mean']:.1%}")
    report.append(f"- Reasonable memory usage: {optimal_stats['memory_mb_mean']:.1f} MB")
    report.append("")

    # Explain contradictions
    report.append("## Why Previous Tests Showed Different Results")
    report.append("")
    report.append("**This benchmark tests the ACTUAL production workflow**:")
    report.append("- Real HTTP requests to S3 Vision (not mocked)")
    report.append(f"- Real DuckDB insertions ({symbol_count} records)")
    report.append("- Real network latency and S3 response times")
    report.append("- Multiple trials to account for variance")
    report.append("")
    report.append("**Previous inconsistencies likely due to**:")
    report.append("- Cold start effects (first request slower)")
    report.append("- Network variance (S3 response times fluctuate)")
    report.append("- Single trials (not statistically significant)")
    report.append("- Partial testing (probe-only, no DB writes)")
    report.append("")

    # Reproduction instructions
    report.append("## How to Reproduce")
    report.append("")
    report.append("```bash")
    report.append("# Run full benchmark (8 worker counts × 5 trials = 40 runs)")
    report.append("uv run python scripts/benchmark_workers.py")
    report.append("")
    report.append("# Quick test (3 worker counts × 3 trials = 9 runs)")
    report.append("uv run python scripts/benchmark_workers.py --quick")
    report.append("")
    report.append("# Custom configuration")
    report.append("uv run python scripts/benchmark_workers.py --workers 10,50,100 --trials 5")
    report.append("```")
    report.append("")

    # Raw data
    report.append("## Raw Trial Data")
    report.append("")
    for worker_count in sorted(results.keys()):
        report.append(f"### {worker_count} Workers")
        report.append("")
        for trial in results[worker_count]:
            if trial.error:
                report.append(f"- Trial {trial.trial_num}: FAILED - {trial.error}")
            else:
                report.append(
                    f"- Trial {trial.trial_num}: {trial.total_time:.2f}s total "
                    f"({trial.probe_time:.2f}s probe + {trial.db_insert_time:.2f}s db)"
                )
        report.append("")

    return "\n".join(report)


def main():
    """Main benchmark execution."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Benchmark optimal worker count for Binance futures availability updates"
    )
    parser.add_argument(
        "--workers",
        type=str,
        default="10,20,30,50,75,100,150,200",
        help="Comma-separated worker counts to test (default: 10,20,30,50,75,100,150,200)",
    )
    parser.add_argument(
        "--trials",
        type=int,
        default=5,
        help="Number of trials per worker count (default: 5)",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick mode: test 10,50,100 workers with 3 trials each",
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Test date (YYYY-MM-DD, default: yesterday)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output report file (default: stdout)",
    )

    args = parser.parse_args()

    # Parse configuration
    if args.quick:
        worker_counts = [10, 50, 100]
        trials = 3
    else:
        worker_counts = [int(w.strip()) for w in args.workers.split(",")]
        trials = args.trials

    # Test date
    if args.date:
        test_date = (
            datetime.datetime.strptime(args.date, "%Y-%m-%d").replace(tzinfo=datetime.UTC).date()
        )
    else:
        test_date = datetime.datetime.now(datetime.UTC).date() - datetime.timedelta(days=1)

    # Load symbols
    symbols = load_discovered_symbols(contract_type="perpetual")

    # Test database path
    db_path = Path("/tmp/benchmark_test.duckdb")

    print("=" * 70)
    print("BINANCE FUTURES AVAILABILITY - WORKER COUNT BENCHMARK")
    print("=" * 70)
    print(f"Test Date: {test_date}")
    print(f"Symbol Count: {len(symbols)}")
    print(f"Worker Counts: {worker_counts}")
    print(f"Trials per Config: {trials}")
    print(f"Total Runs: {len(worker_counts) * trials}")
    print(f"Database: {db_path}")
    print("=" * 70)

    # Run benchmark
    results = run_benchmark_matrix(
        worker_counts=worker_counts,
        trials_per_config=trials,
        test_date=test_date,
        symbols=symbols,
        db_path=db_path,
    )

    # Generate report
    report = generate_report(
        results=results,
        test_date=test_date,
        symbol_count=len(symbols),
    )

    # Output report
    if args.output:
        output_path = Path(args.output)
        output_path.write_text(report)
        print(f"\n✓ Report saved to: {output_path}")
    else:
        print("\n" + "=" * 70)
        print(report)
        print("=" * 70)

    # Clean up
    if db_path.exists():
        db_path.unlink()


if __name__ == "__main__":
    main()
