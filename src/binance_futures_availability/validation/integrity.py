"""Integrity validation: row-level invariants whose violation means corruption, not a data gap.

Unlike continuity/completeness/cross-check (informational warnings per ADR-0003), a failed
invariant fails the workflow so a corrupt database is never published. Motivated by the
2025-11 to 2026-10 incident where ~201k rows had status_code=200 but available=false.
"""

from pathlib import Path

from binance_futures_availability.database.availability_db import AvailabilityDatabase

# name -> SQL counting violating rows
INVARIANTS: dict[str, str] = {
    "available matches status_code (200 <=> true)": (
        "SELECT count(*) FROM daily_availability WHERE available <> (status_code = 200)"
    ),
    "status_code is 200 or 404": (
        "SELECT count(*) FROM daily_availability WHERE status_code NOT IN (200, 404)"
    ),
    "file_size_bytes present exactly when available": (
        "SELECT count(*) FROM daily_availability WHERE available <> (file_size_bytes IS NOT NULL)"
    ),
    "volume only on available rows": (
        "SELECT count(*) FROM daily_availability "
        "WHERE NOT available AND quote_volume_usdt IS NOT NULL"
    ),
}


class IntegrityValidator:
    """Check row-level invariants of daily_availability."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db = AvailabilityDatabase(db_path=db_path)

    def check_integrity(self) -> dict[str, int]:
        """Return {invariant name: violating row count} for every violated invariant."""
        violations = {}
        for name, sql in INVARIANTS.items():
            count = self.db.query(sql)[0][0]
            if count:
                violations[name] = count
        return violations

    def close(self) -> None:
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
