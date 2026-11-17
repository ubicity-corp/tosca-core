"""
What an embedding application adds to validation.

tosca-core validates TOSCA and runs no artifact: it evaluates the functions
TOSCA defines, which are its own code, and no function a profile implements
with an artifact, in Python or otherwise. An application that runs what it
validates can extend validation in two ways, both optional, by registering
from a module listed in EXTENSION_MODULES (bootstrap() imports them):

- **Implementation checks.** Each is called for every implementation
  artifact of an operation or function as validation reaches it, and
  refuses what the application cannot run -- an artifact type it has no way
  to execute, or an input name its artifacts cannot receive. Its errors are
  reported where the artifact is, like the core's own.

- **A function evaluator.** It evaluates a function a profile implements
  with an artifact, or says it cannot by raising CannotEvaluate.

- **An attribute-written check.** Onboarding asks whether a value an
  operation reads is guaranteed to be present. TOSCA's requiredness answers
  for properties; an attribute exists once an operation has written it, and
  which operations are certain to have run before the reading one depends
  on the order the application runs them in. Where a $get_attribute read by
  an operation is otherwise not guaranteed, the check is asked whether an
  earlier operation writes it.

With none of these, every implementation artifact is accepted as TOSCA allows it,
and a function a profile implements with an artifact is left unevaluated: a
validation clause built on one is recorded as not checked
(tosca_core.models.unchecked), never passed and never failed; and an
attribute an operation reads is guaranteed only by a value the templates
give it.
"""
from __future__ import annotations

from typing import Any, Callable, Optional

# check(artifact, type_name, operation, declaration) -> {key: message}
ImplementationCheck = Callable[[Any, str, Any, Any], dict]

# evaluator(signature, context, evaluated_args) -> value
FunctionEvaluator = Callable[[Any, Any, list], Any]

# check(node, tokens, through, reader) -> bool
AttributeWrittenCheck = Callable[[Any, list, list, tuple], bool]


class CannotEvaluate(Exception):
    """Raised by a function evaluator for a function it cannot evaluate;
    the function is then left unevaluated, as with no evaluator"""


_checks: list[ImplementationCheck] = []
_evaluator: Optional[FunctionEvaluator] = None
_attribute_written: Optional[AttributeWrittenCheck] = None


def register_implementation_check(check: ImplementationCheck) -> None:
    """Add a check run on every implementation artifact during validation.

    The check is called with the artifact, the qualified name of its
    artifact type, and, for an operation's implementation, the operation
    and its declaration (None for a function's). It returns a dict of
    errors, empty when the artifact is acceptable. Registering the same
    check again has no effect.
    """
    if check not in _checks:
        _checks.append(check)


def implementation_checks() -> list[ImplementationCheck]:
    """The registered implementation checks, in registration order"""
    return list(_checks)


def set_function_evaluator(evaluator: Optional[FunctionEvaluator]) -> None:
    """Install the evaluator for functions implemented by artifacts, or
    remove it with None"""
    global _evaluator
    _evaluator = evaluator


def function_evaluator() -> Optional[FunctionEvaluator]:
    """The evaluator installed for functions implemented by artifacts, or
    None"""
    return _evaluator


def set_attribute_written_check(check: Optional[AttributeWrittenCheck]) -> None:
    """Install the check that an attribute an operation reads is written by
    an operation certain to have run before it, or remove it with None.

    The check is called as check(node, tokens, through, reader): the node
    template, or the node type standing in for one, whose attribute is read;
    the path below it to the attribute; the kinds of the relationships the
    read followed from the reading entity (each 'CONTAINMENT', 'DEPENDENCY',
    'ASSOCIATION' or None), first 'SOURCE' when a relationship operation
    reads its source; and the reading operation as (interface name,
    operation name), both dash case. It returns True when the attribute is
    certain to be written before the read.
    """
    global _attribute_written
    _attribute_written = check


def attribute_written_check() -> Optional[AttributeWrittenCheck]:
    """The attribute-written check installed, or None"""
    return _attribute_written

