#!/bin/bash
#
# Local workflow testing script
# Simulates GitHub Actions workflow steps for validation before deployment
#
# Usage:
#   ./test-workflow-locally.sh              # Daily update mode (yesterday)
#   ./test-workflow-locally.sh --backfill   # Backfill mode (requires dates)
#   ./test-workflow-locally.sh --backfill --start-date 2024-01-01 --end-date 2024-01-31
#

set -e  # Exit on error
set -u  # Exit on undefined variable

# =============================================================================
# Configuration
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$(pwd)}"
DB_PATH="${DB_PATH:-${HOME}/.cache/binance-futures/availability.duckdb}"
PYTHON_VERSION="${PYTHON_VERSION:-3.12}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# =============================================================================
# Helper Functions
# =============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

section_header() {
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}$1${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
}

check_command() {
    if ! command -v "$1" &> /dev/null; then
        log_error "$1 is not installed. Please install it first."
        return 1
    fi
}

# =============================================================================
# Parse Arguments
# =============================================================================

UPDATE_MODE="daily"
START_DATE=""
END_DATE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --backfill)
            UPDATE_MODE="backfill"
            shift
            ;;
        --start-date)
            START_DATE="$2"
            shift 2
            ;;
        --end-date)
            END_DATE="$2"
            shift 2
            ;;
        --help)
            cat << EOF
Usage: $0 [OPTIONS]

Options:
  --backfill              Run in backfill mode (requires --start-date and --end-date)
  --start-date YYYY-MM-DD Backfill start date
  --end-date YYYY-MM-DD   Backfill end date
  --help                  Show this help message

Examples:
  $0                      # Daily update (yesterday)
  $0 --backfill --start-date 2024-01-01 --end-date 2024-01-31
EOF
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Validate backfill arguments
if [[ "$UPDATE_MODE" == "backfill" ]]; then
    if [[ -z "$START_DATE" ]] || [[ -z "$END_DATE" ]]; then
        log_error "Backfill mode requires --start-date and --end-date"
        exit 1
    fi
fi

# =============================================================================
# Pre-flight Checks
# =============================================================================

section_header "Pre-flight Checks"

log_info "Checking required commands..."
check_command python3 || exit 1
check_command uv || exit 1
check_command duckdb || log_warning "duckdb CLI not found (optional)"

log_info "Python version: $(python3 --version)"
log_info "uv version: $(uv --version)"

log_info "Project root: $PROJECT_ROOT"
log_info "Database path: $DB_PATH"
log_info "Update mode: $UPDATE_MODE"

if [[ "$UPDATE_MODE" == "backfill" ]]; then
    log_info "Date range: $START_DATE to $END_DATE"
fi

log_success "Pre-flight checks passed"

# =============================================================================
# Step 1: Setup Environment
# =============================================================================

section_header "Step 1: Setup Environment"

log_info "Navigating to project root..."
cd "$PROJECT_ROOT"

log_info "Installing project dependencies..."
uv pip install --system -e ".[dev]" || {
    log_error "Failed to install dependencies"
    exit 1
}

log_success "Environment setup complete"

# =============================================================================
# Step 2: Check Existing Database
# =============================================================================

section_header "Step 2: Check Existing Database"

if [[ -f "$DB_PATH" ]]; then
    log_info "Database found: $(ls -lh "$DB_PATH" | awk '{print $5}')"

    log_info "Querying database stats..."
    uv run python -c "
import duckdb
conn = duckdb.connect('$DB_PATH', read_only=True)
result = conn.execute('''
    SELECT
        MIN(date) as earliest_date,
        MAX(date) as latest_date,
        COUNT(DISTINCT date) as total_dates,
        COUNT(DISTINCT symbol) as total_symbols
    FROM daily_availability
''').fetchone()
conn.close()
print(f'  Earliest date: {result[0]}')
print(f'  Latest date: {result[1]}')
print(f'  Total dates: {result[2]}')
print(f'  Total symbols: {result[3]}')
" || log_warning "Failed to query database (may be corrupt)"
else
    log_info "No existing database found (will create new one)"
fi

log_success "Database check complete"

# =============================================================================
# Step 3: Run Update
# =============================================================================

section_header "Step 3: Run Update"

if [[ "$UPDATE_MODE" == "daily" ]]; then
    log_info "Running daily update for yesterday's data..."

    uv run python -c "
import datetime
import logging
from binance_futures_availability.scheduler.daily_update import DailyUpdateScheduler
from binance_futures_availability.scheduler.notifications import setup_scheduler_logging

logger = setup_scheduler_logging(level=logging.INFO)
yesterday = datetime.date.today() - datetime.timedelta(days=1)

scheduler = DailyUpdateScheduler(db_path='$DB_PATH')
scheduler.run_manual_update(date=yesterday)

logger.info(f'Daily update completed for {yesterday}')
" || {
        log_error "Daily update failed"
        exit 1
    }

elif [[ "$UPDATE_MODE" == "backfill" ]]; then
    log_info "Running backfill from $START_DATE to $END_DATE..."

    CMD="uv run python scripts/operations/backfill.py"
    CMD="$CMD --start-date $START_DATE"
    CMD="$CMD --end-date $END_DATE"

    log_info "Executing: $CMD"
    $CMD || {
        log_error "Backfill failed"
        exit 1
    }
fi

log_success "Update complete"

# =============================================================================
# Step 4: Run Validation
# =============================================================================

section_header "Step 4: Run Validation"

log_info "Running database validation checks..."

uv run python scripts/operations/validate.py --verbose || {
    log_error "Validation failed"
    exit 1
}

log_success "Validation passed"

# =============================================================================
# Step 5: Generate Statistics
# =============================================================================

section_header "Step 5: Generate Statistics"

log_info "Generating database statistics..."

uv run python -c "
import duckdb
import json

conn = duckdb.connect('$DB_PATH', read_only=True)

# Overall stats
overall = conn.execute('''
    SELECT
        MIN(date) as earliest_date,
        MAX(date) as latest_date,
        COUNT(DISTINCT date) as total_dates,
        COUNT(DISTINCT symbol) as total_symbols,
        COUNT(*) as total_records,
        SUM(CASE WHEN available THEN 1 ELSE 0 END) as available_count,
        ROUND(AVG(CASE WHEN available THEN 1.0 ELSE 0.0 END) * 100, 2) as availability_pct
    FROM daily_availability
''').fetchone()

# Recent 7 days
recent = conn.execute('''
    SELECT date, COUNT(DISTINCT symbol) as symbol_count
    FROM daily_availability
    WHERE date >= CURRENT_DATE - INTERVAL 7 DAYS
    GROUP BY date
    ORDER BY date DESC
''').fetchall()

conn.close()

# Print stats
print('Overall Statistics:')
print(f'  Date Range: {overall[0]} to {overall[1]}')
print(f'  Total Dates: {overall[2]}')
print(f'  Total Symbols: {overall[3]}')
print(f'  Total Records: {overall[4]:,}')
print(f'  Available: {overall[5]:,} ({overall[6]}%)')
print()
print('Recent 7 Days:')
for date, count in recent:
    print(f'  {date}: {count} symbols')

# Save stats for later use
with open('/tmp/db-stats.json', 'w') as f:
    json.dump({
        'earliest_date': str(overall[0]),
        'latest_date': str(overall[1]),
        'total_dates': overall[2],
        'total_symbols': overall[3],
        'total_records': overall[4],
        'available_count': overall[5],
        'availability_pct': overall[6]
    }, f, indent=2)

print()
print('Stats saved to: /tmp/db-stats.json')
" || {
    log_error "Failed to generate statistics"
    exit 1
}

log_success "Statistics generated"

# =============================================================================
# Step 6: Run Tests
# =============================================================================

section_header "Step 6: Run Tests"

log_info "Running unit tests (excluding integration tests)..."

uv run pytest -m "not integration" --cov-report=term --cov-fail-under=80 || {
    log_error "Tests failed"
    exit 1
}

log_success "Tests passed"

# =============================================================================
# Step 7: Create Distribution Files (Simulation)
# =============================================================================

section_header "Step 7: Create Distribution Files"

log_info "Creating compressed database (simulating release artifact)..."

DIST_DIR="/tmp/binance-futures-dist"
mkdir -p "$DIST_DIR"

cp "$DB_PATH" "$DIST_DIR/availability.duckdb"
gzip -c "$DIST_DIR/availability.duckdb" > "$DIST_DIR/availability.duckdb.gz"

log_info "Distribution files created:"
ls -lh "$DIST_DIR"

log_success "Distribution files ready"

# =============================================================================
# Summary
# =============================================================================

section_header "Workflow Test Summary"

cat << EOF
${GREEN}✓${NC} All workflow steps completed successfully!

${BLUE}Database Information:${NC}
  Location: $DB_PATH
  Size: $(ls -lh "$DB_PATH" | awk '{print $5}')

${BLUE}Distribution Files:${NC}
  Directory: $DIST_DIR
  Files:
    - availability.duckdb (uncompressed)
    - availability.duckdb.gz (compressed)

${BLUE}Statistics:${NC}
$(cat /tmp/db-stats.json | python3 -m json.tool)

${BLUE}Next Steps:${NC}
  1. Review validation results above
  2. Check distribution files in $DIST_DIR
  3. Query database: duckdb $DB_PATH
  4. Deploy workflow to GitHub Actions when ready

${BLUE}GitHub Actions Deployment:${NC}
  cp $SCRIPT_DIR/prototype-workflow.yml .github/workflows/update-database.yml
  git add .github/workflows/update-database.yml
  git commit -m "feat: add GitHub Actions database automation"
  git push

EOF

log_success "Workflow test complete!"

# =============================================================================
# Optional: Interactive Query
# =============================================================================

if command -v duckdb &> /dev/null; then
    echo ""
    read -p "Open database in DuckDB CLI for inspection? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        duckdb "$DB_PATH"
    fi
fi
