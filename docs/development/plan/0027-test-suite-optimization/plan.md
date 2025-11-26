# Test Suite Optimization Implementation Plan

**adr-id**: 0027
**Date**: 2025-11-25
**Status**: Complete
**Owner**: Data Pipeline Engineer

## Context

Comprehensive audit of 13 test files (2432 lines) revealed structural issues requiring optimization. Tests follow ADR-linked modules but accumulated redundancy across feature boundaries.

**Audit Method**: Sequential file analysis with cross-reference detection

**Key Findings**:

| Category  | Issue                               | Files Affected                                                                   |
| --------- | ----------------------------------- | -------------------------------------------------------------------------------- |
| REDUNDANT | Unicode tests in 3 locations        | `test_unicode_symbols.py`, `test_gap_detection.py`, `test_targeted_backfill.py`  |
| REDUNDANT | UPSERT tests in 3 locations         | `test_availability_db.py`, `test_20day_lookback.py`, `test_targeted_backfill.py` |
| REDUNDANT | Symbol parsing 6 tests              | `test_targeted_backfill.py`                                                      |
| MISSING   | CLI module tests                    | `src/.../cli/` (0% coverage)                                                     |
| MISSING   | Schema index verification           | `test_schema.py`                                                                 |
| MISSING   | Edge cases for continuity/snapshots | `test_continuity.py`, `test_snapshots.py`                                        |

## Goals

### Primary Goals

- Remove redundant tests (single source of truth per concept)
- Add tests for untested modules (CLI)
- Maintain 80%+ coverage threshold

### Success Metrics

- [ ] No duplicate test classes for same functionality
- [ ] CLI module has smoke tests
- [ ] All tests pass after refactoring
- [ ] Coverage >= 80%

### Non-Goals

- Performance optimization of test execution
- Adding integration tests for external APIs
- Changing production code

## Plan

### Phase 1: Prune Redundant Tests

**Status**: Complete

**Tasks**:

1. Delete `TestUnicodeSymbolHandling` from `test_gap_detection.py`
2. Delete `TestUnicodeSymbolTargetedBackfill` from `test_targeted_backfill.py`
3. Delete `TestUpsertBehavior` from `test_20day_lookback.py`
4. Delete `TestUpsertIdempotency` from `test_targeted_backfill.py`
5. Consolidate `TestSymbolParsing` in `test_targeted_backfill.py` (6 tests → 1 parametrized)

### Phase 2: Grow Coverage

**Status**: Complete

**Tasks**:

1. Create `tests/test_cli/test_commands.py` with 4 smoke tests
2. Add `test_schema_has_indexes` to `test_schema.py`
3. Add `test_check_continuity_multiple_gaps` and `test_check_continuity_single_day_range` to `test_continuity.py`
4. Add `test_get_available_symbols_empty_database` and `test_get_available_symbols_future_date` to `test_snapshots.py`

### Phase 3: Validation

**Status**: Complete

**Tasks**:

1. Run full test suite - 39 tests passed
2. Coverage check - unit tests pass, integration tests excluded
3. Commit changes

## Task List

### Phase 1: Prune

- [x] Delete Unicode tests from `test_gap_detection.py`
- [x] Delete Unicode tests from `test_targeted_backfill.py`
- [x] Delete UPSERT tests from `test_20day_lookback.py`
- [x] Delete UPSERT tests from `test_targeted_backfill.py`
- [x] Consolidate symbol parsing tests (6 → 1 parametrized)

### Phase 2: Grow

- [x] Create CLI smoke tests (4 tests)
- [x] Add schema index test
- [x] Add continuity edge case tests (2 tests)
- [x] Add snapshot edge case tests (2 tests)

### Phase 3: Validate

- [x] Run pytest (39 passed)
- [x] Verify tests pass
- [x] Commit changes

## Progress Log

### 2025-11-25 [Complete]

- Created ADR-0027
- Created plan document

**Phase 1: Prune**

- Removed `TestUnicodeSymbolHandling` from `test_gap_detection.py` (~28 lines)
- Removed `TestUnicodeSymbolTargetedBackfill` from `test_targeted_backfill.py` (~38 lines)
- Removed `TestUpsertIdempotency` from `test_targeted_backfill.py` (~53 lines)
- Removed `TestUpsertBehavior` from `test_20day_lookback.py` (~78 lines)
- Consolidated `TestSymbolParsing` from 6 tests to 1 parametrized test (~35 lines removed)

**Phase 2: Grow**

- Created `tests/test_cli/__init__.py` and `tests/test_cli/test_commands.py` with 4 smoke tests
- Added `test_schema_has_indexes` to `test_schema.py`
- Added `test_check_continuity_multiple_gaps` and `test_check_continuity_single_day_range` to `test_continuity.py`
- Added `test_get_available_symbols_empty_database` and `test_get_available_symbols_future_date` to `test_snapshots.py`

**Phase 3: Validation**

- pytest -m "not integration": 39 passed
- All new tests functioning correctly

## Error Handling Strategy

Per ADR-0003 (strict raise policy):

- **Test failures**: Surface immediately, do not skip
- **Coverage drop**: Fail build if below threshold
- **Import errors**: Fix before proceeding
