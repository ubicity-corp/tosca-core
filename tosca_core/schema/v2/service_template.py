"""
Topology Schema classes
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2015-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger = logging.getLogger(__name__)

# Marshmallow support
from marshmallow import fields, post_load
from tosca_core.schema.named_object_map import NamedObjectMap
from tosca_core.schema.named_object_list import NamedObjectList

# Schemas used by ServiceTemplateSchema
from tosca_core.schema.base import BaseSchema
from .property_declaration import (
    InputDeclarationSchema,
    ServiceOutputDeclarationSchema)
from .node_template import (
    NodeTemplateSchema)
from .relationship_template import (
    RelationshipTemplateSchema)
from .substitution_mappings import SubstitutionMappingsSchema
from .group_template import (
    GroupTemplateSchema)
from .workflow import (
    WorkflowSchema)
from .policy_template import (
    PolicyTemplateSchema)

# Object class for this schema
from tosca_core.models.service_template import ToscaServiceTemplate

class ServiceTemplateSchema(BaseSchema):
    id = fields.Integer(dump_only=True)
    name = fields.Str(dump_only=True)
    creation_time = fields.DateTime(dump_only=True)

class ServiceTemplateDetailSchema(ServiceTemplateSchema):
    id =                     fields.Integer(dump_only=True)
    inputs =                 NamedObjectMap(fields.Nested(InputDeclarationSchema))
    outputs =                NamedObjectMap(fields.Nested(ServiceOutputDeclarationSchema))
    node_templates =         NamedObjectMap(fields.Nested(NodeTemplateSchema), required=True)
    relationship_templates = NamedObjectMap(fields.Nested(RelationshipTemplateSchema))
    groups =                 NamedObjectMap(fields.Nested(GroupTemplateSchema))
    workflows =              NamedObjectMap(fields.Nested(WorkflowSchema))
    substitution_mappings =  fields.Nested(SubstitutionMappingsSchema)
    policies =               NamedObjectList(fields.Nested(PolicyTemplateSchema))

    @post_load
    def make_object(self, data: dict, **kwargs) -> ToscaServiceTemplate:
        return ToscaServiceTemplate(**data)
