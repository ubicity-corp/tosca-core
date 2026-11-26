"""
Validating one target, and flattening the validator's errors into a
list of findings.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, NamedTuple

from tosca_core.cli import layout


class Finding(NamedTuple):
    """One leaf error, and where in the document it was raised"""
    file: str                # TOSCA file within the target, e.g. "main.yaml"
    path: tuple[str, ...]    # keyname path, e.g. ("node_templates", "client")
    line: int | None
    message: str


class Result(NamedTuple):
    target: Path
    findings: list[Finding]
    fatal: str | None        # the target could not be read at all
    seconds: float
    # Set when the catalog was built without a profile this target
    # imports, so it was not validated. Apart from 'fatal' because it
    # says nothing about the target itself.
    refused: str | None = None
    # Validation clauses that could not be evaluated -- a function a
    # profile implements with an artifact, which nothing here runs. Their
    # values were accepted unchecked; they do not make a target fail.
    not_checked: tuple = ()

    @property
    def ok(self) -> bool:
        return not self.findings and self.fatal is None and self.refused is None


def flatten(errors: Any, file: str = "", path: tuple[str, ...] = (),
            line: int | None = None) -> list[Finding]:
    """Turn the validator's nested errors into a flat list.

    The errors are shaped like the documents that produced them, keyed
    by file name at the top, with 'line' keys at whatever level knew the
    line number. Each finding keeps its keyname path and the nearest
    enclosing line number.
    """
    if errors is None:
        return []
    if isinstance(errors, str):
        return [Finding(file, path, line, errors)]
    if isinstance(errors, dict):
        if isinstance(errors.get("line"), int):
            line = errors["line"]
        out: list[Finding] = []
        for key, value in errors.items():
            if key == "line":
                continue
            if not path and not file:
                out += flatten(value, str(key), (), line)
            else:
                out += flatten(value, file, path + (str(key),), line)
        return out
    if isinstance(errors, (list, tuple)):
        out = []
        for index, value in enumerate(errors):
            out += flatten(value, file, path + (str(index),), line)
        return out
    return [Finding(file, path, line, str(errors))]


def entry_point_problem(target: Path) -> str | None:
    """Why a directory cannot be read as a CSAR, if it cannot.

    Without metadata, ingest takes the single top-level file as the
    entry point, so a directory holding several profiles and a script
    fails with a YAML error about the script. Saying what is actually
    wrong costs one directory listing.
    """
    if not target.is_dir():
        return None
    try:
        meta = layout.find_meta(target)
    except layout.AmbiguousMetadata as e:
        return str(e)
    if meta is not None:
        return None
    sole = layout.sole_top_level_file(target)
    if sole is not None:
        if sole.suffix in (".yaml", ".yml"):
            return None
        return (f"no {layout.META_FILE}, and the only top-level file is "
                f"'{sole.name}', which is not a TOSCA file. If this directory "
                f"holds several profiles, validate each subdirectory instead.")

    names = sorted(p.name for p in target.iterdir() if p.is_file())
    if not names:
        return (f"no {layout.META_FILE} and no top-level file -- this "
                f"directory is not a CSAR. If it holds several profiles, "
                f"validate each subdirectory instead.")
    return (f"no {layout.META_FILE}, and {len(names)} top-level files "
            f"({', '.join(names)}) -- an archive without metadata must hold "
            f"exactly one. Add a {layout.META_FILE} naming the "
            f"Entry-Definitions, or pass the entry file itself.")


def validate(target: Path, skip_file_checks: bool = False) -> Result:
    """Validate a CSAR, a CSAR directory or a single TOSCA file against
    the catalog in the current session, and keep nothing"""
    from tosca_core.core import reset_session
    from tosca_core.csar import validate_csar
    from tosca_core.models import unchecked

    started = time.time()
    if not target.exists():
        return Result(target, [], "not found", 0.0)
    problem = entry_point_problem(target)
    if problem:
        return Result(target, [], problem, time.time() - started)
    try:
        with unchecked.collect() as not_checked:
            errors = validate_csar(str(target), target.name,
                                   skip_file_checks=skip_file_checks)
    except Exception as e:
        return Result(target, [], f"internal error ({e})", time.time() - started)
    finally:
        # validate_csar rolls back, but a failed validation can leave the
        # session unusable for the next target, not only uncommitted
        reset_session()

    seconds = time.time() - started
    if isinstance(errors, str):
        # The target itself could not be read
        return Result(target, [], errors, seconds)
    return Result(target, flatten(errors), None, seconds, not_checked=tuple(not_checked))
