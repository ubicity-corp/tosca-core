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
    InputDeclarationSchema, create_input_declaration,
    ServiceOutputDeclarationSchema, create_output_declaration)
from .operation_implementation import OperationImplementationSchema
from .condition import ConditionSchema
from .activity import ActivitySchema

# Object class for this schema
from tosca_core.models.workflow_template import ToscaWorkflowTemplate


def create_workflow_template(**kwargs) -> ToscaWorkflowTemplate:
    return ToscaWorkflowTemplate(**kwargs)


class PreconditionSchema(Schema):
    target = fields.Str()
    target_relationship = fields.Str()
    condition = fields.List(fields.Nested(ConditionSchema))


class WorkflowStepSchema(Schema):
    target = fields.Str()
    target_relationship = fields.Str()
    operation_host = fields.Str()
    filter = fields.List(fields.Nested(ConditionSchema))
    activities = fields.List(fields.Nested(ActivitySchema))
    on_success = fields.List(fields.Str())
    on_failure = fields.List(fields.Str())

    @post_load
    def warn_about_ignored_keynames(self, data: dict, **kwargs) -> dict:
        """TOSCA 1.3's 'operation_host' is accepted but not acted on, so say
        so rather than ignore it silently."""
        if 'operation_host' in data:
            logger.warning("workflow step keyname 'operation_host' is not "
                           "supported and is ignored")
        return data


class WorkflowSchema(BaseSchema):
    inputs =         NamedObjectMap(fields.Nested(InputDeclarationSchema,
                                                  load_default=create_input_declaration),
                                    allow_none=True)
    outputs =        NamedObjectMap(fields.Nested(ServiceOutputDeclarationSchema,
                                                  load_default=create_output_declaration),
                                    allow_none=True)
    preconditions =  fields.List(fields.Nested(PreconditionSchema))
    steps =          NamedObjectMap(fields.Nested(WorkflowStepSchema))
    implementation = fields.Nested(OperationImplementationSchema)

    @post_load
    def make_object(self, data: dict, **kwargs) -> ToscaWorkflowTemplate:
        return create_workflow_template(**data)


# Global workflow schemas
workflow_schema = WorkflowSchema()
workflows_schema = WorkflowSchema(many=True)
