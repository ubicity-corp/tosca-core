"""
Policy Type Schema
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2018-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# logging support
import logging
logger = logging.getLogger(__name__)

# Marshmallow support
from marshmallow import fields, post_load
from tosca_core.schema.named_object_map import NamedObjectMap

# Schemas used by GroupTypeSchema
from .type import TypeSchema
from .trigger import TriggerSchema

# Object class for this schema
from tosca_core.models.policy_type import ToscaPolicyType


def create_policy_type(**kwargs) -> ToscaPolicyType:
    return ToscaPolicyType(**kwargs)


class PolicyTypeSchema(TypeSchema):
    targets =  fields.List(fields.Str())
    triggers = NamedObjectMap(fields.Nested(TriggerSchema))

    @post_load
    def make_object(self, data: dict, **kwargs) -> ToscaPolicyType:
        return create_policy_type(**data)


# Global policy type schema
policy_type_schema = PolicyTypeSchema()
policy_types_schema = PolicyTypeSchema(many=True)
