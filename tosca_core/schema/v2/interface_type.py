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

# Schemas used by GroupTypeSchema
from .type import TypeSchema
from .property_declaration import (
    InputDeclarationSchema,
    OutputDeclarationSchema)
from .operation_declaration import (
    OperationDeclarationSchema,
    NotificationDeclarationSchema)

# Object class for this schema
from tosca_core.models.interface_type import ToscaInterfaceType


def create_interface_type(**kwargs) -> ToscaInterfaceType:
    return ToscaInterfaceType(**kwargs)


class InterfaceTypeSchema(TypeSchema):
    inputs =        NamedObjectMap(fields.Nested(InputDeclarationSchema))
    outputs =       NamedObjectMap(fields.Nested(OutputDeclarationSchema))
    operations =    NamedObjectMap(fields.Nested(OperationDeclarationSchema))
    notifications = NamedObjectMap(fields.Nested(NotificationDeclarationSchema))

    @post_load
    def make_object(self, data: dict, **kwargs) -> ToscaInterfaceType:
        return create_interface_type(**data)


# Global interface type schema
interface_type_schema = InterfaceTypeSchema()
interface_types_schema = InterfaceTypeSchema(many=True)
