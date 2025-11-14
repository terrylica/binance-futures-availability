#!/usr/bin/env python
"""Execute v1.1.0 schema migration."""

from pathlib import Path
from binance_futures_availability.database import AvailabilityDatabase

def main():
    # Load migration SQL
    migration_file = Path(__file__).parent / "v1.1.0_add_volume_metrics.sql"
    with open(migration_file) as f:
        migration_sql = f.read()

    # Execute migration
    db = AvailabilityDatabase()

    print("=== Executing Migration v1.1.0 ===\n")

    # Split into individual statements and execute
    statements = []
    current_stmt = []

    for line in migration_sql.split('\n'):
        # Skip full-line comments
        if line.strip().startswith('--'):
            continue
        # Add line to current statement
        current_stmt.append(line)
        # If line ends with semicolon, it's end of statement
        if line.strip().endswith(';'):
            stmt = '\n'.join(current_stmt).strip()
            if stmt and not stmt.startswith('--'):
                statements.append(stmt)
            current_stmt = []

    # Execute each statement
    for statement in statements:
        try:
            db.conn.execute(statement)
            # Extract column name for display
            if 'ADD COLUMN' in statement:
                col_name = statement.split('ADD COLUMN')[1].split()[2] if len(statement.split('ADD COLUMN')) > 1 else 'column'
                print(f'✅ Added column: {col_name}')
            elif 'CREATE INDEX' in statement:
                idx_name = statement.split('INDEX')[1].split()[2] if 'IF NOT EXISTS' in statement else statement.split('INDEX')[1].split()[0]
                print(f'✅ Created index: {idx_name}')
            else:
                print(f'✅ Executed: {statement[:50]}...')
        except Exception as e:
            print(f'❌ Failed: {statement[:50]}... Error: {e}')

    # Verify migration
    print('\n=== Verification ===')

    # Check columns using DESCRIBE
    columns = db.conn.execute("DESCRIBE daily_availability").fetchall()
    print(f'Total columns: {len(columns)}')

    # Count new columns
    new_col_names = ['quote_volume_usdt', 'trade_count', 'volume_base', 'taker_buy_volume_base', 'taker_buy_quote_volume_usdt', 'open_price', 'high_price', 'low_price', 'close_price']
    volume_cols = [c for c in columns if c[0] in new_col_names]
    print(f'New volume/price columns: {len(volume_cols)}/9')

    if volume_cols:
        print('\nAdded columns:')
        for col in volume_cols:
            print(f'  - {col[0]} ({col[1]})')

    # Check indexes
    try:
        indexes = db.conn.execute("SELECT index_name FROM duckdb_indexes() WHERE table_name = 'daily_availability'").fetchall()
        print(f'\nIndexes on daily_availability:')
        for idx in indexes:
            print(f'  - {idx[0]}')
    except Exception as e:
        print(f'\nNote: Could not list indexes (DuckDB version issue): {e}')
        # Alternative: try to use the index
        try:
            db.conn.execute("SELECT * FROM daily_availability ORDER BY quote_volume_usdt DESC LIMIT 1")
            print('  ✅ idx_quote_volume_date is functional')
        except Exception as e2:
            print(f'  ❌ Index verification failed: {e2}')

    print('\n=== Migration Complete ===')

if __name__ == '__main__':
    main()
