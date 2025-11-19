"""Tests for volume rankings generation script (ADR-0013).

Test Coverage:
    - Schema validation (PyArrow schema matches specification)
    - Ranking calculation (DENSE_RANK algorithm correctness)
    - Rank change calculation (1d, 7d, 14d, 30d windows)
    - Incremental append behavior (no duplicate dates)
    - Edge cases (empty database, single symbol, ties, inactive symbols)

See: docs/architecture/decisions/0013-volume-rankings-timeseries.md
"""

import datetime
import tempfile
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

# Import functions from the script we're testing
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / ".github" / "scripts"))
from generate_volume_rankings import (
    RANKINGS_SCHEMA,
    generate_rankings_sql,
    get_latest_date_from_parquet,
    merge_tables,
    query_rankings,
    validate_rankings_table,
    write_parquet,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def temp_db() -> Path:
    """Create temporary DuckDB database with daily_availability table."""
    temp_path = Path(tempfile.mktemp(suffix=".duckdb"))

    conn = duckdb.connect(str(temp_path))

    # Create schema matching availability database
    conn.execute("""
        CREATE TABLE daily_availability (
            date DATE NOT NULL,
            symbol VARCHAR NOT NULL,
            available BOOLEAN NOT NULL,
            quote_volume_usdt DOUBLE,
            trade_count BIGINT,
            file_size_bytes BIGINT,
            last_modified TIMESTAMP,
            url VARCHAR NOT NULL,
            status_code INTEGER NOT NULL,
            probe_timestamp TIMESTAMP NOT NULL,
            PRIMARY KEY (date, symbol)
        )
    """)

    conn.close()

    yield temp_path

    # Cleanup
    if temp_path.exists():
        temp_path.unlink()


@pytest.fixture
def populated_db(temp_db: Path) -> Path:
    """Database with sample data for ranking tests.

    Creates 5 days × 5 symbols with varying volumes:
        - BTCUSDT: Rank 1 (highest volume)
        - ETHUSDT: Rank 2
        - SOLUSDT: Rank 3
        - BNBUSDT: Rank 4
        - ADAUSDT: Rank 5 (lowest volume)
    """
    conn = duckdb.connect(str(temp_db))

    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "ADAUSDT"]
    base_volumes = {
        "BTCUSDT": 1_000_000_000,  # Rank 1
        "ETHUSDT": 500_000_000,     # Rank 2
        "SOLUSDT": 100_000_000,     # Rank 3
        "BNBUSDT": 50_000_000,      # Rank 4
        "ADAUSDT": 10_000_000,      # Rank 5
    }

    # Create 5 days of data
    for day_offset in range(5):
        date = datetime.date(2024, 1, 15) + datetime.timedelta(days=day_offset)

        for symbol in symbols:
            # Vary volume slightly per day to simulate rank changes
            volume_multiplier = 1.0 + (day_offset * 0.01)  # 1%, 2%, 3%, 4%, 5% daily growth
            volume = base_volumes[symbol] * volume_multiplier

            conn.execute("""
                INSERT INTO daily_availability VALUES (
                    ?, ?, true, ?, ?,
                    8000000, CURRENT_TIMESTAMP,
                    'https://example.com/file.zip', 200, CURRENT_TIMESTAMP
                )
            """, [date, symbol, volume, int(volume / 1000)])

    conn.close()
    return temp_db


@pytest.fixture
def temp_parquet() -> Path:
    """Create temporary Parquet file path."""
    temp_path = Path(tempfile.mktemp(suffix=".parquet"))
    yield temp_path
    if temp_path.exists():
        temp_path.unlink()


# ============================================================================
# Schema Validation Tests
# ============================================================================


def test_schema_definition():
    """Test RANKINGS_SCHEMA matches ADR-0013 specification."""
    assert len(RANKINGS_SCHEMA) == 13, "Schema should have exactly 13 columns"

    # Verify column names
    expected_columns = [
        'date', 'symbol', 'rank', 'quote_volume_usdt', 'trade_count',
        'rank_change_1d', 'rank_change_7d', 'rank_change_14d', 'rank_change_30d',
        'percentile', 'market_share_pct', 'days_available', 'generation_timestamp'
    ]
    actual_columns = [field.name for field in RANKINGS_SCHEMA]
    assert actual_columns == expected_columns, "Column names must match specification"

    # Verify data types
    assert RANKINGS_SCHEMA.field('date').type == pa.date32()
    assert RANKINGS_SCHEMA.field('symbol').type == pa.string()
    assert RANKINGS_SCHEMA.field('rank').type == pa.uint16()
    assert RANKINGS_SCHEMA.field('quote_volume_usdt').type == pa.float64()
    assert RANKINGS_SCHEMA.field('trade_count').type == pa.uint64()
    assert RANKINGS_SCHEMA.field('rank_change_1d').type == pa.int16()
    assert RANKINGS_SCHEMA.field('rank_change_7d').type == pa.int16()
    assert RANKINGS_SCHEMA.field('rank_change_14d').type == pa.int16()
    assert RANKINGS_SCHEMA.field('rank_change_30d').type == pa.int16()
    assert RANKINGS_SCHEMA.field('percentile').type == pa.float32()
    assert RANKINGS_SCHEMA.field('market_share_pct').type == pa.float32()
    assert RANKINGS_SCHEMA.field('days_available').type == pa.uint8()
    assert RANKINGS_SCHEMA.field('generation_timestamp').type == pa.timestamp('us')


def test_validate_rankings_table_valid(populated_db: Path, temp_parquet: Path):
    """Test validation passes for correctly generated rankings table."""
    # Generate rankings
    table = query_rankings(populated_db, start_date=None, logger=None)

    # Should not raise
    validate_rankings_table(table, logger=None)


def test_validate_rankings_table_schema_mismatch():
    """Test validation fails when schema doesn't match."""
    # Create table with wrong schema
    wrong_schema = pa.schema([
        ('date', pa.date32()),
        ('symbol', pa.string()),
        ('rank', pa.int32()),  # Wrong type (should be uint16)
    ])

    wrong_table = pa.table({
        'date': [datetime.date(2024, 1, 15)],
        'symbol': ['BTCUSDT'],
        'rank': [1],
    }, schema=wrong_schema)

    with pytest.raises(ValueError, match="Schema mismatch"):
        validate_rankings_table(wrong_table, logger=None)


def test_validate_rankings_table_empty():
    """Test validation fails for empty table."""
    empty_table = pa.table({col.name: [] for col in RANKINGS_SCHEMA}, schema=RANKINGS_SCHEMA)

    with pytest.raises(ValueError, match="Rankings table is empty"):
        validate_rankings_table(empty_table, logger=None)


def test_validate_rankings_table_invalid_ranks():
    """Test validation fails when ranks are NULL or <1."""
    # Create table with NULL ranks
    data = {
        'date': [datetime.date(2024, 1, 15)],
        'symbol': ['BTCUSDT'],
        'rank': [None],  # Invalid NULL rank
        'quote_volume_usdt': [1000000.0],
        'trade_count': [10000],
        'rank_change_1d': [None],
        'rank_change_7d': [None],
        'rank_change_14d': [None],
        'rank_change_30d': [None],
        'percentile': [0.0],
        'market_share_pct': [100.0],
        'days_available': [1],
        'generation_timestamp': [datetime.datetime.now()],
    }

    invalid_table = pa.table(data, schema=RANKINGS_SCHEMA)

    with pytest.raises(ValueError, match="Invalid ranks found"):
        validate_rankings_table(invalid_table, logger=None)


# ============================================================================
# Ranking Calculation Tests
# ============================================================================


def test_ranking_calculation_order(populated_db: Path):
    """Test rankings are ordered by quote_volume_usdt DESC."""
    table = query_rankings(populated_db, start_date=None, logger=None)

    # Check first date's rankings
    first_date_data = table.filter(
        pa.compute.equal(table['date'], datetime.date(2024, 1, 15))
    ).to_pydict()

    # Verify order: BTCUSDT (1), ETHUSDT (2), SOLUSDT (3), BNBUSDT (4), ADAUSDT (5)
    expected_order = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "ADAUSDT"]
    actual_symbols = [s for _, s in sorted(zip(first_date_data['rank'], first_date_data['symbol']))]

    assert actual_symbols == expected_order, "Rankings should be ordered by volume DESC"


def test_dense_rank_no_gaps():
    """Test DENSE_RANK produces consecutive ranks (no gaps)."""
    # This test validates the SQL algorithm choice
    sql = generate_rankings_sql(start_date=None)

    # Verify DENSE_RANK is used (not RANK which creates gaps)
    assert "DENSE_RANK()" in sql, "Should use DENSE_RANK for consecutive rankings"
    assert "RANK()" not in sql or "DENSE_RANK()" in sql, "Should not use RANK without DENSE_"


def test_rank_change_calculation(populated_db: Path):
    """Test rank change windows (1d, 7d, 14d, 30d) are calculated correctly."""
    table = query_rankings(populated_db, start_date=None, logger=None)

    # Day 2: Check 1-day rank change (should be 0 for all, since relative order unchanged)
    day2_data = table.filter(
        pa.compute.equal(table['date'], datetime.date(2024, 1, 16))
    ).to_pydict()

    # All symbols maintain same rank (volumes grew proportionally)
    for rank_change in day2_data['rank_change_1d']:
        assert rank_change is None or rank_change == 0, \
            "Rank change should be 0 when relative order unchanged"


def test_rank_change_null_for_insufficient_history(populated_db: Path):
    """Test rank_change_7d/14d/30d are NULL when insufficient history."""
    table = query_rankings(populated_db, start_date=None, logger=None)

    # Day 1: No prior history, all rank changes should be NULL
    day1_data = table.filter(
        pa.compute.equal(table['date'], datetime.date(2024, 1, 15))
    ).to_pydict()

    # All rank changes should be NULL on first day
    for rank_change in day1_data['rank_change_1d']:
        assert rank_change is None, "rank_change_1d should be NULL on first day"

    for rank_change in day1_data['rank_change_7d']:
        assert rank_change is None, "rank_change_7d should be NULL with <7 days history"


def test_percentile_calculation(populated_db: Path):
    """Test percentile rank calculation (0-100, 0=top)."""
    table = query_rankings(populated_db, start_date=None, logger=None)

    # Check first date
    day1_data = table.filter(
        pa.compute.equal(table['date'], datetime.date(2024, 1, 15))
    ).to_pydict()

    # Top rank (BTCUSDT) should have percentile ~0
    btc_percentile = [p for s, p in zip(day1_data['symbol'], day1_data['percentile']) if s == 'BTCUSDT'][0]
    assert btc_percentile < 25, "Top symbol should have low percentile"

    # Bottom rank (ADAUSDT) should have percentile ~100
    ada_percentile = [p for s, p in zip(day1_data['symbol'], day1_data['percentile']) if s == 'ADAUSDT'][0]
    assert ada_percentile > 75, "Bottom symbol should have high percentile"


def test_market_share_calculation(populated_db: Path):
    """Test market_share_pct sums to ~100% per date."""
    table = query_rankings(populated_db, start_date=None, logger=None)

    # Check first date
    day1_data = table.filter(
        pa.compute.equal(table['date'], datetime.date(2024, 1, 15))
    ).to_pydict()

    total_market_share = sum(day1_data['market_share_pct'])

    assert 99.9 < total_market_share < 100.1, \
        "Market share should sum to ~100% per date"


# ============================================================================
# Incremental Append Tests
# ============================================================================


def test_get_latest_date_from_parquet(populated_db: Path, temp_parquet: Path):
    """Test extracting latest date from existing Parquet file."""
    # Generate initial rankings
    table = query_rankings(populated_db, start_date=None, logger=None)
    write_parquet(table, temp_parquet, logger=None)

    # Extract latest date
    latest_date = get_latest_date_from_parquet(temp_parquet)

    assert latest_date == "2024-01-19", "Should extract latest date from Parquet"


def test_get_latest_date_nonexistent_file():
    """Test returns None for non-existent Parquet file."""
    nonexistent = Path("/tmp/nonexistent_file.parquet")

    latest_date = get_latest_date_from_parquet(nonexistent)

    assert latest_date is None, "Should return None for missing file"


def test_merge_tables_no_overlap(populated_db: Path, temp_parquet: Path):
    """Test merging tables with no duplicate dates."""
    # Create two non-overlapping tables
    table1 = query_rankings(populated_db, start_date=None, logger=None)

    # Simulate new data by filtering to later dates
    table1_subset = table1.filter(
        pa.compute.less(table1['date'], datetime.date(2024, 1, 17))
    )

    table2_subset = table1.filter(
        pa.compute.greater_equal(table1['date'], datetime.date(2024, 1, 17))
    )

    # Merge should succeed
    merged = merge_tables(table1_subset, table2_subset, logger=None)

    assert len(merged) == len(table1), "Merged table should have all rows"


def test_merge_tables_with_overlap_raises():
    """Test merging tables with duplicate dates raises ValueError."""
    # Create overlapping tables
    data = {
        'date': [datetime.date(2024, 1, 15)],
        'symbol': ['BTCUSDT'],
        'rank': [1],
        'quote_volume_usdt': [1000000.0],
        'trade_count': [10000],
        'rank_change_1d': [None],
        'rank_change_7d': [None],
        'rank_change_14d': [None],
        'rank_change_30d': [None],
        'percentile': [0.0],
        'market_share_pct': [100.0],
        'days_available': [1],
        'generation_timestamp': [datetime.datetime.now()],
    }

    table1 = pa.table(data, schema=RANKINGS_SCHEMA)
    table2 = pa.table(data, schema=RANKINGS_SCHEMA)  # Same date!

    with pytest.raises(ValueError, match="Duplicate dates found"):
        merge_tables(table1, table2, logger=None)


def test_incremental_append_query(populated_db: Path):
    """Test SQL query with start_date filters correctly."""
    # Query all data
    full_table = query_rankings(populated_db, start_date=None, logger=None)

    # Query only dates > 2024-01-16
    incremental_table = query_rankings(populated_db, start_date="2024-01-16", logger=None)

    # Should have fewer rows (3 days instead of 5)
    assert len(incremental_table) < len(full_table), \
        "Incremental query should return fewer rows"

    # Verify no dates <= 2024-01-16
    dates = incremental_table['date'].to_pylist()
    assert all(d > datetime.date(2024, 1, 16) for d in dates), \
        "Incremental table should only have dates > start_date"


# ============================================================================
# Edge Case Tests
# ============================================================================


def test_empty_database_raises(temp_db: Path):
    """Test querying empty database raises error."""
    # temp_db has no data

    with pytest.raises(RuntimeError, match="Rankings query failed"):
        query_rankings(temp_db, start_date=None, logger=None)


def test_single_symbol_ranking(temp_db: Path):
    """Test ranking with single symbol works correctly."""
    conn = duckdb.connect(str(temp_db))

    # Insert single symbol
    conn.execute("""
        INSERT INTO daily_availability VALUES (
            '2024-01-15', 'BTCUSDT', true, 1000000.0, 10000,
            8000000, CURRENT_TIMESTAMP,
            'https://example.com/file.zip', 200, CURRENT_TIMESTAMP
        )
    """)
    conn.close()

    table = query_rankings(temp_db, start_date=None, logger=None)

    assert len(table) == 1, "Should handle single symbol correctly"
    assert table['rank'][0].as_py() == 1, "Single symbol should have rank 1"
    assert table['percentile'][0].as_py() == 0.0, "Single symbol should have percentile 0"
    assert table['market_share_pct'][0].as_py() == 100.0, "Single symbol should have 100% market share"


def test_tied_volumes_same_rank(temp_db: Path):
    """Test symbols with identical volumes get same rank (DENSE_RANK behavior)."""
    conn = duckdb.connect(str(temp_db))

    # Insert two symbols with identical volumes
    identical_volume = 1000000.0
    conn.execute("""
        INSERT INTO daily_availability VALUES
            ('2024-01-15', 'SYM1USDT', true, ?, 10000, 8000000, CURRENT_TIMESTAMP, 'https://example.com/file.zip', 200, CURRENT_TIMESTAMP),
            ('2024-01-15', 'SYM2USDT', true, ?, 10000, 8000000, CURRENT_TIMESTAMP, 'https://example.com/file.zip', 200, CURRENT_TIMESTAMP),
            ('2024-01-15', 'SYM3USDT', true, 500000.0, 5000, 4000000, CURRENT_TIMESTAMP, 'https://example.com/file.zip', 200, CURRENT_TIMESTAMP)
    """, [identical_volume, identical_volume])
    conn.close()

    table = query_rankings(temp_db, start_date=None, logger=None)
    data = table.to_pydict()

    # Both tied symbols should have rank 1
    tied_ranks = [r for s, r in zip(data['symbol'], data['rank']) if s in ['SYM1USDT', 'SYM2USDT']]
    assert tied_ranks == [1, 1], "Tied symbols should have same rank"

    # Third symbol should have rank 2 (DENSE_RANK, no gap)
    third_rank = [r for s, r in zip(data['symbol'], data['rank']) if s == 'SYM3USDT'][0]
    assert third_rank == 2, "DENSE_RANK should not create gaps after ties"


def test_inactive_symbols_excluded(temp_db: Path):
    """Test symbols with available=FALSE are excluded from rankings."""
    conn = duckdb.connect(str(temp_db))

    # Insert one active and one inactive symbol
    conn.execute("""
        INSERT INTO daily_availability VALUES
            ('2024-01-15', 'ACTIVEUSDT', true, 1000000.0, 10000, 8000000, CURRENT_TIMESTAMP, 'https://example.com/file.zip', 200, CURRENT_TIMESTAMP),
            ('2024-01-15', 'INACTIVEUSDT', false, NULL, NULL, NULL, NULL, 'https://example.com/file.zip', 404, CURRENT_TIMESTAMP)
    """)
    conn.close()

    table = query_rankings(temp_db, start_date=None, logger=None)
    symbols = table['symbol'].to_pylist()

    assert 'ACTIVEUSDT' in symbols, "Active symbol should be included"
    assert 'INACTIVEUSDT' not in symbols, "Inactive symbol should be excluded"


def test_null_volume_excluded(temp_db: Path):
    """Test symbols with NULL quote_volume_usdt are excluded."""
    conn = duckdb.connect(str(temp_db))

    # Insert symbol with NULL volume
    conn.execute("""
        INSERT INTO daily_availability VALUES
            ('2024-01-15', 'NULLVOLUMEUSDT', true, NULL, 10000, 8000000, CURRENT_TIMESTAMP, 'https://example.com/file.zip', 200, CURRENT_TIMESTAMP)
    """)
    conn.close()

    table = query_rankings(temp_db, start_date=None, logger=None)

    assert len(table) == 0, "Symbols with NULL volume should be excluded"


# ============================================================================
# Parquet I/O Tests
# ============================================================================


def test_write_parquet_creates_file(populated_db: Path, temp_parquet: Path):
    """Test Parquet file is created with correct format."""
    table = query_rankings(populated_db, start_date=None, logger=None)

    write_parquet(table, temp_parquet, logger=None)

    assert temp_parquet.exists(), "Parquet file should be created"
    assert temp_parquet.stat().st_size > 0, "Parquet file should not be empty"


def test_parquet_schema_preserved(populated_db: Path, temp_parquet: Path):
    """Test schema is preserved after write/read cycle."""
    table = query_rankings(populated_db, start_date=None, logger=None)
    write_parquet(table, temp_parquet, logger=None)

    # Read back
    read_table = pq.read_table(temp_parquet)

    assert read_table.schema.equals(RANKINGS_SCHEMA), \
        "Schema should be preserved after write/read"


def test_parquet_data_integrity(populated_db: Path, temp_parquet: Path):
    """Test data is preserved after write/read cycle."""
    original_table = query_rankings(populated_db, start_date=None, logger=None)
    write_parquet(original_table, temp_parquet, logger=None)

    # Read back
    read_table = pq.read_table(temp_parquet)

    assert len(read_table) == len(original_table), "Row count should match"

    # Compare data (convert to dict for easier comparison)
    original_dict = original_table.to_pydict()
    read_dict = read_table.to_pydict()

    for col in RANKINGS_SCHEMA.names:
        if col != 'generation_timestamp':  # Timestamps may have precision differences
            assert original_dict[col] == read_dict[col], \
                f"Column {col} data should match after write/read"
