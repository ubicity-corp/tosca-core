"""
Node Declaration Schema
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2015-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# logging support
import logging
logger = logging.getLogger(__name__)

# Marshmallow support
from marshmallow import post_load

# Schemas used by this schema
from .declaration import DeclarationSchema

# Object class for this schema
from tosca_core.models.node_declaration import ToscaNodeDeclaration


class NodeDeclarationSchema(DeclarationSchema):

    # default field used for short-hand grammar
    default_data_key = 'type'

    @post_load
    def make_object(self, data: dict, **kwargs) -> ToscaNodeDeclaration:
        return ToscaNodeDeclaration(**data)
