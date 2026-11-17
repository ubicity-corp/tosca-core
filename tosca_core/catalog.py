"""
Creating the catalog: the database tables, and the normative profiles
every other profile and service template builds on.

Validation needs a catalog: resolving an import or a derived_from means
finding the type it names, and every definition ultimately derives from
the OASIS normative types. Run create_tables() and then
load_normative_profiles() once against a fresh database.
"""
from __future__ import annotations

# Logging support
import logging
logger = logging.getLogger(__name__)

import os
import shutil
from importlib import resources
from typing import Any

# Database support
from tosca_core import db
from tosca_core.constants import constants

# The normative profiles, packaged with tosca-core
CSARS_DIRECTORY = 'csars'
TOSCA_2_0_PROFILE_CSAR = 'org.oasis-open.tosca.2.0.csar'
SIMPLE_1_3_PROFILE_CSAR = 'org.oasis-open.simple.1.3.csar'


class CatalogError(Exception):
    """A normative profile could not be loaded"""

    def __init__(self, csar_name: str, errors: Any) -> None:
        super().__init__(f"cannot load {csar_name}")
        self.csar_name = csar_name
        self.errors = errors


def create_tables() -> None:
    """Create the table of every model module imported (init_db()
    imports MODEL_MODULES)"""
    logger.info("Initializing database schema ...")
    db.create_all()
    db.session.commit()


def load_normative_profiles() -> None:
    """Onboard the TOSCA 2.0 and TOSCA Simple Profile 1.3 normative
    profiles into the current session, and commit them.

    Empties LOCAL_REPO_ROOT first, since it holds the unpacked CSARs of
    the catalog being replaced.

    Raises:
      CatalogError: when a profile does not onboard; the session is
        left for the caller to roll back
    """
    import tosca_core.actions.ingest_csar as csar

    os.makedirs(constants.WORK_DIR, exist_ok=True)
    if os.path.exists(constants.LOCAL_REPO_ROOT):
        shutil.rmtree(constants.LOCAL_REPO_ROOT)
    os.makedirs(constants.LOCAL_REPO_ROOT)

    ref = resources.files('tosca_core').joinpath(CSARS_DIRECTORY)
    with resources.as_file(ref) as csar_dir:
        for csar_name in (TOSCA_2_0_PROFILE_CSAR, SIMPLE_1_3_PROFILE_CSAR):
            logger.info("Loading %s ...", csar_name)
            _profile, errors = csar.ingest_csar_file(csar_name, os.path.join(csar_dir, csar_name))
            if errors:
                raise CatalogError(csar_name, errors)

    db.session.commit()
