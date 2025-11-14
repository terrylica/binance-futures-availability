# ADR-0004: Automation - APScheduler

**Status**: Accepted

**Date**: 2025-11-12

**Context**:

We need automated daily updates to probe yesterday's data from Binance Vision S3 (T+1 availability). The automation must:

- **Run daily**: Execute at 2:00 AM UTC when yesterday's data is stable
- **Persist state**: Survive process restarts and system reboots
- **Handle failures**: Retry failed updates automatically
- **Observability**: Log all executions with success/failure status

Three automation approaches were evaluated:

1. **APScheduler**: Python-based task scheduler with SQLite persistence
   - Pure Python, same runtime as application
   - SQLite job store for state persistence
   - Built-in failure handling and logging
   - No external dependencies

2. **Cron + systemd**: Unix system scheduler
   - Requires shell script wrapper
   - Separate configuration files (crontab, .service)
   - Less portable (Unix-only)
   - No built-in retry logic

3. **Celery + Redis**: Distributed task queue
   - Requires Redis server installation
   - Overkill for single-machine local database
   - Complex deployment

**Decision**:

We will use **APScheduler 3.10+** with SQLite job store for automated daily updates.

**Implementation pattern**:

```python
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.triggers.cron import CronTrigger
import logging

logger = logging.getLogger(__name__)

# Job store configuration
jobstores = {
    'default': SQLAlchemyJobStore(url='sqlite:///~/.cache/binance-futures/scheduler.db')
}

# Initialize scheduler
scheduler = BackgroundScheduler(
    jobstores=jobstores,
    timezone='UTC'
)

def daily_update_job():
    """Probe yesterday's data (T+1 availability)."""
    yesterday = datetime.now(timezone.utc).date() - timedelta(days=1)

    logger.info(f"Starting daily update for {yesterday}")

    try:
        db = AvailabilityDatabase()
        prober = BatchProber()

        # Probe all 708 symbols
        results = prober.probe_all_symbols(date=yesterday)

        # Insert results
        db.insert_batch(results)

        logger.info(f"Daily update completed: {len(results)} symbols probed")

    except Exception as e:
        logger.error(f"Daily update failed for {yesterday}: {e}")
        raise  # APScheduler will log failure and retry next cycle

# Add job
scheduler.add_job(
    func=daily_update_job,
    trigger=CronTrigger(hour=2, minute=0, timezone='UTC'),
    id='daily_availability_update',
    name='Probe yesterday\'s futures availability',
    replace_existing=True,
    max_instances=1
)

# Start scheduler
scheduler.start()
```

**Daemon script** (`scripts/start_scheduler.py`):

```python
#!/usr/bin/env python3
"""Start APScheduler daemon for daily updates."""

import signal
import sys
import time
from pathlib import Path

from binance_futures_availability.scheduler.daily_update import scheduler

def signal_handler(signum, frame):
    """Graceful shutdown on SIGINT/SIGTERM."""
    print("\nShutting down scheduler...")
    scheduler.shutdown(wait=True)
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Write PID file
pid_file = Path.home() / ".cache" / "binance-futures" / "scheduler.pid"
pid_file.parent.mkdir(parents=True, exist_ok=True)
pid_file.write_text(str(os.getpid()))

print("APScheduler daemon started (PID: {})".format(os.getpid()))
print("Daily updates scheduled for 2:00 AM UTC")
print("Press Ctrl+C to stop")

# Keep process alive
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    pass
```

**Consequences**:

**Positive**:

- **Pure Python**: No external scheduler installation required
- **State persistence**: SQLite job store survives process restarts
- **Built-in retry**: Failed jobs automatically retry next cycle (aligns with ADR-0003)
- **Timezone-aware**: Explicit UTC scheduling eliminates DST ambiguity
- **Max instances**: `max_instances=1` prevents overlapping executions
- **Structured logging**: Integrates with Python logging framework
- **Cross-platform**: Works on macOS, Linux, Windows

**Negative**:

- **Process dependency**: Requires daemon process to stay running
- **No system integration**: Not managed by systemd/launchd (user must start manually)

**Operational usage**:

```bash
# Start daemon
uv run python scripts/start_scheduler.py &

# Check status
ps aux | grep start_scheduler

# View logs
tail -f ~/.cache/binance-futures/scheduler.log

# Stop daemon
kill $(cat ~/.cache/binance-futures/scheduler.pid)
```

**SLO alignment**:

- **Availability SLO**: "95% of daily updates complete successfully" - scheduler retries failures
- **Observability SLO**: "All failures logged with full context" - structured logging enabled

**Related Decisions**:

- ADR-0002: DuckDB storage (single-writer compatibility)
- ADR-0003: Strict error policy (scheduler handles retries)
