# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

tosca-core is a TOSCA 2.0 and TOSCA Simple Profile 1.3 parser and semantic validator: YAML → a SQLAlchemy model of types, declarations and templates → validation against TOSCA's rules. It is the open core of the Ubicity orchestrator, which depends on it and adds everything that runs what tosca-core validates: runtime instances, workflows, artifact processors, a REST API. The dependency is one-way: an application embeds tosca-core, and tosca-core never imports the application. `tosca-validate` (`tosca_core/cli/`) is the command-line validator.

## Commands

```bash
pip install -e ".[test]"
pytest                     # all tests; tests/test_standalone.py runs in its own interpreter
tosca-validate -p <profile-tree> <target>...   # validate from the shell (see README)
```

**Cutting a release** is a version bump in `pyproject.toml`, an entry in `CHANGELOG.md` when the public API changes (semantic versioning: an incompatible change only in a major release), and an annotated tag `v<version>`. **Publishing to PyPI** is publishing a GitHub Release for that tag: `.github/workflows/publish.yml` runs only then (a pushed tag alone publishes nothing), checks the tag is `v<version>`, runs the tests, builds and `twine check`s, and uploads by trusted publishing, so no token is stored. Run by hand (`workflow_dispatch`), the same workflow rehearses the path against TestPyPI, uploading `<version>.dev<run number>`, since neither index accepts a version twice.

**Tests** are targeted regression suites, not broad coverage:

- `tests/test_standalone.py` — every module imports, and a catalog builds and templates validate, implementation artifacts among them with nothing installed to run them, with Flask and any embedding application unimportable, and that nothing extends validation, no function evaluator is installed, and no template can instantiate
- `tests/test_extensions.py` — what an embedding application adds to validation: implementation checks (given the artifact type's name, their errors reported, none registered accepting any type) and the function evaluator (installed and removed; none, or `CannotEvaluate`, leaving the function unevaluated)
- `tests/test_profile_functions_not_run.py` — the core runs no function a profile implements, Python (TOSCA 1.3's type, the community's) or not: with no evaluator installed it is left unevaluated, and there is no setting or module to run one
- `tests/test_state_names.py` — `set_state` names: any standalone, a warning for one outside the application's `STATE_NAMES`
- `tests/test_public_api.py` — every name `tosca_core` exports resolves and is in `docs/api.md`, and importing `tosca_core` loads no models
- `tests/test_reset_session.py` — `reset_session()` between units of work, and `init_db()` forgetting cached built-in types when it binds another database
- `tests/test_service_template_delete.py` — a service template is deleted whenever asked: the core creates no services, so it checks for none
- `tests/test_validate_only.py` — validation refusing a CSAR that defines neither a profile nor a service template, as onboarding does
- `tests/test_repository_paths.py` — which files a `file://` repository may read and which directories may be deleted, by resolved path; what a refusal says; retrieving a file under a directory with a space in its name
- `tests/test_local_repository_confinement.py` — where a `file:` repository may point (its CSAR or `LOCAL_REPOSITORY_ROOTS`), `file:` URLs naming a host, and configuring the roots
- `tests/test_lint.py` — `tosca-validate`: profile discovery and selection, the catalog cache and `--reset` (deletes the cached catalogs and run directories only), reporting (clauses not checked among it, the JSON format), and the command line (a community Python function not run, its clause reported as not checked)
- `tests/test_unchecked.py` — a validation clause that could not be evaluated is satisfied but recorded as not checked, once, naming its functions
- `tests/test_tosca_path.py` — path flattening in `ToscaPath.expression`, and reading values by path
- `tests/test_path_head_resolution.py` — a path's named head: a service of templates answers from its nodes whatever the index; a service of instances is asked `resolve_node(name, index, select)` after a negative index is refused, `select` only from `get_entity`
- `tests/test_function_caching.py` — the resolved-function key format `$(sig_id[:type_id])` and keeping the `:type_id` suffix when a deferred function re-emits itself
- `tests/test_tosca_1_3_keynames.py` — the TOSCA 1.3 keynames TOSCA 2.0 dropped
- `tests/test_artifact_checksum.py` — artifact checksums (TOSCA 2.0 §12.2)
- `tests/test_artifact_type_inference.py` — an artifact's type from its file extension, and which of two same-named types a profile sees
- `tests/test_implied_relationship_type.py` — a requirement definition that names no relationship type
- `tests/test_relationship_kind.py` — how a relationship type's kind is found (from metadata, else its parent's), and the `kind` keyname refused by both grammars, naming the metadata spelling
- `tests/test_merge_idempotency.py`, `tests/test_refinement_completeness.py` — merging a refinement with the declaration it refines is safe to repeat, and a completed refinement has nothing left to merge
- `tests/test_presence_check.py` — whether a value is guaranteed present at onboarding: what counts as written, relationship reads, why a check is undecided, and the attribute-written check asked for an attribute an operation reads (none installed: not guaranteed that way)
- `tests/test_value_required_along_path.py`, `tests/test_attribute_required.py`, `tests/test_attribute_value_presence.py` — when a value is required, and that an attribute's value is not checked for presence
- `tests/test_incomplete_optional_inputs.py` — a complex value lacking required fields, refused unless required fields are not checked (as for an optional operation input), nested and in lists and maps; a field without a value is absent from the evaluated value
- `tests/test_function_result_contract.py` — an implemented function declaring a result returns a value or fails (with an evaluator installed)
- `tests/test_builtin_absent_argument.py` — `$concat` of lists with an argument that has no value
- `tests/test_substitution_unmapped_inputs.py` — a substitution input with a value needs no mapping
- `tests/test_tosca_1_3_path_head.py` — a TOSCA 2.0 path may not start at `TARGET` or `SOURCE`
- `tests/test_recognized_names.py` — the dash-case interface and operation names, and the old spellings still accepted
- `tests/test_substituted_requirement_warnings.py` — the warning for requirements a substitution does not carry
- `tests/test_url_field.py` — a URL field is left out where no app serves its endpoint, and null where the object names nothing
- `tests/test_service_inputs_reach_properties.py` — TOSCA 2.0 refuses `$get_input` in operation inputs and artifact properties
- `tests/test_dependency_loops.py` — onboarding refuses a template whose explicit requirements form a loop
- `tests/test_artifact_file_location.py` — where an artifact's file is looked for: under its named repository from any template in the archive, or beside the template that declares it
- `tests/test_other_definitions_names.py` — how the service templates an archive's Other-Definitions carry are named
- `tests/test_artifact_path_steps.py` — `split_requirement_step`: what follows `RELATIONSHIP` in a `$get_artifact` path
- `tests/test_implementing_files.py` — implementing files: implementations stored as artifacts on the implemented signatures with the implementing profile as their profile (repository, file, type scope), function-level and per-signature by position, what is refused (unknown function, extra signatures, other keynames, declarations, a profile not onboarded, a conflict, importing one, a function-level implementation in an ordinary file), deleting either profile, and `profile show` on both
- `tests/test_input_values.py` — input values supplied for a service template or a workflow, by one set of rules: an undeclared input and an invalid value refused, a fixed value neither changed nor needing a value supplied, a default satisfying a required input, and an update checking only what it supplies
- `tests/test_requirement_mapping_short_name.py` — a requirement mapping keyed by a name of any length, two letters among them, is a name and not a [name, count] pair

## The rules that keep it standalone

`tests/test_standalone.py` enforces the first two.

- **No import of an embedding application, and no module-level import of Flask.** Flask is reached only through the lazy `url_for` in `tosca_core/schema/url.py`, which returns `None` without it.
- **The core does not name runtime classes, and creates no instances.** Building instances from templates is the embedding application's. A relationship between a definitional model and a runtime one is declared on the runtime side (as a `backref`), so the mappers here configure without it.
- **The core knows nothing of how instances are named or operations ordered.** A path's named head against a service of instances is the service's to resolve (`resolve_node(name, index, select)`, the contract in `docs/api.md`), and whether an operation certain to run before the reading one writes an attribute is the attribute-written check's (`extensions.set_attribute_written_check`). The presence check for a required value stays here, since TOSCA's requiredness decides it.
- **A clause that cannot be evaluated is reported, not passed.** A validation clause whose function cannot be evaluated where validation runs (one a profile implements with an artifact, Python or not, with no function evaluator installed) goes through `tosca_core/models/unchecked.py`: the value is accepted and the clause recorded as not checked, which `tosca-validate` reports. Never let such a clause count as checked.
- **The core has no processor concept, and runs no artifact.** It never asks whether an artifact can be run, and evaluates only the functions TOSCA defines (`tosca_core/builtin/`, its own code); a function a profile implements with an artifact, Python included, it leaves unevaluated, so validating never runs code a profile ships. An embedding application extends validation through `tosca_core/extensions.py`, from modules listed in `EXTENSION_MODULES`: implementation checks, called for every implementation artifact (to refuse what it cannot run); an evaluator for functions profiles implement with artifacts; and an attribute-written check (whether an operation certain to run first writes an attribute another reads). With none of these, any artifact type is accepted, every such function is left unevaluated, and an attribute an operation reads is guaranteed only by a value the templates give it.
- **An application's vocabulary is not the core's.** A relationship type states its kind in metadata (`relationship-kind`, the snake-case `relationship_kind` still accepted), as the TOSCA community does; the `kind` keyname is refused by both grammars. The core never creates services, so deleting a service template checks for none. The states a `set_state` may name are the application's (`STATE_NAMES`, none standalone: TOSCA defines none), and `tosca_core/models/exceptions.py` holds only what the core raises.
- **The public API is what `tosca_core` exports** (`docs/api.md`, `tests/test_public_api.py`): the `tosca-validate` command and its JSON (`format` 1), the library entry points, configuration, and the embedding API, including the `resolve_node` contract. Everything else is internal. Semantic versioning: only a major release changes the public tier incompatibly, with notes in `CHANGELOG.md`. A new export goes in `_PUBLIC` in `tosca_core/__init__.py` and in `docs/api.md`.
- **Settings are read at call time, never at import.** `tosca_core.constants.constants` is one `CoreConfig` object; an embedding application changes it in place with `configure()` at startup. A module-level `X = constants.Y` would freeze the standalone default.
- **Class names, table names and polymorphic identities are part of the database format** shared with embedding applications' deployments. Renaming a model class renames its table.
- **The library does not configure logging** or write outside `WORK_DIR` and the database. It reads a `file:` repository only inside its CSAR or a configured `LOCAL_REPOSITORY_ROOTS` entry; `WORK_DIR` itself is not readable to a template.
- **A catalog is the database and the directory its CSARs were unpacked into.** The database records each onboarded CSAR by the absolute `file://` URL of that directory (under `LOCAL_REPO_ROOT`), and where an evaluator is installed a profile-defined function runs its artifact from there. Anything that caches or moves a catalog carries both and rewrites the URLs, as `tosca_core/cli/cache.py` does (`restore()`); a database alone makes such functions fail as if the values they check were invalid.
- **Files and messages name no internal document** of any embedding application; a comment explains its point in place.
- **The docs stand on their own.** The README and `docs/` are public: they name no private repository, no embedding application's files or commands, and no product; an embedding application is "an application that embeds tosca-core".

## Layout

```
tosca_core/core.py        db (the Flask-SQLAlchemy-shaped API over plain SQLAlchemy), init_db, session_scope, reset_session
tosca_core/__init__.py    the public API, exported lazily (docs/api.md)
tosca_core/constants.py   CoreConfig: DB_URI, WORK_DIR, LOCAL_REPO_ROOT, LOCAL_REPOSITORY_ROOTS, SUPPORTED_DEFINITIONS_VERSIONS, MODEL_MODULES, EXTENSION_MODULES, STATE_NAMES
tosca_core/bootstrap.py   bootstrap(): init_db + import EXTENSION_MODULES
tosca_core/extensions.py  what an embedding application adds to validation: implementation checks, the function evaluator, the attribute-written check
tosca_core/catalog.py     create_tables(), load_normative_profiles() (the packaged csars/)
tosca_core/csar.py        validate_csar(), onboard_csar(): the library entry points
tosca_core/actions/ingest_csar.py   the CSAR → model → validation pipeline
tosca_core/models/        types, declarations, templates, profiles, functions; unchecked.py (clauses not checked)
tosca_core/schema/        Marshmallow schemas parsing TOSCA YAML (v1/ = Simple Profile, v2/ = TOSCA 2.0)
tosca_core/validate/      semantic validation
tosca_core/builtin/       built-in TOSCA functions and data types
tosca_core/cli/           tosca-validate: the command line, and the catalog cache it validates against
docs/validation.md        tosca-validate in full: output, profile trees, restriction, cache, what validation leaves to the application
docs/api.md               the public API: the two tiers, the versioning rule, every public name, the resolve_node contract
CHANGELOG.md              what each release changed in the public API, and what to do
.github/workflows/        tests.yml (every push), publish.yml (PyPI, on a published GitHub Release)
```

## License

Apache-2.0 (`LICENSE`), declared in `pyproject.toml` as a license expression, which needs setuptools 77.
