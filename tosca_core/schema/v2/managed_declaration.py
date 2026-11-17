"""
Managed Declaration Schema
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2017-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# logging support
import logging
logger = logging.getLogger(__name__)

# Marshmallow support
from marshmallow import fields

# Type hints
from typing import Any
from tosca_core.schema.named_object_map import NamedObjectMap

# Schemas used by RelationshipDeclarationSchema
from .declaration import DeclarationSchema
from .property_declaration import (
    PropertyDeclarationSchema)
from .property_declaration import (
    AttributeDeclarationSchema)
from .interface_declaration import (
    InterfaceDeclarationSchema)


def create_managed_declaration(**kwargs) -> Any:
    return ToscaManagedDeclaration(**kwargs)


class ManagedDeclarationSchema(DeclarationSchema):
    properties = NamedObjectMap(fields.Nested(PropertyDeclarationSchema))
    attributes = NamedObjectMap(fields.Nested(AttributeDeclarationSchema))
    interfaces = NamedObjectMap(fields.Nested(InterfaceDeclarationSchema))

    # default field used for short-hand grammar
    default_data_key = 'type'
