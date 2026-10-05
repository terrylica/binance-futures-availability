# ADR-0028: Upsert Integrity Gate and Daily Volume Collection

**Status**: Accepted

**Date**: 2026-10-05

**Amends**: ADR-0003 (error handling), ADR-0007 (volume metrics), ADR-0013 (rankings), ADR-0019 (indexes)

**Context**:

A health check on 2026-10-05 found that the published database had been silently corrupt since 2025-11. 201,424 rows had `status_code = 200` and a file size but `available = false`, and 275 days showed fewer than 100 available symbols. Every daily run still reported success.

Root cause: under DuckDB 1.4.2, `INSERT OR REPLACE` silently skipped every column that belonged to a secondary index. ADR-0019/0007 had added `idx_available_date (available, date)` and `idx_quote_volume_date`. When the first probe of a date hit S3's T+1 lag (404), the row was stored as `false`, and no later 20-day-lookback re-probe (ADR-0011) could flip it. This was reproduced on a copy of the production database: dropping the indexes or upgrading to DuckDB 1.5.6 each fixes it independently.

Two further gaps surfaced. First, validation never fails by design (ADR-0003), so nothing caught the corruption. Second, the daily path never collected volume (ADR-0007 only wired it into full backfills, and the historical backfill was never run), so no row before 2025-11-26 had volume and the rankings archive (ADR-0013) was effectively empty.

**Decision**:

1. **Never index a mutable, non-key column of `daily_availability`.** Both indexes are dropped. Scans with date zone-map pruning answer snapshot and top-N queries in 2–4 ms on the 2.6M-row table.
2. **Explicit `ON CONFLICT (date, symbol) DO UPDATE`, never `INSERT OR REPLACE`.** Volume columns use `COALESCE(excluded.x, existing.x)`, so an availability-only re-probe never wipes collected volume. DuckDB pinned `>=1.5.6`.
3. **One-time repair migration**: while a legacy index exists, drop it and set `available = (status_code = 200)`. This is exact, because availability is determined by the probe status. The migration cannot run again, so it cannot mask a future regression.
4. **Integrity hard gate (amends ADR-0003).** Data-quality findings stay informational. Row-level invariant violations are corruption, not data gaps, so `validate.py` exits 1 and the database is not published. Invariants: `available ⇔ status_code = 200`, `status_code ∈ {200, 404}`, file size present exactly when available, volume only on available rows.
5. **Daily volume collection (amends ADR-0007).** The daily update fills 1d-kline volume for available rows in its lookback window over the shared HTTP pool. Successful fetches are persisted before any failure raises. A volume failure is logged as an ERROR but does not block publishing availability; failed rows stay NULL and are retried next run. This is a scoped exception to ADR-0003, because volume is supplementary enrichment.
6. **Rankings regenerate in full every run (amends ADR-0013).** Append-only generation froze late-arriving volume and computed `LAG()` rank changes over only the appended rows.

**Consequences**:

- The published database is repaired on the first run with the new code; `daily_symbol_counts` is recomputed.
- A one-time volume catch-up (~720k rows, ~35 min at the measured 352 rows/s) runs by dispatching the workflow with `volume_start_date`.
- Any future upsert regression fails the workflow instead of shipping.
