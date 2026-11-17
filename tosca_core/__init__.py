"""
tosca-core: a TOSCA parser and semantic validator.

Parses TOSCA 2.0 and TOSCA Simple Profile 1.3 service templates and
profiles, packaged as CSARs or as single files, into a model of types,
declarations and templates, and validates them against TOSCA semantics.

The names exported here are the public API (docs/api.md): kept stable
within a minor version, and changed only in a minor version, with notes,
before 1.0. Everything else -- the model classes, the schemas, the ingest
pipeline -- is internal and may change in any release.
"""
from importlib import import_module
from importlib.metadata import version, PackageNotFoundError
from typing import Any

try:
    __version__ = version("tosca-core")
except PackageNotFoundError:
    # Running from a checkout that is not installed
    __version__ = "0.0.0+unknown"

from .core import db

# The public API, by the module that defines each name. Imported when
# first used, so that importing tosca_core loads none of the models.
_PUBLIC = {
    # Validating and onboarding
    "validate_csar": "tosca_core.csar",
    "onboard_csar": "tosca_core.csar",
    # Building a catalog
    "bootstrap": "tosca_core.bootstrap",
    "create_tables": "tosca_core.catalog",
    "load_normative_profiles": "tosca_core.catalog",
    "CatalogError": "tosca_core.catalog",
    # Units of work
    "init_db": "tosca_core.core",
    "session_scope": "tosca_core.core",
    "reset_session": "tosca_core.core",
    # Configuration
    "constants": "tosca_core.constants",
    # Embedding: extending validation, creating instances
    "register_implementation_check": "tosca_core.extensions",
    "set_function_evaluator": "tosca_core.extensions",
    "set_attribute_written_check": "tosca_core.extensions",
    "CannotEvaluate": "tosca_core.extensions",
    # Clauses that could not be checked
    "unchecked": "tosca_core.models",
    # Errors
    "exceptions": "tosca_core.models",
    "ValidationError": "tosca_core.models.exceptions",
}

__all__ = ['db', '__version__', *_PUBLIC]


def __getattr__(name: str) -> Any:
    try:
        module = _PUBLIC[name]
    except KeyError:
        raise AttributeError(f"module 'tosca_core' has no attribute '{name}'") from None
    if module == "tosca_core.models":
        # A module of the API rather than a name in one
        value = import_module(f"tosca_core.models.{name}")
    else:
        value = getattr(import_module(module), name)
    globals()[name] = value
    return value
