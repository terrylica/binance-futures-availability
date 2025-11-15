#!/usr/bin/env python3
"""Run daily update for yesterday's data."""
import sys
import os
import datetime
from binance_futures_availability.scheduler.daily_update import DailyUpdateScheduler
from binance_futures_availability.scheduler.notifications import setup_scheduler_logging

db_path = os.environ.get('DB_PATH')
if not db_path:
    print('Error: DB_PATH environment variable not set')
    sys.exit(1)

logger = setup_scheduler_logging()
yesterday = datetime.date.today() - datetime.timedelta(days=1)

scheduler = DailyUpdateScheduler(db_path=db_path)
scheduler.run_manual_update(date=yesterday)

logger.info(f'Daily update completed for {yesterday}')
