"""
Input values supplied for a service template or a workflow follow one set of
rules: both are incoming parameters with the same keynames (TOSCA 2.0,
Parameter Definition).

A value is supplied only for a declared input; an input with a fixed value
takes none, since a fixed value cannot be changed; a required input not
supplied is satisfied by its fixed value or its default. A service update checks only what it supplies.
"""

import shutil
import textwrap

import pytest

from tosca_core.csar import onboard_csar
from tosca_core.models.service_template import ToscaServiceTemplate
from tosca_core.models.workflow_template import ToscaWorkflowTemplate

INPUTS = """
      fixed:
        type: integer
        value: 5
      defaulted:
        type: integer
        default: 3
      plain:
        type: integer
      optional:
        type: integer
        required: false
"""

TEMPLATE = f"""
tosca_definitions_version: tosca_2_0
node_types:
  Thing: {{}}
service_template:
  inputs:{textwrap.indent(INPUTS, '  ')}
  node_templates:
    node:
      type: Thing
  workflows:
    run:
      inputs:{textwrap.indent(INPUTS, '    ')}
      steps:
        only:
          target: node
          activities:
            - set_state: started
"""


@pytest.fixture
def templates(catalog):
    directory = catalog / "service"
    directory.mkdir()
    (directory / "TOSCA.meta").write_text(
        "CSAR-Version: 2.0\nCreated-By: tests\nEntry-Definitions: service.yaml\n")
    (directory / "service.yaml").write_text(TEMPLATE)
    csar = shutil.make_archive(str(directory), "zip", str(directory))
    _repository, errors = onboard_csar(csar, "service")
    assert errors == {}
    service = ToscaServiceTemplate.query.one()
    workflow = ToscaWorkflowTemplate.query.filter_by(name="run").one()
    return service, workflow


@pytest.fixture(params=["service", "workflow"])
def template(request, templates):
    return templates[0] if request.param == "service" else templates[1]


def test_a_fixed_value_cannot_be_supplied(template):
    errors = template.validate_input_values({"fixed": 6, "plain": 1, "optional": 2})
    assert errors == {"fixed": "overriding value from definition is not allowed"}


def test_a_fixed_value_satisfies_a_required_input(template):
    assert template.validate_input_values({"plain": 1, "optional": 2}) == {}


def test_a_default_satisfies_a_required_input(template):
    errors = template.validate_input_values({"plain": 1})
    assert "defaulted" not in errors
    errors = template.validate_input_values({})
    assert set(errors) == {"plain"}


def test_an_undeclared_input_is_refused(template):
    errors = template.validate_input_values({"plain": 1, "other": 1})
    assert errors["other"] == "not previously defined"


def test_an_invalid_value_is_refused(template):
    assert "plain" in template.validate_input_values({"plain": "one"})


def test_an_update_checks_only_what_it_supplies(templates):
    service, _workflow = templates
    assert service.validate_input_values({}, check_required=False) == {}
    assert "fixed" in service.validate_input_values({"fixed": 6}, check_required=False)
