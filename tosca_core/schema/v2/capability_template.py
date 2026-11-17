"""
Capability Schema
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2015-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger = logging.getLogger(__name__)

# Marshmallow support
from marshmallow import fields, post_load

# Schemas used by CapabilityTemplateSchema
from .template import TemplateSchema

# Object class for this schema
from tosca_core.models.capability_template import ToscaCapabilityTemplate


def create_capability_template(**kwargs) -> ToscaCapabilityTemplate:
    return ToscaCapabilityTemplate(**kwargs)


class CapabilityTemplateSchema(TemplateSchema):

    attributes = fields.Dict()
    directives = fields.List(fields.Str())

    @post_load
    def make_object(self, data: dict, **kwargs) -> ToscaCapabilityTemplate:
        return create_capability_template(**data)
