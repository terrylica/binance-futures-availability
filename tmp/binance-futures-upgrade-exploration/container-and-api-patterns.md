# Container Images and API Patterns for Data Distribution

## Container Distribution Patterns

### Option F: OCI Image with Embedded Database

**Description**: Docker image with pre-loaded database, publish to GitHub Container Registry (GHCR)

**Dockerfile**:

```dockerfile
FROM python:3.12-slim

# Install dependencies
RUN pip install -e .

# Copy pre-built database
COPY .cache/binance-futures/availability.duckdb /data/availability.duckdb

# Create query server
COPY api/server.py /app/server.py

EXPOSE 8000
CMD ["python", "/app/server.py"]
```

**Pros**:

- ✅ Single artifact (image = code + data)
- ✅ Reproducible across environments
- ✅ Works with K8s, Docker Compose, Podman
- ✅ No installation required (`docker run`)
- ✅ Instant startup (pre-built deps)

**Cons**:

- ⚠️ Image size: 500-700 MB (database + Python)
- ⚠️ Slow pull times on limited bandwidth
- ⚠️ Overkill for single user
- ⚠️ Requires Docker/Podman installed
- ⚠️ GHCR storage quota limits (5 GB free)

**Use Case**:

- Data lake integration (Spark, Polars)
- Enterprise data pipelines
- Kubernetes deployments

**Cost**: $0 (GHCR free for public repos)
**User Experience**: 8/10 (for container users)
**Adoption Friction**: High (non-Python ecosystem)
**Recommendation**: ⏸️ Defer until K8s adoption needed

---

## API Server Patterns

### Option G: Lightweight FastAPI Query Server (Modal)

**Description**: REST API for queries, hosted on Modal serverless

**Implementation**:

```python
from fastapi import FastAPI
import duckdb

app = FastAPI()

@app.get("/query")
async def query(sql: str):
    conn = duckdb.connect("/data/availability.duckdb", read_only=True)
    return {"result": conn.execute(sql).fetch_df().to_dict()}

@app.get("/snapshot/{date}")
async def snapshot(date: str):
    conn = duckdb.connect("/data/availability.duckdb", read_only=True)
    result = conn.execute(
        "SELECT symbol FROM daily_availability WHERE date = ?",
        [date]
    ).fetchall()
    return {"symbols": result, "date": date}

@app.get("/timeline/{symbol}")
async def timeline(symbol: str):
    # Similar pattern
    pass
```

**Deployment** (Modal):

```bash
modal deploy api/server.py
# Generates HTTPS endpoint: https://user-project--server.modal.run
```

**Pros**:

- ✅ Natural REST API for data
- ✅ Caching built-in (Modal)
- ✅ Cold start <3s
- ✅ Integrates with monitoring (Datadog, etc)
- ✅ Language-agnostic (any HTTP client works)
- ✅ Query rate limiting built-in

**Cons**:

- ⚠️ Network roundtrip (50-500ms depending on location)
- ⚠️ Cold start latency first request
- ⚠️ API versioning overhead
- ⚠️ Data staleness (cached 1h)
- ⚠️ Requires Modal account ($7/month)

**Cost**: $7-30/month (Modal Pro, storage + compute)
**User Experience**: 7/10 (API dependency, reliable)
**Adoption Friction**: Medium (API docs, auth handling)
**Recommendation**: ✅ Implement if >100 monthly active users

---

### Option H: DuckDB SQL Editor (Jupyter Lite via GitHub Pages)

**Description**: Browser-based SQL editor with remote DuckDB queries

**Technology**: Jupyter Lite + DuckDB WASM

**HTML**:

```html
<script src="https://cdn.jsdelivr.net/pyodide/v0.23.0/full/pyodide.js"></script>
<textarea
  id="query"
  placeholder="SELECT * FROM daily_availability LIMIT 10"
></textarea>
<button onclick="runQuery()">Execute</button>
<div id="results"></div>

<script>
  async function runQuery() {
    let pyodide = await loadPyodide();
    await pyodide.loadPackage("duckdb");

    const sql = document.getElementById("query").value;
    const result = await pyodide.runPythonAsync(`
        import duckdb
        duckdb.execute('SELECT * FROM read_parquet("https://...")').fetchall()
    `);
  }
</script>
```

**Pros**:

- ✅ Zero backend infrastructure
- ✅ Runs entirely in browser
- ✅ GitHub Pages hosting (free)
- ✅ No authentication needed
- ✅ Responsive UI with editor

**Cons**:

- ⚠️ Pyodide startup (3-5s first load)
- ⚠️ Query results limited to browser memory
- ⚠️ Large result sets slow (>100K rows)
- ⚠️ No session persistence
- ⚠️ Niche audience (data scientists only)

**Cost**: $0
**User Experience**: 6/10 (browser-dependent)
**Adoption Friction**: Very High (Pyodide knowledge)
**Recommendation**: ⏸️ Interesting POC, not production-ready

---

## Comparison: API vs Container vs Direct Access

| Pattern                | Latency    | Scalability    | Cost    | DevOps     | When to Use            |
| ---------------------- | ---------- | -------------- | ------- | ---------- | ---------------------- |
| **Direct (Current)**   | <1ms       | Single user    | $0      | None       | Dev, small orgs        |
| **Lazy Load (A)**      | 50ms (1st) | 10-50 users    | $0      | None       | **→ Recommend First**  |
| **Remote Parquet (B)** | 200-500ms  | 100-1000 users | $0      | None       | **→ Recommend Second** |
| **FastAPI (G)**        | 100-300ms  | 1000+ users    | $7/mo   | Modal      | Large deployments      |
| **Container (F)**      | <1ms       | K8s clusters   | $0      | Kubernetes | Enterprise data lake   |
| **API Gateway (G+)**   | 50-100ms   | 10000+ users   | $50+/mo | Full stack | Netflix-scale          |

---

## Data Lake Integration Examples

### DuckDB + Polars (In-Process)

```python
import polars as pl
import duckdb

# Remote Parquet read
df = pl.scan_parquet(
    "https://github.com/.../releases/download/latest/availability.parquet"
).filter(pl.col("date") >= "2024-01-01").collect()

# Polars lazy execution = bandwidth efficient
```

**Pros**: Zero external API, language-native performance
**Cons**: Requires download, limited to Python ecosystem

### Apache Spark (Distributed)

```scala
val df = spark.read
    .parquet("s3://bucket/availability.parquet")
    .filter(col("date") >= "2024-01-01")
    .repartition(100)

df.write.mode("overwrite").parquet("/output")
```

**Pros**: Distributed processing, scales to TB
**Cons**: Requires Spark cluster, operational overhead

### Databricks SQL (Managed)

```sql
SELECT symbol, COUNT(*) as days_available
FROM parquet.`s3://bucket/availability.parquet`
WHERE date >= '2024-01-01'
GROUP BY symbol
ORDER BY days_available DESC
```

**Pros**: No infrastructure, built-in optimization
**Cons**: Vendor lock-in, per-query billing

---

## Recommended Integration Strategy

### For Individual Users (Current)

1. Use **Option A** (Lazy Loading) - transparent first-run download
2. Cache in `~/.cache/` following XDG standard
3. Offline-first design (works without network after download)

### For Data Teams (Growth)

1. Use **Option B** (Remote Parquet) - analytics-ready format
2. Document Polars/DuckDB remote query patterns
3. Publish to S3 when GitHub bandwidth becomes constraint

### For Enterprise (Scale)

1. Use **Option C** (S3+CloudFront) - global distribution
2. Versioned Parquet artifacts with SHA256 checksums
3. Optional: **Option G** (FastAPI) if OLAP queries needed

### For K8s Deployments (Advanced)

1. Use **Option F** (OCI Image) - reproducible packaging
2. Pre-built database in image layers
3. Health checks for query endpoint readiness

---

## Risk Assessment & Mitigation

### Risk 1: GitHub Release API Rate Limits

**Concern**: If >1000 concurrent downloads in hour, hit GH API limits

**Mitigation**:

- Add exponential backoff retry in lazy loader
- Monitor release download stats via GH Analytics
- Switch to S3 when >500 downloads/month

**Implementation**:

```python
import time
import random

def download_with_backoff(url, max_retries=5):
    for attempt in range(max_retries):
        try:
            return urlopen(url)
        except HTTPError as e:
            if e.code == 429:  # Rate limited
                wait = (2 ** attempt) + random.uniform(0, 1)
                time.sleep(wait)
            else:
                raise
```

### Risk 2: Data Staleness in Cache

**Concern**: Users get outdated database if release not recently triggered

**Mitigation**:

- Add version check: `latest_release_date > cached_date - 1 day`
- Implement `--refresh-cache` CLI flag
- Document cache invalidation

### Risk 3: Parquet Format Compatibility

**Concern**: DuckDB Parquet format changes break queries

**Mitigation**:

- Pin DuckDB version in dependencies: `duckdb>=1.0.0,<2.0.0`
- Test remote Parquet reads in CI
- Maintain conversion script for format migrations

---

## Telemetry & Monitoring (Without Tracking)

### What to Measure

1. **Cache Hit Rate** (local metric)
   - Users with cached database
   - Average time to first query

2. **Release Download Stats** (GitHub API)
   - Monthly downloads from release page
   - Spike detection (new users?)

3. **Test Coverage** (CI metric)
   - Remote Parquet query tests
   - API endpoint tests (if deployed)

### Implementation

```python
# Log cache behavior
import logging

logger = logging.getLogger("binance_futures_availability")

class AvailabilityDB:
    def __init__(self):
        if self._cache_exists():
            logger.info("Cache hit - loading from local")
            # metrics: cache_hit = True
        else:
            logger.info("Cache miss - downloading from release")
            # metrics: cache_hit = False
            self._download()
```
