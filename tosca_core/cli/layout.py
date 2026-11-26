"""
Where a CSAR keeps its metadata, and what its entry point is.

Mirrors CsarRepository's rules (tosca_core.models.csar_repository),
which are needed here before any ingest: to find profiles in a tree,
and to say something useful about a directory that is not a CSAR at
all. It decides where to look, never whether the contents are valid.
"""
from __future__ import annotations

from pathlib import Path

META_FILE = "TOSCA.meta"
META_DIR = "TOSCA-Metadata"


class AmbiguousMetadata(Exception):
    """Both metadata locations are populated, which a CSAR may not do"""


def find_meta(root: Path) -> Path | None:
    """The archive's metadata file, or None if it has none.

    A CSAR may carry TOSCA.meta at its root or under TOSCA-Metadata/,
    not both; ingest refuses both with "Multiple 'TOSCA.meta' files
    found".

    Raises:
      AmbiguousMetadata: when both are present
    """
    at_root = root / META_FILE
    in_dir = root / META_DIR / META_FILE
    found = [p for p in (at_root, in_dir) if p.is_file()]
    if len(found) > 1:
        raise AmbiguousMetadata(
            f"both {META_FILE} and {META_DIR}/{META_FILE} are present")
    return found[0] if found else None


def entry_definitions(meta: Path) -> str | None:
    """The Entry-Definitions value from a metadata file"""
    try:
        for line in meta.read_text().splitlines():
            key, sep, value = line.partition(":")
            if sep and key.strip() == "Entry-Definitions":
                return value.strip()
    except OSError:
        pass
    return None


def sole_top_level_file(root: Path) -> Path | None:
    """The single top-level file an archive without metadata falls back
    to, if there is exactly one.

    Counts files of any kind, as CsarRepository does, so a stray README
    makes the fallback ambiguous here for the same reason it does there.
    """
    files = [p for p in root.iterdir() if p.is_file()]
    return files[0] if len(files) == 1 else None
