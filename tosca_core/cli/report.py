"""
Rendering validation results: text for a terminal, one block per target
with each finding at file:line and its keyname path, or JSON for CI.
"""
from __future__ import annotations

import os
import sys
import json
from pathlib import Path
from typing import Iterable, TextIO

from tosca_core.cli.validate import Result

_ARROW = " › "


def _supports_colour(stream: TextIO) -> bool:
    return stream.isatty() and "NO_COLOR" not in os.environ


class _Style:
    def __init__(self, on: bool) -> None:
        self.on = on

    def _wrap(self, code: str, text: str) -> str:
        return f"\033[{code}m{text}\033[0m" if self.on else text

    def bold(self, t: str) -> str: return self._wrap("1", t)
    def red(self, t: str) -> str: return self._wrap("31", t)
    def green(self, t: str) -> str: return self._wrap("32", t)
    def dim(self, t: str) -> str: return self._wrap("2", t)
    def yellow(self, t: str) -> str: return self._wrap("33", t)


def render_text(results: Iterable[Result], stream: TextIO, root: Path | None = None,
                dropped: dict[str, str] | None = None) -> None:
    s = _Style(_supports_colour(stream))
    results = list(results)

    for result in results:
        try:
            shown = result.target.relative_to(root) if root else result.target
        except ValueError:
            shown = result.target

        if result.ok:
            print(f"{s.green('ok')}   {shown}  {s.dim(f'({result.seconds*1000:.0f}ms)')}",
                  file=stream)
            _render_not_checked(result, stream, s)
            continue

        if result.refused:
            print(f"{s.yellow('SKIP')} {s.bold(str(shown))}", file=stream)
            print(f"       {s.yellow(result.refused)}", file=stream)
            continue

        print(f"{s.red('FAIL')} {s.bold(str(shown))}  "
              f"{s.dim(f'({result.seconds*1000:.0f}ms)')}", file=stream)

        if result.fatal:
            print(f"       {s.red(result.fatal)}", file=stream)
            continue

        for finding in result.findings:
            where = finding.file or str(shown)
            if finding.line is not None:
                where = f"{where}:{finding.line}"
            location = s.dim(_ARROW.join(finding.path)) if finding.path else ""
            print(f"       {s.bold(where)}  {location}", file=stream)
            print(f"           {finding.message}", file=stream)
        _render_not_checked(result, stream, s)

    refused = [r for r in results if r.refused]
    failed = [r for r in results if not r.ok and not r.refused]
    total_findings = sum(len(r.findings) for r in failed)
    print(file=stream)
    if not failed and not refused:
        print(s.green(f"{len(results)} target(s) validated, no errors"), file=stream)
    if failed:
        print(s.red(f"{len(failed)} of {len(results)} target(s) failed"
                    f" -- {total_findings} error(s)"), file=stream)
    if refused:
        print(s.yellow(f"{len(refused)} of {len(results)} target(s) import a "
                       "profile left out of the catalog, and were not "
                       "validated"), file=stream)
    unchecked = [r for r in results if r.not_checked]
    if unchecked:
        total = sum(len(r.not_checked) for r in unchecked)
        print(s.yellow(f"{total} validation clause(s) in {len(unchecked)} target(s) "
                       "not checked, and their values accepted: a function in "
                       "them could not be evaluated here, such as one a profile "
                       "implements with an artifact, which tosca-validate does "
                       "not run"), file=stream)

    # A missing profile shows up as a pile of downstream errors whose one
    # cause is a tree that was not given. Say so once.
    missing = sorted({
        f.path[-1] for r in failed for f in r.findings
        if f.message == "profile not found" and f.path
    })
    if missing:
        if dropped:
            # The tree may be present with the profile left out on
            # purpose, or unable to onboard because of what was
            advice = (f"\n      this catalog is restricted ({len(dropped)} "
                      "profile(s) left out), so these may be absent by design "
                      "or by cascade rather than missing from the tree."
                      "\n      --catalog-info lists what was left out and why.")
        else:
            advice = ("\n      add the tree that defines them with "
                      "--profiles <dir>, then re-run.")
        print(s.dim("hint: not in the catalog: " + ", ".join(missing) + advice),
              file=stream)


def _render_not_checked(result: Result, stream: TextIO, s: _Style) -> None:
    """The validation clauses a target's values were accepted without"""
    for n in result.not_checked:
        print(f"       {s.yellow('not checked')}  {n.subject} = {n.value}: "
              f"{', '.join(n.functions)} could not be evaluated", file=stream)


# The version of the JSON output: raised when a field changes meaning or
# goes away, not when one is added
JSON_FORMAT = 1


def render_json(results: Iterable[Result], stream: TextIO) -> None:
    payload = {"format": JSON_FORMAT, "results": [{
        "target": str(result.target),
        "ok": result.ok,
        "fatal": result.fatal,
        "refused": result.refused,
        "seconds": round(result.seconds, 4),
        "findings": [
            {"file": f.file, "path": list(f.path), "line": f.line, "message": f.message}
            for f in result.findings
        ],
        "not_checked": [
            {"subject": n.subject, "value": n.value, "functions": list(n.functions)}
            for n in result.not_checked
        ],
    } for result in results]}
    json.dump(payload, stream, indent=2)
    stream.write("\n")


def render(results: Iterable[Result], fmt: str, root: Path | None = None,
           stream: TextIO | None = None,
           dropped: dict[str, str] | None = None) -> None:
    stream = stream or sys.stdout
    if fmt == "json":
        render_json(results, stream)
    else:
        render_text(results, stream, root, dropped)
