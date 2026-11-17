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
from tosca_core.schema.named_object_map import NamedObjectMap
from .declaration import DeclarationSchema
from .functions import is_function
from .validation_field import ValidationField

# Object class for this schema
from tosca_core.models.property_declaration import ToscaPropertyDeclaration


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
    validations =  ValidationField(data_key='validation')
    entry_schema = fields.Nested('EntrySchemaSchemaV2')
    key_schema =   fields.Nested('EntrySchemaSchemaV2')

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
    """Base property declaration schema. This adds the 'required' keyword
    to the AttributeDeclarationSchema.

    In practice, this schema will only ever get used for service
    template inputs. For all other property declaration scenarios, we
    will use one of the derived schemas that add support for a
    "default field". The specific default field depends on the
    context, which is why there are multiple derived classes.
    """

    required = fields.Boolean()
    properties =   NamedObjectMap(fields.Nested(
        "tosca_core.schema.v2.property_declaration.PropertyDeclarationSchema"))

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


class WorkflowOutputDeclarationSchema(AttributeDeclarationSchema):
    """Workflow outputs (TOSCA 2.0 §9.8 and §13.2). An output of a workflow
    defined by steps is outgoing and takes a 'value', as a service template
    output does. An output of a workflow defined by an 'implementation' is
    incoming: it takes a 'mapping' onto the attribute that stores the value
    the implementation returns. The short notation stays 'value', so the
    workflow validator moves an implementation workflow's list-form short
    notation into 'mapping'.
    """
    mapping = fields.Raw()

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


class EntrySchemaSchemaV2(PropertyDeclarationSchema):
    """The EntrySchemaSchemaV2 is identical to the PropertyDeclarationSchema
    except that is specifies that the 'type' field is to be used as
    the default field in short notations of the syntax
    """

    # default field used for short-hand grammar
    default_data_key = 'type'

    @post_load
    def make_object(self, data: dict, **kwargs) -> ToscaPropertyDeclaration:
        return create_schema_declaration(**data)


class InputParameterSchema(PropertyDeclarationSchema):
    """The InputParameterSchema is identical to the
    AttributeDeclarationSchema except that is specifies that the
    'type' field is to be used as the default field in short notations
    of the syntax
    """

    # default field used for short-hand grammar
    default_data_key = 'type'

    @post_load
    def make_object(self, data: dict, **kwargs) -> ToscaPropertyDeclaration:
        return create_input_declaration(**data)
    

class OutputParameterSchema(PropertyDeclarationSchema):
    """The InputParameterSchema is identical to the
    AttributeDeclarationSchema except that is specifies that the
    'type' field is to be used as the default field in short notations
    of the syntax
    """

    # default field used for short-hand grammar
    default_data_key = 'type'

    @post_load
    def make_object(self, data: dict, **kwargs) -> ToscaPropertyDeclaration:
        return create_output_declaration(**data)
    
