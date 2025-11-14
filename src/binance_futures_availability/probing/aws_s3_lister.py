"""
AWS CLI-based S3 listing for efficient availability checking.

Uses `aws s3 ls` command to list all files for a symbol in one call,
extracting availability information from filenames without HEAD requests.

Performance: ~4.5 seconds per symbol (all dates), vs ~5 seconds per date (all symbols)
"""

import re
import subprocess
from datetime import date, datetime
from typing import Dict, List, Optional


class AWSS3Lister:
    """List Binance Vision S3 files using AWS CLI."""

    BASE_URL = "s3://data.binance.vision/data/futures/um/daily/klines"

    def list_symbol_files(self, symbol: str) -> List[Dict]:
        """
        List all available files for a symbol using AWS CLI.

        Args:
            symbol: Trading pair symbol (e.g., "BTCUSDT")

        Returns:
            List of dicts with date, file_size_bytes, last_modified, url

        Raises:
            RuntimeError: If AWS CLI command fails
        """
        url = f"{self.BASE_URL}/{symbol}/1m/"

        try:
            result = subprocess.run(
                ["aws", "s3", "ls", url, "--no-sign-request"],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,  # Don't raise on non-zero exit (path may not exist)
            )
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(f"AWS CLI timeout for {symbol}: {e}") from e
        except FileNotFoundError as e:
            raise RuntimeError(
                "AWS CLI not found. Install with: brew install awscli"
            ) from e

        # Exit code 1 with empty stdout = path doesn't exist (no files) - this is valid
        # Exit code 0 = success
        # Other exit codes with stderr = real errors
        if result.returncode != 0 and result.stderr.strip():
            raise RuntimeError(
                f"AWS CLI failed for {symbol}: {result.stderr.strip()}"
            )

        # Empty stdout or exit code 1 = no files found (valid for delisted symbols)
        return self._parse_aws_output(result.stdout, symbol)

    def _parse_aws_output(self, output: str, symbol: str) -> List[Dict]:
        """
        Parse AWS CLI ls output into structured availability records.

        AWS ls format:
        2022-03-21 01:58:10      56711 BTCUSDT-1m-2019-12-31.zip
        2022-03-21 01:58:10         92 BTCUSDT-1m-2019-12-31.zip.CHECKSUM

        Args:
            output: Raw stdout from aws s3 ls
            symbol: Symbol being listed

        Returns:
            List of availability records (one per date)
        """
        records = []

        # Regex to match data files (exclude CHECKSUM files)
        # Format: SYMBOL-1m-YYYY-MM-DD.zip
        pattern = rf"{re.escape(symbol)}-1m-(\d{{4}}-\d{{2}}-\d{{2}})\.zip$"

        for line in output.strip().split("\n"):
            if not line:
                continue

            # Skip CHECKSUM files
            if ".CHECKSUM" in line:
                continue

            # Parse line: "DATE TIME SIZE FILENAME"
            parts = line.split(maxsplit=3)
            if len(parts) != 4:
                continue

            date_str, time_str, size_str, filename = parts

            # Extract date from filename (more reliable than parse date)
            match = re.search(pattern, filename)
            if not match:
                continue

            file_date_str = match.group(1)

            try:
                file_date = datetime.strptime(file_date_str, "%Y-%m-%d").date()
                file_size = int(size_str)
                last_modified = datetime.strptime(
                    f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S"
                )

                records.append(
                    {
                        "date": file_date,
                        "file_size_bytes": file_size,
                        "last_modified": last_modified,
                        "url": f"https://data.binance.vision/data/futures/um/daily/klines/{symbol}/1m/{filename}",
                    }
                )
            except (ValueError, IndexError) as e:
                # Skip malformed lines
                continue

        return records

    def get_symbol_availability(
        self,
        symbol: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Dict[date, Dict]:
        """
        Get availability information for a symbol across date range.

        Args:
            symbol: Trading pair symbol
            start_date: Filter to dates >= start_date (optional)
            end_date: Filter to dates <= end_date (optional)

        Returns:
            Dict mapping date -> {file_size_bytes, last_modified, url}
        """
        records = self.list_symbol_files(symbol)

        # Build date-indexed dict
        availability = {}
        for record in records:
            file_date = record["date"]

            # Apply date filters
            if start_date and file_date < start_date:
                continue
            if end_date and file_date > end_date:
                continue

            availability[file_date] = {
                "file_size_bytes": record["file_size_bytes"],
                "last_modified": record["last_modified"],
                "url": record["url"],
            }

        return availability
