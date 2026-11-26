"""
tosca-validate: validate TOSCA templates and profiles from the command
line, against a catalog that is built once and cached.

Validation needs every profile a template imports onboarded into a
catalog first, and onboarding a tree of profiles is the slow part. The
catalog it produces depends only on the profile tree and on this
package, so it is cached under WORK_DIR, keyed by a hash of both, and
reused until either changes.

Nothing here judges a template: every verdict comes from
tosca_core.csar.validate_csar. This package decides what goes into the
catalog, keeps it, and reports what the validator says.

  profiles.py   finding profiles in a tree, choosing and ordering them
  cache.py      building, caching and restoring the catalog
  validate.py   validating one target and flattening its errors
  report.py     text and JSON output
  __main__.py   the command line
"""
