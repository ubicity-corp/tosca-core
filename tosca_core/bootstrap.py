"""
tosca-core bootstrap: what a process runs before it can use the models.

bootstrap() binds the database and imports the model and extension
modules the configuration lists. It configures no logging and writes
nothing but the database; an embedding application does its own setup
around it.
"""
from __future__ import annotations

import importlib
from typing import Optional

from tosca_core.constants import constants
from tosca_core.core import init_db


def bootstrap(db_uri: Optional[str] = None) -> None:
    """Bind the database and load the extensions to validation.

    Args:
      db_uri(string): database to bind; defaults to DB_URI
    """
    # Bind the database and load the model modules so SQLAlchemy can
    # resolve all mapper relationships
    init_db(db_uri if db_uri is not None else constants.DB_URI)

    # Load what this deployment adds to validation (tosca_core.extensions)
    for extension_module in constants.EXTENSION_MODULES:
        importlib.import_module(extension_module)
