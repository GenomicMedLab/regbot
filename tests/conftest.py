"""Provide basic test configuration and fixture root."""

import logging
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def fixtures_dir():
    """Provide path to fixtures directory."""
    return Path(__file__).resolve().parent / "fixtures"


def pytest_addoption(parser):
    """Add custom commands to pytest invocation.

    See https://docs.pytest.org/en/8.1.x/reference/reference.html#parser
    """
    parser.addoption(
        "--verbose-logs",
        action="store_true",
        default=False,
        help="show noisy module logs",
    )


def pytest_configure(config):
    """Configure pytest setup."""
    if not config.getoption("--verbose-logs"):
        logging.getLogger("requests_mock.adapter").setLevel(logging.INFO)
