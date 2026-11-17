"""
Group Type Schema
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2015-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# logging support
import logging
logger = logging.getLogger(__name__)

# Marshmallow support
from marshmallow import fields, post_load

# Schemas used by GroupTypeSchema
from .type import TypeSchema

# Object class for this schema
from tosca_core.models.group_type import ToscaGroupType


def create_group_type(**kwargs) -> ToscaGroupType:
    return ToscaGroupType(**kwargs)


class GroupTypeSchema(TypeSchema):
    members = fields.List(fields.Str())

    @post_load
    def make_object(self, data: dict, **kwargs) -> ToscaGroupType:
        return create_group_type(**data)


# Global group type schema
group_type_schema = GroupTypeSchema()
group_types_schema = GroupTypeSchema(many=True)
