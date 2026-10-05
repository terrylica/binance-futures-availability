"""Regression tests for the silent `available` corruption (2025-11 to 2026-10).

Under DuckDB 1.4.x, INSERT OR REPLACE skipped columns that belonged to a secondary index, so a
re-probe returning 200 could not flip a row stored as 404/false. See schema._UPSERT_BREAKING_INDEXES.
"""

import datetime

import duckdb

from binance_futures_availability.database.availability_db import AvailabilityDatabase

DAY = datetime.date(2026, 9, 17)
NOW = datetime.datetime(2026, 10, 5, 10, 0, 0, tzinfo=datetime.UTC)


def _probe(symbol: str, status: int, **extra) -> dict:
    return {
        "date": DAY,
        "symbol": symbol,
        "available": status == 200,
        "file_size_bytes": 60729 if status == 200 else None,
        "last_modified": NOW if status == 200 else None,
        "url": f"https://data.binance.vision/{symbol}",
        "status_code": status,
        "probe_timestamp": NOW,
        **extra,
    }


def _row(db: AvailabilityDatabase, symbol: str) -> tuple:
    return db.conn.execute(
        "SELECT available, status_code, quote_volume_usdt FROM daily_availability "
        "WHERE date = ? AND symbol = ?",
        [DAY, symbol],
    ).fetchone()


def test_reprobe_flips_unavailable_to_available(temp_db_path):
    """A T+1 404 followed by a 200 on the lookback re-probe must end up available."""
    db = AvailabilityDatabase(db_path=temp_db_path)
    symbols = [f"S{i}USDT" for i in range(500)]
    db.insert_batch([_probe(s, 404) for s in symbols])
    db.close()

    db = AvailabilityDatabase(db_path=temp_db_path)  # persisted table, as in CI
    db.insert_batch([_probe(s, 200) for s in symbols])
    rows = db.conn.execute(
        "SELECT available, status_code, count(*) FROM daily_availability GROUP BY ALL"
    ).fetchall()
    db.close()
    assert rows == [(True, 200, 500)]


def test_reprobe_without_volume_keeps_existing_volume(db):
    db.insert_batch([_probe("BTCUSDT", 200, quote_volume_usdt=1.5e10, trade_count=7)])
    db.insert_batch([_probe("BTCUSDT", 200)])
    assert _row(db, "BTCUSDT") == (True, 200, 1.5e10)


def test_reprobe_with_volume_overwrites_volume(db):
    db.insert_batch([_probe("BTCUSDT", 200, quote_volume_usdt=1.0)])
    db.insert_batch([_probe("BTCUSDT", 200, quote_volume_usdt=2.0)])
    assert _row(db, "BTCUSDT") == (True, 200, 2.0)


def test_legacy_database_is_migrated_and_repaired(temp_db_path):
    """Opening a DB that still carries the legacy indexes drops them and repairs `available`."""
    db = AvailabilityDatabase(db_path=temp_db_path)
    db.insert_batch([_probe("BTCUSDT", 200), _probe("DEADUSDT", 404)])
    db.close()

    conn = duckdb.connect(str(temp_db_path))
    conn.execute("CREATE INDEX idx_available_date ON daily_availability(available, date)")
    conn.execute("DROP INDEX idx_available_date")  # simulate corruption without the index
    conn.execute("UPDATE daily_availability SET available = false")
    conn.execute("CREATE INDEX idx_available_date ON daily_availability(available, date)")
    conn.close()

    db = AvailabilityDatabase(db_path=temp_db_path)
    indexes = {r[0] for r in db.conn.execute("SELECT index_name FROM duckdb_indexes()").fetchall()}
    counts = db.conn.execute(
        "SELECT available_symbols, unavailable_symbols FROM daily_symbol_counts WHERE date = ?",
        [DAY],
    ).fetchone()
    assert "idx_available_date" not in indexes
    assert _row(db, "BTCUSDT")[0] is True
    assert _row(db, "DEADUSDT")[0] is False
    assert counts == (1, 1)
    db.close()
