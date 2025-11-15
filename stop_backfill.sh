#!/bin/bash
# Stop volume backfill gracefully

cd ~/eon/binance-futures-availability

if [ ! -f volume_backfill.pid ]; then
    echo "❌ No backfill PID file found"
    exit 1
fi

PID=$(cat volume_backfill.pid)

if ps -p $PID > /dev/null 2>&1; then
    echo "🛑 Stopping backfill (PID: $PID)..."
    kill $PID
    sleep 2
    
    if ps -p $PID > /dev/null 2>&1; then
        echo "⚠️  Process still running, force killing..."
        kill -9 $PID
    fi
    
    echo "✅ Backfill stopped"
    echo "📊 Check final status: tail -50 volume_backfill_overnight.log"
else
    echo "ℹ️  Process already stopped (PID $PID not running)"
fi

rm -f volume_backfill.pid
