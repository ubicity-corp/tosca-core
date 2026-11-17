"""
Policy Schema
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2018-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger = logging.getLogger(__name__)

# Marshmallow support
from marshmallow import fields, post_load
from tosca_core.schema.named_object_map import NamedObjectMap

# Schemas used by PolicyTemplateSchema
from .template import TemplateSchema
from .trigger import TriggerSchema
from tosca_core.schema.url_field import URLField

# Object class for this schema
from tosca_core.models.policy_template import ToscaPolicyTemplate


def create_policy_template(**kwargs) -> ToscaPolicyTemplate:
    return ToscaPolicyTemplate(**kwargs)


class PolicyTemplateSchema(TemplateSchema):

    type = fields.Str()
    type_url = URLField("type", type_type='<type_class>', type_id='<_type_id>')
    targets = fields.List(fields.Str())
    triggers = NamedObjectMap(fields.Nested(TriggerSchema))

    @post_load
    def make_object(self, data: dict, **kwargs) -> ToscaPolicyTemplate:
        return create_policy_template(**data)
