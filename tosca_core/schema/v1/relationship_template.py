"""
Relationship Schema
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2015-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger = logging.getLogger(__name__)

# Marshmallow support
from marshmallow import post_load

# Schemas used by RelationshipTemplateSchema
from .managed_template import ManagedTemplateSchema

# Object class for this schema
from tosca_core.models.relationship_template import ToscaRelationshipTemplate


def create_relationship_template(**kwargs) -> ToscaRelationshipTemplate:
    return ToscaRelationshipTemplate(**kwargs)


class RelationshipTemplateSchema(ManagedTemplateSchema):
    # Need to deal with the "not a dict" scenario where the value
    # indicates the type of the relationship declaration

    @post_load
    def make_object(self, data: dict, **kwargs) -> ToscaRelationshipTemplate:
        return create_relationship_template(**data)
