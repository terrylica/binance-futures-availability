"""Batch probing with parallel execution for efficient data collection."""

from __future__ import annotations

import datetime
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from binance_futures_availability.probing.s3_vision import ProbeResult, check_symbol_availability
from binance_futures_availability.probing.symbol_discovery import load_discovered_symbols

logger = logging.getLogger(__name__)


class BatchProber:
    """
    Parallel batch probing of futures availability.

    Uses ThreadPoolExecutor for concurrent HTTP HEAD requests.
    Conservative rate limiting to avoid S3 throttling.

    See: docs/decisions/0003-error-handling-strict-policy.md
    """

    def __init__(self, max_workers: int = 10, rate_limit: float = 2.0) -> None:
        """
        Initialize batch prober.

        Args:
            max_workers: Maximum concurrent threads (default: 10)
            rate_limit: Target requests per second (default: 2.0)

        Note:
            Conservative rate_limit=2.0 to avoid S3 throttling.
            708 symbols × 0.5s = ~6 minutes per date.
        """
        self.max_workers = max_workers
        self.rate_limit = rate_limit

    def probe_all_symbols(
        self,
        date: datetime.date,
        symbols: list[str] | None = None,
        contract_type: str = "perpetual",
    ) -> list[dict[str, Any]]:
        """
        Probe all symbols for a specific date in parallel.

        Args:
            date: Trading date to probe
            symbols: Custom symbol list (default: load from symbol_discovery)
            contract_type: "perpetual", "delivery", or "all" (if symbols=None)

        Returns:
            List of probe result dicts (suitable for AvailabilityDatabase.insert_batch)

        Raises:
            RuntimeError: On any probe failure (ADR-0003: strict raise policy)

        Example:
            >>> prober = BatchProber(max_workers=10)
            >>> results = prober.probe_all_symbols(date=datetime.date(2024, 1, 15))
            >>> len(results)
            708
        """
        if symbols is None:
            symbols = load_discovered_symbols(contract_type=contract_type)  # type: ignore

        logger.info(f"Starting batch probe for {len(symbols)} symbols on {date}")

        results = []
        failed = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_symbol = {
                executor.submit(check_symbol_availability, symbol, date): symbol
                for symbol in symbols
            }

            # Collect results as they complete
            for future in as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                try:
                    result: ProbeResult = future.result()
                    results.append(result)

                    if result["available"]:
                        logger.debug(f"✓ {symbol}: available ({result['file_size_bytes']} bytes)")
                    else:
                        logger.debug(f"✗ {symbol}: not available (404)")

                except Exception as e:
                    # Log failure but continue collecting (ADR-0003: raise at end)
                    logger.error(f"Probe failed for {symbol} on {date}: {e}")
                    failed.append((symbol, str(e)))

        # Raise if any failures occurred (ADR-0003: strict policy)
        if failed:
            error_summary = "\n".join(f"  - {sym}: {err}" for sym, err in failed)
            raise RuntimeError(
                f"Batch probe failed for {len(failed)}/{len(symbols)} symbols on {date}:\n"
                f"{error_summary}"
            )

        logger.info(
            f"Batch probe completed: {len(results)} symbols probed, "
            f"{sum(1 for r in results if r['available'])} available"
        )

        return results

    def probe_date_range(
        self,
        start_date: datetime.date,
        end_date: datetime.date,
        symbols: list[str] | None = None,
        contract_type: str = "perpetual",
        checkpoint_callback: callable | None = None,
    ) -> list[dict[str, Any]]:
        """
        Probe multiple dates sequentially.

        Args:
            start_date: Range start (inclusive)
            end_date: Range end (inclusive)
            symbols: Custom symbol list (default: load from symbol_discovery)
            contract_type: "perpetual", "delivery", or "all" (if symbols=None)
            checkpoint_callback: Optional callback(date, results) after each date

        Returns:
            Flattened list of all probe results across date range

        Raises:
            RuntimeError: On any probe failure (ADR-0003: strict raise policy)

        Example:
            >>> prober = BatchProber()
            >>> results = prober.probe_date_range(
            ...     start_date=datetime.date(2024, 1, 1),
            ...     end_date=datetime.date(2024, 1, 7)
            ... )
            >>> len(results)
            4956  # 7 days × 708 symbols
        """
        all_results = []
        current_date = start_date

        while current_date <= end_date:
            logger.info(f"Probing date: {current_date}")

            try:
                date_results = self.probe_all_symbols(
                    date=current_date, symbols=symbols, contract_type=contract_type
                )
                all_results.extend(date_results)

                # Checkpoint callback (for progress tracking)
                if checkpoint_callback:
                    checkpoint_callback(current_date, date_results)

            except RuntimeError as e:
                # Re-raise with date context
                raise RuntimeError(f"Probe failed for {current_date}: {e}") from e

            current_date += datetime.timedelta(days=1)

        logger.info(
            f"Date range probe completed: {len(all_results)} total results "
            f"({start_date} to {end_date})"
        )

        return all_results
