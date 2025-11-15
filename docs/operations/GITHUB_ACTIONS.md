# GitHub Actions Database Automation Setup Guide

## Overview

This workflow automates daily updates to the Binance futures availability DuckDB database using GitHub Actions. The database is published as a GitHub Release asset for easy distribution.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ GitHub Actions Workflow (Runs daily at 3:00 AM UTC)        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. SETUP: Install Python, uv, AWS CLI, dependencies       │
│  2. RESTORE: Download latest database from GitHub Release  │
│  3. UPDATE: Run daily update or backfill                   │
│  4. VALIDATE: Run pytest + validation checks               │
│  5. PUBLISH: Create/update GitHub Release with database    │
│  6. NOTIFY: Post summary to Actions UI                     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
         ┌──────────────────────────────────┐
         │  GitHub Release: "latest"        │
         ├──────────────────────────────────┤
         │  - availability.duckdb           │
         │  - availability.duckdb.gz        │
         │  - Release notes with stats      │
         └──────────────────────────────────┘
```

## Required Setup

### 1. Repository Permissions

The workflow requires the following permissions in your repository:

**Settings → Actions → General → Workflow permissions:**
- ✅ Read and write permissions
- ✅ Allow GitHub Actions to create and approve pull requests

**Required for:**
- Creating/updating releases
- Uploading database assets
- Writing to Actions summary

### 2. Secrets Configuration

**No additional secrets required!**

The workflow uses the built-in `GITHUB_TOKEN` which is automatically provided by GitHub Actions.

### 3. File Placement

Copy the workflow file to your repository:

```bash
# From your repository root
mkdir -p .github/workflows
cp /tmp/github-actions-database-automation/prototype-workflow.yml \
   .github/workflows/update-database.yml
```

### 4. Initial Release Setup

The workflow will automatically create the "latest" release on first run, but you can pre-create it:

```bash
# Optional: Create initial release
gh release create latest \
  --title "Latest Database Snapshot" \
  --notes "Initial database release" \
  --latest
```

## Workflow Triggers

### 1. Scheduled (Automatic)

**When**: Daily at 3:00 AM UTC
**What**: Updates yesterday's data (T+1 availability from S3 Vision)
**Mode**: Daily incremental update

```yaml
schedule:
  - cron: '0 3 * * *'  # Daily at 3:00 AM UTC
```

### 2. Manual Trigger (workflow_dispatch)

**When**: On-demand via GitHub UI or CLI
**What**: Either daily update OR custom backfill
**Options**:
- `update_mode`: "daily" or "backfill"
- `start_date`: Backfill start (YYYY-MM-DD)
- `end_date`: Backfill end (YYYY-MM-DD)

**Example: Manual daily update**
```bash
gh workflow run update-database.yml \
  --field update_mode=daily
```

**Example: Backfill specific date range**
```bash
gh workflow run update-database.yml \
  --field update_mode=backfill \
  --field start_date=2024-01-01 \
  --field end_date=2024-01-31
```

## Workflow Steps Explained

### Step 1: Setup

Installs required tools:
- **Python 3.12** via `actions/setup-python@v5`
- **uv package manager** via `astral-sh/setup-uv@v5`
- **AWS CLI** for bulk S3 operations (backfill mode)
- **Project dependencies** via `uv pip install -e ".[dev]"`

### Step 2: Restore Database

Downloads existing database from latest GitHub Release:

```bash
gh release download latest \
  --pattern "availability.duckdb" \
  --output "$DB_PATH"
```

- If database exists: Downloads and logs stats (date range, record count)
- If no database: Starts fresh (suitable for first run)

### Step 3: Update

**Daily Mode** (default for scheduled runs):
```python
scheduler = DailyUpdateScheduler(db_path='$DB_PATH')
scheduler.run_manual_update(date=yesterday)
```

**Backfill Mode** (manual trigger with custom dates):
```bash
uv run python scripts/operations/backfill.py \
  --start-date 2024-01-01 \
  --end-date 2024-01-31
```

### Step 4: Validate

Runs comprehensive validation checks:

```bash
uv run python scripts/operations/validate.py --verbose
```

**Validation layers:**
1. **Continuity**: Check for missing dates in sequence
2. **Completeness**: Verify symbol counts (≥700 symbols per date)
3. **Cross-check**: Compare with Binance API (>95% match SLO)

**Failure handling:**
- If validation fails, workflow exits with error code
- Database is NOT published if validation fails
- Error details logged to Actions summary

### Step 5: Test

Runs pytest test suite (excluding integration tests):

```bash
uv run pytest -m "not integration" --cov-fail-under=80
```

**Coverage requirement:** ≥80% test coverage (enforced)

### Step 6: Publish

Creates/updates GitHub Release with database assets:

1. **Compress database**: `gzip -c availability.duckdb > availability.duckdb.gz`
2. **Generate release notes**: Stats, validation status, usage examples
3. **Upload assets**: Both compressed and uncompressed database files
4. **Tag**: "latest" (always overwrites previous release)

### Step 7: Notify

Posts summary to GitHub Actions UI:

- Validation status (✅/❌)
- Database statistics (latest date, record count, availability %)
- Download instructions
- Links to release

## Database Publishing

### Release Structure

**Tag**: `latest` (always latest snapshot, overwrites previous)
**Assets**:
- `availability.duckdb` - Uncompressed (50-150 MB)
- `availability.duckdb.gz` - Compressed (recommended, ~10-30 MB)

**Release Notes Include**:
- Update timestamp
- Database statistics
- Validation status
- Usage examples

### Downloading Database

**Via curl/wget:**
```bash
# Compressed (recommended)
wget https://github.com/YOUR-USERNAME/binance-futures-availability/releases/download/latest/availability.duckdb.gz
gunzip availability.duckdb.gz

# Uncompressed
wget https://github.com/YOUR-USERNAME/binance-futures-availability/releases/download/latest/availability.duckdb
```

**Via gh CLI:**
```bash
gh release download latest --pattern "availability.duckdb.gz"
gunzip availability.duckdb.gz
```

**Python automation:**
```python
import urllib.request
import gzip

url = "https://github.com/YOUR-USERNAME/binance-futures-availability/releases/download/latest/availability.duckdb.gz"
urllib.request.urlretrieve(url, "availability.duckdb.gz")

with gzip.open("availability.duckdb.gz", "rb") as f_in:
    with open("availability.duckdb", "wb") as f_out:
        f_out.write(f_in.read())
```

## Cost Analysis

### GitHub Actions Free Tier

**Free for public repositories:**
- ✅ Unlimited minutes
- ✅ Unlimited storage
- ✅ No cost

**Free for private repositories:**
- ✅ 2,000 minutes/month (Linux runners)
- ✅ 500 MB storage
- ⚠️ Database size: 50-150 MB (fits in free tier)

### Estimated Usage

**Daily run:**
- Duration: ~5-10 minutes
- Storage: ~150 MB (database + compressed)
- Minutes/month: ~300 minutes (10 min/day × 30 days)

**Backfill run** (one-time or rare):
- Duration: ~25-30 minutes (full historical backfill)
- Storage: Same 150 MB
- One-time cost

**Conclusion**: Well within free tier limits for public or private repos.

## Monitoring and Troubleshooting

### View Workflow Status

**GitHub UI:**
1. Go to Actions tab
2. Click "Update Binance Futures Availability Database"
3. View run history and logs

**CLI:**
```bash
# List recent runs
gh run list --workflow=update-database.yml

# View specific run
gh run view <run-id>

# Download logs
gh run download <run-id>
```

### Common Issues

#### 1. Validation Fails

**Symptom**: Workflow fails at validation step
**Cause**: Database inconsistencies (missing dates, low symbol counts, API mismatch)
**Solution**:
```bash
# Re-run with backfill mode to fill gaps
gh workflow run update-database.yml \
  --field update_mode=backfill \
  --field start_date=2024-01-01 \
  --field end_date=2024-01-31
```

#### 2. Release Upload Fails

**Symptom**: "Resource not accessible by integration" error
**Cause**: Insufficient repository permissions
**Solution**:
1. Go to Settings → Actions → General
2. Enable "Read and write permissions"
3. Re-run workflow

#### 3. Database Download Fails

**Symptom**: "No existing database found" on first run
**Cause**: No initial release exists
**Solution**: Normal! Workflow will create fresh database and publish first release

#### 4. AWS CLI Errors

**Symptom**: `aws: command not found` or S3 access errors
**Cause**: AWS CLI installation failure or S3 permissions
**Solution**:
- AWS CLI is installed in workflow (check logs)
- S3 Vision is public (no credentials needed)
- Check network connectivity

### Debug Mode

Enable verbose logging by editing workflow:

```yaml
- name: Run daily update
  env:
    LOG_LEVEL: DEBUG  # Add this
  run: |
    uv run python -c "..."
```

## Customization Options

### Change Schedule

Edit cron expression in workflow:

```yaml
schedule:
  - cron: '0 3 * * *'  # Current: 3:00 AM UTC daily

# Examples:
# - cron: '0 */6 * * *'  # Every 6 hours
# - cron: '0 0 * * 0'     # Weekly on Sunday
# - cron: '0 2 1 * *'     # Monthly on 1st
```

### Change Python Version

Edit in workflow:

```yaml
env:
  PYTHON_VERSION: '3.12'  # Change to 3.11, 3.13, etc.
```

### Add Notifications

**Slack notification** (requires webhook secret):

```yaml
- name: Notify Slack
  if: always()
  uses: 8398a7/action-slack@v3
  with:
    status: ${{ job.status }}
    webhook_url: ${{ secrets.SLACK_WEBHOOK }}
```

**Email notification** (built-in):

Settings → Notifications → Actions → Configure notifications

### Change Release Strategy

**Current**: Single "latest" tag (always overwrites)

**Alternative: Dated tags** (keeps history):

```yaml
- name: Create/Update release
  uses: softprops/action-gh-release@v2
  with:
    tag_name: v$(date +%Y%m%d)  # Example: v20241215
    name: Database Snapshot $(date +%Y-%m-%d)
```

## Security Considerations

### 1. Token Permissions

The workflow uses `GITHUB_TOKEN` with minimal required permissions:
- ✅ `contents: write` - For creating releases
- ✅ `pull-requests: write` - For PR comments (optional)

**No additional secrets needed** - S3 Vision is public, no AWS credentials required.

### 2. Dependency Security

**Supply chain security:**
- Uses official GitHub Actions (`actions/checkout@v4`, etc.)
- Uses official uv installer (`astral-sh/setup-uv@v5`)
- Pins action versions (e.g., `@v4`, not `@latest`)

**Python dependencies:**
- Locked in `pyproject.toml`
- No untrusted sources

### 3. Network Access

**Outbound connections:**
- S3 Vision API (data.binance.vision) - Public, no auth
- Binance API (api.binance.com) - Public, validation only
- GitHub API - Authenticated with `GITHUB_TOKEN`

**No inbound connections** - Workflow is fully isolated.

### 4. Database Integrity

**Validation before publish:**
- ✅ Continuity checks (no missing dates)
- ✅ Completeness checks (≥700 symbols per date)
- ✅ Cross-check with Binance API (>95% match)
- ✅ Test suite passes (≥80% coverage)

**Only valid databases are published** - Failures prevent release.

## Migration from Local Scheduler

If you're currently using APScheduler locally, migrate as follows:

### 1. Stop Local Scheduler

```bash
# If using systemd
sudo systemctl stop binance-futures-scheduler
sudo systemctl disable binance-futures-scheduler

# If using screen/tmux
screen -r scheduler  # Attach
Ctrl+C  # Stop
exit
```

### 2. Upload Current Database

```bash
# Compress local database
gzip -c ~/.cache/binance-futures/availability.duckdb > availability.duckdb.gz

# Create initial release
gh release create latest \
  --title "Latest Database Snapshot" \
  --notes "Migrated from local scheduler" \
  availability.duckdb.gz
```

### 3. Enable GitHub Actions Workflow

```bash
# Copy workflow file
cp /tmp/github-actions-database-automation/prototype-workflow.yml \
   .github/workflows/update-database.yml

# Commit and push
git add .github/workflows/update-database.yml
git commit -m "feat: migrate to GitHub Actions for database updates"
git push
```

### 4. Test Manual Run

```bash
# Trigger workflow manually
gh workflow run update-database.yml --field update_mode=daily

# Monitor run
gh run watch
```

### 5. Verify Automation

Wait 24 hours and check:
```bash
# Check recent runs
gh run list --workflow=update-database.yml --limit 5

# Download latest database
gh release download latest --pattern "availability.duckdb.gz"
gunzip availability.duckdb.gz
```

## Performance Characteristics

### Daily Update (Scheduled)

- **Duration**: 5-10 minutes
- **Network**: ~708 HTTP HEAD requests (parallel)
- **Database writes**: ~708 INSERT/UPSERT operations
- **Storage**: Incremental (~100 KB per day)

### Backfill (Manual)

- **Duration**: 25-30 minutes (full history: 2019-09-25 to present)
- **Network**: AWS CLI bulk listing (~327 symbols × 1 call each)
- **Database writes**: Bulk INSERT (~500,000 records)
- **Storage**: Full database creation (50-150 MB)

### Validation

- **Duration**: 1-2 minutes
- **Checks**: 3 validation layers (continuity, completeness, cross-check)
- **Network**: 1 API call (Binance exchangeInfo for cross-check)

## Advanced Usage

### Parallel Multiple Repositories

Run workflow in multiple repositories for different data:

**Repo 1**: `binance-futures-availability` (USDT perpetuals)
**Repo 2**: `binance-spot-availability` (Spot pairs)
**Repo 3**: `binance-coin-futures-availability` (COIN-M futures)

Each repository publishes to its own "latest" release.

### Database Versioning

**Current**: Single "latest" tag (simple, always up-to-date)

**Alternative**: Semantic versioning with retention policy:

```yaml
# Keep last 30 daily snapshots + monthly archives
tag_name: v$(date +%Y%m%d-%H%M)
```

Then clean old releases periodically:
```bash
# Keep only last 30 releases
gh release list --limit 1000 | tail -n +31 | awk '{print $1}' | xargs -I {} gh release delete {}
```

### Multi-Region Distribution

Use GitHub Releases as primary source, then sync to other storage:

```yaml
- name: Sync to S3 (optional)
  run: |
    aws s3 cp availability.duckdb.gz s3://my-bucket/availability.duckdb.gz
  env:
    AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
    AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
```

## Testing Locally

### Option 1: Use `act` (GitHub Actions emulator)

```bash
# Install act
brew install act  # macOS
# or
curl https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash

# Test workflow locally
act workflow_dispatch \
  --secret GITHUB_TOKEN=$YOUR_GITHUB_TOKEN \
  --input update_mode=daily
```

**Limitations:**
- Large runner images (~10+ GB)
- Some Actions features not supported
- Network access may differ

### Option 2: Dry-run Script

Simulate workflow steps without running Actions:

```bash
# Create test script
cat > test_workflow.sh << 'EOF'
#!/bin/bash
set -e

echo "=== SETUP ==="
uv pip install -e ".[dev]"

echo "=== UPDATE ==="
uv run python -c "
from binance_futures_availability.scheduler.daily_update import DailyUpdateScheduler
import datetime
scheduler = DailyUpdateScheduler()
scheduler.run_manual_update(date=datetime.date.today() - datetime.timedelta(days=1))
"

echo "=== VALIDATE ==="
uv run python scripts/operations/validate.py

echo "=== TEST ==="
uv run pytest -m "not integration"

echo "=== SUCCESS ==="
EOF

chmod +x test_workflow.sh
./test_workflow.sh
```

## Support and Troubleshooting

### Logs and Debugging

**View workflow logs:**
```bash
gh run view --log
```

**Download artifacts** (if workflow saves any):
```bash
gh run download <run-id>
```

**Check database integrity:**
```python
import duckdb
conn = duckdb.connect('availability.duckdb', read_only=True)
print(conn.execute("PRAGMA integrity_check").fetchall())
```

### Getting Help

1. **Check workflow logs** - Most issues have clear error messages
2. **Review validation output** - Shows specific data quality issues
3. **Test locally** - Use dry-run script to isolate issue
4. **GitHub Discussions** - Ask community for help
5. **File Issue** - Report bugs with workflow logs attached

## Best Practices

1. ✅ **Monitor first 3 runs** - Ensure workflow executes correctly
2. ✅ **Set up notifications** - Get alerted on failures
3. ✅ **Review validation reports** - Check data quality regularly
4. ✅ **Test backfill mode** - Before using on large date ranges
5. ✅ **Keep workflow file in version control** - Track changes
6. ✅ **Use protected branches** - Require reviews for workflow changes
7. ✅ **Enable dependabot** - Keep action versions updated
8. ✅ **Document customizations** - If you modify workflow

## Next Steps

After setup:

1. ✅ **Test manual run**: `gh workflow run update-database.yml --field update_mode=daily`
2. ✅ **Wait for scheduled run**: Check at 3:00 AM UTC next day
3. ✅ **Verify release**: Download and query database
4. ✅ **Set up monitoring**: Configure notifications
5. ✅ **Document for team**: Share download instructions
