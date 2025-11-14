# ADR-0003: Error Handling - Strict Raise Policy

**Status**: Accepted

**Date**: 2025-11-12

**Context**:

When probing Binance Vision S3 for file availability, various failures can occur:

- **Network errors**: Timeouts, DNS failures, connection refused
- **HTTP errors**: 404 (file not found), 403 (forbidden), 500 (server error)
- **Transient failures**: Temporary S3 outages, throttling

Three error handling strategies were evaluated:

1. **Strict raise policy**: Raise all errors immediately, no retries/fallbacks
   - Explicit failure visibility
   - Scheduler retries failed updates in next cycle
   - No silent data corruption

2. **Retry with backoff**: Automatic retry 3x with exponential backoff
   - Hides transient failures
   - Longer update times
   - Complex retry logic

3. **Fallback to defaults**: Mark unavailable on error, continue probing
   - Silent failures
   - Data corruption risk (404 vs network error)
   - Poor observability

**Decision**:

We will use the **strict raise policy**: raise and propagate all errors immediately with NO retries, fallbacks, or silent failures.

**Implementation pattern**:

```python
def check_symbol_availability(symbol: str, date: datetime.date) -> dict:
    """
    Check if a symbol's 1m klines file exists on Binance Vision S3.

    Raises:
        RuntimeError: On any network or HTTP error (NO RETRY)
    """
    url = f"https://data.binance.vision/data/futures/um/daily/klines/{symbol}/1m/{symbol}-1m-{date}.zip"

    try:
        response = urllib.request.urlopen(url, timeout=10)
        return {
            'available': True,
            'status_code': 200,
            'file_size_bytes': int(response.headers.get('Content-Length', 0)),
            'last_modified': response.headers.get('Last-Modified'),
        }
    except urllib.error.HTTPError as e:
        # NO RETRY - raise immediately with full context
        raise RuntimeError(
            f"S3 probe failed for {symbol} on {date}: "
            f"HTTP {e.code} - {e.reason}"
        ) from e
    except urllib.error.URLError as e:
        # NO RETRY - raise immediately
        raise RuntimeError(
            f"Network error probing {symbol} on {date}: {e.reason}"
        ) from e
```

**Logging pattern**:

```python
import logging

logger = logging.getLogger(__name__)

try:
    result = check_symbol_availability(symbol, date)
except RuntimeError as e:
    # Log with full context before propagating
    logger.error(
        "Probe failed",
        extra={
            'symbol': symbol,
            'date': str(date),
            'error': str(e),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
    )
    raise  # Propagate to caller (scheduler)
```

**Consequences**:

**Positive**:

- **Fail-fast**: Errors surface immediately during development
- **Explicit visibility**: All failures logged with full context (symbol, date, error)
- **No silent corruption**: Impossible to record incorrect availability status
- **Simple code**: No retry logic, no timeout tuning, no fallback branches
- **Scheduler resilience**: APScheduler retries failed jobs in next cycle
- **Debugging**: Complete error chain preserved via `raise ... from e`

**Negative**:

- **No automatic retry**: Transient failures require manual intervention or waiting for next cycle
- **Longer backfill on failures**: Must re-run failed date ranges

**Mitigations**:

- **Scheduler retry**: Daily updates retry automatically next day
- **Checkpoint backfill**: Backfill script saves progress, can resume from last successful date
- **Structured logging**: All errors captured with context for post-mortem analysis

**SLO alignment**:

- **Observability SLO**: "All failures logged with full context" - satisfied
- **Availability SLO**: "95% of daily updates complete successfully" - allows 5% failure rate

**Related Decisions**:

- ADR-0004: APScheduler automation (handles retry scheduling)
