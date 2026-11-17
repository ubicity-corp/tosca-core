"""
Repository Schema class used by Marshmallow
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2015-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger = logging.getLogger(__name__)

# Marshmallow support
from marshmallow import fields, post_load

# Schemas on which this schema depends
from tosca_core.schema.base import BaseSchema

# Object class for this schema
from tosca_core.models.repository import ToscaRepository


class RepositorySchema(BaseSchema):

    id = fields.Integer(dump_only=True)
    name = fields.Str()
    # Use fields.Str rather than fields.URL: the latter's defaults
    # reject perfectly valid 'file:' URIs (no host) and relative
    # 'file:<path>' refs that the spec allows. ToscaRepositoryValidator
    # checks the URL semantically and resolves it inside the CSAR.
    url = fields.Str()

    # default field used for short-hand grammar
    default_data_key = 'url'

    @post_load
    def make_object(self, data: dict, **kwargs) -> ToscaRepository:
        return ToscaRepository(**data)



