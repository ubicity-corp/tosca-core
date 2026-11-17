"""
The value of an attribute declared only as an attribute is not checked for
presence.

TOSCA gives attribute definitions no 'required' keyname, so such an attribute
is never required, and a value that may be absent -- one read through an
optional requirement, say -- is what it may hold. An operation reading the
attribute is checked where it reads it. A required property's value is still
checked.

DB-free: the real validate_function_value runs on a stand-in declaration and
function.
"""

from types import SimpleNamespace

import pytest

import tosca_core.models.exceptions as te
import tosca_core.models.property_declaration as module
from tosca_core.models.property_declaration import ToscaPropertyDeclaration


class Function:
    name = 'get_attribute'
    expression = {'$get_attribute': ['SELF', 'RELATIONSHIP', 'cert', 'CAPABILITY', 'credentials']}

    def __init__(self):
        self.checked = False

    def get_result_declaration(self, context, value_declaration=None):
        return SimpleNamespace(has_templated_type=lambda: False, has_type=lambda t: True, type='map')

    def is_return_value_present(self, context):
        self.checked = True
        return False


class Declaration:
    validate_function_value = ToscaPropertyDeclaration.validate_function_value

    def __init__(self, role):
        self.name = 'credentials'
        self.type = 'map'
        self.type_entity = SimpleNamespace()
        self.role = role

    def is_required(self):
        return True


@pytest.fixture
def function(monkeypatch):
    function = Function()
    monkeypatch.setattr(module, 'ToscaFunction', lambda value, context, **kwargs: function)
    return function


def test_an_attribute_value_is_not_checked(function):
    declaration = Declaration('ATTRIBUTE')
    assert declaration.validate_function_value(None, function.expression, check_presence=True) \
        == function.expression
    assert not function.checked


def test_a_required_property_value_is_checked(function):
    with pytest.raises(te.ValidationError):
        Declaration('PROPERTY').validate_function_value(None, function.expression,
                                                        check_presence=True)
    assert function.checked
