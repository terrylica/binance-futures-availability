# System Architecture

**Version**: 1.0.0
**Updated**: 2025-11-25
**ADR**: [0025-system-architecture-documentation](decisions/0025-system-architecture-documentation.md)

## Overview

The binance-futures-availability system tracks daily availability of USDT perpetual futures from Binance Vision S3. It collects availability data and volume metrics, stores them in DuckDB, and distributes via GitHub Releases.

**Key Characteristics**:

- **Data Source**: Binance Vision S3 (~327 active symbols, 2019-09-25 to present)
- **Storage**: DuckDB columnar database (50-150 MB compressed)
- **Automation**: GitHub Actions (daily 3AM UTC)
- **Distribution**: GitHub Releases with gzip compression

## Data Flow Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    BINANCE VISION S3                         │
│     https://data.binance.vision/data/futures/um/daily/       │
│              (~327 active symbols, 2019-09-25 to now)        │
└─────────────────────────────┬────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
    ┌─────▼─────┐       ┌─────▼─────┐       ┌─────▼─────┐
    │ DISCOVERY │       │COLLECTION │       │  VOLUME   │
    │           │       │           │       │  METRICS  │
    │ S3 XML    │       │ HTTP HEAD │       │ 1d klines │
    │ enumerate │       │ AWS CLI   │       │ OHLCV     │
    └─────┬─────┘       └─────┬─────┘       └─────┬─────┘
          │                   │                   │
          └───────────────────┼───────────────────┘
                              │
                     ┌────────▼────────┐
                     │     DUCKDB      │
                     │                 │
                     │daily_availability│
                     │ (date, symbol)  │
                     │   50-150 MB     │
                     └────────┬────────┘
                              │
         ┌────────────────────┼────────────────────┐
         │                    │                    │
   ┌─────▼─────┐        ┌─────▼─────┐        ┌─────▼─────┐
   │ VALIDATION│        │  RANKINGS │        │  RELEASE  │
   │           │        │           │        │           │
   │Transparency│       │  Parquet  │        │  .duckdb  │
   │  -first   │        │  7d/30d   │        │  .gz      │
   └─────┬─────┘        └─────┬─────┘        └─────┬─────┘
         │                    │                    │
         └────────────────────┼────────────────────┘
                              │
                     ┌────────▼────────┐
                     │  NOTIFICATION   │
                     │                 │
                     │  Pushover API   │
                     │  (instant push) │
                     └─────────────────┘
```

**Data Flow Summary**:

| Stage        | Input               | Output               | ADR      |
| ------------ | ------------------- | -------------------- | -------- |
| Discovery    | S3 XML API          | symbols.json         | ADR-0010 |
| Collection   | HTTP HEAD / AWS CLI | availability records | ADR-0005 |
| Volume       | 1d klines ZIP       | OHLCV metrics        | ADR-0007 |
| Storage      | Records             | DuckDB table         | ADR-0002 |
| Validation   | Database            | Warnings (info only) | ADR-0003 |
| Rankings     | Database            | Parquet snapshots    | ADR-0013 |
| Release      | Database            | GitHub Release       | ADR-0009 |
| Notification | Status              | Pushover alert       | ADR-0022 |

## Runtime Control Flow

```
┌─────────────────────────────────────────────────────────────┐
│                     TRIGGER SOURCES                         │
├──────────────┬──────────────┬──────────────┬───────────────┤
│   SCHEDULE   │    MANUAL    │     CLI      │   BACKFILL    │
│  (3AM UTC)   │  (dispatch)  │   (query)    │  (one-time)   │
│   cron job   │  gh workflow │ binance-*    │  full history │
└──────┬───────┴──────┬───────┴──────┬───────┴───────┬───────┘
       │              │              │               │
       ▼              ▼              ▼               ▼
┌────────────┐ ┌────────────┐ ┌────────────┐ ┌──────────────┐
│   Daily    │ │   Custom   │ │  Read-only │ │ AWS CLI bulk │
│   Update   │ │  Lookback  │ │   Queries  │ │ 2019-present │
│  20 days   │ │   N days   │ │  snapshot  │ │  ~25 minutes │
│  ~1.5 sec  │ │  variable  │ │  timeline  │ │  327 symbols │
└────────────┘ └────────────┘ └────────────┘ └──────────────┘
```

**Execution Modes**:

| Mode     | Trigger            | Duration | Use Case                  |
| -------- | ------------------ | -------- | ------------------------- |
| Schedule | Cron 3AM UTC       | ~3-5 min | Daily automated updates   |
| Manual   | workflow_dispatch  | Variable | Custom lookback, testing  |
| CLI      | binance-futures-\* | <1 sec   | Queries, debugging        |
| Backfill | One-time script    | ~25 min  | Initial setup, gap repair |

## Component Architecture

```
src/binance_futures_availability/
│
├── database/
│   ├── availability_db.py    # DuckDB operations (CRUD)
│   └── schema.py             # Table creation + migrations
│
├── probing/
│   ├── batch_prober.py       # Parallel HTTP HEAD (150 workers)
│   ├── aws_lister.py         # AWS CLI bulk listing
│   ├── s3_vision.py          # S3 URL construction
│   └── symbol_discovery.py   # S3 XML enumeration
│
├── queries/
│   ├── snapshot.py           # Point-in-time queries (<1ms)
│   ├── timeline.py           # Symbol history (<10ms)
│   ├── analytics.py          # Aggregations
│   └── volume.py             # OHLCV metrics
│
├── validation/
│   ├── continuity.py         # Missing date detection
│   ├── completeness.py       # Symbol count validation
│   └── cross_check.py        # Binance API comparison
│
├── cli/
│   ├── main.py               # Entry point
│   └── commands.py           # Subcommands
│
├── config/
│   └── symbol_loader.py      # Symbol list management
│
└── data/
    └── symbols.json          # Auto-discovered symbols
```

**Module Responsibilities**:

| Module      | Responsibility         | Key Classes                                    |
| ----------- | ---------------------- | ---------------------------------------------- |
| database/   | DuckDB storage layer   | `AvailabilityDatabase`, `create_schema()`      |
| probing/    | S3 data collection     | `BatchProber`, `AWSS3Lister`                   |
| queries/    | Data access layer      | `SnapshotQueries`, `TimelineQueries`           |
| validation/ | Data quality checks    | `ContinuityValidator`, `CompletenessValidator` |
| cli/        | Command-line interface | `main()`, subcommands                          |
| config/     | Symbol configuration   | `load_symbols()`                               |

## Deployment Topology

```
┌────────────────────────────────────────────────────────────┐
│                  GitHub Repository                         │
│           terrylica/binance-futures-availability           │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │          GitHub Actions Workflow                     │  │
│  │          .github/workflows/update-database.yml       │  │
│  │                                                      │  │
│  │  Environment:                                        │  │
│  │  - ubuntu-latest                                     │  │
│  │  - Python 3.12                                       │  │
│  │  - AWS CLI (pre-installed)                           │  │
│  │  - uv package manager                                │  │
│  │                                                      │  │
│  │  Schedule: Daily 3:00 AM UTC                         │  │
│  │  Secrets: DOPPLER_TOKEN (Pushover credentials)       │  │
│  └──────────────────────────────────────────────────────┘  │
│                           │                                │
│                           ▼                                │
│  ┌──────────────────────────────────────────────────────┐  │
│  │            GitHub Releases (tag: latest)             │  │
│  │                                                      │  │
│  │  Assets:                                             │  │
│  │  - availability.duckdb (50-150 MB)                   │  │
│  │  - availability.duckdb.gz (compressed)               │  │
│  │  - volume-rankings-timeseries.parquet                │  │
│  │  - Release notes with statistics                     │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                            │
└────────────────────────────────────────────────────────────┘
                            │
          ┌─────────────────┼─────────────────┐
          │                 │                 │
    ┌─────▼─────┐     ┌─────▼─────┐     ┌─────▼─────┐
    │ Pushover  │     │  Binance  │     │   Users   │
    │    API    │     │  Vision   │     │           │
    │           │     │    S3     │     │ Download  │
    │  Notify   │     │ (source)  │     │ & query   │
    └───────────┘     └───────────┘     └───────────┘
```

**Infrastructure Components**:

| Component         | Purpose            | SLA         |
| ----------------- | ------------------ | ----------- |
| GitHub Actions    | Workflow execution | 99.9%       |
| GitHub Releases   | Asset distribution | 99.9%       |
| Binance Vision S3 | Data source        | Best-effort |
| Pushover API      | Notifications      | 99.9%       |
| Doppler           | Secrets management | 99.99%      |

## Related Documentation

### Architecture Decision Records

- [ADR-0002](decisions/0002-storage-technology-duckdb.md): Storage Technology - DuckDB
- [ADR-0003](decisions/0003-error-handling-strict-policy.md): Error Handling - Strict Raise Policy
- [ADR-0005](decisions/0005-aws-cli-bulk-operations.md): AWS CLI for Bulk Operations
- [ADR-0007](decisions/0007-trading-volume-metrics.md): Trading Volume Metrics
- [ADR-0009](decisions/0009-github-actions-automation.md): GitHub Actions Automation
- [ADR-0010](decisions/0010-dynamic-symbol-discovery.md): Dynamic Symbol Discovery
- [ADR-0011](decisions/0011-20day-lookback-reliability.md): 20-Day Lookback Reliability
- [ADR-0013](decisions/0013-volume-rankings-timeseries.md): Volume Rankings Timeseries
- [ADR-0022](decisions/0022-pushover-workflow-notifications.md): Pushover Notifications
- [ADR-0025](decisions/0025-system-architecture-documentation.md): This Documentation

### Operational Guides

- [CLAUDE.md](../../CLAUDE.md): Project memory and quick reference
- [README.md](../../README.md): User-facing documentation
- [QUICKSTART.md](../guides/QUICKSTART.md): Getting started guide
- [GITHUB_ACTIONS.md](../operations/GITHUB_ACTIONS.md): CI/CD workflow details

### Schema Documentation

- [availability-database.schema.json](../schema/availability-database.schema.json): Database schema
- [query-patterns.schema.json](../schema/query-patterns.schema.json): Query patterns
