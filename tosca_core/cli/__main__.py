"""
tosca-validate: the command line.

  tosca-validate [-p PROFILE_TREE ...] TARGET ...

Each target is a CSAR, a CSAR directory or a single TOSCA file. The
catalog holds the normative profiles and every profile under the given
trees (TOSCA_CORE_PROFILES, a list separated like PATH, when none is
given), and is cached under WORK_DIR until the trees or tosca-core
change.

Exit status: 0 when every target is valid, 1 when any is not, 2 for a
usage error or a target the catalog was restricted from answering for.
"""
from __future__ import annotations

import os
import sys
import shutil
import logging
import argparse
import tempfile
from pathlib import Path

from tosca_core import __version__

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_ERROR = 2

#: Profile trees to use when no --profiles is given
PROFILES_ENV = "TOSCA_CORE_PROFILES"


def default_profiles_dirs() -> list[Path]:
    return [Path(d) for d in os.environ.get(PROFILES_ENV, "").split(os.pathsep) if d]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="tosca-validate",
        description="Validate TOSCA templates and profiles against a cached "
                    "catalog of the profiles they import.",
    )
    p.add_argument("targets", nargs="*", type=Path,
                   help="CSARs, CSAR directories, or TOSCA YAML files")
    p.add_argument("-p", "--profiles", type=Path, action="append", default=None,
                   metavar="DIR",
                   help="profile tree to build the catalog from; repeatable, "
                        "so trees that import each other can be combined "
                        f"(default: ${PROFILES_ENV}, else the normative "
                        "profiles only)")
    p.add_argument("--only-profile", action="append", default=None,
                   metavar="GLOB",
                   help="build the catalog from only the profiles matching "
                        "GLOB, plus the ones they import; repeatable. Matched "
                        "against the profile's declared name:version, e.g. "
                        "'org.*' or '*:3.0'")
    p.add_argument("--exclude-profile", action="append", default=None,
                   metavar="GLOB",
                   help="leave profiles matching GLOB out of the catalog; "
                        "repeatable, and wins over --only-profile. A target "
                        "importing one of them is not validated")
    p.add_argument("--rebuild", action="store_true",
                   help="rebuild the cached catalog even if it is current")
    p.add_argument("--catalog-info", action="store_true",
                   help="report the catalog cache state and exit")
    p.add_argument("--reset", action="store_true",
                   help="start from scratch: delete every cached catalog and "
                        "leftover run directory, then validate any targets "
                        "against a catalog built anew")
    p.add_argument("--skip-file-checks", action="store_true",
                   help="do not require the files that artifacts name to exist")
    p.add_argument("-f", "--format", choices=("text", "json"), default="text")
    p.add_argument("-v", "--verbose", action="store_true",
                   help="show catalog build progress and the validator's log")
    p.add_argument("-q", "--quiet", action="store_true",
                   help="suppress progress; print results only")
    p.add_argument("-V", "--version", action="version",
                   version=f"tosca-validate (tosca-core {__version__})")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.targets and not args.catalog_info and not args.reset:
        parser.error("no targets given")

    if args.reset:
        from tosca_core.cli import cache
        deleted = cache.reset()
        if not args.quiet:
            what = ", ".join(str(d) for d in deleted) if deleted else "nothing to delete"
            print(f"reset: {what}", file=sys.stderr)
        if not args.targets and not args.catalog_info:
            return EXIT_OK

    profiles_dirs = args.profiles or default_profiles_dirs()
    missing = [d for d in profiles_dirs if not d.is_dir()]
    if missing:
        for d in missing:
            print(f"error: profile tree {d} does not exist", file=sys.stderr)
        return EXIT_ERROR

    # Progress goes to stderr, so '-f json' output stays parseable
    def log(message: str) -> None:
        if not args.quiet:
            print(message, file=sys.stderr)

    from tosca_core.constants import constants
    from tosca_core.cli import cache
    from tosca_core.cli.profiles import Selection

    selection = Selection(tuple(args.only_profile or ()),
                          tuple(args.exclude_profile or ()))

    # The validator logs each error as it finds it, which repeats the
    # findings printed below, interleaved with them. Shown with -v only.
    core_logger = logging.getLogger("tosca_core")
    saved_level, saved_propagate = core_logger.level, core_logger.propagate
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    core_logger.addHandler(handler)
    core_logger.setLevel(logging.INFO if args.verbose else logging.CRITICAL)
    core_logger.propagate = False

    saved = {name: getattr(constants, name)
             for name in ("WORK_DIR", "LOCAL_REPO_ROOT")}
    runs = cache.runs_dir()
    runs.mkdir(parents=True, exist_ok=True)
    run_dir = Path(tempfile.mkdtemp(prefix="run-", dir=runs)).resolve()
    try:
        run_db, cached_db, key, hit = cache.plan(
            profiles_dirs, run_dir, rebuild=args.rebuild, selection=selection)
        if args.catalog_info:
            return _catalog_info(cache, cached_db, key, profiles_dirs, hit)

        # Confine this run to its own directory: CSARs are unpacked there,
        # and a file repository may name only files under it
        constants.configure(WORK_DIR=str(run_dir),
                            LOCAL_REPO_ROOT=str(run_dir / cache.RUN_REPO))
        from tosca_core.bootstrap import bootstrap
        from tosca_core.catalog import CatalogError
        bootstrap(f"sqlite:///{run_db}")

        from tosca_core.cli import report
        from tosca_core.cli.profiles import unsupported
        from tosca_core.cli.validate import Result, validate

        if hit:
            log(f"catalog: cache hit ({key})")
            _, dropped = cache.selection_of(cached_db)
        else:
            try:
                onboarded, failed, seconds, dropped = cache.build(
                    profiles_dirs, run_dir, log, selection=selection)
            except CatalogError as e:
                print(f"error: {e}: {e.errors}", file=sys.stderr)
                return EXIT_ERROR
            cache.publish(run_db, cached_db, profiles_dirs, key,
                          onboarded, failed, seconds,
                          selection=selection, dropped=dropped)
            log(f"catalog: built {len(onboarded)} profiles in {seconds:.1f}s ({key})")
            for name, error in failed:
                log(f"  warning: profile {name} did not onboard: {error}")

        results = []
        for target in args.targets:
            reason = unsupported(target, dropped)
            if reason:
                results.append(Result(target, [], None, 0.0, refused=reason))
            else:
                results.append(validate(target, args.skip_file_checks))

        report.render(results, args.format, root=Path.cwd(), dropped=dropped)
        if any(r.refused for r in results):
            # Not a verdict on the targets: the run asked for something
            # this catalog was built not to answer
            return EXIT_ERROR
        return EXIT_FINDINGS if any(not r.ok for r in results) else EXIT_OK
    finally:
        from tosca_core.core import reset_session
        reset_session()
        constants.configure(**saved)
        core_logger.removeHandler(handler)
        core_logger.setLevel(saved_level)
        core_logger.propagate = saved_propagate
        shutil.rmtree(run_dir, ignore_errors=True)


def _catalog_info(cache, cached_db: Path, key: str, profiles_dirs: list[Path],
                  hit: bool) -> int:
    for index, d in enumerate(profiles_dirs or ["(none: normative profiles only)"]):
        print(f"{'profile tree :' if index == 0 else '             :'} {d}")
    print(f"fingerprint  : {key}")
    print(f"catalog      : {cached_db}")
    if not hit:
        print("state        : not built (the next run builds it)")
        return EXIT_OK
    data = cache.read_manifest(cached_db)
    size = cached_db.stat().st_size / 1024
    print(f"state        : current ({size:.0f} KB, built in "
          f"{data.get('seconds', '?')}s)")
    print(f"onboarded    : {len(data.get('onboarded', []))} profiles")
    for name in data.get("onboarded", []):
        print(f"               {name}")
    failed = data.get("failed", [])
    if failed:
        print(f"not onboarded: {len(failed)}")
        for name, error in failed:
            print(f"               {name}: {error}")
    recorded = data.get("selection") or {}
    only, exclude = recorded.get("only") or [], recorded.get("exclude") or []
    if only:
        print(f"only         : {', '.join(only)}")
    if exclude:
        print(f"excluded     : {', '.join(exclude)}")
    dropped = data.get("dropped") or {}
    if dropped:
        print(f"left out     : {len(dropped)} profiles; a target importing one "
              "is not validated")
        for profile_id in sorted(dropped):
            print(f"               {profile_id}: {dropped[profile_id]}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
