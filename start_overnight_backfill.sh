#!/bin/bash
# Start volume backfill in background - safe to close terminal/Claude
# Output saved to: volume_backfill_overnight.log
# Prevents Mac from sleeping during execution

cd ~/eon/binance-futures-availability

# Run with caffeinate (prevents Mac sleep) + nohup (survives terminal close)
# -u flag for Python: unbuffered output (shows progress immediately)
nohup caffeinate -s uv run python -u scripts/operations/backfill_volume.py --workers 10 > volume_backfill_overnight.log 2>&1 &

# Save PID for later
echo $! > volume_backfill.pid

echo "✅ Volume backfill started in background!"
echo "📝 PID: $(cat volume_backfill.pid)"
echo "📊 Monitor progress: tail -f volume_backfill_overnight.log"
echo "🛑 Stop if needed: kill $(cat volume_backfill.pid)"
echo ""
echo "Safe to close this terminal and Claude Code CLI now."
echo "Estimated completion: ~7.3 hours from now"
