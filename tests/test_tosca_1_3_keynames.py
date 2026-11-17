"""
Keynames TOSCA 1.3 defines and TOSCA 2.0 dropped.

'timeout' and 'operation_host' on an operation implementation, 'operation_host'
on a workflow step, and 'deploy_path' on an artifact are TOSCA 1.3 keynames. The
TOSCA 2.0 grammar refuses them as keynames it does not define. The TOSCA 1.3
grammar accepts them: 'timeout' and 'operation_host' are ignored with a
warning, and 'deploy_path' is refused as unsupported when the artifact is
validated.
"""

import importlib
import logging
from types import SimpleNamespace

import pytest
from marshmallow import ValidationError

from tosca_core.constants import constants

# Loading an artifact builds a model object, which SQLAlchemy can configure
# only once every model is defined, as the migrate command arranges.
for model_module in constants.MODEL_MODULES:
    importlib.import_module(model_module)

from tosca_core.schema.v1.operation_implementation import (
    OperationImplementationSchema as V1OperationImplementationSchema)
from tosca_core.schema.v1.workflow import WorkflowStepSchema as V1WorkflowStepSchema
from tosca_core.schema.v2.artifact_template import ArtifactTemplateSchema as V2ArtifactTemplateSchema
from tosca_core.schema.v2.operation_implementation import (
    OperationImplementationSchema as V2OperationImplementationSchema)
from tosca_core.schema.v2.workflow import WorkflowStepSchema as V2WorkflowStepSchema
from tosca_core.validate import get_validator


@pytest.mark.parametrize("schema, data, keyname", [
    (V2OperationImplementationSchema, {"primary": "create.sh", "timeout": 60}, "timeout"),
    (V2OperationImplementationSchema, {"primary": "create.sh", "operation_host": "SELF"}, "operation_host"),
    (V2WorkflowStepSchema, {"target": "node", "operation_host": "SELF"}, "operation_host"),
    (V2ArtifactTemplateSchema, {"type": "Bash", "file": "create.sh", "deploy_path": "/opt"}, "deploy_path"),
], ids=["implementation-timeout", "implementation-operation_host",
        "step-operation_host", "artifact-deploy_path"])
def test_tosca_2_0_refuses_the_keyname(schema, data, keyname):
    with pytest.raises(ValidationError) as error:
        schema().load(data)
    assert keyname in str(error.value)


@pytest.mark.parametrize("schema, data, keyname", [
    (V1OperationImplementationSchema, {"primary": "create.sh", "timeout": 60}, "timeout"),
    (V1OperationImplementationSchema, {"primary": "create.sh", "operation_host": "SELF"}, "operation_host"),
    (V1WorkflowStepSchema, {"target": "node", "operation_host": "SELF"}, "operation_host"),
], ids=["implementation-timeout", "implementation-operation_host", "step-operation_host"])
def test_tosca_1_3_accepts_the_keyname_with_a_warning(schema, data, keyname, caplog):
    with caplog.at_level(logging.WARNING):
        schema().load(data)
    assert f"'{keyname}' is not supported and is ignored" in caplog.text


def test_tosca_1_3_deploy_path_is_refused_as_unsupported():
    errors = get_validator('ToscaArtifact').validate_deploy_path(
        SimpleNamespace(name="script", deploy_path="/opt/placed"))
    assert "not supported" in errors


def test_artifact_without_deploy_path_passes():
    assert not get_validator('ToscaArtifact').validate_deploy_path(SimpleNamespace(name="script"))
