"""
What the presence check answers when it cannot say "present".

The check asks whether a value is guaranteed to be present at onboarding
(`is_return_value_present`, `is_value_present`, `validate_value_presence`,
`is_property_template_present`). It answers True or False, and callers branch
on that. Two answers need more than False, because the author has to be told
something other than "this value may be missing":

  * the check could not decide -- a path it cannot resolve, an error inside
    it: `Undecided`, with the reason;
  * the value refers to itself, directly or through others: `Circular`,
    with the values in the loop.

Both are false, so every caller that branches on the answer behaves exactly
as it does for "not present"; only the callers that word the error ask for
the reason (`explain`).
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator, Optional


class NotDecided:
    """A false answer that says why it is not True."""

    def __bool__(self) -> bool:
        return False

    def describe(self, subject: str) -> str:
        raise NotImplementedError


class Undecided(NotDecided):
    """The check could not decide whether the value is present."""

    def __init__(self, reason: str) -> None:
        self.reason = reason

    def describe(self, subject: str) -> str:
        return f"cannot tell whether {subject} is present: {self.reason}"

    def __repr__(self) -> str:
        return f"Undecided({self.reason!r})"


class Circular(NotDecided):
    """The value is defined in terms of itself."""

    def __init__(self, chain: list[str]) -> None:
        self.chain = chain

    def describe(self, subject: str) -> str:
        return f"{subject} refers to itself: {' -> '.join(self.chain)}"

    def __repr__(self) -> str:
        return f"Circular({self.chain!r})"


class Message(str):
    """An error message from `validate_value_presence` that also carries the
    answer it reports, so a caller one level up can pass that answer on
    rather than a plain False."""

    def __new__(cls, text: str, answer: NotDecided) -> "Message":
        message = super().__new__(cls, text)
        message.answer = answer
        return message


def explain(answer: Any, subject: str, otherwise: str) -> str:
    """The error for a value found not present: the reason when the check did
    not decide or found a loop, 'otherwise' when the value may simply be
    absent."""
    if isinstance(answer, NotDecided):
        return answer.describe(subject)
    return otherwise


def answer_of(message: Optional[str]) -> Any:
    """What a `validate_value_presence` error stands for: the answer it
    carries, or plain False."""
    return getattr(message, "answer", False)


# The values being resolved, innermost last, as (key, label) pairs. A value
# the check reaches again while resolving it is a loop.
_resolving: ContextVar[tuple] = ContextVar("presence_resolving", default=())


def enter(key: Any, label: str) -> Any:
    """Start resolving a value. Answers the token to pass to `leave`, or a
    `Circular` when the value is already being resolved."""
    stack = _resolving.get()
    for index, (seen, _) in enumerate(stack):
        if seen == key:
            return Circular([name for _, name in stack[index:]] + [label])
    return _resolving.set(stack + ((key, label),))


def leave(token: Any) -> None:
    _resolving.reset(token)


# The values whose presence is being checked, outermost first, as
# (declaration, context) pairs: what a warning names as the value it is
# about. Rendered only when a warning is logged.
_checking: ContextVar[tuple] = ContextVar("presence_checking", default=())


@contextmanager
def checking(declaration: Any, context: Any) -> Iterator[None]:
    """Record that the presence of 'declaration''s value is being checked
    in 'context', for the duration of the block."""
    token = _checking.set(_checking.get() + ((declaration, context),))
    try:
        yield
    finally:
        _checking.reset(token)


def where() -> str:
    """The values being checked, for a warning: ' (for input 'x' of
    Standard.delete in 'Server')', each value a read leads to after the
    first, or '' outside any check."""
    labels = []
    for declaration, context in _checking.get():
        label = describe(declaration, context)
        if not labels or labels[-1] != label:
            labels.append(label)
    return f" (for {' / '.join(labels)})" if labels else ""


def read_by() -> Optional[tuple]:
    """The operation that reads the value being checked, when that value is
    an input: (interface name, operation name) for an input of an operation,
    (interface name, None) for an input of an interface, which each of its
    operations receives. None when the innermost value checked is not an
    input of an operation or an interface. An interface name that cannot be
    found is None."""
    stack = _checking.get()
    if not stack:
        return None
    declaration, context = stack[-1]
    if getattr(declaration, 'role', None) != 'INPUT':
        return None
    context_interface = getattr(context, 'name', None) \
        if type(context).__name__ in ('ToscaInterfaceTemplate', 'ToscaInterfaceDeclaration') \
        else None
    operation = _safely(lambda: declaration._containing_operation_declaration)
    if operation is not None:
        interface = _safely(lambda: operation._containing_interface_declaration)
        return (getattr(interface, 'name', None) or context_interface, operation.name)
    if _is_interface_or_operation(context):
        return (context_interface, None)
    return None


_KINDS = {'INPUT': 'input', 'OUTPUT': 'output', 'PROPERTY': 'property',
          'ATTRIBUTE': 'attribute'}


def describe(declaration: Any, context: Any) -> str:
    """'input 'x' of Standard.delete in 'Server'': the kind and name of the
    value, the operation it is an input of when it is one, and the type or
    template it is checked in."""
    label = f"{_KINDS.get(getattr(declaration, 'role', None), 'value')} " \
            f"'{getattr(declaration, 'name', declaration)}'"
    operation = _safely(lambda: declaration._containing_operation_declaration)
    if operation is not None:
        interface = _safely(lambda: operation._containing_interface_declaration or
                            operation._containing_interface_type)
        prefix = f"{interface.name}." if interface is not None else ""
        label += f" of {prefix}{operation.name}"
    # An interface or operation as the context stands for the type or
    # template it is declared in; an input of the interface itself says so.
    owner = context
    if _is_interface_or_operation(context):
        if operation is None and not hasattr(context, '_containing_interface_declaration'):
            label += f" of {getattr(context, 'name', context)}"
        owner = _safely(lambda: context.SELF()) or \
            _safely(lambda: context._containing_type) or context
    return label + f" in '{getattr(owner, 'name', owner)}'"


_INTERFACES_AND_OPERATIONS = ('ToscaInterfaceTemplate', 'ToscaInterfaceDeclaration',
                              'ToscaOperationTemplate', 'ToscaOperationDeclaration')


def _is_interface_or_operation(context: Any) -> bool:
    return (type(context).__name__ in _INTERFACES_AND_OPERATIONS or
            hasattr(context, '_containing_interface_declaration'))


def _safely(get: Any) -> Any:
    try:
        return get()
    except Exception:
        return None
