"""
Per-validation-call context, threaded via contextvars so that
validators (which are looked up as singletons) can read options set
by the action layer without having to add parameters to every
validate_* method.
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2026, Ubicity Corp."
__email__ = "info@ubicity.com"

import contextlib
import contextvars
from typing import Iterator


_skip_file_checks: contextvars.ContextVar[bool] = contextvars.ContextVar(
    'skip_file_checks', default=False)


def skip_file_checks() -> bool:
    """Return True when the current validation run should skip
    existence checks against artifact files (e.g. for artifacts on
    unreachable networks).
    """
    return _skip_file_checks.get()


@contextlib.contextmanager
def validation_options(*, skip_file_checks: bool = False) -> Iterator[None]:
    """Context manager that sets per-call validation options for the
    duration of the block. Resets the previous values on exit.
    """
    token = _skip_file_checks.set(skip_file_checks)
    try:
        yield
    finally:
        _skip_file_checks.reset(token)
