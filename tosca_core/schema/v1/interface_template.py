"""
Interface Schema classes
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
from tosca_core.schema.unknown_field_mixin import UnknownFieldMixin

# Schemas used by InterfaceTemplateSchema
from .template import TemplateSchema
from .operation import (
    OperationSchema, create_operation_template,
    NotificationSchema, create_notification_template)

# Object class for this schema
from tosca_core.models.interface_template import ToscaInterfaceTemplate


def create_interface_template(**kwargs) -> ToscaInterfaceTemplate:
    return ToscaInterfaceTemplate(**kwargs)


class InterfaceTemplateSchema(UnknownFieldMixin, TemplateSchema):

    operations =    NamedObjectMap(fields.Nested(OperationSchema,
                                                 load_default=create_operation_template),
                                   allow_none=True)
    notifications = NamedObjectMap(fields.Nested(NotificationSchema,
                                                 load_default=create_notification_template),
                                   allow_none=True)
    inputs =        fields.Dict(allow_none=True)
    outputs =       fields.Dict(allow_none=True)

    unknown_field_map = 'operations'

    @post_load
    def make_object(self, data: dict, **kwargs) -> ToscaInterfaceTemplate:
        return create_interface_template(**data)
