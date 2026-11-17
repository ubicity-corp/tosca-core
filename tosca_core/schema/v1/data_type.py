"""
DataTypeSchema class used by Marshmallow
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2015-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger = logging.getLogger(__name__)

# Marshmallow support
from marshmallow import fields, post_load

# Schemas used by DataTypeSchema
from .type import TypeSchema
from .constraint import ConstraintSchema

# Object class for this schema
from tosca_core.models.data_type import ToscaDataType


def create_data_type(**kwargs) -> ToscaDataType:
    return ToscaDataType(**kwargs)


class DataTypeSchema(TypeSchema):
    constraints = fields.List(fields.Nested(ConstraintSchema))
    entry_schema = fields.Nested('EntrySchemaSchemaV1')
    key_schema = fields.Nested('EntrySchemaSchemaV1')

    @post_load
    def make_object(self, data: dict, **kwargs) -> ToscaDataType:
        return create_data_type(**data)


# Global data type schema
data_type_schema = DataTypeSchema()
data_types_schema = DataTypeSchema(many=True)
