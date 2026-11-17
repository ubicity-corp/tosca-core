"""
Requirement Schema
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2015-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# logging support
import logging
logger = logging.getLogger(__name__)

# URLs to REST resources
from tosca_core.schema.url import url_for

# Marshmallow support
from marshmallow import fields, post_load, missing

# Type hints
from typing import Any

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
    node_url = fields.Method('get_node_url')
    relationship = fields.Nested(ManagedTemplateSchema)
    capability = fields.Str()
    occurrences = fields.List(fields.Raw())
    node_filter = fields.Nested(NodeFilterSchema)

    # default field used for short-hand grammar
    default_data_key = 'node'


    def get_node_url(self, obj: Any) -> Any:
        url = None
        if obj._target_node_type:
            url = url_for('type', type_type='node', type_id=obj._target_node_type_id)
        elif obj._target_node:
            url = url_for('node', node_id=obj._target_node_id)
        return url if url is not None else missing

    @post_load
    def make_object(self, data: dict, **kwargs) -> ToscaRelationshipTemplate:
        return ToscaRelationshipTemplate(**data)
