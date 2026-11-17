"""
What the presence check says when it cannot say "present".

The onboarding check asks whether a value is guaranteed to be present. Beyond
True and False it has two answers, both false so that every caller branches
exactly as for "not present", but each saying why: `Undecided`, when the check
could not decide -- a path it cannot resolve, an error inside it -- and
`Circular`, when the value is defined in terms of itself. Callers that word
the error ask for the reason, so a failure of the check is not reported to
the author as an optional parameter.

A context that is not a template -- a type, a declaration -- still answers a
plain False: that is a limit of the check, not a failure of it.

DB-free: the methods are called on stand-in functions, templates and
declarations.
"""

from types import SimpleNamespace

import pytest

import tosca_core.models.presence as presence
from tosca_core.models.function import ToscaFunction
from tosca_core.models.property_declaration import ToscaPropertyDeclaration as PD


def optional_declaration():
    return SimpleNamespace(is_required=lambda: False)


class Function:
    """A $get_property stand-in: the real presence methods, a given path and
    result declaration."""
    is_return_value_present = ToscaFunction.is_return_value_present
    _presence = ToscaFunction._presence
    _path_presence = ToscaFunction._path_presence
    _end_presence = ToscaFunction._end_presence
    _attribute_presence = ToscaFunction._attribute_presence
    _if_presence = ToscaFunction._if_presence
    _arguments_presence = ToscaFunction._arguments_presence
    signature = None

    def __init__(self, args, result_declaration, name='get_property'):
        self.name = name
        self.args = args
        self.result_declaration = result_declaration

    def __str__(self):
        return f"$get_property: {self.args}"


def get_property(args, context_node=None, result_declaration=None):
    """A $get_property with an optional result unless one is given."""
    return Function(args, result_declaration or optional_declaration())


def check(function, node):
    context = SimpleNamespace(SELF=lambda: node)
    return function.is_return_value_present(context)


# --- The two answers ------------------------------------------------------------------

def test_both_answers_are_false():
    assert not presence.Undecided('why')
    assert not presence.Circular(['a', 'b', 'a'])


def test_explain_gives_the_reason_or_the_usual_message():
    assert presence.explain(presence.Undecided('no such node'), 'x', 'usual') == \
        'cannot tell whether x is present: no such node'
    assert presence.explain(presence.Circular(['n.a', 'n.b', 'n.a']), 'x', 'usual') == \
        'x refers to itself: n.a -> n.b -> n.a'
    assert presence.explain(False, 'x', 'usual') == 'usual'


# --- is_return_value_present ----------------------------------------------------------

def test_a_context_that_is_not_a_template_answers_false():
    """A type or declaration cannot say whether it holds a value: plain False,
    as before."""
    answer = check(get_property(['SELF', 'port'], None), SimpleNamespace(name='T'))
    assert answer is False


def test_an_error_inside_the_check_is_undecided():
    def broken(path, declaration):
        raise AttributeError("'NoneType' object has no attribute 'properties'")
    node = SimpleNamespace(name='client', is_property_template_present=broken)
    answer = check(get_property(['SELF', 'port'], node), node)
    assert isinstance(answer, presence.Undecided)
    assert 'AttributeError' in answer.reason


def test_a_path_that_cannot_be_resolved_is_undecided():
    def unresolvable():
        raise KeyError('no node named server')
    function = get_property(['SELF', 'port'])
    answer = function.is_return_value_present(SimpleNamespace(SELF=unresolvable))
    assert isinstance(answer, presence.Undecided)
    assert 'cannot resolve the path' in answer.reason


def test_a_value_that_reads_itself_through_another_is_circular():
    """a reads b, and b reads a: the check finds the loop instead of
    recursing until Python gives up."""
    node = SimpleNamespace(name='client')

    def is_property_template_present(path, declaration):
        # a's value is b, b's value is a.
        other = {'a': 'b', 'b': 'a'}[path]
        return check(get_property(['SELF', other], node), node)

    node.is_property_template_present = is_property_template_present
    answer = check(get_property(['SELF', 'a'], node), node)
    assert isinstance(answer, presence.Circular)
    assert answer.chain == ['client.a', 'client.b', 'client.a']


def test_the_guard_is_released_after_each_check():
    node = SimpleNamespace(name='client', is_property_template_present=lambda p, d: True)
    assert check(get_property(['SELF', 'a'], node), node) is True
    assert check(get_property(['SELF', 'a'], node), node) is True


# --- validate_value_presence and is_value_present ----------------------------------

class Declaration:
    """A declaration whose values the stand-in check judges by name."""
    validate_value_presence = PD.validate_value_presence
    _validate_value_presence = PD._validate_value_presence

    def __init__(self, answers, **fields):
        self.name = 'endpoint'
        self.answers = answers
        for k, v in fields.items():
            setattr(self, k, v)

    def is_value_present(self, value, context):
        return self.answers[value]


def test_an_undecided_value_is_reported_as_undecided():
    decl = Declaration({'v': presence.Undecided('no such node')})
    error = decl.validate_value_presence(None, {'endpoint': 'v'})
    assert error == "cannot tell whether the value of 'endpoint' is present: no such node"
    assert isinstance(presence.answer_of(error), presence.Undecided)


def test_a_value_that_may_be_absent_is_reported_as_before():
    decl = Declaration({'v': False})
    assert decl.validate_value_presence(None, {'endpoint': 'v'}) == \
        'required but value references optional parameter'
    assert presence.answer_of('required but value references optional parameter') is False


def test_an_undecided_default_still_gives_way_to_a_present_value():
    """Control flow is as before: a default that is not guaranteed is not
    fatal when the assigned value is."""
    decl = Declaration({'d': presence.Undecided('why'), 'v': True}, default='d')
    assert decl.validate_value_presence(None, {'endpoint': 'v'}) is None


def test_an_error_while_checking_a_default_is_not_no_default():
    """An AttributeError from the check is not read as 'there is no default'."""
    class Raising(Declaration):
        def is_value_present(self, value, context):
            if value == 'd':
                return presence.Undecided("AttributeError while checking d")
            return False
    decl = Raising({}, default='d')
    error = decl.validate_value_presence(None, {})
    assert 'cannot tell whether' in error


def test_an_error_inside_a_function_check_is_not_present():
    """is_value_present answers Undecided for an error raised while checking a
    function, where a TypeError used to count the value as present."""
    class Function:
        def __init__(self, value, context):
            pass

        def is_return_value_present(self, context):
            raise TypeError('unsupported operand')

    import tosca_core.models.property_declaration as module
    original = module.ToscaFunction
    module.ToscaFunction = Function
    try:
        answer = PD.is_value_present(SimpleNamespace(), {'$get_property': ['SELF', 'x']}, None)
    finally:
        module.ToscaFunction = original
    assert isinstance(answer, presence.Undecided)
    assert 'TypeError' in answer.reason


# --- Following the path: types, requirements fulfilled at deploy, optional hops -----

class Value:
    """The declaration of the value a path reads: required or not, with or
    without a default, judged by the real is_value_present."""
    is_value_present = PD.is_value_present

    def __init__(self, required, **default):
        self.required = required
        if 'default' in default:
            self.default = default['default']

    def is_required(self):
        return self.required


def requirement(minimum, target=None):
    """A requirement declaration with the given minimum count."""
    return SimpleNamespace(is_required=lambda: minimum >= 1, target_node_type=target)


def assigned(target_type=None, target_node=None):
    """A requirement template: its target template, or the target type it
    or its declaration names."""
    return SimpleNamespace(target_node=target_node,
                           get_target_query_node_type=lambda: target_type)


class Type:
    """A type or declaration: requirement declarations, no values of its own."""
    def __init__(self, name='T', requirements=None):
        self.name = name
        self.requirements = requirements or {}

    def get_requirement_declaration(self, name):
        return self.requirements[name]


class Template:
    """A node template: requirement templates, and an answer for its own
    values that records what it was asked."""
    def __init__(self, name='node', requirements=None, answer=True):
        self.name = name
        self.requirements = requirements or {}
        self.answer = answer
        self.asked = []

    def get_requirement(self, name):
        return self.requirements.get(name)

    def is_property_template_present(self, path, declaration):
        self.asked.append(path)
        return self.answer


def test_a_type_answers_from_a_literal_default():
    """An optional property with a literal default is guaranteed in a type's
    context, where it used to count as absent."""
    function = get_property(['SELF', 'port'], result_declaration=Value(False, default=8080))
    assert check(function, Type()) is True


def test_a_type_answers_absent_for_an_optional_property_without_a_default():
    function = get_property(['SELF', 'port'], result_declaration=Value(False))
    assert check(function, Type()) is False


def test_a_target_found_at_deploy_answers_from_its_declared_type():
    """The requirement is the template's, its target is found in the
    inventory at deploy: the declared target type answers."""
    node = Template(requirements={'server': assigned(Type('Server'))})
    function = get_property(['SELF', 'RELATIONSHIP', 'server', 'TARGET', 'port'],
                            result_declaration=Value(False, default=8080))
    assert check(function, node) is True
    assert node.asked == []


def test_a_target_template_answers_for_its_own_value():
    target = Template('server', answer=True)
    node = Template(requirements={'server': assigned(target_node=target)})
    function = get_property(['SELF', 'RELATIONSHIP', 'server', 'TARGET', 'port'])
    assert check(function, node) is True
    assert target.asked == ['port']


def test_an_unassigned_optional_requirement_leaves_an_optional_value_absent():
    function = get_property(['SELF', 'RELATIONSHIP', 'server', 'TARGET', 'port'])
    assert check(function, Template()) is False


def test_a_required_value_through_an_unassigned_optional_requirement_warns(caplog):
    """Not guaranteed, but reported as a warning for now and answered as
    before, so no template fails for it yet."""
    function = get_property(['SELF', 'RELATIONSHIP', 'server', 'TARGET', 'port'],
                            result_declaration=Value(True))
    with caplog.at_level('WARNING'):
        assert check(function, Template()) is True
    assert "requirement 'server' of 'node', which is not assigned" in caplog.text


def test_a_required_value_through_a_zero_minimum_in_a_type_warns(caplog):
    node_type = Type(requirements={'server': requirement(0, Type('Server'))})
    function = get_property(['SELF', 'RELATIONSHIP', 'server', 'TARGET', 'port'],
                            result_declaration=Value(True))
    with caplog.at_level('WARNING'):
        assert check(function, node_type) is True
    assert "whose minimum count is zero" in caplog.text


def test_a_required_value_through_a_mandatory_requirement_is_guaranteed(caplog):
    node_type = Type(requirements={'server': requirement(1, Type('Server'))})
    function = get_property(['SELF', 'RELATIONSHIP', 'server', 'TARGET', 'port'],
                            result_declaration=Value(True))
    with caplog.at_level('WARNING'):
        assert check(function, node_type) is True
    assert caplog.text == ''


def test_a_target_that_names_no_type_leaves_an_optional_value_absent():
    """Neither the template nor the requirement names a target type: nothing
    to ask, so an optional value is not guaranteed."""
    node = Template(requirements={'server': assigned()})
    function = get_property(['SELF', 'RELATIONSHIP', 'server', 'TARGET', 'port'])
    assert check(function, node) is False


def test_a_target_that_names_no_type_leaves_a_required_value_guaranteed():
    node = Template(requirements={'server': assigned()})
    function = get_property(['SELF', 'RELATIONSHIP', 'server', 'TARGET', 'port'],
                            result_declaration=Value(True))
    assert check(function, node) is True


# --- $get_attribute, the built-ins, $if and profile functions ------------------------
#
# Every answer other than "guaranteed" is logged as a warning and answered as
# guaranteed for now; _presence gives the answer as found.

class Literal:
    """A stand-in for ToscaFunction's constructor: dicts are the functions
    given, anything else is a literal."""
    def __init__(self, functions):
        self.functions = functions

    def __call__(self, argument, context=None):
        if isinstance(argument, dict):
            return self.functions[next(iter(argument))]
        raise TypeError('not a function')


def with_functions(monkeypatch, **functions):
    import tosca_core.models.function as module
    monkeypatch.setattr(module, 'ToscaFunction', Literal(functions))


class Attribute(Value):
    """An attribute declared only as an attribute: no required-ness of its
    own (is_required answers the declaration default, True, and must not
    count)."""
    role = 'ATTRIBUTE'

    def __init__(self, **default):
        super().__init__(True, **default)


def get_attribute(args, result_declaration):
    return Function(args, result_declaration, name='get_attribute')


def test_a_reflected_attribute_follows_its_property(caplog):
    """Read through $get_attribute, a property keeps its own rule."""
    required = get_attribute(['SELF', 'port'], Value(True))
    optional = get_attribute(['SELF', 'port'], Value(False))
    assert check(required, Type()) is True
    assert optional._presence(SimpleNamespace(SELF=lambda: Type())) is False
    with caplog.at_level('WARNING'):
        assert check(optional, Type()) is True
    assert 'not shown to be present: its result may be absent' in caplog.text


def test_an_attribute_without_a_default_is_not_guaranteed(caplog):
    function = get_attribute(['SELF', 'address'], Attribute())
    assert function._presence(SimpleNamespace(SELF=lambda: Type())) is False
    with caplog.at_level('WARNING'):
        assert check(function, Type()) is True
    assert 'not shown to be present' in caplog.text


def test_an_attribute_with_a_literal_default_is_guaranteed(monkeypatch, caplog):
    with_functions(monkeypatch)
    function = get_attribute(['SELF', 'state'], Attribute(default='initial'))
    with caplog.at_level('WARNING'):
        assert check(function, Type()) is True
    assert caplog.text == ''


def test_an_attribute_a_template_assigns_is_guaranteed(monkeypatch):
    with_functions(monkeypatch)
    node = SimpleNamespace(name='node', get_attribute_or_property_template=lambda kind, name: 'x')
    function = get_attribute(['SELF', 'address'], Attribute())
    assert function._presence(SimpleNamespace(SELF=lambda: node)) is True


def builtin(name, args):
    function = Function(args, None, name=name)
    function.signature = SimpleNamespace(artifacts=[])
    return function


def test_concat_is_guaranteed_when_every_argument_is(monkeypatch):
    with_functions(monkeypatch, present=get_property(['SELF', 'a'], result_declaration=Value(True)))
    function = builtin('concat', ['http://', {'present': []}, ':80'])
    assert function._presence(SimpleNamespace(SELF=lambda: Type())) is True


def test_concat_with_an_argument_that_may_be_absent_warns(monkeypatch, caplog):
    with_functions(monkeypatch, absent=get_property(['SELF', 'a'], result_declaration=Value(False)))
    function = builtin('concat', ['http://', {'absent': []}, ':80'])
    context = SimpleNamespace(SELF=lambda: Type())
    assert function._presence(context) is False
    with caplog.at_level('WARNING'):
        assert function.is_return_value_present(context) is True
    assert 'not shown to be present' in caplog.text


def test_join_checks_the_entries_of_its_list(monkeypatch):
    with_functions(monkeypatch, absent=get_property(['SELF', 'a'], result_declaration=Value(False)))
    function = builtin('join', [['a', {'absent': []}], ':'])
    assert function._presence(SimpleNamespace(SELF=lambda: Type())) is False


def test_if_with_a_literal_condition_needs_only_its_branch(monkeypatch):
    with_functions(monkeypatch, absent=get_property(['SELF', 'a'], result_declaration=Value(False)))
    context = SimpleNamespace(SELF=lambda: Type())
    assert builtin('if', [True, 'x', {'absent': []}])._presence(context) is True
    assert builtin('if', [False, 'x', {'absent': []}])._presence(context) is False


def test_if_with_a_computed_condition_needs_both_branches(monkeypatch):
    with_functions(monkeypatch,
                   condition=get_property(['SELF', 'c'], result_declaration=Value(True)),
                   absent=get_property(['SELF', 'a'], result_declaration=Value(False)))
    context = SimpleNamespace(SELF=lambda: Type())
    assert builtin('if', [{'condition': []}, 'x', 'y'])._presence(context) is True
    assert builtin('if', [{'condition': []}, 'x', {'absent': []}])._presence(context) is False


def test_a_profile_function_is_undecided(caplog):
    function = Function([], None, name='unique_name')
    function.signature = SimpleNamespace(artifacts=['unique.py'])
    answer = function._presence(None)
    assert isinstance(answer, presence.Undecided)
    with caplog.at_level('WARNING'):
        assert function.is_return_value_present(None) is True
    assert 'implemented by a profile' in caplog.text


@pytest.mark.parametrize('name, args', [
    ('unique_name', []),
    # Its argument is the value that may be absent, and it still answers.
    ('is_defined', [{'$get_attribute': ['SELF', 'RELATIONSHIP', 'host', 'TARGET', 'name']}]),
])
def test_a_profile_function_declaring_a_result_is_guaranteed(name, args, caplog):
    """An implementation returning null fails the evaluation, so a declared
    result is present whatever the arguments."""
    function = Function(args, None, name=name)
    function.signature = SimpleNamespace(artifacts=['f.py'], result=SimpleNamespace())
    with caplog.at_level('WARNING'):
        assert function.is_return_value_present(None) is True
    assert not caplog.text


def test_other_built_ins_are_guaranteed():
    assert builtin('sum', [1, 2])._presence(None) is True


def test_get_input_and_get_property_are_not_softened(caplog):
    """Their answers were already enforced: no warning, the answer as found."""
    function = get_property(['SELF', 'port'], result_declaration=Value(False))
    with caplog.at_level('WARNING'):
        assert check(function, Type()) is False
    assert caplog.text == ''


# --- What a warning is about ------------------------------------------------------------

def test_describe_names_an_operation_input_and_its_owner():
    interface = SimpleNamespace(name='Standard')
    operation = SimpleNamespace(name='delete', _containing_interface_declaration=interface,
                                SELF=lambda: SimpleNamespace(name='Server'))
    declaration = SimpleNamespace(role='INPUT', name='preexisting',
                                  _containing_operation_declaration=operation)
    assert presence.describe(declaration, operation) == \
        "input 'preexisting' of Standard.delete in 'Server'"


def test_describe_names_a_property_and_its_template():
    declaration = SimpleNamespace(role='PROPERTY', name='endpoint')
    assert presence.describe(declaration, SimpleNamespace(name='client')) == \
        "property 'endpoint' in 'client'"


def test_where_names_the_values_being_checked_outermost_first():
    outer = (SimpleNamespace(role='INPUT', name='address'), SimpleNamespace(name='Server'))
    inner = (SimpleNamespace(role='PROPERTY', name='endpoint'), SimpleNamespace(name='Server'))
    assert presence.where() == ''
    with presence.checking(*outer):
        with presence.checking(*outer):
            with presence.checking(*inner):
                assert presence.where() == \
                    " (for input 'address' in 'Server' / property 'endpoint' in 'Server')"
    assert presence.where() == ''


def test_a_warning_names_the_value_it_is_about(caplog):
    declaration = SimpleNamespace(role='INPUT', name='address')
    function = get_attribute(['SELF', 'address'], Attribute())
    with caplog.at_level('WARNING'):
        with presence.checking(declaration, SimpleNamespace(name='Server')):
            assert check(function, Type()) is True
    assert "(for input 'address' in 'Server'): not shown to be present: its result may be absent" \
        in caplog.text


def test_describe_names_the_template_an_interface_belongs_to():
    """An input checked in an interface template names the node template,
    not the interface."""
    ToscaInterfaceTemplate = type('ToscaInterfaceTemplate', (), {})
    interface = ToscaInterfaceTemplate()
    interface.name = 'Standard'
    interface.SELF = lambda: SimpleNamespace(name='controller')
    operation = SimpleNamespace(name='create', _containing_interface_declaration=SimpleNamespace(name='Standard'))
    declaration = SimpleNamespace(role='INPUT', name='aws_vpc_id',
                                  _containing_operation_declaration=operation)
    assert presence.describe(declaration, interface) == \
        "input 'aws_vpc_id' of Standard.create in 'controller'"
    interface_input = SimpleNamespace(role='INPUT', name='kubeconfig')
    assert presence.describe(interface_input, interface) == \
        "input 'kubeconfig' of Standard in 'controller'"


# --- An attribute an earlier operation writes ------------------------------------------


# --- An attribute an operation reads, and the order operations run in -----------
#
# Whether an operation certain to have run before the reading one writes an
# attribute depends on the order an application runs operations in, which
# TOSCA does not define. The core asks the attribute-written check an
# application installs (extensions.set_attribute_written_check); with none,
# only a value the templates give an attribute guarantees it. The Ubicity
# orchestrator's deploy-order check, and its tests, are in ubicity (0.4.0).

def reading(operation, interface='Standard', role='INPUT'):
    """The value checked is an input of 'interface'.'operation'."""
    declaration = SimpleNamespace(role=role, name='x', _containing_operation_declaration=SimpleNamespace(
        name=operation, _containing_interface_declaration=SimpleNamespace(name=interface)))
    return presence.checking(declaration, SimpleNamespace(name='Subnet'))


def depends_on(kind='DEPENDENCY'):
    return Type('Subnet', requirements={'vpc': SimpleNamespace(
        is_required=lambda: True, target_node_type=Type('Vpc'),
        type_entity=SimpleNamespace(get_kind=lambda: kind))})


TARGET_ID = ['SELF', 'RELATIONSHIP', 'vpc', 'TARGET', 'vpc_id']


@pytest.fixture
def written_check(monkeypatch):
    """Install a check that records what it is asked and answers True"""
    from tosca_core import extensions
    asked = []
    monkeypatch.setattr(extensions, '_attribute_written',
                        lambda *args: asked.append(args) or True)
    return asked


def test_with_no_check_an_attribute_is_not_shown_present_by_an_operation(monkeypatch, caplog):
    """An attribute not shown present warns (and is accepted, as an
    attribute's value is not refused for presence)"""
    from tosca_core import extensions
    monkeypatch.setattr(extensions, '_attribute_written', None)
    function = get_attribute(TARGET_ID, Attribute())
    with caplog.at_level('WARNING'), reading('configure'):
        check(function, depends_on())
    assert 'not shown to be present' in caplog.text


def test_a_check_that_says_written_silences_the_warning(written_check, caplog):
    function = get_attribute(TARGET_ID, Attribute())
    with caplog.at_level('WARNING'), reading('configure'):
        assert check(function, depends_on()) is True
    assert caplog.text == ''


def test_the_check_is_asked_with_the_node_path_kinds_and_reader(written_check):
    function = get_attribute(TARGET_ID, Attribute())
    with reading('configure', interface='Standard'):
        assert check(function, depends_on()) is True
    [(node, tokens, through, reader)] = written_check
    assert node.name == 'Vpc'
    assert tokens == ['vpc_id']
    assert through == ['DEPENDENCY']
    assert reader == ('standard', 'configure')


def test_a_read_that_is_not_by_an_operation_is_not_asked(written_check):
    function = get_attribute(TARGET_ID, Attribute())
    check(function, depends_on())
    assert written_check == []


def test_a_property_read_is_not_asked(written_check):
    function = Function(TARGET_ID, Value(False))
    with reading('configure'):
        check(function, depends_on())
    assert written_check == []
