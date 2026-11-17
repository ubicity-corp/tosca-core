"""
Whether a requirement definition's relationship type may be left out.

TOSCA 1.3 lets a requirement definition leave out its relationship type, and
the orchestrator then picks one whose valid capability types include the
requirement's capability. TOSCA 2.0 makes the relationship mandatory (section
8.4), so there a requirement definition that names none is refused rather than
given one. A refinement of an inherited requirement takes its parent's type
before this check runs, so it is not affected.

The node type, requirement and relationship type are stand-ins; no database is
used.
"""

from types import SimpleNamespace

from tosca_core.validate import get_validator


def links_to():
    return SimpleNamespace(name="LinksTo", is_valid_capability_type=lambda capability: True)


def node_type(relationship_type):
    profile = SimpleNamespace(get_relationship_types=lambda: {"LinksTo": relationship_type})
    return SimpleNamespace(name="BaseNode", profile=profile)


def requirement(tosca_version):
    return SimpleNamespace(name="link", tosca_version=tosca_version,
                           target_capability_type=SimpleNamespace(name="Linkable"))


def test_tosca_1_3_finds_the_relationship_type():
    relationship_type = links_to()
    declaration = requirement("tosca_simple_yaml_1_3")
    errors = get_validator('ToscaRelationshipDeclaration').validate_implied_type(
        node_type(relationship_type), declaration)
    assert errors == {}
    assert declaration.type_entity is relationship_type


def test_tosca_2_0_refuses_a_requirement_without_a_relationship_type():
    declaration = requirement("tosca_2_0")
    errors = get_validator('ToscaRelationshipDeclaration').validate_implied_type(
        node_type(links_to()), declaration)
    assert errors == "no relationship type"
    assert not hasattr(declaration, "type_entity")
