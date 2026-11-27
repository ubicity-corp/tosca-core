"""
Node Schema
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

# Schemas used by NodeTemplateSchema
from .managed_template import ManagedTemplateSchema
from .capability_template import CapabilityTemplateSchema, create_capability_template
from .artifact_template import ArtifactTemplateSchema, create_artifact_template
from .node_filter import NodeFilterSchema
from .requirement import RequirementSchema, create_requirement

# Object class for this schema
from tosca_core.models.node_template import ToscaNodeTemplate

def create_node_template(**kwargs) -> ToscaNodeTemplate:
    return ToscaNodeTemplate(**kwargs)


class NodeTemplateSchema(ManagedTemplateSchema):
    requirements = NamedObjectList(fields.Nested(RequirementSchema,
                                                 load_default=create_requirement),
                                   allow_none=True)
    capabilities = NamedObjectMap(fields.Nested(CapabilityTemplateSchema,
                                                load_default=create_capability_template),
                                  allow_none=True)
    attributes =   fields.Dict()
    artifacts =    NamedObjectMap(fields.Nested(ArtifactTemplateSchema,
                                                load_default=create_artifact_template),
                                  allow_none=True)
    node_filter =  fields.Nested(NodeFilterSchema)
    count =        fields.Raw()    # 'Count' value can be an integer or a function.
    directives =   fields.List(fields.Str())
    
    @post_load
    def make_object(self, data: dict, **kwargs) -> ToscaNodeTemplate:
        return create_node_template(**data)
