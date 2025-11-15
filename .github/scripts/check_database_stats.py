#!/usr/bin/env python3
"""Check database stats after download."""
import sys
import os
import duckdb

db_path = os.environ.get('DB_PATH')
if not db_path:
    print('Error: DB_PATH environment variable not set')
    sys.exit(1)

try:
    conn = duckdb.connect(db_path, read_only=True)
    result = conn.execute('''
        SELECT
            MIN(date) as earliest_date,
            MAX(date) as latest_date,
            COUNT(DISTINCT date) as total_dates,
            COUNT(DISTINCT symbol) as total_symbols
        FROM daily_availability
    ''').fetchone()
    conn.close()
    print(f'Database stats: {result[0]} to {result[1]}, {result[2]} dates, {result[3]} symbols')
except Exception as e:
    print(f'Error querying database: {e}')
    sys.exit(1)
