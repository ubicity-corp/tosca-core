"""
A function a profile implements returns a value of the result its signature
declares, or its evaluation fails.

The presence check counts such a function as present, so an implementation
returning null must not pass as a value. A signature that declares no result
may return anything, null included. Only null counts as no value: an empty
string is what $to_lowercase of an empty string returns.

DB-free: the real evaluate runs on a stand-in signature.
"""

from types import SimpleNamespace

import pytest

import tosca_core.models.exceptions as te
from tosca_core import extensions
from tosca_core.models.function_declaration import ToscaSignature


@pytest.fixture(autouse=True)
def evaluator(monkeypatch):
    """An implementation runs only where a function evaluator is installed;
    with none, the function is left unevaluated. This one returns what the
    stand-in signature says its implementation returns."""
    monkeypatch.setattr(extensions, "_evaluator",
                        lambda signature, context, args: signature.returns)


class Signature:
    evaluate = ToscaSignature.evaluate
    intrinsics = {}

    def __init__(self, returns, result=True):
        self.function = SimpleNamespace(name='f')
        self.artifacts = ['f.py']
        self.result = SimpleNamespace() if result else None
        self.returns = returns

    def resolve_templated_type(self, context, args, value_declaration):
        return None

    def evaluate_function_arguments(self, context, args, **kwargs):
        return args


@pytest.mark.parametrize('value', ['x', '', False, 0, [], {}])
def test_a_declared_result_with_a_value_is_returned(value):
    assert Signature(value).evaluate(None, []) == value


def test_a_declared_result_without_a_value_fails():
    with pytest.raises(te.ProcessorError, match=r'\$f returned no value'):
        Signature(None).evaluate(None, [])


def test_a_signature_without_a_result_may_return_null():
    assert Signature(None, result=False).evaluate(None, []) is None
