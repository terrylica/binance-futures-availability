# Autonomous E2E Testing Framework

Self-bootstrapping test framework using Playwright 1.56+ AI agents for autonomous web UI and API testing.

## Overview

This framework enables AI agents to autonomously test web services without manual intervention:

- **HTTP API Testing**: Port 8123 (ClickHouse HTTP interface)
- **UI Testing**: Port 5521 (ClickHouse web UI) with screenshot capture
- **Latest Technologies**: Playwright 1.56+ (Oct 2025 release with AI agents)

## Quick Start

### Prerequisites

```bash
# Install dependencies
uv sync --extra e2e

# Install Playwright browsers
uv run playwright install chromium
```

### Run Tests

**Option 1: Autonomous Mode** (No pytest, direct execution)

```bash
# Test HTTP API
uv run python tests/e2e/test_clickhouse_http.py

# Test Web UI
uv run python tests/e2e/test_clickhouse_ui.py
```

**Option 2: Pytest Mode** (Full test suite)

```bash
# Run all tests
uv run pytest tests/e2e/

# Run HTTP tests only
uv run pytest tests/e2e/test_clickhouse_http.py

# Run UI tests only
uv run pytest tests/e2e/test_clickhouse_ui.py

# Run with headed browser (show UI)
uv run pytest tests/e2e/test_clickhouse_ui.py --headed

# Run with slow motion
uv run pytest tests/e2e/ --headed --slowmo=100
```

## Test Structure

```
tests/e2e/
├── README.md                    # This file
├── conftest.py                  # Pytest configuration
├── test_clickhouse_http.py      # HTTP API tests (port 8123)
├── test_clickhouse_ui.py        # Web UI tests (port 5521)
├── screenshots/                 # Auto-generated screenshots
│   ├── autonomous_homepage.png
│   └── autonomous_metrics.png
└── test-results/                # Test artifacts
```

## Test Coverage

### Port 8123: ClickHouse HTTP API

✅ **8/8 Tests Passing**

1. Root endpoint returns "Ok."
2. Version query (SELECT version())
3. Database listing (system.databases)
4. Table counting (system.tables)
5. Health check (/ping endpoint)
6. JSON format output
7. Error handling (404 for missing tables)
8. Query log availability

### Port 5521: ClickHouse Web UI

✅ **5/8 Tests Passing**

1. ✓ Homepage loads successfully
2. ⚠ Metrics page loads (but has known bug)
3. ✓ Local instance warning detected
4. ✓ Server metrics visible (uptime, version, databases)
5. ✓ Running Queries section found
6. ⚠ Queries tab navigation (link not found - UI may use different label)
7. ⚠ Tables tab navigation (link not found - UI may use different label)
8. ✓ No error messages detected

## Known Issues

### Issue: "Missing columns: 'steps'" in Metrics Page

**Symptom**: Metrics page shows error:

```
Missing columns: 'steps' while processing query: 'steps', required columns: 'steps' 'steps'.
```

**Root Cause**: The UI generates a query with a CTE (Common Table Expression) named `steps`, but ClickHouse 24.1.8 can't resolve it inside the `FROM numbers(steps)` subquery. This is a bug in the UI's query generation, not ClickHouse itself.

**Workaround**: Use the "Queries" tab instead of "Metrics" dashboard for manual queries.

**Suggested Fix**: Upgrade ClickHouse to 24.8+ (better CTE handling) or file issue with UI maintainers.

## Screenshot Capture

Screenshots are automatically captured:

- **On test execution**: `tests/e2e/screenshots/autonomous_*.png`
- **On test failure**: `tests/e2e/screenshots/*.png` (pytest mode)
- **Full page**: All screenshots capture entire page, not just viewport

View screenshots to verify visual state without manual inspection.

## Latest Technologies (2025)

### Playwright 1.56+ AI Agents

Released October 2025, Playwright now includes 3 AI agents:

1. **Planner Agent**: Designs test plans from high-level goals
2. **Generator Agent**: Converts plans into executable Playwright code
3. **Healer Agent**: Auto-fixes broken tests when UI changes

**Note**: This framework uses base Playwright with autonomous execution. AI agent features available via Playwright Test CLI.

### Dependencies

- `playwright>=1.56.0` - AI agent testing (Oct 2025 release)
- `pytest-playwright>=0.7.0` - Pytest integration
- `httpx>=0.28.0` - Async HTTP client for API testing
- `pytest>=9.0.0` - Latest pytest (2025)

## Customization

### Add New Tests

1. Create new test file: `tests/e2e/test_myservice.py`
2. Use test classes for organization:

```python
class TestMyService:
    def test_feature(self, page):
        page.goto("http://localhost:PORT")
        # assertions...
```

3. Add autonomous runner for standalone execution:

```python
if __name__ == "__main__":
    # Direct execution without pytest
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        # tests...
```

### Configure Browser

Edit `conftest.py` to change:

- Viewport size (default: 1920x1080)
- Browser type (chromium, firefox, webkit)
- Timeout settings
- Screenshot options

## Troubleshooting

### Browser Not Found

```bash
# Install browsers
uv run playwright install chromium

# Or install all browsers
uv run playwright install
```

### Connection Refused

Ensure services are running:

```bash
# Check port 8123
curl http://localhost:8123/

# Check port 5521
curl http://localhost:5521/
```

### Tests Fail in Headed Mode

Run with slowmo to see what's happening:

```bash
uv run pytest tests/e2e/ --headed --slowmo=1000
```

## Future Enhancements

1. **AI Agent Integration**: Use Playwright Test AI agents (Planner, Generator, Healer)
2. **Visual Regression**: Compare screenshots against baseline images
3. **Performance Metrics**: Track page load times, query latency
4. **CI/CD Integration**: GitHub Actions for automated testing
5. **Parallel Execution**: Run tests across multiple browsers simultaneously

## References

- [Playwright Documentation](https://playwright.dev/python/)
- [Playwright AI Agents (2025)](https://playwright.dev/docs/test-agents)
- [pytest-playwright Plugin](https://playwright.dev/python/docs/test-runners)
- [httpx Documentation](https://www.python-httpx.org/)
