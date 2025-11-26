# Binance Futures Availability Database

**Version**: v1.3.0
**Created**: 2025-11-12
**Updated**: 2025-11-25
**Status**: Production-ready (GitHub Actions automation enabled, infrastructure v1.3.0)
**Pattern**: Follows `ValidationStorage` pattern from gapless-crypto-data
**Purpose**: Track daily availability of ALL USDT perpetual futures from Binance Vision (2019-09-25 to present)

**Note**: Symbol count is dynamic - we discover and probe all perpetual instruments available on each date. Current count: ~327 active symbols, but historical dates may have different counts as instruments are listed/delisted over time.

## Quick Links

- **Architecture**: [`docs/architecture/ARCHITECTURE.md`](docs/architecture/ARCHITECTURE.md) - System diagrams and component overview
- **SSoT Plan**: [`docs/development/plan/v1.0.0/plan.yaml`](docs/development/plan/v1.0.0/plan.yaml)
- **Schema**: [`docs/schema/availability-database.schema.json`](docs/schema/availability-database.schema.json)
- **MADRs**: [`docs/architecture/decisions/`](docs/architecture/decisions/)
- **Guides**: [`docs/guides/`](docs/guides/)

## Architecture Decisions

All architectural decisions documented as MADRs in `docs/architecture/decisions/`:

### [0001: Schema Design - Daily Table Pattern](docs/architecture/decisions/0001-schema-design-daily-table.md)

**Decision**: Use daily availability table (not range table) for simple append-only updates
**Rationale**: Idempotent inserts, point-in-time accuracy, future-proof for suspensions/relistings

### [0002: Storage Technology - DuckDB](docs/architecture/decisions/0002-storage-technology-duckdb.md)

**Decision**: DuckDB for single-file columnar storage
**Rationale**: 50-150MB database, sub-second analytical queries, no server overhead

### [0003: Error Handling - Strict Raise Policy](docs/architecture/decisions/0003-error-handling-strict-policy.md)

**Decision**: Raise+propagate all errors immediately, no retries/fallbacks
**Rationale**: Fail fast, workflow retries next scheduled cycle, explicit error visibility

### [0004: Automation - APScheduler](docs/architecture/decisions/0004-automation-apscheduler.md)

**Status**: ⚠️ SUPERSEDED by ADR-0009 (GitHub Actions automation)

### [0005: AWS CLI for Bulk Operations](docs/architecture/decisions/0005-aws-cli-bulk-operations.md)

**Decision**: Hybrid approach - AWS CLI for historical backfill, HTTP HEAD for daily updates
**Rationale**: AWS CLI is 7.2x faster for bulk operations (25 min vs 3 hours), HEAD requests simpler for incremental updates

### [0006: Volume Metrics Collection](docs/architecture/decisions/0006-volume-metrics-collection.md)

**Decision**: Collect file_size_bytes and last_modified from both collection methods
**Rationale**: Zero marginal cost, enables volume analytics and audit trails, minimal storage overhead (25 MB)

### [0007: Trading Volume Metrics](docs/architecture/decisions/0007-trading-volume-metrics.md)

**Status**: ✅ ACCEPTED (Implemented 2025-11-24)
**Decision**: Extend daily_availability table with 9 OHLCV columns from Binance Vision 1d klines
**Rationale**: Portfolio universe selection, survivorship bias elimination, volume-based symbol ranking
**Implementation**: Schema drift fix (no migration), integrated into backfill.py with --collect-volume flag

### [0008: Workspace Organization](docs/architecture/decisions/0008-workspace-organization.md)

**Decision**: Cleanup legacy code, fix documentation drift, consolidate redundant guides
**Rationale**: 30+ broken script references, 70% doc overlap between CLAUDE.md and README.md

### [0009: GitHub Actions Automation](docs/architecture/decisions/0009-github-actions-automation.md)

**Decision**: Replace APScheduler daemon with GitHub Actions for daily updates and distribution
**Rationale**: Zero infrastructure overhead, 99.9% SLA, built-in observability, automated GitHub Releases publishing
**Supersedes**: ADR-0004 (APScheduler)

### [0010: Dynamic Symbol Discovery](docs/architecture/decisions/0010-dynamic-symbol-discovery.md)

**Decision**: Daily S3 XML API enumeration to auto-update symbols.json with git auto-commit
**Rationale**: Detect new symbol listings within 24 hours, eliminate manual symbol.json maintenance, never remove delisted symbols

### [0011: 20-Day Lookback Reliability](docs/architecture/decisions/0011-20day-lookback-reliability.md)

**Decision**: Probe last 20 days on each daily update (not just yesterday)
**Rationale**: Auto-repair gaps from previous failures, handle S3 publishing delays, update changed volume metrics, validate data continuity

### [0012: Auto-Backfill New Symbols](docs/architecture/decisions/0012-auto-backfill-new-symbols.md)

**Decision**: Conditional auto-backfill workflow step that detects symbol gaps and backfills historical data for new symbols only
**Rationale**: Zero manual intervention when Binance lists new symbols, complete historical coverage within 24 hours of discovery, zero overhead when no new symbols (99% of runs)

### [0013: Volume Rankings Timeseries](docs/architecture/decisions/0013-volume-rankings-timeseries.md)

**Decision**: Daily Parquet snapshots of symbol rankings with 7d/30d aggregations
**Rationale**: Track market dynamics, identify trending symbols, enable time-series analysis without database queries

### [0014: Easy Query Access](docs/architecture/decisions/0014-easy-query-access.md)

**Decision**: Provide both CLI and Python API for common queries (snapshot, timeline, analytics)
**Rationale**: Lower barrier to entry, support diverse use cases (scripts, notebooks, production), consistent query interface

### [0015: Skill Extraction](docs/architecture/decisions/0015-skill-extraction.md)

**Decision**: Extract validated workflows into reusable skills (multi-agent investigation, DuckDB remote queries, documentation improvement)
**Rationale**: Codify proven patterns, enable reuse across projects, reduce repeated discovery work

### [0017: Documentation Structure Migration](docs/architecture/decisions/0017-documentation-structure-migration.md)

**Decision**: Migrate ADRs to `docs/architecture/decisions/`, plans to `docs/development/plan/` with Google Design Doc format
**Rationale**: Industry-standard paths enable tooling integration (adr-tools, Log4brains, Backstage), explicit ADR↔plan linkage via `adr-id`, narrative markdown improves readability

### [0018: Technology Stack Upgrade 2025](docs/architecture/decisions/0018-technology-stack-upgrade-2025.md)

**Decision**: Upgrade dependencies to latest stable versions with upper-bound constraints (DuckDB 1.4, urllib3 2.5, pyarrow 22, pytest 8.4, GitHub Actions v6)
**Rationale**: 9-15% performance improvement, 60% storage reduction, zero breaking changes, security patches applied
**Impact**: Dependencies secured with semantic versioning constraints, pytest 8.4 constrained by pytest-playwright

### [0019: Performance Optimization Strategy](docs/architecture/decisions/0019-performance-optimization-strategy.md)

**Decision**: Implement 4 proven optimizations: HTTP connection pooling, DNS cache warming, column compression, materialized views
**Rationale**: 9-15% faster daily updates (1.48s → 1.35s), 60% storage reduction (50-150MB → 20-50MB), zero complexity trade-offs
**Impact**: HTTP pooling (7%), DNS caching (3%), compression (60% storage), materialized views (50x faster analytics)

### [0020: CI/CD Maturity Improvements](docs/architecture/decisions/0020-cicd-maturity-improvements.md)

**Decision**: Add critical CI/CD gates: Dependabot, ruff linting, test gates, coverage thresholds (80%)
**Rationale**: CI/CD maturity 7.1 → 7.8 (+10%), 10:1 ROI for P0/P1 quick wins, zero infrastructure overhead
**Impact**: Weekly automated dependency updates, fail-fast linting, enforced test coverage

### [0021: Observability Phase 0 Foundation](docs/architecture/decisions/0021-observability-phase0-foundation.md)

**Status**: ⚠️ DEFERRED to future sprint (8 hours effort)
**Decision**: Establish lightweight observability foundation: schema drift detection, correlation IDs, data catalog
**Rationale**: 3x faster debugging (>30min → <10min), 400-500% ROI, zero infrastructure overhead
**Impact**: Deferred to Q1 2026 for deeper integration

### [0022: Pushover Workflow Notifications](docs/architecture/decisions/0022-pushover-workflow-notifications.md)

**Status**: ✅ ACCEPTED (Implemented 2025-11-22)
**Decision**: Add Pushover notifications to GitHub Actions workflow for instant status visibility
**Rationale**: 30 hours/year saved, instant failure detection, no manual GitHub UI monitoring
**Implementation**: Doppler SecretOps for PUSHOVER_APP_TOKEN/PUSHOVER_USER_KEY, custom curl notification

### [0023: Doppler-Native Secrets Consolidation](docs/architecture/decisions/0023-doppler-secrets-consolidation.md)

**Status**: ✅ ACCEPTED (Implemented 2025-11-25)
**Decision**: Consolidate all automation secrets to Doppler, remove 1Password from automation workflows
**Rationale**: Single source of truth, Doppler GitHub App auto-sync, centralized audit trail
**Implementation**: GitHub tokens migrated to Doppler `notifications/prd`, local access via service token

### [0024: ClickHouse E2E Test Removal](docs/architecture/decisions/0024-clickhouse-cleanup.md)

**Status**: ✅ ACCEPTED (Implemented 2025-11-25)
**Decision**: Remove all ClickHouse-related E2E tests and artifacts (tests/e2e/, ADR-0016, [e2e] deps)
**Rationale**: ClickHouse tests were exploratory, not connected to production DuckDB pipeline

### [0025: System Architecture Documentation](docs/architecture/decisions/0025-system-architecture-documentation.md)

**Status**: ✅ ACCEPTED (Implemented 2025-11-25)
**Decision**: Create comprehensive architecture documentation with ASCII diagrams
**Implementation**: `docs/architecture/ARCHITECTURE.md` with data flow, runtime, component, and deployment diagrams

### [0026: Documentation Rectification](docs/architecture/decisions/0026-documentation-rectification.md)

**Status**: ✅ ACCEPTED (Implemented 2025-11-25)
**Decision**: Rectify 47 documentation issues across 6 severity levels
**Implementation**: Fixed critical issues (broken class references, badges, platform syntax), removed stale ADR-0016 references, synchronized documentation with codebase

## Core Principles

### Error Handling

**Data Collection** (ADR-0003 - Strict Raise Policy):

- **Policy**: Raise and propagate all errors immediately
- **No retries**: Network failures raise immediately, workflow retries next scheduled cycle
- **No fallbacks**: No default values or silent handling
- **No silent failures**: All errors logged with full context

**Validation Findings** (ADR-0003 - Transparency-First, Updated 2025-11-24):

- **Philosophy**: Full transparency over binary pass/fail
- **Never fail**: Validation warnings are informational only (always exit 0)
- **Publish always**: Database published regardless of validation state
- **Human review**: Trust human judgment via Pushover → GitHub Release notes
- **Interpretation guide**: Release notes explain common warning causes (S3 delays, listing/delisting)

### Dependencies

**OSS libraries only**: DuckDB, urllib3, AWS CLI
**Avoid custom implementations**: Use proven libraries, not custom code
**Hybrid tooling**: Right tool for each job (AWS CLI for bulk, HEAD requests for incremental)
**Automation**: GitHub Actions (zero infrastructure overhead, 99.9% SLA)

### SLOs (Service Level Objectives)

Focus on 4 dimensions (explicitly **not** speed/performance/security):

**Availability**:

- Target: 95% of daily updates complete successfully
- Measurement: Monitor GitHub Actions workflow logs for completion rate

**Correctness**:

- Target: >95% match with Binance exchangeInfo API for current date
- Measurement: Daily validation cross-check

**Observability**:

- Target: All failures logged with full context (symbol, date, HTTP status, error message)
- Measurement: Structured logs with timestamp, level, component, error details

**Maintainability**:

- Target: 80%+ test coverage, all public functions documented
- Measurement: pytest --cov, docstring coverage check

## Database Schema

**SSoT**: See [`docs/schema/availability-database.schema.json`](docs/schema/availability-database.schema.json)

**Summary**:

- **Table**: `daily_availability` with PRIMARY KEY (date, symbol)
- **Volume Metrics** (ADR-0006): `file_size_bytes`, `last_modified` enable trend analysis
- **Indexes**: Optimized for snapshot (~1ms) and timeline (~10ms) queries
- **Storage**: `~/.cache/binance-futures/availability.duckdb` (50-150 MB compressed)

**See README.md for schema details and query examples**

## Data Collection

### Source

**Binance Vision S3**: `https://data.binance.vision/data/futures/um/daily/klines/`
**URL Pattern**: `{base}/{symbol}/1m/{symbol}-1m-{YYYY-MM-DD}.zip`

### Hybrid Collection Strategy (ADR-0005)

**Backfill**: AWS CLI S3 listing (~1.1 min for full history, 327 symbols)
**Daily Updates**: HTTP HEAD requests (~1.5 sec, 150 workers, GitHub Actions 3AM UTC)
**Details**: See [ADR-0005](docs/architecture/decisions/0005-aws-cli-bulk-operations.md) and [worker benchmark](docs/benchmarks/worker-count-benchmark-2025-11-15.md)

### Symbol Discovery

**Dynamic Discovery** (ADR-0010): S3 XML API enumeration (~327 symbols, daily 3AM UTC)
**Auto-Update**: symbols.json committed when changes detected
**Details**: See [ADR-0010](docs/architecture/decisions/0010-dynamic-symbol-discovery.md)

**Backfill Behavior**:

- **New symbols**: Probed going forward from discovery date
- **Historical backfill**: User triggers manually via workflow_dispatch
- **Delisted symbols**: Never removed, continue probing forever (ADR-0010 decision)
- **Failure handling**: Discovery failure fails workflow (strict consistency per ADR-0003)

## Automation

### Primary: GitHub Actions (ADR-0009) - **PRODUCTION-READY**

**Technology**: GitHub Actions with GitHub Releases distribution
**Status**: ✅ Deployed and operational (as of 2025-11-15)
**Frequency**: Daily at 3:00 AM UTC (automated via cron schedule)
**Job**: Update yesterday's data (S3 Vision has T+1 availability)
**Distribution**: Automated publishing to GitHub Releases (gzip compressed)
**Cost**: $0/month (public repos: unlimited Actions minutes + storage)
**SLA**: 99.9% (GitHub Actions platform guarantee)

**Workflow**: `.github/workflows/update-database.yml`
**First Run**: Manual backfill required to create initial database (see Quick Start)
**Monitoring**: See [MONITORING.md](docs/operations/MONITORING.md)

**Error Handling**: Strict raise policy (ADR-0003), workflow retries next cycle on failure

### Pushover Notifications (ADR-0022) - **NEW**

**Technology**: Pushover API with Doppler SecretOps integration
**Status**: ✅ Implemented (as of 2025-11-22)
**Trigger**: All workflow statuses (success/failure/cancelled)
**Delivery**: Instant notifications to phone/desktop (< 5 seconds)

**Notification Content**:

- **Success**: Database stats (latest_date, records, available/unavailable counts), validation status, volume rankings status, run URL
- **Failure**: Error context, validation status, trigger type, logs URL
- **Cancelled**: Cancellation notice, trigger type, run URL

**Setup Required** (one-time):

1. Add `DOPPLER_TOKEN` to GitHub repository secrets:
   - Navigate: https://github.com/terrylica/binance-futures-availability/settings/secrets/actions
   - Create Doppler service token: https://dashboard.doppler.com/workplace/*/projects/notifications/configs/prd/access
   - Add secret: `DOPPLER_TOKEN` = `<service_token>`

2. Verify Doppler secrets exist:
   - `PUSHOVER_API_TOKEN` (from https://pushover.net/apps)
   - `PUSHOVER_USER_KEY` (from Pushover dashboard)

**Impact**:

- Eliminates manual GitHub UI workflow monitoring (30 hours/year saved)
- Instant failure detection → faster incident response
- Consistent UX between local monitoring script and CI workflow

**References**: ADR-0022, `docs/development/plan/0022-pushover-workflow-notifications/plan.md`

## Testing

### Coverage Requirements

**Target**: 80%+ test coverage (enforced by pytest-cov)
**Unit tests**: Mock S3 responses, test database operations
**Integration tests**: Hit live S3 Vision API (marked with `@pytest.mark.integration`)

### Running Tests

```bash
# Unit tests only (fast, no network)
pytest -m "not integration"

# All tests including integration (slow, requires network)
pytest

# With coverage report
pytest --cov=src/binance_futures_availability --cov-report=html
```

## Key Dependencies

### Required

- **duckdb>=1.4.0,<2.0.0**: Columnar database engine (ADR-0018)
- **urllib3>=2.5.0,<3.0.0**: HTTP client for S3 HEAD requests
- **pyarrow>=22.0.0,<23.0.0**: Parquet support for volume rankings

### Development

- **pytest>=8.4.0**: Testing framework
- **pytest-cov>=5.0.0**: Coverage reporting
- **pytest-mock>=3.14.0**: Mocking for unit tests
- **ruff>=0.14.5**: Linting and formatting (ADR-0018)

## Quick Start

### Installation

```bash
# Clone or navigate to project
cd ~/eon/binance-futures-availability

# Install package in development mode
uv pip install -e .

# Install development dependencies
uv pip install -e ".[dev]"
```

### Run Historical Backfill

```bash
# Backfill from 2019-09-25 (first UM-futures) to yesterday
uv run python scripts/operations/backfill.py

# Estimated time: ~25 minutes (AWS CLI bulk listing)
# Database size after: 50-150 MB
```

### Production: GitHub Actions Automation (ADR-0009) ✅

**Status**: Production-ready (automated daily updates at 3:00 AM UTC)

**Complete setup instructions**: See [README.md Quick Start](README.md#quick-start)

**Key Points**:

- First-time setup: Manual backfill via `gh workflow run` (creates initial database)
- Automated execution: Daily at 3:00 AM UTC (zero manual intervention)
- Distribution: GitHub Releases with gzip compression
- Monitoring: `docs/operations/MONITORING.md`

### Query Database

**Complete examples**: See [docs/guides/QUERY_EXAMPLES.md](docs/guides/QUERY_EXAMPLES.md)

**Quick reference**:

```bash
# CLI queries
uv run binance-futures-availability query snapshot 2024-01-15
uv run binance-futures-availability query timeline BTCUSDT

# Python API
from binance_futures_availability.queries import SnapshotQueries
```

**Volume metrics queries**: See ADR-0006 and QUERY_EXAMPLES.md

### Validate Database

```bash
# Run all validation checks
uv run python scripts/validate_database.py

# Checks:
# - Date continuity (no missing dates)
# - Symbol count per date (should be 100-700)
# - Cross-check with Binance exchangeInfo API (>95% match)
```

## Related Projects

### gapless-crypto-data

Spot OHLCV data collection with ValidationStorage pattern (this project follows same pattern)

### vision-futures-explorer

Initial futures discovery exploration (source of probe functions)

**Location**: `gapless-crypto-data/scratch/vision-futures-explorer/`
**Files copied**:

- `historical_probe.py` → `src/binance_futures_availability/probing/s3_vision.py`
- `futures_discovery.py` → `src/binance_futures_availability/probing/symbol_discovery.py`

## Reusable Skills

Project-specific skills extracted from validated workflows (ADR-0015):

### [`multi-agent-parallel-investigation`](skills/multi-agent-parallel-investigation/SKILL.md)

Decompose complex questions into 4-6 parallel investigations with different perspectives, synthesize into phased decision framework. Use when facing architecture decisions with multiple unknowns in crypto/trading data platforms.

### [`duckdb-remote-parquet-query`](skills/duckdb-remote-parquet-query/SKILL.md)

Query remote Parquet files via HTTP without downloading using DuckDB httpfs. Leverage column pruning, row filtering, and range requests for efficient bandwidth usage. Use for crypto/trading data distribution and analytics.

### [`documentation-improvement-workflow`](skills/documentation-improvement-workflow/SKILL.md)

Systematically improve documentation quality from 7/10 → 9/10 using assessment checklists and transformation patterns. Use when documentation exists but lacks Quick Start, clear prerequisites, or working examples. Optimized for crypto/trading data projects.

## SSoT Documentation

All specification documents follow SSoT principles:

### Implementation Plan

**File**: `docs/development/plan/v1.0.0/plan.yaml`
**Format**: YAML with OpenAPI-style structure
**Version**: Semantic versioning (currently 1.0.0)
**Content**: Phases, deliverables, SLOs, dependencies, risks, success criteria

### Schema Specification

**File**: `docs/schema/availability-database.schema.json`
**Format**: JSON Schema Draft 7
**Content**: Table definitions, indexes, data types, constraints, SLOs

### Query Patterns

**File**: `docs/schema/query-patterns.schema.json`
**Format**: JSON Schema Draft 7
**Content**: Common query patterns, performance targets, example code

## Project Structure

```
binance-futures-availability/
├── CLAUDE.md                      # This file (project memory)
├── README.md                      # User-facing documentation
├── pyproject.toml                 # Package configuration
│
├── docs/
│   ├── architecture/
│   │   ├── decisions/             # MADR decision records (25 ADRs)
│   │   └── ARCHITECTURE.md        # System architecture diagrams
│   ├── development/
│   │   └── plan/                  # Implementation plans (Google Design Doc format)
│   ├── schema/                    # JSON Schema specifications
│   ├── guides/                    # User guides
│   └── operations/                # Operations documentation
│
├── src/
│   └── binance_futures_availability/
│       ├── database/              # DuckDB operations
│       ├── probing/               # S3 Vision probing
│       ├── queries/               # Query helpers
│       ├── validation/            # Data validation
│       └── cli/                   # CLI interface
│
├── tests/                         # pytest test suite
├── scripts/                       # Operational scripts
└── .cache/                        # Runtime data (database, logs)
```

## Common Operations

**See**: [README.md](README.md) for database status checks, validation, and query examples

## Troubleshooting

**See**: [TROUBLESHOOTING.md](docs/guides/TROUBLESHOOTING.md) for common issues (database not found, S3 probe failures, validation errors, workflow debugging)

## Development Workflow

### Make Changes

```bash
# Edit source files
vim src/binance_futures_availability/database/availability_db.py

# Run tests
pytest tests/test_database/test_availability_db.py

# Check coverage
pytest --cov --cov-report=html
open htmlcov/index.html
```

### Run Linting

```bash
# Format code
ruff format src/ tests/

# Check linting
ruff check src/ tests/

# Fix auto-fixable issues
ruff check --fix src/ tests/
```

### Update Documentation

When making changes:

1. Update relevant MADR if architecture changes
2. Update SSoT plan if phases/SLOs change
3. Update JSON Schema if database schema changes
4. Update CLAUDE.md if core principles change

## Support & References

### Binance Vision Documentation

- **Data Repository**: https://data.binance.vision/
- **GitHub**: https://github.com/binance/binance-public-data
- **API Docs**: https://binance-docs.github.io/apidocs/futures/en/

### DuckDB Documentation

- **Official Docs**: https://duckdb.org/docs/
- **Python API**: https://duckdb.org/docs/api/python/overview
- **Performance**: https://duckdb.org/why_duckdb

## Version History

### v1.3.0 (2025-11-25)

- Trading volume metrics (ADR-0007): 9 OHLCV columns from Binance Vision 1d klines
- Pushover notifications (ADR-0022): Instant workflow status alerts
- Doppler secrets consolidation (ADR-0023): Centralized secret management
- ClickHouse cleanup (ADR-0024): Removed exploratory E2E tests
- System architecture documentation (ADR-0025): Comprehensive ASCII diagrams

### v1.2.0 (2025-11-20)

- Technology stack upgrade (ADR-0018): DuckDB 1.4, urllib3 2.5, pyarrow 22
- CI/CD maturity improvements (ADR-0020): Dependabot, ruff linting, coverage enforcement

### v1.0.0 (2025-11-12)

- Initial implementation with 15 MADRs (ADR-0001 through ADR-0015)
- Historical backfill (2019-09-25 to present)
- GitHub Actions automation (ADR-0009, supersedes APScheduler ADR-0004)
- 80%+ test coverage achieved
- Volume metrics collection (file_size_bytes, last_modified)
