"""
Interface Type Schema
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2015-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# logging support
import logging
logger = logging.getLogger(__name__)

# Support for checking if we have a Map

# Marshmallow support
from marshmallow import fields, post_load
from tosca_core.schema.named_object_map import NamedObjectMap
from tosca_core.schema.unknown_field_mixin import UnknownFieldMixin

# Schemas used by GroupTypeSchema
from .type import TypeSchema
from .property_declaration import (
    InputDeclarationSchema, create_input_declaration,
    OutputDeclarationSchema, create_output_declaration)
from .operation_declaration import (
    OperationDeclarationSchema, create_operation_declaration,
    NotificationDeclarationSchema, create_notification_declaration)

# Object class for this schema
from tosca_core.models.interface_type import ToscaInterfaceType


def create_interface_type(**kwargs) -> ToscaInterfaceType:
    return ToscaInterfaceType(**kwargs)


class InterfaceTypeSchema(UnknownFieldMixin, TypeSchema):
    inputs =        NamedObjectMap(fields.Nested(InputDeclarationSchema,
                                                 load_default=create_input_declaration),
                                   allow_none=True)
    outputs =       NamedObjectMap(fields.Nested(OutputDeclarationSchema,
                                                 load_default=create_output_declaration),
                                   allow_none=True)
    operations =    NamedObjectMap(fields.Nested(OperationDeclarationSchema,
                                                 load_default=create_operation_declaration),
                                   allow_none=True)
    notifications = NamedObjectMap(fields.Nested(NotificationDeclarationSchema,
                                                 load_default=create_notification_declaration),
                                   allow_none=True)

    unknown_field_map = 'operations'

    @post_load
    def make_object(self, data: dict, **kwargs) -> ToscaInterfaceType:
        return create_interface_type(**data)


# Global interface type schema
interface_type_schema = InterfaceTypeSchema()
interface_types_schema = InterfaceTypeSchema(many=True)
