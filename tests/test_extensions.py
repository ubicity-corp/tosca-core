"""
What an embedding application adds to validation (tosca_core.extensions).

tosca-core runs no artifacts, and knows nothing of what runs them. An
application can register implementation checks, called for every
implementation artifact with its artifact type's qualified name, whose
errors join the artifact's own; and it can install an evaluator for
functions a profile implements with an artifact. With neither, any artifact
type is accepted, and such a function -- Python or not -- is left
unevaluated, as it is when an evaluator says it cannot evaluate it.

Artifacts and signatures are stand-ins; no database is used.
"""

from types import SimpleNamespace

import pytest

from tosca_core import extensions
from tosca_core.models.function_declaration import ToscaSignature
from tosca_core.validate.operation_implementation import (
    ToscaOperationImplementationValidator,
    operation_input_names,
    operation_output_names,
)


@pytest.fixture(autouse=True)
def nothing_registered(monkeypatch):
    monkeypatch.setattr(extensions, "_checks", [])
    monkeypatch.setattr(extensions, "_evaluator", None)


# ---------------------------------------------------------------------------
# Implementation checks
# ---------------------------------------------------------------------------

def _artifact(type_name):
    """An implementation artifact of the named type, as validation sees it"""
    return SimpleNamespace(
        name="impl",
        declaration=SimpleNamespace(type_entity=SimpleNamespace(qualified_name=type_name)))


def _check(artifact, operation=None):
    return ToscaOperationImplementationValidator().check_implementation(artifact, None, operation)


def test_with_no_checks_any_artifact_type_is_accepted():
    assert _check(_artifact("com.example:1.0:Anything")) == {}


def test_a_check_sees_the_type_name_and_its_errors_are_reported():
    seen = []

    def check(artifact, type_name, operation, declaration):
        seen.append((type_name, operation))
        return {"processor": f"cannot run '{type_name}'"}

    extensions.register_implementation_check(check)
    assert _check(_artifact("com.example:1.0:Script"), "op") == {
        "processor": "cannot run 'com.example:1.0:Script'"}
    assert seen == [("com.example:1.0:Script", "op")]


def test_the_errors_of_every_check_are_reported():
    extensions.register_implementation_check(lambda *args: {"a": "first"})
    extensions.register_implementation_check(lambda *args: {})
    extensions.register_implementation_check(lambda *args: {"b": "second"})
    assert _check(_artifact("t")) == {"a": "first", "b": "second"}


def test_registering_a_check_again_runs_it_once():
    calls = []

    def check(*args):
        calls.append(args)
        return {}

    extensions.register_implementation_check(check)
    extensions.register_implementation_check(check)
    _check(_artifact("t"))
    assert len(calls) == 1


def test_an_artifact_whose_type_does_not_resolve_is_left_to_its_own_validation():
    extensions.register_implementation_check(lambda *args: {"x": "should not run"})
    assert _check(SimpleNamespace(name="impl")) == {}


class Declared:
    def __init__(self, inputs=(), outputs=(), interface=None):
        self.inputs, self.outputs = list(inputs), list(outputs)
        self._containing_interface_declaration = interface
        self._containing_interface_type = None

    def get_input_declarations(self):
        return {name: None for name in self.inputs}

    def get_output_declarations(self):
        return {name: None for name in self.outputs}


def test_an_operations_names_include_its_interfaces_and_its_templates():
    declaration = Declared(inputs=["a"], outputs=["x"], interface=Declared(inputs=["b"], outputs=["y"]))
    template = SimpleNamespace(inputs={"c": 1}, outputs={"z": []})
    assert operation_input_names(template, declaration) == ["a", "b", "c"]
    assert operation_output_names(template, declaration) == ["x", "y", "z"]


# ---------------------------------------------------------------------------
# The function evaluator
# ---------------------------------------------------------------------------

class Signature:
    evaluate = ToscaSignature.evaluate
    intrinsics = {}
    result = None

    def __init__(self):
        self.function = SimpleNamespace(name="f")
        self.artifacts = ["f.py"]

    def resolve_templated_type(self, context, args, value_declaration):
        return None

    def evaluate_function_arguments(self, context, args, **kwargs):
        return args

    def function_expression(self, args, resolved_type):
        return {"$f": args}


def test_with_no_evaluator_the_function_is_left_unevaluated():
    assert extensions.function_evaluator() is None
    assert Signature().evaluate(None, [1]) == {"$f": [1]}


def test_an_evaluator_is_installed_and_removed():
    def evaluator(signature, context, args):
        return 42

    extensions.set_function_evaluator(evaluator)
    assert extensions.function_evaluator() is evaluator
    extensions.set_function_evaluator(None)
    assert extensions.function_evaluator() is None


def test_the_evaluator_is_given_the_signature_and_the_evaluated_arguments():
    seen = []

    def evaluator(signature, context, args):
        seen.append((signature.function.name, context, args))
        return 42

    extensions.set_function_evaluator(evaluator)
    assert Signature().evaluate("ctx", [1]) == 42
    assert seen == [("f", "ctx", [1])]


def test_a_function_the_evaluator_cannot_evaluate_is_left_unevaluated():
    def evaluator(signature, context, args):
        raise extensions.CannotEvaluate("not mine")

    extensions.set_function_evaluator(evaluator)
    assert Signature().evaluate(None, [1]) == {"$f": [1]}


def test_an_evaluator_that_fails_fails_the_evaluation():
    def evaluator(signature, context, args):
        raise RuntimeError("script exited 1")

    extensions.set_function_evaluator(evaluator)
    with pytest.raises(NotImplementedError, match="script exited 1"):
        Signature().evaluate(None, [1])
