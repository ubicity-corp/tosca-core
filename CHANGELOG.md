# Changes

What changed in each release that changes the public API
([docs/api.md](docs/api.md)), and what to do about it. tosca-core follows
semantic versioning: only a major release changes the public API
incompatibly.

## 1.1.0

**Implementing files** ([docs/validation.md](docs/validation.md#implementing-files)):
a TOSCA 2.0 file with a top-level `implements` adds implementations to an
onboarded profile's functions, at the function level or per signature. New
grammar only; every file valid before is valid now, except that an ordinary
file still may not give a function-level `implementation`.

**Two new columns.** An existing database needs them added before the new
version opens it; a new database gets them from `create_tables()`:

```sql
ALTER TABLE tosca_template ADD COLUMN _defining_profile_id INTEGER REFERENCES tosca_profile(id);
ALTER TABLE tosca_import ADD COLUMN implements BOOLEAN DEFAULT FALSE;
```

A function signature's existing implementation artifacts, with no defining
profile recorded, are taken as their own profile's.

**Embedding and `STATE_NAMES` are provisional** ([docs/api.md](docs/api.md#versions)):
public, but they may change in a minor release, which says what changed and
what to do here. Nothing changes in them in this release.

**Workflow inputs follow the rules service-template inputs follow.** Both are
incoming parameters (TOSCA 2.0, Parameter Definition), and one implementation
now validates the values supplied for either. For a workflow this changes two
things: a value supplied for an input with a fixed `value` is refused, since a
fixed value cannot be changed, where it was accepted; and a required input
with a fixed `value` needs nothing supplied, where it was refused.

**`tosca_core.lint` is now `tosca_core.cli`.** It holds what `tosca-validate`
runs; the command is unchanged. Not public API, but an import of
`tosca_core.lint` needs the new name.

**The `kind` keyname's error names `relationship-kind`**, the kebab-case
metadata key; `relationship_kind` is still accepted.

## 1.0.0

The first release published on PyPI. The public API is 0.4's, unchanged, and
is now kept under semantic versioning. Nothing to do coming from 0.4.1.

## 0.4.0

What the open core does is narrowed to what TOSCA defines; what belongs to an
orchestrator moved out (decided 2026-11-09).

**tosca-core runs no function a profile implements.** 0.3 evaluated functions
implemented in Python itself (TOSCA 1.3's `tosca.artifacts.Implementation.Python`
and the community's `Python` type), so a validation clause built on the
community's `$in_range` was checked standalone. Now such a clause is reported
as not checked, as one built on any other artifact always was, and validating
a template never runs code a profile ships. Removed:

- `tosca-validate --no-run-functions`: drop it from command lines; there is
  nothing left to turn off.
- the `RUN_PYTHON_FUNCTIONS` setting and `TOSCA_CORE_RUN_PYTHON_FUNCTIONS`;
  `configure(RUN_PYTHON_FUNCTIONS=...)` now raises `TypeError`.
- `tosca_core.python_functions` (internal, but the orchestrator called its
  `run_function`). An application that runs these functions installs an
  evaluator with `set_function_evaluator`, which no longer replaces an
  evaluator of the core's: with none installed, there is none.

**The `kind` keyname on relationship types is refused**, in both grammars. It
was a Ubicity extension; state the kind in metadata, as the TOSCA community
does, and as the error says:

```yaml
relationship_types:
  HostedOn:
    metadata:
      relationship_kind: CONTAINMENT
```

**tosca-core creates no instances, and knows nothing of how they are named or
when operations run.** The templates' `instantiate()` methods, a count
evaluated in a service (`get_count`), the workflow step expansion and
`register_instance_factory` (with `tosca_core.models.instance_factory`) are
removed: an application that runs services builds its instances itself. A
path's named head against a service of instances is resolved by the service,
which answers `resolve_node(name, index, select)`. And whether an attribute an
operation reads is written by an operation certain to run first is asked of a
new extension point, `set_attribute_written_check(check)`; with none, only a
value the templates give an attribute guarantees it (it is not refused, only
warned about, as before). `exceptions.InstantiateError` goes with them.

**Deleting a service template no longer checks for services created from it**
(the core creates none). An application that creates them refuses the delete
itself while they exist.

**`tosca-validate --reset`** starts from scratch: it deletes every cached
catalog and leftover run directory, and nothing else under `WORK_DIR`; with
targets, it then validates them against a catalog built anew.

**Licensed under Apache-2.0** (`LICENSE`).

Also: the package's author is Ubicity Corp. (info@ubicity.com), and messages
and docstrings no longer name the orchestrator's processors or modules.
