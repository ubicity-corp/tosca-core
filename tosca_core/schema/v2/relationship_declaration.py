"""
Relationship Declaration Schema
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
from .managed_declaration import (
    ManagedDeclarationSchema)

# Object class for this schema
from tosca_core.models.relationship_declaration import ToscaRelationshipDeclaration


def create_relationship_declaration(**kwargs) -> ToscaRelationshipDeclaration:
    return ToscaRelationshipDeclaration(**kwargs)


class RelationshipDeclarationSchema(BaseSchema):
    """Relationship Declaration. In the TOSCA specification, this is
    referred to as a 'requirement definition'. We use the name
    'relationship declaration' for consistency reasons
    """

    relationship =   fields.Nested(ManagedDeclarationSchema, allow_none=True)
    node =           fields.Str(allow_none=True)
    capability =     fields.Str(allow_none=True)
    count_range =    fields.List(fields.Raw())
    node_filter =    fields.Dict()  
    allocation =     fields.Dict()

    # default field used for short-hand grammar
    default_data_key = 'capability'

    @post_load
    def make_object(self, data: dict, **kwargs) -> ToscaRelationshipDeclaration:
        return create_relationship_declaration(**data)
