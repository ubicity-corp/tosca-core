"""
Process-lifetime cache for built-in TOSCA data types.

The TOSCA built-ins (integer, float, string, boolean, list, map,
scalar, …) all live in the 'builtin' profile that ubctctl initialize
ingests once. Every other profile imports it implicitly, so
profile.get_data_type('integer') will eventually walk down into the
builtin profile and return the same entity regardless of which
profile asked.

To avoid re-walking the import graph from every validator and model
method that needs a built-in type, this module resolves the 'builtin'
profile once via get_profile_by_name('builtin'), then looks each
type up directly with get_local_type. Subsequent calls are served
from a dict.

Scope:
- Strictly limited to types defined in the 'builtin' profile. Callers
  that want a user-defined type should keep using
  profile.get_data_type, which respects the calling profile's import
  graph and any overrides.
- The cache lives at module level, so its lifetime is the Python
  process, which outlives any one session. A single CLI invocation can
  span several sessions -- deleting six services runs six teardowns --
  so every cached ORM object is re-merged into the current session
  before it is used. Caching the object itself and reading it directly
  leaves a detached instance whose lazy loads fail as soon as the
  session that loaded it closes.
- Re-merging cannot help when the cached object's row is gone: the
  catalog was rebuilt, an ingest that created it rolled back, or the
  session was bound to another database. reset() forgets the cache for
  those cases; tosca_core.core.reset_session() and init_db() call it.
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2026, Ubicity Corp."
__email__ = "info@ubicity.com"

from typing import Any

from tosca_core import db


_cache: dict[str, Any] = {}
_profile = None


def _builtin_profile() -> Any:
    """Return the 'builtin' profile, attached to the CURRENT session.

    Resolved once and cached, then re-merged on every call for the same
    reason ``get`` re-merges the types it caches: the cache outlives the
    session that populated it, and reading ``data_types`` off a detached
    profile raises DetachedInstanceError.
    """
    global _profile
    if _profile is None:
        # Imported lazily to avoid a cycle: tosca_core.models.profile
        # pulls in many of the same models that import this module.
        from tosca_core.models.profile import get_profile_by_name
        _profile = get_profile_by_name('builtin')
    return db.session.merge(_profile, load=False)


def get(name: str) -> Any:
    """Return the built-in TOSCA data type entity for `name`. Resolved
    once against the 'builtin' profile via get_local_type and cached.
    The cached object is re-merged into the current session on each
    call so that lazy-loadable attributes remain accessible across
    request boundaries (e.g. during autonomous recovery).
    """
    if name not in _cache:
        _cache[name] = _builtin_profile().get_local_type(name, 'data')
    return db.session.merge(_cache[name], load=False)


def reset() -> None:
    """Forget the cached built-in types and profile, so the next lookup
    resolves them against the current database"""
    global _profile
    _cache.clear()
    _profile = None
