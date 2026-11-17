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


class CredentialSchema(BaseSchema):
    protocol = fields.Str()
    token_type = fields.Str()
    token = fields.Str()
    keys = fields.Dict()
    user = fields.Str()

class RepositorySchema(BaseSchema):

    id = fields.Integer(dump_only=True)
    # Use fields.Str rather than fields.URL: the latter's defaults
    # reject 'file:' URIs without a host and relative 'file:<path>'
    # refs the spec allows. ToscaRepositoryValidator checks the URL
    # semantically and resolves it inside the CSAR.
    url = fields.Str()
    name = fields.Str()
    credential = fields.Nested(CredentialSchema)

    # default field used for short-hand grammar
    default_data_key = 'url'

    @post_load
    def make_object(self, data: dict, **kwargs) -> ToscaRepository:
        return ToscaRepository(**data)



