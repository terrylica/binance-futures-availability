# /// script
# dependencies = [
#   "playwright>=1.56.0",
#   "pytest>=9.0.0",
#   "pytest-playwright>=0.7.0",
# ]
# ///
"""
Pytest configuration for E2E tests with Playwright.

This module configures Playwright for autonomous web UI testing with:
- Screenshot capture on failure
- Headless mode by default
- Configurable browser (chromium, firefox, webkit)
"""

import pytest


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """Configure browser context with optimized settings."""
    return {
        **browser_context_args,
        "viewport": {"width": 1920, "height": 1080},
        "ignore_https_errors": True,  # For local development
    }


@pytest.fixture
def context(browser):
    """Create isolated browser context for each test."""
    context = browser.new_context()
    yield context
    context.close()


def pytest_addoption(parser):
    """Add custom CLI options for E2E tests."""
    # Note: --headed is already provided by pytest-playwright
    # Note: --slowmo is already provided by pytest-playwright
