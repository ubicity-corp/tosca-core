"""
Managed Type Schema
"""
from __future__ import annotations

__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2015-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# logging support
import logging
logger = logging.getLogger(__name__)

# Marshmallow support
from marshmallow import fields
from tosca_core.schema.named_object_map import NamedObjectMap

# Schemas used by GroupTypeSchema
from .type import TypeSchema
from .property_declaration import (
    AttributeDeclarationSchema, create_attribute_declaration)
from .interface_declaration import (
    InterfaceDeclarationSchema, create_interface_declaration)


class ManagedTypeSchema(TypeSchema):
    attributes = NamedObjectMap(fields.Nested(AttributeDeclarationSchema,
                                              load_default=create_attribute_declaration),
                                allow_none=True)
    interfaces = NamedObjectMap(fields.Nested(InterfaceDeclarationSchema,
                                              load_default=create_interface_declaration),
                                allow_none=True)
