"""Volume ranking and analytics queries.

Provides query methods for analyzing trading volume metrics collected from 1d kline files.
Implements ADR-0007 volume ranking capabilities.
"""

from datetime import date
from typing import List, Optional

from binance_futures_availability.database import AvailabilityDatabase


class VolumeQueries:
    """Query interface for volume ranking and analytics."""

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize volume queries.

        Args:
            db_path: Optional custom database path
        """
        self.db = AvailabilityDatabase(db_path=db_path)

    def get_top_by_volume(
        self,
        target_date: date,
        limit: int = 10,
        min_volume: Optional[float] = None,
    ) -> List[dict]:
        """
        Get top N symbols by trading volume for a specific date.

        Args:
            target_date: Date to query
            limit: Maximum number of symbols to return
            min_volume: Optional minimum volume filter (USDT)

        Returns:
            List of dicts with keys: symbol, quote_volume_usdt, trade_count,
            volume_rank, market_share_pct

        Example:
            >>> vq = VolumeQueries()
            >>> top10 = vq.get_top_by_volume(date(2024, 1, 15), limit=10)
            >>> print(f"{top10[0]['symbol']}: ${top10[0]['quote_volume_usdt']:,.0f}")
            BTCUSDT: $10,237,828,483
        """
        sql = """
            WITH ranked AS (
                SELECT
                    symbol,
                    quote_volume_usdt,
                    trade_count,
                    RANK() OVER (ORDER BY quote_volume_usdt DESC) as volume_rank,
                    SUM(quote_volume_usdt) OVER () as total_market_volume
                FROM daily_availability
                WHERE date = ?
                  AND available = TRUE
                  AND quote_volume_usdt IS NOT NULL
        """

        params = [target_date]

        if min_volume is not None:
            sql += " AND quote_volume_usdt >= ?"
            params.append(min_volume)

        sql += """
            )
            SELECT
                symbol,
                quote_volume_usdt,
                trade_count,
                volume_rank,
                ROUND(100.0 * quote_volume_usdt / total_market_volume, 2) as market_share_pct
            FROM ranked
            ORDER BY quote_volume_usdt DESC
            LIMIT ?
        """

        params.append(limit)

        results = self.db.query(sql, params)

        return [
            {
                "symbol": row[0],
                "quote_volume_usdt": row[1],
                "trade_count": row[2],
                "volume_rank": row[3],
                "market_share_pct": row[4],
            }
            for row in results
        ]

    def get_volume_percentile(
        self, symbol: str, target_date: date
    ) -> Optional[dict]:
        """
        Get volume percentile ranking for a symbol on a specific date.

        Args:
            symbol: Trading pair symbol
            target_date: Date to query

        Returns:
            Dict with percentile, rank, total_symbols, or None if no data

        Example:
            >>> vq = VolumeQueries()
            >>> pct = vq.get_volume_percentile('BTCUSDT', date(2024, 1, 15))
            >>> print(f"BTCUSDT is in top {100 - pct['percentile']:.1f}%")
            BTCUSDT is in top 0.4%
        """
        sql = """
            WITH ranked AS (
                SELECT
                    symbol,
                    quote_volume_usdt,
                    RANK() OVER (ORDER BY quote_volume_usdt DESC) as rank,
                    COUNT(*) OVER () as total_symbols
                FROM daily_availability
                WHERE date = ?
                  AND available = TRUE
                  AND quote_volume_usdt IS NOT NULL
            )
            SELECT
                rank,
                total_symbols,
                ROUND(100.0 * (total_symbols - rank) / total_symbols, 2) as percentile
            FROM ranked
            WHERE symbol = ?
        """

        results = self.db.query(sql, [target_date, symbol])

        if not results:
            return None

        row = results[0]
        return {
            "symbol": symbol,
            "rank": row[0],
            "total_symbols": row[1],
            "percentile": row[2],
        }

    def get_average_volume(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> Optional[dict]:
        """
        Get average daily volume for a symbol over a date range.

        Args:
            symbol: Trading pair symbol
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            Dict with avg_volume, avg_trades, days_with_data, or None if no data

        Example:
            >>> vq = VolumeQueries()
            >>> avg = vq.get_average_volume('BTCUSDT', date(2024, 1, 1), date(2024, 1, 31))
            >>> print(f"Avg daily volume: ${avg['avg_volume_usdt']:,.0f}")
            Avg daily volume: $9,542,123,456
        """
        sql = """
            SELECT
                AVG(quote_volume_usdt) as avg_volume_usdt,
                AVG(trade_count) as avg_trade_count,
                COUNT(*) as days_with_data,
                MIN(quote_volume_usdt) as min_volume_usdt,
                MAX(quote_volume_usdt) as max_volume_usdt
            FROM daily_availability
            WHERE symbol = ?
              AND date BETWEEN ? AND ?
              AND available = TRUE
              AND quote_volume_usdt IS NOT NULL
        """

        results = self.db.query(sql, [symbol, start_date, end_date])

        if not results or results[0][0] is None:
            return None

        row = results[0]
        return {
            "symbol": symbol,
            "avg_volume_usdt": row[0],
            "avg_trade_count": row[1],
            "days_with_data": row[2],
            "min_volume_usdt": row[3],
            "max_volume_usdt": row[4],
        }

    def get_volume_trend(
        self,
        symbol: str,
        days: int = 30,
    ) -> List[dict]:
        """
        Get daily volume trend for last N days.

        Args:
            symbol: Trading pair symbol
            days: Number of days to include

        Returns:
            List of dicts with date, quote_volume_usdt, trade_count

        Example:
            >>> vq = VolumeQueries()
            >>> trend = vq.get_volume_trend('BTCUSDT', days=7)
            >>> for day in trend:
            >>>     print(f"{day['date']}: ${day['quote_volume_usdt']:,.0f}")
        """
        sql = """
            SELECT
                date,
                quote_volume_usdt,
                trade_count
            FROM daily_availability
            WHERE symbol = ?
              AND available = TRUE
              AND quote_volume_usdt IS NOT NULL
            ORDER BY date DESC
            LIMIT ?
        """

        results = self.db.query(sql, [symbol, days])

        return [
            {
                "date": row[0],
                "quote_volume_usdt": row[1],
                "trade_count": row[2],
            }
            for row in results
        ]

    def get_market_summary(self, target_date: date) -> Optional[dict]:
        """
        Get overall market volume summary for a date.

        Args:
            target_date: Date to query

        Returns:
            Dict with total_volume, total_trades, symbol_count, or None if no data

        Example:
            >>> vq = VolumeQueries()
            >>> summary = vq.get_market_summary(date(2024, 1, 15))
            >>> print(f"Total market volume: ${summary['total_volume_usdt']:,.0f}")
            Total market volume: $45,123,456,789
        """
        sql = """
            SELECT
                SUM(quote_volume_usdt) as total_volume_usdt,
                SUM(trade_count) as total_trade_count,
                COUNT(*) as symbol_count,
                AVG(quote_volume_usdt) as avg_volume_usdt
            FROM daily_availability
            WHERE date = ?
              AND available = TRUE
              AND quote_volume_usdt IS NOT NULL
        """

        results = self.db.query(sql, [target_date])

        if not results or results[0][0] is None:
            return None

        row = results[0]
        return {
            "date": target_date,
            "total_volume_usdt": row[0],
            "total_trade_count": row[1],
            "symbol_count": row[2],
            "avg_volume_usdt": row[3],
        }
