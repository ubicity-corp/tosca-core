"""
Where an artifact's file is looked for.

An artifact that names a repository is found by its 'file' under that
repository, whichever file in its archive the declaring template is: an entry
template at the archive's root and one in a subdirectory, such as a profile's
Other-Definitions, find it at the same place. An artifact that names no
repository is found relative to the template that declares it, in that
template's own archive.

Repositories and profiles are stand-ins; no database is used.
"""

from types import SimpleNamespace

import pytest

from tosca_core.models.repository import ToscaRepository
from tosca_core.validate.artifact import ToscaArtifactValidator


class Repository:
    """A repository holding a fixed set of absolute paths."""

    def __init__(self, *paths):
        self.name = 'repository'
        self.paths = set(paths)

    get_absolute_path = ToscaRepository.get_absolute_path

    def exists(self, file_name):
        return file_name in self.paths


class Artifact(SimpleNamespace):
    """An artifact whose 'file' reads '_file', as the model's does."""

    @property
    def file(self):
        return self._file


def artifact(file, template, repo, repository=None):
    a = Artifact(name='artifact', _file=file, repo=repo,
                 profile=SimpleNamespace(tosca_file_path=template))
    if repository:
        a._repository = repository
    return a


@pytest.mark.parametrize("template", [
    "/main.yaml",
    "/substitutions/dcn/main.yaml",
])
def test_a_named_repository_resolves_from_its_root(template):
    store = Repository("/vendor/image.tar")
    a = artifact("vendor/image.tar", template, store, repository="store")
    assert ToscaArtifactValidator().validate_file(a) is None
    assert a._file == "/vendor/image.tar"


@pytest.mark.parametrize("template, expected", [
    ("/main.yaml", "/artifacts/create.sh"),
    ("/substitutions/dcn/main.yaml", "/substitutions/dcn/artifacts/create.sh"),
])
def test_no_repository_resolves_from_the_declaring_template(template, expected):
    csar = Repository(expected)
    a = artifact("artifacts/create.sh", template, csar)
    assert ToscaArtifactValidator().validate_file(a) is None
    assert a._file == expected


def test_a_missing_file_in_a_named_repository_is_reported():
    store = Repository()
    a = artifact("vendor/image.tar", "/substitutions/dcn/main.yaml", store,
                 repository="store")
    assert ToscaArtifactValidator().validate_file(a) == "'/vendor/image.tar' not found"
