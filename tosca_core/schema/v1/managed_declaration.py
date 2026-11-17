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
from .interface_declaration import (
    InterfaceDeclarationSchema, create_interface_declaration)


def create_managed_declaration(**kwargs) -> Any:
    return ToscaManagedDeclaration(**kwargs)


class ManagedDeclarationSchema(DeclarationSchema):
    interfaces = NamedObjectMap(fields.Nested(InterfaceDeclarationSchema,
                                              load_default=create_interface_declaration),
                                allow_none=True)

    # default field used for short-hand grammar
    default_data_key = 'type'
