"""Symbol loader for Binance USDT perpetual futures.

Loads symbols from JSON data file instead of hardcoded lists.
Replaces the legacy symbol_discovery.py hardcoded approach.
"""

import json
from pathlib import Path
from typing import Literal

# Path to symbols.json (relative to this file)
SYMBOLS_FILE = Path(__file__).parent.parent / "data" / "symbols.json"


def load_symbols(
    contract_type: Literal["perpetual", "delivery", "all"] = "perpetual",
) -> list[str]:
    """
    Load Binance USDT futures symbols from JSON data file.

    Args:
        contract_type:
            - "perpetual": USDT perpetual contracts (708 symbols, e.g., BTCUSDT)
            - "delivery": Quarterly delivery contracts (44 symbols, e.g., BTCUSDT_231229)
            - "all": All futures contracts (752 symbols)

    Returns:
        List of symbol strings

    Raises:
        FileNotFoundError: If symbols.json is missing
        ValueError: If invalid contract_type specified

    Example:
        >>> symbols = load_symbols("perpetual")
        >>> len(symbols)
        708
        >>> "BTCUSDT" in symbols
        True
        >>> symbols = load_symbols("all")
        >>> len(symbols)
        752
    """
    if not SYMBOLS_FILE.exists():
        raise FileNotFoundError(
            f"Symbols data file not found: {SYMBOLS_FILE}\n"
            f"Expected location: src/binance_futures_availability/data/symbols.json"
        )

    with open(SYMBOLS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    perpetual = data["perpetual_symbols"]
    delivery = data["delivery_symbols"]

    if contract_type == "perpetual":
        return perpetual
    elif contract_type == "delivery":
        return delivery
    elif contract_type == "all":
        return perpetual + delivery
    else:
        raise ValueError(
            f"Invalid contract_type: {contract_type}. "
            f"Must be 'perpetual', 'delivery', or 'all'"
        )


def get_symbol_metadata() -> dict:
    """
    Get metadata about the symbol discovery process.

    Returns:
        Dict with discovery_date, source, method, and counts

    Example:
        >>> meta = get_symbol_metadata()
        >>> meta["discovery_date"]
        '2025-11-12'
        >>> meta["total_perpetual"]
        708
    """
    if not SYMBOLS_FILE.exists():
        raise FileNotFoundError(
            f"Symbols data file not found: {SYMBOLS_FILE}"
        )

    with open(SYMBOLS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data["metadata"]
