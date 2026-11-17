"""
Onboarding warns about two requirements of a substituted node that the
substitution does not carry as the operational model expects.

A substituting template warns about each containment requirement of the type
it substitutes for that its substitution mappings do not map: the containment
then applies to the substituted node as a whole. A dependency or association
left unmapped, and a mapped containment, are not reported.

A node template with the 'substitute' directive warns about each requirement
whose relationship implements an operation, from its type or from the
template's own interface assignment, whatever the relationship's kind: the
substituted node holds no resource for the operation to act on.

DB-free: the real validator methods run on stand-in types and templates.
"""

from types import SimpleNamespace

import pytest

from tosca_core.validate.node_template import ToscaNodeTemplateValidator
from tosca_core.validate.substitution_mappings import ToscaSubstitutionMappingsValidator


# Unmapped containment requirements

def requirement(name, kind):
    relationship_type = SimpleNamespace(get_kind=lambda: kind)
    return SimpleNamespace(name=name, type_entity=relationship_type)


def node_type(*requirements):
    return SimpleNamespace(name='Platform', get_requirement_declarations=lambda: list(requirements))


def containment_warnings(node_type, mappings, caplog):
    validator = ToscaSubstitutionMappingsValidator.__new__(ToscaSubstitutionMappingsValidator)
    substitution_mappings = SimpleNamespace(requirements=mappings)
    with caplog.at_level('WARNING'):
        validator.warn_unmapped_containment(node_type, substitution_mappings)
    return [r.getMessage() for r in caplog.records if 'containment requirement' in r.getMessage()]


def test_an_unmapped_containment_requirement_warns(caplog):
    warnings = containment_warnings(node_type(requirement('host', 'CONTAINMENT')), [], caplog)
    assert len(warnings) == 1
    assert "'Platform'" in warnings[0] and "'host'" in warnings[0]


@pytest.mark.parametrize('key', ['host', ('host', 1)])
def test_a_mapped_containment_requirement_does_not_warn(key, caplog):
    mappings = [{key: ['server', 'host']}]
    assert not containment_warnings(node_type(requirement('host', 'CONTAINMENT')), mappings, caplog)


@pytest.mark.parametrize('kind', ['DEPENDENCY', 'ASSOCIATION'])
def test_an_unmapped_requirement_of_another_kind_does_not_warn(kind, caplog):
    assert not containment_warnings(node_type(requirement('uses', kind)), [], caplog)


def test_mappings_with_no_requirements_still_warn(caplog):
    validator = ToscaSubstitutionMappingsValidator.__new__(ToscaSubstitutionMappingsValidator)
    with caplog.at_level('WARNING'):
        validator.warn_unmapped_containment(node_type(requirement('host', 'CONTAINMENT')),
                                            SimpleNamespace())
    assert any('containment requirement' in r.getMessage() for r in caplog.records)


def test_only_the_unmapped_one_of_several_warns(caplog):
    platform = node_type(requirement('host', 'CONTAINMENT'), requirement('storage', 'CONTAINMENT'))
    warnings = containment_warnings(platform, [{('host', 1): ['server', 'host']}], caplog)
    assert len(warnings) == 1 and "'storage'" in warnings[0]


# Operations on the relationships of a substituted node

class Interface:
    """An interface template: declared operations, the template's own, and
    which of them have an implementation."""

    def __init__(self, declared=(), assigned=(), implemented=()):
        self.declaration = SimpleNamespace(
            get_operation_declarations=lambda: {name: None for name in declared})
        self.operations = {name: None for name in assigned}
        self.implemented = set(implemented)

    def get_operation_implementation(self, name):
        return ['artifact'] if name in self.implemented else []


def operation_warnings(interfaces, caplog):
    validator = ToscaNodeTemplateValidator.__new__(ToscaNodeTemplateValidator)
    relationship = SimpleNamespace(name='host', interfaces=interfaces)
    node_template = SimpleNamespace(name='pair', requirements=[relationship])
    with caplog.at_level('WARNING'):
        validator.warn_operations_on_substituted_requirements(node_template)
    return [r.getMessage() for r in caplog.records if 'is substituted' in r.getMessage()]


def test_an_operation_the_type_implements_warns(caplog):
    configure = Interface(declared=['pre-configure-source', 'remove-target'],
                          implemented=['pre-configure-source'])
    warnings = operation_warnings({'configure': configure}, caplog)
    assert len(warnings) == 1
    assert "'pair'" in warnings[0] and "'host'" in warnings[0]
    assert "'configure.pre-configure-source'" in warnings[0]
    assert 'remove-target' not in warnings[0]


def test_an_operation_the_template_implements_warns(caplog):
    configure = Interface(declared=['post-configure-source'], assigned=['post-configure-source'],
                          implemented=['post-configure-source'])
    assert operation_warnings({'configure': configure}, caplog)


def test_declared_operations_without_implementations_do_not_warn(caplog):
    configure = Interface(declared=['pre-configure-source', 'remove-target'])
    assert not operation_warnings({'configure': configure}, caplog)


def test_a_relationship_with_no_interfaces_does_not_warn(caplog):
    assert not operation_warnings({}, caplog)
