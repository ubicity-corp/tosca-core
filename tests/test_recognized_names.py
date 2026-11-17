"""
The interface and operation names the orchestrator recognizes by their
spelling: the dash case TOSCA 2.0 prescribes and the spelling of TOSCA 1.3,
treated as one name.
"""
import pytest

import tosca_core.models.recognized_names as rn


@pytest.mark.parametrize('name, expected', [
    ('Standard', 'standard'), ('standard', 'standard'),
    ('Configure', 'configure'),
    ('patch', 'patch'),
])
def test_an_interface_name_reads_in_dash_case(name, expected):
    assert rn.interface_name(name) == expected


@pytest.mark.parametrize('name, expected', [
    ('pre_create_source', 'pre-create-source'), ('add_target', 'add-target'),
    ('remove-source', 'remove-source'), ('create', 'create'), ('own_operation', 'own_operation'),
])
def test_an_operation_name_reads_in_dash_case(name, expected):
    assert rn.operation_name(name) == expected


@pytest.mark.parametrize('declared, asked', [
    ('Standard', 'standard'), ('standard', 'Standard'),
    ('Configure', 'configure'),
])
def test_an_interface_is_found_under_either_spelling(declared, asked):
    assert rn.lookup_interface({declared: 'found'}.__getitem__, asked) == 'found'


@pytest.mark.parametrize('declared, asked', [
    ('pre_configure_source', 'pre-configure-source'),
    ('remove-target', 'remove_target'),
])
def test_an_operation_is_found_under_either_spelling(declared, asked):
    assert rn.lookup_operation({declared: 'found'}.__getitem__, asked) == 'found'


def test_a_name_that_is_not_recognized_has_one_spelling():
    with pytest.raises(KeyError):
        rn.lookup_interface({'Patch': 'found'}.__getitem__, 'patch')
    with pytest.raises(KeyError):
        rn.lookup_operation({'own_operation': 'found'}.__getitem__, 'own-operation')


class Interface:
    def __init__(self, *operations):
        self.operations = set(operations)

    def get_operation_declaration(self, name):
        if name not in self.operations:
            raise KeyError(name)
        return name


@pytest.mark.parametrize('interface, asked, expected', [
    (Interface('add_target'), 'add-target', 'add_target'),
    (Interface('add-target'), 'add_target', 'add-target'),
    (Interface('create'), 'add-target', 'add-target'),
    (None, 'add-target', 'add-target'),
])
def test_an_operation_is_called_under_the_spelling_its_interface_declares(interface, asked,
                                                                           expected):
    assert rn.declared_operation(interface, asked) == expected


def test_the_lifecycle_interfaces_are_recognized_under_either_spelling():
    assert rn.is_standard_interface('standard') and rn.is_standard_interface('Standard')
    assert rn.is_configure_interface('configure') and rn.is_configure_interface('Configure')
    assert not rn.is_configure_interface('Associate')
