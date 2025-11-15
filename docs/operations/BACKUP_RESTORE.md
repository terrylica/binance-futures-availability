# Backup & Restore

Database backup and recovery procedures.

## Database File Location

**Primary database**: `~/.cache/binance-futures/availability.duckdb`
**Size**: 50-150 MB (compressed columnar storage)
**Format**: DuckDB single-file database

## Backup Strategies

### Strategy 1: Simple File Copy

**Frequency**: Daily (recommended)
**Method**: Copy database file

```bash
#!/bin/bash
# backup_daily.sh

SOURCE="$HOME/.cache/binance-futures/availability.duckdb"
BACKUP_DIR="$HOME/backups/binance-futures"
DATE=$(date +%Y%m%d)

mkdir -p "$BACKUP_DIR"
cp "$SOURCE" "$BACKUP_DIR/availability-$DATE.duckdb"

# Keep last 7 days
find "$BACKUP_DIR" -name "availability-*.duckdb" -mtime +7 -delete

echo "Backup completed: availability-$DATE.duckdb"
```

Schedule with cron:

```cron
# Daily backup at 3:00 AM (after scheduler update at 2:00 AM)
0 3 * * * /path/to/backup_daily.sh
```

### Strategy 2: Export to CSV (Human-Readable)

**Use case**: Archive, external analysis, compliance

```python
from binance_futures_availability.database import AvailabilityDatabase

db = AvailabilityDatabase()

# Export full database to CSV
db.conn.execute("""
    COPY (SELECT * FROM daily_availability ORDER BY date, symbol)
    TO 'backup_availability.csv'
    (HEADER, DELIMITER ',')
""")

db.close()
```

**File size**: ~500-1000 MB (uncompressed CSV)

### Strategy 3: Export to Parquet (Efficient Archive)

**Use case**: Long-term storage, data lake integration

```python
from binance_futures_availability.database import AvailabilityDatabase

db = AvailabilityDatabase()

# Export to Parquet (smaller than CSV)
db.conn.execute("""
    COPY (SELECT * FROM daily_availability ORDER BY date, symbol)
    TO 'backup_availability.parquet'
    (FORMAT PARQUET, COMPRESSION ZSTD)
""")

db.close()
```

**File size**: ~30-50 MB (compressed Parquet)

### Strategy 4: Incremental Backup

**Use case**: Minimize backup size

```python
from binance_futures_availability.database import AvailabilityDatabase
from datetime import date, timedelta

db = AvailabilityDatabase()

# Backup only last 30 days (incremental)
cutoff_date = date.today() - timedelta(days=30)

db.conn.execute(f"""
    COPY (
        SELECT * FROM daily_availability
        WHERE date >= '{cutoff_date}'
        ORDER BY date, symbol
    ) TO 'backup_incremental.parquet'
    (FORMAT PARQUET, COMPRESSION ZSTD)
""")

db.close()
```

## Backup Verification

### Verify Backup Integrity

```bash
#!/bin/bash
# verify_backup.sh

BACKUP_FILE="$1"

# Check file exists and is not empty
if [ ! -s "$BACKUP_FILE" ]; then
    echo "ERROR: Backup file missing or empty"
    exit 1
fi

# Check DuckDB can open file
python3 -c "
import duckdb
conn = duckdb.connect('$BACKUP_FILE', read_only=True)
count = conn.execute('SELECT COUNT(*) FROM daily_availability').fetchone()[0]
print(f'Backup verified: {count:,} records')
conn.close()
"
```

### Compare Backup vs Current Database

```python
import duckdb

# Open both databases
current = duckdb.connect('~/.cache/binance-futures/availability.duckdb', read_only=True)
backup = duckdb.connect('backup_availability.duckdb', read_only=True)

# Compare record counts
current_count = current.execute('SELECT COUNT(*) FROM daily_availability').fetchone()[0]
backup_count = backup.execute('SELECT COUNT(*) FROM daily_availability').fetchone()[0]

print(f"Current DB: {current_count:,} records")
print(f"Backup DB: {backup_count:,} records")
print(f"Difference: {current_count - backup_count:,} records")

current.close()
backup.close()
```

## Restore Procedures

### Restore from DuckDB Backup

**Scenario**: Database corrupted, restore from backup

```bash
#!/bin/bash
# restore_backup.sh

BACKUP_FILE="$1"
TARGET="$HOME/.cache/binance-futures/availability.duckdb"

# Backup current database (if exists)
if [ -f "$TARGET" ]; then
    mv "$TARGET" "$TARGET.corrupted-$(date +%Y%m%d%H%M%S)"
fi

# Restore from backup
cp "$BACKUP_FILE" "$TARGET"

echo "Restore completed from $BACKUP_FILE"
```

### Restore from CSV

```python
from binance_futures_availability.database import AvailabilityDatabase, create_schema
import duckdb

# Create new database
db = AvailabilityDatabase()

# Import from CSV
db.conn.execute("""
    COPY daily_availability
    FROM 'backup_availability.csv'
    (HEADER, DELIMITER ',')
""")

db.close()

print("Restore from CSV completed")
```

### Restore from Parquet

```python
from binance_futures_availability.database import AvailabilityDatabase

db = AvailabilityDatabase()

# Import from Parquet
db.conn.execute("""
    INSERT INTO daily_availability
    SELECT * FROM read_parquet('backup_availability.parquet')
""")

db.close()

print("Restore from Parquet completed")
```

## Disaster Recovery

### Full Recovery Procedure

1. **Identify backup file**:

   ```bash
   ls -lh ~/backups/binance-futures/
   ```

2. **Verify backup integrity**:

   ```bash
   ./verify_backup.sh ~/backups/binance-futures/availability-20251111.duckdb
   ```

3. **Stop scheduler** (if running):

   ```bash
   uv run python scripts/start_scheduler.py --stop
   ```

4. **Restore database**:

   ```bash
   ./restore_backup.sh ~/backups/binance-futures/availability-20251111.duckdb
   ```

5. **Validate restored database**:

   ```bash
   uv run python scripts/validate_database.py
   ```

6. **Backfill missing dates** (if backup is old):

   ```bash
   # Backfill from backup date to yesterday (~25 minutes with AWS CLI)
   uv run python scripts/scripts/operations/backfill.py --start-date 2025-11-11
   ```

7. **Restart scheduler**:
   ```bash
   uv run python scripts/start_scheduler.py
   ```

### Rebuild from Scratch

**Scenario**: All backups lost, rebuild database

```bash
# Clear everything
rm -rf ~/.cache/binance-futures/

# Run full backfill (~25 minutes with AWS CLI)
uv run python scripts/scripts/operations/backfill.py

# Validate
uv run python scripts/validate_database.py

# Start scheduler
uv run python scripts/start_scheduler.py
```

## Off-Site Backup

### Cloud Storage (S3/GCS)

**Recommended**: Daily sync to cloud storage

```bash
#!/bin/bash
# backup_to_s3.sh

SOURCE="$HOME/.cache/binance-futures/availability.duckdb"
DATE=$(date +%Y%m%d)
S3_BUCKET="s3://your-backup-bucket/binance-futures"

# Upload to S3
aws s3 cp "$SOURCE" "$S3_BUCKET/availability-$DATE.duckdb"

# Verify upload
aws s3 ls "$S3_BUCKET/availability-$DATE.duckdb"

echo "S3 backup completed"
```

### Restore from S3

```bash
aws s3 cp s3://your-backup-bucket/binance-futures/availability-20251111.duckdb \
    ~/.cache/binance-futures/availability.duckdb
```

## Retention Policy

### Recommended Retention Schedule

- **Daily backups**: Keep last 7 days
- **Weekly backups**: Keep last 4 weeks (every Sunday)
- **Monthly backups**: Keep last 12 months (first of month)
- **Yearly backups**: Keep indefinitely

**Implementation**:

```bash
#!/bin/bash
# retention_policy.sh

BACKUP_DIR="$HOME/backups/binance-futures"
DATE=$(date +%Y%m%d)
DAY_OF_WEEK=$(date +%u)  # 1=Monday, 7=Sunday
DAY_OF_MONTH=$(date +%d)

# Daily backup
cp ~/.cache/binance-futures/availability.duckdb \
    "$BACKUP_DIR/daily/availability-$DATE.duckdb"

# Weekly backup (Sunday)
if [ "$DAY_OF_WEEK" -eq 7 ]; then
    cp ~/.cache/binance-futures/availability.duckdb \
        "$BACKUP_DIR/weekly/availability-$DATE.duckdb"
fi

# Monthly backup (1st of month)
if [ "$DAY_OF_MONTH" -eq 01 ]; then
    cp ~/.cache/binance-futures/availability.duckdb \
        "$BACKUP_DIR/monthly/availability-$DATE.duckdb"
fi

# Cleanup old backups
find "$BACKUP_DIR/daily" -name "*.duckdb" -mtime +7 -delete
find "$BACKUP_DIR/weekly" -name "*.duckdb" -mtime +28 -delete
find "$BACKUP_DIR/monthly" -name "*.duckdb" -mtime +365 -delete
```

## Backup Size Estimation

**Full database**: 50-150 MB (DuckDB compressed)
**CSV export**: 500-1000 MB (uncompressed)
**Parquet export**: 30-50 MB (compressed)

**Annual growth**: ~50 MB/year

## See Also

- [Automation](AUTOMATION.md): Scheduler setup
- [Monitoring](MONITORING.md): Health checks
- [ADR-0002](../decisions/0002-storage-technology-duckdb.md): DuckDB choice
