"""Tests for the integrity hard gate (row-level invariants)."""

import importlib.util
from pathlib import Path

from binance_futures_availability.validation.integrity import IntegrityValidator


def test_clean_database_has_no_violations(db, sample_probe_result, temp_db_path):
    db.insert_availability(**sample_probe_result)
    db.close()
    with IntegrityValidator(db_path=temp_db_path) as validator:
        assert validator.check_integrity() == {}


def test_available_status_mismatch_is_reported(db, sample_probe_result, temp_db_path):
    db.insert_availability(**sample_probe_result)
    db.conn.execute("UPDATE daily_availability SET available = false")
    db.close()
    with IntegrityValidator(db_path=temp_db_path) as validator:
        violations = validator.check_integrity()
    assert violations["available matches status_code (200 <=> true)"] == 1


def test_validate_script_exits_nonzero_on_corruption(
    db, sample_probe_result, temp_db_path, monkeypatch
):
    db.insert_availability(**sample_probe_result)
    db.conn.execute("UPDATE daily_availability SET status_code = 500")
    db.close()
    monkeypatch.setenv("DB_PATH", str(temp_db_path))
    monkeypatch.setattr("sys.argv", ["validate.py"])
    path = Path(__file__).parents[2] / "scripts" / "operations" / "validate.py"
    spec = importlib.util.spec_from_file_location("validate_script", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.main() == 1
