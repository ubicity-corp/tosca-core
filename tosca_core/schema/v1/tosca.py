"""
TOSCA File v1.x schema
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2015-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger = logging.getLogger(__name__)

# Marshmallow support
from marshmallow import fields, post_load, validates, ValidationError
from tosca_core.schema.named_object_map import NamedObjectMap

# Schema utilities
from tosca_core.schema.base import BaseSchema

# Schemas used by ToscaSchema
from .imprt import ImportSchema
from .repository import RepositorySchema
from .node_type import NodeTypeSchema, create_node_type
from .data_type import DataTypeSchema, create_data_type
from .group_type import GroupTypeSchema, create_group_type
from .service_template import ServiceTemplateSchema
from .relationship_type import RelationshipTypeSchema, create_relationship_type
from .capability_type import CapabilityTypeSchema, create_capability_type
from .artifact_type import ArtifactTypeSchema, create_artifact_type
from .interface_type import InterfaceTypeSchema, create_interface_type
from .policy_type import PolicyTypeSchema, create_policy_type

# Object class for this schema
from tosca_core.models.tosca_data import ToscaData


class ToscaSchema(BaseSchema):
    """Top-level schema for a TOSCA file"""
    
    # TOSCA version
    tosca_definitions_version = fields.Str()

    # Anchors
    dsl_definitions = fields.Dict()

    # v1-specific imports
    imports = fields.List(fields.Nested(ImportSchema))

    # TOSCA v1.x supports a 'namespace' keyword instead of a 'profile'
    # keyword.
    profile = fields.Str(data_key='namespace')

    # Repository definitions
    repositories = NamedObjectMap(fields.Nested(RepositorySchema))

    # Type definitions
    node_types = NamedObjectMap(
        fields.Nested(NodeTypeSchema, load_default=create_node_type),
        allow_none=True)
    data_types = NamedObjectMap(
        fields.Nested(DataTypeSchema, load_default=create_data_type),
        allow_none=True)
    group_types = NamedObjectMap(
        fields.Nested(GroupTypeSchema, load_default=create_group_type),
        allow_none=True)
    relationship_types = NamedObjectMap(
        fields.Nested(RelationshipTypeSchema, load_default=create_relationship_type),
        allow_none=True)
    capability_types = NamedObjectMap(
        fields.Nested(CapabilityTypeSchema, load_default=create_capability_type),
        allow_none=True)
    artifact_types = NamedObjectMap(
        fields.Nested(ArtifactTypeSchema, load_default=create_artifact_type),
        allow_none=True)
    interface_types = NamedObjectMap(
        fields.Nested(InterfaceTypeSchema, load_default=create_interface_type),
        allow_none=True)
    policy_types = NamedObjectMap(
        fields.Nested(PolicyTypeSchema, load_default=create_policy_type),
        allow_none=True)

    # Topology template
    service_template = fields.Nested(ServiceTemplateSchema, data_key='topology_template')

    @validates('dsl_definitions')
    def validate_dsl_definitions(self, value, **kwargs) -> None:
        """Reject dsl_definitions entries that aren't a YAML anchor.
        Each entry is meant to anchor reusable YAML content; an entry
        with no value (or a bare value with no '&anchor' marker) has
        nothing to anchor and is almost certainly a typo.
        """
        errors = {}
        for name, v in (value or {}).items():
            if v is None:
                errors[name] = 'must not be empty'
                continue
            anchor = getattr(v, 'anchor', None)
            if not getattr(anchor, 'value', None):
                errors[name] = 'must be a YAML anchor'
        if errors:
            raise ValidationError(errors)

    @post_load
    def make_object(self, data: dict, **kwargs) -> ToscaData:
        return ToscaData(**data)
    
