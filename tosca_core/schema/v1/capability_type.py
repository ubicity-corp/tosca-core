"""
Capability Type Schema
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

# Schemas used by GroupTypeSchema
from .type import TypeSchema
from .property_declaration import (
    AttributeDeclarationSchema, create_attribute_declaration)

# Object class for this schema
from tosca_core.models.capability_type import ToscaCapabilityType


def create_capability_type(**kwargs) -> ToscaCapabilityType:
    return ToscaCapabilityType(**kwargs)


class CapabilityTypeSchema(TypeSchema):
    attributes =         NamedObjectMap(fields.Nested(AttributeDeclarationSchema,
                                                      load_default=create_attribute_declaration),
                                        allow_none=True)
    valid_source_node_types = fields.List(fields.Str(), data_key='valid_source_types')

    @post_load
    def make_object(self, data: dict, **kwargs) -> ToscaCapabilityType:
        return create_capability_type(**data)


# Global capability type schema
capability_type_schema = CapabilityTypeSchema()
capability_types_schema = CapabilityTypeSchema(many=True)
