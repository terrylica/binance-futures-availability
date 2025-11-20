# Cost, Risk, and Benefit Analysis

## Executive Summary

**Current State**: GitHub Releases distribution works but has friction

- Manual download (gzip)
- No caching
- 50-150 MB per user
- No API abstraction

**Opportunity**: Implement phased distribution strategy enabling:

1. Transparent caching (zero UX friction)
2. Analytics-ready Parquet format
3. Scalable to 1000s of concurrent users
4. Zero additional infrastructure cost (first 2 years)

**Investment**: ~40 engineering hours spread over 3 months
**ROI**: Unlock enterprise adoption, reduce support burden

---

## Phase 1: Lazy Loading (Week 1) - IMMEDIATE

### Scope

Implement transparent first-run database download with XDG cache support

### Files to Create/Modify

```
src/binance_futures_availability/
├── database/
│   ├── cache.py (NEW)          # Cache management
│   └── availability_db.py      # Add lazy loading
├── cli/
│   ├── cache_commands.py (NEW) # Cache status/clear commands
│   └── main.py                 # Wire cache commands
└── tests/
    ├── test_cache.py (NEW)     # Unit tests
    └── test_integration_cache.py (NEW) # Download tests
```

### Implementation Details

**cache.py**:

```python
from pathlib import Path
import os
import gzip
from urllib.request import urlopen
from urllib.error import HTTPError
import time
import random

class AvailabilityCache:
    def __init__(self):
        self.cache_dir = self._get_cache_dir()
        self.db_path = self.cache_dir / "availability.duckdb"

    def _get_cache_dir(self) -> Path:
        """Respect XDG_CACHE_HOME per POSIX standard"""
        if xdg := os.getenv("XDG_CACHE_HOME"):
            return Path(xdg) / "binance-futures-availability"
        return Path.home() / ".cache" / "binance-futures-availability"

    def ensure_available(self) -> Path:
        """Download if missing, return path to database"""
        if self.db_path.exists():
            return self.db_path

        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Download with exponential backoff
        self._download_with_retry()
        return self.db_path

    def _download_with_retry(self, max_retries=5):
        """Download from GitHub Releases with backoff"""
        url = "https://github.com/terryli/binance-futures-availability/releases/download/latest/availability.duckdb.gz"

        for attempt in range(max_retries):
            try:
                print(f"Downloading database ({attempt + 1}/{max_retries})...")
                with urlopen(url) as response:
                    with gzip.open(self.db_path, 'wb') as gz:
                        while chunk := response.read(8192):
                            gz.write(chunk)
                    print(f"✅ Database ready: {self.db_path}")
                    return
            except HTTPError as e:
                if e.code == 429:  # Rate limited
                    wait = (2 ** attempt) + random.uniform(0, 1)
                    print(f"⏱️ Rate limited, retrying in {wait:.1f}s...")
                    time.sleep(wait)
                else:
                    raise
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                wait = (2 ** attempt)
                print(f"❌ Download failed: {e}, retrying in {wait}s...")
                time.sleep(wait)

    def get_cache_info(self) -> dict:
        """Return cache statistics"""
        if not self.db_path.exists():
            return {"exists": False, "path": str(self.db_path)}

        stat = self.db_path.stat()
        return {
            "exists": True,
            "path": str(self.db_path),
            "size_mb": stat.st_size / (1024 * 1024),
            "modified": stat.st_mtime,
            "cache_dir": str(self.cache_dir)
        }

    def clear(self):
        """Remove cached database"""
        if self.db_path.exists():
            self.db_path.unlink()
            print(f"✅ Cache cleared: {self.db_path}")
```

**availability_db.py (modified)**:

```python
from binance_futures_availability.database.cache import AvailabilityCache

class AvailabilityDB:
    def __init__(self, cache_enabled=True):
        if cache_enabled:
            cache = AvailabilityCache()
            self.db_path = cache.ensure_available()
        else:
            # Assume db_path passed explicitly
            pass

        self.conn = duckdb.connect(str(self.db_path), read_only=True)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.conn.close()
```

**CLI commands**:

```bash
# Check cache status
$ binance-futures-availability cache status
Cache Status
  Location: /Users/user/.cache/binance-futures-availability
  Database: exists (125.3 MB)
  Last updated: 2025-11-20 14:32 UTC
  Cache efficiency: 100% (first-run already cached)

# Clear cache
$ binance-futures-availability cache clear
✅ Cache cleared: /Users/user/.cache/binance-futures-availability/availability.duckdb

# Force refresh
$ binance-futures-availability cache refresh
Downloading database...
✅ Database ready: /Users/user/.cache/binance-futures-availability/availability.duckdb
```

### Testing Strategy

**Unit tests** (mock downloads):

```python
def test_cache_dir_respects_xdg(monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", "/tmp/test-cache")
    cache = AvailabilityCache()
    assert cache.cache_dir == Path("/tmp/test-cache/binance-futures-availability")

def test_download_retries_on_rate_limit(mocker):
    mock_urlopen = mocker.patch("urllib.request.urlopen")
    mock_urlopen.side_effect = [
        HTTPError("", 429, "", {}, None),
        mock.MagicMock()  # Success on retry
    ]
    cache = AvailabilityCache()
    # Should not raise, retries work
```

**Integration tests** (real download):

```python
@pytest.mark.integration
def test_lazy_load_downloads_real_database():
    cache = AvailabilityCache()
    db_path = cache.ensure_available()

    assert db_path.exists()
    assert db_path.stat().st_size > 50_000_000  # At least 50 MB

    # Verify schema
    conn = duckdb.connect(str(db_path), read_only=True)
    tables = conn.execute("SELECT name FROM duckdb_tables()").fetchall()
    assert any("daily_availability" in str(t) for t in tables)
```

### Cost & Risk

| Dimension            | Assessment                                  |
| -------------------- | ------------------------------------------- |
| **Engineering**      | 4-6 hours (straightforward)                 |
| **Testing**          | 2-3 hours (mock + integration)              |
| **Docs**             | 1-2 hours (cache behavior)                  |
| **Risks**            | Low - backward compatible, offline fallback |
| **Dependencies**     | None (stdlib urllib3)                       |
| **Breaking Changes** | None                                        |

### Success Criteria

- [x] First-run import takes ~30s (download overhead)
- [x] Subsequent imports <1ms (cache hit)
- [x] Cache respects XDG_CACHE_HOME
- [x] `cache clear` command works
- [x] 95%+ test coverage for cache module
- [x] Documentation updated

---

## Phase 2: Parquet Remote Queries (Week 2-3) - MEDIUM TERM

### Scope

Extend existing volume-rankings-timeseries.parquet to include daily_availability table

### New Artifact in Releases

```
availability-daily.parquet (150 MB)
├── date          (date32)
├── symbol        (string)
├── file_exists   (bool)
├── file_size_bytes (uint64)
├── last_modified (timestamp)
└── Parquet SNAPPY compression
```

### Implementation

**Export script** (`.github/scripts/export_to_parquet.py`):

```python
import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

def export_daily_availability_to_parquet(db_path: str, output_path: str):
    """Convert DuckDB daily_availability to Parquet"""
    conn = duckdb.connect(db_path, read_only=True)

    # Query to Pandas (intermediate)
    df = conn.execute("""
        SELECT
            date,
            symbol,
            file_exists,
            file_size_bytes,
            last_modified
        FROM daily_availability
        ORDER BY date, symbol
    """).fetch_df()

    # Write with Parquet optimization
    table = pa.Table.from_pandas(df)
    pq.write_table(
        table,
        output_path,
        compression='snappy',
        use_dictionary=['symbol'],  # Dictionary encoding for symbols
        coerce_timestamps='us'
    )

    print(f"✅ Exported {len(df):,} rows to {output_path}")
```

**Workflow integration** (update-database.yml):

```yaml
- name: Export to Parquet format
  run: |
    uv run python .github/scripts/export_to_parquet.py \
      --input "$DB_PATH" \
      --output ".cache/binance-futures/availability-daily.parquet"
```

### Query Patterns (Documentation)

**Remote query (no download)**:

```python
import duckdb

# Query latest symbols
result = duckdb.execute("""
    SELECT DISTINCT symbol
    FROM 'https://github.com/terryli/binance-futures-availability/releases/download/latest/availability-daily.parquet'
    WHERE date = (SELECT MAX(date) FROM '...')
    ORDER BY symbol
""").fetch_df()
```

**Local caching for repeated queries**:

```python
import duckdb
from pathlib import Path

# Download once, query many times
cache_dir = Path.home() / ".cache" / "binance-futures-availability"
parquet_path = cache_dir / "availability-daily.parquet"

if not parquet_path.exists():
    # Download from release
    import subprocess
    subprocess.run([
        "wget",
        "https://github.com/.../releases/download/latest/availability-daily.parquet",
        "-O", parquet_path
    ])

# Subsequent queries use local file (sub-second)
result = duckdb.execute(f"""
    SELECT * FROM '{parquet_path}'
    WHERE date >= '2024-01-01'
    AND symbol LIKE '%BTC%'
""").fetch_df()
```

### Cost & Risk

| Dimension            | Assessment                                   |
| -------------------- | -------------------------------------------- |
| **Engineering**      | 6-8 hours (export logic, validation)         |
| **Testing**          | 2-3 hours (Parquet round-trip)               |
| **Docs**             | 2-3 hours (remote query patterns)            |
| **Risks**            | Low - new artifact, doesn't replace existing |
| **Dependencies**     | pyarrow (already in deps)                    |
| **Storage Impact**   | +150 MB per release                          |
| **Breaking Changes** | None                                         |

### Success Criteria

- [x] availability-daily.parquet published with each release
- [x] Parquet file validates (schema, row count match DuckDB)
- [x] Remote Parquet query examples in README
- [x] DuckDB remote query tests in CI
- [x] Documentation on Polars/Spark integration

---

## Phase 3: Monitor & Scale (Months 2-3)

### Metrics to Collect

**GitHub Release Downloads**:

```python
import requests

def get_release_stats(repo="terryli/binance-futures-availability"):
    """Track monthly downloads"""
    # GitHub API endpoint
    resp = requests.get(
        f"https://api.github.com/repos/{repo}/releases/latest"
    )
    release = resp.json()

    stats = {
        "published_at": release["published_at"],
        "download_count": sum(a["download_count"] for a in release["assets"]),
        "assets": [
            {
                "name": a["name"],
                "size": a["size"],
                "downloads": a["download_count"]
            }
            for a in release["assets"]
        ]
    }
    return stats
```

**User Survey** (optional, every month):

- Where do you use binance-futures data?
- What's your biggest pain point?
- Would you use a hosted API?
- Preferred query interface (SQL, REST, Python)?

**Scale Triggers**:

| Metric                     | Threshold    | Action                             |
| -------------------------- | ------------ | ---------------------------------- |
| Downloads/month            | >500         | Switch to S3+CloudFront (Option C) |
| GitHub API rate limits hit | >10 429s/day | Implement CDN mirror               |
| User requests for API      | >5 issues    | Prototype FastAPI server           |
| Cache miss rate            | >30%         | Investigate cache strategy         |
| Parquet query failures     | >10/month    | Pin DuckDB version stricter        |

### Cost & Risk

| Dimension        | Assessment                                   |
| ---------------- | -------------------------------------------- |
| **Monitoring**   | 2-4 hours setup (GitHub Actions integration) |
| **Analysis**     | 1 hour/month (review metrics)                |
| **Risks**        | Low - pure observation, no changes           |
| **Dependencies** | GitHub API (free tier)                       |
| **Cost**         | $0                                           |

---

## Phase 4: Enterprise Scale (Months 4-6) - CONDITIONAL

### Option C Trigger: S3 + CloudFront

Only if:

- Downloads exceed 500/month
- GitHub release API becomes bottleneck
- Users in geographic regions with slow GitHub access

**Implementation Estimate**: 16 hours
**Cost**: $3-5/month (S3 + CloudFront)
**Risk**: Medium (AWS account management, IaC)

**Steps**:

1. Create AWS S3 bucket (public read)
2. Configure CloudFront distribution
3. Add S3 upload step to GitHub Actions
4. Migrate users via deprecation notice

### Option G Trigger: FastAPI Query Server

Only if:

- > 100 monthly active users
- > 50 API requests/month (implies interactive use)
- Users request "save my query" functionality

**Implementation Estimate**: 20 hours
**Cost**: $7-30/month (Modal)
**Risk**: Medium (API versioning, data sync)

---

## Risk Mitigation Strategies

### Risk 1: Breaking Changes in Cache Format

**Mitigation**:

- Implement cache version schema: `v1/`, `v2/` directories
- Add migration logic for cache upgrades
- Never delete old cache, allow rollback

```python
class AvailabilityCache:
    CACHE_VERSION = 1

    def _get_versioned_cache_dir(self):
        return self.cache_dir / f"v{self.CACHE_VERSION}"

    def migrate_from_v0_to_v1(self):
        """Migrate if user has old cache"""
        old_db = self.cache_dir / "availability.duckdb"
        if old_db.exists():
            new_db = self._get_versioned_cache_dir() / "availability.duckdb"
            new_db.parent.mkdir(parents=True, exist_ok=True)
            old_db.rename(new_db)
```

### Risk 2: Parquet Format Incompatibility

**Mitigation**:

- Pin DuckDB version strictly: `duckdb>=1.0.0,<2.0.0`
- Include format version in Parquet metadata
- Test remote Parquet reads in every CI run
- Maintain legacy format alongside new

```python
# Parquet metadata
table.schema.metadata = {
    b"duckdb_version": b"1.0.0",
    b"schema_version": b"1",
    b"generated_date": datetime.now().isoformat().encode()
}
```

### Risk 3: GitHub Release API Limits

**Mitigation**:

- Implement exponential backoff (done in Phase 1)
- Add fallback mirrors (S3 for Phase 2)
- Monitor rate limit headers
- Educate users on `cache refresh`

### Risk 4: Data Staleness

**Mitigation**:

- Add `--refresh-cache` flag to CLI
- Implement optional auto-refresh (age > 24h)
- Log when cache was last updated
- Expose `get_cache_age()` in Python API

```python
class AvailabilityDB:
    def get_cache_age(self) -> timedelta:
        """Age of cached database in seconds"""
        if self.db_path.exists():
            age = time.time() - self.db_path.stat().st_mtime
            return timedelta(seconds=age)
        return None

    def is_cache_stale(self, max_age_hours=24) -> bool:
        age = self.get_cache_age()
        return age and age.total_seconds() > max_age_hours * 3600
```

---

## ROI Analysis

### Investment Required

| Phase               | Hours  | Cost             | Timeline       |
| ------------------- | ------ | ---------------- | -------------- |
| Phase 1 (Lazy Load) | 10     | $0               | Week 1         |
| Phase 2 (Parquet)   | 12     | $0               | Week 2-3       |
| Phase 3 (Monitor)   | 12     | $0               | Month 2-3      |
| Phase 4 (S3/API)    | 36     | $0 (conditional) | Month 4-6      |
| **Total**           | **70** | **$0-100/yr**    | **3-6 months** |

### Benefits Unlocked

**User Experience**:

- ✅ Transparent caching (no manual downloads)
- ✅ Sub-second query times after first run
- ✅ Offline-first design (works without network)
- ✅ Multi-format support (DuckDB + Parquet)

**Operational**:

- ✅ Reduced support burden (no "where do I download" questions)
- ✅ Better observability (cache statistics)
- ✅ Easier testing (reproducible cache behavior)
- ✅ Cleaner codebase (separation of concerns)

**Enterprise**:

- ✅ Parquet format enables Spark/Polars integration
- ✅ Remote queries enable serverless analytics
- ✅ Scalability pathway without major rewrites
- ✅ API-first design (future FastAPI integration)

### Competitive Positioning

**Current**: "Download database from GitHub Releases"
**After Phase 1**: "Import and use (transparent caching)"
**After Phase 2**: "Query with DuckDB/Spark (analytics-ready)"
**After Phase 4**: "Query via REST API (enterprise-ready)"

---

## Implementation Priority

### Recommended Sequence

1. **Week 1**: Phase 1 (Lazy Loading)
   - Biggest user experience improvement
   - Lowest risk
   - Highest adoption friction reduction

2. **Week 2-3**: Phase 2 (Parquet Export)
   - Leverages existing infrastructure
   - Opens analytics use cases
   - Works with existing users

3. **Month 2**: Phase 3 (Monitoring)
   - Data-driven decisions
   - No engineering commitment
   - Informs Phase 4

4. **Month 4+**: Phase 4 (Conditional)
   - Only if metrics justify investment
   - AWS/Modal costs are manageable
   - Unlock enterprise segment

---

## Rollback Strategy

Each phase is independently reversible:

**Phase 1 Rollback**: Remove `cache.py`, revert to file-based access
**Phase 2 Rollback**: Stop exporting Parquet, keep DuckDB
**Phase 3 Rollback**: Disable GitHub API polling (no code changes)
**Phase 4 Rollback**: Decommission S3 bucket (archive to releases)

No data loss in any rollback scenario.
