"""
A validation clause that could not be evaluated is not checked.

Evaluating a clause whose function cannot be evaluated where validation runs
-- a function a profile implements with an artifact, with no function
evaluator installed -- returns the unevaluated expression. That expression used to
count as satisfied because it is truthy, so the value read as checked. It
still does not fail the value, but it is recorded as not checked, once, for
whoever collects around the validation.

Signatures are stand-ins; no database is used.
"""

from types import SimpleNamespace

import pytest

import tosca_core.models.function_declaration as fd
from tosca_core.models import unchecked


@pytest.fixture(autouse=True)
def signatures(monkeypatch):
    names = {17: "in_range", 3: "and"}
    monkeypatch.setattr(fd, "get_signature",
                        lambda sig_id: SimpleNamespace(function=SimpleNamespace(name=names[sig_id])))


@pytest.mark.parametrize("result", [True, False, None])
def test_an_evaluated_clause_keeps_its_result(result):
    with unchecked.collect() as found:
        assert unchecked.verdict(result, "property 'number'", 50) is result
    assert found == []


def test_an_unevaluated_clause_is_satisfied_and_recorded():
    with unchecked.collect() as found:
        assert unchecked.verdict({"$(17)": [50, [1, 10]]}, "property 'number'", 50) is True
    assert found == [unchecked.NotChecked("property 'number'", "50", ("$in_range",))]


def test_every_function_left_in_the_clause_is_named():
    clause = {"$(3)": [{"$(17)": [50, [1, 10]]}, {"$(17)": [50, [0, 99]]}]}
    with unchecked.collect() as found:
        unchecked.verdict(clause, "data type 'Port'", 50)
    assert found[0].functions == ("$and", "$in_range")


def test_a_clause_evaluated_twice_is_recorded_once():
    with unchecked.collect() as found:
        for _ in range(2):
            unchecked.verdict({"$(17)": [50, [1, 10]]}, "property 'number'", 50)
    assert len(found) == 1


def test_nothing_is_recorded_outside_a_collection():
    assert unchecked.verdict({"$(17)": [50, [1, 10]]}, "property 'number'", 50) is True
    with unchecked.collect() as found:
        pass
    assert found == []


def test_a_long_value_is_cut_short():
    with unchecked.collect() as found:
        unchecked.verdict({"$(17)": ["x" * 100, ["a", "z"]]}, "property 'name'", "x" * 100)
    assert len(found[0].value) == 60 and found[0].value.endswith("...")
