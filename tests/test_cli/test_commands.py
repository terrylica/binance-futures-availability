"""CLI smoke tests (ADR-0027).

Test coverage:
- Help message displays without error
- Version flag returns successfully
- Missing command returns non-zero exit

See: docs/architecture/decisions/0027-test-suite-optimization.md
"""

import subprocess
import sys


class TestCLISmoke:
    """Smoke tests for CLI entry point."""

    def test_help_flag_exits_zero(self):
        """--help should display help and exit 0."""
        result = subprocess.run(
            [sys.executable, "-m", "binance_futures_availability.cli.main", "--help"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "binance-futures-availability" in result.stdout
        assert "Available commands" in result.stdout

    def test_version_flag_exits_zero(self):
        """--version should display version and exit 0."""
        result = subprocess.run(
            [sys.executable, "-m", "binance_futures_availability.cli.main", "--version"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "binance-futures-availability" in result.stdout

    def test_no_command_exits_nonzero(self):
        """No command should print help and exit 1."""
        result = subprocess.run(
            [sys.executable, "-m", "binance_futures_availability.cli.main"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 1
        assert "binance-futures-availability" in result.stdout

    def test_query_help_exits_zero(self):
        """query --help should display query subcommands."""
        result = subprocess.run(
            [sys.executable, "-m", "binance_futures_availability.cli.main", "query", "--help"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "snapshot" in result.stdout or "timeline" in result.stdout
