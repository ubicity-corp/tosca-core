"""
A value read through a path is required only if it is required at every step.

$get_property and $get_attribute read a property or attribute and may descend
into it: through the fields of a data type, and into the entries of a list
or map. The value is required when the property or attribute it starts from
is -- an attribute declared only as an attribute is not -- and every field on
the way is; an entry of a list or map may be absent, so a step into one makes
the value optional. A short-form input takes its required-ness from this,
unless it states its own.

DB-free: the real methods run on stand-in declarations.
"""

from types import SimpleNamespace

import pytest

from tosca_core.models.function import ToscaFunction, _navigation_length
from tosca_core.models.property_declaration import ToscaPropertyDeclaration as PD


class Declaration:
    """A property, attribute or field declaration: its type is a list, a map
    or a data type with fields."""
    is_required_along = PD.is_required_along

    def __init__(self, required=True, kind='data', fields=None, entry=None, role='PROPERTY'):
        self.required = required
        self.role = role
        self.fields = fields or {}
        self.entry = entry
        self.type_entity = SimpleNamespace(is_list=lambda: kind == 'list',
                                           is_map=lambda: kind == 'map')

    def is_required(self):
        return self.required

    def get_property_declaration(self, step):
        return self.entry if self.entry is not None else self.fields[step]


def credential_ref():
    return Declaration(fields={'file': Declaration(), 'name': Declaration(required=False)})


def test_a_required_field_of_a_required_property_is_required():
    endpoint = Declaration(fields={'address': Declaration(), 'port': Declaration()})
    assert endpoint.is_required_along(['address']) is True


def test_an_optional_field_on_the_way_makes_the_value_optional():
    socket = Declaration(fields={'address': Declaration(required=False)})
    outer = Declaration(fields={'address': socket})
    assert outer.is_required_along(['address', 'address']) is False


@pytest.mark.parametrize('kind, step', [('map', 'kubeconfig'), ('list', 0)])
def test_an_entry_of_a_list_or_map_may_be_absent(kind, step):
    collection = Declaration(kind=kind, entry=credential_ref())
    assert collection.is_required_along([step, 'file']) is False


def test_the_value_itself_answers_for_an_empty_path():
    assert Declaration(kind='map').is_required_along([]) is True


@pytest.mark.parametrize('tokens, start', [
    (['credentials', 'kubeconfig', 'file'], 0),
    (['CAPABILITY', 'endpoint', 'address', 'address'], 2),
    (['RELATIONSHIP', 'host', 'TARGET', 'credentials'], 3),
    (['RELATIONSHIP', 'link', 0, 'TARGET', 'RELATIONSHIP', 'link', 'TARGET', 'cidr_block'], 7),
    (['RELATIONSHIP', 'host', 'TARGET', 'CAPABILITY', 'endpoint', 'address'], 5),
    # Right after a requirement, CAPABILITY is the bound capability, with no name.
    (['RELATIONSHIP', 'identity', 'CAPABILITY', 'credentials', 'x509_cert', 'file'], 3),
    (['RELATIONSHIP', 'credential', 0, 'CAPABILITY', 'credentials', 'cloud_account', 'file'], 4),
    (['RELATIONSHIP', 'host', 'TARGET', 'RELATIONSHIP', 'credential', 'CAPABILITY', 'credentials',
      'cloud_account', 'file'], 6),
])
def test_navigation_ends_at_the_first_token_naming_a_value(tokens, start):
    assert _navigation_length(tokens) == start


class Node:
    """A node declaration: its properties and attributes, found by the path
    below the node the way the engine finds them."""
    def __init__(self, values):
        self.values = values

    def _find(self, path):
        return self.values[path if isinstance(path, str) else path[-1]]

    get_property_declaration = _find
    get_attribute_declaration = _find


class Function:
    is_value_required = ToscaFunction.is_value_required

    def __init__(self, name, args):
        self.name, self.args = name, args


def value_required(name, args, node, result=None):
    context = SimpleNamespace(SELF=lambda: node)
    return Function(name, args).is_value_required(context, result or Declaration())


def test_an_entry_of_an_optional_map_is_optional_though_its_field_is_required():
    """The kubeconfig case: CredentialRef.file is required, the credentials
    map is optional, and its kubeconfig entry exists once configure writes it."""
    node = Node({'credentials': Declaration(required=False, kind='map', entry=credential_ref())})
    assert value_required('get_attribute', ['SELF', 'credentials', 'kubeconfig', 'file'], node) \
        is False


def test_an_entry_of_a_required_map_is_still_optional():
    node = Node({'credentials': Declaration(kind='map', entry=credential_ref())})
    assert value_required('get_property', ['SELF', 'credentials', 'kubeconfig', 'file'], node) \
        is False


def test_a_required_field_of_a_capability_property_is_required():
    endpoint = Declaration(fields={'address': Declaration(), 'port': Declaration()})
    node = Node({'address': endpoint})
    assert value_required('get_attribute', ['SELF', 'CAPABILITY', 'endpoint', 'address', 'port'],
                          node) is True


def test_a_value_below_an_attribute_declared_only_as_one_is_optional():
    node = Node({'status': Declaration(role='ATTRIBUTE', fields={'phase': Declaration()})})
    assert value_required('get_attribute', ['SELF', 'status', 'phase'], node) is False


def test_other_functions_answer_from_their_result_declaration():
    assert Function('get_input', ['name']).is_value_required(None, Declaration()) is True
    assert Function('get_input', ['name']).is_value_required(
        None, Declaration(required=False)) is False


# --- A short-form input takes this rule, unless it states its own --------------------

from tosca_core.validate.property_declaration import ToscaPropertyDeclarationValidator


class Parameter:
    def __init__(self, required=None):
        self.name = 'kubeconfig'
        self._required = required
        self.type = None

    def merge_augmented_type(self, declaration):
        self.type = 'string'

    def merge_augmented_field(self, field, declaration):
        if getattr(self, field) is None:
            setattr(self, field, getattr(declaration, field))


def implied(monkeypatch, parameter, required_along):
    """Run validate_value_type with a function whose end declaration is
    required and whose path is 'required_along'."""
    function = SimpleNamespace(
        get_result_declaration=lambda context: SimpleNamespace(_required=True, role='PROPERTY'),
        is_value_required=lambda context, declaration: required_along)
    import tosca_core.validate.property_declaration as module
    monkeypatch.setattr(module, 'ToscaFunction', lambda value, context: function)
    validator = ToscaPropertyDeclarationValidator.__new__(ToscaPropertyDeclarationValidator)
    assert validator.validate_value_type(SimpleNamespace(name='K3s'), parameter, {}) is None
    return parameter._required


def test_a_short_form_input_is_optional_when_its_path_is(monkeypatch):
    assert implied(monkeypatch, Parameter(), required_along=False) is False


def test_a_short_form_input_is_required_when_its_path_is(monkeypatch):
    assert implied(monkeypatch, Parameter(), required_along=True) is True


def test_an_input_that_states_required_keeps_it(monkeypatch):
    assert implied(monkeypatch, Parameter(required=True), required_along=False) is True


def test_an_entry_read_through_a_bound_capability_is_optional():
    """[RELATIONSHIP, identity, CAPABILITY, credentials, x509_cert, file]: the
    bound capability's credentials map, then its x509_cert entry, which may be
    absent -- whatever the required file below it."""
    credentials = Declaration(kind='map', entry=credential_ref())
    node = Node({'credentials': credentials})
    function_args = ['SELF', 'RELATIONSHIP', 'identity', 'CAPABILITY', 'credentials', 'x509_cert', 'file']
    assert value_required('get_attribute', function_args, node) is False
