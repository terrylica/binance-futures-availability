"""
Binance Vision S3 Symbol Discovery via XML API.

Discovers all USDT futures symbols from Binance Vision S3 bucket using bucket listing.
No AWS credentials or API keys required - uses public bucket access.

Adapted from vision-futures-explorer/futures_discovery.py with the following changes:
- Removed PEP 723 script dependencies
- Added Python 3.12+ type hints
- Replaced print() with logging module
- Simplified return structure (dict instead of tuple)
- Aligned error handling with ADR-0003 (strict raise policy)

Performance: ~0.51s for ~369 symbols (proven benchmark from vision-futures-explorer)
"""

import logging
import urllib.request
from datetime import datetime
from xml.etree import ElementTree

logger = logging.getLogger(__name__)


def discover_all_futures_symbols(
    market_type: str = "um", granularity: str = "daily"
) -> dict[str, list[str]]:
    """
    Discover all futures symbols from Binance Vision S3 bucket via XML API.

    Uses S3 bucket listing to enumerate symbol directories. No authentication required
    for public buckets. Handles pagination automatically.

    Args:
        market_type: "um" (USDT-Margined) or "cm" (Coin-Margined). Default: "um"
        granularity: "daily" or "monthly". Default: "daily"

    Returns:
        Dict with symbol lists:
        {
            "perpetual": ["BTCUSDT", "ETHUSDT", ...],
            "delivery": ["BTCUSDT_231229", ...]
        }

    Raises:
        RuntimeError: S3 request timeout, network error, XML parse error

    Performance:
        ~0.51s for 369 symbols (empirically measured)

    Example:
        >>> symbols = discover_all_futures_symbols()
        >>> len(symbols["perpetual"])
        327
        >>> "BTCUSDT" in symbols["perpetual"]
        True
    """
    base_url = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
    prefix = f"data/futures/{market_type}/{granularity}/klines/"

    all_symbols: list[str] = []
    request_count = 0
    marker: str | None = None
    start_time = datetime.now()

    # S3 XML namespace
    ns = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}

    logger.info(f"Discovering {market_type.upper()} futures symbols from Binance Vision S3...")
    logger.debug(f"S3 prefix: {prefix}")

    while True:
        # Build request URL with optional marker for pagination
        params: dict[str, str] = {"prefix": prefix, "delimiter": "/"}
        if marker:
            params["marker"] = marker

        # Construct query string
        query_string = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{base_url}?{query_string}"

        request_count += 1
        logger.debug(f"S3 request #{request_count}: {url}")

        # Fetch S3 listing (raises on timeout/error - ADR-0003 compliant)
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                xml_data = response.read()
        except urllib.error.URLError as e:
            raise RuntimeError(f"Failed to fetch S3 listing: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Unexpected error during S3 listing: {e}") from e

        # Parse XML response (raises on malformed XML - ADR-0003 compliant)
        try:
            root = ElementTree.fromstring(xml_data)
        except ElementTree.ParseError as e:
            raise RuntimeError(f"Failed to parse S3 XML response: {e}") from e

        # Extract symbol directories from CommonPrefixes
        batch_symbols: list[str] = []
        for prefix_elem in root.findall(".//s3:CommonPrefixes/s3:Prefix", ns):
            # Example: "data/futures/um/daily/klines/BTCUSDT/"
            path = prefix_elem.text
            if path:
                symbol = path.rstrip("/").split("/")[-1]
                batch_symbols.append(symbol)

        all_symbols.extend(batch_symbols)
        logger.debug(f"Found {len(batch_symbols)} symbols this batch (total: {len(all_symbols)})")

        # Check if more results exist (pagination)
        is_truncated_elem = root.find(".//s3:IsTruncated", ns)
        is_truncated = is_truncated_elem is not None and is_truncated_elem.text == "true"

        if not is_truncated:
            break

        # Get next marker for pagination
        next_marker_elem = root.find(".//s3:NextMarker", ns)
        if next_marker_elem is not None:
            marker = next_marker_elem.text
        else:
            # Sometimes NextMarker is not provided, use last symbol as marker
            if batch_symbols:
                marker = f"{prefix}{batch_symbols[-1]}/"
            else:
                break

    duration = (datetime.now() - start_time).total_seconds()

    logger.info(f"Discovery complete: {len(all_symbols)} symbols in {duration:.2f}s")
    logger.info(f"S3 requests: {request_count}")

    # Classify symbols: perpetual vs delivery
    perpetual_symbols = filter_perpetual_contracts(all_symbols)
    delivery_symbols = [s for s in all_symbols if s not in perpetual_symbols]

    logger.info(
        f"Classification: {len(perpetual_symbols)} perpetual, {len(delivery_symbols)} delivery"
    )

    return {
        "perpetual": sorted(perpetual_symbols),
        "delivery": sorted(delivery_symbols),
    }


def classify_symbol(symbol: str) -> str:
    """
    Classify futures symbol as perpetual or delivery contract.

    Args:
        symbol: Futures symbol (e.g., "BTCUSDT" or "BTCUSDT_231229")

    Returns:
        "perpetual" for perpetual contracts, "delivery" for dated contracts

    Examples:
        >>> classify_symbol("BTCUSDT")
        'perpetual'
        >>> classify_symbol("BTCUSDT_231229")
        'delivery'
    """
    if "_" in symbol:
        # Delivery contract has underscore + date suffix: BTCUSDT_231229
        parts = symbol.rsplit("_", 1)
        date_str = parts[1]

        # Validate date format (YYMMDD)
        try:
            datetime.strptime(date_str, "%y%m%d")
            return "delivery"
        except ValueError:
            # Invalid date format, treat as perpetual variant
            return "perpetual"
    else:
        # No underscore = perpetual contract
        return "perpetual"


def filter_perpetual_contracts(symbols: list[str]) -> list[str]:
    """
    Filter symbol list to include only perpetual contracts.

    Args:
        symbols: List of all futures symbols (perpetual + delivery mixed)

    Returns:
        Filtered list containing only perpetual contracts

    Example:
        >>> symbols = ["BTCUSDT", "ETHUSDT", "BTCUSDT_231229"]
        >>> filter_perpetual_contracts(symbols)
        ['BTCUSDT', 'ETHUSDT']
    """
    return [s for s in symbols if classify_symbol(s) == "perpetual"]
