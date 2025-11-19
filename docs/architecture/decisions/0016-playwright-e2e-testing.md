# ADR-0016: Playwright E2E Testing Framework

**Status**: Accepted

**Date**: 2025-11-18

**Context**:

We needed to verify ClickHouse services (HTTP API on port 8123 and Web UI on port 5521) were functional without requiring manual browser inspection or manual API testing. The challenges were:

1. **Manual verification is time-consuming**: Opening browsers, clicking through UI, copying curl commands
2. **No visual proof**: Text-based tests can't capture UI rendering issues or layout problems
3. **Outdated testing tools**: Many E2E frameworks use older dependencies (Playwright 1.40, pytest 7.x)
4. **No autonomous execution**: Tests requiring manual setup or human verification defeat automation purpose
5. **Insufficient evidence**: Passing tests without screenshots/logs don't prove the UI actually works

Two approaches were considered:

1. **Manual testing**: Developer opens browser, clicks through UI, runs curl commands
   - Pros: Simple, no code needed
   - Cons: Time-consuming, not repeatable, no audit trail, requires human intervention

2. **Automated E2E framework**: Playwright + pytest with screenshot capture
   - Pros: Repeatable, visual proof, autonomous, creates audit trail
   - Cons: Requires initial setup, dependency management, learning curve

**Decision**:

We will implement an **autonomous E2E testing framework** using:

**Technology Stack** (latest 2025 versions):

- **Playwright 1.56+** (Oct 2025 release with AI agents: Planner, Generator, Healer)
- **pytest 9.0** (2025 testing framework)
- **pytest-playwright 0.7.1** (Playwright pytest integration)
- **httpx 0.28.1** (async HTTP client for API testing)

**Framework Design**:

```python
# PEP 723 inline dependencies for self-contained scripts
# /// script
# dependencies = [
#   "playwright>=1.56.0",
#   "pytest>=9.0.0",
#   "pytest-playwright>=0.7.0",
# ]
# ///

@pytest.mark.ui
class TestClickHouseUI:
    """Test suite for ClickHouse UI (port 5521)."""

    def test_ui_loads_successfully(self, page):
        """Test that UI homepage loads without errors."""
        page.goto(UI_URL, wait_until="domcontentloaded")
        page.screenshot(path="homepage.png", full_page=True)
        assert page.title(), "Page should have a title"
```

**Testing Approach**:

1. **HTTP API Tests** (`test_clickhouse_http.py`):
   - Root endpoint verification
   - Version query
   - Database listing
   - Table count
   - Error handling
   - JSON format output
   - Health check endpoint

2. **Web UI Tests** (`test_clickhouse_ui.py`):
   - Homepage loading
   - Metrics page (with known CTE bug detection)
   - Explorer sidebar visibility
   - Navigation (Queries, Tables tabs)
   - Server info display
   - Screenshot capture for all states

**Evidence Requirements**:

1. **Screenshot proof**: Mandatory 1280x720 PNG screenshots for all UI states
2. **Test output logs**: Full pytest report with timing and assertions
3. **Diagnostic reports**: Root cause analysis for any detected issues
4. **Autonomous execution**: Tests run headless by default, headed mode for debugging

**File Structure**:

```
tests/e2e/
├── conftest.py                  # Pytest Playwright configuration
├── pytest.ini                   # E2E-specific settings (no coverage)
├── test_clickhouse_http.py      # 8 HTTP API tests
├── test_clickhouse_ui.py        # 8 web UI tests
├── README.md                    # Framework documentation
├── DIAGNOSTIC_REPORT.md         # Detailed findings
├── TEST_RESULTS.md              # Test execution summary
└── screenshots/                 # Auto-captured screenshots
    ├── homepage.png
    ├── metrics_page.png
    └── explorer_sidebar.png
```

**Consequences**:

**Positive**:

- **Visual proof of functionality**: Screenshots verify UI renders correctly, not just that HTML loaded
- **Autonomous execution**: Zero manual intervention - tests run headless and capture all evidence
- **Latest 2025 tools**: Playwright 1.56+ with AI agents, pytest 9.0, httpx 0.28.1
- **Comprehensive coverage**: 16 tests (8 HTTP API + 8 UI) covering happy path, errors, edge cases
- **Self-contained scripts**: PEP 723 inline dependencies make tests portable and bootstrappable
- **Audit trail**: Test results + screenshots + diagnostic reports create permanent record
- **Bug detection**: Automatically identified "Missing columns: 'steps'" CTE bug in UI
- **Root cause documentation**: Diagnostic reports explain WHY failures occur, not just THAT they failed
- **Repeatable verification**: Run `uv run pytest tests/e2e/ -v` anytime to re-verify services
- **CI-ready**: Headless mode works in GitHub Actions without X server

**Negative**:

- **Browser dependency**: Requires Playwright browser installation (~300 MB Chromium)
- **Slower than unit tests**: 4.66 seconds total (vs sub-second for pure HTTP tests)
- **Network dependency**: Tests require live ClickHouse services running
- **Screenshot storage**: 3 screenshots = ~94 KB (minimal but not zero)
- **Learning curve**: Team needs to understand Playwright page API and pytest fixtures

**Neutral**:

- **Separate pytest.ini needed**: E2E tests can't use project-level pytest settings (coverage conflict)
- **Integration test marking**: Tests marked `@pytest.mark.ui` and `@pytest.mark.integration` for filtering
- **Dual execution modes**: Both pytest and standalone Python execution supported

**Alternatives Considered**:

1. **Selenium + pytest**: Rejected due to slower execution and older API design
2. **Manual curl + browser testing**: Rejected due to lack of repeatability and audit trail
3. **Puppeteer (Node.js)**: Rejected due to preference for Python tooling consistency
4. **Cypress**: Rejected due to JavaScript requirement and slower startup time

**Success Criteria** (all met):

- ✅ All tests passing (16 passed, 1 skipped)
- ✅ Screenshots captured automatically (3 screenshots, 1280x720 PNG)
- ✅ Execution time < 10 seconds (achieved 4.66 seconds)
- ✅ Zero manual intervention required (fully autonomous)
- ✅ Latest 2025 tool versions (Playwright 1.56+, pytest 9.0)
- ✅ Comprehensive documentation (README, DIAGNOSTIC_REPORT, TEST_RESULTS)
- ✅ Root cause analysis for known issues (CTE bug documented)
- ✅ Code quality standards met (ruff format + ruff check passing)

**Implementation Notes**:

**Installation**:

```bash
# Add to pyproject.toml
[project.optional-dependencies]
e2e = [
    "playwright>=1.56.0",
    "pytest-playwright>=0.7.0",
    "httpx>=0.28.0",
]

# Install dependencies
uv sync --extra e2e
uv run playwright install chromium
```

**Usage**:

```bash
# Run all E2E tests
uv run pytest tests/e2e/ -v

# Run HTTP API tests only
uv run pytest tests/e2e/test_clickhouse_http.py -v

# Run UI tests with visible browser (debugging)
uv run pytest tests/e2e/test_clickhouse_ui.py --headed

# Autonomous mode (no pytest)
uv run python tests/e2e/test_clickhouse_http.py
uv run python tests/e2e/test_clickhouse_ui.py
```

**Known Issues Detected**:

1. **"Missing columns: 'steps'" bug** (ClickHouse UI):
   - Root Cause: UI generates CTE query that ClickHouse 24.1.8 can't resolve inside `numbers()` function
   - Impact: Metrics dashboard chart doesn't load (cosmetic only)
   - Workaround: Use Queries tab instead of Metrics dashboard
   - Status: Documented in DIAGNOSTIC_REPORT.md

**References**:

- Playwright 1.56 Release: https://github.com/microsoft/playwright/releases/tag/v1.56.0
- pytest 9.0 Changelog: https://docs.pytest.org/en/stable/changelog.html
- PEP 723 Inline Dependencies: https://peps.python.org/pep-0723/
- Test Results: `tests/e2e/TEST_RESULTS.md`
- Diagnostic Report: `tests/e2e/DIAGNOSTIC_REPORT.md`

**Related Decisions**:

- ADR-0003: Error Handling - Strict Raise Policy (E2E tests follow same error handling)
- ADR-0009: GitHub Actions Automation (E2E tests can run in CI/CD)
