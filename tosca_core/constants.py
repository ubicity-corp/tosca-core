"""
tosca-core configuration.

One CoreConfig object, `constants`, holds every setting tosca-core
reads. It loads standalone defaults at import: the definitions versions
and model modules from the packaged tosca_core.yaml, an in-memory SQLite
database, a per-user working directory, no local repository roots, no
and no state names. The environment can override all but the state names
(TOSCA_CORE_DB_URI, TOSCA_CORE_DIR, TOSCA_CORE_LOCAL_REPOSITORY_ROOTS).

An application embedding tosca-core calls constants.configure() with its
own values once at startup, before using the models. tosca-core reads
its settings when it needs them, never at import, so values configured
after import take effect.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field, fields
from importlib import resources
from typing import Any, Dict, List, Tuple

from ruamel.yaml import YAML

_CONFIG_FILE: str = "tosca_core.yaml"


def _default_work_dir() -> str:
    """A per-user directory tosca-core may read and write"""
    base = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
    return os.path.join(base, "tosca-core")


def _absolute_roots(roots: Any) -> Tuple[str, ...]:
    """Local repository roots as a tuple, each an absolute path

    Raises:
      ValueError: for a relative root, which would depend on the working
        directory
    """
    roots = tuple(roots)
    relative = [r for r in roots if not os.path.isabs(r)]
    if relative:
        raise ValueError("LOCAL_REPOSITORY_ROOTS must be absolute paths: " + ", ".join(relative))
    return roots


@dataclass(frozen=True)
class CoreConfig:
    """tosca-core's settings. Change them with configure(), not by
    assignment."""

    # Database the models are bound to by init_db() when no URI is given
    DB_URI: str = "sqlite://"

    # The directory tosca-core may read and write
    WORK_DIR: str = ""

    # Where onboarded CSARs are unpacked, under WORK_DIR by default
    LOCAL_REPO_ROOT: str = ""

    # Directories outside a CSAR that a 'file:' repository may name, each
    # absolute. Set by the operator, never by a template; empty, a template
    # reads only its own CSAR.
    LOCAL_REPOSITORY_ROOTS: Tuple[str, ...] = ()

    # tosca_definitions_version values accepted, each mapped to the
    # normative profile it implies
    SUPPORTED_DEFINITIONS_VERSIONS: Dict[str, str] = field(default_factory=dict)

    # Modules imported by init_db() so SQLAlchemy can resolve every mapper
    MODEL_MODULES: List[str] = field(default_factory=list)

    # Modules imported by bootstrap() to extend validation (tosca_core.extensions)
    EXTENSION_MODULES: List[str] = field(default_factory=list)

    # The states a 'set_state' activity may name. TOSCA defines none, so
    # empty accepts any; an application that runs workflows supplies its
    # own, and validation warns of a name outside them.
    STATE_NAMES: Tuple[str, ...] = ()

    def configure(self, **values: Any) -> None:
        """Replace settings in place, so every module holding this
        object sees the new values.

        Raises:
          TypeError: for a name that is not a setting
        """
        names = {f.name for f in fields(self)}
        unknown = sorted(set(values) - names)
        if unknown:
            raise TypeError(f"unknown tosca-core settings: {', '.join(unknown)}")
        if "LOCAL_REPOSITORY_ROOTS" in values:
            values["LOCAL_REPOSITORY_ROOTS"] = _absolute_roots(values["LOCAL_REPOSITORY_ROOTS"])
        if "STATE_NAMES" in values:
            values["STATE_NAMES"] = tuple(values["STATE_NAMES"])
        if "WORK_DIR" in values and "LOCAL_REPO_ROOT" not in values:
            values["LOCAL_REPO_ROOT"] = os.path.join(values["WORK_DIR"], "repository")
        for name, value in values.items():
            object.__setattr__(self, name, value)

    @classmethod
    def load(cls) -> "CoreConfig":
        """Standalone defaults: the packaged config file, then the
        environment"""
        config_file = resources.files("tosca_core.config").joinpath(_CONFIG_FILE)
        with config_file.open("r") as f:
            raw = YAML(typ="safe").load(f) or {}
        work_dir = os.environ.get("TOSCA_CORE_DIR") or _default_work_dir()
        roots = os.environ.get("TOSCA_CORE_LOCAL_REPOSITORY_ROOTS") or ""
        return cls(
            DB_URI=os.environ.get("TOSCA_CORE_DB_URI") or "sqlite://",
            WORK_DIR=work_dir,
            LOCAL_REPO_ROOT=os.path.join(work_dir, "repository"),
            LOCAL_REPOSITORY_ROOTS=_absolute_roots(r for r in roots.split(os.pathsep) if r),
            SUPPORTED_DEFINITIONS_VERSIONS=raw.get("SUPPORTED_DEFINITIONS_VERSIONS", {}),
            MODEL_MODULES=raw.get("MODEL_MODULES", []),
            EXTENSION_MODULES=raw.get("EXTENSION_MODULES", []),
        )


constants: CoreConfig = CoreConfig.load()
