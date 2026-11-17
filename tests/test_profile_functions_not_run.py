"""
tosca-core runs no function a profile implements.

It evaluates the functions TOSCA defines, which are its own code, and
leaves a function a profile implements with an artifact unevaluated, in
Python or otherwise, unless an embedding application installs an evaluator
(tosca_core.extensions). Validating a template therefore never runs code a
profile ships. Before 0.4.0 the core ran Python implementations itself;
these tests pin that it no longer does, whatever the artifact type.

Signatures are stand-ins; no database is used.
"""

from types import SimpleNamespace

import pytest

from tosca_core import extensions
from tosca_core.constants import constants
from tosca_core.models.function_declaration import ToscaSignature

PYTHON_TYPES = (
    "http://docs.oasis-open.org/tosca/ns/simple/yaml/1.3:tosca.artifacts.Implementation.Python",
    "community.tosca.core:0.2:Python",
    "org.example:1.0:Bash",
)


class Signature:
    """A signature of a function a profile implements with an artifact,
    borrowing ToscaSignature.evaluate (not a mapped subclass, which would
    configure the mappers before every model is imported)"""
    evaluate = ToscaSignature.evaluate
    intrinsics = {}

    def __init__(self, type_name):
        artifact = SimpleNamespace(
            declaration=SimpleNamespace(type_entity=SimpleNamespace(qualified_name=type_name)),
            retrieve=lambda: pytest.fail("the artifact was retrieved"))
        self.function = SimpleNamespace(name="between")
        self.artifacts = [artifact]
        self.result = None

    def resolve_templated_type(self, context, args, value_declaration):
        return None

    def evaluate_function_arguments(self, context, args, **kwargs):
        return args

    def function_expression(self, args, resolved_type):
        return {"$between": args}


@pytest.fixture(autouse=True)
def no_evaluator(monkeypatch):
    monkeypatch.setattr(extensions, "_evaluator", None)


@pytest.mark.parametrize("type_name", PYTHON_TYPES)
def test_the_function_is_left_unevaluated(type_name):
    assert Signature(type_name).evaluate(None, [5, [1, 10]]) == {"$between": [5, [1, 10]]}


def test_there_is_no_evaluator_of_the_cores_own():
    assert extensions.function_evaluator() is None


def test_running_python_functions_is_not_a_setting():
    assert not hasattr(constants, "RUN_PYTHON_FUNCTIONS")
    with pytest.raises(TypeError):
        constants.configure(RUN_PYTHON_FUNCTIONS=True)


def test_the_core_has_no_python_function_runner():
    with pytest.raises(ImportError):
        import tosca_core.python_functions  # noqa: F401
