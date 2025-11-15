#!/usr/bin/env python3
"""Generate comprehensive database statistics."""
import sys
import os
import json
import duckdb

db_path = os.environ.get('DB_PATH')
if not db_path:
    print('Error: DB_PATH environment variable not set')
    sys.exit(1)

try:
    conn = duckdb.connect(db_path, read_only=True)

    # Overall stats
    overall = conn.execute('''
        SELECT
            MIN(date) as earliest_date,
            MAX(date) as latest_date,
            COUNT(DISTINCT date) as total_dates,
            COUNT(DISTINCT symbol) as total_symbols,
            COUNT(*) as total_records,
            SUM(CASE WHEN available THEN 1 ELSE 0 END) as available_count,
            ROUND(AVG(CASE WHEN available THEN 1.0 ELSE 0.0 END) * 100, 2) as availability_pct
        FROM daily_availability
    ''').fetchone()

    # Recent 7 days
    recent = conn.execute('''
        SELECT date, COUNT(DISTINCT symbol) as symbol_count
        FROM daily_availability
        WHERE date >= CURRENT_DATE - INTERVAL 7 DAYS
        GROUP BY date
        ORDER BY date DESC
    ''').fetchall()

    conn.close()

    # Print stats
    print('Overall Statistics:')
    print(f'  Date Range: {overall[0]} to {overall[1]}')
    print(f'  Total Dates: {overall[2]}')
    print(f'  Total Symbols: {overall[3]}')
    print(f'  Total Records: {overall[4]:,}')
    print(f'  Available: {overall[5]:,} ({overall[6]}%)')
    print()
    print('Recent 7 Days:')
    for date, count in recent:
        print(f'  {date}: {count} symbols')

    # Export for GitHub summary
    with open('stats.json', 'w') as f:
        json.dump({
            'earliest_date': str(overall[0]),
            'latest_date': str(overall[1]),
            'total_dates': overall[2],
            'total_symbols': overall[3],
            'total_records': overall[4],
            'available_count': overall[5],
            'availability_pct': overall[6]
        }, f)

except Exception as e:
    print(f'Error generating stats: {e}')
    sys.exit(1)
