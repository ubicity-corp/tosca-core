"""
Activity Schema class
"""
from __future__ import annotations

__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2019-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger = logging.getLogger(__name__)

# Marshmallow support
from marshmallow import fields

# Schemas used by WorkflowSchema
from tosca_core.schema.base import BaseSchema


class CallOperationSchema(BaseSchema):
    operation = fields.Str()
    inputs = fields.Dict()
                          
    # default field used for short-hand grammar
    default_data_key = 'operation'


class ActivitySchema(BaseSchema):
    # The TOSCA key name for the 'update' action is 'update', but that name
    # conflicts with the update operation on Python dictionaries, so we convert it
    # to 'update_'
    update_ = fields.Dict(data_key='update')
    delegate = fields.Str()
    set_state = fields.Str()
    call_operation = fields.Nested(CallOperationSchema)
    inline = fields.Str()
