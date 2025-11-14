#!/bin/bash
# Quick system health check

echo "🔍 SYSTEM HEALTH CHECK"
echo "===================="
echo ""

# Database exists
if [ -f ~/.cache/binance-futures/availability.duckdb ]; then
    SIZE=$(ls -lh ~/.cache/binance-futures/availability.duckdb | awk '{print $5}')
    echo "✅ Database exists ($SIZE)"
else
    echo "❌ Database not found"
    exit 1
fi

# Record count
source .venv/bin/activate 2>/dev/null
RECORDS=$(python -c "import duckdb; print(duckdb.connect('~/.cache/binance-futures/availability.duckdb').execute('SELECT COUNT(*) FROM daily_availability').fetchone()[0])" 2>/dev/null)
echo "✅ Total records: $RECORDS"

# Date range
DATE_INFO=$(python -c "import duckdb; r=duckdb.connect('~/.cache/binance-futures/availability.duckdb').execute('SELECT MIN(date), MAX(date), COUNT(DISTINCT date) FROM daily_availability').fetchone(); print(f'{r[0]} to {r[1]} ({r[2]} days)')" 2>/dev/null)
echo "✅ Date coverage: $DATE_INFO"

# Latest availability
LATEST=$(python -c "import duckdb; r=duckdb.connect('~/.cache/binance-futures/availability.duckdb').execute('SELECT SUM(CASE WHEN available THEN 1 ELSE 0 END), COUNT(*) FROM daily_availability WHERE date=(SELECT MAX(date) FROM daily_availability)').fetchone(); print(f'{r[0]}/{r[1]} symbols ({r[0]*100//r[1]}%)')" 2>/dev/null)
echo "✅ Latest date: $LATEST available"

echo ""
echo "System operational ✅"
