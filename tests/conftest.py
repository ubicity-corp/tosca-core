"""
Fixtures shared by the tests.
"""

import pytest

from tosca_core.bootstrap import bootstrap
from tosca_core.catalog import create_tables, load_normative_profiles
from tosca_core.constants import constants
from tosca_core.core import reset_session, session_scope


@pytest.fixture
def catalog(tmp_path):
    """A file-backed catalog holding the normative profiles, in a
    directory of its own that the test may also write templates to"""
    saved = {name: getattr(constants, name) for name in ("WORK_DIR", "LOCAL_REPO_ROOT")}
    constants.configure(WORK_DIR=str(tmp_path / "work"))
    bootstrap(f"sqlite:///{tmp_path / 'catalog.db'}")
    with session_scope():
        create_tables()
    with session_scope():
        load_normative_profiles()
    yield tmp_path
    reset_session()
    constants.configure(**saved)
