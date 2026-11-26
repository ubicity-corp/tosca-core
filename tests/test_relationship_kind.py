"""
How a relationship type's kind is found.

A type states its kind in ``metadata: {relationship-kind: ...}``, as the
TOSCA community does; failing that, it takes its parent type's kind, and a
type with neither and no parent is a DEPENDENCY. The metadata is read by
``get_kind()`` itself, not only copied in by validation, so a type has its
kind whether or not it has been validated. The ``kind:`` keyname, once a
Ubicity extension, is refused by both grammars, naming the metadata
spelling instead (0.4.0).

Relationship types are stand-ins carrying ToscaRelationshipType's own
``get_kind()``; no database is used.
"""

import pytest

from tosca_core.models.relationship_type import ToscaRelationshipType
from tosca_core.schema.v1.relationship_type import relationship_type_schema as v1_schema
from tosca_core.schema.v2.relationship_type import relationship_type_schema as v2_schema


class RelationshipType:
    get_kind = ToscaRelationshipType.get_kind
    default_kind = ToscaRelationshipType.default_kind

    def __init__(self, kind=None, meta_data=None, parent=None):
        self._kind, self._meta_data, self._parent = kind, meta_data, parent

    @property
    def kind(self):
        if self._kind is None:
            raise AttributeError("no kind")
        return self._kind

    @property
    def meta_data(self):
        if not self._meta_data:
            raise AttributeError("no meta_data")
        return self._meta_data

    @property
    def parent(self):
        if self._parent is None:
            raise AttributeError("no parent")
        return self._parent


def test_the_kind_validation_copied_from_metadata():
    assert RelationshipType(kind="CONTAINMENT").get_kind() == "CONTAINMENT"


def test_the_metadata_spelling_without_validation():
    relationship_type = RelationshipType(meta_data={"relationship_kind": "association"})
    assert relationship_type.get_kind() == "ASSOCIATION"


@pytest.mark.parametrize("schema", [v1_schema, v2_schema], ids=["1.3", "2.0"])
def test_the_kind_keyname_is_refused_naming_metadata(schema):
    errors = schema.validate({"derived_from": "DependsOn", "kind": "CONTAINMENT"})
    assert "relationship-kind: CONTAINMENT" in str(errors["kind"])


@pytest.mark.parametrize("schema", [v1_schema, v2_schema], ids=["1.3", "2.0"])
def test_the_kind_in_metadata_is_accepted(schema):
    assert schema.validate({"derived_from": "DependsOn",
                            "metadata": {"relationship_kind": "CONTAINMENT"}}) == {}


def test_metadata_without_a_kind_falls_through_to_the_parent():
    parent = RelationshipType(meta_data={"relationship_kind": "CONTAINMENT"})
    child = RelationshipType(meta_data={"version": "1"}, parent=parent)
    assert child.get_kind() == "CONTAINMENT"


def test_a_type_inherits_its_parents_metadata_kind():
    parent = RelationshipType(meta_data={"relationship_kind": "ASSOCIATION"})
    assert RelationshipType(parent=parent).get_kind() == "ASSOCIATION"


def test_no_kind_anywhere_is_a_dependency():
    assert RelationshipType().get_kind() == "DEPENDENCY"
