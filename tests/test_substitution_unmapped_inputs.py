"""
A substituting template's required input needs a property mapping unless it
has a default or gives its own value.

An input that states a value is computed in the template -- from other inputs,
for instance -- and a mapping to it would have nothing to supply.

DB-free: the real validator method runs on stand-in inputs.
"""

from types import SimpleNamespace

import pytest

from tosca_core.validate.substitution_mappings import ToscaSubstitutionMappingsValidator


class Input:
    def __init__(self, required=True, **given):
        self.required = required
        for name, value in given.items():
            setattr(self, name, value)

    def is_required(self):
        return self.required


def unmapped_warnings(input, caplog):
    validator = ToscaSubstitutionMappingsValidator.__new__(ToscaSubstitutionMappingsValidator)
    service = SimpleNamespace(inputs={'x': input})
    with caplog.at_level('WARNING'):
        assert validator.validate_property_mappings(service, None, SimpleNamespace()) == {}
    return [r for r in caplog.records if 'not mapped' in r.getMessage()]


@pytest.mark.parametrize('given', [{'value': {'$get_input': 'y'}}, {'default': 1}])
def test_a_required_input_with_a_value_or_default_needs_no_mapping(given, caplog):
    assert not unmapped_warnings(Input(**given), caplog)


def test_a_required_input_with_neither_warns(caplog):
    assert unmapped_warnings(Input(), caplog)


def test_an_optional_input_needs_no_mapping(caplog):
    assert not unmapped_warnings(Input(required=False), caplog)
