"""
tosca-validate: profile discovery and selection, the catalog cache, error
flattening, reporting, and the command line end to end.
"""

import io
import json
import os
import stat
import zipfile
from pathlib import Path

import pytest

from tosca_core.constants import constants
from tosca_core.lint import cache, profiles, report
from tosca_core.lint.__main__ import EXIT_ERROR, EXIT_FINDINGS, EXIT_OK, main
from tosca_core.lint.validate import Finding, Result, entry_point_problem, flatten


def _profile(root: Path, *parts: str) -> Path:
    d = root.joinpath(*parts)
    d.mkdir(parents=True)
    (d / "TOSCA.meta").write_text("Entry-Definitions: profile.yaml\n")
    (d / "profile.yaml").write_text("tosca_definitions_version: tosca_2_0\n")
    return d


def _named_profile(root: Path, name: str, *, imports: tuple[str, ...] = (),
                   body: str = "") -> Path:
    """A profile declaring 'name', in the directory its name implies"""
    d = root / name.replace(":", "/").replace(".", "/")
    d.mkdir(parents=True)
    (d / "TOSCA.meta").write_text(
        "CSAR-Version: 2.0\nCreated-By: tests\nEntry-Definitions: profile.yaml\n")
    lines = ["tosca_definitions_version: tosca_2_0", f"profile: {name}"]
    if imports:
        lines.append("imports:")
        lines += [f"  - profile: {i}" for i in imports]
    (d / "profile.yaml").write_text("\n".join(lines) + "\n" + body)
    return d


def _target(root: Path, *, imports: tuple[str, ...] = (), meta: bool = True) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    if meta:
        (root / "TOSCA.meta").write_text("Entry-Definitions: main.yaml\n")
    lines = ["tosca_definitions_version: tosca_2_0"]
    if imports:
        lines.append("imports:")
        lines += [f"  - profile: {i}" for i in imports]
    (root / "main.yaml").write_text("\n".join(lines) + "\n")
    return root


# ---------------------------------------------------------------------------
# Flattening the validator's errors
# ---------------------------------------------------------------------------

def test_flatten_keys_top_level_by_file():
    assert flatten({"main.yaml": "boom"}) == [Finding("main.yaml", (), None, "boom")]


def test_flatten_carries_the_nearest_line_down_to_the_leaf():
    errors = {"main.yaml": {"service_template": {"line": 28, "node_templates": {
        "client": {"type": "not found"}}}}}
    assert flatten(errors) == [Finding(
        "main.yaml", ("service_template", "node_templates", "client", "type"),
        28, "not found")]


def test_flatten_prefers_an_inner_line():
    errors = {"main.yaml": {"line": 1, "a": {"line": 9, "b": "bad"}}}
    assert flatten(errors)[0].line == 9


def test_flatten_never_reports_a_line_key():
    assert flatten({"main.yaml": {"line": 3}}) == []


def test_flatten_walks_lists():
    assert [f.path for f in flatten({"m.yaml": {"x": ["a", "b"]}})] == [("x", "0"), ("x", "1")]


def test_flatten_of_nothing_is_nothing():
    assert flatten(None) == [] and flatten({}) == []


def test_a_result_is_ok_only_when_clean():
    assert Result(Path("t"), [], None, 0.1).ok
    assert not Result(Path("t"), [Finding("m", (), 1, "x")], None, 0.1).ok
    assert not Result(Path("t"), [], "not found", 0.1).ok
    assert not Result(Path("t"), [], None, 0.0, refused="nope").ok


# ---------------------------------------------------------------------------
# Whether a directory can be read as a CSAR
# ---------------------------------------------------------------------------

def test_entry_point_ok_with_metadata(tmp_path):
    assert entry_point_problem(_target(tmp_path / "t")) is None


def test_entry_point_accepts_the_metadata_subdirectory(tmp_path):
    t = tmp_path / "t"
    (t / "TOSCA-Metadata").mkdir(parents=True)
    (t / "TOSCA-Metadata" / "TOSCA.meta").write_text("Entry-Definitions: main.yaml\n")
    (t / "main.yaml").write_text("tosca_definitions_version: tosca_2_0\n")
    (t / "README").write_text("x")
    assert entry_point_problem(t) is None


def test_entry_point_ok_with_a_single_template(tmp_path):
    assert entry_point_problem(_target(tmp_path / "t", meta=False)) is None


def test_entry_point_refuses_metadata_in_both_places(tmp_path):
    t = _target(tmp_path / "t")
    (t / "TOSCA-Metadata").mkdir()
    (t / "TOSCA-Metadata" / "TOSCA.meta").write_text("Entry-Definitions: main.yaml\n")
    assert "both" in entry_point_problem(t)


def test_entry_point_names_a_sole_file_that_is_not_tosca(tmp_path):
    t = tmp_path / "t"
    t.mkdir()
    (t / "run.sh").write_text("#!/bin/sh\n")
    assert "'run.sh'" in entry_point_problem(t)


def test_entry_point_refuses_several_files_without_metadata(tmp_path):
    t = _target(tmp_path / "t", meta=False)
    (t / "README").write_text("x")
    assert "2 top-level files" in entry_point_problem(t)


def test_entry_point_explains_a_directory_of_profiles(tmp_path):
    _profile(tmp_path / "t", "a")
    assert "not a CSAR" in entry_point_problem(tmp_path / "t")


def test_entry_point_leaves_files_to_the_validator(tmp_path):
    f = tmp_path / "x.csar"
    f.write_bytes(b"")
    assert entry_point_problem(f) is None


# ---------------------------------------------------------------------------
# Profile discovery and ordering
# ---------------------------------------------------------------------------

def test_discover_names_profiles_after_their_path(tmp_path):
    _profile(tmp_path, "com", "example", "core", "2.7")
    assert [p.name for p in profiles.discover_profiles([tmp_path])] == ["com.example.core.2.7"]


def test_discover_spans_several_trees(tmp_path):
    _profile(tmp_path / "one", "com", "a")
    _profile(tmp_path / "two", "com", "b")
    found = profiles.discover_profiles([tmp_path / "one", tmp_path / "two"])
    assert {p.name for p in found} == {"com.a", "com.b"}


def test_discover_does_not_descend_into_a_profile(tmp_path):
    root = _profile(tmp_path, "com", "a")
    (root / "sub").mkdir()
    (root / "sub" / "TOSCA.meta").write_text("Entry-Definitions: s.yaml\n")
    assert [p.name for p in profiles.discover_profiles([tmp_path])] == ["com.a"]


def test_discover_skips_vcs_directories(tmp_path):
    (tmp_path / ".git" / "x").mkdir(parents=True)
    (tmp_path / ".git" / "x" / "TOSCA.meta").touch()
    assert profiles.discover_profiles([tmp_path]) == []


def test_dependency_order_puts_imports_first(tmp_path):
    _named_profile(tmp_path, "com.b:1.0", imports=("com.a:1.0",))
    _named_profile(tmp_path, "com.a:1.0")
    names = [p.name for p in profiles.dependency_order(profiles.discover_profiles([tmp_path]))]
    assert names.index("com.a.1.0") < names.index("com.b.1.0")


def test_dependency_order_survives_a_cycle(tmp_path):
    _named_profile(tmp_path, "com.a:1.0", imports=("com.b:1.0",))
    _named_profile(tmp_path, "com.b:1.0", imports=("com.a:1.0",))
    found = profiles.discover_profiles([tmp_path])
    assert sorted(profiles.dependency_order(found)) == sorted(found)


def test_zip_profile_keeps_the_executable_bit(tmp_path):
    root = _profile(tmp_path, "com", "a")
    (root / "create.sh").write_text("#!/bin/sh\n")
    (root / "create.sh").chmod(0o755)
    with zipfile.ZipFile(profiles.zip_profile(root, tmp_path / "a.csar")) as z:
        assert (z.getinfo("create.sh").external_attr >> 16) & stat.S_IXUSR


# ---------------------------------------------------------------------------
# Restricting which profiles a catalog holds
# ---------------------------------------------------------------------------

def test_an_empty_selection_is_not_a_restriction():
    assert profiles.Selection().restricted is False


@pytest.mark.parametrize("pattern", ["com.b:2.0", "com.b", "*:2.0", "com.b*"])
def test_exclude_matches_every_spelling_of_a_profile(tmp_path, pattern):
    _named_profile(tmp_path, "com.a:1.0")
    _named_profile(tmp_path, "com.b:2.0")
    kept, dropped = profiles.select(profiles.discover_profiles([tmp_path]),
                                    profiles.Selection(exclude=(pattern,)))
    assert [p.name for p in kept] == ["com.a.1.0"]
    assert list(dropped) == ["com.b:2.0"]


def test_only_keeps_what_the_wanted_profiles_import(tmp_path):
    _named_profile(tmp_path, "org.app:1.0", imports=("com.mid:1.0",))
    _named_profile(tmp_path, "com.mid:1.0", imports=("com.base:1.0",))
    _named_profile(tmp_path, "com.base:1.0")
    _named_profile(tmp_path, "com.other:1.0")
    kept, dropped = profiles.select(profiles.discover_profiles([tmp_path]),
                                    profiles.Selection(only=("org.app",)))
    assert sorted(p.name for p in kept) == ["com.base.1.0", "com.mid.1.0", "org.app.1.0"]
    assert list(dropped) == ["com.other:1.0"]


def test_exclude_wins_over_only(tmp_path):
    _named_profile(tmp_path, "org.a:1.0")
    _named_profile(tmp_path, "org.b:1.0")
    kept, _ = profiles.select(profiles.discover_profiles([tmp_path]),
                              profiles.Selection(only=("org.*",), exclude=("org.b",)))
    assert [p.name for p in kept] == ["org.a.1.0"]


def test_unsupported_names_the_profile_and_the_reason(tmp_path):
    target = _target(tmp_path / "svc", imports=("com.a:3.0",))
    reason = profiles.unsupported(target, {"com.a:3.0": "--exclude-profile '*:3.0'"})
    assert "com.a:3.0" in reason and "--exclude-profile '*:3.0'" in reason


def test_unsupported_ignores_what_was_not_dropped(tmp_path):
    target = _target(tmp_path / "svc", imports=("com.b:1.0",))
    assert profiles.unsupported(target, {"com.a:3.0": "why"}) is None
    assert profiles.unsupported(target, {}) is None


def test_unsupported_reads_a_bare_yaml_target(tmp_path):
    single = tmp_path / "main.yaml"
    single.write_text("tosca_definitions_version: tosca_2_0\n"
                      "imports:\n  - profile: com.a:3.0\n")
    assert profiles.unsupported(single, {"com.a:3.0": "why"}) is not None


def test_unsupported_does_not_refuse_an_unreadable_target(tmp_path):
    target = _target(tmp_path / "svc")
    (target / "main.yaml").write_text("this: [is, not: valid yaml\n")
    assert profiles.unsupported(target, {"com.a:3.0": "why"}) is None


def test_unsupported_sees_the_profile_a_target_declares(tmp_path):
    target = _target(tmp_path / "prof")
    (target / "main.yaml").write_text("tosca_definitions_version: tosca_2_0\n"
                                      "profile: com.a:3.0\n")
    assert profiles.unsupported(target, {"com.a:3.0": "why"}) is not None


# ---------------------------------------------------------------------------
# Cache keys
# ---------------------------------------------------------------------------

def test_fingerprint_follows_content_not_mtime(tmp_path):
    root = _profile(tmp_path, "com", "a")
    before = cache.fingerprint([tmp_path])
    os.utime(root / "profile.yaml", (0, 0))
    assert cache.fingerprint([tmp_path]) == before
    (root / "profile.yaml").write_text("tosca_definitions_version: tosca_2_0\n# edit\n")
    assert cache.fingerprint([tmp_path]) != before


def test_fingerprint_follows_the_executable_bit(tmp_path):
    script = _profile(tmp_path, "com", "a") / "create.sh"
    script.write_text("#!/bin/sh\n")
    before = cache.fingerprint([tmp_path])
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    assert cache.fingerprint([tmp_path]) != before


def test_fingerprint_distinguishes_tree_sets(tmp_path):
    _profile(tmp_path / "one", "com", "a")
    _profile(tmp_path / "two", "com", "b")
    assert (cache.fingerprint([tmp_path / "one"])
            != cache.fingerprint([tmp_path / "one", tmp_path / "two"]))


def test_a_restriction_changes_the_key_and_its_order_does_not(tmp_path):
    _profile(tmp_path, "com", "a")
    key = lambda s: cache.fingerprint([tmp_path], extra=s.as_extra())
    Selection = profiles.Selection
    assert key(Selection()) != key(Selection(exclude=("com.a",)))
    assert key(Selection(only=("com.a",))) != key(Selection(exclude=("com.a",)))
    assert key(Selection(exclude=("a", "b"))) == key(Selection(exclude=("b", "a")))


def test_the_key_follows_the_engine(tmp_path, monkeypatch):
    before = cache.fingerprint([tmp_path])
    monkeypatch.setattr(cache, "engine_id", lambda: "tosca-core/other")
    assert cache.fingerprint([tmp_path]) != before


def test_the_key_follows_the_local_repository_roots(tmp_path):
    saved = constants.LOCAL_REPOSITORY_ROOTS
    before = cache.fingerprint([tmp_path])
    try:
        constants.configure(LOCAL_REPOSITORY_ROOTS=[str(tmp_path / "store")])
        assert cache.fingerprint([tmp_path]) != before
    finally:
        constants.configure(LOCAL_REPOSITORY_ROOTS=saved)


def test_a_manifest_without_a_selection_reads_as_unrestricted(tmp_path):
    db = tmp_path / "catalog.sqlite"
    cache.manifest_path(db).write_text(json.dumps({"fingerprint": "abc"}))
    selection, dropped = cache.selection_of(db)
    assert selection.restricted is False and dropped == {}


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def _render(results, fmt="text", **kwargs) -> str:
    out = io.StringIO()
    report.render(results, fmt, stream=out, **kwargs)
    return out.getvalue()


def test_report_counts_a_refusal_apart_from_a_failure():
    text = _render([
        Result(Path("bad"), [Finding("main.yaml", (), 1, "boom")], None, 0.1),
        Result(Path("skipped"), [], None, 0.0, refused="imports com.a:3.0"),
    ])
    assert "1 of 2 target(s) failed" in text
    assert "1 of 2 target(s) import a profile left out" in text
    assert "SKIP" in text


def test_json_carries_findings_and_refusals():
    payload = json.loads(_render([
        Result(Path("a"), [Finding("m.yaml", ("x", "y"), 3, "bad")], None, 0.1),
        Result(Path("b"), [], None, 0.0, refused="because"),
    ], "json"))
    assert payload["format"] == 1
    payload = payload["results"]
    assert payload[0]["findings"] == [
        {"file": "m.yaml", "path": ["x", "y"], "line": 3, "message": "bad"}]
    assert payload[1]["refused"] == "because" and payload[1]["ok"] is False


def test_a_clause_not_checked_is_reported_and_does_not_fail():
    from tosca_core.models.unchecked import NotChecked
    note = NotChecked("property 'number'", "50", ("$in_range",))
    result = Result(Path("svc"), [], None, 0.1, not_checked=(note,))
    assert result.ok
    text = _render([result])
    assert "not checked  property 'number' = 50: $in_range could not be evaluated" in text
    assert "1 validation clause(s) in 1 target(s) not checked" in text
    assert "no errors" in text
    payload = json.loads(_render([result], "json"))["results"]
    assert payload[0]["ok"] is True
    assert payload[0]["not_checked"] == [
        {"subject": "property 'number'", "value": "50", "functions": ["$in_range"]}]


def test_nothing_not_checked_says_nothing():
    text = _render([Result(Path("svc"), [], None, 0.1)])
    assert "not checked" not in text
    payload = json.loads(_render([Result(Path("svc"), [], None, 0.1)], "json"))
    assert payload["results"][0]["not_checked"] == []


def test_the_missing_profile_hint_depends_on_the_restriction():
    missing = [Result(Path("svc"), [Finding("main.yaml", ("imports", "com.a:1.0"),
                                            None, "profile not found")], None, 0.1)]
    assert "add the tree that defines them" in _render(missing)
    restricted = _render(missing, dropped={"com.b:1.0": "--exclude-profile"})
    assert "restricted" in restricted
    assert "add the tree that defines them" not in restricted


# ---------------------------------------------------------------------------
# The command line, end to end
# ---------------------------------------------------------------------------

_SERVER_TYPE = "node_types:\n  Server: {}\n"


@pytest.fixture
def work_dir(tmp_path, monkeypatch):
    """A WORK_DIR of the test's own, so catalogs are cached there"""
    monkeypatch.delenv("TOSCA_CORE_PROFILES", raising=False)
    saved = {name: getattr(constants, name) for name in ("WORK_DIR", "LOCAL_REPO_ROOT")}
    constants.configure(WORK_DIR=str(tmp_path / "work"))
    yield tmp_path / "work"
    constants.configure(**saved)


def _service(root: Path, node_type: str, imports: str = "") -> Path:
    root.mkdir(parents=True)
    (root / "main.yaml").write_text(
        "tosca_definitions_version: tosca_2_0\n" + imports +
        f"service_template:\n  node_templates:\n    server:\n      type: {node_type}\n")
    return root


_IMPORT_BASE = "imports:\n  - profile: org.example.base:1.0\n    namespace: base\n"


_CHECKS = """artifact_types:
  Python:
    file_ext: [py]
functions:
  between:
    signatures:
      - arguments:
          - type: integer
          - type: list
            entry_schema: integer
        result: boolean
        implementation:
          primary:
            type: Python
            file: functions/between.py
"""


def test_a_clause_on_a_function_implemented_by_an_artifact_is_not_checked(
        work_dir, tmp_path, capsys):
    """tosca-core runs no artifact: the clause is reported, not passed"""
    tree = tmp_path / "profiles"
    profile = _named_profile(tree, "org.example.checks:1.0", body=_CHECKS)
    (profile / "functions").mkdir()
    (profile / "functions" / "between.py").write_text("import sys\n")
    svc = tmp_path / "svc"
    svc.mkdir()
    (svc / "main.yaml").write_text(
        "tosca_definitions_version: tosca_2_0\n"
        "imports:\n  - profile: org.example.checks:1.0\n"
        "node_types:\n  Port:\n    properties:\n      number:\n"
        "        type: integer\n"
        "        validation: { $between: [ $value, [1, 10] ] }\n"
        "service_template:\n  node_templates:\n    port:\n      type: Port\n"
        "      properties:\n        number: 50\n")
    assert main(["-q", "-p", str(tree), str(svc)]) == EXIT_OK
    out = capsys.readouterr().out
    assert "not checked  property 'number' = 50: $between could not be evaluated" in out


def _checked_service(tmp_path: Path, number: int, profile: str) -> Path:
    svc = tmp_path / f"svc{number}"
    svc.mkdir()
    (svc / "main.yaml").write_text(
        "tosca_definitions_version: tosca_2_0\n"
        f"imports:\n  - profile: {profile}\n"
        "node_types:\n  Port:\n    properties:\n      number:\n"
        "        type: integer\n"
        "        validation: { $between: [ $value, [1, 10] ] }\n"
        "service_template:\n  node_templates:\n    port:\n      type: Port\n"
        f"      properties:\n        number: {number}\n")
    return svc


@pytest.fixture
def community_checks(tmp_path):
    """A profile implementing $between in Python, with the TOSCA
    community's Python type; the file leaves a mark if it is ever loaded"""
    tree = tmp_path / "community"
    profile = _named_profile(tree, "community.tosca.core:0.9", body=_CHECKS)
    (profile / "functions").mkdir()
    mark = tmp_path / "loaded"
    (profile / "functions" / "between.py").write_text(
        f"open({str(mark)!r}, 'w').close()\n"
        "def between(args):\n"
        "    value, (low, high) = args\n"
        "    return low <= value <= high\n")
    return tree


def test_a_function_implemented_in_python_is_not_run(work_dir, tmp_path, community_checks, capsys):
    """Not even with the community's Python type: a valid and an invalid
    value are both accepted, each with the clause reported as not checked"""
    for number in (5, 50):
        svc = _checked_service(tmp_path, number, "community.tosca.core:0.9")
        assert main(["-q", "-p", str(community_checks), str(svc)]) == EXIT_OK
        assert "$between could not be evaluated" in capsys.readouterr().out
    assert not (tmp_path / "loaded").exists()


def test_a_valid_and_an_invalid_template(work_dir, tmp_path, capsys):
    good = _service(tmp_path / "good", "Server", _SERVER_TYPE)
    bad = _service(tmp_path / "bad", "NoSuchType")
    assert main(["-q", str(good)]) == EXIT_OK
    capsys.readouterr()
    assert main(["-q", "-f", "json", str(good), str(bad)]) == EXIT_FINDINGS
    payload = json.loads(capsys.readouterr().out)["results"]
    assert [r["ok"] for r in payload] == [True, False]
    assert payload[1]["findings"]


def test_a_template_validates_against_a_profile_from_a_tree(work_dir, tmp_path, capsys):
    tree = tmp_path / "profiles"
    _named_profile(tree, "org.example.base:1.0", body=_SERVER_TYPE)
    svc = _service(tmp_path / "svc", "base:Server", _IMPORT_BASE)

    # Without the tree the import is missing, and the report says so
    assert main(["-q", str(svc)]) == EXIT_FINDINGS
    assert "not in the catalog: org.example.base:1.0" in capsys.readouterr().out

    assert main(["-q", "-p", str(tree), str(svc)]) == EXIT_OK

    # The second run restores the cached catalog rather than building it
    assert main(["-p", str(tree), str(svc)]) == EXIT_OK
    assert "cache hit" in capsys.readouterr().err
    assert len(list((work_dir / "catalogs").glob("catalog-*.sqlite"))) == 2


def test_the_profile_tree_can_come_from_the_environment(work_dir, tmp_path, monkeypatch):
    tree = tmp_path / "profiles"
    _named_profile(tree, "org.example.base:1.0", body=_SERVER_TYPE)
    svc = _service(tmp_path / "svc", "base:Server", _IMPORT_BASE)
    monkeypatch.setenv("TOSCA_CORE_PROFILES", str(tree))
    assert main(["-q", str(svc)]) == EXIT_OK


def test_a_restricted_catalog_refuses_what_it_left_out(work_dir, tmp_path, capsys):
    tree = tmp_path / "profiles"
    _named_profile(tree, "org.example.base:1.0", body=_SERVER_TYPE)
    svc = _service(tmp_path / "svc", "base:Server", _IMPORT_BASE)
    args = ["-q", "-p", str(tree), "--exclude-profile", "org.example.*", str(svc)]
    assert main(args) == EXIT_ERROR
    # And still does on a cache hit, from what the catalog recorded
    assert main(args) == EXIT_ERROR
    assert capsys.readouterr().out.count("SKIP") == 2


def test_catalog_info_reports_the_cache(work_dir, tmp_path, capsys):
    tree = tmp_path / "profiles"
    _named_profile(tree, "org.example.base:1.0", body=_SERVER_TYPE)
    assert main(["--catalog-info", "-p", str(tree)]) == EXIT_OK
    assert "not built" in capsys.readouterr().out
    main(["-q", "-p", str(tree), str(_service(tmp_path / "svc", "base:Server", _IMPORT_BASE))])
    capsys.readouterr()
    assert main(["--catalog-info", "-p", str(tree)]) == EXIT_OK
    out = capsys.readouterr().out
    assert "current" in out and "org.example.base.1.0" in out


def test_reset_starts_from_scratch(work_dir, tmp_path, capsys):
    """It deletes the cached catalogs and run directories, nothing else
    under WORK_DIR, and the next run builds the catalog anew"""
    tree = tmp_path / "profiles"
    _named_profile(tree, "org.example.base:1.0", body=_SERVER_TYPE)
    svc = _service(tmp_path / "svc", "base:Server", _IMPORT_BASE)
    assert main(["-q", "-p", str(tree), str(svc)]) == EXIT_OK
    keep = work_dir / "keep.txt"
    keep.write_text("not tosca-validate's")
    assert (work_dir / "catalogs").is_dir()

    assert main(["--reset"]) == EXIT_OK
    assert "reset:" in capsys.readouterr().err
    assert not (work_dir / "catalogs").exists() and not (work_dir / "runs").exists()
    assert keep.read_text() == "not tosca-validate's"

    assert main(["--reset", "-p", str(tree), str(svc)]) == EXIT_OK
    err = capsys.readouterr().err
    assert "catalog: built" in err and "cache hit" not in err


def test_reset_with_nothing_cached(work_dir, capsys):
    assert main(["--reset"]) == EXIT_OK
    assert "nothing to delete" in capsys.readouterr().err


def test_a_missing_tree_is_a_usage_error(work_dir, tmp_path):
    assert main(["-p", str(tmp_path / "nowhere"), str(tmp_path)]) == EXIT_ERROR


def test_a_run_leaves_the_configuration_as_it_found_it(work_dir, tmp_path):
    before = (constants.WORK_DIR, constants.LOCAL_REPO_ROOT)
    main(["-q", str(_service(tmp_path / "svc", "Server", _SERVER_TYPE))])
    assert (constants.WORK_DIR, constants.LOCAL_REPO_ROOT) == before
    assert list((work_dir / "runs").iterdir()) == []
