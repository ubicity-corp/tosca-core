"""
Profile Schema class used by Marshmallow
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

# Schemas on which this schema depends
from tosca_core.schema.base import BaseSchema
from tosca_core.schema.url_field import URLField
from tosca_core.schema.v2.repository import RepositorySchema

from .node_type import NodeTypeSchema
from .data_type import DataTypeSchema
from .group_type import GroupTypeSchema
from .relationship_type import RelationshipTypeSchema
from .capability_type import CapabilityTypeSchema
from .artifact_type import ArtifactTypeSchema
from .interface_type import InterfaceTypeSchema
from .policy_type import PolicyTypeSchema
from .function_declaration import FunctionDeclarationSchema
from .service_template import ServiceTemplateSchema

class ProfileSchema(BaseSchema):
    id = fields.Integer(dump_only=True)
    url = URLField('profile', profile_id='<id>')
    creation_time = fields.DateTime(dump_only=True)
    name = fields.Str()
    service = fields.Nested(ServiceTemplateSchema, data_key='service_template', dump_only=True)

class ProfileDetailSchema(ProfileSchema):
    tosca_file_path = fields.Str(dump_only=True)
    repository = fields.Nested(RepositorySchema, dump_only=True)
    node_types = NamedObjectMap(fields.Nested(NodeTypeSchema))
    data_types = NamedObjectMap(fields.Nested(DataTypeSchema))
    group_types = NamedObjectMap(fields.Nested(GroupTypeSchema))
    relationship_types = NamedObjectMap(fields.Nested(RelationshipTypeSchema))
    capability_types = NamedObjectMap(fields.Nested(CapabilityTypeSchema))
    artifact_types = NamedObjectMap(fields.Nested(ArtifactTypeSchema))
    interface_types = NamedObjectMap(fields.Nested(InterfaceTypeSchema))
    policy_types = NamedObjectMap(fields.Nested(PolicyTypeSchema))
    functions = NamedObjectMap(fields.Nested(FunctionDeclarationSchema))
