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
    InputDeclarationSchema, create_input_declaration,
    ServiceOutputDeclarationSchema, create_output_declaration)
from .node_template import (
    NodeTemplateSchema, create_node_template)
from .relationship_template import (
    RelationshipTemplateSchema, create_relationship_template)
from .substitution_mappings import SubstitutionMappingsSchema
from .group_template import (
    GroupTemplateSchema, create_group_template)
from .workflow import (
    WorkflowSchema, create_workflow_template)
from .policy_template import (
    PolicyTemplateSchema, create_policy_template)

# Object class for this schema
from tosca_core.models.service_template import ToscaServiceTemplate


class ServiceTemplateSchema(BaseSchema):

    id =                     fields.Integer(dump_only=True)
    inputs =                 NamedObjectMap(fields.Nested(InputDeclarationSchema,
                                                          load_default=create_input_declaration),
                                            allow_none=True)
    outputs =                NamedObjectMap(fields.Nested(ServiceOutputDeclarationSchema,
                                                          load_default=create_output_declaration),
                                            allow_none=True)
    node_templates =         NamedObjectMap(fields.Nested(NodeTemplateSchema,
                                                          load_default=create_node_template,
                                                          allow_none=True),
                                            allow_none=True)
    relationship_templates = NamedObjectMap(fields.Nested(RelationshipTemplateSchema,
                                                          load_default=create_relationship_template),
                                            allow_none=True)
    groups =                 NamedObjectMap(fields.Nested(GroupTemplateSchema,
                                                          load_default=create_group_template),
                                            allow_none=True)
    workflows =              NamedObjectMap(fields.Nested(WorkflowSchema,
                                                          load_default=create_workflow_template),
                                            allow_none=True)
    substitution_mappings =  fields.Nested(SubstitutionMappingsSchema)
    policies =               NamedObjectList(fields.Nested(PolicyTemplateSchema,
                                                           load_default=create_policy_template),
                                             allow_none=True)

    @post_load
    def make_object(self, data: dict, **kwargs) -> ToscaServiceTemplate:
        return ToscaServiceTemplate(**data)
