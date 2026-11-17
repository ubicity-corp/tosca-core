"""
How an artifact without a type gets one, and which of two types of the same name
a profile sees.

TOSCA 1.3 lets an artifact's type be inferred from its file extension. TOSCA 2.0
requires an artifact to name its type (section 12.2), so there an untyped
artifact is left without a declaration: it takes the type of the artifact it
refines, if any, and its validation otherwise reports that it does not name its
type.

Profile.get_types, which that inference searches, resolves a name the way
get_type does: a profile's own type before an imported one, and an earlier
import before a later one. So a profile that defines its own Bash keeps it when
an import brings another Bash into view.

Artifacts and profiles are stand-ins; no database is used.
"""

import importlib
from types import SimpleNamespace

import pytest

from tosca_core.constants import constants

# Creating an artifact builds a model object, which SQLAlchemy can configure
# only once every model is defined, as the migrate command arranges.
for model_module in constants.MODEL_MODULES:
    importlib.import_module(model_module)

import tosca_core.models.exceptions as te
from tosca_core.models.artifact import ToscaArtifact
from tosca_core.models.profile import ToscaProfile


# ---------------------------------------------------------------------------
# Inference from the file extension
# ---------------------------------------------------------------------------

class ArtifactType:
    def __init__(self, name):
        self.name = name

    def create_declaration(self, artifact_name):
        return SimpleNamespace(type_name=self.name, artifact=artifact_name)


class ProfileWithTypes:
    """A profile that knows one named type and infers `.sh` as a Bash."""

    def __init__(self, tosca_version):
        self.tosca_version = tosca_version

    def get_type(self, type_name, type_class):
        if type_name is None:
            raise AttributeError("no type")
        return ArtifactType(type_name)

    def get_artifact_types_for_ext(self, ext):
        return [ArtifactType("InferredBash")] if ext == "sh" else []


@pytest.fixture
def in_profile(monkeypatch):
    def use(tosca_version):
        profile = ProfileWithTypes(tosca_version)
        monkeypatch.setattr(ToscaArtifact, "profile", property(lambda self: profile))
    return use


def test_tosca_1_3_infers_the_type_from_the_file_extension(in_profile):
    in_profile("tosca_simple_yaml_1_3")
    declaration = ToscaArtifact(name="script", file="create.sh").create_declaration()
    assert declaration.type_name == "InferredBash"


def test_tosca_2_0_does_not_infer_the_type(in_profile):
    in_profile("tosca_2_0")
    with pytest.raises(te.TypeNotNamed) as error:
        ToscaArtifact(name="script", file="create.sh").create_declaration()
    assert str(error.value) == "does not name its type"


def test_tosca_2_0_uses_the_type_the_artifact_names(in_profile):
    in_profile("tosca_2_0")
    declaration = ToscaArtifact(name="script", file="create.sh", type="Bash").create_declaration()
    assert declaration.type_name == "Bash"


def test_tosca_1_3_extension_with_no_type_is_still_not_specified(in_profile):
    in_profile("tosca_simple_yaml_1_3")
    with pytest.raises(AttributeError):
        ToscaArtifact(name="data", file="payload.unknown").create_declaration()


# ---------------------------------------------------------------------------
# Which type of a shared name a profile sees
# ---------------------------------------------------------------------------

class Profile:
    """A stand-in carrying ToscaProfile's own lookup methods."""

    get_types = ToscaProfile.get_types
    get_artifact_types = ToscaProfile.get_artifact_types
    get_artifact_types_for_ext = ToscaProfile.get_artifact_types_for_ext

    def __init__(self, name, local, imports=()):
        self.name = name
        self._local = local
        self.imported = [SimpleNamespace(imported=p) for p in imports]

    def get_local_types(self, type_class):
        return dict(self._local)


def bash(owner):
    return SimpleNamespace(name=f"{owner}:Bash", supports_extension=lambda ext: ext == "sh")


def test_a_profiles_own_type_wins_over_one_it_imports():
    # com.ubicity defines Bash and imports com.ubicity.core, which imports the
    # community core profile and its own Bash.
    community = Profile("community.tosca.core", {"Bash": bash("community"), "Python": "community-python"})
    core = Profile("com.ubicity.core", {}, imports=[community])
    ubicity = Profile("com.ubicity", {"Bash": bash("ubicity")}, imports=[core])
    types = ubicity.get_types("artifact")
    assert types["Bash"].name == "ubicity:Bash"
    assert types["Python"] == "community-python"


def test_an_earlier_import_wins_over_a_later_one():
    first = Profile("first", {"Widget": "from-first"})
    second = Profile("second", {"Widget": "from-second"})
    template = Profile("template", {}, imports=[first, second])
    assert template.get_types("artifact")["Widget"] == "from-first"


def test_inference_finds_the_profiles_own_bash():
    community = Profile("community.tosca.core", {"Bash": bash("community")})
    core = Profile("com.ubicity.core", {}, imports=[community])
    ubicity = Profile("com.ubicity", {"Bash": bash("ubicity")}, imports=[core])
    template = Profile("template", {}, imports=[ubicity])
    assert [t.name for t in template.get_artifact_types_for_ext("sh")] == ["ubicity:Bash"]
