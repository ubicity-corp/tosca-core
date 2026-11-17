"""
A TOSCA 2.0 file starts a path at SELF or a node's name.

TOSCA 1.3 started a relationship's paths at TARGET or SOURCE; TOSCA 2.0
(§10.3) spells them SELF, TARGET and SELF, SOURCE, so a path in a 2.0 file
that starts at TARGET or SOURCE is refused, naming its 2.0 spelling, for
each function that takes a path. A TOSCA 1.x file keeps the 1.3 heads, and
an entity whose version is unknown is not refused on a guess.

DB-free: the check runs on stand-in contexts.
"""

from types import SimpleNamespace

import pytest

from tosca_core.models.function_declaration import ToscaSignature, refuse_tosca_1_3_path_head


def context(version):
    return SimpleNamespace(tosca_version=version)


@pytest.mark.parametrize('head', ['TARGET', 'SOURCE'])
def test_a_1_3_head_is_refused_in_a_2_0_file(head):
    with pytest.raises(ValueError) as error:
        refuse_tosca_1_3_path_head('get_attribute', [head, 'instance_id'], context('tosca_2_0'))
    assert str(error.value) == (
        f"$get_attribute: [{head}, instance_id]: TOSCA 2.0 starts a path at SELF or a "
        f"node's name; write [SELF, {head}, instance_id]")


@pytest.mark.parametrize('version', ['tosca_simple_yaml_1_3', 'tosca_simple_yaml_1_0'])
def test_a_1_x_file_keeps_the_1_3_heads(version):
    refuse_tosca_1_3_path_head('get_attribute', ['TARGET', 'instance_id'], context(version))


@pytest.mark.parametrize('args', [
    ['SELF', 'TARGET', 'instance_id'],
    ['SELF', 'RELATIONSHIP', 'host', 'TARGET', 'name'],
    ['server', 'port'],
])
def test_a_2_0_path_is_accepted(args):
    refuse_tosca_1_3_path_head('get_attribute', args, context('tosca_2_0'))


def test_an_unknown_version_is_not_refused():
    refuse_tosca_1_3_path_head('get_attribute', ['TARGET', 'x'], context(None))
    refuse_tosca_1_3_path_head('get_attribute', ['TARGET', 'x'], SimpleNamespace())


@pytest.mark.parametrize('function', ['get_property', 'get_attribute', 'get_artifact'])
def test_each_path_function_refuses_it(function):
    """The check runs before the path is resolved, so the signature itself
    is not needed."""
    method = getattr(ToscaSignature, f'get_result_for_{function}')
    with pytest.raises(ValueError, match=r'write \[SELF, SOURCE, x\]'):
        method(None, context('tosca_2_0'), ['SOURCE', 'x'])
