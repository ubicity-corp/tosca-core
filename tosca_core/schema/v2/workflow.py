"""
Workflow Template Schema classes
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2017-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger = logging.getLogger(__name__)

# Marshmallow support
from marshmallow import Schema, fields, post_load
from tosca_core.schema.named_object_map import NamedObjectMap

# Schemas used by WorkflowSchema
from tosca_core.schema.base import BaseSchema
from .property_declaration import (
    InputDeclarationSchema,
    WorkflowOutputDeclarationSchema)
from .operation_implementation import OperationImplementationSchema
from .activity import ActivitySchema

# Object class for this schema
from tosca_core.models.workflow_template import ToscaWorkflowTemplate


def create_workflow_template(**kwargs) -> ToscaWorkflowTemplate:
    return ToscaWorkflowTemplate(**kwargs)


class WorkflowStepSchema(Schema):
    target = fields.Str()
    target_relationship = fields.Str()
    filter = fields.Dict()
    activities = fields.List(fields.Nested(ActivitySchema))
    on_success = fields.List(fields.Str())
    on_failure = fields.List(fields.Str())


class WorkflowSchema(BaseSchema):
    inputs =         NamedObjectMap(fields.Nested(InputDeclarationSchema))
    outputs =        NamedObjectMap(fields.Nested(WorkflowOutputDeclarationSchema))
    preconditions =  fields.Dict()
    steps =          NamedObjectMap(fields.Nested(WorkflowStepSchema))
    implementation = fields.Nested(OperationImplementationSchema)

    @post_load
    def make_object(self, data: dict, **kwargs) -> ToscaWorkflowTemplate:
        return create_workflow_template(**data)
