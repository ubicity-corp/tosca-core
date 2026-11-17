"""
Operation Declaration Schema
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2015-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# logging support
import logging
logger = logging.getLogger(__name__)

# Marshmallow support
from marshmallow import fields, post_load
from tosca_core.schema.named_object_map import NamedObjectMap

# Schemas used by CapabilityDeclarationSchema
from tosca_core.schema.base import BaseSchema
from .property_declaration import (
    InputDeclarationSchema,  create_input_declaration,
    OutputDeclarationSchema, create_output_declaration)
from .operation_implementation import OperationImplementationSchema

# Object class for this schema
from tosca_core.models.operation_declaration import ToscaOperationDeclaration


def create_operation_declaration(**kwargs) -> ToscaOperationDeclaration:
    return ToscaOperationDeclaration(role='OPERATION', **kwargs)

def create_notification_declaration(**kwargs) -> ToscaOperationDeclaration:
    return ToscaOperationDeclaration(role='NOTIFICATION', **kwargs)


class OperationDeclarationSchema(BaseSchema):
    implementation = fields.Nested(OperationImplementationSchema)
    inputs =         NamedObjectMap(fields.Nested(InputDeclarationSchema,
                                                  load_default=create_input_declaration),
                                    allow_none=True)
    outputs =        NamedObjectMap(fields.Nested(OutputDeclarationSchema,
                                                  load_default=create_output_declaration),
                                    allow_none=True)

    # default field used for short-hand grammar
    default_data_key = 'implementation'

    @post_load
    def make_object(self, data: dict, **kwargs) -> ToscaOperationDeclaration:
        return create_operation_declaration(**data)


class NotificationDeclarationSchema(OperationDeclarationSchema):
    @post_load
    def make_object(self, data: dict, **kwargs) -> ToscaOperationDeclaration:
        return create_notification_declaration(**data)
    
