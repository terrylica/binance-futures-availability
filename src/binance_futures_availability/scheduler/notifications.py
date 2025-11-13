"""Notification and logging utilities for scheduler failures.

See: docs/decisions/0003-error-handling-strict-policy.md (observability)
"""

import datetime
import logging
from pathlib import Path
from typing import Any


def setup_scheduler_logging(
    log_path: Path | None = None, level: int = logging.INFO
) -> logging.Logger:
    """
    Configure structured logging for scheduler operations.

    Args:
        log_path: Log file path (default: ~/.cache/binance-futures/scheduler.log)
        level: Logging level (default: INFO)

    Returns:
        Configured logger instance

    Example:
        >>> logger = setup_scheduler_logging()
        >>> logger.info("Scheduler started")

    Log format:
        2025-11-12 02:00:00,123 | INFO | scheduler.daily_update | Daily update completed for 2025-11-11
    """
    if log_path is None:
        cache_dir = Path.home() / ".cache" / "binance-futures"
        cache_dir.mkdir(parents=True, exist_ok=True)
        log_path = cache_dir / "scheduler.log"

    # Create logger
    logger = logging.getLogger("binance_futures_availability.scheduler")
    logger.setLevel(level)

    # File handler
    file_handler = logging.FileHandler(log_path)
    file_handler.setLevel(level)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)

    # Formatter (structured format)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Add handlers if not already added
    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger


def log_probe_failure(
    symbol: str,
    date: datetime.date,
    error: Exception,
    logger: logging.Logger | None = None,
) -> None:
    """
    Log probe failure with structured context.

    Args:
        symbol: Symbol that failed
        date: Date that failed
        error: Exception raised
        logger: Logger instance (default: create new)

    Example:
        >>> log_probe_failure('BTCUSDT', datetime.date(2024, 1, 15), RuntimeError("Network timeout"))

    Log output:
        2025-11-12 02:00:00,123 | ERROR | scheduler | Probe failed for BTCUSDT on 2024-01-15: Network timeout

    SLO:
        Observability SLO: "All failures logged with full context"
        See: docs/plans/v1.0.0-implementation-plan.yaml (slos.observability)
    """
    if logger is None:
        logger = setup_scheduler_logging()

    logger.error(
        f"Probe failed for {symbol} on {date}: {error}",
        extra={
            "symbol": symbol,
            "date": str(date),
            "error_type": type(error).__name__,
            "error_message": str(error),
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        },
        exc_info=True,
    )


def log_batch_summary(
    date: datetime.date,
    total_symbols: int,
    available_count: int,
    failed_count: int = 0,
    duration_seconds: float | None = None,
    logger: logging.Logger | None = None,
) -> None:
    """
    Log batch probe summary with metrics.

    Args:
        date: Date probed
        total_symbols: Total symbols attempted
        available_count: Symbols found available
        failed_count: Symbols that failed to probe
        duration_seconds: Execution time in seconds
        logger: Logger instance (default: create new)

    Example:
        >>> log_batch_summary(
        ...     date=datetime.date(2024, 1, 15),
        ...     total_symbols=708,
        ...     available_count=708,
        ...     failed_count=0,
        ...     duration_seconds=125.3
        ... )

    Log output:
        2025-11-12 02:02:05,456 | INFO | scheduler | Batch summary for 2024-01-15: 708 total, 708 available, 0 failed (125.3s)
    """
    if logger is None:
        logger = setup_scheduler_logging()

    duration_str = f"{duration_seconds:.1f}s" if duration_seconds else "N/A"

    logger.info(
        f"Batch summary for {date}: {total_symbols} total, "
        f"{available_count} available, {failed_count} failed ({duration_str})",
        extra={
            "date": str(date),
            "total_symbols": total_symbols,
            "available_count": available_count,
            "failed_count": failed_count,
            "duration_seconds": duration_seconds,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        },
    )


def format_error_report(error_context: dict[str, Any]) -> str:
    """
    Format error context into human-readable report.

    Args:
        error_context: Dict with error details (symbol, date, error, etc.)

    Returns:
        Formatted error report string

    Example:
        >>> context = {
        ...     'symbol': 'BTCUSDT',
        ...     'date': '2024-01-15',
        ...     'error': 'Network timeout',
        ...     'status_code': None,
        ...     'timestamp': '2025-11-12T02:00:00Z'
        ... }
        >>> print(format_error_report(context))
        Error Report
        ============
        Symbol: BTCUSDT
        Date: 2024-01-15
        Error: Network timeout
        Status Code: None
        Timestamp: 2025-11-12T02:00:00Z
    """
    report_lines = [
        "Error Report",
        "=" * 50,
        f"Symbol: {error_context.get('symbol', 'N/A')}",
        f"Date: {error_context.get('date', 'N/A')}",
        f"Error: {error_context.get('error', 'N/A')}",
        f"Status Code: {error_context.get('status_code', 'N/A')}",
        f"Timestamp: {error_context.get('timestamp', 'N/A')}",
        "=" * 50,
    ]

    return "\n".join(report_lines)
