"""
Property Declaration Schema 
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2015-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# logging support
import logging
logger = logging.getLogger(__name__)

# Marshmallow support
from marshmallow import fields, post_load

# Type hints
from typing import Any

# Schemas used by this module
from .declaration import DeclarationSchema
from .constraint import ConstraintSchema

# Object class for this schema
from tosca_core.models.property_declaration import ToscaPropertyDeclaration
    
function_names = [
    'concat',
    'get_input',
    'get_artifact',
    'get_attribute',
    'get_property',
    'get_nodes_of_type',
    'get_operation_output',
    'token',
]
    
def is_function(data: Any) -> bool:
    """Helper function to check if data represent a TOSCA function"""
    
    # Try to parse data as a function statement
    try:
        [(name, args)] = list(data.items())
        if name in function_names: return True
    except Exception:
        # Not formatted as function
        logger.debug("Not formatted as function.")
        #pass
    return False
    

def create_attribute_declaration(**kwargs) -> ToscaPropertyDeclaration:
    return ToscaPropertyDeclaration(role='ATTRIBUTE', **kwargs)

def create_property_declaration(**kwargs) -> ToscaPropertyDeclaration:
    return ToscaPropertyDeclaration(role='PROPERTY', **kwargs)

def create_input_declaration(**kwargs) -> ToscaPropertyDeclaration:
    return ToscaPropertyDeclaration(role='INPUT', **kwargs)

def create_output_declaration(**kwargs) -> ToscaPropertyDeclaration:
    return ToscaPropertyDeclaration(role='OUTPUT', **kwargs)

def create_schema_declaration(**kwargs) -> ToscaPropertyDeclaration:
    return ToscaPropertyDeclaration(role='SCHEMA', **kwargs)


class AttributeDeclarationSchema(DeclarationSchema):
    """Base AttributeDeclarationSchema. Note that the 'value' keyword
    holds the fixed value for a attribute declaration. This schema also
    specifies that this 'value' field is to be used as the default
    field in short notations of the syntax
    """

    status =       fields.Str()
    default =      fields.Raw()
    value =        fields.Raw()
    constraints =  fields.List(fields.Nested(ConstraintSchema))
    entry_schema = fields.Nested('EntrySchemaSchemaV1')
    key_schema =   fields.Nested('EntrySchemaSchemaV1')

    # default field used for short-hand grammar
    default_data_key = 'value'

    def load(self, data: Any, **kwargs) -> Any:
        """Override the default Schema load() method to correctly deal with
        value expressions
        """
        if is_function(data):
            data = {
                self.default_data_key : data
            }

        return super(AttributeDeclarationSchema, self).load(data, **kwargs)


    @post_load
    def make_object(self, data: dict, **kwargs) -> ToscaPropertyDeclaration:
        return create_attribute_declaration(**data)


class PropertyDeclarationSchema(AttributeDeclarationSchema):
    """Base property declaration schema. This adds the 'required' and
    'constraints' keywords to the AttributeDeclarationSchema

    In practice, this schema will only ever get used for service
    template inputs. For all other property declaration scenarios, we
    will use one of the derived schemas that add support for a
    "defauld field". The specific default field depends on the
    context, which is why there are multiple derived classes.
    """

    required = fields.Boolean()

    @post_load
    def make_object(self, data: dict, **kwargs) -> ToscaPropertyDeclaration:
        return create_property_declaration(**data)


class InputDeclarationSchema(PropertyDeclarationSchema):
    """The InputDeclarationSchema is identical to the
    PropertyDeclarationSchema, except that it creates a
    ToscaPropertyDeclaration with an 'INPUT' role
    """
    @post_load
    def make_object(self, data: dict, **kwargs) -> ToscaPropertyDeclaration:
        return create_input_declaration(**data)


class ServiceOutputDeclarationSchema(AttributeDeclarationSchema):
    """The TemplateOutputDeclarationSchema is identical to the
    AttributeDeclarationSchema, except that it creates a
    ToscaPropertyDeclaration with an 'OUTPUT' role
    """
    @post_load
    def make_object(self, data: dict, **kwargs) -> ToscaPropertyDeclaration:
        return create_output_declaration(**data)


class OutputDeclarationSchema(PropertyDeclarationSchema):
    """The OutputDeclarationSchema adds a 'mapping' keyword to the
    PropertyDeclarationSchema which holds the 'attribute mapping' to
    be used for an declaration. This schema also specifies that this
    'mapping' field is to be used as the default field in short
    notations of the syntax. And finally, it creates a
    ToscaPropertyDeclaration with an 'OUTPUT' role
    """
    
    mapping = fields.Raw()

    # default field used for short-hand grammar
    default_data_key = 'mapping'

    @post_load
    def make_object(self, data: dict, **kwargs) -> ToscaPropertyDeclaration:
        return create_output_declaration(**data)


class EntrySchemaSchemaV1(PropertyDeclarationSchema):
    """The EntrySchemaSchemaV1 is identical to the PropertyDeclarationSchema
    except that is specifies that the 'type' field is to be used as
    the default field in short notations of the syntax
    """

    # default field used for short-hand grammar
    default_data_key = 'type'

    @post_load
    def make_object(self, data: dict, **kwargs) -> ToscaPropertyDeclaration:
        return create_schema_declaration(**data)
