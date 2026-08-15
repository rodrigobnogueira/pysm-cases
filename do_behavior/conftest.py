"""Test helpers for the do-behavior case.

This case runs behaviors on background threads, so its tests must never rely
on `time.sleep()` to "probably" be long enough. Everything waits on a
condition instead, with a hard timeout so a broken behavior fails the test
fast instead of hanging the suite.
"""

import time
from collections.abc import Callable
from typing import TypeVar

import pytest

T = TypeVar("T")

DEFAULT_TIMEOUT = 2.0
"""Seconds a `wait_until` call waits before declaring the condition failed."""

POLL_INTERVAL = 0.005
"""Seconds between two evaluations of the predicate."""


def _wait_until(
    predicate: Callable[[], T],
    timeout: float = DEFAULT_TIMEOUT,
    interval: float = POLL_INTERVAL,
    message: str | None = None,
) -> T:
    """Poll `predicate` until it returns a truthy value and return that value.

    Raises an `AssertionError` once `timeout` seconds have elapsed, so a test
    that waits for something that never happens fails with a clear message
    instead of blocking the suite.
    """
    deadline = time.monotonic() + timeout
    while True:
        result = predicate()
        if result:
            return result
        if time.monotonic() >= deadline:
            raise AssertionError(
                message or f"condition was not met within {timeout}s"
            )
        time.sleep(interval)


@pytest.fixture
def wait_until() -> Callable[..., object]:
    """Expose `_wait_until` to tests as a fixture."""
    return _wait_until
