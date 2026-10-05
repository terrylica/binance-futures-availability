"""Cross-check validation: Verify against Binance exchangeInfo API.

Metric is recall: of the perpetuals the API lists as TRADING, the share with a Vision file in
the database on the checked date. Symbols only in the database are expected and not errors:
SETTLING (delisting) contracts keep publishing daily files (133 such symbols on 2026-10-05).
Binance geo-blocks the API (HTTP 451) on GitHub's US runners, so this check runs locally only.

See: docs/development/plan/v1.0.0-implementation-plan.yaml (slos.correctness)
"""

import datetime
import json
import urllib.request
from pathlib import Path
from typing import Any

from binance_futures_availability.database.availability_db import AvailabilityDatabase

# Vision's um/daily/klines tree holds both; quarterly delivery contracts are out of scope.
PERPETUAL_CONTRACT_TYPES = frozenset({"PERPETUAL", "TRADIFI_PERPETUAL"})

# Same S3 publishing buffer as the continuity/completeness checks: a first probe of "yesterday"
# often 404s under the T+1 lag (measured: 93% recall at T-1 vs 100% at T-2 on 2026-10-05).
DEFAULT_LAG_DAYS = 3


class CrossCheckValidator:
    """
    Verify database accuracy against Binance exchangeInfo API.

    SLO: >95% of API TRADING perpetuals available in the database (recall)
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
        Fetch every perpetual the API lists as TRADING (any quote asset, incl. TradFi perps).

        Returns:
            Set of symbol strings (e.g., {'BTCUSDT', '1000PEPEUSDC', 'AAPLUSDT', ...})

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

            return {
                s["symbol"]
                for s in data["symbols"]
                if s.get("contractType") in PERPETUAL_CONTRACT_TYPES
                and s.get("status") == "TRADING"
            }

        except Exception as e:
            raise RuntimeError(f"Failed to fetch exchangeInfo from API: {e}") from e

    def cross_check_current_date(self, date: datetime.date | None = None) -> dict[str, Any]:
        """
        Compare database symbols against live exchangeInfo API.

        Args:
            date: Date to check (default: today - DEFAULT_LAG_DAYS)

        Returns:
            Dict with keys:
                - date: Date checked
                - db_symbols: Set of symbols in database
                - api_symbols: Set of symbols from API
                - match_count: Number of matching symbols
                - match_percentage: Recall of API TRADING perpetuals in the database (0-100)
                - only_in_db: Symbols in database but not TRADING in API (expected: settling/delisted)
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
        if date is None:
            date = datetime.date.today() - datetime.timedelta(days=DEFAULT_LAG_DAYS)
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

            # Recall over the API's TRADING set; DB-only symbols are expected (see module doc)
            match_percentage = (
                (len(matching_symbols) / len(api_symbols) * 100) if api_symbols else 0.0
            )

            return {
                "date": str(date),
                "db_symbol_count": len(db_symbols),
                "api_symbol_count": len(api_symbols),
                "match_count": len(matching_symbols),
                "match_percentage": round(match_percentage, 2),
                "only_in_db": sorted(only_in_db),
                "only_in_api": sorted(only_in_api),
                "slo_met": match_percentage > 95.0,  # SLO: >95% recall
            }

        except Exception as e:
            raise RuntimeError(f"Cross-check validation failed for {date}: {e}") from e

    def validate_cross_check(self, date: datetime.date | None = None) -> bool:
        """
        Validate that database matches API (assertion-style check).

        Args:
            date: Date to check (default: today - DEFAULT_LAG_DAYS)

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
