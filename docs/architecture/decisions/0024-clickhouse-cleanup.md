# ADR-0024: ClickHouse E2E Test Removal

**Status**: Accepted

**Date**: 2025-11-25

**Context**:

The binance-futures-availability project uses DuckDB for local columnar storage (ADR-0002). During exploratory development, ClickHouse E2E tests were added to validate a local Docker ClickHouse instance (ADR-0016). These tests:

1. Target localhost:8123 (HTTP API) and localhost:5521 (Web UI)
2. Require Playwright browser automation and httpx dependencies
3. Are not connected to the production DuckDB-based data pipeline
4. Created confusion about the project's storage technology

The CI/CD pipeline is currently blocked by an unrelated ruff linting error, providing an opportunity to clean up these unused artifacts.

**Decision**:

Remove all ClickHouse-related E2E tests and artifacts:

1. **Delete `tests/e2e/` directory** - Contains ClickHouse-specific tests, Playwright configuration, screenshots, and documentation
2. **Delete ADR-0016** - The Playwright E2E testing decision is being reversed
3. **Remove `[e2e]` optional dependencies** - playwright, pytest-playwright, httpx are no longer needed
4. **Update documentation** - Remove ADR-0016 references from CLAUDE.md and update CI_CD_AUDIT_REPORT.md

**Consequences**:

**Positive**:
- Cleaner codebase focused on DuckDB storage
- Reduced dependency footprint (3 fewer optional packages)
- No confusion about storage technology choices
- Faster CI/CD (no unused test infrastructure)

**Negative**:
- Loss of Playwright E2E testing framework (can be recreated if needed)
- Historical test results deleted (documented in this ADR for reference)

**Related Decisions**:
- ADR-0002: Storage Technology - DuckDB (remains in effect)
- ADR-0016: Playwright E2E Testing (SUPERSEDED by this ADR)

**Artifacts Removed**:
- `tests/e2e/` (14+ files including test_clickhouse_http.py, test_clickhouse_ui.py)
- `docs/architecture/decisions/0016-playwright-e2e-testing.md`
- `[e2e]` group in pyproject.toml
