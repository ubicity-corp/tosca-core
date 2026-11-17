"""
String, list and set functions with an argument that has no value.

A string, list or set function whose argument evaluates to no value
evaluates to no value itself, rather than treating the argument as empty:
a concatenation missing a piece is not a value. This holds for every
argument, not only the first, and for $join for every entry of the list
it joins.

DB-free: the built-in implementations are called directly.
"""

from tosca_core.builtin.functions import (concat_list, concat_string, intersection, join,
                                       token, union)


def test_strings_concatenate():
    assert concat_string(['http://', 'host', ':', '8080']) == 'http://host:8080'


def test_a_string_argument_with_no_value_leaves_no_value():
    assert concat_string(['http://', None, ':', '8080']) is None


def test_lists_concatenate():
    assert concat_list([['a'], [], ['b', 'c']]) == ['a', 'b', 'c']


def test_a_list_argument_with_no_value_leaves_no_value():
    assert concat_list([['a'], None, ['b']]) is None


def test_join():
    assert join([['a', 'b'], ':']) == 'a:b'
    assert join([['a', 'b']]) == 'ab'


def test_join_with_no_list_entry_or_delimiter_leaves_no_value():
    assert join([None, ':']) is None
    assert join([['a', None], ':']) is None
    assert join([['a', 'b'], None]) is None


def test_token_with_an_argument_with_no_value_leaves_no_value():
    assert token(['a:b', ':', 1]) == 'b'
    assert token([None, ':', 1]) is None
    assert token(['a:b', None, 1]) is None


def test_union_and_intersection():
    assert sorted(union([['a', 'b'], ['b', 'c']])) == ['a', 'b', 'c']
    assert intersection([['a', 'b'], ['b', 'c']]) == ['b']


def test_a_set_argument_with_no_value_leaves_no_value():
    assert union([None, ['a']]) is None
    assert union([['a'], None]) is None
    assert intersection([['a'], None]) is None
