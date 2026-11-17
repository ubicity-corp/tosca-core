"""
Which local paths a repository may read, and which it may delete.

Both checks confine a file:// repository to a directory: reading to the
repository's own directory, deleting to a repository inside the
repository root. Both used to compare strings,
so a sibling directory whose name merely starts with the allowed one
('<root>-backup') passed, and deleting could name the root itself.
They compare resolved paths now.
"""

from pathlib import Path
from types import SimpleNamespace

import pytest

from tosca_core.constants import constants
from tosca_core.models.csar_repository import CsarRepository
from tosca_core.models.repository import ToscaRepository


@pytest.fixture
def dirs(tmp_path):
    """A working directory holding the repository root, a repository in
    it, a sibling of the root, and a directory outside both"""
    saved = {name: getattr(constants, name) for name in ("WORK_DIR", "LOCAL_REPO_ROOT")}
    work = tmp_path / "work"
    root = work / "repository"
    repo = root / "some-csar"
    sibling = work / "repository-backup"
    outside = tmp_path / "outside"
    for d in (repo, sibling, outside):
        d.mkdir(parents=True)
        (d / "file.yaml").write_text("x")
    constants.configure(WORK_DIR=str(work), LOCAL_REPO_ROOT=str(root))
    yield SimpleNamespace(work=work, root=root, repo=repo, sibling=sibling, outside=outside)
    constants.configure(**saved)


def _delete(path):
    CsarRepository.delete_repo_dir(SimpleNamespace(url=Path(path).as_uri()))


def _readable(repo_dir, path):
    return ToscaRepository.url_refusal(SimpleNamespace(url=Path(repo_dir).as_uri()),
                                       Path(path).as_uri()) is None


@pytest.fixture
def models():
    """Every model class, so a real ToscaRepository can be built"""
    import importlib
    for module in constants.MODEL_MODULES:
        importlib.import_module(module)


# ---------------------------------------------------------------------------
# delete_repo_dir
# ---------------------------------------------------------------------------

def test_a_repository_inside_the_root_is_deleted(dirs):
    _delete(dirs.repo)
    assert not dirs.repo.exists()


def test_a_sibling_of_the_root_is_not_deleted(dirs):
    _delete(dirs.sibling)
    assert dirs.sibling.exists()


def test_the_root_itself_is_not_deleted(dirs):
    _delete(dirs.root)
    assert dirs.repo.exists()


def test_a_path_leaving_the_root_through_dotdot_is_not_deleted(dirs):
    _delete(str(dirs.root) + "/../repository-backup")
    assert dirs.sibling.exists()


# ---------------------------------------------------------------------------
# is_valid_url
# ---------------------------------------------------------------------------

def test_a_file_in_the_working_directory_is_not_readable(dirs):
    assert not _readable(dirs.outside, dirs.repo / "file.yaml")


def test_a_file_in_the_repository_itself_is_readable(dirs):
    assert _readable(dirs.outside, dirs.outside / "file.yaml")


def test_a_sibling_of_the_repository_is_not_readable(dirs, tmp_path):
    sibling = tmp_path / "outside-other"
    sibling.mkdir()
    (sibling / "file.yaml").write_text("x")
    assert not _readable(dirs.outside, sibling / "file.yaml")


def test_a_sibling_of_the_working_directory_is_not_readable(dirs, tmp_path):
    sibling = tmp_path / "work-other"
    sibling.mkdir()
    (sibling / "file.yaml").write_text("x")
    assert not _readable(dirs.repo, sibling / "file.yaml")


def test_dotdot_out_of_the_repository_is_not_readable(dirs, tmp_path):
    (tmp_path / "secret.yaml").write_text("x")
    assert not _readable(dirs.outside, str(dirs.outside) + "/../secret.yaml")


# ---------------------------------------------------------------------------
# What a refusal says
# ---------------------------------------------------------------------------

def test_a_refusal_names_the_path_and_the_repository(dirs, tmp_path):
    (tmp_path / "secret.yaml").write_text("x")
    refusal = ToscaRepository.url_refusal(SimpleNamespace(url=Path(dirs.outside).as_uri()),
                                          Path(str(dirs.outside) + "/../secret.yaml").as_uri())
    assert refusal.startswith("access denied: ")
    assert str((tmp_path / "secret.yaml").resolve()) in refusal
    assert str(dirs.outside.resolve()) in refusal
    assert "keep the file inside the repository" in refusal


def test_retrieving_a_refused_file_raises_the_reason_not_a_scheme_error(dirs, tmp_path, models):
    (tmp_path / "secret.yaml").write_text("x")
    repository = ToscaRepository(url=Path(dirs.outside).as_uri() + "/")
    with pytest.raises(ValueError) as error:
        repository.retrieve("../secret.yaml")
    assert "access denied" in str(error.value)
    assert "scheme" not in str(error.value)


def test_a_file_in_a_directory_with_a_space_is_readable(dirs, tmp_path, models):
    spaced = tmp_path / "my repo"
    spaced.mkdir()
    (spaced / "file.yaml").write_text("x")
    repository = ToscaRepository(url=spaced.as_uri() + "/")
    assert Path(repository.retrieve("file.yaml")).read_text() == "x"
