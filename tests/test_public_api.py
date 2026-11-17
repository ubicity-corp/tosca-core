"""
The public API: what tosca-core keeps stable (docs/api.md).

The names `tosca_core` exports are the library's public surface; each
resolves to what its module defines, importing `tosca_core` loads none
of the models until one is used, and docs/api.md documents every one.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

import tosca_core

API_DOC = Path(__file__).resolve().parents[1] / "docs" / "api.md"


@pytest.mark.parametrize("name", tosca_core.__all__)
def test_every_exported_name_resolves(name):
    assert getattr(tosca_core, name) is not None


def test_exported_names_are_what_their_modules_define():
    from tosca_core.csar import validate_csar
    from tosca_core.extensions import register_implementation_check
    from tosca_core.models import unchecked
    assert tosca_core.validate_csar is validate_csar
    assert tosca_core.register_implementation_check is register_implementation_check
    assert tosca_core.unchecked is unchecked


def test_an_unknown_name_is_an_attribute_error():
    with pytest.raises(AttributeError):
        tosca_core.no_such_name


@pytest.mark.parametrize("name", [n for n in tosca_core.__all__ if n != "__version__"])
def test_the_api_document_names_every_export(name):
    assert f"`{name}" in API_DOC.read_text()


def test_importing_tosca_core_loads_no_models():
    probe = ("import json, sys, tosca_core; "
             "print(json.dumps(sorted(m for m in sys.modules if m.startswith('tosca_core.models'))))")
    result = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == []
