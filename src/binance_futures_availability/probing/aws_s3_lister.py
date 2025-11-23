"""
AWS CLI-based S3 listing for efficient availability checking.

Uses `aws s3 ls` command to list all files for a symbol in one call,
extracting availability information from filenames without HEAD requests.

Performance: ~4.5 seconds per symbol (all dates), vs ~5 seconds per date (all symbols)
"""

import csv
import io
import re
import subprocess
import zipfile
from datetime import date, datetime


class AWSS3Lister:
    """List Binance Vision S3 files using AWS CLI."""

    BASE_URL = "s3://data.binance.vision/data/futures/um/daily/klines"

    def list_symbol_files(self, symbol: str) -> list[dict]:
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
            raise RuntimeError("AWS CLI not found. Install with: brew install awscli") from e

        # Exit code 1 with empty stdout = path doesn't exist (no files) - this is valid
        # Exit code 0 = success
        # Other exit codes with stderr = real errors
        if result.returncode != 0 and result.stderr.strip():
            raise RuntimeError(f"AWS CLI failed for {symbol}: {result.stderr.strip()}")

        # Empty stdout or exit code 1 = no files found (valid for delisted symbols)
        return self._parse_aws_output(result.stdout, symbol)

    def _parse_aws_output(self, output: str, symbol: str) -> list[dict]:
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
                last_modified = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")

                records.append(
                    {
                        "date": file_date,
                        "file_size_bytes": file_size,
                        "last_modified": last_modified,
                        "url": f"https://data.binance.vision/data/futures/um/daily/klines/{symbol}/1m/{filename}",
                    }
                )
            except (ValueError, IndexError):
                # Skip malformed lines
                continue

        return records

    def get_symbol_availability(
        self,
        symbol: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict[date, dict]:
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

    def download_1d_kline(self, symbol: str, target_date: date) -> dict | None:
        """
        Download and parse 1d kline file for a specific symbol and date.

        Downloads the 1d kline ZIP file from S3, extracts the CSV, and parses
        the trading volume metrics.

        Args:
            symbol: Trading pair symbol (e.g., "BTCUSDT")
            target_date: Date to fetch kline data for

        Returns:
            Dict with volume metrics, or None if file doesn't exist:
            {
                "quote_volume_usdt": float,
                "trade_count": int,
                "volume_base": float,
                "taker_buy_volume_base": float,
                "taker_buy_quote_volume_usdt": float,
                "open_price": float,
                "high_price": float,
                "low_price": float,
                "close_price": float,
            }

        Raises:
            RuntimeError: If AWS CLI fails or CSV parsing fails
        """
        # Build S3 URL for 1d kline file
        date_str = target_date.strftime("%Y-%m-%d")
        filename = f"{symbol}-1d-{date_str}.zip"
        s3_url = f"{self.BASE_URL}/{symbol}/1d/{filename}"

        try:
            # Download file to stdout using AWS CLI
            result = subprocess.run(
                ["aws", "s3", "cp", s3_url, "-", "--no-sign-request"],
                capture_output=True,
                timeout=30,
                check=False,
            )
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(
                f"AWS CLI timeout downloading 1d kline for {symbol} {date_str}: {e}"
            ) from e
        except FileNotFoundError as e:
            raise RuntimeError("AWS CLI not found. Install with: brew install awscli") from e

        # Exit code 1 = file not found (valid for dates without data)
        if result.returncode == 1:
            return None

        # Other non-zero exit codes = real errors
        if result.returncode != 0:
            raise RuntimeError(
                f"AWS CLI failed downloading 1d kline for {symbol} {date_str}: "
                f"{result.stderr.decode('utf-8').strip()}"
            )

        # Parse ZIP file from stdout
        try:
            zip_data = io.BytesIO(result.stdout)
            with zipfile.ZipFile(zip_data) as zf:
                # Should contain single CSV file: SYMBOL-1d-YYYY-MM-DD.csv
                csv_filename = f"{symbol}-1d-{date_str}.csv"
                with zf.open(csv_filename) as csv_file:
                    csv_content = csv_file.read().decode("utf-8")
                    return self._parse_1d_kline_csv(csv_content, symbol, target_date)
        except zipfile.BadZipFile as e:
            raise RuntimeError(f"Invalid ZIP file for {symbol} {date_str}") from e
        except KeyError as e:
            raise RuntimeError(f"CSV file not found in ZIP for {symbol} {date_str}: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Failed to parse 1d kline for {symbol} {date_str}: {e}") from e

    def _parse_1d_kline_csv(self, csv_content: str, symbol: str, target_date: date) -> dict:
        """
        Parse 1d kline CSV content into volume metrics.

        CSV format (single row, 12 fields):
        open_time,open,high,low,close,volume,close_time,quote_volume,count,
        taker_buy_volume,taker_buy_quote_volume,ignore

        Args:
            csv_content: Raw CSV content
            symbol: Symbol (for error messages)
            target_date: Date (for error messages)

        Returns:
            Dict with 9 volume/price metrics

        Raises:
            RuntimeError: If CSV format is invalid
        """
        reader = csv.reader(io.StringIO(csv_content))
        rows = list(reader)

        # Skip header row if present
        # Expected: header + 1 data row = 2 rows total
        if len(rows) == 2:
            # First row is header, second is data
            row = rows[1]
        elif len(rows) == 1:
            # No header, just data
            row = rows[0]
        else:
            raise RuntimeError(
                f"Expected 1-2 rows in 1d kline CSV for {symbol} {target_date}, got {len(rows)}"
            )

        if len(row) != 12:
            raise RuntimeError(
                f"Expected 12 fields in 1d kline CSV for {symbol} {target_date}, got {len(row)}"
            )

        # Extract fields (indices 0-11)
        # 0: open_time, 1: open, 2: high, 3: low, 4: close, 5: volume,
        # 6: close_time, 7: quote_volume, 8: count, 9: taker_buy_volume,
        # 10: taker_buy_quote_volume, 11: ignore
        try:
            return {
                "quote_volume_usdt": float(row[7]),  # quote_volume
                "trade_count": int(row[8]),  # count
                "volume_base": float(row[5]),  # volume
                "taker_buy_volume_base": float(row[9]),  # taker_buy_volume
                "taker_buy_quote_volume_usdt": float(row[10]),  # taker_buy_quote_volume
                "open_price": float(row[1]),  # open
                "high_price": float(row[2]),  # high
                "low_price": float(row[3]),  # low
                "close_price": float(row[4]),  # close
            }
        except (ValueError, IndexError) as e:
            raise RuntimeError(
                f"Failed to parse numeric fields in 1d kline CSV for {symbol} {target_date}: {e}"
            ) from e
