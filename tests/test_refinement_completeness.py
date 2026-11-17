"""
Refinement-completeness tests.

``get_unmerged_fields`` answers the question the validation walk asks wherever it is told a
refinement was completed before validation began: would merging the declaration it refines in
again still copy anything? A completed refinement answers "nothing".

The check exists because the reads that used to resolve through the augmentation chain are gone:
refinements are completed in a pass of their own before validation. An incomplete declaration no longer produces an error on the way through; it answers with
whatever it holds, which is a missing type, default or validation.

Validations are deliberately not checked: ``merge_augmented_validations`` combines rather than
fills, so it always has something left to do, which is what ``test_merge_idempotency.py`` pins.

DB-free: the methods are called on duck-typed declarations carrying the fields the check reads.
"""

import pytest

from tosca_core.models.declaration import ToscaDeclaration
from tosca_core.models.property_declaration import ToscaPropertyDeclaration as PD


class Decl:
    """A declaration carrying every field the check reads, all unset by default."""

    merged_fields = PD.merged_fields
    get_unmerged_fields = PD.get_unmerged_fields

    def __init__(self, **fields):
        for field in self.merged_fields:
            setattr(self, field, None)
        self._type = None
        self._type_entity = None
        self.name = 'p'
        for field, value in fields.items():
            setattr(self, field, value)


def test_a_refinement_carrying_everything_is_complete():
    parent = Decl(_type='string', _default=22, _required=True)
    child = Decl(_type='string', _default=22, _required=True)
    assert child.get_unmerged_fields(parent) == []


def test_a_refinement_of_its_own_is_complete():
    # The refinement states more than the parent, and nothing less.
    parent = Decl(_type='string')
    child = Decl(_type='string', _default=22, _validations={'$greater_than': 0})
    assert child.get_unmerged_fields(parent) == []


def test_an_unmerged_field_is_reported():
    parent = Decl(_type='string', _default=22)
    child = Decl(_type='string')
    assert child.get_unmerged_fields(parent) == ['_default']


def test_an_unmerged_type_is_reported():
    parent = Decl(_type='string')
    child = Decl(_default=22)
    assert child.get_unmerged_fields(parent) == ['type']


def test_a_type_already_resolved_counts_as_merged():
    # 'merge_augmented_type' copies the resolved entity rather than the name.
    parent = Decl(_type='string')
    child = Decl(_type_entity=object(), _default=22)
    assert child.get_unmerged_fields(parent) == []


def test_every_unmerged_field_is_reported():
    parent = Decl(_type='string', _default=22, _required=True, _entry_schema=object())
    child = Decl(_type='string')
    assert child.get_unmerged_fields(parent) == ['_default', '_required', '_entry_schema']


def test_validations_are_not_checked():
    # The validations merge combines rather than fills, so it is never 'done'.
    parent = Decl(_type='string', _validations={'$greater_than': 0})
    child = Decl(_type='string')
    assert child.get_unmerged_fields(parent) == []


def test_a_field_the_parent_does_not_state_is_not_reported():
    parent = Decl(_type='string')
    child = Decl(_type='string')
    assert child.get_unmerged_fields(parent) == []


def test_an_entity_without_the_check_is_skipped():
    # An operation declaration is never merged -- its inputs and outputs are --
    # so it does not implement the check, and the walk passes over it.
    from tosca_core.validate.validator import ToscaValidator

    class Containing:
        name = 'Standard'

    class Operation:
        name = 'create'

    ToscaValidator().assert_augmentation_complete(
        Containing(), 'operations', 'create', Operation(), Operation())


def test_the_base_declaration_checks_name_description_and_type():
    # Interface, capability and relationship declarations use the base list.
    assert ToscaDeclaration.merged_fields == ('name', '_description')
    for field in ('_default', '_required'):
        assert field not in ToscaDeclaration.merged_fields
