# Automation Setup

Configure and manage automated daily updates using APScheduler.

See: [ADR-0004: APScheduler Automation](../decisions/0004-automation-apscheduler.md)

## Overview

**Schedule**: Daily at 2:00 AM UTC
**Target**: Probe yesterday's data (T+1 availability from S3 Vision)
**Technology**: APScheduler 3.10+ with SQLite job store
**SLO**: 95% of daily updates complete successfully

## Quick Start

### Start Scheduler Daemon

```bash
uv run python scripts/start_scheduler.py
```

**Output**:
```
Binance Futures Availability - APScheduler Daemon
Schedule: Daily at 2:00 AM UTC
Target: Probe yesterday's data (T+1 availability)
PID: 12345
Scheduler started successfully
Press Ctrl+C to stop
```

### Run in Background

**Option 1: nohup**

```bash
nohup uv run python scripts/start_scheduler.py > /dev/null 2>&1 &

# Check status
ps aux | grep start_scheduler
```

**Option 2: screen**

```bash
screen -S binance-scheduler
uv run python scripts/start_scheduler.py
# Press Ctrl+A, D to detach

# Reattach later
screen -r binance-scheduler
```

**Option 3: tmux**

```bash
tmux new -s scheduler
uv run python scripts/start_scheduler.py
# Press Ctrl+B, D to detach

# Reattach later
tmux attach -t scheduler
```

### Stop Scheduler

```bash
# Option 1: Use stop command
uv run python scripts/start_scheduler.py --stop

# Option 2: Find and kill process
ps aux | grep start_scheduler
kill <PID>

# Option 3: If running in foreground
# Press Ctrl+C
```

## Scheduler Configuration

### State Persistence

**Job store location**: `~/.cache/binance-futures/scheduler.db`

APScheduler persists job state to SQLite, allowing:
- Process restart recovery
- Job execution history
- Scheduled job state preservation

### Schedule Details

```python
from apscheduler.triggers.cron import CronTrigger

trigger = CronTrigger(
    hour=2,         # 2:00 AM
    minute=0,
    timezone='UTC'  # Always UTC, no DST ambiguity
)
```

**Why 2:00 AM UTC?**
- Binance Vision S3 uploads previous day's data during T+1 (next day)
- 2:00 AM provides buffer for S3 upload completion
- UTC avoids DST time shifts

### Execution Parameters

- **Job ID**: `daily_availability_update`
- **Max instances**: 1 (prevents overlapping executions)
- **Replace existing**: True (idempotent job registration)

## Monitoring

### Check Scheduler Status

```bash
# Check if scheduler is running
ps aux | grep start_scheduler

# Check PID file
cat ~/.cache/binance-futures/scheduler.pid
```

### View Logs

```bash
# Follow live logs
tail -f ~/.cache/binance-futures/scheduler.log

# View recent logs
tail -n 100 ~/.cache/binance-futures/scheduler.log

# Search for errors
grep ERROR ~/.cache/binance-futures/scheduler.log
```

**Log format**:
```
2025-11-12 02:00:00,123 | INFO | scheduler.daily_update | Starting daily update for 2025-11-11
2025-11-12 02:02:05,456 | INFO | scheduler.daily_update | Daily update completed: 708 symbols probed, 708 available
```

### Verify Daily Updates

```bash
# Check recent symbol counts
uv run binance-futures-availability query analytics summary --json | tail -n 10

# Or with Python
python -c "
from binance_futures_availability.validation import CompletenessValidator
v = CompletenessValidator()
summary = v.get_symbol_counts_summary(days=7)
for s in summary:
    print(f\"{s['date']}: {s['symbol_count']} symbols\")
v.close()
"
```

### Alerting on Failures

Monitor scheduler logs for errors:

```bash
#!/bin/bash
# check_scheduler.sh - Run via cron every hour

LOG_FILE="$HOME/.cache/binance-futures/scheduler.log"
ERROR_COUNT=$(grep -c "ERROR.*Daily update failed" "$LOG_FILE" | tail -n 1)

if [ "$ERROR_COUNT" -gt 0 ]; then
    echo "ALERT: $ERROR_COUNT daily update failures found"
    # Send email/Slack notification here
    exit 1
fi
```

## Manual Updates

### Run Manual Update for Specific Date

```bash
# CLI
uv run binance-futures-availability update manual --date 2024-01-15

# Python
python -c "
from binance_futures_availability.scheduler import DailyUpdateScheduler
scheduler = DailyUpdateScheduler()
scheduler.run_manual_update(date='2024-01-15')
"
```

### Run Manual Update for Yesterday

```bash
uv run binance-futures-availability update manual
```

## Error Handling

### Retry Policy

**ADR-0003**: Strict raise policy - no automatic retries

- Failed updates raise RuntimeError immediately
- APScheduler logs failure but continues
- **Next scheduled run will retry** (24 hours later)

### Manual Retry After Failure

If daily update fails:

```bash
# Check logs for failure date
grep "Daily update failed" ~/.cache/binance-futures/scheduler.log

# Manually retry
uv run binance-futures-availability update manual --date 2024-01-15

# Verify success
uv run python scripts/validate_database.py
```

## Production Deployment

### systemd Service (Linux)

Create service file: `/etc/systemd/system/binance-scheduler.service`

```ini
[Unit]
Description=Binance Futures Availability Scheduler
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/home/youruser/eon/binance-futures-availability
ExecStart=/home/youruser/.local/bin/uv run python scripts/start_scheduler.py
Restart=on-failure
RestartSec=60

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable binance-scheduler
sudo systemctl start binance-scheduler

# Check status
sudo systemctl status binance-scheduler

# View logs
sudo journalctl -u binance-scheduler -f
```

### launchd Service (macOS)

Create plist: `~/Library/LaunchAgents/com.binance.scheduler.plist`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.binance.scheduler</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/youruser/.local/bin/uv</string>
        <string>run</string>
        <string>python</string>
        <string>scripts/start_scheduler.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/youruser/eon/binance-futures-availability</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/binance-scheduler.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/binance-scheduler-error.log</string>
</dict>
</plist>
```

Load service:

```bash
launchctl load ~/Library/LaunchAgents/com.binance.scheduler.plist

# Check status
launchctl list | grep binance

# Unload
launchctl unload ~/Library/LaunchAgents/com.binance.scheduler.plist
```

## SLO Compliance

**Target**: 95% of daily updates complete successfully

### Measure Success Rate

```bash
#!/usr/bin/env python3
"""Calculate daily update success rate."""

from binance_futures_availability.validation import ContinuityValidator
from datetime import date, timedelta

v = ContinuityValidator()

# Check last 30 days
end_date = date.today() - timedelta(days=1)
start_date = end_date - timedelta(days=30)

missing_dates = v.check_continuity(start_date=start_date, end_date=end_date)

total_days = (end_date - start_date).days + 1
success_days = total_days - len(missing_dates)
success_rate = (success_days / total_days) * 100

print(f"Success rate (last 30 days): {success_rate:.1f}%")
print(f"SLO target: 95%")
print(f"SLO met: {'YES' if success_rate >= 95 else 'NO'}")

v.close()
```

## See Also

- [Backup & Restore](BACKUP_RESTORE.md): Database backup procedures
- [Monitoring](MONITORING.md): Health checks and alerting
- [ADR-0004](../decisions/0004-automation-apscheduler.md): Automation architecture decision
