# ADR-0012: Auto-Backfill New Symbols

**Status**: Proposed
**Date**: 2025-11-17
**Relates-To**: ADR-0009 (GitHub Actions Automation), ADR-0011 (20-Day Lookback)

## Context

When Binance lists new perpetual futures symbols, they appear in S3 Vision with historical data availability. Our daily symbol discovery (`discover_symbols.py`) detects these new symbols and updates `symbols.json`.

**Current Gap**: When new symbols are discovered, we only probe forward (yesterday's data via daily update). Historical data (2019-09-25 to present) remains uncollected until manual backfill.

**Problem**: Manual backfill intervention violates automation principles and creates incomplete data gaps.

**Discovery Pattern**:

- New symbols appear in S3 Vision bucket listings (detected via daily XML API enumeration)
- `symbols.json` is updated automatically when new symbols found
- Git commit created with `[skip ci]` to avoid workflow loops
- **Gap**: No automatic historical backfill triggered

**Example Scenario**:

- Day 1: Symbol `NEWUSDT` listed, discovered, added to `symbols.json`
- Day 1 result: Only 1 day of data collected (yesterday)
- Day 2-N: Daily updates continue collecting new days
- Historical gap: 2019-09-25 to Day 1 remains empty until manual backfill

## Decision

Implement **conditional auto-backfill** as integrated workflow step that:

1. **Detects symbol gaps** by comparing `symbols.json` with database contents
2. **Triggers targeted backfill** for new symbols only (not re-probing existing data)
3. **Runs conditionally** only when new symbols detected (zero overhead otherwise)
4. **Uses existing infrastructure** (BatchProber, backfill.py) for consistency

**Architecture**:

```
Daily Workflow:
  ├─ Symbol Discovery (always runs)
  │   └─ Updates symbols.json if new symbols found
  ├─ Gap Detection (conditional: if symbols.json changed)
  │   └─ Compare symbols.json vs database, output new symbols
  ├─ Auto-Backfill (conditional: if gaps detected)
  │   └─ Backfill new symbols only (2019-09-25 to yesterday)
  └─ Daily Update (always runs)
      └─ Probe all symbols for yesterday (with 20-day lookback per ADR-0011)
```

**Conditional Execution**: Backfill step skipped when `symbols.json` unchanged (99% of days), ensuring zero performance overhead.

## Implementation

### Gap Detection Script

**File**: `scripts/operations/detect_symbol_gaps.py`

**Purpose**: Compare discovered symbols against database, identify missing symbols.

**Logic**:

```python
discovered_symbols = load_symbols_from_json()  # All symbols from symbols.json
database_symbols = query_database_symbols()     # All symbols ever probed
new_symbols = discovered_symbols - database_symbols
return new_symbols  # Empty list if no gaps
```

**Output**: JSON array of new symbol names (e.g., `["NEWUSDT", "OTHERUSDT"]`)

**Exit Code**: 0 if gaps found (triggers backfill), 1 if no gaps (skips backfill)

### Targeted Backfill Support

**File**: `scripts/operations/backfill.py`

**Enhancement**: Add `--symbols` parameter for targeted backfill.

**Current Behavior**: Backfills ALL symbols from `symbols.json`
**New Behavior**: Backfills ONLY specified symbols when `--symbols` provided

**Usage**:

```bash
# Backfill specific symbols only
uv run python scripts/operations/backfill.py --symbols NEWUSDT,OTHERUSDT

# Backfill all symbols (existing behavior, no --symbols flag)
uv run python scripts/operations/backfill.py
```

**Performance**: Targeted backfill for 1 symbol ≈ 4.5 seconds (vs 25 minutes for all 713 symbols)

### Workflow Integration

**File**: `.github/workflows/update-database.yml`

**New Steps** (inserted after symbol discovery):

```yaml
- name: Detect symbol gaps
  id: detect_gaps
  if: steps.discovery.outputs.symbols_changed == 'true'
  run: |
    NEW_SYMBOLS=$(uv run python scripts/operations/detect_symbol_gaps.py)
    echo "new_symbols=$NEW_SYMBOLS" >> $GITHUB_OUTPUT
    if [ -n "$NEW_SYMBOLS" ]; then
      echo "gaps_detected=true" >> $GITHUB_OUTPUT
    else
      echo "gaps_detected=false" >> $GITHUB_OUTPUT
    fi

- name: Auto-backfill new symbols
  if: steps.detect_gaps.outputs.gaps_detected == 'true'
  run: |
    NEW_SYMBOLS="${{ steps.detect_gaps.outputs.new_symbols }}"
    echo "Backfilling new symbols: $NEW_SYMBOLS"
    uv run python scripts/operations/backfill.py --symbols "$NEW_SYMBOLS"
```

**Conditional Logic**:

- `detect_gaps` runs ONLY if `symbols.json` changed
- `auto-backfill` runs ONLY if gaps detected
- Both steps skipped on 99% of daily runs (zero overhead)

## Consequences

### Positive

**Availability**:

- ✅ **Zero manual intervention**: New symbols automatically get full historical data
- ✅ **No data gaps**: Historical completeness maintained automatically
- ✅ **Idempotent**: Re-running backfill for same symbols is safe (UPSERT semantics)

**Correctness**:

- ✅ **Targeted backfill**: Only new symbols processed (no redundant re-probing)
- ✅ **Reuses proven code**: Same BatchProber + backfill.py infrastructure as manual backfills
- ✅ **Database consistency**: UPSERT handles overlaps between backfill and daily updates

**Observability**:

- ✅ **Workflow logs**: Clear indication of gap detection and backfill execution
- ✅ **GitHub commit history**: `symbols.json` updates visible with timestamps
- ✅ **Database audit trail**: `probe_timestamp` shows when historical data was backfilled

**Maintainability**:

- ✅ **Minimal code changes**: Reuses 90% of existing backfill infrastructure
- ✅ **Conditional execution**: Zero overhead when no new symbols (99% of days)
- ✅ **Testable**: Gap detection logic isolated, easy to unit test

### Neutral/Negative

**Performance**:

- ⚠️ **Backfill duration**: 1 new symbol adds ~4.5 seconds to workflow
- ⚠️ **Multiple new symbols**: N symbols × 4.5s (e.g., 5 symbols = 22.5s)
- **Mitigation**: Rare occurrence (new listings happen ~1-2 times per month)

**Complexity**:

- ⚠️ **Conditional workflow logic**: Adds complexity to YAML (if statements, outputs)
- **Mitigation**: Well-documented, follows GitHub Actions best practices

**Error Handling**:

- ⚠️ **Backfill failure blocks daily update**: If backfill fails, entire workflow fails
- **Mitigation**: Follows ADR-0003 strict error policy (fail fast, retry next cycle)
- **Alternative**: Could separate backfill into independent workflow (rejected for simplicity)

## Alternatives Considered

### Alternative 1: Separate Backfill Workflow

**Approach**: Trigger separate workflow when `symbols.json` changes (via `workflow_dispatch` or repository_dispatch).

**Rejected Because**:

- ❌ **Higher complexity**: Two workflows to maintain instead of one
- ❌ **Race conditions**: Backfill and daily update could conflict
- ❌ **Lower observability**: Results split across multiple workflow runs

### Alternative 2: Manual Backfill with Alerts

**Approach**: Send Slack/email alert when new symbols detected, require manual backfill.

**Rejected Because**:

- ❌ **Violates automation principle**: Requires human intervention
- ❌ **Data gaps**: Historical data remains incomplete until manual action
- ❌ **Not scalable**: Doesn't align with "set and forget" automation goal

### Alternative 3: Nightly Full Backfill

**Approach**: Re-backfill ALL symbols nightly to catch any gaps.

**Rejected Because**:

- ❌ **Wasteful**: 99.9% of data re-probed unnecessarily every night
- ❌ **S3 request overhead**: 713 symbols × 2,240 days × 150 workers = massive load
- ❌ **Workflow duration**: Would take ~25 minutes nightly (vs 2 minutes currently)

## Implementation Plan

**See**: `docs/plans/0012-auto-backfill/plan.yaml`

**Phases**:

1. **Phase 1**: Implement gap detection script + unit tests
2. **Phase 2**: Add `--symbols` parameter to backfill.py + tests
3. **Phase 3**: Integrate conditional steps into workflow + validation
4. **Phase 4**: Test with simulated new symbol (add fake symbol, verify backfill)

**Exit Criteria**: New symbol detected → full historical backfill completed → daily updates continue seamlessly.

## SLOs

**Availability**:

- New symbols get full historical data within 24 hours of discovery (single workflow run)
- Zero manual intervention required for symbol onboarding

**Correctness**:

- 100% historical coverage for all symbols (no gaps from listing date to present)
- Targeted backfill avoids redundant re-probing (efficiency)

**Observability**:

- Workflow logs show gap detection results (how many new symbols found)
- Backfill step logs show which symbols processed and duration
- Database `probe_timestamp` distinguishes backfilled data from daily updates

**Maintainability**:

- Reuses existing `BatchProber` and `backfill.py` (minimal new code)
- Conditional execution keeps workflow fast when no new symbols (99% of days)
- Gap detection script is <50 lines, easily testable

## References

- **ADR-0009**: GitHub Actions Automation (established workflow foundation)
- **ADR-0011**: 20-Day Lookback (ensures overlap between backfill and daily updates)
- **Symbol Discovery**: `scripts/operations/discover_symbols.py`
- **Backfill Infrastructure**: `scripts/operations/backfill.py`
- **Batch Probing**: `src/binance_futures_availability/probing/batch_prober.py`

## Notes

**Interaction with ADR-0011 (20-Day Lookback)**:

The 20-day lookback ensures seamless handoff between backfill and daily updates:

- **Day 0**: New symbol discovered, backfill runs (2019-09-25 to yesterday)
- **Day 1-20**: Daily update probes last 20 days (includes backfill overlap)
- **Result**: Any gaps between backfill completion and daily update are automatically filled

**UPSERT semantics** ensure no data corruption from overlapping probes.

**Workflow Performance**:

Typical daily run (no new symbols):

- Symbol discovery: ~1-2s
- Gap detection: Skipped (conditional)
- Auto-backfill: Skipped (conditional)
- Daily update: ~2 minutes (20-day lookback)
- **Total**: ~2 minutes (unchanged from baseline)

Daily run with 1 new symbol:

- Symbol discovery: ~1-2s
- Gap detection: ~1s
- Auto-backfill: ~4.5s (1 symbol × full history)
- Daily update: ~2 minutes (20-day lookback)
- **Total**: ~2 minutes 7 seconds (+7 seconds overhead)

**Idempotency**: Re-running backfill for same symbol is safe. `PRIMARY KEY (date, symbol)` ensures UPSERT behavior (no duplicates).
