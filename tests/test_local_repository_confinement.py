"""
Where on the host a template may read files from.

A 'file:' repository is onboarded only when its resolved directory lies inside
the declaring CSAR's own directory or inside one of the local repository roots
the operator configures (LOCAL_REPOSITORY_ROOTS); the template cannot widen
that. Every fetch is then checked against the repository's own resolved
directory, so a symbolic link out of it, or a directory that only shares its
name as a prefix, is refused. A 'file:' URL may name no host but 'localhost':
any other host, this machine's own names among them, is refused rather than
opened. Deleting a CSAR's directory is in test_repository_paths.py.

Repositories are stand-ins; no database is used.
"""

import importlib
from types import SimpleNamespace

import pytest

from tosca_core.constants import CoreConfig, constants

for model_module in constants.MODEL_MODULES:
    importlib.import_module(model_module)

import tosca_core.models.exceptions as te
import tosca_core.models.repository as tr
from tosca_core.models.repository import ToscaRepository


def url(path):
    return path.as_uri() + "/"


@pytest.fixture
def csar(tmp_path):
    """A CSAR's directory holding one file, beside a file outside it."""
    root = tmp_path / "repo" / "csar"
    (root / "artifacts").mkdir(parents=True)
    (root / "artifacts" / "create.sh").write_text("")
    (tmp_path / "secret").write_text("")
    return root


@pytest.fixture
def roots():
    saved = constants.LOCAL_REPOSITORY_ROOTS

    def configure(*paths):
        constants.configure(LOCAL_REPOSITORY_ROOTS=[str(p) for p in paths])
    configure()
    yield configure
    constants.configure(LOCAL_REPOSITORY_ROOTS=saved)


def fetchable(repository_url, file_name):
    repository = SimpleNamespace(url=repository_url)
    return ToscaRepository.url_refusal(
        repository, ToscaRepository.get_file_url(repository, file_name)) is None


# ---------------------------------------------------------------------------
# Fetching from a repository
# ---------------------------------------------------------------------------

def test_a_file_in_the_repository_is_fetched(csar):
    assert fetchable(url(csar), "artifacts/create.sh")


def test_dot_segments_do_not_leave_the_repository(csar):
    assert not fetchable(url(csar), "../../secret")


def test_a_symbolic_link_out_of_the_repository_is_refused(csar, tmp_path):
    (csar / "artifacts" / "link").symlink_to(tmp_path / "secret")
    assert not fetchable(url(csar), "artifacts/link")


def test_a_sibling_sharing_the_repository_name_is_refused(csar, tmp_path):
    sibling = tmp_path / "repo" / "csar-backup"
    sibling.mkdir()
    (sibling / "x").write_text("")
    repository = SimpleNamespace(url=url(csar))
    assert ToscaRepository.url_refusal(repository, url(sibling) + "x")


def test_a_file_on_another_host_is_refused(csar):
    repository = SimpleNamespace(url=url(csar))
    other = "file://fileserver" + url(csar)[len("file://"):] + "artifacts/create.sh"
    assert "no host but 'localhost'" in ToscaRepository.url_refusal(repository, other)


def test_a_url_of_another_scheme_is_not_checked_here():
    assert fetchable("https://example.com/repo/", "x")


# ---------------------------------------------------------------------------
# Onboarding a repository
# ---------------------------------------------------------------------------

def test_a_repository_inside_the_csar_is_onboarded(csar, roots):
    assert tr.check_local_repository(url(csar / "artifacts"), url(csar)) is None


def test_a_repository_at_the_file_system_root_is_refused(csar, roots):
    assert "outside the CSAR" in tr.check_local_repository("file:///", url(csar))


def test_a_configured_root_is_onboarded(csar, roots, tmp_path):
    store = tmp_path / "store"
    store.mkdir()
    roots(store)
    assert tr.check_local_repository(url(store / "vendor"), url(csar)) is None


def test_a_sibling_of_a_configured_root_is_refused(csar, roots, tmp_path):
    roots(tmp_path / "store")
    assert tr.check_local_repository(url(tmp_path / "store-other"), url(csar))


def test_a_symbolic_link_out_of_the_csar_is_refused(csar, roots, tmp_path):
    (csar / "elsewhere").symlink_to(tmp_path)
    assert tr.check_local_repository(url(csar / "elsewhere"), url(csar))


def test_localhost_names_this_machine(csar, roots):
    localhost = "file://localhost" + url(csar)[len("file://"):]
    assert tr.check_local_repository(localhost, url(csar)) is None


@pytest.mark.parametrize("host", ["127.0.0.1", "fileserver"])
def test_any_other_host_is_refused(csar, roots, host):
    other = "file://" + host + url(csar)[len("file://"):]
    assert "no host but 'localhost'" in tr.check_local_repository(other, url(csar))


def test_a_repository_of_another_scheme_is_not_checked_here(csar, roots):
    assert tr.check_local_repository("https://example.com/repo/", url(csar)) is None


# ---------------------------------------------------------------------------
# A 'file:' URL without a repository
# ---------------------------------------------------------------------------

def test_a_localhost_url_is_a_path_in_the_csar():
    assert tr.normalize_file_uri("file://localhost/types.yaml") == "/types.yaml"


@pytest.mark.parametrize("file_url", [
    "file://localhost/etc/passwd", "file://127.0.0.1/etc/passwd", "file://tosca/etc/passwd"])
def test_a_file_url_is_never_a_repository_of_its_own(file_url):
    with pytest.raises(te.RepositoryNotFound, match="no host but 'localhost'"):
        tr.create_repository_for_url(file_url)


# ---------------------------------------------------------------------------
# Configuring the roots
# ---------------------------------------------------------------------------

def test_the_roots_come_from_the_environment(monkeypatch):
    monkeypatch.setenv("TOSCA_CORE_LOCAL_REPOSITORY_ROOTS", "/srv/a:/srv/b")
    assert CoreConfig.load().LOCAL_REPOSITORY_ROOTS == ("/srv/a", "/srv/b")


def test_there_are_no_roots_by_default(monkeypatch):
    monkeypatch.delenv("TOSCA_CORE_LOCAL_REPOSITORY_ROOTS", raising=False)
    assert CoreConfig.load().LOCAL_REPOSITORY_ROOTS == ()


def test_a_relative_root_is_refused(monkeypatch):
    monkeypatch.setenv("TOSCA_CORE_LOCAL_REPOSITORY_ROOTS", "store")
    with pytest.raises(ValueError, match="must be absolute"):
        CoreConfig.load()


def test_a_relative_root_is_refused_when_configured(roots):
    with pytest.raises(ValueError, match="must be absolute"):
        constants.configure(LOCAL_REPOSITORY_ROOTS=["store"])
