"""
Validating is a dry run of onboarding, not a weaker check.

A CSAR must define a profile (by naming one) or a service template.
Onboarding refused one that defines neither, but validation accepted it
-- the check was skipped when only validating -- so a template passed
validation and then failed to onboard.
"""

import textwrap

from tosca_core.csar import validate_csar

# Types, but no profile name and no service template
NEITHER = textwrap.dedent("""\
    tosca_definitions_version: tosca_2_0
    node_types:
      Server: {}
    """)

SERVICE = textwrap.dedent("""\
    tosca_definitions_version: tosca_2_0
    node_types:
      Server: {}
    service_template:
      node_templates:
        server:
          type: Server
    """)


def test_neither_a_profile_nor_a_service_template_is_refused(catalog):
    (catalog / "neither.yaml").write_text(NEITHER)
    errors = validate_csar(str(catalog / "neither.yaml"))
    assert "no profile or service catalog entry defined" in str(errors)


def test_a_service_template_still_validates(catalog):
    (catalog / "service.yaml").write_text(SERVICE)
    assert validate_csar(str(catalog / "service.yaml")) == {}
