# Plan: ClickHouse E2E Test Removal

**adr-id**: 0024
**Status**: Complete
**Created**: 2025-11-25
**Updated**: 2025-11-25

---

## 1. Context

### 1.1 Problem Statement

The binance-futures-availability project contains ClickHouse E2E tests that are not relevant to the production DuckDB-based system. These tests:

- Target a local Docker ClickHouse instance (not production)
- Add unnecessary dependencies (playwright, httpx)
- Create confusion about the project's storage architecture

Additionally, the CI/CD pipeline is blocked by a ruff linting error since 2025-11-25 03:47 UTC.

### 1.2 Current State

| Component            | Status  | Issue                               |
| -------------------- | ------- | ----------------------------------- |
| DuckDB Regime        | HEALTHY | No issues                           |
| CI/CD Pipeline       | BLOCKED | Ruff SIM118 error in backfill.py:67 |
| ClickHouse Artifacts | UNUSED  | 14+ files in tests/e2e/             |

### 1.3 Goals

1. Restore CI/CD pipeline functionality
2. Remove all ClickHouse-related artifacts
3. Update documentation to reflect changes
4. Verify Doppler token synchronization

---

## 2. Plan

### Phase 1: Fix CI/CD (Critical)

**Task 1.1**: Fix ruff SIM118 linting error

- File: `scripts/operations/backfill.py` line 67
- Change: `for date in availability.keys():` → `for date in availability:`

**Task 1.2**: Verify Doppler token sync

- Check GH_TOKEN_TERRYLICA exists in Doppler
- Trigger manual sync if needed
- Verify with `gh api user`

### Phase 2: Remove ClickHouse Artifacts

**Task 2.1**: Delete tests/e2e/ directory

```
tests/e2e/
├── test_clickhouse_http.py (251 lines)
├── test_clickhouse_ui.py (308 lines)
├── README.md
├── DIAGNOSTIC_REPORT.md
├── TEST_RESULTS.md
├── conftest.py
├── pytest.ini
├── screenshots/ (5 PNG files)
├── __pycache__/
└── tests/
```

**Task 2.2**: Delete ADR-0016

- File: `docs/architecture/decisions/0016-playwright-e2e-testing.md`

**Task 2.3**: Remove [e2e] dependencies from pyproject.toml

```toml
# Remove lines 24-28
e2e = [
    "playwright>=1.56.0",
    "pytest-playwright>=0.7.0",
    "httpx>=0.28.0",
]
```

### Phase 3: Update Documentation

**Task 3.1**: Update CLAUDE.md

- Remove ADR-0016 reference from ADR list

**Task 3.2**: Update CI_CD_AUDIT_REPORT.md

- Remove ClickHouse E2E test references
- Add note about removal date and reason

### Phase 4: Verify & Commit

**Task 4.1**: Run local validation

- `ruff check scripts/`
- `pytest -m "not integration"`

**Task 4.2**: Commit and push

- Commit message following conventional commits
- Verify CI/CD passes

---

## 3. Task List

| #   | Task                                  | Status   | Notes                          |
| --- | ------------------------------------- | -------- | ------------------------------ |
| 1   | Create ADR-0024 and plan              | COMPLETE |                                |
| 2   | Fix ruff SIM118 error                 | COMPLETE | backfill.py:67                 |
| 3   | Verify Doppler token sync             | COMPLETE | Token valid, synced 18:54 UTC  |
| 4   | Delete tests/e2e/ directory           | COMPLETE | 14+ files removed              |
| 5   | Delete ADR-0016                       | COMPLETE |                                |
| 6   | Remove [e2e] deps from pyproject.toml | COMPLETE | Also removed ui marker         |
| 7   | Update CLAUDE.md                      | COMPLETE | No references found            |
| 8   | Update CI_CD_AUDIT_REPORT.md          | COMPLETE | Updated testing status         |
| 9   | Fix schema drift (ADR-0007 migration) | COMPLETE | Added volume columns migration |
| 10  | Commit and verify CI/CD               | COMPLETE | Run 19682724421 succeeded      |

---

## 4. Progress Log

### 2025-11-25

- **08:30 UTC**: Investigation completed - found CI/CD blocked by ruff error
- **08:45 UTC**: Plan created, ADR-0024 written
- **08:50 UTC**: Beginning implementation
- **19:00 UTC**: All cleanup tasks complete, committing changes
- **20:05 UTC**: First workflow run failed - schema drift issue discovered
- **20:10 UTC**: Added ADR-0007 volume columns migration to schema.py
- **20:14 UTC**: Workflow run 19682724421 succeeded - all tasks complete

---

## 5. Success Criteria

- [x] CI/CD pipeline passes (ruff check, pytest)
- [x] No ClickHouse references in tests/
- [x] ADR-0016 deleted
- [x] pyproject.toml has no [e2e] group
- [x] CLAUDE.md updated (no references found)
- [x] GitHub Actions workflow succeeds (run 19682724421)
