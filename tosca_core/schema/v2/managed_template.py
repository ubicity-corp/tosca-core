"""
Managed Instance Schema
"""
from __future__ import annotations

__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2015-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger = logging.getLogger(__name__)

# Marshmallow support
from marshmallow import fields
from tosca_core.schema.named_object_map import NamedObjectMap
from tosca_core.schema.url_field import URLField

# Schemas used by ManagedTemplateSchema
from .template import TemplateSchema
from .interface_template import (
    InterfaceTemplateSchema)


class ManagedTemplateSchema(TemplateSchema):
    interfaces = NamedObjectMap(fields.Nested(InterfaceTemplateSchema))
    attributes = fields.Dict()
    directives = fields.List(fields.Str())
    type =       fields.Str()
    type_url =   URLField("type", type_type='<type_class>', type_id='<_type_id>')
    copy =       fields.Str(load_only=True)

    # default field used for short-hand grammar
    default_data_key: str = 'type'
