"""
Version 2 Import Schema class used by Marshmallow
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2016-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger = logging.getLogger(__name__)

# Marshmallow support
from marshmallow import fields, post_load

# Schemas on which this schema depends
from tosca_core.schema.base import BaseSchema

# Object class for this schema
from tosca_core.models.imprt import ToscaImport


class ImportSchema(BaseSchema):

    url =        fields.Str()
    profile =    fields.Str()
    repository = fields.Str()
    namespace =  fields.Str()
    
    # default field used for short-hand grammar
    default_data_key = 'url'

    @post_load
    def make_object(self, data: dict, **kwargs) -> ToscaImport:
        return ToscaImport(**data)
