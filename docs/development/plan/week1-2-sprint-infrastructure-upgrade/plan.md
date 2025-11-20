# Week 1-2 Sprint: Infrastructure Upgrade Implementation Plan

**adr-id**: 0018, 0019, 0020, 0021 (consolidated sprint plan)
**Date**: 2025-11-20
**Status**: In Progress
**Owner**: System Architect
**Estimated Effort**: 16-18 hours

## Context

This plan implements four infrastructure improvements discovered through comprehensive research (6 sub-agents, 450KB analysis, 29 documents):

1. **Technology Stack Upgrade** (ADR-0018): DuckDB 1.4, urllib3 2.5, pyarrow 22, pytest 9, GitHub Actions v6
2. **Performance Optimization** (ADR-0019): HTTP pooling, DNS caching, compression, materialized views
3. **CI/CD Maturity** (ADR-0020): Test gates, Dependabot, linting, coverage thresholds
4. **Observability Phase 0** (ADR-0021): Schema drift detection, correlation IDs, data catalog

**Research Base**: `docs/research/2025-week1-sprint/` (8 files, 189KB)

**Expected Outcomes**:

- Performance: 9-15% faster (1.48s → 1.35s daily updates)
- Storage: 60% reduction (50-150MB → 20-50MB)
- CI/CD Maturity: 7.1 → 7.8 (+10%)
- Debugging: 3x faster (>30min → <10min)
- Cost: $0 (all infrastructure-free)

## Goals

### Primary Goals

- ✅ Upgrade all dependencies to latest stable versions with zero breaking changes
- ✅ Implement 4 proven performance optimizations (HTTP pooling, DNS, compression, materialized views)
- ✅ Add critical CI/CD gates (tests before publish, Dependabot, linting)
- ✅ Establish observability foundation (schema drift, correlation IDs, catalog)

### Success Metrics

- All tests pass (pytest)
- Database validation >95% API match
- Performance: 1.48s → 1.35s daily updates
- Storage: 50-150MB → 20-50MB database
- CI/CD maturity: 7.1 → 7.8
- Debugging time: >30min → <10min
- Zero data loss or corruption

### Non-Goals

- Feature expansion (funding rates, OI) → Deferred to future sprint
- Grafana Cloud SLO tracking → Deferred to Q1 2026
- Soda Core / Great Expectations → Deferred to Q2 2026
- E2E tests in CI → Deferred to Phase 2

## Plan

### Phase 1: Documentation (COMPLETED)

**Status**: ✅ Complete
**Artifacts**:

- ADR-0018: Technology Stack Upgrade 2025
- ADR-0019: Performance Optimization Strategy
- ADR-0020: CI/CD Maturity Improvements
- ADR-0021: Observability Phase 0 Foundation
- Research files copied to `docs/research/2025-week1-sprint/`
- This plan document created

### Phase 2: Technology Stack Upgrade (3.5 hours)

**Files to Modify**:

1. `pyproject.toml` - Update dependency versions with upper bounds
2. `.github/workflows/update-database.yml` - GitHub Actions v4→v6
3. `.github/workflows/release.yml` - GitHub Actions v5→v6

**Implementation**:

```toml
# pyproject.toml
[project]
dependencies = [
    "duckdb>=1.4.0,<2.0.0",       # Up from >=1.0.0
    "urllib3>=2.5.0,<3.0.0",      # Up from >=2.0.0
    "pyarrow>=22.0.0,<23.0.0",    # Up from >=18.0.0
]

[project.optional-dependencies]
dev = [
    "pytest>=9.0.0,<10.0.0",      # Up from >=8.4.0
    "ruff>=0.14.5",                # Up from >=0.14.0
]
```

**Validation**:

```bash
uv sync
pytest -m "not integration"
pytest
python scripts/operations/validate.py
```

### Phase 3: Performance Optimization (2 hours)

**Files to Create/Modify**:

1. `src/binance_futures_availability/probing/s3_vision.py` - HTTP pooling
2. `src/binance_futures_availability/probing/batch_prober.py` - DNS caching
3. `src/binance_futures_availability/database/schema.py` - Compression
4. `src/binance_futures_availability/database/availability_db.py` - Materialized views

**Implementation**:

- HTTP Connection Pooling: urllib → urllib3.PoolManager (15 min)
- DNS Cache Warming: socket.gethostbyname() (5 min)
- Column Compression: USING COMPRESSION dict/bitpacking (10 min)
- Materialized Views: daily_symbol_counts table (30 min)

**Validation**:

```bash
# Benchmark before/after
time uv run python scripts/operations/update_daily.py
# Check database size reduction
ls -lh ~/.cache/binance-futures/availability.duckdb
```

### Phase 4: CI/CD Quick Wins (3-4 hours)

**Files to Create/Modify**:

1. `.github/workflows/update-database.yml` - Move tests earlier, add ruff
2. `.github/dependabot.yml` - NEW FILE
3. `.pre-commit-config.yaml` - NEW FILE
4. `pyproject.toml` - Add `--cov-fail-under=80`
5. `README.md` - Add workflow badges
6. DELETE: `.github/workflows/update-database-simple.yml`

**Implementation**:

- Move test execution before database publish (30 min)
- Create Dependabot config for pip + npm (30 min)
- Add ruff linting step to CI (15 min)
- Add coverage threshold enforcement (5 min)
- Remove unused workflow (5 min)
- Add workflow badges (15 min)
- Create pre-commit config (optional, 30 min)

**Validation**:

```bash
# Trigger workflow to verify test gates
gh workflow run update-database.yml --ref $(git branch --show-current)
# Verify Dependabot created
gh api repos/terrylica/binance-futures-availability/dependabot/secrets
```

### Phase 5: Observability Phase 0 (8 hours)

**Files to Create**:

1. `src/binance_futures_availability/validation/schema_drift.py` - NEW MODULE
2. `docs/schema/DATA_CATALOG.md` - NEW DOCUMENTATION
3. `tests/test_validation/test_schema_drift.py` - NEW TESTS

**Files to Modify**:

1. `src/binance_futures_availability/probing/batch_prober.py` - Correlation IDs
2. `scripts/operations/validate.py` - Add schema drift check
3. `docs/operations/MONITORING.md` - Update with new checks

**Implementation** (from phase-0-implementation-checklist.md):

- Schema drift detection module (2 hours)
- Batch correlation ID logging (2 hours)
- Data catalog documentation (4 hours)
- Integration with validation suite (30 min)
- Unit tests for schema drift (1.5 hours)

**Validation**:

```bash
# Test schema drift detection
pytest tests/test_validation/test_schema_drift.py
# Verify correlation IDs in logs
uv run python scripts/operations/update_daily.py 2>&1 | grep "batch_id"
```

### Phase 6: Final Validation & Release (1 hour)

**Tasks**:

1. Run full test suite (pytest)
2. Run database validation (scripts/operations/validate.py)
3. Benchmark performance improvements
4. Verify storage reduction
5. Create conventional commit
6. Use semantic-release to create release
7. Verify PyPI publish (pypi-doppler skill)
8. Create execution log

**Validation Commands**:

```bash
# Full test suite
pytest --cov --cov-report=term

# Database validation
python scripts/operations/validate.py

# Performance benchmark
time uv run python scripts/operations/update_daily.py

# Storage check
ls -lh ~/.cache/binance-futures/availability.duckdb

# Create release
git add -A
git commit -m "feat: comprehensive infrastructure upgrade (ADR-0018 to ADR-0021)

- Upgrade dependencies: DuckDB 1.4, urllib3 2.5, pyarrow 22, pytest 9
- Performance: HTTP pooling, DNS caching, compression, materialized views
- CI/CD: Test gates, Dependabot, linting, coverage thresholds
- Observability: Schema drift detection, correlation IDs, data catalog

BREAKING CHANGE: None (all changes backward-compatible)

Performance improvement: 9-15% faster (1.48s → 1.35s)
Storage reduction: 60% (50-150MB → 20-50MB)
CI/CD maturity: 7.1 → 7.8
Debugging: 3x faster (>30min → <10min)

ADR-0018, ADR-0019, ADR-0020, ADR-0021"

# semantic-release handles version bump, changelog, tag, publish
npx semantic-release
```

## Task List

### Phase 1: Documentation ✅

- [x] Create ADR-0018 (Technology Stack Upgrade)
- [x] Create ADR-0019 (Performance Optimization)
- [x] Create ADR-0020 (CI/CD Maturity)
- [x] Create ADR-0021 (Observability Phase 0)
- [x] Copy research files to docs/research/
- [x] Create this plan document

### Phase 2: Technology Stack Upgrade

- [ ] Update pyproject.toml dependencies
- [ ] Update GitHub Actions workflows (v4→v6, v5→v6)
- [ ] Run uv sync and verify dependency resolution
- [ ] Run pytest and verify all tests pass
- [ ] Run validation suite

### Phase 3: Performance Optimization

- [ ] Add HTTP connection pooling (s3_vision.py)
- [ ] Add DNS cache warming (batch_prober.py)
- [ ] Add column compression (schema.py)
- [ ] Add materialized views (availability_db.py)
- [ ] Benchmark performance before/after
- [ ] Verify storage reduction

### Phase 4: CI/CD Quick Wins

- [ ] Move tests before database publish (update-database.yml)
- [ ] Add ruff linting to CI
- [ ] Create .github/dependabot.yml
- [ ] Add coverage threshold to pyproject.toml
- [ ] Delete update-database-simple.yml
- [ ] Add workflow badges to README.md
- [ ] (Optional) Create .pre-commit-config.yaml
- [ ] Verify test gates work (trigger workflow)

### Phase 5: Observability Phase 0

- [ ] Create schema_drift.py module
- [ ] Add batch correlation IDs to batch_prober.py
- [ ] Create DATA_CATALOG.md documentation
- [ ] Update validate.py with schema drift check
- [ ] Update MONITORING.md with new checks
- [ ] Write unit tests for schema drift
- [ ] Verify correlation IDs in logs

### Phase 6: Final Validation & Release

- [ ] Run full test suite with coverage
- [ ] Run database validation suite
- [ ] Benchmark performance improvements
- [ ] Verify storage reduction
- [ ] Create conventional commit
- [ ] Run semantic-release
- [ ] Verify PyPI publish
- [ ] Create execution log in logs/

## Risks & Mitigation

| Risk                            | Severity | Mitigation                                      |
| ------------------------------- | -------- | ----------------------------------------------- |
| Dependency resolution conflicts | Low      | All upgrades validated as backward-compatible   |
| Test failures                   | Low      | Run after each phase, fix immediately           |
| Performance regression          | Very Low | Benchmark before/after, rollback if >10% slower |
| CI/CD workflow breakage         | Low      | Test on feature branch first                    |
| Schema drift false positives    | Low      | Test with current schema first                  |

## Rollback Plan

If any phase fails:

1. Git revert changes from that phase
2. Re-run tests to verify rollback successful
3. Document failure in execution log
4. Resume from previous successful phase

All changes are in version control, full rollback available.

## Links

- **ADRs**: `docs/architecture/decisions/0018-*.md` through `0021-*.md`
- **Research**: `docs/research/2025-week1-sprint/` (189KB, 8 files)
- **Related Plans**: None (this is the consolidated sprint plan)

## Notes

This is a consolidated plan covering 4 ADRs as a single sprint. Each phase can be completed independently and validated before proceeding. Total estimated effort: 16-18 hours over 1-2 weeks.
