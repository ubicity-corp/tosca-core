"""
Node Type Schema
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2015-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# logging support
import logging
logger = logging.getLogger(__name__)

# Marshmallow support
from marshmallow import fields, post_load
from tosca_core.schema.named_object_map import NamedObjectMap
from tosca_core.schema.named_object_list import NamedObjectList

# Schemas used by GroupTypeSchema
from .managed_type import ManagedTypeSchema
from .capability_declaration import (
    CapabilityDeclarationSchema)
from .relationship_declaration import (
    RelationshipDeclarationSchema)
from .artifact_template import (
    ArtifactTemplateSchema)

# Object class for this schema
from tosca_core.models.node_type import ToscaNodeType


def create_node_type(**kwargs) -> ToscaNodeType:
    return ToscaNodeType(**kwargs)


class NodeTypeSchema(ManagedTypeSchema):
    capabilities = NamedObjectMap(fields.Nested(CapabilityDeclarationSchema))
    requirements = NamedObjectList(fields.Nested(RelationshipDeclarationSchema))
    artifacts =    NamedObjectMap(fields.Nested(ArtifactTemplateSchema))

    @post_load
    def make_object(self, data: dict, **kwargs) -> ToscaNodeType:
        return create_node_type(**data)


# Global node type schema
node_type_schema = NodeTypeSchema()
node_types_schema = NodeTypeSchema(many=True)
