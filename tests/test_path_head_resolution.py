"""
How a TOSCA path's named head is resolved.

Against a service of templates there is one template whatever its count,
and a declaration lookup wants it. Against a service of instances, which
representations exist and how they are named is the application's: the
core asks the service's resolve_node(name, index, select) (since 0.4.0;
before, the core parsed the Ubicity orchestrator's 'name:N' names itself).
What TOSCA defines stays here: an index is passed on as written, ALL as
ALL, and a negative one is refused. Only get_entity lets the service answer
for a selectable template (select).

Services are stand-ins; no database is used.
"""

from types import SimpleNamespace

import pytest

import tosca_core.models.exceptions as te
from tosca_core.models.path import ToscaPath


class Instances:
    """A service of instances: records what it was asked"""

    def __init__(self):
        self.asked = []

    def resolve_node(self, name, index, select):
        self.asked.append((name, index, select))
        return f"{name}@{index}"


def context(service):
    return SimpleNamespace(service=service)


def test_a_service_of_templates_answers_from_its_nodes_whatever_the_index():
    templates = SimpleNamespace(nodes={"web": "the web template"})
    for path in (["web", "port"], ["web", 2, "port"], ["web", "ALL", "port"]):
        assert ToscaPath(path, head_index=True).get_entity_declaration(
            context(templates)) == "the web template"


@pytest.mark.parametrize("path, index", [
    (["web", "port"], None),
    (["web", 2, "port"], 2),
    (["web", "ALL", "port"], "ALL"),
])
def test_a_service_of_instances_is_asked_with_the_index(path, index):
    instances = Instances()
    assert ToscaPath(path, head_index=True).get_entity_declaration(
        context(instances)) == f"web@{index}"
    assert instances.asked == [("web", index, False)]


def test_only_get_entity_lets_a_selectable_template_answer():
    instances = Instances()
    ToscaPath(["web", "port"], head_index=True).get_entity(context(instances))
    assert instances.asked == [("web", None, True)]


def test_a_negative_index_is_refused_before_the_service_is_asked():
    instances = Instances()
    with pytest.raises(te.InvalidPathError, match="negative"):
        ToscaPath(["web", -1, "port"], head_index=True).get_entity(context(instances))
    assert instances.asked == []


def test_reserved_heads_do_not_reach_the_service():
    instances = Instances()
    ctx = SimpleNamespace(service=instances, SELF=lambda: "me")
    assert ToscaPath(["SELF", "port"], head_index=True).get_entity(ctx) == "me"
    assert instances.asked == []
