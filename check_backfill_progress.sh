#!/bin/bash
# Check volume backfill progress

cd ~/eon/binance-futures-availability

echo "=== Volume Backfill Status ==="
echo ""

# Check if PID file exists
if [ ! -f volume_backfill.pid ]; then
    echo "❌ No backfill running (no PID file found)"
    echo ""
    echo "Start with: ./start_overnight_backfill.sh"
    exit 1
fi

PID=$(cat volume_backfill.pid)

# Check if process is still running
if ps -p $PID > /dev/null 2>&1; then
    echo "✅ Backfill is RUNNING (PID: $PID)"
    
    # Show runtime
    START_TIME=$(ps -p $PID -o lstart=)
    echo "📅 Started: $START_TIME"
    
    # Show CPU/Memory usage
    echo ""
    echo "📊 Resource Usage:"
    ps -p $PID -o %cpu,%mem,rss,vsz
    
    # Show last 20 lines of log
    echo ""
    echo "📝 Recent Progress (last 20 lines):"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    tail -20 volume_backfill_overnight.log
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "💡 Watch live: tail -f volume_backfill_overnight.log"
else
    echo "⚠️  Process NOT running (PID $PID not found)"
    echo ""
    echo "Check log for completion status:"
    echo "  tail -50 volume_backfill_overnight.log"
fi
