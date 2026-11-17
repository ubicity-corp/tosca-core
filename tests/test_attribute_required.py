"""
Attributes, properties and required-ness.

Every property is also an attribute of the same name, whose initial value is
the property's value. So:

- a type may not declare an attribute under the name of a property of its
  own or of an ancestor, nor a property under the name of an attribute an
  ancestor declares (validate/type.py, validate_attribute_names);
- a parameter whose type is implied by the value it reads takes that value's
  required-ness: a property's own, and for an attribute declared as one, which
  has none, not required (validate/property_declaration.py,
  validate_value_type);
- a list of values read from several entities takes the role and
  required-ness of what it lists, so a list of a reflected property is not
  mistaken for a list of an attribute (models/property_declaration.py,
  as_list_declaration).

DB-free: the methods are called on stand-in types and declarations.
"""

from types import SimpleNamespace

import tosca_core.models.property_declaration as property_declaration_module
import tosca_core.validate.property_declaration as validator_module
from tosca_core.models.declaration import ToscaDeclaration
from tosca_core.validate.type import ToscaTypeValidator


# --- Attribute names ------------------------------------------------------------------

class Type:
    def __init__(self, properties=(), attributes=(), parent=None):
        self.properties = {name: object() for name in properties}
        self.attributes = {name: object() for name in attributes}
        self.parent = parent

    def get_property_declarations(self):
        inherited = self.parent.get_property_declarations() if self.parent else {}
        return {**inherited, **self.properties}

    def get_attribute_declarations(self):
        inherited = self.parent.get_attribute_declarations() if self.parent else {}
        return {**inherited, **self.attributes}


def names(type_entity):
    return ToscaTypeValidator().validate_attribute_names(type_entity)


def test_distinct_names_are_accepted():
    parent = Type(properties=['port'], attributes=['address'])
    assert names(Type(properties=['name'], attributes=['state'], parent=parent)) == {}


def test_refining_a_property_or_an_attribute_is_accepted():
    parent = Type(properties=['port'], attributes=['address'])
    assert names(Type(properties=['port'], attributes=['address'], parent=parent)) == {}


def test_an_attribute_named_like_a_property_of_the_same_type_is_refused():
    errors = names(Type(properties=['ip_address'], attributes=['ip_address']))
    assert list(errors['attributes']) == ['ip_address']


def test_an_attribute_named_like_an_inherited_property_is_refused():
    parent = Type(properties=['ip_address'])
    errors = names(Type(attributes=['ip_address'], parent=parent))
    assert 'inherited property' in errors['attributes']['ip_address']


def test_a_property_named_like_an_inherited_attribute_is_refused():
    parent = Type(attributes=['ip_address'])
    errors = names(Type(properties=['ip_address'], parent=parent))
    assert list(errors['properties']) == ['ip_address']


# --- Implied required-ness ------------------------------------------------------------

class Parameter:
    """A short-notation parameter definition: a value, no type, no required."""
    merge_augmented_field = ToscaDeclaration.merge_augmented_field
    name = 'preexisting'
    type = 'list'

    def __init__(self):
        self._required = None

    @property
    def required(self):
        if self._required is None:
            raise AttributeError('no required')
        return self._required

    def merge_augmented_type(self, declaration):
        pass


def implied(monkeypatch, result):
    """Infer a parameter from a function whose result is 'result'."""
    function = SimpleNamespace(get_result_declaration=lambda context: result)
    monkeypatch.setattr(validator_module, 'ToscaFunction', lambda value, context: function)
    parameter = Parameter()
    validator = validator_module.ToscaPropertyDeclarationValidator()
    assert validator.validate_value_type(SimpleNamespace(name='T'), parameter, {'$f': []}) is None
    return parameter


def test_a_parameter_reading_an_attribute_is_not_required(monkeypatch):
    parameter = implied(monkeypatch, SimpleNamespace(role='ATTRIBUTE', _required=None))
    assert parameter._required is False


def test_a_parameter_reading_a_property_takes_its_required(monkeypatch):
    optional = implied(monkeypatch, SimpleNamespace(role='PROPERTY', _required=False))
    assert optional._required is False
    required = implied(monkeypatch, SimpleNamespace(role='PROPERTY', _required=True))
    assert required._required is True


def test_a_parameter_reading_a_property_that_states_no_required_stays_required(monkeypatch):
    """No 'required' on the property means required, and the parameter
    keeps the same default."""
    parameter = implied(monkeypatch, SimpleNamespace(role='PROPERTY', _required=None))
    assert parameter._required is None


# --- Lists of values -------------------------------------------------------------------

class Declaration:
    """A stand-in for ToscaPropertyDeclaration's constructor and the fields
    as_list_declaration sets."""
    def __init__(self, name=None, role=None):
        self.name = name
        self.role = role
        self._required = None

    def merge_augmented_declaration(self, other):
        pass


def listed(monkeypatch, value_declaration, attr_or_prop):
    monkeypatch.setattr(property_declaration_module, 'ToscaPropertyDeclaration', Declaration)
    monkeypatch.setattr(property_declaration_module, 'builtin_types',
                        SimpleNamespace(get=lambda name: name))
    return property_declaration_module.as_list_declaration(value_declaration, 'server',
                                                           attr_or_prop)


def test_a_list_of_a_reflected_property_is_a_list_of_that_property(monkeypatch):
    value = SimpleNamespace(role='PROPERTY', _required=True)
    declaration = listed(monkeypatch, value, 'attributes')
    assert (declaration.role, declaration._required) == ('PROPERTY', True)


def test_a_list_of_an_attribute_is_a_list_of_that_attribute(monkeypatch):
    value = SimpleNamespace(role='ATTRIBUTE', _required=None)
    declaration = listed(monkeypatch, value, 'attributes')
    assert (declaration.role, declaration._required) == ('ATTRIBUTE', None)


def test_a_value_with_neither_role_takes_the_role_it_was_read_as(monkeypatch):
    value = SimpleNamespace(role='SCHEMA', _required=None)
    assert listed(monkeypatch, value, 'properties').role == 'PROPERTY'
