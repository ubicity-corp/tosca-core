"""
Building, caching and restoring the catalog a validation runs against.

A catalog is a SQLite database holding the normative profiles and every
profile in the given trees, plus the directory their CSARs were unpacked
into: the database records each one by the file URL of that directory,
and a function a profile implements with an artifact runs the file it
finds there where an evaluator is installed (tosca_core.extensions).
The two are cached together under WORK_DIR/catalogs, keyed by a hash of
the profile trees and of this package.

Every run works on a copy, in a run directory of its own. A miss builds
into that copy and then publishes it; a hit restores the cached one into
it. Either way validation happens against the copy, so a run can neither
damage the cache nor see another run's work.
"""
from __future__ import annotations

import os
import json
import time
import shutil
import sqlite3
import hashlib
import functools
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable, Iterable

from tosca_core.constants import constants
from tosca_core.cli.profiles import (IGNORED_DIRS, Profile, Selection,
                                      discover_profiles, dependency_order,
                                      select, zip_profile)

#: Bumped when a change to how a catalog is built or stored changes what
#: an existing cached one means
CATALOG_FORMAT = 1

#: The run's LOCAL_REPO_ROOT, under its run directory
RUN_REPO = "repository"


class CatalogError(Exception):
    """The catalog cannot be located or built as asked"""


def cache_dir() -> Path:
    """Where catalogs are cached: under WORK_DIR, the only directory
    tosca-core writes to"""
    return Path(constants.WORK_DIR) / "catalogs"


def runs_dir() -> Path:
    """Where each run works on its copy of a catalog, under WORK_DIR"""
    return Path(constants.WORK_DIR) / "runs"


def reset() -> list[Path]:
    """Start from scratch: delete every cached catalog and every run
    directory left behind, and nothing else under WORK_DIR. A run going on
    at the same time loses its copy.

    Returns:
      the directories deleted
    """
    deleted = []
    for directory in (cache_dir(), runs_dir()):
        if directory.is_dir() and not directory.is_symlink():
            shutil.rmtree(directory)
            deleted.append(directory)
    return deleted


@functools.cache
def engine_id() -> str:
    """tosca-core's version and a hash of its source.

    A catalog's schema is the ORM's, and its contents are what this
    code's parser made of the profiles, so a catalog built by other code
    must not be reused. The version alone does not change between
    commits of a checkout; the source does.
    """
    import tosca_core

    package = Path(tosca_core.__file__).resolve().parent
    h = hashlib.sha256()
    for root, dirs, files in os.walk(package):
        dirs[:] = sorted(d for d in dirs if d not in IGNORED_DIRS)
        for name in sorted(files):
            if name.endswith((".pyc", ".pyo")):
                continue
            full = Path(root) / name
            h.update(str(full.relative_to(package)).encode())
            h.update(full.read_bytes())
    return f"tosca-core/{tosca_core.__version__}/{h.hexdigest()[:12]}"


def fingerprint(profiles_dirs: list[Path], extra: Iterable[str] = ()) -> str:
    """Content hash of the profile trees, plus whatever else the catalog
    depends on.

    Hashes contents and executable bits, not modification times, so a
    fresh clone of the same trees hits the same entry. The local
    repository roots are part of the key: they decide which profiles
    declaring a 'file:' repository outside their CSAR onboard.
    """
    h = hashlib.sha256()
    h.update(f"format={CATALOG_FORMAT} engine={engine_id()}\n".encode())
    for root in constants.LOCAL_REPOSITORY_ROOTS:
        h.update(f"local-repository-root={root}\n".encode())
    for item in sorted(extra):
        h.update(f"extra={item}\n".encode())

    for profiles_dir in profiles_dirs:
        h.update(f"tree={profiles_dir.name}\n".encode())
        for root, dirs, files in os.walk(profiles_dir):
            dirs[:] = sorted(d for d in dirs if d not in IGNORED_DIRS)
            for name in sorted(files):
                full = Path(root) / name
                h.update(str(full.relative_to(profiles_dir)).encode())
                h.update(f":{os.stat(full).st_mode & 0o777:o}:".encode())
                with open(full, "rb") as fh:
                    for chunk in iter(lambda: fh.read(1 << 20), b""):
                        h.update(chunk)
    return h.hexdigest()[:16]


def manifest_path(db_path: Path) -> Path:
    return db_path.with_suffix(".json")


def repo_path(db_path: Path) -> Path:
    """Where a cached catalog keeps the CSARs its profiles were unpacked
    from"""
    return db_path.with_suffix(".repo")


def repo_url(root: Path) -> str:
    """The file URL prefix of CSARs unpacked under 'root', built the
    way CsarRepository builds it"""
    return urllib.parse.urljoin(
        "file:", urllib.request.pathname2url(os.path.abspath(root) + os.sep))


def read_manifest(db_path: Path) -> dict:
    try:
        return json.loads(manifest_path(db_path).read_text())
    except (OSError, ValueError):
        return {}


def selection_of(db_path: Path) -> tuple[Selection, dict[str, str]]:
    """The Selection a catalog was built with, and what it dropped. A
    catalog restores its restriction from its manifest, so a cache hit
    refuses what the catalog cannot answer for just as a build does."""
    manifest = read_manifest(db_path)
    recorded = manifest.get("selection") or {}
    selection = Selection(tuple(recorded.get("only") or ()),
                          tuple(recorded.get("exclude") or ()))
    dropped = manifest.get("dropped") or {}
    return selection, dropped if isinstance(dropped, dict) else {}


def restore(cached_db: Path, run_db: Path) -> None:
    """Copy a cached catalog into a run directory: the database, and the
    unpacked CSARs it refers to, pointed at their new location"""
    from tosca_core.models.repository import ToscaRepository

    shutil.copyfile(cached_db, run_db)
    run_repo = run_db.parent / RUN_REPO
    shutil.copytree(repo_path(cached_db), run_repo)
    old = read_manifest(cached_db)["repo_url"]
    new = repo_url(run_repo)
    table = ToscaRepository.__table__.name
    con = sqlite3.connect(run_db)
    try:
        rows = con.execute(f"SELECT id, _url FROM {table}").fetchall()
        con.executemany(f"UPDATE {table} SET _url = ? WHERE id = ?",
                        [(new + url[len(old):], id_) for id_, url in rows
                         if url and url.startswith(old)])
        con.commit()
    finally:
        con.close()


def plan(profiles_dirs: list[Path], run_dir: Path, rebuild: bool = False,
         selection: Selection = Selection()) -> tuple[Path, Path, str, bool]:
    """Decide the database a run uses, restoring the cached catalog into
    the run directory when there is a current one.

    Returns:
      (run_db, cached_db, key, hit): on a miss the caller builds into
        run_db and then calls publish()
    """
    run_db = run_dir / "catalog.sqlite"
    key = fingerprint([d.resolve() for d in profiles_dirs],
                      extra=selection.as_extra())
    cache = cache_dir()
    cache.mkdir(parents=True, exist_ok=True)
    cached_db = cache / f"catalog-{key}.sqlite"

    hit = (not rebuild and cached_db.exists() and repo_path(cached_db).is_dir()
           and "repo_url" in read_manifest(cached_db))
    if hit:
        restore(cached_db, run_db)
    return run_db, cached_db, key, hit


def _onboard_all(profiles: list[Profile], staging: Path,
                 log: Callable[[str], None]) -> tuple[list[str], list[tuple[str, str]]]:
    """Onboard every profile, in passes, until a pass makes no progress.

    dependency_order() gets the order mostly right; retrying is what
    makes it right, and it also lets the rest land when one profile
    cannot onboard at all.
    """
    from tosca_core import db
    from tosca_core.core import reset_session
    from tosca_core.csar import onboard_csar

    pending = dependency_order(profiles)
    onboarded: list[str] = []
    failures: dict[str, str] = {}

    while pending:
        progressed = False
        still: list[Profile] = []
        for profile in pending:
            csar_name = f"{profile.name}.csar"
            csar = zip_profile(profile.root, staging / csar_name)
            try:
                _repository, errors = onboard_csar(str(csar), csar_name)
            except Exception as e:
                errors = f"internal error ({e})"
            if errors:
                # A failed ingest can leave the session unusable for the
                # next one, not only uncommitted
                reset_session()
                failures[profile.name] = str(errors)
                still.append(profile)
            else:
                db.session.commit()
                onboarded.append(profile.name)
                failures.pop(profile.name, None)
                progressed = True
                log(f"  onboarded {profile.name}")
        if not progressed:
            break
        pending = still

    return onboarded, [(n, failures[n]) for n in sorted(failures)]


def build(profiles_dirs: list[Path], run_dir: Path, log: Callable[[str], None],
          selection: Selection = Selection()
          ) -> tuple[list[str], list[tuple[str, str]], float, dict[str, str]]:
    """Populate the bound database: the tables, the normative profiles,
    then the chosen profiles of the trees.

    Returns:
      (onboarded, failed, seconds, dropped)

    Raises:
      tosca_core.catalog.CatalogError: when a normative profile does
        not load
    """
    from sqlalchemy import text

    from tosca_core import db
    from tosca_core.catalog import create_tables, load_normative_profiles
    from tosca_core.core import reset_session

    started = time.time()
    discovered = discover_profiles(profiles_dirs)
    profiles, dropped = select(discovered, selection)
    log(f"building catalog: {len(profiles)} profiles"
        + (" under " + ", ".join(str(d) for d in profiles_dirs) if profiles_dirs else ""))
    if dropped:
        log(f"  restricted: {len(dropped)} of {len(discovered)} profiles left "
            f"out ({', '.join(sorted(dropped))})")

    create_tables()
    load_normative_profiles()
    log("  loaded the TOSCA 2.0 and Simple Profile 1.3 normative profiles")

    staging = run_dir / "staging"
    staging.mkdir(parents=True, exist_ok=True)
    onboarded, failed = _onboard_all(profiles, staging, log)
    shutil.rmtree(staging, ignore_errors=True)

    # SQLite runs in WAL mode, so the build is spread over the database
    # and its log until the log is folded back in; publish() copies one
    # file. Resetting afterwards keeps the build's session and cached
    # types out of the first validation.
    db.session.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
    db.session.commit()
    reset_session()
    return onboarded, failed, time.time() - started, dropped


def publish(run_db: Path, cached_db: Path, profiles_dirs: list[Path], key: str,
            onboarded: list[str], failed: list[tuple[str, str]],
            seconds: float, selection: Selection = Selection(),
            dropped: dict[str, str] | None = None) -> None:
    """Install a freshly built catalog into the cache.

    Each part is copied beside its final name and then renamed into
    place, CSARs first, so an interrupted publish never leaves a
    database in the cache without the CSARs it refers to.
    """
    run_repo = run_db.parent / RUN_REPO
    repo = repo_path(cached_db)
    tmp_repo = repo.with_name(repo.name + ".partial")
    shutil.rmtree(tmp_repo, ignore_errors=True)
    if run_repo.is_dir():
        shutil.copytree(run_repo, tmp_repo)
    else:
        tmp_repo.mkdir()
    shutil.rmtree(repo, ignore_errors=True)
    os.replace(tmp_repo, repo)

    tmp = cached_db.with_suffix(".sqlite.partial")
    shutil.copyfile(run_db, tmp)
    os.replace(tmp, cached_db)
    manifest_path(cached_db).write_text(json.dumps({
        "profiles_dirs": [str(d) for d in profiles_dirs],
        "fingerprint": key,
        "catalog_format": CATALOG_FORMAT,
        "engine": engine_id(),
        # The URL prefix the database records for the unpacked CSARs,
        # which restore() rewrites to wherever a run copies them
        "repo_url": repo_url(run_repo),
        "onboarded": onboarded,
        "failed": [[n, e] for n, e in failed],
        "seconds": round(seconds, 2),
        "selection": {"only": list(selection.only),
                      "exclude": list(selection.exclude)},
        "dropped": dict(dropped or {}),
    }, indent=2))
