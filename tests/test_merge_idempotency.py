"""
Refinement-merge idempotency tests.

A refinement states only what it changes; ``merge_augmented_declaration`` completes it by
merging in the declaration it refines. Running that merge in its own pass ahead of
validation requires it to be safe to run twice: while the pass and the merge validation
used to do on the way coexist, a declaration can be merged by both. These tests pin the individual merge paths:

- ``merge_augmented_field`` fills a field only when it is unset, so a second run is a no-op;
- ``merge_augmented_validations`` combines the refined declaration's validations with the
  refinement's own under ``$and``. It is not idempotent, and is not made so: a second run
  nests one more ``$and`` around the same predicates, which evaluates the same, is bounded to
  one level because there are only ever two merges, and is written to the refinement's own
  object. Recognising that the predicates are already there would mean comparing validation
  expressions, which are rewritten into resolved form between the two merges and are equal
  only up to argument order and the semantics of the functions in them. What is pinned is
  that the refined declaration is left alone;
- ``merge_augmented_entry_schema`` and ``merge_augmented_key_schema`` give a refinement with
  no schema of its own a *reference* to the refined declaration's schema, and a second run
  recognises that shared object instead of merging it into itself. That comparison is by
  identity, which no rewrite changes, and it matters because the shared object belongs to
  another declaration -- one a refinement in a different profile may share.

None of this shows in an outcome a deploy or a ``tosca-tests`` case can observe; only a test
that inspects the structure sees it.

DB-free: the merge methods are called on a duck-typed declaration whose accessors raise
``AttributeError`` when unset, as ``ToscaPropertyDeclaration``'s do.
"""

import copy

import pytest

from tosca_core.models.property_declaration import ToscaPropertyDeclaration as PD


class Decl:
    """The parts of a property declaration the merge methods touch. Each accessor raises
    ``AttributeError`` when its field is unset, and ``validations`` ignores a ``None``
    assignment, matching ``ToscaPropertyDeclaration``."""

    name = 'p'

    def __init__(self, validations=None, entry_schema=None, key_schema=None, default=None):
        self._validations = validations
        self._entry_schema = entry_schema
        self._key_schema = key_schema
        self._default = default

    @property
    def validations(self):
        if self._validations is None:
            raise AttributeError("'p' does not have 'validations'")
        return self._validations

    @validations.setter
    def validations(self, value):
        if value is not None:
            self._validations = value

    @property
    def entry_schema(self):
        if self._entry_schema is None:
            raise AttributeError("'p' does not have 'entry_schema'")
        return self._entry_schema

    @property
    def key_schema(self):
        if self._key_schema is None:
            raise AttributeError("'p' does not have 'key_schema'")
        return self._key_schema


class Schema:
    """A schema declaration that records what is merged into it."""

    def __init__(self):
        self.merged = []

    def merge_augmented_declaration(self, other):
        self.merged.append(other)


# ---------------------------------------------------------------------------
# merge_augmented_field: idempotent
# ---------------------------------------------------------------------------

def test_merge_augmented_field_fills_an_unset_field():
    child, parent = Decl(), Decl(default=22)
    PD.merge_augmented_field(child, '_default', parent)
    assert child._default == 22


def test_merge_augmented_field_is_idempotent():
    child, parent = Decl(), Decl(default=22)
    PD.merge_augmented_field(child, '_default', parent)
    PD.merge_augmented_field(child, '_default', parent)
    assert child._default == 22


def test_merge_augmented_field_keeps_the_refinements_own_value():
    child, parent = Decl(default=80), Decl(default=22)
    PD.merge_augmented_field(child, '_default', parent)
    assert child._default == 80


# ---------------------------------------------------------------------------
# merge_augmented_validations: combines under $and, and a second run adds a level
# ---------------------------------------------------------------------------

PARENT = {'$greater_than': [{'$value': []}, 0]}
OWN = {'$less_than': [{'$value': []}, 100]}


def test_merge_augmented_validations_keeps_both():
    child, parent = Decl(validations=OWN), Decl(validations=PARENT)
    PD.merge_augmented_validations(child, parent)
    assert child._validations == {'$and': [PARENT, OWN]}


def test_merge_augmented_validations_takes_the_parents_when_it_has_none():
    child, parent = Decl(), Decl(validations=PARENT)
    PD.merge_augmented_validations(child, parent)
    assert child._validations == PARENT


def test_merge_augmented_validations_twice_adds_one_level_to_the_refinement_only():
    child, parent = Decl(validations=OWN), Decl(validations=copy.deepcopy(PARENT))
    PD.merge_augmented_validations(child, parent)
    PD.merge_augmented_validations(child, parent)
    assert child._validations == {'$and': [PARENT, {'$and': [PARENT, OWN]}]}
    assert parent._validations == PARENT


def test_merge_augmented_validations_taken_from_the_parent_twice_leaves_the_parent_alone():
    # With none of its own the refinement takes the parent's object as its own; the second
    # run must build a new one rather than combine into the object it shares.
    shared = copy.deepcopy(PARENT)
    child, parent = Decl(), Decl(validations=shared)
    PD.merge_augmented_validations(child, parent)
    PD.merge_augmented_validations(child, parent)
    assert parent._validations is shared
    assert shared == PARENT
    assert child._validations == {'$and': [PARENT, PARENT]}


# ---------------------------------------------------------------------------
# merge_augmented_entry_schema / merge_augmented_key_schema: share, and recognise the share
# ---------------------------------------------------------------------------

MERGES = [
    ('entry_schema', PD.merge_augmented_entry_schema),
    ('key_schema', PD.merge_augmented_key_schema),
]


@pytest.mark.parametrize('field,merge', MERGES)
def test_merge_augmented_schema_takes_the_parents_when_it_has_none(field, merge):
    shared = Schema()
    child, parent = Decl(), Decl(**{field: shared})
    merge(child, parent)
    assert getattr(child, field) is shared
    assert shared.merged == []


@pytest.mark.parametrize('field,merge', MERGES)
def test_merge_augmented_schema_merges_into_the_refinements_own(field, merge):
    own, parents = Schema(), Schema()
    child, parent = Decl(**{field: own}), Decl(**{field: parents})
    merge(child, parent)
    assert own.merged == [parents]


@pytest.mark.parametrize('field,merge', MERGES)
def test_merge_augmented_schema_is_idempotent(field, merge):
    shared = Schema()
    child, parent = Decl(), Decl(**{field: shared})
    merge(child, parent)
    merge(child, parent)
    assert shared.merged == []
