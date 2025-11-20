# Modern Python Packaging Analysis for Data-Centric Packages

## Current State (binance-futures-availability)

**Strengths:**

- Semantic-release automation (pytest-compatible)
- GitHub Actions native distribution (zero infrastructure)
- Hybrid collection (AWS CLI + HTTP)
- Clean pyproject.toml (hatchling backend)
- DuckDB columnar format (50-150 MB)
- Volume rankings in Parquet (20 MB, remote query capable)

**Weaknesses:**

- Manual database download friction (gzip from GitHub Releases)
- No built-in caching layer
- No API abstraction (forces local file access)
- Parquet remote queries require DuckDB knowledge
- No PyPI integration for data files
- No version pinning for data artifacts

## Packaging Tools Landscape (Python 3.12+)

### Tool Comparison Matrix

| Tool       | Type            | Data Files      | CI/CD       | Cost | Maturity   |
| ---------- | --------------- | --------------- | ----------- | ---- | ---------- |
| **uv**     | Package Manager | ❌ No           | ✅ Native   | $0   | 🟢 Stable  |
| **hatch**  | Build System    | ⚠️ Limited      | ✅ Plugins  | $0   | 🟢 Stable  |
| **PDM**    | Package Manager | ✅ Data Files   | ✅ Backends | $0   | 🟢 Stable  |
| **rye**    | All-in-one      | ⚠️ Experimental | ✅ Built-in | $0   | 🟡 Growing |
| **poetry** | Package Manager | ⚠️ Plugins      | ✅ Scripts  | $0   | 🟢 Stable  |

### For Data-Centric Distribution

**Primary Challenge**: Python packaging was designed for code, not gigabytes of data.

**Solutions**:

1. **Lazy Loading Pattern** (Recommended for 50-150 MB)
   - Ship package with metadata only
   - Download data on first use
   - Cache in `$XDG_CACHE_HOME/binance-futures-availability/`
   - Zero installation size overhead

2. **Parquet on S3 (ADR-0013 Ready)**
   - Remote query via DuckDB httpfs
   - Pay-per-request S3 (fraction of cent per query)
   - Works globally with CloudFront
   - Version pinning via URL: `.../v1.0.0/volume-rankings.parquet`

3. **DuckDB Over HTTP**
   - DuckDB 1.0+ supports remote Parquet queries
   - 30-50% bandwidth savings vs download
   - No local storage required
   - SQL query interface

4. **Data Package Specification** (frictionless)
   - Standard metadata format
   - Integrates with PyPI
   - Versioned alongside code

## Option Analysis

### Option A: Enhanced GitHub Releases (Current + Lazy Loading)

**Description**: Keep GitHub Releases as primary distribution, add lazy loading to eliminate download friction

**Implementation**:

```python
class AvailabilityDB:
    def __init__(self):
        self.db_path = self._ensure_downloaded()

    def _ensure_downloaded(self):
        cache_dir = Path(os.getenv('XDG_CACHE_HOME', f"{Path.home()}/.cache"))
        db_path = cache_dir / "binance-futures" / "availability.duckdb"

        if not db_path.exists():
            # Download from GitHub Releases
            url = "https://github.com/.../releases/download/latest/availability.duckdb.gz"
            with urlopen(url) as r:
                with gzip.open(db_path) as gz:
                    db_path.write_bytes(gz.read())

        return db_path
```

**Pros**:

- ✅ Zero new infrastructure
- ✅ Transparent to users
- ✅ Works offline after first download
- ✅ Respects XDG cache standard
- ✅ Easy debugging (db_path visible)

**Cons**:

- ⚠️ 50-150 MB download on first import
- ⚠️ Cache invalidation requires rm

**Cost**: $0
**User Experience**: 7/10 (first run slow, subsequent fast)
**Adoption Friction**: Very low
**Recommendation**: ✅ Quick win - implement immediately

---

### Option B: Remote Parquet Queries (ADR-0013 Native)

**Description**: Leverage existing volume-rankings-timeseries.parquet, extend to daily_availability

**Implementation**:

```python
import duckdb

# Remote query - no download
result = duckdb.execute("""
    SELECT * FROM 'https://github.com/.../releases/download/latest/daily-availability.parquet'
    WHERE date = '2024-01-15'
""").fetch_df()
```

**Pros**:

- ✅ Zero local storage
- ✅ Real-time data access
- ✅ Bandwidth efficient (column pruning)
- ✅ Works with cloud analytics (Databricks, etc)
- ✅ Already proven (volume-rankings works)

**Cons**:

- ⚠️ DuckDB httpfs dependency (adds ~10 MB)
- ⚠️ Requires network on every query
- ⚠️ Cold query latency ~2-5 seconds (S3 roundtrip)
- ⚠️ Not ideal for high-frequency apps

**Cost**: ~$0.01-0.05/month (GitHub bandwidth is free)
**User Experience**: 8/10 (transparent, scalable)
**Adoption Friction**: Low (import duckdb, change URL)
**Recommendation**: ✅ Medium-term - convert availability to Parquet

---

### Option C: S3 + CloudFront Distribution (Production Scale)

**Description**: Replace GitHub Releases with CloudFront CDN, serve compressed/Parquet directly

**Implementation**:

```python
import s3fs
import duckdb

# S3 direct access (authentication-free public bucket)
result = duckdb.execute("""
    SELECT * FROM 's3://my-bucket/data/availability-2025-11-20.parquet'
""").fetch_df()
```

**Pros**:

- ✅ Scalable to 1000s of concurrent users
- ✅ Geographic distribution (CloudFront edge caches)
- ✅ Versioned artifacts (daily snapshots)
- ✅ Parquet native (analytics tools understand)
- ✅ Pay-as-you-go (S3 + CloudFront)

**Cons**:

- ❌ Requires AWS account + management
- ⚠️ Monthly cost ($1-5 for this use case)
- ⚠️ Adds operational complexity
- ⚠️ Not suitable until >1000 users

**Cost**: $1-5/month (S3 storage + egress)
**User Experience**: 9/10 (global CDN, version control)
**Adoption Friction**: Medium (s3fs dependency, auth)
**Recommendation**: ⏸️ Defer until usage demands it

---

### Option D: Hosted Query API (Serverless)

**Description**: DuckDB query service via FastAPI on Modal/Fly.io

**Implementation**:

```python
import httpx

response = httpx.get(
    "https://binance-api.eon.cloud/query",
    params={
        "query": "SELECT * FROM availability WHERE date = '2024-01-15'",
        "format": "parquet"
    }
)
df = response.content  # Raw Parquet bytes
```

**Pros**:

- ✅ REST API abstraction
- ✅ Caching layer (Redis)
- ✅ Query logging/analytics
- ✅ Rate limiting built-in
- ✅ Works with any language

**Cons**:

- ❌ Requires server maintenance
- ⚠️ Cold start latency (Modal: 1-3s)
- ⚠️ API versioning headaches
- ⚠️ Data sync complexity

**Cost**: $10-50/month (Modal Pro or Fly.io Postgres)
**User Experience**: 7/10 (API dependency)
**Adoption Friction**: High (new auth model)
**Recommendation**: ❌ Premature - wait for 100+ daily active users

---

### Option E: Data Package + Registry

**Description**: Use frictionless Data Package spec, register with datasets.org

**Implementation**:

```json
{
  "name": "binance-futures-availability",
  "version": "1.1.0",
  "resources": [
    {
      "name": "daily_availability",
      "url": "s3://bucket/availability.parquet",
      "hash": "sha256:abc123...",
      "schema": {...}
    }
  ]
}
```

**Pros**:

- ✅ Standard metadata format
- ✅ Tool-agnostic (R, Python, Julia compatible)
- ✅ Versioning built-in
- ✅ Reproducible research friendly

**Cons**:

- ⚠️ Ecosystem still niche
- ⚠️ Limited tool support vs PyPI
- ⚠️ Learning curve for users
- ⚠️ Not well integrated with Python packaging

**Cost**: $0
**User Experience**: 6/10 (non-standard)
**Adoption Friction**: High (ecosystem education)
**Recommendation**: ⏸️ Consider for Dask/Polars users later

---

## Recommended Phased Approach

### Phase 1: Quick Wins (Week 1)

- ✅ **Implement lazy loading** (Option A)
  - `from binance_futures_availability import get_db()`
  - Transparent caching in `~/.cache/`
  - Zero changes to release process

### Phase 2: Analytics-Friendly (Week 2-3)

- ✅ **Convert availability to Parquet** (Option B)
  - Replicate current DuckDB export logic
  - Add to release artifacts
  - Document remote query pattern

### Phase 3: Monitor Adoption (Months 2-3)

- ⏸️ **Track download stats** from GitHub Releases
- ⏸️ **Survey users** (Reddit, Discord, Issues)
- ⏸️ If >500 downloads/month → Consider Option C
- ⏸️ If >50 API requests/month → Reconsider Option D

### Phase 4: Scale Horizontally (Months 4-6)

- ⏸️ **S3 + CloudFront** (Option C) if data transfer costs exceed $5/month
- ⏸️ **Hosted Query API** (Option D) if users demand interactive exploration

---

## Cost Comparison (12 Months)

| Option        | Setup  | Monthly | Annual | User Impact         |
| ------------- | ------ | ------- | ------ | ------------------- |
| A (Lazy Load) | 2 hrs  | $0      | $0     | +1s first run       |
| B (Parquet)   | 4 hrs  | $0      | $0     | -2-5s per query     |
| C (S3+CDN)    | 8 hrs  | $3      | $36    | Global 50ms latency |
| D (API)       | 16 hrs | $20     | $240   | +100ms API latency  |
| E (Data Pkg)  | 4 hrs  | $0      | $0     | Non-standard        |

---

## Integration with Current Stack

**Preserves**:

- ✅ Semantic-release (no changes)
- ✅ GitHub Actions workflow
- ✅ DuckDB database format
- ✅ Existing API/CLI

**Enhances**:

- 🔄 First-run experience (lazy load)
- 🔄 Query performance (Parquet remote)
- 🔄 Discoverability (PyPI data files)
- 🔄 Scalability pathway (S3/CDN ready)
