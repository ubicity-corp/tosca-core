"""
Returning the ORM to a clean slate between units of work.

A batch validator or a long-running process validates many templates in
one process, and some fail. reset_session() rolls back, discards the
session, and forgets the built-in types cached from it, so one failure
cannot leak into the next target. init_db() forgets the cache too when
it binds another database, whose rows the cached objects are not.
"""

import textwrap

from tosca_core.core import init_db, reset_session, session
from tosca_core.csar import validate_csar
from tosca_core.models import builtin_types

VALID = textwrap.dedent("""\
    tosca_definitions_version: tosca_2_0
    node_types:
      Server:
        properties:
          port: {type: integer}
    service_template:
      node_templates:
        server:
          type: Server
          properties: {port: 80}
    """)

INVALID = textwrap.dedent("""\
    tosca_definitions_version: tosca_2_0
    service_template:
      node_templates:
        server:
          type: NoSuchType
    """)


def test_reset_session_discards_the_session_and_the_cache(catalog):
    builtin_types.get("integer")
    assert builtin_types._cache
    reset_session()
    assert not session.registry.has()
    assert builtin_types._cache == {} and builtin_types._profile is None


def test_a_failed_validation_does_not_affect_the_next(catalog):
    (catalog / "invalid.yaml").write_text(INVALID)
    (catalog / "valid.yaml").write_text(VALID)
    assert validate_csar(str(catalog / "invalid.yaml")) != {}
    reset_session()
    assert validate_csar(str(catalog / "valid.yaml")) == {}


def test_binding_another_database_forgets_the_cache(catalog, tmp_path):
    builtin_types.get("integer")
    assert builtin_types._cache
    init_db(f"sqlite:///{tmp_path / 'other.db'}")
    assert builtin_types._cache == {}
