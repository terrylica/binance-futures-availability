"""Symbol discovery for Binance USDT perpetual futures.

DEPRECATED: This module is a backward-compatibility wrapper.
New code should use: from binance_futures_availability.config import load_symbols

Copied and adapted from: scratch/vision-futures-explorer/futures_discovery.py

Symbol data now stored in: src/binance_futures_availability/data/symbols.json
This allows easier updates without modifying code.
"""

from typing import Literal

# Import from new symbol_loader module
from binance_futures_availability.config.symbol_loader import load_symbols


def load_discovered_symbols(
    contract_type: Literal["perpetual", "delivery", "all"] = "perpetual",
) -> list[str]:
    """
    Load the list of discovered Binance USDT futures symbols.

    DEPRECATED: Use `from binance_futures_availability.config import load_symbols` instead.

    Args:
        contract_type:
            - "perpetual": USDT perpetual contracts (708 symbols, e.g., BTCUSDT)
            - "delivery": Quarterly delivery contracts (44 symbols, e.g., BTCUSDT_231229)
            - "all": All futures contracts (752 symbols)

    Returns:
        List of symbol strings

    Note:
        Symbol data loaded from data/symbols.json (discovered 2025-11-12).
        For the most up-to-date list, use the exchangeInfo API or re-run S3 discovery.

    Example:
        >>> symbols = load_discovered_symbols("perpetual")
        >>> len(symbols)
        708
        >>> "BTCUSDT" in symbols
        True
    """
    return load_symbols(contract_type)
