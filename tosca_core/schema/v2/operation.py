"""
Operation Schema classes
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2015-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger = logging.getLogger(__name__)

# Marshmallow support
from marshmallow import fields, post_load
from .functions import refuse_service_input

# Schemas used by OperationSchema
from tosca_core.schema.base import BaseSchema
from .operation_implementation import OperationImplementationSchema

# Object class for this schema
from tosca_core.models.operation_template import ToscaOperationTemplate


def create_operation_template(**kwargs) -> ToscaOperationTemplate:
    return ToscaOperationTemplate(role='OPERATION', **kwargs)

def create_notification_template(**kwargs) -> ToscaOperationTemplate:
    return ToscaOperationTemplate(role='NOTIFICATION', **kwargs)


class OperationSchema(BaseSchema):

    implementation = fields.Nested(OperationImplementationSchema)
    inputs =         fields.Dict(validate=refuse_service_input)
    outputs =        fields.Dict()
    
    # default field used for short-hand grammar
    default_data_key = 'implementation'

    @post_load
    def make_object(self, data: dict, **kwargs) -> ToscaOperationTemplate:
        return create_operation_template(**data)


class NotificationSchema(OperationSchema):
    @post_load
    def make_object(self, data: dict, **kwargs) -> ToscaOperationTemplate:
        return create_notification_template(**data)
    
    
