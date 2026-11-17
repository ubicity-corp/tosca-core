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
    AttributeDeclarationSchema)
from .interface_declaration import (
    InterfaceDeclarationSchema)


class ManagedTypeSchema(TypeSchema):
    attributes = NamedObjectMap(fields.Nested(AttributeDeclarationSchema))
    interfaces = NamedObjectMap(fields.Nested(InterfaceDeclarationSchema))
