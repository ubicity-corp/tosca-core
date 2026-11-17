"""
Path-flattening tests for ``ToscaPath.expression``.

A TOSCA path arrives as a sequence of segments, and ``expression``
returns those segments flat so callers can walk them one level at a
time. The tail's container kind varies with where the path was written:
a path written as a YAML block or flow sequence in a *value* position
parses to a list, while one written as a flow sequence in a *mapping
key* -- the form substitution attribute mappings use -- parses to a
tuple, because a mapping key must be hashable.

Both kinds carry the same path and must flatten identically. These tests
pin that, because a tail left unflattened is not rejected anywhere
downstream: ``Instance.set_attribute`` walks all but the last segment
and writes the last one as a key, so an unflattened tail silently
becomes a tuple-keyed entry that no reader ever finds.
"""

import pytest

from tosca_core.models.path import ToscaPath, extract_path_value


class TestExpressionFlattening:
    """``expression`` returns a flat list whatever the tail's container"""

    def test_two_segment_path(self):
        assert ToscaPath(["credentials", "kubeconfig"]).expression == [
            "credentials", "kubeconfig"]

    def test_three_segment_list_path(self):
        assert ToscaPath(["credentials", "kubeconfig", "file"]).expression == [
            "credentials", "kubeconfig", "file"]

    def test_three_segment_tuple_path(self):
        """A flow sequence in a mapping key parses to a tuple"""
        assert ToscaPath(("credentials", "kubeconfig", "file")).expression == [
            "credentials", "kubeconfig", "file"]

    def test_tuple_and_list_paths_agree(self):
        segments = ["credentials", "ssh_key", "name"]
        assert ToscaPath(tuple(segments)).expression == \
            ToscaPath(list(segments)).expression

    def test_deep_tuple_path(self):
        assert ToscaPath(("a", "b", "c", "d", "e")).expression == [
            "a", "b", "c", "d", "e"]

    def test_no_segment_is_itself_a_sequence(self):
        """A flat result holds only scalars, never a nested tail"""
        for segment in ToscaPath(("credentials", "kubeconfig", "file")).expression:
            assert not isinstance(segment, (list, tuple))


class TestInvalidPaths:
    """Shapes that do not describe a path are rejected"""

    @pytest.mark.parametrize("path", [
        "credentials",          # a string is iterable, but is not a path
        ["credentials"],        # a head with no sub-entity
        (),
        None,
        42,
    ])
    def test_rejected(self, path):
        with pytest.raises(TypeError):
            ToscaPath(path)


@pytest.fixture(scope="module")
def db_session(tmp_path_factory):
    """extract_path_value resolves each segment through the builtin
    integer type (which is what enables index-by-function), and that
    needs a catalog holding the normative profiles.
    """
    from tosca_core.bootstrap import bootstrap
    from tosca_core.catalog import create_tables, load_normative_profiles
    from tosca_core.constants import constants
    from tosca_core.core import session_scope
    constants.configure(WORK_DIR=str(tmp_path_factory.mktemp("tosca-core")))
    bootstrap("sqlite://")
    create_tables()
    load_normative_profiles()
    with session_scope():
        yield


@pytest.mark.usefixtures("db_session")
class TestExtractPathValue:
    """Descending into a value, where the field may not be there.

    `name` on a credential entry is optional: absent means the file's own
    default -- `[default]` for a cloud account, `current-context` for a
    kubeconfig. Reading it has to yield None rather than raise, or the
    "absent selects the default" half of the model cannot be read at all.
    Required fields are enforced when the model is built, so a key that
    is missing at read time is an optional one that was not supplied.
    """

    CREDS = {"cloud_account": {"file": "/vault/aws"}}
    NAMED = {"cloud_account": {"name": "cci", "file": "/vault/aws"}}

    def test_present_field(self):
        assert extract_path_value(None, self.NAMED, ["cloud_account", "name"]) == "cci"

    def test_absent_optional_field(self):
        assert extract_path_value(None, self.CREDS, ["cloud_account", "file"]) == "/vault/aws"
        assert extract_path_value(None, self.CREDS, ["cloud_account", "name"]) is None

    def test_absent_key_at_first_level(self):
        assert extract_path_value(None, self.CREDS, ["ssh_key", "file"]) is None

    def test_empty_value_short_circuits(self):
        assert extract_path_value(None, {}, ["cloud_account", "name"]) == {}
        assert extract_path_value(None, None, ["cloud_account", "name"]) is None

    def test_wrong_shape_still_raises(self):
        """Only an absent key is tolerated; a mis-shaped value is a defect."""
        with pytest.raises(TypeError):
            extract_path_value(None, {"cloud_account": "/vault/aws"},
                               ["cloud_account", "name"])

    def test_list_index_still_raises(self):
        """An index past the end of a list is a defect, not an absent key."""
        with pytest.raises(IndexError):
            extract_path_value(None, {"a": []}, ["a", 0])
