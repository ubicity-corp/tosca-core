"""
Artifact checksums (TOSCA 2.0 §12.2).

An artifact may give a checksum of its file and the algorithm it was computed
with. A checksum needs an algorithm the orchestrator has; case and hyphens in
its name do not matter, and a bare 'SHA' names no algorithm. A file that does
not match its checksum is refused, at onboarding and whenever it is fetched.

The checks run on temporary files; no repository or orchestrator is involved.
"""

import hashlib
from types import SimpleNamespace

import pytest

from tosca_core.models.artifact import check_checksum, checksum_algorithm_name, file_checksum
from tosca_core.validate import get_validator

HELLO_SHA256 = hashlib.sha256(b"hello\n").hexdigest()
HELLO_MD5 = hashlib.md5(b"hello\n").hexdigest()


@pytest.fixture
def hello(tmp_path):
    path = tmp_path / "hello.txt"
    path.write_text("hello\n")
    return str(path)


@pytest.mark.parametrize("name, expected", [
    ("MD5", "md5"), ("SHA-1", "sha1"), ("SHA-256", "sha256"), ("sha256", "sha256"),
    ("SHA3-256", "sha3_256"), ("sha3_512", "sha3_512"), ("BLAKE2b", "blake2b"),
])
def test_algorithm_names(name, expected):
    assert checksum_algorithm_name(name) == expected


@pytest.mark.parametrize("name", ["SHA", "CRC32", "shake_128"])
def test_unsupported_algorithm_is_refused(name):
    with pytest.raises(ValueError) as error:
        checksum_algorithm_name(name)
    assert "is not supported" in str(error.value)


def test_file_checksum(hello):
    assert file_checksum(hello, "sha256") == HELLO_SHA256
    assert file_checksum(hello, "md5") == HELLO_MD5


def test_matching_checksum_passes_whatever_its_case(hello):
    check_checksum(hello, HELLO_SHA256.upper(), "SHA-256")


def test_mismatching_checksum_is_refused(hello):
    with pytest.raises(ValueError) as error:
        check_checksum(hello, HELLO_MD5, "SHA-256")
    assert "does not match its checksum" in str(error.value)


def artifact(path, checksum=None, algorithm=None):
    """An artifact whose repository hands back the file at 'path'."""
    return SimpleNamespace(name="installer", file="hello.txt",
                           _checksum=checksum, _checksum_algorithm=algorithm,
                           repo=SimpleNamespace(retrieve=lambda file: path))


@pytest.mark.parametrize("checksum, algorithm, refusal", [
    (None, None, None),
    (HELLO_SHA256, "SHA-256", None),
    (HELLO_MD5, "md5", None),
    (HELLO_SHA256, None, "needs a 'checksum_algorithm'"),
    (HELLO_SHA256, "SHA", "is not supported"),
    (HELLO_MD5, "SHA-256", "does not match its checksum"),
], ids=["none", "sha256", "md5", "no-algorithm", "bare-sha", "mismatch"])
def test_onboarding_checks_the_checksum(hello, checksum, algorithm, refusal):
    result = get_validator('ToscaArtifact').validate_checksum(artifact(hello, checksum, algorithm))
    if refusal is None:
        assert result is None
    else:
        assert refusal in result
