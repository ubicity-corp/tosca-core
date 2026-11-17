"""
Validating and onboarding CSARs: the entry points for using tosca-core
as a library.

Both work against the catalog in the current session, which must hold
the normative profiles (see tosca_core.catalog) and any profile the
CSAR imports. Neither commits: that is the caller's decision, for
example through tosca_core.core.session_scope().
"""
from __future__ import annotations

import os
from typing import Any, Optional, Union

from tosca_core import db


def validate_csar(path: str, name: Optional[str] = None,
                  skip_file_checks: bool = False) -> Union[dict, str]:
    """Validate a CSAR, a CSAR directory or a single TOSCA file, and
    persist nothing.

    Rolls back the session afterwards, discarding anything the caller
    had not committed.

    Args:
      path(string): the file or directory to validate
      name(string): the name to report it under; defaults to the base
        name of 'path'
      skip_file_checks(bool): do not require the files that artifacts
        name to exist

    Returns:
      {} when it is valid; a string when it cannot be read at all (not a
      CSAR, no metadata); otherwise the errors as a nested dict: keyed by
      file, then by each step of the YAML path to what is wrong (keyname,
      template name, list index as a string), with a message, or a list of
      messages, at the end of each path, and the line number, where known,
      under 'line' beside the keys it locates (docs/api.md)
    """
    from tosca_core.actions.ingest_csar import ingest_csar_file
    try:
        _repository, errors = ingest_csar_file(
            name or os.path.basename(os.path.normpath(path)), path,
            validate_only=True, skip_file_checks=skip_file_checks)
        return errors or {}
    finally:
        db.session.rollback()


def onboard_csar(path: str, name: Optional[str] = None) -> tuple[Any, dict]:
    """Validate a CSAR and add its profile or service template to the
    catalog in the current session, without committing.

    Returns:
      (repository, errors): the errors as validate_csar returns them; on
        errors the caller should roll back
    """
    from tosca_core.actions.ingest_csar import ingest_csar_file
    repository, errors = ingest_csar_file(
        name or os.path.basename(os.path.normpath(path)), path)
    return repository, errors or {}
