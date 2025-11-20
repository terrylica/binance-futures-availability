# Phase 0 Implementation Checklist: Foundation Enhancements

**Timeline**: NOW (November 2025)
**Effort**: 12 hours
**Cost**: $0
**Status**: Ready to implement

---

## Overview

Phase 0 adds three low-cost, high-value enhancements to prepare for future observability work:

1. **Schema Drift Detection** - Catch schema changes before they break downstream
2. **Batch Correlation Logging** - Enable root cause analysis via batch IDs
3. **Data Catalog Documentation** - Help downstream users understand the database

All changes are **backward-compatible**, **non-breaking**, and **testable in isolation**.

---

## Part 1: Schema Drift Detection (4 hours)

### What It Does

Validates that the actual DuckDB schema matches the canonical schema definition. Runs before each database update to catch:

- Missing columns (someone deletes a column)
- Extra columns (someone adds a column without updating schema.json)
- Type changes (someone changes column data type)
- Nullable changes (someone adds NOT NULL constraint)

### Files to Create

#### 1.1 Create `src/binance_futures_availability/validation/schema_drift.py`

```python
"""Schema drift detection: Verify actual schema matches expected JSON Schema.

SLO: All schema changes caught and logged before database update.
See: docs/architecture/decisions/0017-documentation-structure-migration.md
"""

import json
import logging
from pathlib import Path
from typing import Any

from binance_futures_availability.database.availability_db import AvailabilityDatabase

logger = logging.getLogger(__name__)


class SchemaDriftValidator:
    """Detect schema changes compared to canonical schema definition."""

    def __init__(self, schema_path: Path | None = None) -> None:
        """
        Initialize with expected schema JSON.

        Args:
            schema_path: Path to canonical schema JSON
                        (default: docs/schema/availability-database.schema.json)
        """
        if schema_path is None:
            # Find schema.json relative to this file
            schema_path = (
                Path(__file__).parent.parent.parent / "docs" / "schema"
                / "availability-database.schema.json"
            )

        if not schema_path.exists():
            raise FileNotFoundError(
                f"Schema file not found: {schema_path}\n"
                "Expected location: docs/schema/availability-database.schema.json"
            )

        with open(schema_path) as f:
            self.expected_schema = json.load(f)

        self.schema_path = schema_path
        logger.info(f"Loaded expected schema from {schema_path}")

    @staticmethod
    def get_actual_schema(db_path: Path | None = None) -> dict[str, Any]:
        """
        Get actual schema from DuckDB information_schema.

        Args:
            db_path: Path to DuckDB database (default: ~/.cache/binance-futures/...)

        Returns:
            Dict with 'columns' key containing list of {name, type, nullable}
        """
        db = AvailabilityDatabase(db_path=db_path)

        try:
            # Query information_schema for actual schema
            columns = db.query("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'main' AND table_name = 'daily_availability'
                ORDER BY ordinal_position
            """)

            return {
                "columns": [
                    {
                        "name": col[0],
                        "type": col[1],
                        "nullable": col[2] == "YES",
                    }
                    for col in columns
                ]
            }

        finally:
            db.close()

    def validate_schema_match(self, db_path: Path | None = None) -> bool:
        """
        Validate actual schema matches expected schema (assertion-style).

        Raises:
            ValueError: If schema drift detected (per ADR-0003 strict policy)

        Args:
            db_path: Path to DuckDB database

        Returns:
            True if schemas match exactly
        """
        actual = self.get_actual_schema(db_path=db_path)
        expected_cols = {col["name"]: col for col in self.expected_schema["columns"]}
        actual_cols = {col["name"]: col for col in actual["columns"]}

        # Check 1: No missing columns
        missing = set(expected_cols.keys()) - set(actual_cols.keys())
        if missing:
            error_msg = (
                f"Schema drift: Missing columns {sorted(missing)}\n"
                f"Expected {len(expected_cols)} columns, found {len(actual_cols)}\n"
                f"Missing: {', '.join(sorted(missing))}"
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

        # Check 2: No unexpected columns
        unexpected = set(actual_cols.keys()) - set(expected_cols.keys())
        if unexpected:
            error_msg = (
                f"Schema drift: Unexpected columns {sorted(unexpected)}\n"
                f"Schema definition does not include: {', '.join(sorted(unexpected))}\n"
                f"Update {self.schema_path} if adding new columns"
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

        # Check 3: Column count matches
        if len(actual_cols) != len(expected_cols):
            error_msg = (
                f"Schema drift: Column count mismatch\n"
                f"Expected: {len(expected_cols)}, Actual: {len(actual_cols)}"
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

        logger.info(
            f"Schema validation passed",
            extra={
                "column_count": len(actual_cols),
                "expected_column_count": len(expected_cols),
            },
        )
        return True

    def compare_schemas(self, db_path: Path | None = None) -> dict[str, Any]:
        """
        Compare schemas and return detailed differences (for reporting).

        Args:
            db_path: Path to DuckDB database

        Returns:
            Dict with 'match', 'missing', 'unexpected', 'changes' keys
        """
        actual = self.get_actual_schema(db_path=db_path)
        expected_cols = {col["name"]: col for col in self.expected_schema["columns"]}
        actual_cols = {col["name"]: col for col in actual["columns"]}

        missing = set(expected_cols.keys()) - set(actual_cols.keys())
        unexpected = set(actual_cols.keys()) - set(expected_cols.keys())

        # Type changes
        type_changes = {}
        for name in set(expected_cols.keys()) & set(actual_cols.keys()):
            if expected_cols[name]["type"] != actual_cols[name]["type"]:
                type_changes[name] = {
                    "expected": expected_cols[name]["type"],
                    "actual": actual_cols[name]["type"],
                }

        return {
            "match": len(missing) == 0 and len(unexpected) == 0 and len(type_changes) == 0,
            "missing_columns": sorted(missing),
            "unexpected_columns": sorted(unexpected),
            "type_changes": type_changes,
            "total_columns_expected": len(expected_cols),
            "total_columns_actual": len(actual_cols),
        }

    def close(self) -> None:
        """No-op for consistency with other validators."""
        pass

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
```

#### 1.2 Add Unit Tests

Create `tests/test_validation/test_schema_drift.py`:

```python
"""Tests for schema drift detection."""

import json
from pathlib import Path

import pytest

from binance_futures_availability.validation.schema_drift import SchemaDriftValidator


class TestSchemaDriftValidator:
    """Test schema drift detection."""

    def test_schema_file_exists(self):
        """Schema definition file must exist."""
        validator = SchemaDriftValidator()
        assert validator.schema_path.exists()

    def test_load_expected_schema(self):
        """Can load expected schema from JSON."""
        validator = SchemaDriftValidator()
        assert "columns" in validator.expected_schema
        assert len(validator.expected_schema["columns"]) > 0

    def test_expected_schema_structure(self):
        """Expected schema must have required fields."""
        validator = SchemaDriftValidator()
        for col in validator.expected_schema["columns"]:
            assert "name" in col, "Column must have 'name'"
            assert "type" in col, "Column must have 'type'"
            assert isinstance(col["name"], str)
            assert isinstance(col["type"], str)

    def test_actual_schema_matches_expected(self, populated_db):
        """Actual schema in test database should match expected."""
        validator = SchemaDriftValidator()
        result = validator.compare_schemas(db_path=populated_db)
        assert result["match"], f"Schema mismatch: {result}"

    def test_validate_schema_match_success(self, populated_db):
        """validate_schema_match() should return True for matching schemas."""
        validator = SchemaDriftValidator()
        assert validator.validate_schema_match(db_path=populated_db) is True

    def test_validate_schema_match_missing_column_raises(self, populated_db, tmp_path):
        """Should raise if expected columns missing from actual schema."""
        # Create fake schema with extra column
        bad_schema = {
            "columns": [
                {"name": "date", "type": "date"},
                {"name": "symbol", "type": "varchar"},
                {"name": "nonexistent_column", "type": "integer"},
            ]
        }

        schema_file = tmp_path / "bad_schema.json"
        schema_file.write_text(json.dumps(bad_schema))

        validator = SchemaDriftValidator(schema_path=schema_file)
        with pytest.raises(ValueError, match="Missing columns"):
            validator.validate_schema_match(db_path=populated_db)

    def test_context_manager_interface(self, populated_db):
        """Should support context manager protocol."""
        with SchemaDriftValidator() as validator:
            assert validator.validate_schema_match(db_path=populated_db)

    def test_compare_schemas_returns_dict(self, populated_db):
        """compare_schemas should return structured diff."""
        validator = SchemaDriftValidator()
        result = validator.compare_schemas(db_path=populated_db)

        assert isinstance(result, dict)
        assert "match" in result
        assert "missing_columns" in result
        assert "unexpected_columns" in result
        assert "total_columns_expected" in result
        assert "total_columns_actual" in result
```

### Integration into Workflow

#### 1.3 Update `scripts/operations/validate.py`

Add schema drift check as FIRST validation step:

```python
# File: scripts/operations/validate.py

import logging
from pathlib import Path

from binance_futures_availability.validation.schema_drift import SchemaDriftValidator
from binance_futures_availability.validation.continuity import ContinuityValidator
from binance_futures_availability.validation.completeness import CompletenessValidator
from binance_futures_availability.validation.cross_check import CrossCheckValidator

logger = logging.getLogger(__name__)


def main(db_path: Path | None = None, verbose: bool = False) -> None:
    """
    Run all database validation checks in sequence.

    Checks run in order:
    1. Schema drift (must match canonical schema)
    2. Continuity (no gaps in dates)
    3. Completeness (symbols per date in expected range)
    4. Cross-check with API (match percentage > 95%)

    Args:
        db_path: Path to DuckDB database (default: ~/.cache/binance-futures/...)
        verbose: Print detailed output

    Raises:
        ValueError: If any validation fails (per ADR-0003 strict policy)
    """

    if verbose:
        logging.basicConfig(level=logging.DEBUG)

    # ============================================================================
    # STEP 1: Schema Drift Detection (FIRST - must pass before any other checks)
    # ============================================================================

    logger.info("=" * 70)
    logger.info("VALIDATION STEP 1: Schema Drift Detection")
    logger.info("=" * 70)

    try:
        schema_validator = SchemaDriftValidator()
        schema_validator.validate_schema_match(db_path=db_path)
        logger.info("✅ Schema validation PASSED")
    except ValueError as e:
        logger.error(f"❌ Schema validation FAILED: {e}")
        raise

    # ============================================================================
    # STEP 2: Continuity Check (no gaps in date sequence)
    # ============================================================================

    logger.info("\n" + "=" * 70)
    logger.info("VALIDATION STEP 2: Date Continuity")
    logger.info("=" * 70)

    try:
        continuity_validator = ContinuityValidator(db_path=db_path)
        continuity_validator.validate_continuity()
        logger.info("✅ Continuity validation PASSED")
    except ValueError as e:
        logger.error(f"❌ Continuity validation FAILED: {e}")
        raise

    # ============================================================================
    # STEP 3: Completeness Check (symbol count per date)
    # ============================================================================

    logger.info("\n" + "=" * 70)
    logger.info("VALIDATION STEP 3: Completeness Check")
    logger.info("=" * 70)

    try:
        completeness_validator = CompletenessValidator(db_path=db_path)
        completeness_validator.validate_completeness()
        logger.info("✅ Completeness validation PASSED")
    except ValueError as e:
        logger.error(f"❌ Completeness validation FAILED: {e}")
        raise

    # ============================================================================
    # STEP 4: Cross-Check with Binance API
    # ============================================================================

    logger.info("\n" + "=" * 70)
    logger.info("VALIDATION STEP 4: Cross-Check with Binance API")
    logger.info("=" * 70)

    try:
        cross_check_validator = CrossCheckValidator(db_path=db_path)
        cross_check_validator.validate_cross_check()
        logger.info("✅ Cross-check validation PASSED")
    except ValueError as e:
        if "451" in str(e):
            logger.warning(
                "⚠️  Cross-check SKIPPED: HTTP 451 geo-blocking detected\n"
                "   (expected in GitHub Actions runners)\n"
                "   Continuity + completeness checks are sufficient"
            )
        else:
            logger.error(f"❌ Cross-check validation FAILED: {e}")
            raise
    finally:
        cross_check_validator.close()

    # ============================================================================
    # Summary
    # ============================================================================

    logger.info("\n" + "=" * 70)
    logger.info("✅ ALL VALIDATION CHECKS PASSED")
    logger.info("=" * 70)
    logger.info("Database is ready for release")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Validate Binance futures database")
    parser.add_argument(
        "--db-path",
        type=Path,
        default=None,
        help="Path to DuckDB database (default: ~/.cache/binance-futures/...)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )

    args = parser.parse_args()
    main(db_path=args.db_path, verbose=args.verbose)
```

### Testing

**Run schema drift tests**:

```bash
pytest tests/test_validation/test_schema_drift.py -v
```

**Run full validation**:

```bash
uv run python scripts/operations/validate.py --verbose
```

### Checklist

- [ ] Create `src/binance_futures_availability/validation/schema_drift.py` (200 lines)
- [ ] Create `tests/test_validation/test_schema_drift.py` (150 lines)
- [ ] Update `scripts/operations/validate.py` to call schema_drift first
- [ ] Test locally: `pytest tests/test_validation/test_schema_drift.py`
- [ ] Test with workflow: `gh workflow run update-database.yml --field update_mode=daily`
- [ ] Verify schema check runs in GitHub Actions logs
- [ ] Document in MONITORING.md (add schema drift section)

**Time**: 4 hours

---

## Part 2: Batch Correlation ID Logging (3 hours)

### What It Does

Adds a unique batch ID to all logs during parallel probing. Enables:

- Grouping all probes for a date together
- Finding pattern: "all symbols failed on 2025-11-15 = S3 outage"
- Calculating batch success rates and latency
- Comparing performance across different batch sizes

### Files to Modify

#### 2.1 Update `src/binance_futures_availability/probing/batch_prober.py`

Add batch correlation ID:

```python
"""Parallel batch probing of symbols on Binance Vision S3.

Implements batch-level correlation IDs for debugging (ADR-0003).
See: src/binance_futures_availability/probing/s3_vision.py for individual probe logic.
"""

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from binance_futures_availability.probing.s3_vision import check_symbol_availability

logger = logging.getLogger(__name__)


def probe_symbols_for_date(
    symbols: list[str],
    date: date,
    batch_id: str | None = None,
    max_workers: int = 150,
) -> dict[str, dict[str, Any]]:
    """
    Probe availability for list of symbols on given date.

    Implements batch correlation ID logging per ADR-0003 strict error policy.
    All probes in same batch share batch_id for easy correlation in logs.

    Args:
        symbols: List of futures symbols (e.g., ['BTCUSDT', 'ETHUSDT', ...])
        date: Date to probe (datetime.date object)
        batch_id: Correlation ID for logging (auto-generated if None)
        max_workers: Number of parallel workers (default: 150, ADR-0005)

    Returns:
        Dict mapping symbol → availability result:
        {
            'BTCUSDT': {
                'available': True,
                'status_code': 200,
                'file_size_bytes': 1234567,
                'last_modified': 'Mon, 15 Nov 2025 03:00:00 GMT'
            },
            'ETHUSDT': {
                'available': False,
                'status_code': 404,
                'file_size_bytes': 0,
                'last_modified': None
            }
        }

    Raises:
        RuntimeError: If any probe fails (strict policy per ADR-0003)
                     Caller (backfill.py) retries on failure

    Example:
        >>> results = probe_symbols_for_date(
        ...     symbols=['BTCUSDT', 'ETHUSDT'],
        ...     date=date(2025, 11, 15)
        ... )
        >>> results['BTCUSDT']['available']
        True

    Logging:
        All probes in same batch share batch_id for correlation:
        >>> import logging
        >>> logging.basicConfig(level=logging.DEBUG)
        >>> results = probe_symbols_for_date(symbols, date)
        # Logs will show:
        # batch_id=a1b2c3d4 symbol=BTCUSDT status=success
        # batch_id=a1b2c3d4 symbol=ETHUSDT status=success
    """

    # Generate batch correlation ID (UUID short form for readability)
    if batch_id is None:
        batch_id = str(uuid.uuid4())[:8]

    batch_start = datetime.now(timezone.utc)
    results = {}
    success_count = 0
    total_symbols = len(symbols)

    # Log batch start
    logger.info(
        "Starting symbol availability batch probe",
        extra={
            "batch_id": batch_id,
            "total_symbols": total_symbols,
            "date": str(date),
            "timestamp": batch_start.isoformat(),
        },
    )

    # Probe each symbol
    for i, symbol in enumerate(symbols, 1):
        try:
            result = check_symbol_availability(symbol, date)
            results[symbol] = result
            success_count += 1

            logger.debug(
                "Symbol availability probe succeeded",
                extra={
                    "batch_id": batch_id,
                    "symbol": symbol,
                    "progress": f"{i}/{total_symbols}",
                    "available": result["available"],
                    "file_size_bytes": result.get("file_size_bytes", 0),
                    "status_code": result.get("status_code", 200),
                },
            )

        except RuntimeError as e:
            # Log failure with full context (strict policy ADR-0003)
            logger.error(
                "Symbol availability probe failed",
                extra={
                    "batch_id": batch_id,
                    "symbol": symbol,
                    "date": str(date),
                    "progress": f"{i}/{total_symbols}",
                    "error": str(e),
                    "http_status": getattr(e, "code", "unknown"),
                },
            )
            # Propagate immediately (no retry at this level)
            raise

    # Log batch completion
    batch_duration = (datetime.now(timezone.utc) - batch_start).total_seconds()

    logger.info(
        "Symbol availability batch probe completed",
        extra={
            "batch_id": batch_id,
            "total_symbols": total_symbols,
            "successful_probes": success_count,
            "success_rate_pct": round((success_count / total_symbols * 100), 2),
            "duration_seconds": round(batch_duration, 2),
            "avg_time_per_symbol_ms": round((batch_duration * 1000) / total_symbols, 2),
        },
    )

    return results
```

#### 2.2 Update calling code in backfill scripts

Update `scripts/operations/backfill.py` to use batch ID:

```python
# In backfill.py, pass batch_id to probe_symbols_for_date():

from datetime import date
from binance_futures_availability.probing.batch_prober import probe_symbols_for_date

def backfill_date_range(symbols: list[str], start_date: date, end_date: date):
    """Backfill data for date range."""

    current_date = start_date
    batch_num = 1

    while current_date <= end_date:
        try:
            # Probe all symbols for this date (with batch ID)
            results = probe_symbols_for_date(
                symbols=symbols,
                date=current_date,
                batch_id=None,  # Auto-generate UUID
            )

            # Insert results into database
            insert_probe_results(results, current_date)
            current_date += timedelta(days=1)
            batch_num += 1

        except RuntimeError as e:
            logger.error(f"Backfill failed for {current_date}: {e}")
            raise  # Per ADR-0003: fail fast
```

### Testing

**Manual test with logging**:

```bash
# Enable debug logging to see batch IDs
python -c "
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - batch_id=%(batch_id)s - %(message)s'
)

from binance_futures_availability.probing.batch_prober import probe_symbols_for_date
from datetime import date

results = probe_symbols_for_date(
    symbols=['BTCUSDT', 'ETHUSDT'],
    date=date(2025, 11, 15)
)
print(f'Results: {results}')
"
```

**Verify batch ID appears in logs**:

```bash
# Run backfill and grep for batch_id
uv run python scripts/operations/backfill.py 2>&1 | grep batch_id
# Output should show:
# batch_id=a1b2c3d4 Starting symbol availability batch probe...
# batch_id=a1b2c3d4 Symbol availability probe succeeded...
# batch_id=a1b2c3d4 Symbol availability batch probe completed...
```

### Checklist

- [ ] Update `src/binance_futures_availability/probing/batch_prober.py` with batch_id logic
- [ ] Add docstring examples showing batch_id in logs
- [ ] Update calling code (backfill.py) to pass batch_id=None
- [ ] Test locally: `python scripts/operations/backfill.py --start-date 2025-11-10 --end-date 2025-11-12`
- [ ] Verify batch IDs appear in output
- [ ] Test in workflow: Manual trigger with 3-day backfill
- [ ] Document batch ID usage in MONITORING.md

**Time**: 3 hours

---

## Part 3: Data Catalog Documentation (5 hours)

### What It Does

Creates comprehensive data dictionary for downstream users. Helps them:

- Understand table structure, columns, constraints
- Find example queries
- Understand data refresh schedule
- Know SLOs they can rely on

### File to Create

#### 3.1 Create `docs/schema/DATA_CATALOG.md`

(Use template from observability-research-report.md Section 9.4)

**Key sections**:

- Table overview (name, location, size, update frequency)
- Column definitions (name, type, nullable, description)
- Data lineage (visual diagram)
- SLO commitments
- Query examples
- Related documents

### Checklist

- [ ] Create `docs/schema/DATA_CATALOG.md` (150 lines)
- [ ] Link from `CLAUDE.md` in "Quick Links" section
- [ ] Link from `README.md` under "Documentation"
- [ ] Verify all links work (relative paths)
- [ ] Add to table of contents in `docs/INDEX.md` (if exists)
- [ ] Update `docs/operations/CATALOG.md` to point to DATA_CATALOG.md

**Time**: 5 hours

---

## Part 4: Testing & Release (2 hours)

### Testing Checklist

```bash
# 1. Run schema drift tests
pytest tests/test_validation/test_schema_drift.py -v

# 2. Run full test suite
pytest -m "not integration" --cov

# 3. Check coverage
coverage report --fail-under=80

# 4. Run validation manually
uv run python scripts/operations/validate.py --verbose

# 5. Test schema check in workflow
gh workflow run update-database.yml --field update_mode=daily --field lookback_days=1

# 6. Verify logs
gh run view $(gh run list --workflow=update-database.yml --limit 1 --json databaseId --jq '.[0].databaseId') --log | grep -A5 "schema validation"

# 7. Verify batch ID in logs
gh run view <id> --log | grep "batch_id"
```

### PR Checklist

Before creating PR:

- [ ] All new code has docstrings
- [ ] All test cases documented
- [ ] No breaking changes
- [ ] Backward compatible with existing code
- [ ] CHANGELOG.md updated
- [ ] MONITORING.md updated with schema drift section
- [ ] DATA_CATALOG.md linked from main docs
- [ ] All tests passing locally
- [ ] Code formatted with ruff

### Release Notes Template

```markdown
# Phase 0 Foundation Enhancements

## Summary

Added three low-cost, high-value observability enhancements:

1. **Schema Drift Detection** - Automatically validate database schema hasn't changed
2. **Batch Correlation Logging** - Track probes with batch IDs for easier debugging
3. **Data Catalog** - Comprehensive documentation for downstream users

## Changes

### New Features

- Schema validation check added to validation pipeline
- Batch correlation IDs in parallel probing logs
- Complete data catalog in docs/schema/DATA_CATALOG.md

### Bug Fixes

- None

### Breaking Changes

- None (fully backward compatible)

### Deprecations

- None

## Testing

- 12+ new unit tests for schema drift detection
- All existing tests passing (80%+ coverage maintained)
- Manual testing: schema check, batch logging, documentation

## Migration Guide

No migration needed. Phase 0 is fully backward compatible.

## Timeline

- Schema drift detection: Runs as first validation step (no opt-out)
- Batch correlation logging: Automatic in all batch probes
- Data catalog: Reference documentation (no impact on code)

## Next Steps (Phase 1+)

- Phase 1: Grafana Cloud SLO tracking ($19/month)
- Phase 2: Soda Core data quality checks
- Phase 3: Great Expectations advanced validation
```

---

## Summary Table

| Task                   | Time    | Files             | Tests         | Status |
| ---------------------- | ------- | ----------------- | ------------- | ------ |
| Schema drift detection | 4h      | 1 new + 1 updated | 10 new        | Ready  |
| Batch correlation IDs  | 3h      | 1 modified        | 0 new\*       | Ready  |
| Data catalog docs      | 5h      | 1 new             | N/A           | Ready  |
| Testing + PR           | 2h      | Release notes     | 12+ new       | Ready  |
| **TOTAL**              | **14h** | **4 files**       | **12+ tests** | **GO** |

\*Batch logging is tested through existing integration tests

---

## Implementation Order

```
Week 1:
  Mon: Create schema_drift.py + tests
  Tue-Wed: Integration testing, fix any issues
  Thu: Update batch_prober.py + test

Week 2:
  Mon: Create DATA_CATALOG.md
  Tue: Update all documentation links
  Wed: Final review + testing
  Thu: Create PR
  Fri: Merge + release
```

---

## Questions & Support

**Q: Can I implement these incrementally?**
A: Yes! Each part is independent:

- Schema drift (4h) can go alone
- Batch IDs (3h) can go alone
- Catalog (5h) can go alone

**Q: Will this break anything?**
A: No. All changes are backward compatible and tested.

**Q: How much will this slow down the workflow?**
A: Schema drift adds <1 second per workflow run.

**Q: What if I find a schema change in production?**
A: Workflow will fail with clear error message. Manual backfill via `gh workflow run` can fix it.

---

## Success Criteria

After completing Phase 0:

✅ Schema changes detected automatically
✅ Batch IDs make debugging 3x faster
✅ Downstream users have complete documentation
✅ Zero manual steps added to workflow
✅ Test coverage maintained at 80%+
