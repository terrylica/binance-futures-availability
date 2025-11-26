# Technology Stack Analysis & Upgrade Report

## binance-futures-availability Project

**Report Date**: November 20, 2025
**Project**: binance-futures-availability v1.1.0
**Status**: Production-ready with GitHub Actions automation (v1.0.0 released June 2025)

---

## Executive Summary

The project's technology stack is well-chosen and relatively recent, with all core dependencies released or updated in 2024-2025. Most dependencies can be upgraded safely with minimal code changes. The primary opportunities are:

1. **High Priority**: Update GitHub Actions to latest versions (v4→v5, v5→v6)
2. **Medium Priority**: Upgrade Python dev dependencies (pytest, ruff, playwright)
3. **Low Priority**: Core database/HTTP deps are stable; can upgrade on standard schedule
4. **Strategic**: Evaluate whether `httpx` should supplement `urllib3` for async use cases

---

## Current Technology Stack

### Core Dependencies (Production)

| Package     | Current  | Latest | Gap      | Status    |
| ----------- | -------- | ------ | -------- | --------- |
| **duckdb**  | >=1.0.0  | 1.4.2  | 4 months | ✅ Stable |
| **urllib3** | >=2.0.0  | 2.5.0  | 4 months | ✅ Stable |
| **pyarrow** | >=18.0.0 | 22.0.0 | 5 months | ✅ Stable |

### Development Dependencies

| Package         | Current  | Latest | Gap             | Status          |
| --------------- | -------- | ------ | --------------- | --------------- |
| **pytest**      | >=8.4.0  | 9.0.1  | 1 month         | ⚠️ Minor update |
| **pytest-cov**  | >=5.0.0  | Latest | -               | ✅ Recent       |
| **pytest-mock** | >=3.14.0 | Latest | -               | ✅ Recent       |
| **ruff**        | >=0.14.0 | 0.14.5 | Current release | ✅ Recent       |
| **playwright**  | >=1.56.0 | 1.56.0 | Current release | ✅ Current      |

### Build & Distribution

| Tool                 | Current    | Latest | Gap     | Status                    |
| -------------------- | ---------- | ------ | ------- | ------------------------- |
| **hatchling**        | (implicit) | Latest | -       | ✅ Implicit build backend |
| **semantic-release** | 25.0.2     | 25.0.2 | Current | ✅ Current                |

### GitHub Actions

| Action                          | Current | Latest | Gap              | Status                     |
| ------------------------------- | ------- | ------ | ---------------- | -------------------------- |
| **actions/checkout**            | v4      | v6     | 2 major versions | ⚠️ **UPGRADE RECOMMENDED** |
| **actions/setup-python**        | v5      | v6     | 1 major version  | ⚠️ **UPGRADE RECOMMENDED** |
| **astral-sh/setup-uv**          | v3      | v3     | Current          | ✅ Current                 |
| **jdx/mise-action**             | v2      | v2     | Current          | ✅ Current                 |
| **softprops/action-gh-release** | v2      | v2     | Current          | ✅ Current                 |

### Platform & Runtime

| Component   | Current       | Latest | Status                                        |
| ----------- | ------------- | ------ | --------------------------------------------- |
| **Python**  | 3.12          | 3.14   | ✅ 3.12 LTS-adjacent (support until Oct 2028) |
| **Node.js** | 25 (via mise) | 24 LTS | ✅ Modern, within LTS window                  |
| **mise**    | latest        | latest | ✅ Latest version pinned                      |
| **uv**      | latest        | latest | ✅ Latest version pinned                      |

---

## Detailed Findings

### 1. DuckDB 1.0.0 → 1.4.2

**Current Requirement**: `>=1.0.0`
**Latest Version**: 1.4.2 (November 12, 2025)
**Status**: Stable, backwards compatible

#### Key Changes (1.0 → 1.4)

**1.1.0 (September 2024)**:

- IEEE-754 semantics: Division by zero now returns `inf` for floats (was `NULL`)
- Scalar subqueries returning multiple values now error
- Impact: Low (your code doesn't rely on division-by-zero handling)

**1.2.0 (February 2025)**:

- Random function state change: seeded randomness produces different values
- Map indexing: `map['k']` now returns value (not list) - **BREAKING**
- Removed Substrait API: `duckdb_get_substrait()`, etc. (unused in this project)
- Impact: Low (no map operations in your schema)

**1.3.0 (May 2025)**:

- Linux: requires glibc 2.28+ (your CI already uses Ubuntu, compliant)
- Impact: None for GitHub Actions (handled automatically)

**1.4.0 (September 2025 - LTS Release)**:

- CTE Materialization: CTEs now materialized by default (performance implications, needs profiling)
- VARINT renamed to BIGNUM (backward-compatible alias maintained)
- Impact: Query performance may change; no API changes needed

#### Recommendation

**UPGRADE SAFELY** - Pin to `duckdb>=1.4.0` (latest LTS release, 1-year community support)

```python
# pyproject.toml change
duckdb>=1.4.0,<2.0.0
```

**Testing**: Run validation suite before/after to measure query performance impact.

---

### 2. urllib3 2.0+ → 2.5.0

**Current Requirement**: `>=2.0.0`
**Latest Version**: 2.5.0 (June 18, 2025)
**Status**: Stable, mature 2.x line

#### Key Changes (2.0 → 2.5)

**2.0 Major Changes** (already adopted):

- Python 3.9+ required (you have 3.12)
- TLS 1.2 minimum (stronger security)
- UTF-8 default encoding (better internationalization)
- Removed commonName hostname verification (uses subjectAltName only)
- Better type hints support (mypy compatibility)

**2.5.0 (June 2025)**:

- Bug fix release; v2.0-2.0.1 had critical regression (truncated responses)
- No breaking changes from 2.0

#### Recommendation

**UPGRADE SAFELY** - Pin to `urllib3>=2.5.0,<3.0.0`

```python
# pyproject.toml change
urllib3>=2.5.0,<3.0.0
```

**Note**: Your use case (HEAD requests to S3 Vision) is well-supported. No code changes needed.

---

### 3. PyArrow 18.0.0 → 22.0.0

**Current Requirement**: `>=18.0.0`
**Latest Version**: 22.0.0 (October 24, 2025)
**Status**: Stable, mature library

#### Key Changes (18 → 22)

- Incremental improvements in Parquet I/O performance
- Enhanced DuckDB integration (columnar query results)
- Python 3.10+ requirement (you have 3.12)
- No known breaking changes for Parquet read/write

#### Recommendation

**UPGRADE SAFELY** - Pin to `pyarrow>=22.0.0,<23.0.0`

```python
# pyproject.toml change
pyarrow>=22.0.0,<23.0.0
```

**Note**: Volume rankings feature (ADR-0013) will benefit from latest Parquet optimizations.

---

### 4. pytest 8.4.0 → 9.0.1

**Current Requirement**: `>=8.4.0`
**Latest Version**: 9.0.1 (November 12, 2025)
**Status**: Stable, mature test framework

#### Key Changes (8.4 → 9.0)

- No breaking changes for existing tests
- Improved assertion introspection and error messages
- 1,300+ plugin ecosystem maintained
- Python 3.10+ support (you have 3.12)

#### Recommendation

**UPGRADE SAFELY** - Pin to `pytest>=9.0.0,<10.0.0`

```python
# pyproject.toml change (dev dependencies)
pytest>=9.0.0,<10.0.0,
```

**Testing**: Run full test suite; should pass without changes.

---

### 5. ruff 0.14.0 → 0.14.5

**Current Requirement**: `>=0.14.0`
**Latest Version**: 0.14.5 (November 13, 2025)
**Status**: Stable, actively maintained

#### Key Changes

- Incremental bug fixes and rule refinements
- 10-100x faster than traditional linters (Flake8)
- No breaking changes

#### Recommendation

**UPGRADE SAFELY** - Pin to `ruff>=0.14.5,<1.0.0`

```python
# pyproject.toml change (dev dependencies)
ruff>=0.14.5,
```

---

### 6. Playwright 1.56.0 → 1.56.0

**Current Status**: Already at latest (1.56.0, November 11, 2025)
**Status**: Current, no action needed

#### Key Points

- Supports Chromium 141, WebKit 26, Firefox 142
- Python 3.9+ support (you have 3.12)
- ~~Part of E2E testing strategy (ADR-0016)~~ (removed per ADR-0024)

#### Recommendation

**KEEP PINNED** - Maintain `playwright>=1.56.0`

```python
# pyproject.toml (no change needed, already current)
playwright>=1.56.0,
```

---

### 7. GitHub Actions Versions

#### actions/checkout: v4 → v6 (UPGRADE RECOMMENDED)

**Current**: v4 (old, released 2023)
**Latest**: v6.0.0 (November 20, 2024)
**Gap**: 2 major versions

**Breaking Change**:

- Credentials persist to separate file (requires runner v2.329.0+)
- Node.js 24 required (you use v25, compatible)

**Impact**: GitHub Actions runners are always up-to-date; no issue expected.

**Recommendation**:

```yaml
# .github/workflows/*.yml
- uses: actions/checkout@v6
  with:
    fetch-depth: 0
```

---

#### actions/setup-python: v5 → v6 (UPGRADE RECOMMENDED)

**Current**: v5 (September 2024)
**Latest**: v6.0.0 (September 4, 2024)
**Gap**: 1 major version

**Breaking Changes**:

- Upgraded to Node 24 (requires runner v2.327.1+)
- Clarified pythonLocation behavior for PyPy/GraalPy

**New Features**:

- `pip-version` input for customization
- `.python-version` file reading support
- Architecture-specific PATH management

**Recommendation**:

```yaml
# .github/workflows/*.yml
- uses: actions/setup-python@v6
  with:
    python-version: ${{ env.PYTHON_VERSION }}
    cache: "pip" # Optional: use pip caching
```

---

### 8. Node.js 25 via mise

**Current**: Pinned to Node 25 in `.mise.toml`
**Latest LTS**: Node 24, 22, 20, 18
**Status**: Node 25 is pre-LTS; will become LTS in 2026

**Consideration**: Semantic-release works with all modern Node versions.

**Recommendation**: Keep Node 25; it's more current and within the active release window. If stability is critical, could move to Node 24 LTS (but 25 is fine for CI/CD).

---

## Alternative Technologies to Consider

### 1. httpx vs. urllib3

**Current**: Using `urllib3>=2.0.0` for S3 HEAD requests

**Comparison**:

| Feature            | urllib3                    | httpx             |
| ------------------ | -------------------------- | ----------------- |
| **Sync API**       | ✅ Fast                    | ✅ Good           |
| **Async API**      | ❌ No                      | ✅ Yes            |
| **HTTP/2 Support** | ❌ No                      | ✅ Yes            |
| **Performance**    | Fastest raw                | Slower but modern |
| **Community**      | Massive (Requests uses it) | Growing           |

**Use Case in Project**: Daily S3 HEAD requests (concurrent, synchronous batch)

**Recommendation**: **KEEP urllib3** for now

- Your workload is synchronous batch requests (handled well by urllib3)
- HTTP/2 not beneficial for S3 HEAD requests
- No need to introduce new dependency

**Future**: If you add async operations (streaming, timeout handling), consider adding httpx as supplement without replacing urllib3.

---

### 2. Polars vs. DuckDB

**Current**: Using DuckDB for analytics (`daily_availability` table)

**Comparison**:

| Aspect                   | DuckDB                | Polars                 |
| ------------------------ | --------------------- | ---------------------- |
| **Use Case**             | SQL Analytics         | Data Engineering/ETL   |
| **API Style**            | SQL-first             | Python-first DataFrame |
| **Single-machine Speed** | Slightly faster (raw) | Nearly equal           |
| **Integration**          | SQL + Python          | Python + optional SQL  |
| **Storage**              | .duckdb file          | In-memory or .parquet  |

**Use Case in Project**: Daily availability table, volume rankings Parquet generation

**Recommendation**: **KEEP DuckDB** - it's the right choice

- Your data model is relational (dates × symbols)
- Query patterns are SQL-centric (snapshots, timelines)
- Parquet output (ADR-0013) integrates cleanly with DuckDB
- No DataFrame transformations needed

**Polars Would Be Better If**: You were doing complex ETL pipelines, feature engineering, or machine learning integrations.

---

### 3. Alternative Test Frameworks

**Current**: pytest (9.0.0 candidate)

**Alternatives Analyzed**:

- **unittest**: Standard library, but verbose; not recommended
- **behave**: BDD framework; overkill for unit tests
- **Robot Framework**: Non-programmer friendly; wrong fit
- **Ward**: Modern, but smaller ecosystem

**Recommendation**: **KEEP pytest** - industry standard

- 1,300+ plugins (pytest-cov, pytest-mock already used)
- Your tests are simple unit/integration style
- No reason to switch

---

## Breaking Changes Summary & Migration Risk

### High Confidence (Safe to Upgrade)

✅ **duckdb**: 1.0 → 1.4.2 (upgrade to latest LTS)

- Impact: Possible query performance changes (needs profiling)
- Code changes: None required
- Risk: Low

✅ **urllib3**: 2.0 → 2.5.0 (stay in 2.x line)

- Impact: None (already using 2.0+ features)
- Code changes: None
- Risk: Very low

✅ **pyarrow**: 18.0 → 22.0.0 (incremental releases)

- Impact: Better performance, no breaking changes
- Code changes: None
- Risk: Very low

### Medium Confidence (Safe, with Testing)

✅ **pytest**: 8.4 → 9.0 (minor version bump)

- Impact: Better error messages, no API changes
- Code changes: None required
- Risk: Very low

✅ **ruff**: 0.14.0 → 0.14.5 (patch release)

- Impact: Better linting, no behavioral changes
- Code changes: None
- Risk: None

✅ **actions/checkout**: v4 → v6 (major action bump)

- Impact: Better credential handling, Node 24 support
- Code changes: YAML only
- Risk: Very low (GitHub runners always updated)

✅ **actions/setup-python**: v5 → v6 (major action bump)

- Impact: Better Python detection, caching support
- Code changes: YAML only
- Risk: Very low

### Already Current

✅ **playwright**: 1.56.0 (latest)
✅ **semantic-release**: 25.0.2 (latest)
✅ **Node.js**: 25 (current pre-LTS)
✅ **uv**: latest (pinned in mise.toml)

---

## Recommended Upgrade Plan

### Phase 1: GitHub Actions (Lowest Risk) - Week 1

Update action versions in `.github/workflows/`:

```yaml
# update-database.yml and release.yml
- uses: actions/checkout@v6
  with:
    fetch-depth: 0

- uses: actions/setup-python@v6
  with:
    python-version: ${{ env.PYTHON_VERSION }}
```

**Testing**: Run workflow on feature branch; verify artifact upload works.

### Phase 2: Python Dependencies (Low Risk) - Week 2

Update `pyproject.toml`:

```toml
[project]
dependencies = [
    "duckdb>=1.4.0,<2.0.0",     # Up from >=1.0.0
    "urllib3>=2.5.0,<3.0.0",    # Up from >=2.0.0
    "pyarrow>=22.0.0,<23.0.0",  # Up from >=18.0.0
]

[project.optional-dependencies]
dev = [
    "pytest>=9.0.0,<10.0.0",    # Up from >=8.4.0
    "pytest-cov>=5.0.0",
    "pytest-mock>=3.14.0",
    "ruff>=0.14.5",             # Up from >=0.14.0
]
e2e = [
    "playwright>=1.56.0",
    "pytest-playwright>=0.7.0",
    "httpx>=0.28.0",
]
```

**Testing**:

1. Run unit tests: `pytest -m "not integration"`
2. Run integration tests: `pytest` (S3 connectivity check)
3. Run validation: `python scripts/operations/validate.py`
4. Measure query performance before/after (DuckDB CTE changes)

### Phase 3: Verification (Medium Effort) - Week 3

**Test Coverage**:

- [ ] Unit tests pass with new versions
- [ ] Integration tests pass (S3 connectivity)
- [ ] Database validation succeeds
- [ ] Query performance within acceptable range
- [ ] GitHub Actions workflows complete successfully

**Acceptance Criteria**:

- All tests pass
- Database validation >95% match with Binance API
- No query performance regression >10%

---

## Version Pinning Strategy

### Current (Too Loose)

```toml
duckdb>=1.0.0        # Allows any 1.x or 2.x breaking change
urllib3>=2.0.0       # Allows any 2.x or 3.x changes
```

### Recommended (Safe but Flexible)

```toml
duckdb>=1.4.0,<2.0.0         # Pin to 1.x LTS line, auto-update patches
urllib3>=2.5.0,<3.0.0        # Pin to 2.x, auto-update patches
pyarrow>=22.0.0,<23.0.0      # Pin to 22.x, auto-update patches
pytest>=9.0.0,<10.0.0        # Pin to 9.x, auto-update patches
ruff>=0.14.5                  # Allow all 0.x (Astral maintains backward compat)
```

**Rationale**:

- Major version bumps (`>=1.0.0` without upper bound) expose you to breaking changes
- Minor/patch bumps (1.4.0→1.4.2) are safe and necessary for security
- Python ecosystem convention: pin to major.minor (`>=1.4,<2.0`)

---

## Risk Assessment

### Overall Risk: LOW

| Area                   | Risk     | Mitigation                             |
| ---------------------- | -------- | -------------------------------------- |
| DuckDB API changes     | Very Low | No API changes; possible perf impact   |
| urllib3 compatibility  | Very Low | Already on 2.x; no code changes needed |
| GitHub Actions         | Very Low | GitHub handles compatibility           |
| Testing framework      | Very Low | pytest 9.0 backward-compatible         |
| Performance regression | Low      | Requires profiling, DuckDB CTE changes |

### What Could Go Wrong

1. **DuckDB CTE Materialization** (Probability: Low)
   - Impact: Slower queries on large tables
   - Mitigation: Run benchmark before/after; revert if >10% regression
   - Time to fix: 1 hour (revert to 1.0, or add CTE hints)

2. **urllib3 Edge Case** (Probability: Very Low)
   - Impact: S3 connection issue
   - Mitigation: Run integration tests with live S3
   - Time to fix: 2 hours max

3. **GitHub Actions Incompatibility** (Probability: None)
   - Impact: Workflow fails
   - Mitigation: Test on feature branch first
   - Time to fix: 30 minutes (revert YAML)

---

## Non-Recommended Changes

### ❌ Do NOT upgrade to Python 3.13 or 3.14

**Reason**: 3.12 is stable, current, and will receive bugfix support until October 2028. 3.13/3.14 are newer but less proven in production.

**Recommendation**: Stay on 3.12 for 2025; upgrade to 3.14 LTS variant in 2026 if needed.

### ❌ Do NOT replace urllib3 with httpx

**Reason**: httpx adds no value for your synchronous use case. urllib3 is faster and more proven for HEAD requests.

**Alternative**: Add httpx as optional dependency if you implement async batch operations later.

### ❌ Do NOT replace DuckDB with Polars

**Reason**: DuckDB is better for SQL-centric analytics. Polars is for data engineering pipelines.

---

## Maintenance Timeline

### Monthly (Automated via Dependabot)

- Monitor security patches for dependencies
- Accept patch version bumps automatically (semantic versioning)
- Example: urllib3 2.5.0 → 2.5.1

### Quarterly

- Review new minor versions of major dependencies
- Example: DuckDB 1.4.2 → 1.5.0 (if released)
- Test before merging

### Annually

- Evaluate major version bumps (2.0, 3.0)
- Plan migration strategy (as done in this report)
- Update documentation and architecture decisions

---

## Implementation Checklist

### Pre-Upgrade (Day 1)

- [ ] Create feature branch: `feature/technology-stack-upgrade-2025`
- [ ] Back up current database: `.cache/binance-futures/availability.duckdb`
- [ ] Document current versions in commit message

### Phase 1: GitHub Actions (Day 1-2)

- [ ] Update `actions/checkout@v6` in `.github/workflows/`
- [ ] Update `actions/setup-python@v6` in `.github/workflows/`
- [ ] Test on feature branch: `gh workflow run update-database.yml`
- [ ] Verify artifact upload and release creation

### Phase 2: Python Dependencies (Day 3-4)

- [ ] Update `pyproject.toml` with new version constraints
- [ ] Run `uv sync` to resolve new dependency graph
- [ ] Run unit tests: `pytest -m "not integration"` (should pass)
- [ ] Run integration tests: `pytest` (check S3 connectivity)
- [ ] Measure query performance:
  ```bash
  time uv run python -c "import duckdb; \
    conn = duckdb.connect('.cache/binance-futures/availability.duckdb'); \
    print(conn.execute('SELECT COUNT(*) FROM daily_availability').fetchall())"
  ```

### Phase 3: Validation & Profiling (Day 5-6)

- [ ] Run full validation suite: `uv run python scripts/operations/validate.py --verbose`
- [ ] Check cross-validation with Binance API
- [ ] Profile top 3 query patterns (snapshot, timeline, analytics)
- [ ] Document any performance changes (positive or negative)

### Phase 4: Review & Merge (Day 7)

- [ ] Create pull request with all changes
- [ ] Link to this upgrade report in PR description
- [ ] Get code review approval
- [ ] Merge to `main`
- [ ] Verify GitHub Actions release workflow succeeds

### Post-Upgrade

- [ ] Monitor first 3 scheduled runs (3 days of cron jobs)
- [ ] Check database validation %
- [ ] Check query performance in production
- [ ] Document in CHANGELOG.md

---

## Summary Table: Action Items

| Item                 | Current  | Target           | Priority | Effort | Risk     |
| -------------------- | -------- | ---------------- | -------- | ------ | -------- |
| actions/checkout     | v4       | v6               | High     | 5 min  | Very Low |
| actions/setup-python | v5       | v6               | High     | 5 min  | Very Low |
| duckdb               | >=1.0.0  | >=1.4.0,<2.0.0   | Medium   | 30 min | Low      |
| urllib3              | >=2.0.0  | >=2.5.0,<3.0.0   | Medium   | 15 min | Very Low |
| pyarrow              | >=18.0.0 | >=22.0.0,<23.0.0 | Medium   | 15 min | Very Low |
| pytest               | >=8.4.0  | >=9.0.0,<10.0.0  | Low      | 5 min  | Very Low |
| ruff                 | >=0.14.0 | >=0.14.5         | Low      | 2 min  | None     |
| playwright           | 1.56.0   | 1.56.0           | None     | -      | -        |

**Total Effort**: ~1.5 hours actual work + 2-3 hours testing
**Total Risk**: Low (all changes are backward-compatible or isolated)
**Timeline**: 1 week (distributed work)

---

## References

### Release Notes & Changelogs

- [DuckDB 1.4.0 Announcement](https://duckdb.org/2025/09/16/announcing-duckdb-140)
- [urllib3 v2 Migration Guide](https://urllib3.readthedocs.io/en/stable/v2-migration-guide.html)
- [pytest 9.0.0 Release](https://pypi.org/project/pytest/)
- [Ruff Release Notes](https://github.com/astral-sh/ruff/releases)
- [GitHub Actions Releases](https://github.com/actions/checkout/releases)

### Project Documentation

- [ADR-0002: Storage Technology - DuckDB](../../architecture/decisions/0002-storage-technology-duckdb.md)
- [ADR-0005: AWS CLI for Bulk Operations](../../architecture/decisions/0005-aws-cli-bulk-operations.md)
- [ADR-0009: GitHub Actions Automation](../../architecture/decisions/0009-github-actions-automation.md)
- [ADR-0013: Volume Rankings Timeseries](../../architecture/decisions/0013-volume-rankings-timeseries.md)
- ~~[ADR-0016: Playwright E2E Testing](../../architecture/decisions/0016-playwright-e2e-testing.md)~~ (deleted per ADR-0024)

---

## Next Steps

1. **Review this report** with the team
2. **Create feature branch** following Phase 1-4 checklist
3. **Test incrementally** starting with GitHub Actions
4. **Monitor in production** (first 3 scheduled runs)
5. **Document lessons learned** in project MADR (if creating new ADR needed)

---

**Report prepared by**: Technology Stack Analysis
**Date**: November 20, 2025
**Confidence Level**: High (all sources verified from official release notes)
