"""
Node Template Schema
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
from .capability_template import CapabilityTemplateSchema
from .artifact_template import ArtifactTemplateSchema
from .requirement import RequirementSchema

# Object class for this schema
from tosca_core.models.node_template import ToscaNodeTemplate

def create_node_template(**kwargs) -> ToscaNodeTemplate:
    return ToscaNodeTemplate(**kwargs)


class NodeTemplateSchema(ManagedTemplateSchema):
    requirements = NamedObjectList(fields.Nested(RequirementSchema))
    capabilities = NamedObjectMap(fields.Nested(CapabilityTemplateSchema))
    artifacts =    NamedObjectMap(fields.Nested(ArtifactTemplateSchema))
    count =        fields.Raw()    # 'Count' value can be an integer or a function.
    node_filter =  fields.Dict() 
    directives =   fields.List(fields.Str())
    
    @post_load
    def make_object(self, data: dict, **kwargs) -> ToscaNodeTemplate:
        return create_node_template(**data)
