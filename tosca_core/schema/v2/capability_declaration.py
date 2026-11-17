"""
Capability Declaration Schema
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
from .declaration import DeclarationSchema
from .property_declaration import (
    PropertyDeclarationSchema)
from .property_declaration import (
    AttributeDeclarationSchema)

# Object class for this schema
from tosca_core.models.capability_declaration import ToscaCapabilityDeclaration


def create_capability_declaration(**kwargs) -> ToscaCapabilityDeclaration:
    return ToscaCapabilityDeclaration(**kwargs)


class CapabilityDeclarationSchema(DeclarationSchema):
    properties =               NamedObjectMap(fields.Nested(PropertyDeclarationSchema))
    attributes =               NamedObjectMap(fields.Nested(AttributeDeclarationSchema))
    valid_source_node_types =  fields.List(fields.Str())
    valid_relationship_types = fields.List(fields.Str())

    # default field used for short-hand grammar
    default_data_key = 'type'

    @post_load
    def make_object(self, data: dict, **kwargs) -> ToscaCapabilityDeclaration:
        return create_capability_declaration(**data)
