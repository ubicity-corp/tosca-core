"""split_requirement_step: what follows RELATIONSHIP in a path to an artifact."""
import pytest

from tosca_core.models.path import split_requirement_step


def test_name_and_artifact():
    assert split_requirement_step(['host', 'TARGET', 'served']) == ('host', None, ['TARGET', 'served'])


def test_index_selects_one_relationship():
    assert split_requirement_step(['servers', 1, 'TARGET', 'served']) == ('servers', 1, ['TARGET', 'served'])


def test_one_element_left_is_a_bare_name():
    assert split_requirement_step(['servers', 0, 'served']) == ('servers', 0, 'served')


def test_all_is_no_index():
    assert split_requirement_step(['server', 'ALL', 'TARGET', 'served']) == ('server', None, ['TARGET', 'served'])


@pytest.mark.parametrize('sub_entity', [['host'], ['servers', 0], 'host'])
def test_nothing_after_the_requirement(sub_entity):
    with pytest.raises(TypeError):
        split_requirement_step(sub_entity)
