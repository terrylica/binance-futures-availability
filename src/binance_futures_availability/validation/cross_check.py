"""Cross-check validation: Verify against Binance exchangeInfo API.

See: docs/development/plan/v1.0.0-implementation-plan.yaml (slos.correctness)
"""

import datetime
import json
import urllib.request
from pathlib import Path
from typing import Any

from binance_futures_availability.database.availability_db import AvailabilityDatabase


class CrossCheckValidator:
    """
    Verify database accuracy against Binance exchangeInfo API.

    SLO: >95% match with exchangeInfo API for current date
    See: docs/development/plan/v1.0.0-implementation-plan.yaml (slos.correctness)

    Note:
        exchangeInfo only provides CURRENT data (no historical snapshots).
        This validator can only check today's data against live API.
    """

    def __init__(self, db_path: Path | None = None) -> None:
        """
        Initialize cross-check validator.

        Args:
            db_path: Custom database path (default: ~/.cache/binance-futures/availability.duckdb)
        """
        self.db = AvailabilityDatabase(db_path=db_path)
        self.api_url = "https://fapi.binance.com/fapi/v1/exchangeInfo"

    def fetch_current_symbols_from_api(self) -> set[str]:
        """
        Fetch currently trading USDT perpetual symbols from Binance API.

        Returns:
            Set of symbol strings (e.g., {'BTCUSDT', 'ETHUSDT', ...})

        Raises:
            RuntimeError: On API request failure

        API Endpoint:
            GET https://fapi.binance.com/fapi/v1/exchangeInfo

        Response:
            {
                "symbols": [
                    {
                        "symbol": "BTCUSDT",
                        "status": "TRADING",
                        "contractType": "PERPETUAL",
                        ...
                    },
                    ...
                ]
            }
        """
        try:
            with urllib.request.urlopen(self.api_url, timeout=10) as response:
                data = json.loads(response.read().decode())

            # Filter for USDT perpetual contracts with TRADING status
            return {
                s["symbol"]
                for s in data["symbols"]
                if s.get("contractType") == "PERPETUAL"
                and s.get("status") == "TRADING"
                and s["symbol"].endswith("USDT")
            }

        except Exception as e:
            raise RuntimeError(f"Failed to fetch exchangeInfo from API: {e}") from e

    def cross_check_current_date(self, date: datetime.date | None = None) -> dict[str, Any]:
        """
        Compare database symbols against live exchangeInfo API.

        Args:
            date: Date to check (default: yesterday, since today may be incomplete)

        Returns:
            Dict with keys:
                - date: Date checked
                - db_symbols: Set of symbols in database
                - api_symbols: Set of symbols from API
                - match_count: Number of matching symbols
                - match_percentage: Percentage match (0-100)
                - only_in_db: Symbols in database but not in API (potential delistings)
                - only_in_api: Symbols in API but not in database (potential missing data)

        Raises:
            RuntimeError: On validation failure

        Example:
            >>> validator = CrossCheckValidator()
            >>> result = validator.cross_check_current_date()
            >>> result['match_percentage']
            98.5  # 98.5% match (exceeds 95% SLO)

        SLO:
            match_percentage > 95% (docs/development/plan/v1.0.0-implementation-plan.yaml)
        """
        # Default: check yesterday (today may be incomplete)
        if date is None:
            date = datetime.date.today() - datetime.timedelta(days=1)
        elif isinstance(date, str):
            date = datetime.date.fromisoformat(date)

        try:
            # Fetch database symbols for date
            rows = self.db.query(
                """
                SELECT symbol
                FROM daily_availability
                WHERE date = ? AND available = true
                """,
                [date],
            )
            db_symbols = {row[0] for row in rows}

            # Fetch current symbols from API
            api_symbols = self.fetch_current_symbols_from_api()

            # Calculate match metrics
            matching_symbols = db_symbols & api_symbols
            only_in_db = db_symbols - api_symbols
            only_in_api = api_symbols - db_symbols

            total_unique = len(db_symbols | api_symbols)
            match_percentage = (
                (len(matching_symbols) / total_unique * 100) if total_unique > 0 else 0.0
            )

            return {
                "date": str(date),
                "db_symbol_count": len(db_symbols),
                "api_symbol_count": len(api_symbols),
                "match_count": len(matching_symbols),
                "match_percentage": round(match_percentage, 2),
                "only_in_db": sorted(only_in_db),
                "only_in_api": sorted(only_in_api),
                "slo_met": match_percentage > 95.0,  # SLO: >95% match
            }

        except Exception as e:
            raise RuntimeError(f"Cross-check validation failed for {date}: {e}") from e

    def validate_cross_check(self, date: datetime.date | None = None) -> bool:
        """
        Validate that database matches API (assertion-style check).

        Args:
            date: Date to check (default: yesterday)

        Returns:
            True if match_percentage > 95%, False otherwise

        Raises:
            RuntimeError: If cross-check fails

        Example:
            >>> validator = CrossCheckValidator()
            >>> validator.validate_cross_check()
            True  # Success: >95% match with API
        """
        result = self.cross_check_current_date(date=date)
        return result["slo_met"]

    def close(self) -> None:
        """Close database connection."""
        self.db.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit (auto-close connection)."""
        self.close()
