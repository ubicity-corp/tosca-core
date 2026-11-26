# tosca-core

A parser and semantic validator for TOSCA 2.0 and the TOSCA Simple Profile
in YAML 1.3, with Simple Profile 1.0 to 1.2 accepted and validated as 1.3.

tosca-core reads service templates and profiles, packaged as CSARs, as CSAR
directories or as single YAML files. It builds a model of the types,
declarations and templates they define, resolves imports and `derived_from`
against a catalog of profiles, evaluates the functions TOSCA defines, and
checks the result against TOSCA's rules. Deploying what a template describes
is the work of an application that embeds tosca-core, which can extend
validation with what it knows about running artifacts.

The public API, what stays stable from one release to the next, is in
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

## Validate from the command line

`tosca-validate` validates from a shell, building the catalog once and
caching it:

```console
$ tosca-validate -p profiles svc/my-service
FAIL svc/my-service  (24ms)
       main.yaml:28  service_template › node_templates › client › properties › performance
           $get_property: ['SELF', 'RELATIONSHIP', 'server', 'CAPABILITY', 'quality'] not found

1 of 1 target(s) failed -- 1 error(s)
```

Each target is a CSAR, a CSAR directory or a single TOSCA file. The catalog
holds the normative profiles and every profile under the trees given with
`-p` (or `TOSCA_CORE_PROFILES`, separated like `PATH`). It is cached until
the trees or tosca-core change: building it for a few dozen profiles takes
tens of seconds, and a run against the cached catalog takes well under one.

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

It exits 0 when every target is valid, 1 when any has a finding or cannot be
read, and 2 for a usage error, a catalog that cannot be built, or a target a
restricted catalog refused.

**Validation evaluates the functions TOSCA defines, and only those.** A
function a profile implements with an artifact, such as the TOSCA community
profile's `$in_range`, is left to an application that runs artifacts. A
validation clause built on one is listed as **not checked** under its target,
and does not make the target fail.

**[docs/validation.md](https://github.com/ubicity-corp/tosca-core/blob/master/docs/validation.md)**
covers the rest: reading the output and its JSON, giving profile trees,
restricting the catalog, the cache, and what validation leaves to the
application that deploys a template.

## Validate from Python

From Python, validation needs a catalog holding the normative profiles, which every
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

`validate_csar` persists nothing. It returns `{}` for a valid target, a string
when the target cannot be read at all, and otherwise the errors as a nested
dict that follows the structure of the documents
([docs/api.md](https://github.com/ubicity-corp/tosca-core/blob/master/docs/api.md)).
A template that imports other profiles needs them onboarded first with
`onboard_csar`, inside a `session_scope()` so they are committed.

To validate many templates in one process, call `reset_session()` between
them, so that a validation that fails leaves nothing behind for the next.

## Configuration

tosca-core reads its settings from `tosca_core.constants.constants`, which an
application changes with `configure()`. From a shell:

| Environment variable | Sets |
|---|---|
| `TOSCA_CORE_DB_URI` | the database (`DB_URI`); in-memory SQLite by default |
| `TOSCA_CORE_DIR` | the working directory tosca-core reads and writes (`WORK_DIR`); `tosca-core` under `XDG_CACHE_HOME`, or `~/.cache/tosca-core`, by default |
| `TOSCA_CORE_LOCAL_REPOSITORY_ROOTS` | the directories outside a CSAR that a `file:` repository may name; absolute paths, separated like `PATH`; none by default |
| `TOSCA_CORE_PROFILES` | `tosca-validate`'s profile trees |

Every setting is listed in
[docs/api.md](https://github.com/ubicity-corp/tosca-core/blob/master/docs/api.md#3-configuration).

A file-backed SQLite database (`sqlite:////abs/path/catalog.db`) keeps the
catalog between runs, so the normative profiles are loaded once. A catalog is
the database together with its working directory: the database records each
onboarded CSAR by the absolute path it was unpacked to, under `WORK_DIR`.
Keep the two together.

## Embedding tosca-core

An application that deploys what tosca-core validates configures it at
startup, builds its own runtime objects from the templates, and extends
validation from the modules it lists in `EXTENSION_MODULES`: a check for every
implementation artifact, an evaluator for functions profiles implement with
artifacts, and a check for attributes an earlier operation writes. Where
tosca-core evaluates a path against a service of instances, it asks that
service to resolve the node a path names. The full contract is section 4 of
[docs/api.md](https://github.com/ubicity-corp/tosca-core/blob/master/docs/api.md#4-embedding).

## Tests

```bash
pytest
```

`tests/test_standalone.py` checks, in a separate interpreter, that every
module imports and a template validates with Flask and any embedding
application unavailable.

## Contributing

Report a problem or ask a question by opening an issue. Changes come as pull
requests, with a test that pins what they fix and `pytest` passing. Report a
security vulnerability privately, through the repository's Security tab,
rather than in an issue.

## License

Apache License 2.0; see [LICENSE](https://github.com/ubicity-corp/tosca-core/blob/master/LICENSE).
