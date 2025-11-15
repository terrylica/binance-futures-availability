#!/usr/bin/env python3
"""
Database Consistency Verification Script (ADR-0009 Phase 4)

Compares databases from GitHub Actions and local APScheduler to verify consistency
during parallel operation period.

Usage:
    uv run python scripts/verify-database-consistency.py
    uv run python scripts/verify-database-consistency.py --download-latest
    uv run python scripts/verify-database-consistency.py --detailed

Exit codes:
    0 - Databases are consistent
    1 - Databases differ or validation errors
    2 - Missing database files

Raises errors immediately (ADR-0003 compliant).
"""

import argparse
import subprocess
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Tuple

import duckdb


# =============================================================================
# Configuration
# =============================================================================

LOCAL_DB_PATH = Path.home() / ".cache/binance-futures/availability.duckdb"
GITHUB_RELEASE_TAG = "latest"
GITHUB_COMPRESSED_FILE = "availability.duckdb.zst"


# =============================================================================
# Helper Functions
# =============================================================================

def log_info(message: str) -> None:
    """Log informational message."""
    print(f"[INFO] {message}")


def log_success(message: str) -> None:
    """Log success message."""
    print(f"[✓] {message}")


def log_error(message: str) -> None:
    """Log error message."""
    print(f"[✗] {message}", file=sys.stderr)


def log_warning(message: str) -> None:
    """Log warning message."""
    print(f"[⚠] {message}")


# =============================================================================
# Database Operations
# =============================================================================

def download_github_database(temp_dir: Path) -> Path:
    """
    Download latest database from GitHub Releases.

    Args:
        temp_dir: Temporary directory for download

    Returns:
        Path to decompressed database file

    Raises:
        subprocess.CalledProcessError: If download fails
        FileNotFoundError: If downloaded file not found
    """
    log_info(f"Downloading {GITHUB_RELEASE_TAG} release from GitHub...")

    compressed_path = temp_dir / GITHUB_COMPRESSED_FILE
    decompressed_path = temp_dir / "availability.duckdb"

    # Download from GitHub Releases
    try:
        subprocess.run(
            [
                "gh",
                "release",
                "download",
                GITHUB_RELEASE_TAG,
                "--pattern",
                GITHUB_COMPRESSED_FILE,
                "--dir",
                str(temp_dir),
                "--clobber",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        log_error(f"Failed to download release: {e.stderr}")
        raise

    if not compressed_path.exists():
        raise FileNotFoundError(f"Downloaded file not found: {compressed_path}")

    log_success(f"Downloaded: {compressed_path} ({compressed_path.stat().st_size / 1024 / 1024:.1f} MB)")

    # Decompress with zstd
    log_info("Decompressing database...")
    try:
        subprocess.run(
            ["zstd", "-d", str(compressed_path), "-o", str(decompressed_path), "--force"],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        log_error(f"Failed to decompress: {e.stderr}")
        raise

    if not decompressed_path.exists():
        raise FileNotFoundError(f"Decompressed file not found: {decompressed_path}")

    log_success(f"Decompressed: {decompressed_path} ({decompressed_path.stat().st_size / 1024 / 1024:.1f} MB)")

    return decompressed_path


def get_database_stats(db_path: Path) -> Dict[str, any]:
    """
    Get database statistics.

    Args:
        db_path: Path to database file

    Returns:
        Dictionary of database statistics

    Raises:
        FileNotFoundError: If database file not found
        duckdb.Error: If query fails
    """
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    conn = duckdb.connect(str(db_path), read_only=True)

    try:
        # Get basic counts
        total_count = conn.execute("SELECT COUNT(*) FROM daily_availability").fetchone()[0]
        available_count = conn.execute(
            "SELECT COUNT(*) FROM daily_availability WHERE available = true"
        ).fetchone()[0]
        unavailable_count = conn.execute(
            "SELECT COUNT(*) FROM daily_availability WHERE available = false"
        ).fetchone()[0]

        # Get date range
        date_range = conn.execute(
            "SELECT MIN(date), MAX(date) FROM daily_availability"
        ).fetchone()

        # Get volume data coverage
        volume_count = conn.execute(
            "SELECT COUNT(*) FROM daily_availability WHERE file_size_bytes IS NOT NULL"
        ).fetchone()[0]

        # Get distinct dates and symbols
        distinct_dates = conn.execute(
            "SELECT COUNT(DISTINCT date) FROM daily_availability"
        ).fetchone()[0]
        distinct_symbols = conn.execute(
            "SELECT COUNT(DISTINCT symbol) FROM daily_availability"
        ).fetchone()[0]

        # Get yesterday's stats (most recent expected update)
        yesterday = date.today() - timedelta(days=1)
        yesterday_count = conn.execute(
            "SELECT COUNT(*) FROM daily_availability WHERE date = ?", [yesterday]
        ).fetchone()[0]

        return {
            "total_records": total_count,
            "available_records": available_count,
            "unavailable_records": unavailable_count,
            "volume_records": volume_count,
            "min_date": date_range[0],
            "max_date": date_range[1],
            "distinct_dates": distinct_dates,
            "distinct_symbols": distinct_symbols,
            "yesterday_count": yesterday_count,
        }
    finally:
        conn.close()


def compare_databases(
    local_stats: Dict[str, any], github_stats: Dict[str, any]
) -> Tuple[bool, List[str]]:
    """
    Compare statistics from two databases.

    Args:
        local_stats: Statistics from local database
        github_stats: Statistics from GitHub database

    Returns:
        Tuple of (is_consistent, list_of_differences)
    """
    differences = []

    # Compare counts
    if local_stats["total_records"] != github_stats["total_records"]:
        differences.append(
            f"Total records: Local={local_stats['total_records']:,}, "
            f"GitHub={github_stats['total_records']:,}, "
            f"Diff={abs(local_stats['total_records'] - github_stats['total_records']):,}"
        )

    if local_stats["available_records"] != github_stats["available_records"]:
        differences.append(
            f"Available records: Local={local_stats['available_records']:,}, "
            f"GitHub={github_stats['available_records']:,}, "
            f"Diff={abs(local_stats['available_records'] - github_stats['available_records']):,}"
        )

    # Compare date ranges
    if local_stats["min_date"] != github_stats["min_date"]:
        differences.append(
            f"Minimum date: Local={local_stats['min_date']}, GitHub={github_stats['min_date']}"
        )

    if local_stats["max_date"] != github_stats["max_date"]:
        differences.append(
            f"Maximum date: Local={local_stats['max_date']}, GitHub={github_stats['max_date']}"
        )

    # Compare distinct counts
    if local_stats["distinct_dates"] != github_stats["distinct_dates"]:
        differences.append(
            f"Distinct dates: Local={local_stats['distinct_dates']:,}, "
            f"GitHub={github_stats['distinct_dates']:,}"
        )

    # Compare yesterday's data (most important for daily consistency)
    if local_stats["yesterday_count"] != github_stats["yesterday_count"]:
        differences.append(
            f"Yesterday's records: Local={local_stats['yesterday_count']}, "
            f"GitHub={github_stats['yesterday_count']}"
        )

    is_consistent = len(differences) == 0

    return is_consistent, differences


def detailed_comparison(local_path: Path, github_path: Path) -> List[str]:
    """
    Perform detailed row-by-row comparison for yesterday's data.

    Args:
        local_path: Path to local database
        github_path: Path to GitHub database

    Returns:
        List of detailed differences

    Raises:
        duckdb.Error: If query fails
    """
    differences = []
    yesterday = date.today() - timedelta(days=1)

    local_conn = duckdb.connect(str(local_path), read_only=True)
    github_conn = duckdb.connect(str(github_path), read_only=True)

    try:
        # Get yesterday's data from both databases
        local_data = local_conn.execute(
            """
            SELECT symbol, available, file_size_bytes
            FROM daily_availability
            WHERE date = ?
            ORDER BY symbol
            """,
            [yesterday],
        ).fetchall()

        github_data = github_conn.execute(
            """
            SELECT symbol, available, file_size_bytes
            FROM daily_availability
            WHERE date = ?
            ORDER BY symbol
            """,
            [yesterday],
        ).fetchall()

        # Convert to dictionaries for easier comparison
        local_dict = {row[0]: row for row in local_data}
        github_dict = {row[0]: row for row in github_data}

        # Find symbols only in local
        local_only = set(local_dict.keys()) - set(github_dict.keys())
        if local_only:
            differences.append(f"Symbols only in local: {sorted(local_only)[:10]}")

        # Find symbols only in GitHub
        github_only = set(github_dict.keys()) - set(local_dict.keys())
        if github_only:
            differences.append(f"Symbols only in GitHub: {sorted(github_only)[:10]}")

        # Compare common symbols
        common_symbols = set(local_dict.keys()) & set(github_dict.keys())
        mismatches = []
        for symbol in common_symbols:
            if local_dict[symbol] != github_dict[symbol]:
                mismatches.append(
                    f"  {symbol}: Local={local_dict[symbol][1:]}, GitHub={github_dict[symbol][1:]}"
                )

        if mismatches:
            differences.append(f"Data mismatches for {len(mismatches)} symbols:")
            differences.extend(mismatches[:10])  # Show first 10

    finally:
        local_conn.close()
        github_conn.close()

    return differences


# =============================================================================
# Main Function
# =============================================================================

def main() -> int:
    """
    Main function.

    Returns:
        Exit code (0 = consistent, 1 = differences, 2 = error)
    """
    parser = argparse.ArgumentParser(
        description="Verify database consistency between local and GitHub (ADR-0009 Phase 4)"
    )
    parser.add_argument(
        "--download-latest",
        action="store_true",
        help="Download latest database from GitHub Releases",
    )
    parser.add_argument(
        "--detailed",
        action="store_true",
        help="Perform detailed row-by-row comparison (slower)",
    )
    args = parser.parse_args()

    print("=" * 80)
    print("Database Consistency Verification (ADR-0009 Phase 4)")
    print("=" * 80)
    print()

    # Check if local database exists
    if not LOCAL_DB_PATH.exists():
        log_error(f"Local database not found: {LOCAL_DB_PATH}")
        log_info("Run: uv run python scripts/operations/backfill.py")
        return 2

    # Download GitHub database to temp directory
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Download and decompress
            github_db_path = download_github_database(temp_path)

            # Get statistics from both databases
            log_info("Analyzing local database...")
            local_stats = get_database_stats(LOCAL_DB_PATH)

            log_info("Analyzing GitHub database...")
            github_stats = get_database_stats(github_db_path)

            # Print statistics
            print()
            print("=" * 80)
            print("Database Statistics Comparison")
            print("=" * 80)
            print()

            print(f"{'Metric':<30} {'Local':>15} {'GitHub':>15} {'Match':>10}")
            print("-" * 80)

            metrics = [
                ("Total records", "total_records"),
                ("Available records", "available_records"),
                ("Unavailable records", "unavailable_records"),
                ("Records with volume", "volume_records"),
                ("Distinct dates", "distinct_dates"),
                ("Distinct symbols", "distinct_symbols"),
                ("Yesterday's records", "yesterday_count"),
            ]

            for label, key in metrics:
                local_val = local_stats[key]
                github_val = github_stats[key]
                match = "✓" if local_val == github_val else "✗"

                if isinstance(local_val, int):
                    print(f"{label:<30} {local_val:>15,} {github_val:>15,} {match:>10}")
                else:
                    print(f"{label:<30} {str(local_val):>15} {str(github_val):>15} {match:>10}")

            print()
            print(f"{'Date range':<30} {local_stats['min_date']} to {local_stats['max_date']}")
            print(f"{'GitHub date range':<30} {github_stats['min_date']} to {github_stats['max_date']}")

            # Compare databases
            is_consistent, differences = compare_databases(local_stats, github_stats)

            print()
            print("=" * 80)
            print("Consistency Analysis")
            print("=" * 80)
            print()

            if is_consistent:
                log_success("✅ Databases are CONSISTENT")
                log_info("Local APScheduler and GitHub Actions are producing identical results")
                exit_code = 0
            else:
                log_error("❌ Databases have DIFFERENCES")
                print()
                for diff in differences:
                    log_warning(f"  {diff}")
                exit_code = 1

            # Detailed comparison if requested
            if args.detailed:
                print()
                print("=" * 80)
                print("Detailed Comparison (Yesterday's Data)")
                print("=" * 80)
                print()

                detailed_diffs = detailed_comparison(LOCAL_DB_PATH, github_db_path)

                if detailed_diffs:
                    for diff in detailed_diffs:
                        log_warning(diff)
                else:
                    log_success("No detailed differences found")

            # Summary and recommendations
            print()
            print("=" * 80)
            print("Recommendations")
            print("=" * 80)
            print()

            if is_consistent:
                log_info("✓ Safe to deprecate APScheduler after 3 consecutive consistent checks")
                log_info("✓ GitHub Actions workflow is functioning correctly")
            else:
                log_warning("⚠ DO NOT deprecate APScheduler yet")
                log_warning("⚠ Investigate differences before proceeding")
                log_info("  1. Check GitHub Actions workflow logs: gh run list --workflow=update-database.yml")
                log_info("  2. Verify validation checks passed in workflow output")
                log_info("  3. Compare APScheduler logs with GitHub Actions logs")

            return exit_code

    except FileNotFoundError as e:
        log_error(f"File not found: {e}")
        return 2
    except subprocess.CalledProcessError as e:
        log_error(f"Command failed: {e}")
        return 2
    except Exception as e:
        log_error(f"Unexpected error: {e}")
        raise  # Re-raise for traceback (ADR-0003: raise+propagate)


if __name__ == "__main__":
    sys.exit(main())
