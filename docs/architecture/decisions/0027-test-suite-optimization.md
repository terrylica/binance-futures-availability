# ADR-0027: Test Suite Optimization

**Status**: Accepted

**Date**: 2025-11-25

**Context**:

Comprehensive test audit of 13 test files (2432 lines) identified optimization opportunities:

| Category | Count | Lines | Impact |
| -------- | ----- | ----- | ------ |
| Redundant Unicode tests | 3 locations | ~85 | Maintenance burden |
| Redundant UPSERT tests | 3 locations | ~130 | Conceptual confusion |
| Excessive parsing tests | 6 tests | ~50 | Low-value coverage |
| Missing CLI tests | 0 tests | 0 | Coverage gap |
| Missing edge cases | 0 tests | 0 | Coverage gap |

Key issues:

1. **Unicode symbol tests** duplicated in `test_unicode_symbols.py`, `test_gap_detection.py`, and `test_targeted_backfill.py`
2. **UPSERT behavior tests** duplicated in `test_availability_db.py`, `test_20day_lookback.py`, and `test_targeted_backfill.py`
3. **CLI module** has zero test coverage
4. **Schema indexes** not verified in tests

**Decision**:

Optimize test suite through pruning redundancy and growing coverage gaps:

**Prune** (remove ~215 lines):

1. Delete `TestUnicodeSymbolHandling` from `test_gap_detection.py`
2. Delete `TestUnicodeSymbolTargetedBackfill` from `test_targeted_backfill.py`
3. Delete `TestUpsertBehavior` from `test_20day_lookback.py`
4. Delete `TestUpsertIdempotency` from `test_targeted_backfill.py`
5. Consolidate `TestSymbolParsing` to 2 representative tests

**Grow** (add ~100 lines):

1. Add CLI smoke tests (`test_cli/test_commands.py`)
2. Add schema index verification test
3. Add continuity edge case tests
4. Add snapshot empty database test

**Consequences**:

**Positive**:

- Reduced maintenance burden (single source of truth for each concept)
- Clear test ownership (Unicode in probing, UPSERT in database)
- Increased coverage for previously untested modules (CLI)
- Faster test execution (fewer redundant tests)

**Negative**:

- One-time refactoring effort
- May expose latent bugs in CLI module

**Related Decisions**:

- ADR-0003: Error handling - strict policy (informs test assertions)
- ADR-0007: Volume metrics (tested in rankings generation)
- ADR-0011: 20-day lookback (retains date range tests)
- ADR-0012: Auto-backfill (retains gap detection tests)

**SLO Compliance**:

- **Availability**: Tests run reliably without flaky redundancy
- **Correctness**: Single source of truth prevents divergent test behavior
- **Observability**: Clear test file ownership per module
- **Maintainability**: Reduced lines, higher signal-to-noise ratio
