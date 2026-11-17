"""
Node Filter Schema
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
from tosca_core.schema.named_object_list import NamedObjectList
from tosca_core.schema.url_field import URLField

# Schemas used by NodeFilterSchema
from tosca_core.schema.base import BaseSchema
from .constraint import ConstraintSchema


class CapabilityFilterSchema(BaseSchema):
    properties = NamedObjectList(fields.Nested(ConstraintSchema))

class NodeFilterSchema(BaseSchema):
    node = fields.Str(dump_only=True)
    type_url = URLField("type", type_type='<type_class>', type_id='<_type_id>')
    properties = NamedObjectList(fields.Nested(ConstraintSchema))
    capabilities = NamedObjectList(fields.Nested(CapabilityFilterSchema))
