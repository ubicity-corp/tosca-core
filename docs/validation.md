# Validating TOSCA with tosca-core

tosca-core validates TOSCA 2.0 and Simple Profile 1.3 service templates and
profiles: the same parsing and the same semantic checks the Ubicity orchestrator
runs when it onboards a CSAR, with nothing persisted. This page covers
`tosca-validate`, the command that does it from a shell, and what its verdicts
can and cannot tell you. The library calls underneath are in the README
("Validate a template").

```console
$ tosca-validate -p ../tosca-profiles svc/my-service
FAIL svc/my-service  (24ms)
       main.yaml:28  service_template › node_templates › client › properties › performance
           $get_property: ['SELF', 'RELATIONSHIP', 'server', 'CAPABILITY', 'quality'] not found

1 of 1 target(s) failed -- 1 error(s)
```

## What it does, and what it does not

A template can only be validated against the profiles it imports, so validation
needs a **catalog**: a database holding the normative profiles and every profile
the template builds on. Building one means onboarding each profile, which is the
slow part — about 40 seconds for the 46 profiles of `tosca-profiles` and the
community tree. `tosca-validate` builds it once, caches it keyed by the contents
of the profile trees, and validates every later target against a copy, in well
under a second.

It does not re-implement anything. Every verdict comes from
`tosca_core.csar.validate_csar`, which runs onboarding's own pipeline
(`tosca_core.actions.ingest_csar`) with `validate_only=True` and rolls back.
`tosca-validate` adds the catalog, the cache and the report.

It also runs without the orchestrator, and that has one consequence worth
knowing up front: **nothing extends validation** — no check of what the
orchestrator can run — so those checks are not made (see "What it will not
catch"). Nor does it run any artifact, so a function a profile implements with
one is not evaluated: see "Functions profiles implement".

`ubicity catalog validate` asks the Ubicity orchestrator, with its extensions,
and is the answer for what that orchestrator will accept.

## Targets

```bash
tosca-validate svc/my-service              # a CSAR directory -- no zip needed
tosca-validate build/my-service.csar       # a CSAR archive
tosca-validate main.yaml                   # a single TOSCA file
tosca-validate svc/*/                      # many targets, one catalog
```

A directory is read the way onboarding reads an archive: the entry point is the
`Entry-Definitions` of a `TOSCA.meta` at its root or under `TOSCA-Metadata/`
(both at once is an error), and without either the archive must hold exactly
one top-level file, which is taken as the template. When a directory cannot be
read that way, `tosca-validate` says why before onboarding would — no metadata
and several files, or a sole file that is not YAML — rather than letting the
parser fail on a shell script. A directory holding several profiles is not a
target; validate each subdirectory, or give the directory with `-p`.

Targets are independent: each is validated against the run's copy of the
catalog, and the session is rolled back and reset after it
(`tosca_core.core.reset_session`), so a target cannot see another's
definitions and a failing one cannot affect the next.

## Reading the output

Each target gets one line: `ok`, `FAIL`, or `SKIP` (see "Restricting the
catalog"), with the time it took. Under a `FAIL` each finding is anchored to the
file and line where it was raised and the **keyname path** that leads to it —
`service_template › node_templates › client › properties › performance` — which
is usually more precise than the line. A target that could not be read at all
(not found, no metadata, an empty archive, both a profile and a service
template) shows the reason instead of findings.

A validation clause whose function cannot be evaluated here — a function a
profile implements with an artifact, in Python or otherwise — is neither passed
nor failed. The value is accepted, and
the clause is listed under its target as not checked, with a count at the end;
it does not make the target fail:

```
ok   svc/port  (20ms)
       not checked  property 'number' = 50: $in_range could not be evaluated
```

Treat such a value as unchecked: the orchestrator, which runs the artifact,
evaluates the clause when it onboards the template, and may refuse it.

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
usage error or a target refused by a restricted catalog — a refusal says
nothing about the target, so it is not reported as a failure.

## Profile trees

The catalog holds the normative TOSCA 2.0 and Simple Profile 1.3 profiles, which
tosca-core ships, and every profile under the trees you give:

```bash
tosca-validate -p ../tosca-profiles \
               -p ../tosca-community-contributions/profiles/community \
               svc/my-service
export TOSCA_CORE_PROFILES=~/a/profiles:~/b/profiles     # the same, separated like PATH
```

There are no default trees: with neither `-p` nor `TOSCA_CORE_PROFILES`, the
catalog holds the normative profiles only, which is enough for a template that
imports nothing else.

A profile is any directory with a `TOSCA.meta` (or `TOSCA-Metadata/`), found by
walking each tree; profiles do not nest, and `.git`, `.github`, `__pycache__`,
`node_modules` and `.pytest_cache` are skipped. Each is named after its path in
the tree (`com/ubicity/core` is `com.ubicity.core`) and archived and onboarded
as a CSAR, with file modes kept. Trees that import each other can be combined:
profiles are onboarded in the order their `imports:` imply, and onboarding is
retried until a pass makes no progress, so a wrong order costs a pass and a
profile that cannot onboard does not stop the rest. `--catalog-info` lists what
onboarded and, for each profile that did not, the validator's reason.

### The Ubicity profiles need the community tree, at the version they import

`com.ubicity.core:3.0` imports `community.tosca.core:0.2`, and every other
Ubicity profile builds on it, so `tosca-profiles` alone onboards almost nothing.
The community profiles come from
`https://github.com/oasis-open/tosca-community-contributions`, and **the tree must
be at the version tosca-profiles imports**. 0.2 is not released yet: it is that
repository's `master` (tosca-profiles' own scripts build it from a local clone's
working tree, until 0.2 is released and they onboard it by URL). A tree at `v0.1`,
or one months behind, fails the same way:

```
com.ubicity.core: {'profile.yaml': {'imports': {'community.tosca.core:0.2': 'profile not found'}, ...
```

and every Ubicity profile with it, after which every template importing one
fails on the import, before anything in it is checked.

**Give only `profiles/community`.** The repository's `profiles/` also holds
copies of other profiles, Ubicity's among them (`io/kubernetes/1.35`,
`com/ubicity/2.5`, ...); given as a tree, they enter the catalog beside
tosca-profiles' own, and the one that onboards first wins. A tree at `master`
with only the community profiles:

```bash
git clone --filter=blob:none --sparse \
    https://github.com/oasis-open/tosca-community-contributions.git community
git -C community sparse-checkout set profiles/community
tosca-validate -p ../tosca-profiles -p community/profiles/community ...
```

A `not found` on a type another tree provides means that tree first.

### Directories that are not profiles

`tosca-profiles/tests/` holds service templates with a `TOSCA.meta` that import
a file their own harness stages, so they show as six profiles that did not
onboard (`tests.aws.host_contract_aws`, ...). They are harmless; leave them out
with `--exclude-profile 'tests.*'`.

## Restricting the catalog

A catalog can be built from some of the profiles. Two repeatable flags select
them, matched as `fnmatch` globs against three spellings of each profile — the
`name:version` it declares, that name without the version, and its
directory-derived name — so whatever you have in front of you, normally an
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
       imports com.ubicity.infra:3.0, which this catalog was built without
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

Catalogs live in `WORK_DIR/catalogs` — `~/.cache/tosca-core/catalogs` unless
`TOSCA_CORE_DIR` or `XDG_CACHE_HOME` says otherwise — keyed by a hash of:

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
with the validator's reason — the first thing to read when a verdict surprises
you.

## Files outside a CSAR

A `file:` repository may name only a directory inside the CSAR that declares
it, or inside a local repository root: a directory the operator lists in
`TOSCA_CORE_LOCAL_REPOSITORY_ROOTS` (absolute paths, separated like `PATH`;
none by default). A profile or template declaring one anywhere else is refused
when it is onboarded or validated, naming the directory. Every file read
through a repository must then resolve, after `..` and symbolic links, inside
that repository's directory, and a `file:` URL may name no host but
`localhost`. The same rules hold in the orchestrator, which sets its own roots.

## Functions profiles implement

A profile may implement a function with an artifact rather than in TOSCA; the
community core implements `$in_range` in Python. tosca-validate runs none of
them, Python included, so validating a template never runs code a profile
ships: a validation clause built on one is reported as not checked, and the
orchestrator, which runs the artifact, evaluates it when it onboards the
template. The functions TOSCA defines are tosca-core's own code and are always
evaluated. (tosca-core 0.3 ran functions implemented in Python itself, unless
`--no-run-functions` was given; 0.4.0 removed both.)

## `--skip-file-checks`

Turns off the checks that the files an artifact declares exist. Use it to
validate a template away from its artifacts — a checkout without the
`playbooks/` directory, a fragment under review — where only the type graph is
in question.

## What it will not catch

A validator sees what is declared. It is never given the input values and runs
nothing, so whatever goes wrong only once a service is instantiated is invisible
to it.

- **Inputs.** A bad value in a deployment's inputs — a string that is not JSON,
  a node count that makes a requirement unsatisfiable, an arithmetic overflow in
  a function of an input, an input the template does not declare — is reported
  when the service is added, not when the template is validated.
- **Running the artifacts.** A script that exits non-zero, a playbook task that
  fails, output that is not a map, a required output an operation did not
  produce, a function whose implementation rejects its arguments: the model is
  valid, and the failure is what the implementation does.
- **Live instances.** A `select` or `substitute` directive, or a requirement
  that resolves against another service, needs that service deployed. A
  dangling requirement's target is chosen at fulfillment, so a dependency loop
  it would close is found only then; a loop of explicit requirements is
  refused here.
- **What the archive is used as.** A valid service template given to
  `ubicity profile add`, or a profile given to `catalog add`, is refused by the
  command, not by the validator, which only sees the archive.
- **What the orchestrator can run.** Whether an artifact type can be executed,
  and which input and output names its artifacts can receive (a Bash script
  cannot be given an input named `api.version`), are questions for whatever
  runs it: the Ubicity orchestrator answers them at onboarding, through its
  extensions to tosca-core's validation, and tosca-validate has none. Nor
  does it run a function a profile implements with an artifact, Python
  included: a validation clause built on one is reported as not checked (see
  "Reading the output"), never passed. See the README's "Embedding tosca-core".
- **The order operations run in.** An attribute exists once an operation has
  written it, so whether one an operation reads is certain to be there depends
  on which operations run first, which TOSCA leaves to the orchestrator. The
  Ubicity orchestrator answers from its deploy workflow at onboarding;
  tosca-validate does not know it, so such an attribute is not shown present
  (a warning in the log with `-v`, never a refusal: an attribute's value is not
  refused for presence).
- **Simple Profile 1.0, 1.1 and 1.2 are validated as 1.3.** All four versions
  are accepted, but `SUPPORTED_DEFINITIONS_VERSIONS` maps each onto the 1.3
  namespace and the parser has two grammars, `tosca_2_0` and 1.3. So 1.3-only
  syntax in a 1.0 file passes, and anything 1.3 changed is flagged; conformance
  to 1.0 as such is not on offer.
- **Packaging.** What makes an artifact runnable rather than declared — a Bash
  script's executable bit, a remote script sourcing a sibling it cannot reach —
  fails at deploy time.

## Measured against tosca-tests

The `tosca-tests` corpus encodes the expected verdict in its directory names:
`success_cases` must pass, `failure_cases` must fail. Every case is a
deployment, though — its runner onboards the archive, adds a service with the
case's inputs and requires it to reach ACTIVE — so a validator is expected to
disagree with it wherever the failure needs the deployment.

Measured on 2026-11-17 with tosca-core 1.0.0, `tosca-tests` at `d2d9e18`,
`tosca-profiles` at `2f163057` and the community profiles at `master` `14ead36`
(0.2; 52 directories found, 46 onboarded, the six above not), **538 of 579 cases
agree**: v2 success 251/254, v2 failure 103/137, v1 success 124/125, v1 failure
60/63. 22 clauses in 13 cases are not checked, all `$in_range`, which the
community profile implements in Python. The 41 disagreements are the gaps above:

| n | what the case needs | cases |
|---|---|---|
| 16 | its **inputs**, read only by `service add` | `any_to_any_overflow`, `capability_directives_internal`, `capability_mapping_onto_zero_count`, `invalid_json`, `node_count_zero_required`, `node_path_index_negative`, `node_path_index_out_of_range`, `pairs_overflow`, `requirement_directives_external`, `requirement_mapping_mandatory_targets_exceed`, `requirement_mapping_target_count_undecidable`, `scalar_allocation_overflow`, `substitutes_input_refused`; v1 `mysql`, `namespace`, `properties` |
| 11 | the **artifacts run** | `implementation_dependency_fails`, `operation_required_input_without_value`, `operation_required_output_not_produced`, `processor_ansible_failed_task`, `processor_bash_nonzero_exit`, `processor_bash_not_executable`, `processor_bash_stdout_not_a_map`, `processor_python_exception`, `processor_python_stdout_not_a_map`, `processor_tar_member_outside_directory`, `socket_to_ssh_url_port_zero` |
| 5 | the orchestrator's **extensions**: what its processors can run | `bash_input_name_not_a_shell_name`, `processor_missing_dependency`, `processor_missing_derived_artifact_type`, `processor_missing_function`, `processor_missing_named_artifact` |
| 2 | **two services deployed** | `capability_directives_external`, `requirement_directives_internal` |
| 1 | **fulfillment** of a dangling requirement, in a deployed service | `dangling_requirement_only_closes_loop` |
| 2 | the **command** the archive is given to | `not_a_profile`, `not_a_service_template` |
| 2 | **profiles onboarded in order** before the template, not one archive | `relationship_type_from_profile`; v1 `success_cases/import` |
| 2 | the harness's **setup outside the archive**: `run.sh` creates the repository the template names under `/tmp` and configures it as a local repository root | `artifact_repository`, `import_repository` |

With the orchestrator's extensions installed — tosca-core configured by
`ubicity.constants` — the same run agrees on **543 of 579**, five more: the
cases that need the extensions, and nothing else; and no clause is left not checked, since the orchestrator's
evaluator runs the `$in_range` functions.

To reproduce, validate each suite's directories with both trees and compare
`ok` with the suite's name:

```bash
# from a directory holding tosca-profiles, community and tosca-tests
tosca-validate -q -f json -p tosca-profiles -p community/profiles/community \
    tosca-tests/v2/failure_cases/*/ > failures.json     # each result should have "ok": false
```

A failure suite that scores *higher* when profiles fail to onboard is not good
news: a failure case whose imports never loaded fails for the wrong reason.
Check `--catalog-info` before trusting a rise.

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

| module (`tosca_core/lint/`) | |
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
refusal — never a wrong verdict, which only the validator gives.

The library call returns what `-f json` flattens: `validate_csar` gives `{}` for
a valid target, a string for one it could not read, and otherwise a dictionary
shaped like the documents — keyed by file name, then by keyname, with a `line`
key wherever the validator knew one ([api.md](api.md)).
