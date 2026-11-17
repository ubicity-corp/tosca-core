"""
Validation clauses that could not be checked.

A validation clause is evaluated where validation runs. A function in it
that cannot be evaluated there -- above all a function a profile
implements with an artifact, Python or not, when no function evaluator is
installed (tosca_core.extensions) -- leaves the clause as an unevaluated
expression. Such a clause is neither passed nor failed: the value is
accepted, and the clause is recorded as not checked, so that a caller can
say so rather than report a value that was never checked as valid.

A caller that wants the record collects it around a validation:

    with unchecked.collect() as not_checked:
        errors = validate_csar(...)
    # not_checked: a list of NotChecked
"""
from __future__ import annotations

__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2015-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

import logging
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator, NamedTuple, Optional

logger: logging.Logger = logging.getLogger(__name__)


class NotChecked(NamedTuple):
    """One validation clause that could not be evaluated"""
    subject: str                # what the clause validates, e.g. "property 'number'"
    value: str                  # the value it was to check, as shown
    functions: tuple[str, ...]  # the functions left unevaluated, e.g. ('$in_range',)


_collected: ContextVar[Optional[list]] = ContextVar("tosca_core_unchecked", default=None)


@contextmanager
def collect() -> Iterator[list[NotChecked]]:
    """Collect the clauses not checked while the block runs, each once"""
    found: list[NotChecked] = []
    token = _collected.set(found)
    try:
        yield found
    finally:
        _collected.reset(token)


def verdict(result: Any, subject: str, value: Any) -> Any:
    """The verdict of a validation clause that evaluated to 'result'.

    An evaluated clause's result is returned as it is. An unevaluated one
    is recorded as not checked and counts as satisfied.

    Args:
      result: what evaluating the clause returned
      subject: what the clause validates, for the record
      value: the value the clause was to check

    Returns:
      result, or True for a clause that could not be evaluated
    """
    from tosca_core.models.function_declaration import is_function, resolve_function_names
    if not is_function(result):
        return result
    readable = resolve_function_names(result)
    record = NotChecked(subject, _shown(value), tuple(sorted(_function_names(readable))))
    logger.info("%s: validation of %s not checked: %s could not be evaluated",
                record.subject, record.value, ", ".join(record.functions))
    found = _collected.get()
    if found is not None and record not in found:
        found.append(record)
    return True


def _function_names(value: Any) -> set[str]:
    """The '$name' keys anywhere in a readable expression"""
    names: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(key, str) and key.startswith('$') and not key.startswith('$('):
                names.add(key)
            names |= _function_names(item)
    elif isinstance(value, list):
        for item in value:
            names |= _function_names(item)
    return names


def _shown(value: Any) -> str:
    """A value as a report shows it, cut short when long"""
    text = repr(value)
    return text if len(text) <= 60 else text[:57] + "..."
