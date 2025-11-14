# Legacy Scripts

Deprecated scripts preserved for reference.

⚠️ **WARNING:** These scripts use obsolete methods and should NOT be used in production.

## Scripts

### backfill_head.py

**Status:** DEPRECATED
**Replacement:** `scripts/operations/backfill.py` (AWS CLI method)

**Why deprecated:**

- Uses HTTP HEAD requests (1 request per symbol per date)
- 7.2x slower than AWS CLI approach (3 hours vs 25 minutes)
- 4,587x more API calls (1.5M requests vs 327 calls)
- Higher risk of S3 rate limiting

**Historical context:**

- Original backfill implementation from v1.0.0
- Worked well for incremental daily updates
- Not efficient for bulk historical backfill
- Replaced by AWS CLI approach in ADR-0005

**Preserved for:**

- Understanding incremental update logic
- Reference implementation of HEAD request probing
- Historical documentation

## Migration Guide

If you're using legacy scripts, migrate as follows:

### Old (HEAD-based backfill)

```bash
uv run python scripts/run_backfill.py  # DEPRECATED
```

### New (AWS CLI backfill)

```bash
uv run python scripts/operations/backfill.py
```

See `docs/decisions/0005-aws-cli-bulk-operations.md` for rationale.
