"""
No template holds a loop of dependencies or containments.

A loop has no order to build or tear down in. One formed by explicit
requirements is in the template, and onboarding refuses it, naming the loop.
Associations order nothing, and close no loop. One a dangling requirement
would close appears only at fulfillment, which the orchestrator checks.

Templates are stand-ins; no database is used.
"""

from types import SimpleNamespace

from tosca_core.validate.service_template import ToscaServiceTemplateValidator


def requirement(target, kind='DEPENDENCY', dangling=False):
    return SimpleNamespace(
        is_dangling=lambda: dangling,
        declaration=SimpleNamespace(type_entity=SimpleNamespace(get_kind=lambda: kind)),
        target_node=SimpleNamespace(name=target))


def templates(**edges):
    """Node templates named by keyword, each with requirements on the listed targets."""
    return {name: SimpleNamespace(relationships=list(requirements))
            for name, requirements in edges.items()}


def loop_in(node_templates):
    return ToscaServiceTemplateValidator.find_dependency_loop(None, node_templates)


def test_a_loop_of_explicit_requirements_is_named():
    assert loop_in(templates(a=[requirement('b')], b=[requirement('a')])) == ['a', 'b', 'a']


def test_a_node_that_requires_itself_is_a_loop():
    assert loop_in(templates(a=[requirement('a', kind='CONTAINMENT')])) == ['a', 'a']


def test_a_chain_is_not_a_loop():
    assert loop_in(templates(a=[requirement('b')], b=[requirement('c')], c=[])) is None


def test_an_association_closes_no_loop():
    assert loop_in(templates(a=[requirement('b')], b=[requirement('a', kind='ASSOCIATION')])) is None


def test_a_dangling_requirement_is_left_to_fulfillment():
    assert loop_in(templates(a=[requirement('b')], b=[requirement('a', dangling=True)])) is None
