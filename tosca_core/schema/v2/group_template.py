"""
Group Schema
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2015-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger = logging.getLogger(__name__)

# Marshmallow support
from marshmallow import fields, post_load

# Schemas used by GroupTemplateSchema
from .template import TemplateSchema

# Object class for this schema
from tosca_core.models.group_template import ToscaGroupTemplate


def create_group_template(**kwargs) -> ToscaGroupTemplate:
    return ToscaGroupTemplate(**kwargs)

class GroupTemplateSchema(TemplateSchema):
    type = fields.Str()
    members = fields.List(fields.Str())
    policies = fields.Raw()

    @post_load
    def make_object(self, data: dict, **kwargs) -> ToscaGroupTemplate:
        return create_group_template(**data)
