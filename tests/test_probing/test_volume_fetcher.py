"""Tests for 1d-kline volume fetching (ADR-0007) over the shared HTTP pool."""

import datetime
import io
import zipfile
from unittest.mock import MagicMock

import pytest

from binance_futures_availability.probing import volume_fetcher
from binance_futures_availability.probing.volume_fetcher import (
    collect_missing_volume,
    fetch_1d_volume,
    parse_1d_kline_csv,
)

DAY = datetime.date(2026, 10, 3)
HEADER = (
    "open_time,open,high,low,close,volume,close_time,quote_volume,count,"
    "taker_buy_volume,taker_buy_quote_volume,ignore\n"
)
ROW = (
    "1790985600000,84482.70,84994.90,84409.50,84710.60,43165.689,1791071999999,"
    "3655672542.40470,885100,20823.629,1763687920.41070,0\n"
)


def _zip(csv_text: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(f"BTCUSDT-1d-{DAY}.csv", csv_text)
    return buf.getvalue()


def _response(status: int, data: bytes = b"") -> MagicMock:
    return MagicMock(status=status, data=data)


@pytest.mark.parametrize("csv_text", [HEADER + ROW, ROW])
def test_parse_with_and_without_header(csv_text):
    metrics = parse_1d_kline_csv(csv_text, "BTCUSDT", DAY)
    assert metrics["quote_volume_usdt"] == pytest.approx(3655672542.4047)
    assert metrics["trade_count"] == 885100
    assert metrics["close_price"] == pytest.approx(84710.6)


def test_parse_rejects_malformed_csv():
    with pytest.raises(RuntimeError, match="Unexpected 1d kline CSV shape"):
        parse_1d_kline_csv(HEADER + "1,2,3\n", "BTCUSDT", DAY)


def test_fetch_parses_zip(mocker):
    mocker.patch.object(
        volume_fetcher.HTTP_POOL, "request", return_value=_response(200, _zip(HEADER + ROW))
    )
    metrics = fetch_1d_volume("BTCUSDT", DAY)
    assert metrics is not None
    assert metrics["trade_count"] == 885100


def test_fetch_returns_none_on_404(mocker):
    mocker.patch.object(volume_fetcher.HTTP_POOL, "request", return_value=_response(404))
    assert fetch_1d_volume("BTCUSDT", DAY) is None


def test_fetch_raises_on_other_status(mocker):
    mocker.patch.object(volume_fetcher.HTTP_POOL, "request", return_value=_response(503))
    with pytest.raises(RuntimeError, match="HTTP 503"):
        fetch_1d_volume("BTCUSDT", DAY)


def _seed(db, symbol: str, available: bool) -> None:
    db.insert_availability(
        date=DAY,
        symbol=symbol,
        available=available,
        file_size_bytes=100 if available else None,
        last_modified=None,
        url="u",
        status_code=200 if available else 404,
        probe_timestamp=datetime.datetime.now(datetime.UTC),
    )


def test_collect_fills_available_rows_and_skips_unpublished(db, mocker):
    _seed(db, "BTCUSDT", True)
    _seed(db, "NEWUSDT", True)
    _seed(db, "DEADUSDT", False)
    metrics = parse_1d_kline_csv(ROW, "BTCUSDT", DAY)
    fetch = mocker.patch.object(
        volume_fetcher,
        "fetch_1d_volume",
        side_effect=lambda s, d: metrics if s == "BTCUSDT" else None,
    )

    stats = collect_missing_volume(db, DAY, DAY, max_workers=2)

    assert stats == {"pending": 2, "filled": 1, "missing": 1}
    assert {c.args[0] for c in fetch.call_args_list} == {"BTCUSDT", "NEWUSDT"}
    rows = dict(db.query("SELECT symbol, trade_count FROM daily_availability"))
    assert rows == {"BTCUSDT": 885100, "NEWUSDT": None, "DEADUSDT": None}

    # An availability-only re-probe must not wipe the collected volume
    _seed(db, "BTCUSDT", True)
    assert db.query("SELECT trade_count FROM daily_availability WHERE symbol = 'BTCUSDT'") == [
        (885100,)
    ]
    # Nothing left to fetch for BTCUSDT on the next run
    fetch.reset_mock()
    collect_missing_volume(db, DAY, DAY, max_workers=2)
    assert [c.args[0] for c in fetch.call_args_list] == ["NEWUSDT"]


def test_collect_keeps_successes_then_raises_on_failure(db, mocker):
    _seed(db, "BTCUSDT", True)
    _seed(db, "FLAKYUSDT", True)
    metrics = parse_1d_kline_csv(ROW, "BTCUSDT", DAY)

    def fetch(symbol, _date):
        if symbol == "FLAKYUSDT":
            raise RuntimeError("DNS failure")
        return metrics

    mocker.patch.object(volume_fetcher, "fetch_1d_volume", side_effect=fetch)
    with pytest.raises(RuntimeError, match=r"failed for 1/2 rows \(1 filled rows were kept\)"):
        collect_missing_volume(db, DAY, DAY, max_workers=2)
    rows = dict(db.query("SELECT symbol, trade_count FROM daily_availability"))
    assert rows == {"BTCUSDT": 885100, "FLAKYUSDT": None}
