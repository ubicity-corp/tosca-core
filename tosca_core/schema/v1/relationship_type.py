"""
Relationship Type Schema
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2015-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# logging support
import logging
logger = logging.getLogger(__name__)

# Marshmallow support
from marshmallow import ValidationError, fields, post_load, pre_load

# Schemas used by GroupTypeSchema
from .managed_type import ManagedTypeSchema

# Object class for this schema
from tosca_core.models.relationship_type import ToscaRelationshipType


def create_relationship_type(**kwargs) -> ToscaRelationshipType:
    return ToscaRelationshipType(**kwargs)


class RelationshipTypeSchema(ManagedTypeSchema):
    valid_capability_types = fields.List(fields.Str(), data_key='valid_target_types')

    @pre_load
    def refuse_kind(self, data, **kwargs):
        """'kind' was a Ubicity extension, not TOSCA; a relationship type
        states its kind in metadata, as the TOSCA community does"""
        if isinstance(data, dict) and 'kind' in data:
            raise ValidationError(
                {'kind': "not a TOSCA keyname: state the kind in metadata, "
                         "as 'metadata: {relationship-kind: " + str(data['kind']) + "}'"})
        return data

    @post_load
    def make_object(self, data: dict, **kwargs) -> ToscaRelationshipType:
        return create_relationship_type(**data)


# Global relationship type schema
relationship_type_schema = RelationshipTypeSchema()
relationship_types_schema = RelationshipTypeSchema(many=True)
