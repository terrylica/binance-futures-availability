"""Volume metrics from Binance Vision 1d kline files (ADR-0007), fetched over the shared HTTP pool.

One 1d kline zip is ~350 bytes, so a GET costs about the same as the availability HEAD probe.
Used by the daily update (lookback window) and by scripts/operations/backfill_volume.py.
"""

import csv
import datetime
import io
import logging
import urllib.parse
import zipfile
from concurrent.futures import ThreadPoolExecutor

from binance_futures_availability.database.availability_db import (
    VOLUME_COLUMNS,
    AvailabilityDatabase,
)
from binance_futures_availability.probing.s3_vision import HTTP_POOL, MAX_WORKERS

logger = logging.getLogger(__name__)

BASE_URL = "https://data.binance.vision/data/futures/um/daily/klines"


def parse_1d_kline_csv(csv_content: str, symbol: str, target_date: datetime.date) -> dict:
    """
    Parse a 1d kline CSV (optional header + one row of 12 fields) into the 9 volume metrics.

    Raises:
        RuntimeError: If the CSV shape or numeric fields are invalid
    """
    rows = [row for row in csv.reader(io.StringIO(csv_content)) if row]
    if rows and rows[0][0] == "open_time":
        rows = rows[1:]
    if len(rows) != 1 or len(rows[0]) != 12:
        raise RuntimeError(f"Unexpected 1d kline CSV shape for {symbol} {target_date}: {rows!r}")
    row = rows[0]
    try:
        return {
            "quote_volume_usdt": float(row[7]),
            "trade_count": int(row[8]),
            "volume_base": float(row[5]),
            "taker_buy_volume_base": float(row[9]),
            "taker_buy_quote_volume_usdt": float(row[10]),
            "open_price": float(row[1]),
            "high_price": float(row[2]),
            "low_price": float(row[3]),
            "close_price": float(row[4]),
        }
    except ValueError as e:
        raise RuntimeError(f"Non-numeric 1d kline field for {symbol} {target_date}: {e}") from e


def fetch_1d_volume(symbol: str, target_date: datetime.date) -> dict | None:
    """
    Download and parse one 1d kline file.

    Returns:
        The 9 volume metrics, or None on 404 (not published yet; the next lookback retries)

    Raises:
        RuntimeError: On any other HTTP status, network error, or malformed file (ADR-0003)
    """
    encoded = urllib.parse.quote(symbol, safe="")
    date_str = target_date.strftime("%Y-%m-%d")
    url = f"{BASE_URL}/{encoded}/1d/{encoded}-1d-{date_str}.zip"
    try:
        response = HTTP_POOL.request("GET", url)
    except Exception as e:
        raise RuntimeError(f"Network error fetching 1d kline {symbol} {date_str}: {e}") from e
    if response.status == 404:
        return None
    if response.status != 200:
        raise RuntimeError(f"1d kline fetch failed for {symbol} {date_str}: HTTP {response.status}")
    try:
        with zipfile.ZipFile(io.BytesIO(response.data)) as zf:
            csv_content = zf.read(zf.namelist()[0]).decode("utf-8")
    except (zipfile.BadZipFile, IndexError) as e:
        raise RuntimeError(f"Invalid 1d kline zip for {symbol} {date_str}: {e}") from e
    return parse_1d_kline_csv(csv_content, symbol, target_date)


def collect_missing_volume(
    db: AvailabilityDatabase,
    start_date: datetime.date,
    end_date: datetime.date,
    max_workers: int = MAX_WORKERS,
) -> dict[str, int]:
    """
    Fill volume metrics for available rows in [start_date, end_date] that have none yet.

    Returns:
        {"pending": rows needing volume, "filled": rows updated, "missing": 1d file not yet on S3}

    Raises:
        RuntimeError: If any fetch failed, after persisting all successful fetches
    """
    pending = db.query(
        "SELECT symbol, date FROM daily_availability "
        "WHERE available AND quote_volume_usdt IS NULL AND date BETWEEN ? AND ? "
        "ORDER BY date, symbol",
        [start_date, end_date],
    )
    logger.info(f"Volume: {len(pending):,} available rows lack volume ({start_date}..{end_date})")
    if not pending:
        return {"pending": 0, "filled": 0, "missing": 0}

    def fetch(item: tuple[str, datetime.date]):
        symbol, target_date = item
        try:
            return symbol, target_date, fetch_1d_volume(symbol, target_date), None
        except RuntimeError as e:
            return symbol, target_date, None, str(e)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(fetch, pending))

    # Persist every success BEFORE raising: one transient failure must not discard the rest
    # (measured: 1 DNS error in 43,060 fetches). Failed rows stay NULL and are retried next run.
    updates = [
        (*(metrics[c] for c in VOLUME_COLUMNS), symbol, target_date)
        for symbol, target_date, metrics, _ in results
        if metrics is not None
    ]
    if updates:
        db.conn.executemany(
            f"UPDATE daily_availability SET {', '.join(f'{c} = ?' for c in VOLUME_COLUMNS)} "
            "WHERE symbol = ? AND date = ?",
            updates,
        )
    failed = [(s, d, err) for s, d, _, err in results if err]
    stats = {
        "pending": len(pending),
        "filled": len(updates),
        "missing": len(pending) - len(updates) - len(failed),
    }
    logger.info(
        f"Volume: filled {stats['filled']:,}, 1d file not yet published {stats['missing']:,}"
    )
    if failed:
        summary = "\n".join(f"  - {s} {d}: {err}" for s, d, err in failed[:20])
        raise RuntimeError(
            f"Volume fetch failed for {len(failed)}/{len(pending)} rows "
            f"({stats['filled']:,} filled rows were kept):\n{summary}"
        )
    return stats
