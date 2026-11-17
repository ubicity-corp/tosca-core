"""
An operation input declared 'required: false' may be incomplete.

A value of a complex type lacking fields its type declares required is an
error for a required input, as for any property. An input declared
'required: false' may be absent or incomplete -- a Socket read from a
machine that never got an address has its port and no address -- and is
passed as it is, so the artifact can tell the two apart. Only the check for
required fields is lifted: a value of the wrong type is refused either way.
The rule reaches nested values and the entries of lists and maps.

An evaluated value of a complex type carries only the fields that have one:
a field without a value is absent, required or not, so an incomplete Socket
reaches the artifact as its port alone.

Passing an operation's inputs to its artifact is the orchestrator's;
ubicity's test_incomplete_optional_inputs.py has that half. DB-free: the
methods are called on duck-typed declarations.
"""

from types import SimpleNamespace

import pytest

import tosca_core.models.exceptions as te
from tosca_core.models.declaration import ToscaDeclaration
from tosca_core.models.property_declaration import ToscaPropertyDeclaration as PD


class Field:
    """A field of a complex type: accepts strings and integers only."""

    def __init__(self, required):
        self.required = required

    def is_required(self):
        return self.required

    def validate_value(self, context, value, check_presence=False, check_required_fields=True):
        if not isinstance(value, (str, int)):
            raise te.ValidationError('invalid value', f"{value!r} is not a scalar")
        return value

    def validate_value_presence(self, context, properties):
        return 'required but not specified'


class Socket:
    """A complex type with a required 'address' and an optional 'port'."""

    name = 'Socket'
    type = 'Socket'
    validate_property_templates = ToscaDeclaration.validate_property_templates

    def get_property_declarations(self):
        return {'address': Field(required=True), 'port': Field(required=False)}


def validate(value, check_required_fields=True):
    return Socket().validate_property_templates(
        None, value, check_required_fields=check_required_fields)


def test_a_value_lacking_a_required_field_is_refused():
    with pytest.raises(te.ValidationError, match='invalid properties'):
        validate({'port': 22})


def test_it_is_accepted_when_required_fields_are_not_checked():
    assert validate({'port': 22}, check_required_fields=False) == {'port': 22}


def test_a_field_of_the_wrong_type_is_refused_either_way():
    with pytest.raises(te.ValidationError):
        validate({'port': [22]}, check_required_fields=False)


def test_an_unknown_field_is_refused_either_way():
    with pytest.raises(te.ValidationError):
        validate({'port': 22, 'protocol': 'ssh'}, check_required_fields=False)


class Entries:
    """A map or list declaration whose entry schema records how it was asked
    to validate each entry."""

    validate_values_for_entry_schema = PD.validate_values_for_entry_schema
    name = 'credentials'

    def __init__(self):
        self.asked = []
        entry = SimpleNamespace(type_entity=SimpleNamespace(name='NamedCredentialRef'))
        entry.validate_value = lambda context, value, check_required_fields=True: (
            self.asked.append(check_required_fields) or value)
        self.get_entry_schema = lambda: entry


@pytest.mark.parametrize('value', [{'ssh': {'name': 'key'}}, [{'name': 'key'}]])
def test_map_and_list_entries_follow_the_rule(value):
    entries = Entries()
    entries.validate_values_for_entry_schema(None, value, check_required_fields=False)
    assert entries.asked == [False]


class Evaluated:
    """A field declaration that evaluates to the value it is given."""

    def __init__(self, required):
        self.required = required

    def is_required(self):
        return self.required

    def get_evaluated_value(self, context, templates, value=None, value_declaration=None, **kwargs):
        return value


def test_a_field_without_a_value_is_absent_required_or_not():
    socket = SimpleNamespace(get_property_declarations=lambda: {
        'address': Evaluated(required=True), 'port': Evaluated(required=False),
        'protocol': Evaluated(required=False)})
    assert PD.evaluate_complex_value(socket, None, {}, value={'port': 22}) == {'port': 22}

