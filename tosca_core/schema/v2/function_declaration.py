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
from marshmallow import fields, post_dump, post_load

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

    @post_dump(pass_original=True)
    def show_implementer(self, data: dict, signature: ToscaSignature, **kwargs) -> dict:
        """A signature shows the implementation its own profile declares.
        One an implementing file supplied is shown as 'implemented_by',
        naming that profile, so the declaration reads as published."""
        defining = implementer(signature)
        if defining is not None:
            data.pop('implementation', None)
            data['implemented_by'] = defining.label
        return data


def implementer(signature: ToscaSignature):
    """The implementing profile that supplied a signature's
    implementation, or None where it has none or declares its own"""
    if not signature.artifacts:
        return None
    defining = signature.artifacts[-1].defining_profile
    function = signature.function
    if defining is None or function is None or defining is function.profile:
        return None
    return defining

def create_signature(**kwargs) -> ToscaSignature:
    return ToscaSignature(**kwargs)
    
    
class FunctionDeclarationSchema(BaseSchema):
    id =           fields.Integer(dump_only=True)
    name =         fields.Str()
    signatures =   fields.List(fields.Nested(SignatureSchema))
    # A function-level implementation, applying to every signature
    # that does not carry its own. Only an implementing file may give
    # one; it is kept as written and loaded once per signature.
    implementation = fields.Raw(load_only=True)

    @post_load
    def make_object(self, data: dict, **kwargs) -> ToscaFunctionDeclaration:
        return create_function_declaration(**data)

def create_function_declaration(**kwargs) -> ToscaFunctionDeclaration:
    return ToscaFunctionDeclaration(**kwargs)
    
