# tosca-core's public API

What tosca-core promises to keep stable, and what it does not.

## Two tiers

**Public**, and kept stable as below:

1. the `tosca-validate` command: its options, exit status and JSON output;
2. the library entry points: validating, onboarding, building a catalog,
   units of work;
3. configuration: the settings and the environment variables;
4. embedding: extending validation, and what a service of instances answers
   (provisional, below).

Each is listed in full below. The names of 2 and 4, with the error types
and the configuration object, are exported by the `tosca_core` package
itself (`from tosca_core import validate_csar`); that list is the
library's public API.

**Internal**, and free to change in any release: everything else. That
includes the model classes (types, declarations, templates, profiles) and
their methods, the Marshmallow schemas, the ingest pipeline
(`tosca_core.actions`), `tosca_core.validate`, the built-in functions, and
the database tables. An application that reaches into them pins tosca-core
to an exact version and moves with it.

## Versions

Semantic versioning, from 1.0:

- a **patch** release (1.0.0 to 1.0.1) fixes without changing the public tier;
- a **minor** release (1.0 to 1.1) may add to it, and changes nothing that
  works already;
- only a **major** release (1 to 2) changes it incompatibly, and says what
  changed and what to do in [CHANGELOG.md](../CHANGELOG.md).

**Provisional** names are public, but may change in a minor release while
the applications that embed tosca-core are few: everything under 4.
Embedding, and the `STATE_NAMES` setting. A minor release that changes one
says what changed and what to do in [CHANGELOG.md](../CHANGELOG.md).

The internal tier may change in any release.

## 1. `tosca-validate`

```
tosca-validate [-p DIR]... [--only-profile GLOB]... [--exclude-profile GLOB]...
               [--rebuild] [--reset] [--catalog-info] [--skip-file-checks]
               [-f text|json] [-q] [-v] TARGET...
```

The options are documented in [validation.md](validation.md). Exit status:
`0` every target valid, `1` any finding or unreadable target, `2` a usage
error, a catalog that cannot be built, or a target a restricted catalog
refused. A refusal takes precedence: a run with one exits `2` whatever the
other targets' verdicts.

`-f json` writes one object:

```json
{
  "format": 1,
  "results": [
    {
      "target": "svc/port",
      "ok": false,
      "fatal": null,
      "refused": null,
      "seconds": 0.0213,
      "findings": [{"file": "main.yaml", "path": ["service_template", "node_templates", "port"],
                    "line": 9, "message": "..."}],
      "not_checked": [{"subject": "property 'number'", "value": "50", "functions": ["$in_range"]}]
    }
  ]
}
```

`format` is raised when a field changes meaning or goes away; a new field
does not raise it. The fields are described under "Reading the output" in
[validation.md](validation.md). The text output is for people and may
change in any release.

## 2. Library entry points

| Name | |
|---|---|
| `bootstrap(db_uri=None)` | bind the database (`DB_URI` by default), import the model modules and `EXTENSION_MODULES` |
| `create_tables()` | create the catalog's tables |
| `load_normative_profiles()` | onboard the TOSCA 2.0 and Simple Profile 1.3 profiles tosca-core ships; raises `CatalogError` |
| `CatalogError` | raised when a normative profile does not onboard; `csar_name` names it and `errors` holds the validator's findings |
| `validate_csar(path, name=None, skip_file_checks=False)` | validate a CSAR, CSAR directory or TOSCA file; persists nothing |
| `onboard_csar(path, name=None)` | validate and add to the catalog, without committing; returns `(repository, errors)` |
| `init_db(db_uri)` | bind the database only |
| `session_scope()` | a unit of work: commit on success, roll back on error, remove the session |
| `reset_session()` | discard the session between independent validations |
| `db` | the database object the models are declared on |
| `unchecked` | `unchecked.collect()`: the validation clauses that could not be evaluated, gathered around a validation |
| `exceptions`, `ValidationError` | the errors tosca-core raises (`tosca_core.models.exceptions`) |

### What `validate_csar` returns

`{}` when the target is valid. A string when it cannot be read at all: not
found, not a CSAR, no metadata, an empty archive. Otherwise the errors as a
nested dict that follows the structure of the documents: keyed by file, then by each step of
the YAML path to what is wrong (a keyname, a template name, a list index as
a string), with a message, or a list of messages, at the end of each path;
`line`, beside the keys it locates, is the line number where the validator
knew one.

```python
{"main.yaml": {
    "service_template": {
        "line": 3,
        "node_templates": {
            "server": {"line": 5, "type": "not found"}}}}}
```

`onboard_csar` returns its errors the same way. `tosca-validate` flattens
this tree into the `findings` of its JSON output.

## 3. Configuration

`tosca_core.constants.constants` (exported as `constants`) holds every
setting; `constants.configure(NAME=value, ...)` changes them in place, and
tosca-core reads them when it needs them, so a change made after import
takes effect.

| Setting | Default | Environment |
|---|---|---|
| `DB_URI` | `sqlite://` (in memory) | `TOSCA_CORE_DB_URI` |
| `WORK_DIR` | `tosca-core` under `XDG_CACHE_HOME`, or `~/.cache/tosca-core` | `TOSCA_CORE_DIR` |
| `LOCAL_REPO_ROOT` | `WORK_DIR/repository` | |
| `LOCAL_REPOSITORY_ROOTS` | none | `TOSCA_CORE_LOCAL_REPOSITORY_ROOTS` (absolute, separated like `PATH`) |
| `STATE_NAMES` (provisional), the states the application's workflows use; a `set_state` naming another is logged as a warning, never refused | none: any state accepted | |
| `MODEL_MODULES`, `EXTENSION_MODULES` | tosca-core's models; none | |
| `SUPPORTED_DEFINITIONS_VERSIONS` | TOSCA 2.0 and Simple Profile 1.0–1.3 | |

`TOSCA_CORE_PROFILES` gives `tosca-validate` its profile trees.

## 4. Embedding

Provisional (see *Versions*).

An application that runs what tosca-core validates extends it from modules
listed in `EXTENSION_MODULES`, which `bootstrap()` imports:

| Name | |
|---|---|
| `register_implementation_check(check)` | `check(artifact, type_name, operation, declaration)` is called for every implementation artifact as validation reaches it, and returns `{key: message}` errors, reported where the artifact is |
| `set_function_evaluator(evaluator)` | `evaluator(signature, context, args)` evaluates a function a profile implements with an artifact, or raises `CannotEvaluate` to leave it unevaluated; `None` removes it |
| `CannotEvaluate` | raised by an evaluator for a function it does not evaluate |
| `set_attribute_written_check(check)` | `check(node, tokens, through, reader)` says whether an attribute an operation reads is written by an operation certain to have run before it, which depends on the order the application runs operations in; without one, only a value the templates give an attribute guarantees it; `None` removes it |

`operation_input_names()` and `operation_output_names()` in
`tosca_core.validate.operation_implementation` give an implementation check
an operation's names. tosca-core has no evaluator of its own: with none
installed, such a function is left unevaluated.

**A service of instances.** tosca-core creates no instances, but evaluates
paths against an application's when the application asks it to (a property
or attribute read at runtime). For a named head (a path starting with a node
template's name rather than `SELF`, `SOURCE` or `TARGET`) it asks the
service the context belongs to:

```python
service.resolve_node(name, index, select) -> entity or list of entities
```

`index` is `None` (follow the template's declaration: a list when it may yield
several representations, even if it yielded one), `'ALL'` (every
representation), or a non-negative integer, already evaluated; `select` is true
when a selectable template may answer with the node it was bound to. It raises
`KeyError` for "no value yet" and `exceptions.InvalidPathError` for an index
that cannot exist. A service without `resolve_node` is taken to be a service of
templates, which answers from its `nodes`.
