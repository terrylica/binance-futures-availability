# Monitoring & Health Checks

Monitor database health, scheduler performance, and data quality.

## Health Check Commands

### Quick Health Check

```bash
#!/bin/bash
# health_check.sh - Run all health checks

echo "=== Binance Futures Availability - Health Check ==="

# 1. Check scheduler is running
if pgrep -f "start_scheduler.py" > /dev/null; then
    echo "✓ Scheduler: Running"
else
    echo "✗ Scheduler: NOT running"
fi

# 2. Check database exists
DB_PATH="$HOME/.cache/binance-futures/availability.duckdb"
if [ -f "$DB_PATH" ]; then
    DB_SIZE=$(du -h "$DB_PATH" | cut -f1)
    echo "✓ Database: Exists ($DB_SIZE)"
else
    echo "✗ Database: NOT found"
fi

# 3. Check recent update
LAST_UPDATE=$(python3 -c "
from binance_futures_availability.database import AvailabilityDatabase
db = AvailabilityDatabase()
result = db.query('SELECT MAX(date) FROM daily_availability')
print(result[0][0] if result[0][0] else 'None')
db.close()
")
echo "✓ Last update: $LAST_UPDATE"

# 4. Run validation
echo ""
echo "Running validation checks..."
uv run python scripts/validate_database.py
```

### Database Metrics

```python
#!/usr/bin/env python3
"""Database health metrics."""

from binance_futures_availability.database import AvailabilityDatabase
from datetime import date, timedelta
import os

db = AvailabilityDatabase()

# Total records
total_records = db.query("SELECT COUNT(*) FROM daily_availability")[0][0]

# Date range
date_range = db.query(
    "SELECT MIN(date), MAX(date) FROM daily_availability"
)[0]

# Database file size
db_size_mb = os.path.getsize(db.db_path) / 1024 / 1024

# Recent symbol count
yesterday = date.today() - timedelta(days=1)
recent_count = db.query(
    "SELECT COUNT(*) FROM daily_availability WHERE date = ? AND available = true",
    [yesterday]
)[0][0]

print(f"Total records: {total_records:,}")
print(f"Date range: {date_range[0]} to {date_range[1]}")
print(f"Database size: {db_size_mb:.1f} MB")
print(f"Yesterday's symbols: {recent_count}")

db.close()
```

## SLO Monitoring

### Availability SLO: 95% Daily Update Success Rate

```python
#!/usr/bin/env python3
"""Monitor daily update success rate (SLO: 95%)."""

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

print(f"Daily Update Success Rate (Last 30 Days)")
print(f"==========================================")
print(f"Success rate: {success_rate:.1f}%")
print(f"SLO target: 95%")
print(f"Status: {'PASS ✓' if success_rate >= 95 else 'FAIL ✗'}")

if missing_dates:
    print(f"\nMissing dates: {len(missing_dates)}")
    for d in missing_dates[:5]:
        print(f"  - {d}")

v.close()
```

### Correctness SLO: >95% Match with API

```python
#!/usr/bin/env python3
"""Monitor database correctness vs Binance API (SLO: >95%)."""

from binance_futures_availability.validation import CrossCheckValidator

v = CrossCheckValidator()

try:
    result = v.cross_check_current_date()

    print(f"Database vs API Cross-Check")
    print(f"============================")
    print(f"Match percentage: {result['match_percentage']}%")
    print(f"SLO target: >95%")
    print(f"Status: {'PASS ✓' if result['slo_met'] else 'FAIL ✗'}")

    print(f"\nDetails:")
    print(f"  DB symbols: {result['db_symbol_count']}")
    print(f"  API symbols: {result['api_symbol_count']}")
    print(f"  Matching: {result['match_count']}")

    if result['only_in_db']:
        print(f"\n  Only in DB (possible delistings): {len(result['only_in_db'])}")
    if result['only_in_api']:
        print(f"  Only in API (possible new listings): {len(result['only_in_api'])}")

except Exception as e:
    print(f"Cross-check failed: {e}")

v.close()
```

### Observability SLO: All Failures Logged

Check error logging completeness:

```bash
# Count logged errors in last 24 hours
journalctl -u binance-scheduler --since "24 hours ago" | grep ERROR | wc -l

# Or check log file directly
grep ERROR ~/.cache/binance-futures/scheduler.log | tail -n 10
```

### Maintainability SLO: 80%+ Test Coverage

```bash
# Run tests with coverage
pytest --cov --cov-report=term-missing

# Check coverage percentage
pytest --cov --cov-fail-under=80
```

## Performance Monitoring

### Query Performance

```python
#!/usr/bin/env python3
"""Monitor query performance against SLO targets."""

import time
from binance_futures_availability.queries import SnapshotQueries, TimelineQueries

# Snapshot query performance (SLO: <1ms)
start = time.time()
with SnapshotQueries() as q:
    results = q.get_available_symbols_on_date('2024-01-15')
snapshot_time_ms = (time.time() - start) * 1000

print(f"Query Performance")
print(f"=================")
print(f"Snapshot query: {snapshot_time_ms:.2f}ms (SLO: <1ms)")
print(f"  Status: {'PASS ✓' if snapshot_time_ms < 1 else 'WARN ⚠' if snapshot_time_ms < 10 else 'FAIL ✗'}")

# Timeline query performance (SLO: <10ms)
start = time.time()
with TimelineQueries() as q:
    timeline = q.get_symbol_availability_timeline('BTCUSDT')
timeline_time_ms = (time.time() - start) * 1000

print(f"Timeline query: {timeline_time_ms:.2f}ms (SLO: <10ms)")
print(f"  Status: {'PASS ✓' if timeline_time_ms < 10 else 'WARN ⚠' if timeline_time_ms < 50 else 'FAIL ✗'}")
```

### Daily Update Duration

Monitor how long daily updates take:

```bash
# Extract update duration from logs
grep "Daily update completed" ~/.cache/binance-futures/scheduler.log | tail -n 7
```

## Alerting

### Email Alerts on Failure

```bash
#!/bin/bash
# alert_on_failure.sh - Run via cron every hour

LOG_FILE="$HOME/.cache/binance-futures/scheduler.log"
LAST_HOUR=$(date -d '1 hour ago' +"%Y-%m-%d %H")

# Check for errors in last hour
ERROR_COUNT=$(grep "$LAST_HOUR" "$LOG_FILE" | grep -c "ERROR.*Daily update failed")

if [ "$ERROR_COUNT" -gt 0 ]; then
    # Send email alert
    echo "Daily update failed. Check logs: $LOG_FILE" | \
        mail -s "ALERT: Binance Futures Scheduler Failure" admin@example.com

    exit 1
fi
```

### Slack Alerts

```python
#!/usr/bin/env python3
"""Send Slack alert on validation failure."""

import requests
from binance_futures_availability.validation import ContinuityValidator

SLACK_WEBHOOK_URL = "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

v = ContinuityValidator()
missing_dates = v.check_continuity()
v.close()

if missing_dates:
    message = {
        "text": f"⚠️ Binance Futures Availability Alert",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Continuity Check Failed*\n{len(missing_dates)} missing dates detected"
                }
            }
        ]
    }

    requests.post(SLACK_WEBHOOK_URL, json=message)
```

## Prometheus Metrics (Optional)

Export metrics for Prometheus monitoring:

```python
#!/usr/bin/env python3
"""Prometheus metrics exporter."""

from binance_futures_availability.database import AvailabilityDatabase
from prometheus_client import Gauge, start_http_server
import time

# Define metrics
db_total_records = Gauge('binance_futures_db_total_records', 'Total records in database')
db_size_mb = Gauge('binance_futures_db_size_mb', 'Database file size in MB')
recent_symbol_count = Gauge('binance_futures_recent_symbol_count', 'Yesterday\'s symbol count')

def collect_metrics():
    """Collect and update metrics."""
    db = AvailabilityDatabase()

    # Total records
    total = db.query("SELECT COUNT(*) FROM daily_availability")[0][0]
    db_total_records.set(total)

    # Database size
    import os
    size_mb = os.path.getsize(db.db_path) / 1024 / 1024
    db_size_mb.set(size_mb)

    # Recent symbol count
    from datetime import date, timedelta
    yesterday = date.today() - timedelta(days=1)
    count = db.query(
        "SELECT COUNT(*) FROM daily_availability WHERE date = ? AND available = true",
        [yesterday]
    )[0][0]
    recent_symbol_count.set(count)

    db.close()

if __name__ == "__main__":
    # Start Prometheus HTTP server
    start_http_server(8000)

    print("Prometheus metrics server started on :8000")

    # Collect metrics every 60 seconds
    while True:
        collect_metrics()
        time.sleep(60)
```

**Prometheus scrape config**:

```yaml
scrape_configs:
  - job_name: "binance-futures"
    static_configs:
      - targets: ["localhost:8000"]
```

## Grafana Dashboard

Example metrics to visualize:

1. **Total Records Over Time**
2. **Daily Symbol Count Trend**
3. **Database Size Growth**
4. **Query Performance (Snapshot/Timeline)**
5. **Daily Update Success Rate**
6. **API Match Percentage**

## Automated Monitoring Script

Comprehensive monitoring script to run via cron:

```bash
#!/bin/bash
# monitor.sh - Run every hour

# 1. Check scheduler is running
if ! pgrep -f "start_scheduler.py" > /dev/null; then
    echo "ALERT: Scheduler not running" | mail -s "Scheduler Down" admin@example.com
    exit 1
fi

# 2. Run validation
uv run python scripts/validate_database.py > /tmp/validation.log 2>&1
if [ $? -ne 0 ]; then
    echo "ALERT: Validation failed" | mail -s "Validation Failure" -a /tmp/validation.log admin@example.com
    exit 1
fi

# 3. Check disk space
DB_DIR="$HOME/.cache/binance-futures"
DISK_USAGE=$(df -h "$DB_DIR" | tail -1 | awk '{print $5}' | sed 's/%//')
if [ "$DISK_USAGE" -gt 90 ]; then
    echo "ALERT: Disk usage at ${DISK_USAGE}%" | mail -s "Disk Space Warning" admin@example.com
fi

echo "Monitoring check passed"
```

**Cron schedule**:

```cron
# Run monitoring every hour
0 * * * * /path/to/monitor.sh

# Run SLO checks daily at 9 AM
0 9 * * * /path/to/slo_check.sh
```

## See Also

- [Automation](AUTOMATION.md): Scheduler setup
- [Backup & Restore](BACKUP_RESTORE.md): Backup procedures
- [Troubleshooting](../guides/TROUBLESHOOTING.md): Common issues
