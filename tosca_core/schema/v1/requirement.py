"""
Requirement Schema
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2015-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# logging support
import logging
logger = logging.getLogger(__name__)

# Marshmallow support
from marshmallow import fields, post_load

# Schemas used by CapabilityDeclarationSchema
from tosca_core.schema.base import BaseSchema
from .managed_template import ManagedTemplateSchema
from .node_filter import NodeFilterSchema

# Object class for this schema
from tosca_core.models.relationship_template import ToscaRelationshipTemplate


def create_requirement(**kwargs) -> ToscaRelationshipTemplate:
    return ToscaRelationshipTemplate(**kwargs)


class RequirementSchema(BaseSchema):

    id = fields.Integer(dump_only=True)
    name = fields.Str()
    node = fields.Str()
    relationship = fields.Nested(ManagedTemplateSchema)
    capability = fields.Str()
    occurrences = fields.List(fields.Raw())
    node_filter = fields.Nested(NodeFilterSchema)

    # default field used for short-hand grammar
    default_data_key = 'node'


    @post_load
    def make_object(self, data: dict, **kwargs) -> ToscaRelationshipTemplate:
        return ToscaRelationshipTemplate(**data)
