"""
Where a TOSCA 2.0 template may read a service input.

A service input reaches an entity only through its properties, so an update
can tell when it changed and every other node can read it. An operation input
a template assigns, at the interface or the operation, and an artifact's
property, are refused when they call $get_input anywhere within them, with the
remedy in the message. A property still reads its input, and an operation
input still reads a property.

Only the TOSCA 2.0 schema has the rule; TOSCA 1.3 templates keep what their
specification allows.
"""

import importlib

import pytest
from marshmallow import ValidationError

from tosca_core.constants import constants

for model_module in constants.MODEL_MODULES:
    importlib.import_module(model_module)

from tosca_core.schema.v2.artifact_template import ArtifactTemplateSchema
from tosca_core.schema.v2.interface_template import InterfaceTemplateSchema
from tosca_core.schema.v2.operation import OperationSchema
from tosca_core.schema.v2.functions import reads_service_input

REMEDY = "only through its properties"
INPUT = {"$get_input": "region"}


def refused(schema, data):
    with pytest.raises(ValidationError) as error:
        schema().load(data)
    return str(error.value.messages)


def test_an_operation_input_is_refused():
    assert REMEDY in refused(OperationSchema, {"inputs": {"region": INPUT}})


def test_an_interface_input_is_refused():
    assert REMEDY in refused(InterfaceTemplateSchema, {"inputs": {"region": INPUT}})


def test_an_artifact_property_is_refused():
    assert REMEDY in refused(ArtifactTemplateSchema, {
        "file": "create.sh", "properties": {"host": {"address": INPUT}}})


def test_an_input_nested_in_another_function_is_refused():
    assert REMEDY in refused(OperationSchema, {
        "inputs": {"name": {"$concat": ["vm-", INPUT]}}})


def test_an_operation_input_reading_a_property_loads():
    operation = OperationSchema().load(
        {"inputs": {"region": {"$get_property": ["SELF", "region"]}}})
    assert operation.inputs == {"region": {"$get_property": ["SELF", "region"]}}


@pytest.mark.parametrize("data, reads", [
    (INPUT, True),
    ({"$concat": ["a", [INPUT]]}, True),
    ({"$get_property": ["SELF", "region"]}, False),
    ("$get_input", False),
    ({"$$get_input": "region"}, False),
])
def test_what_reads_a_service_input(data, reads):
    assert reads_service_input(data) is reads
