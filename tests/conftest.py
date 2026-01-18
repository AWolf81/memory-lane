"""
Pytest configuration and fixtures for MemoryLane tests.
"""

import os
import pytest


def is_ci():
    """Check if running in CI environment."""
    return os.environ.get("CI") == "true" or os.environ.get("GITHUB_ACTIONS") == "true"


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "local_only: mark test to run only locally (skipped in CI)"
    )


def pytest_collection_modifyitems(config, items):
    """Skip local_only tests when running in CI."""
    if not is_ci():
        return

    skip_ci = pytest.mark.skip(reason="Test requires local resources (skipped in CI)")
    for item in items:
        if "local_only" in item.keywords:
            item.add_marker(skip_ci)


@pytest.fixture
def is_local():
    """Fixture to check if running locally (not in CI)."""
    return not is_ci()


@pytest.fixture
def skip_in_ci():
    """Fixture to skip test if running in CI."""
    if is_ci():
        pytest.skip("Skipped in CI - requires local resources")
