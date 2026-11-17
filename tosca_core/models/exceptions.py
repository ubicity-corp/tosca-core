"""
The exceptions tosca-core raises.

An embedding application defines its own beside these, for what it does
with the models (running services, say), and may re-export these with them.
"""
from __future__ import annotations

__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2018-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Type hints
from typing import Any, Optional

# Logging support
import logging
logger: logging.Logger = logging.getLogger(__name__)


# Exceptions
class ValidationError(Exception):
    def __init__(self, message: str, errors: Optional[Any] = None) -> None:
        super(ValidationError, self).__init__(message)
        self.message: str = message
        self.errors: Optional[Any] = errors
    def __str__(self) -> str:
        import json
        return self.message + ':\n' + json.dumps(self.errors, ensure_ascii=False, indent=2)

class ProfileAlreadyExists(Exception):
    pass

class ProfileNotFound(Exception):
    pass

class TypeNotFound(Exception):
    pass

class TypeNotNamed(AttributeError):
    """An entity whose type must be named does not name it. An
    AttributeError, like a missing type, so that a refinement still takes
    the type of what it refines; validation reports its message."""
    pass

class CircularInheritance(Exception):
    pass

class FunctionNotFound(Exception):
    pass

class SignatureNotFound(Exception):
    pass

class TypeAlreadyExists(Exception):
    pass

class RepositoryNotFound(Exception):
    pass

class TemplateNotFound(Exception):
    pass

class DeletionRefused(Exception):
    """A profile or service template cannot be deleted: another profile
    imports it, or an embedding application holds services of it."""
    pass

# Topology-related exceptions:
class ModelCorruptionError(Exception):
    pass

class InvalidPathError(Exception):
    pass

class ProcessorError(Exception):
    """A function implementation failed: its artifact could not be run, or
    it returned no value though its signature declares a result."""
    pass
