"""
TOSCA File v2 Schema class
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
from .node_type import NodeTypeSchema
from .data_type import DataTypeSchema
from .group_type import GroupTypeSchema
from .service_template import ServiceTemplateDetailSchema
from .relationship_type import RelationshipTypeSchema
from .capability_type import CapabilityTypeSchema
from .artifact_type import ArtifactTypeSchema
from .interface_type import InterfaceTypeSchema
from .policy_type import PolicyTypeSchema
from .function_declaration import FunctionDeclarationSchema

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

    # TOSCA v2.x supports a 'profile' keyword.
    profile = fields.Str()

    # An implementing file names the profile it adds implementations
    # to (profile name and version), and declares nothing of its own.
    implements = fields.Str()

    # Repository definitions
    repositories = NamedObjectMap(fields.Nested(RepositorySchema))

    # Type definitions
    node_types = NamedObjectMap(
        fields.Nested(NodeTypeSchema))
    data_types = NamedObjectMap(
        fields.Nested(DataTypeSchema))
    group_types = NamedObjectMap(
        fields.Nested(GroupTypeSchema))
    relationship_types = NamedObjectMap(
        fields.Nested(RelationshipTypeSchema))
    capability_types = NamedObjectMap(
        fields.Nested(CapabilityTypeSchema))
    artifact_types = NamedObjectMap(
        fields.Nested(ArtifactTypeSchema))
    interface_types = NamedObjectMap(
        fields.Nested(InterfaceTypeSchema))
    policy_types = NamedObjectMap(
        fields.Nested(PolicyTypeSchema))
    functions = NamedObjectMap(
        fields.Nested(FunctionDeclarationSchema))

    # Topology template
    service_template = fields.Nested(ServiceTemplateDetailSchema)

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
    
