"""
Implementing files: a TOSCA file whose 'implements' names an onboarded
profile adds implementations to that profile's functions and declares
nothing of its own.

An implementation is stored as artifacts on the implemented profile's
signatures, each recording the implementing profile as the one that
defined it; that profile is the artifact's profile for its repository, the
path its file is relative to, and its type's scope. A function-level
implementation applies to every signature, one on a signature overriding
it, signatures addressed by position. A signature with an implementation
already, declared or supplied, is a conflict. The implemented profile
shows its declarations as published, marking a signature implemented
elsewhere with 'implemented_by'; the implementing profile shows what it
implements in its file's form. An implementing file is never imported, and
the profile it implements cannot be deleted while it exists.
"""

import shutil
import textwrap

import pytest

from tosca_core import db
from tosca_core.core import reset_session
from tosca_core.csar import onboard_csar
from tosca_core.cli.profiles import _imports_of
from tosca_core.models import exceptions as te
from tosca_core.models.profile import get_profile_by_name
from tosca_core.schema.v2.profile import ProfileDetailSchema

TYPES = """\
    tosca_definitions_version: tosca_2_0
    profile: example.types:1.0
    artifact_types:
      Script:
        file_ext: [ py ]
    """

# Declares signatures only, apart from 'declared', which carries its own
# implementation.
FUNCTIONS = """\
    tosca_definitions_version: tosca_2_0
    profile: example.functions:1.0
    imports:
      - profile: example.types:1.0
    functions:
      single:
        signatures:
          - arguments: [ string ]
            result: string
      double:
        signatures:
          - arguments: [ string ]
            result: string
          - arguments: [ integer ]
            result: string
          - arguments: [ float ]
            result: string
      declared:
        signatures:
          - arguments: [ string ]
            result: string
            implementation:
              primary:
                type: Script
                file: declared.py
    """

IMPLEMENTS = """\
    tosca_definitions_version: tosca_2_0
    profile: example.functions.impl:1.0
    implements: example.functions:1.0
    imports:
      - profile: example.types:1.0
    functions:
      single:
        implementation:
          primary:
            type: Script
            file: impl/single.py
      double:
        implementation:
          primary:
            type: Script
            file: impl/double.py
        signatures:
          - {}
          - implementation:
              primary:
                type: Script
                file: impl/double_integer.py
    """


def write_profile(catalog, name, text, files=()):
    directory = catalog / name
    directory.mkdir()
    (directory / "TOSCA.meta").write_text(
        "CSAR-Version: 2.0\nCreated-By: tests\nEntry-Definitions: profile.yaml\n")
    (directory / "profile.yaml").write_text(textwrap.dedent(text))
    for file in files:
        (directory / file).parent.mkdir(parents=True, exist_ok=True)
        (directory / file).write_text("def f(*args):\n    return None\n")
    return directory


def zipped(directory):
    """The directory as a CSAR file beside it"""
    return shutil.make_archive(str(directory), "zip", str(directory))


def onboard(catalog, name, text, files=()):
    directory = write_profile(catalog, name, text, files)
    _repository, errors = onboard_csar(zipped(directory), name)
    return errors


@pytest.fixture
def implemented(catalog):
    """The implemented profile, committed, and a new session, so the
    implementing file meets it as loaded from the catalog"""
    assert onboard(catalog, "types", TYPES) == {}
    assert onboard(catalog, "functions", FUNCTIONS, ["declared.py"]) == {}
    db.session.commit()
    reset_session()
    return catalog


IMPL_FILES = ["impl/single.py", "impl/double.py", "impl/double_integer.py"]


@pytest.fixture
def implementing(implemented):
    assert onboard(implemented, "impl", IMPLEMENTS, IMPL_FILES) == {}
    return implemented


def signatures(function_name):
    return get_profile_by_name("example.functions:1.0").functions[function_name].signatures


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def test_the_implementations_are_artifacts_on_the_implemented_signatures(implementing):
    impl = get_profile_by_name("example.functions.impl:1.0")
    (signature,) = signatures("single")
    (artifact,) = signature.artifacts
    assert artifact.defining_profile is impl
    assert signature.implementation["primary"] is artifact
    # The implementing profile has none of its own
    assert impl.functions == {}


def test_an_implementing_artifact_has_the_implementing_profile_and_its_files(implementing):
    impl = get_profile_by_name("example.functions.impl:1.0")
    (artifact,) = signatures("single")[0].artifacts
    assert artifact.profile is impl
    assert artifact.repo is impl.repository
    assert artifact.retrieve().endswith("impl/single.py")
    assert artifact.declaration.type_entity.qualified_name == "example.types:1.0:Script"


def test_a_function_level_implementation_reaches_every_signature_but_overridden_ones(implementing):
    files = [signature.artifacts[-1].file for signature in signatures("double")]
    assert files == ["/impl/double.py", "/impl/double_integer.py", "/impl/double.py"]


def test_a_declared_implementation_records_its_own_profile(implemented):
    (artifact,) = signatures("declared")[0].artifacts
    assert artifact.defining_profile is get_profile_by_name("example.functions:1.0")


def test_implements_is_recorded_as_a_flagged_import(implementing):
    impl = get_profile_by_name("example.functions.impl:1.0")
    functions = get_profile_by_name("example.functions:1.0")
    assert impl.implements is functions
    assert functions.implemented_by == [impl]
    assert functions.implements is None


def test_the_implemented_profiles_names_are_in_scope(implementing):
    impl = get_profile_by_name("example.functions.impl:1.0")
    assert impl.get_function("single") is get_profile_by_name(
        "example.functions:1.0").functions["single"]


def test_an_unnamed_implementing_file_onboards(implemented):
    unnamed = IMPLEMENTS.replace("    profile: example.functions.impl:1.0\n", "")
    assert onboard(implemented, "unnamed", unnamed, IMPL_FILES) == {}
    (artifact,) = signatures("single")[0].artifacts
    assert not artifact.defining_profile.has_well_known_name


# ---------------------------------------------------------------------------
# What is refused
# ---------------------------------------------------------------------------

def extended(text):
    """IMPLEMENTS with top-level text added at its end"""
    return textwrap.dedent(IMPLEMENTS) + text


def refused(catalog, text, files=IMPL_FILES):
    errors = onboard(catalog, "refused", text, files)
    db.session.rollback()
    return str(errors)


def test_an_unknown_function_is_refused(implemented):
    text = IMPLEMENTS.replace("      single:\n", "      missing:\n")
    assert "not a function of 'example.functions:1.0'" in refused(implemented, text)


def test_more_signatures_than_declared_are_refused(implemented):
    text = IMPLEMENTS.replace("          - {}\n", "          - {}\n          - {}\n          - {}\n")
    assert "4 signatures given, 'double' declares 3" in refused(implemented, text)


@pytest.mark.parametrize("keyname, text", [
    ("arguments", "          - arguments: [ string ]\n"),
    ("description", "          - description: no\n"),
])
def test_a_signature_keyname_besides_implementation_is_refused(implemented, keyname, text):
    errors = refused(implemented, IMPLEMENTS.replace("          - {}\n", text))
    assert f"'{keyname}': 'not allowed in an implementing file'" in errors


def test_a_function_description_is_refused(implemented):
    text = IMPLEMENTS.replace("      single:\n", "      single:\n        description: no\n")
    assert "'description': 'not allowed in an implementing file'" in refused(implemented, text)


def test_a_declaration_is_refused(implemented):
    text = extended("data_types:\n  Mine: {}\n")
    assert "an implementing file declares nothing of its own" in refused(implemented, text)


def test_an_operation_refinement_is_refused(implemented):
    text = extended("node_types:\n  Mine: {}\n")
    assert "an implementing file may implement functions only" in refused(implemented, text)


def test_a_profile_not_onboarded_cannot_be_implemented(implemented):
    text = IMPLEMENTS.replace("implements: example.functions:1.0", "implements: example.other:1.0")
    assert "profile 'example.other:1.0' is not onboarded" in refused(implemented, text)


def test_a_declared_implementation_is_a_conflict(implemented):
    text = extended("  declared:\n    implementation: impl/single.py\n")
    assert "'example.functions:1.0' declares its implementation" in refused(implemented, text)


def test_a_second_implementing_file_is_a_conflict(implementing):
    text = IMPLEMENTS.replace("example.functions.impl:1.0", "example.functions.other:1.0")
    assert "already implemented by 'example.functions.impl:1.0'" in refused(implementing, text)


def test_an_implementing_file_cannot_be_imported_by_name(implementing):
    text = """\
        tosca_definitions_version: tosca_2_0
        profile: example.importer:1.0
        imports:
          - profile: example.functions.impl:1.0
        """
    assert "an implementing file cannot be imported" in refused(implementing, text, ())


def test_an_implementing_file_cannot_be_imported_by_url(implemented):
    directory = write_profile(implemented, "by_url", """\
        tosca_definitions_version: tosca_2_0
        profile: example.importer:1.0
        imports:
          - url: impl.yaml
        """)
    (directory / "impl.yaml").write_text(textwrap.dedent(IMPLEMENTS))
    _repository, errors = onboard_csar(zipped(directory), "by_url")
    db.session.rollback()
    assert "an implementing file cannot be imported" in str(errors)


def test_an_ordinary_file_gives_no_function_level_implementation(implemented):
    text = """\
        tosca_definitions_version: tosca_2_0
        profile: example.ordinary:1.0
        functions:
          mine:
            implementation: impl/single.py
            signatures:
              - result: string
        """
    errors = refused(implemented, text)
    assert "a function-level implementation is allowed only in an implementing file" in errors


# ---------------------------------------------------------------------------
# Removal
# ---------------------------------------------------------------------------

def test_the_implemented_profile_cannot_be_deleted(implementing):
    functions = get_profile_by_name("example.functions:1.0")
    impl = get_profile_by_name("example.functions.impl:1.0")
    assert functions.delete(check_only=True) is False
    with pytest.raises(te.DeletionRefused, match=f"implemented by Profile {impl.id}"):
        functions.delete()


def test_deleting_the_implementing_profile_takes_its_implementations(implementing):
    get_profile_by_name("example.functions.impl:1.0").delete()
    db.session.flush()
    db.session.expire_all()
    assert all(not signature.artifacts for signature in signatures("double"))
    assert len(signatures("declared")[0].artifacts) == 1
    assert get_profile_by_name("example.functions:1.0").delete(check_only=True) is True


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

def test_the_implemented_profile_shows_its_declarations_as_published(implementing):
    shown = ProfileDetailSchema().dump(get_profile_by_name("example.functions:1.0"))
    (single,) = shown["functions"]["single"]["signatures"]
    assert "implementation" not in single
    assert single["implemented_by"] == "example.functions.impl:1.0"
    (declared,) = shown["functions"]["declared"]["signatures"]
    assert declared["implementation"]["primary"]["file"] == "/declared.py"
    assert "implemented_by" not in declared


def test_the_implementing_profile_shows_its_implementations(implementing):
    shown = ProfileDetailSchema().dump(get_profile_by_name("example.functions.impl:1.0"))
    assert shown["implements"] == "example.functions:1.0"
    double = shown["functions"]["double"]["signatures"]
    assert [entry["implementation"]["primary"]["file"] for entry in double] == [
        "/impl/double.py", "/impl/double_integer.py", "/impl/double.py"]
    (single,) = shown["functions"]["single"]["signatures"]
    assert single["implementation"]["primary"]["file"] == "/impl/single.py"


# ---------------------------------------------------------------------------
# tosca-validate
# ---------------------------------------------------------------------------

def test_tosca_validate_orders_an_implementing_file_after_what_it_implements():
    assert _imports_of({"implements": "example.functions:1.0",
                        "imports": [{"profile": "example.types:1.0"}]}) == {
        "example.functions:1.0", "example.types:1.0"}
