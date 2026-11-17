"""
Function Declaration Schema classes
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2022-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# logging support
import logging
logger = logging.getLogger(__name__)

# Marshmallow support
from marshmallow import fields, post_load

# Schemas used by FunctionDeclarationSchema
from tosca_core.schema.base import BaseSchema
from .property_declaration import (InputParameterSchema, OutputParameterSchema)
from .operation_implementation import OperationImplementationSchema

# Object class for this schema
from tosca_core.models.function_declaration import ToscaFunctionDeclaration, ToscaSignature


class SignatureSchema(BaseSchema):
    id =           fields.Integer(dump_only=True)
    arguments = fields.List(fields.Nested(InputParameterSchema))
    optional_arguments = fields.List(fields.Nested(InputParameterSchema))
    variadic = fields.Boolean()
    result = fields.Nested(OutputParameterSchema)
    implementation = fields.Nested(OperationImplementationSchema)
    
    @post_load
    def make_object(self, data: dict, **kwargs) -> ToscaSignature:
        return create_signature(**data)

def create_signature(**kwargs) -> ToscaSignature:
    return ToscaSignature(**kwargs)
    
    
class FunctionDeclarationSchema(BaseSchema):
    id =           fields.Integer(dump_only=True)
    name =         fields.Str()
    signatures =   fields.List(fields.Nested(SignatureSchema))

    @post_load
    def make_object(self, data: dict, **kwargs) -> ToscaFunctionDeclaration:
        return create_function_declaration(**data)

def create_function_declaration(**kwargs) -> ToscaFunctionDeclaration:
    return ToscaFunctionDeclaration(**kwargs)
    
