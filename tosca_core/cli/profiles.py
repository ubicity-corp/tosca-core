"""
Finding the profiles in a tree, choosing which of them a catalog holds,
and putting them in the order they can be onboarded.

Everything here reads files and nothing more. The two TOSCA keywords it
looks at -- the 'profile' a file declares and the 'profile' of each
entry under 'imports' -- are read for ordering and selection only. It is
not an implementation of import resolution: getting it wrong costs an
extra onboarding pass or a later "profile not found", never a wrong
verdict.
"""
from __future__ import annotations

import os
import fnmatch
import zipfile
from pathlib import Path
from typing import NamedTuple

from tosca_core.cli import layout

#: Never contribute to a profile, and would only add churn to a cache key
IGNORED_DIRS = {".git", "__pycache__", ".github", "node_modules", ".pytest_cache"}


class Profile(NamedTuple):
    # Named for its path relative to its tree: io/kubernetes/1.35 is
    # io.kubernetes.1.35. What it declares itself is in declared_ids().
    name: str
    root: Path


class Selection(NamedTuple):
    """Which of the discovered profiles a catalog is built from.

    Patterns are fnmatch globs, tried against three spellings of each
    profile: the name:version it declares, that name without the
    version, and its directory-derived name. So 'com.example.infra',
    'com.example.infra:3.0' and '*:3.0' all select the same profile.

    'only' keeps what it matches and everything those profiles import,
    since a profile without its imports does not onboard. 'exclude'
    drops what it matches and wins over 'only'; dropping something
    another profile needs is allowed, and the profiles that then fail to
    onboard are reported like any other.
    """
    only: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()

    @property
    def restricted(self) -> bool:
        # Not __bool__: an empty Selection is a two-element tuple, so
        # tuple truthiness would say the opposite
        return bool(self.only or self.exclude)

    def as_extra(self) -> list[str]:
        """The selection's contribution to a catalog's cache key: two
        catalogs built from one tree under different restrictions hold
        different profiles"""
        return ([f"only={pattern}" for pattern in self.only]
                + [f"exclude={pattern}" for pattern in self.exclude])


def discover_profiles(profiles_dirs: list[Path]) -> list[Profile]:
    """Every profile under the given trees: each directory carrying a
    TOSCA.meta. Profiles do not nest, so a profile's own subdirectories
    are not searched."""
    found: list[Profile] = []
    for profiles_dir in profiles_dirs:
        for root, dirs, files in os.walk(profiles_dir):
            dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
            if layout.META_FILE in files or layout.META_DIR in dirs:
                path = Path(root)
                found.append(
                    Profile(".".join(path.relative_to(profiles_dir).parts), path))
                dirs[:] = []
    return sorted(found)


def zip_profile(src: Path, dest: Path) -> Path:
    """Archive a profile directory as a CSAR.

    Onboarding needs an archive: a bare directory is accepted only when
    validating. File modes go into external_attr because extraction
    restores them, and an artifact that loses its executable bit fails
    only when it is run.
    """
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(src):
            dirs[:] = sorted(d for d in dirs if d not in IGNORED_DIRS)
            for name in sorted(files):
                full = Path(root) / name
                info = zipfile.ZipInfo(str(full.relative_to(src)))
                info.external_attr = (os.stat(full).st_mode & 0xFFFF) << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(info, full.read_bytes())
    return dest


def _entry_file(root: Path) -> Path | None:
    """The top-level TOSCA file a CSAR directory's metadata names"""
    try:
        meta = layout.find_meta(root)
    except layout.AmbiguousMetadata:
        return None
    if meta is None:
        return None
    entry = layout.entry_definitions(meta)
    return root / entry if entry else None


def _parse(path: Path) -> dict | None:
    """One TOSCA document parsed, or None if it is not a readable
    mapping. Never raises: a file that does not parse is the
    validator's to report, with a line number."""
    from ruamel.yaml import YAML

    try:
        data = YAML(typ="safe", pure=True).load(path.read_text()) or {}
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _entry_data(root: Path) -> dict | None:
    """A CSAR directory's top-level document, parsed"""
    entry = _entry_file(root)
    if entry is None or not entry.is_file():
        return None
    return _parse(entry)


def _imports_of(data: dict) -> set[str]:
    """The profile names a parsed document imports, the one an
    implementing file implements among them: it onboards only after it"""
    names = {
        item["profile"]
        for item in data.get("imports") or []
        if isinstance(item, dict) and isinstance(item.get("profile"), str)
    }
    if isinstance(data.get("implements"), str):
        names.add(data["implements"])
    return names


def _own_name(data: dict) -> str | None:
    """The profile name a parsed document declares for itself"""
    own = data.get("profile") or data.get("namespace")
    return own if isinstance(own, str) else None


def declared_ids(profiles: list[Profile]) -> dict[str, str]:
    """Map each profile's directory-derived name to the name:version it
    declares, which is what an 'imports' entry and a selection pattern
    are written against"""
    ids: dict[str, str] = {}
    for profile in profiles:
        data = _entry_data(profile.root)
        own = _own_name(data) if data is not None else None
        if own:
            ids[profile.name] = own
    return ids


def declared_imports(profiles: list[Profile]) -> dict[str, set[str]]:
    """Map each profile to the profiles in this set it imports, both by
    directory-derived name. Imports of profiles outside the set (the
    normative ones, say) are left out."""
    declares: dict[str, str] = {}
    imports: dict[str, set[str]] = {p.name: set() for p in profiles}
    for profile in profiles:
        data = _entry_data(profile.root)
        if data is None:
            continue
        own = _own_name(data)
        if own:
            declares[own] = profile.name
        imports[profile.name] |= _imports_of(data)
    return {
        name: {declares[dep] for dep in deps if dep in declares and declares[dep] != name}
        for name, deps in imports.items()
    }


def dependency_order(profiles: list[Profile]) -> list[Profile]:
    """Profiles sorted so each follows the ones it imports. A cycle is
    broken arbitrarily: the order is a hint, and onboarding retries."""
    deps = declared_imports(profiles)
    by_name = {p.name: p for p in profiles}
    ordered: list[Profile] = []
    placed: set[str] = set()

    def place(name: str, seen: frozenset[str]) -> None:
        if name in placed or name in seen:
            return
        for dep in sorted(deps.get(name, ())):
            place(dep, seen | {name})
        if name not in placed:
            placed.add(name)
            ordered.append(by_name[name])

    for profile in profiles:
        place(profile.name, frozenset())
    return ordered


def _matches(pattern: str, name: str, declared: str | None) -> bool:
    """Whether a selection pattern picks out this profile"""
    candidates = {name}
    if declared:
        candidates.add(declared)
        candidates.add(declared.split(":", 1)[0])
    return any(fnmatch.fnmatchcase(c, pattern) for c in candidates)


def select(profiles: list[Profile],
           selection: Selection) -> tuple[list[Profile], dict[str, str]]:
    """Apply a Selection.

    Returns:
      (kept, dropped): the profiles to onboard, and {declared name: why
        it was left out}. The second is recorded with the catalog, so a
        target importing a dropped profile is refused by name rather
        than failing with a bare "profile not found".
    """
    if not selection.restricted:
        return list(profiles), {}

    ids = declared_ids(profiles)
    keep = {p.name for p in profiles}
    why: dict[str, str] = {}

    if selection.only:
        wanted = {p.name for p in profiles
                  if any(_matches(pat, p.name, ids.get(p.name))
                         for pat in selection.only)}
        # Keep what they import, transitively. Keeping too much costs
        # build time, not correctness.
        deps = declared_imports(profiles)
        closure, frontier = set(wanted), list(wanted)
        while frontier:
            for dep in deps.get(frontier.pop(), ()):
                if dep not in closure:
                    closure.add(dep)
                    frontier.append(dep)
        pattern_list = ", ".join(repr(p) for p in selection.only)
        for profile in profiles:
            if profile.name not in closure:
                why[profile.name] = f"--only-profile {pattern_list}"
        keep &= closure

    for profile in profiles:
        for pattern in selection.exclude:
            if _matches(pattern, profile.name, ids.get(profile.name)):
                why[profile.name] = f"--exclude-profile {pattern!r}"
                keep.discard(profile.name)
                break

    kept = [p for p in profiles if p.name in keep]
    dropped = {ids.get(name, name): reason for name, reason in why.items()}
    return kept, dropped


def target_imports(target: Path) -> set[str]:
    """The profile names a target imports or declares itself, as far as
    they can be read without the validator. Archives are not opened."""
    data = None
    if target.is_dir():
        data = _entry_data(target)
        if data is None:
            # No metadata: try the conventional names
            for name in ("main.yaml", "main.yml", "service.yaml"):
                if (target / name).is_file():
                    data = _parse(target / name)
                    break
    elif target.suffix in (".yaml", ".yml") and target.is_file():
        data = _parse(target)

    if data is None:
        return set()
    ids = _imports_of(data)
    own = _own_name(data)
    if own:
        ids.add(own)
    return ids


def unsupported(target: Path, dropped: dict[str, str]) -> str | None:
    """Why a catalog built without the 'dropped' profiles cannot answer
    for 'target', or None.

    Only profiles known to have been dropped count, so a target this
    cannot read is validated, never refused.
    """
    if not dropped:
        return None
    for profile_id in sorted(target_imports(target)):
        if profile_id in dropped:
            return (f"imports {profile_id}, which this catalog was built "
                    f"without ({dropped[profile_id]}). Validating against a "
                    "catalog that lacks it would judge the wrong types, so "
                    "it is not validated.")
    return None
