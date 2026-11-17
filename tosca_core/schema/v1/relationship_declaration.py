"""
Relationship Declaration Schema.
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
from .managed_declaration import (
    ManagedDeclarationSchema, create_managed_declaration)
from .node_filter import NodeFilterSchema

# Object class for this schema
from tosca_core.models.relationship_declaration import ToscaRelationshipDeclaration


def create_relationship_declaration(**kwargs) -> ToscaRelationshipDeclaration:
    return ToscaRelationshipDeclaration(**kwargs)


class RelationshipDeclarationSchema(BaseSchema):
    """Relationship Declaration. In the TOSCA specification, this is
    referred to as a 'requirement definition'. We use the name
    'relationship declaration' for consistency with the Ubicity naming
    scheme.
    """

    relationship =   fields.Nested(ManagedDeclarationSchema, allow_none=True)
    node =           fields.Str(allow_none=True)
    node_url =       fields.Method('get_node_url')
    capability =     fields.Str(allow_none=True)
    capability_url = fields.Method('get_capability_url')
    count_range =    fields.List(fields.Raw(), data_key='occurrences')
    node_filter =    fields.Nested(NodeFilterSchema)

    # default field used for short-hand grammar
    default_data_key = 'capability'

    def get_node_url(self, obj: Any) -> Any:
        url = None
        if obj._target_node_type:
            url = url_for('type', type_type='node', type_id=obj._target_node_type_id)
        return url if url is not None else missing

    def get_capability_url(self, obj: Any) -> Any:
        url = None
        if obj._target_capability_type:
            url = url_for('type', type_type='capability', type_id=obj._target_capability_type_id)
        return url if url is not None else missing

    @post_load
    def make_object(self, data: dict, **kwargs) -> ToscaRelationshipDeclaration:
        return create_relationship_declaration(**data)
