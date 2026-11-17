"""
Type Schema classes
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2015-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# logging support
import logging
logger = logging.getLogger(__name__)

# Marshmallow support
from marshmallow import fields, missing

# Type hints
from typing import Any
from tosca_core.schema.named_object_map import NamedObjectMap
from tosca_core.schema.url_field import URLField

# Schemas used by TypeSchema
from tosca_core.schema.base import BaseSchema
from .property_declaration import (
    PropertyDeclarationSchema, create_property_declaration)


class TypeSchema(BaseSchema):

    type_class =   fields.Str(dump_only=True)
    version =      fields.Str()
    id =           fields.Integer(dump_only=True)
    name =         fields.Str()
    short_name =   fields.Str(dump_only=True)
    url =          URLField('type', type_type='<type_class>', type_id='<id>')
    derived_from = fields.Str(load_only=True)
    parent =       fields.Method('get_parent_name')
    parent_url =   URLField('type', type_type='<type_class>', type_id='<parent_id>')
    properties =   NamedObjectMap(fields.Nested(PropertyDeclarationSchema,
                                                load_default=create_property_declaration),
                                  allow_none=True)

    def get_parent_name(self, obj: Any) -> Any:
        try:
            return obj.parent.name
        except AttributeError:
            return missing
