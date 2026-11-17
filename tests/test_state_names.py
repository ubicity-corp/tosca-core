"""
The states a set_state activity may name are the application's.

TOSCA defines no states, so standalone any name is accepted. An
application that runs workflows supplies its own (STATE_NAMES), and
validation warns of a name outside them, without refusing the template.
"""

import logging
from types import SimpleNamespace

import pytest

from tosca_core.constants import constants
from tosca_core.validate.activity import validate_activity


@pytest.fixture
def state_names():
    saved = constants.STATE_NAMES
    yield lambda names: constants.configure(STATE_NAMES=names)
    constants.configure(STATE_NAMES=saved)


def set_state(name):
    owner = SimpleNamespace(name='deploy', service=None)
    return validate_activity(owner, {'name': 'step', 'set_state': name},
                             owner_label='Workflow', changed_collection=None)


def test_standalone_any_state_is_accepted(caplog):
    assert constants.STATE_NAMES == ()
    with caplog.at_level(logging.WARNING):
        assert set_state('BAKED') == {}
    assert caplog.records == []


def test_a_state_the_application_names_is_accepted(state_names, caplog):
    state_names(['IDLE', 'ACTIVE'])
    with caplog.at_level(logging.WARNING):
        assert set_state('ACTIVE') == {}
    assert caplog.records == []


def test_another_state_is_warned_of_not_refused(state_names, caplog):
    state_names(['IDLE', 'ACTIVE'])
    with caplog.at_level(logging.WARNING):
        assert set_state('BAKED') == {}
    assert "'set_state: BAKED' is not one of this application's states (IDLE, ACTIVE)" in caplog.text


def test_the_names_are_kept_as_a_tuple(state_names):
    state_names(name for name in ['IDLE'])
    assert constants.STATE_NAMES == ('IDLE',)
