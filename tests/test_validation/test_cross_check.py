"""Tests for the exchangeInfo cross-check (recall over API TRADING perpetuals)."""

import datetime
import io
import json

from binance_futures_availability.validation import cross_check
from binance_futures_availability.validation.cross_check import CrossCheckValidator

DAY = datetime.date(2026, 10, 3)


def _exchange_info(*symbols: tuple[str, str, str]) -> io.BytesIO:
    payload = {"symbols": [{"symbol": s, "contractType": c, "status": st} for s, c, st in symbols]}
    return io.BytesIO(json.dumps(payload).encode())


def test_recall_scopes_to_trading_perpetuals(db, temp_db_path, mocker):
    now = datetime.datetime.now(datetime.UTC)
    for symbol in ("BTCUSDT", "1000PEPEUSDC", "AAPLUSDT", "OLDUSDT"):
        db.insert_availability(
            date=DAY,
            symbol=symbol,
            available=True,
            file_size_bytes=1,
            last_modified=None,
            url="u",
            status_code=200,
            probe_timestamp=now,
        )
    db.close()
    mocker.patch.object(
        cross_check.urllib.request,
        "urlopen",
        return_value=_exchange_info(
            ("BTCUSDT", "PERPETUAL", "TRADING"),
            ("1000PEPEUSDC", "PERPETUAL", "TRADING"),  # non-USDT quote counts
            ("AAPLUSDT", "TRADIFI_PERPETUAL", "TRADING"),  # TradFi perp counts
            ("NEWUSDT", "PERPETUAL", "TRADING"),  # missing from DB -> lowers recall
            ("OLDUSDT", "PERPETUAL", "SETTLING"),  # still publishes; DB-only is fine
            ("BTCUSDT_261225", "CURRENT_QUARTER", "TRADING"),  # out of scope
        ),
    )

    with CrossCheckValidator(db_path=temp_db_path) as validator:
        result = validator.cross_check_current_date(DAY)

    assert result["api_symbol_count"] == 4
    assert result["match_percentage"] == 75.0
    assert result["only_in_api"] == ["NEWUSDT"]
    assert result["only_in_db"] == ["OLDUSDT"]
    assert result["slo_met"] is False
