"""
Trigger Schema
"""
from __future__ import annotations

__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2018-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger = logging.getLogger(__name__)

# Marshmallow support
from marshmallow import Schema, fields, pre_load

# Schemas on which this schema depends
from tosca_core.schema.base import BaseSchema
from .activity import ActivitySchema

class TriggerSchema(BaseSchema):
    event = fields.Str()
    condition = fields.Dict()
    action = fields.List(fields.Nested(ActivitySchema))

