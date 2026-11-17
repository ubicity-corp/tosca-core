# tosca-core

A parser and semantic validator for TOSCA 2.0 and the TOSCA Simple Profile
in YAML 1.3.

tosca-core reads service templates and profiles, packaged as CSARs, as CSAR
directories or as single YAML files. It builds a model of the types,
declarations and templates they define, resolves imports and `derived_from`
against a catalog of profiles, and checks the result against TOSCA's rules.
It does not deploy anything and runs no artifact: running what a template
describes, a function a profile implements with an artifact among it, is left
to an application that embeds it. It evaluates the functions TOSCA defines,
which are its own code.

The public API -- what stays stable from one release to the next -- is in
[docs/api.md](https://github.com/ubicity-corp/tosca-core/blob/master/docs/api.md).

## Install

```bash
pip install tosca-core
pip install "tosca-core[flask]"   # when serving the model through a Flask REST API
```

The `flask` extra only matters to an application that serves the model over
HTTP: dump-only URL fields link entities to its resources, and without Flask
they are omitted.

Python 3.10 or later. tosca-core keeps its catalog in a database through
SQLAlchemy. By default that is an in-memory SQLite database, so there is no
server to run.

From a checkout, with the test dependencies:

```bash
pip install -e ".[test]"
```

## Validate a template

Validation needs a catalog holding the normative profiles, which every
TOSCA definition ultimately derives from. Build one, then validate:

```python
from tosca_core import (bootstrap, create_tables, load_normative_profiles,
                        session_scope, validate_csar)

bootstrap()                      # bind the database, load the models
with session_scope():
    create_tables()
with session_scope():
    load_normative_profiles()    # TOSCA 2.0 and Simple Profile 1.3

errors = validate_csar("service.yaml")
print(errors or "valid")
```

`validate_csar` persists nothing, and returns `{}`, a string when the target
cannot be read at all, or the errors as a dict shaped like the documents (see
[docs/api.md](https://github.com/ubicity-corp/tosca-core/blob/master/docs/api.md)). A template that imports other profiles needs them
onboarded first with `onboard_csar`, followed by a commit.

To validate many templates in one process, call `reset_session()` between
them. A validation that fails can
leave the session in a state that would otherwise affect the next one.

## Validate from the command line

`tosca-validate` does the same from a shell, building the catalog once and
caching it:

```console
$ tosca-validate -p ../tosca-profiles -p ../community/profiles/community svc/my-service
FAIL svc/my-service  (24ms)
       main.yaml:28  service_template › node_templates › client › properties › performance
           $get_property: ['SELF', 'RELATIONSHIP', 'server', 'CAPABILITY', 'quality'] not found

1 of 1 target(s) failed -- 1 error(s)
```

Each target is a CSAR, a CSAR directory or a single TOSCA file. The catalog
holds the normative profiles and every profile under the trees given with
`-p` (or `TOSCA_CORE_PROFILES`, separated like `PATH`), and is cached under
`WORK_DIR/catalogs` until the trees or tosca-core change: the first run over
the Ubicity profiles takes about 40 seconds, later runs well under one.

| Option | |
|---|---|
| `-p DIR`, `--profiles DIR` | a profile tree; repeatable |
| `--only-profile GLOB`, `--exclude-profile GLOB` | build the catalog from some of the profiles; a target importing one left out is refused, not validated |
| `--rebuild` | rebuild the cached catalog |
| `--reset` | start from scratch: delete every cached catalog, then validate any targets |
| `--catalog-info` | show the catalog the trees select, and what did not onboard and why |
| `--skip-file-checks` | do not require the files that artifacts name to exist |
| `-f json` | results as JSON, for CI |
| `-q`, `-v` | no progress; or tosca-core's log as well |

It exits 0 when every target is valid, 1 when any is not, and 2 for a usage
error or a target a restricted catalog refused.

**Validating never runs a profile's code.** A function a profile implements
with an artifact, in Python or otherwise -- the community profile's `$in_range`,
for instance -- is not evaluated, so a validation clause built on one is listed
as **not checked** under its target, and its value accepted; it does not make
the target fail. The orchestrator, which runs the artifact, checks it when it
onboards the template.

**[docs/validation.md](https://github.com/ubicity-corp/tosca-core/blob/master/docs/validation.md)** covers the rest: reading the
output and its JSON, which profile trees the Ubicity profiles need (the
community profiles at 0.2, for now the community repository's `master`), restricting the catalog, the
cache, what validation cannot catch — inputs, running artifacts, and the checks
that need the orchestrator's extensions — and how it measures against
the `tosca-tests` corpus, every disagreement accounted for.

## Configuration

| Setting | Default | Override |
|---|---|---|
| `DB_URI` | `sqlite://` (in memory) | `TOSCA_CORE_DB_URI`, or `bootstrap(db_uri)` |
| `WORK_DIR`, the directory tosca-core may read and write | `~/.cache/tosca-core` | `TOSCA_CORE_DIR` |
| `LOCAL_REPO_ROOT`, where onboarded CSARs are unpacked | `WORK_DIR/repository` | |
| `LOCAL_REPOSITORY_ROOTS`, the directories outside a CSAR a `file:` repository may name | none | `TOSCA_CORE_LOCAL_REPOSITORY_ROOTS` (absolute paths, separated like `PATH`) |
| `STATE_NAMES`, the states a workflow's `set_state` may name | none: any | |

A file-backed SQLite database (`sqlite:////abs/path/catalog.db`) keeps the
catalog between runs, so the normative profiles are loaded once. Keep its
`WORK_DIR` with it: the database records where each onboarded CSAR was unpacked,
by absolute path under `LOCAL_REPO_ROOT`, and where an application installs a
function evaluator (see "Embedding tosca-core"), a function a profile implements
with an artifact runs the file it finds there. A database without that
directory, or copied somewhere its recorded paths do not reach, validates such
functions as failing.

## Embedding tosca-core

An application that deploys what tosca-core validates extends it at startup:

- **Configuration:** `tosca_core.constants.constants.configure(...)` sets its
  own database, working directory, local repository roots, model modules,
  extension modules, and the state names its workflows use.
  tosca-core reads its settings when it needs them, never at import.
- **Instances:** tosca-core creates none. An application that runs services
  builds its own runtime objects from the templates, reading them through the
  models (the Ubicity orchestrator's are in its `ubicity/models/instantiate.py`).
  Where tosca-core evaluates a path against those instances, it asks the
  service for a named head: `service.resolve_node(name, index, select)`, with
  the index evaluated (`None`, `'ALL'` or a non-negative integer), returns the
  instance or a list of them, raising `KeyError` for "no value yet" and
  `InvalidPathError` for an index that cannot exist; `select` lets a
  selectable template answer with the node it was bound to. A service without
  `resolve_node` is taken to be a service of templates.
- **Extensions to validation:** tosca-core runs no artifacts, and knows
  nothing of what runs them. From a module
  listed in `EXTENSION_MODULES`
  (`bootstrap()` imports them), an application that runs artifacts adds to
  validation through `tosca_core.extensions`:
  - `register_implementation_check(check)`: `check(artifact, type_name,
    operation, declaration)` is called for every implementation artifact as
    validation reaches it, and returns `{key: message}` errors, reported where
    the artifact is -- to refuse an artifact type it cannot run, or an input
    name its artifacts cannot receive. `operation_input_names()` and
    `operation_output_names()` in `tosca_core.validate.operation_implementation`
    give an operation's names.
  - `set_function_evaluator(evaluator)`: `evaluator(signature, context, args)`
    evaluates a function a profile implements with an artifact, or raises
    `CannotEvaluate` to leave it unevaluated.
  - `set_attribute_written_check(check)`: `check(node, tokens, through,
    reader)` says whether an attribute an operation reads is written by an
    operation certain to have run before it -- which depends on the order the
    application runs operations in, so TOSCA cannot say.

  With none of these, any artifact type is accepted, as TOSCA allows; a
  function a profile implements with an artifact, Python or not, is left
  unevaluated, and a validation clause built on one is recorded as not
  checked (`tosca_core.models.unchecked.collect()` gathers them), never
  counted as passed; and an attribute an operation reads is guaranteed only by
  a value the templates give it. The Ubicity orchestrator's extensions are in its
  `ubicity/processors/onboarding.py`.

## Tests

```bash
pytest
```

`tests/test_standalone.py` checks, in a separate interpreter, that every
module imports and a template validates with Flask and any embedding
application unavailable.

## License

Apache License 2.0; see [LICENSE](https://github.com/ubicity-corp/tosca-core/blob/master/LICENSE).
