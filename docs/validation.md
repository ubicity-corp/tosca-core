# Validating TOSCA with tosca-core

tosca-core validates TOSCA 2.0 and Simple Profile 1.3 service templates and
profiles: the parsing and semantic checks of onboarding a CSAR into a catalog,
with nothing persisted. This page covers `tosca-validate`, the command that
does it from a shell, and what its verdicts tell you. The library calls
underneath are in [api.md](api.md).

```console
$ tosca-validate -p profiles svc/my-service
FAIL svc/my-service  (24ms)
       main.yaml:28  service_template › node_templates › client › properties › performance
           $get_property: ['SELF', 'RELATIONSHIP', 'server', 'CAPABILITY', 'quality'] not found

1 of 1 target(s) failed -- 1 error(s)
```

## What it checks

A template can only be validated against the profiles it imports, so validation
needs a **catalog**: a database holding the normative profiles and every profile
the template builds on. Building one means onboarding each profile, which is the
slow part: tens of seconds for a few dozen profiles. `tosca-validate` builds it
once, caches it keyed by the contents of the profile trees, and validates every
later target against a copy, in well under a second.

Every verdict comes from `validate_csar`, which runs onboarding's own pipeline
in validate-only mode and rolls back. `tosca-validate` adds the catalog, the
cache and the report.

It checks a template against TOSCA's rules and the profiles it builds on, and
evaluates the functions TOSCA defines. What an application that runs the
template adds to validation, such as which artifact types it can execute, is
checked by that application, which embeds tosca-core and extends its validation
(see "What validation leaves to the application").

## Targets

```bash
tosca-validate svc/my-service              # a CSAR directory, no zip needed
tosca-validate build/my-service.csar       # a CSAR archive
tosca-validate main.yaml                   # a single TOSCA file
tosca-validate svc/*/                      # many targets, one catalog
```

A directory is read the way onboarding reads an archive: the entry point is the
`Entry-Definitions` of a `TOSCA.meta` at its root or under `TOSCA-Metadata/`
(both at once is an error), and without either the archive must hold exactly
one top-level file, which is taken as the template. When a directory cannot be
read that way, `tosca-validate` says why before onboarding would (no metadata
and several files, or a sole file that is not YAML) rather than letting the
parser fail on a shell script. A directory holding several profiles is not a
target; validate each subdirectory, or give the directory with `-p`.

Targets are independent: each is validated against the run's copy of the
catalog, and the session is rolled back and reset after it
(`reset_session`), so a target cannot see another's definitions and a failing
one cannot affect the next.

## Reading the output

Each target gets one line: `ok`, `FAIL`, or `SKIP` (see "Restricting the
catalog"), with the time it took. Under a `FAIL` each finding is anchored to the
file and line where it was raised and the **keyname path** that leads to it,
`service_template › node_templates › client › properties › performance`, which
is usually more precise than the line. A target that could not be read at all
(not found, no metadata, an empty archive, both a profile and a service
template) shows the reason instead of findings.

A validation clause built on a function a profile implements (see "Functions
profiles implement") is listed under its target as not checked, with a count at
the end:

```
ok   svc/port  (20ms)
       not checked  property 'number' = 50: $in_range could not be evaluated
```

When findings include `profile not found`, the report names the missing
profiles once at the end, since the dozens of downstream `not found` errors all
have that one cause:

```
hint: not in the catalog: community.tosca.core:0.1
      add the tree that defines them with --profiles <dir>, then re-run.
```

`-f json` writes one object, for CI: `{"format": 1, "results": [...]}`, with one
entry in `results` per target. `format` is raised only when a field changes
meaning or goes away ([api.md](api.md)). Each entry:

| field | |
|---|---|
| `target` | the path as given |
| `ok` | true when there are no findings, no fatal reason and no refusal |
| `fatal` | why the target could not be read, or null |
| `refused` | why the catalog cannot answer for it, or null |
| `seconds` | time spent on it |
| `findings` | `[{file, path, line, message}]`: `path` is the keyname path as a list, `line` the nearest line the validator recorded, or null |
| `not_checked` | `[{subject, value, functions}]`: the validation clauses that could not be evaluated, what each validates (`property 'number'`, `data type 'Port'`), the value, and the functions left unevaluated; empty when every clause was checked. They do not affect `ok` |

Progress goes to stderr, so stdout stays parseable. `-q` suppresses it; `-v`
adds tosca-core's own log, which repeats every finding as it is raised.

Exit status: `0` every target valid, `1` any finding or unreadable target, `2` a
usage error, a catalog that cannot be built, or a target refused by a restricted
catalog. A refusal says nothing about the target, so it is not reported as a
failure, and it takes precedence: a run with one exits `2`.

## Profile trees

The catalog holds the normative TOSCA 2.0 and Simple Profile 1.3 profiles, which
tosca-core ships, and every profile under the trees you give:

```bash
tosca-validate -p profiles \
               -p tosca-community-contributions/profiles/community \
               svc/my-service
export TOSCA_CORE_PROFILES=~/a/profiles:~/b/profiles     # the same, separated like PATH
```

With neither `-p` nor `TOSCA_CORE_PROFILES`, the catalog holds the normative
profiles only, which is enough for a template that imports nothing else.

A profile is any directory with a `TOSCA.meta` (or `TOSCA-Metadata/`), found by
walking each tree; profiles do not nest, and `.git`, `.github`, `__pycache__`,
`node_modules` and `.pytest_cache` are skipped. Each is named after its path in
the tree (`org/example/core` is `org.example.core`) and archived and onboarded
as a CSAR, with file modes kept. Trees that import each other can be combined:
profiles are onboarded in the order their `imports:` imply, and onboarding is
retried until a pass makes no progress, so a wrong order costs a pass and a
profile that cannot onboard does not stop the rest. `--catalog-info` lists what
onboarded and, for each profile that did not, the validator's reason.

### A tree at the version its importers name

A profile that imports one from another tree needs that tree at the version it
imports. Profiles building on the TOSCA community's, for example, need
`https://github.com/oasis-open/tosca-community-contributions` at the version of
`community.tosca.core` they import. A tree at another version fails on the
import:

```
org.example.core: {'profile.yaml': {'imports': {'community.tosca.core:0.2': 'profile not found'}, ...
```

and every profile built on it fails with it, after which every template
importing one fails on the import, before anything in it is checked.

**Give only the profiles you mean.** A repository's tree can hold copies of
profiles you also give from elsewhere; given as a tree, they enter the catalog
beside the others, and the one that onboards first wins. The community
repository's `profiles/` holds such copies, so give its `profiles/community`
alone:

```bash
git clone --filter=blob:none --sparse \
    https://github.com/oasis-open/tosca-community-contributions.git community
git -C community sparse-checkout set profiles/community
tosca-validate -p profiles -p community/profiles/community ...
```

A `not found` on a type another tree provides means that tree first.

### Directories that are not profiles

A tree's test directories may hold service templates with a `TOSCA.meta`; they
are found like profiles and listed as profiles that did not onboard. Leave them
out with `--exclude-profile 'tests.*'`.

## Restricting the catalog

A catalog can be built from some of the profiles. Two repeatable flags select
them, matched as `fnmatch` globs against three spellings of each profile: the
`name:version` it declares, that name without the version, and its
directory-derived name. So whatever you have in front of you, normally an
`imports:` line, works:

```bash
tosca-validate -p tree --only-profile 'org.nginx' svc/        # nginx and what it needs
tosca-validate -p tree --exclude-profile '*:3.0' svc/         # everything but the 3.0 line
tosca-validate -p tree --only-profile 'org.*' --exclude-profile 'org.wordpress' svc/
```

`--only-profile` keeps what it matches **and everything that imports**,
transitively: a profile without its imports does not onboard. `--exclude-profile`
is taken literally and wins over `--only-profile`; excluding something other
profiles import is allowed, and they then fail to onboard like any other.

A restricted catalog **refuses what it cannot answer for**. A target that
imports, or is, a profile the catalog was built without is not validated:

```
SKIP svc/workflow
       imports org.example.infra:3.0, which this catalog was built without
       (--exclude-profile '*:3.0'). Validating against a catalog that lacks it
       would judge the wrong types, so it is not validated.

1 of 1 target(s) import a profile left out of the catalog, and were not validated
```

It is counted apart from failures, carries `refused` in JSON, and exits 2. Two
properties make it safe to rely on: it refuses only on profiles the catalog is
**recorded** as having left out, so a target it cannot read, an id it has never
seen, or a `.csar` (which it does not open) is validated normally and never
refused by mistake; and the restriction is stored with the catalog, so a cache
hit refuses exactly as the build did. A restricted and an unrestricted catalog
from the same trees are separate cache entries.

## The catalog cache

Catalogs live in `WORK_DIR/catalogs` (`~/.cache/tosca-core/catalogs` unless
`TOSCA_CORE_DIR` or `XDG_CACHE_HOME` says otherwise), keyed by a hash of:

- every file in every tree, by contents and executable bit, not modification
  time, so a fresh clone of the same trees hits the same entry;
- the restriction, if any;
- the local repository roots, if any (below);
- tosca-core's version and a hash of its source, since the catalog's schema is
  tosca-core's ORM and its contents are what tosca-core's parser made of the
  profiles. Editing tosca-core rebuilds the catalog; there is nothing to
  invalidate by hand.

A catalog is a SQLite database **and** the directory its CSARs were unpacked
into (`catalog-<key>.repo`): the database records each CSAR by its unpacked
path, and an application that installs a function evaluator runs a profile's
function files from there. Each run copies both into its own
directory under `WORK_DIR/runs`, rewrites the recorded paths, validates there
and deletes it, so runs never change the cache or each other, and an
interrupted build never leaves a partial catalog under a good key.

```bash
tosca-validate -p tree --catalog-info      # the catalog these trees select, and its state
tosca-validate -p tree --rebuild svc/      # rebuild it anyway
tosca-validate --reset                     # delete every cached catalog: start from scratch
```

`--reset` deletes `WORK_DIR/catalogs` and `WORK_DIR/runs` and nothing else;
with targets, it then validates them against a catalog built anew.

`--catalog-info` prints the trees, the cache key, the catalog's file and size,
how long it took to build, every profile onboarded, and every one that was not
with the validator's reason: the first thing to read when a verdict surprises
you.

## Files outside a CSAR

A `file:` repository may name only a directory inside the CSAR that declares
it, or inside a local repository root: a directory the operator lists in
`TOSCA_CORE_LOCAL_REPOSITORY_ROOTS` (absolute paths, separated like `PATH`;
none by default). A profile or template declaring one anywhere else is refused
when it is onboarded or validated, naming the directory. Every file read
through a repository must then resolve, after `..` and symbolic links, inside
that repository's directory, and a `file:` URL may name no host but
`localhost`. An application embedding tosca-core sets its own roots.

## Functions profiles implement

tosca-core evaluates the functions TOSCA defines, which are its own code. A
profile may also implement a function with an artifact; the TOSCA community's
core profile implements `$in_range` in Python. Evaluating one means running
the artifact, which is the work of an application that runs artifacts, so
validating a template runs only tosca-core's code. A validation clause built on
such a function has its value accepted and is reported as not checked, never as
passed; it does not make the target fail. Treat the value as unchecked until the
application that runs the artifact has evaluated the clause.

## Implementing files

A profile can declare functions without implementations, leaving each
processor to supply its own. An **implementing file** supplies them: a TOSCA
2.0 file whose top-level `implements` names an onboarded profile, by the name
and version an import of it would use, and which adds implementations to that
profile's functions. This is an extension of TOSCA 2.0, following a proposal to
the TOSCA community.

```yaml
tosca_definitions_version: tosca_2_0
profile: example.functions.python:1.0
implements: example.functions:1.0
imports:
  - profile: example.artifacts:1.0
functions:
  to_string:
    implementation:
      primary:
        type: Script
        file: functions/to_string.py
    signatures:
      - {}
      - implementation:
          primary:
            type: Script
            file: functions/to_string_float.py
```

- Each `functions` entry names a function of the implemented profile and holds
  only `implementation`. One at the function level applies to every signature;
  one in `signatures` applies to the signature at the same position in the
  function's list, and an empty entry leaves that signature to the function-level
  implementation. Arguments, results, descriptions and metadata belong to the
  implemented profile.
- The file declares nothing of its own: no types, functions or service template.
  It may import the profiles that declare its artifact types, and the implemented
  profile's names are in its default namespace.
- A signature that already has an implementation, declared with it or supplied
  by another implementing file, is a conflict.
- Onboarding the file is what puts its implementations into effect, for every
  template that imports the implemented profile. It is never imported: an import
  that names one is an error. The implemented profile is onboarded first, and
  cannot be deleted while the file is onboarded; deleting the file removes its
  implementations.
- An implementation's artifact belongs to the implementing file: its `file` is
  found in the implementing file's archive, and its type in that file's scope.
- A profile shows its declarations as published. A signature implemented by an
  implementing file has no `implementation` but an `implemented_by` naming that
  file's profile; the implementing profile shows `implements` and its
  implementations in the form its file gives them.

`tosca-validate` onboards an implementing file after the profile it implements.
Since tosca-core runs no implementation, an implementing file changes no
verdict: a clause built on a function it implements is still reported as not
checked.

## `--skip-file-checks`

Turns off the checks that the files an artifact declares exist. Use it to
validate a template away from its artifacts (a checkout without the
`playbooks/` directory, a fragment under review) where only the type graph is
in question.

## What validation leaves to the application

A validator checks what a template declares. The input values a service is
created with, and what happens when its artifacts run, belong to the
application that deploys it, which checks them then:

- **Inputs.** A bad value in a deployment's inputs (a string that is not JSON,
  a node count that makes a requirement unsatisfiable, an arithmetic overflow in
  a function of an input, an input the template does not declare) is reported
  when the service is created.
- **Running the artifacts.** A script that exits non-zero, a playbook task that
  fails, output that is not a map, a required output an operation did not
  produce, a function whose implementation rejects its arguments: the model is
  valid, and the failure is what the implementation does.
- **Live instances.** A `select` or `substitute` directive, or a requirement
  that resolves against another service, needs that service deployed. A
  dangling requirement's target is chosen at fulfillment, so a dependency loop
  it would close is found only then; a loop of explicit requirements is
  refused here.
- **What the archive is used as.** An application that adds profiles and
  service templates through separate commands refuses an archive of the other
  kind; the validator sees only the archive.
- **What the application can run.** Whether an artifact type can be executed,
  and which input and output names its artifacts can receive (a Bash script
  cannot be given an input named `api.version`), are questions for whatever
  runs it. An application answers them through its extensions to tosca-core's
  validation (api.md, "Embedding"); `tosca-validate` installs none.
- **The order operations run in.** An attribute exists once an operation has
  written it, so whether one an operation reads is certain to be there depends
  on which operations run first, which TOSCA leaves to the application. An
  application that installs an attribute-written check answers from its own
  order; without one, such an attribute is not shown present (a warning in the
  log with `-v`, never a refusal: an attribute's value is not refused for
  presence).
- **Simple Profile 1.0, 1.1 and 1.2 are validated as 1.3.** All four versions
  are accepted, but `SUPPORTED_DEFINITIONS_VERSIONS` maps each onto the 1.3
  namespace and the parser has two grammars, `tosca_2_0` and 1.3. So 1.3-only
  syntax in a 1.0 file passes, and anything 1.3 changed is flagged; conformance
  to 1.0 as such is not on offer.
- **Packaging.** What makes an artifact runnable rather than declared (a Bash
  script's executable bit, a remote script sourcing a sibling it cannot reach)
  shows only at deploy time.

A test suite whose cases are deployments therefore disagrees with a validator
wherever a failure needs the deployment. A failure suite that scores *higher*
when profiles fail to onboard is not good news: a failure case whose imports
never loaded fails for the wrong reason. Check `--catalog-info` before trusting
a rise.

## How it works

```
   -p trees ──► discover profiles ──► select (--only/--exclude) ──► key
                                                                     │
                       WORK_DIR/catalogs/catalog-<key>.sqlite + .repo
                            │ hit                      │ miss
                    copy into the run         create tables, normative
                            │                 profiles, onboard in order,
                            │                 retry to a fixpoint, publish
                            └──────────┬───────────────┘
                     WORK_DIR/runs/run-*  (WORK_DIR and LOCAL_REPO_ROOT
                                           pointed here for the run)
                                       │
                  for each target: validate_csar(validate_only) → reset_session()
                                       │
                                 report, delete the run
```

| module (`tosca_core/cli/`) | |
|---|---|
| `__main__.py` | the command: options, the run directory, configuration restored afterwards |
| `profiles.py` | discovery, the `imports:` graph, ordering, selection, refusal |
| `cache.py` | the cache key, building, publishing and restoring catalogs |
| `validate.py` | one target through `validate_csar`, and the error tree flattened into findings |
| `report.py` | text and JSON output |
| `layout.py` | where a CSAR keeps its metadata, read before any ingest |

`profiles.py` reads two keywords, the `profile:` a file declares and the
`profile:` of each `imports:` entry, and only for hints: getting them wrong
costs an onboarding pass, a spare profile in a restricted catalog, or a missed
refusal, never a wrong verdict, which only the validator gives.

The JSON findings are `validate_csar`'s error tree flattened; [api.md](api.md)
describes the tree.
