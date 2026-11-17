"""
Trigger Schema
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2018-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger = logging.getLogger(__name__)

# Marshmallow support
from marshmallow import Schema, fields, pre_load

# Type hints
from typing import Any

# Support for checking whether condition data to be loaded use
# short-hand notation
import collections.abc

# Schemas on which this schema depends
from tosca_core.schema.base import BaseSchema
from .condition import ConditionSchema
from .activity import ActivitySchema


class TriggerConditionSchema(BaseSchema):
    @pre_load
    def expand_short_notation(self, data: Any, **kwargs) -> Any:
        # Are we using expanded notation?
        if isinstance(data, collections.abc.Mapping):
            # We have a map. Return data unchanged
            return data

        # Data are not a map, which means they are in short-hand
        # notation. Move data under 'constraint' keyword
        new_data = dict()
        new_data['constraint'] = data
        return new_data

    constraint = fields.List(fields.Nested(ConditionSchema))
    period = fields.Str()
    evaluations = fields.Integer()
    method = fields.Str()

class TargetFilterSchema(Schema):
    node = fields.Str()
    capability= fields.Str()
    requirement = fields.Str()
    
class TriggerSchema(BaseSchema):
    event = fields.Str()
    schedule = fields.Str()
    target_filter = fields.Nested(TargetFilterSchema)
    condition = fields.Nested(TriggerConditionSchema)
    action = fields.List(fields.Nested(ActivitySchema))
