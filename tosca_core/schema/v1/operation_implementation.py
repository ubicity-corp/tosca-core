"""
Operation Schema classes
"""
from __future__ import annotations

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
from .artifact_template import ArtifactTemplateSchema


class OperationImplementationSchema(BaseSchema):
    primary: fields.Nested = fields.Nested(ArtifactTemplateSchema)
    dependencies: fields.List = fields.List(fields.Nested(ArtifactTemplateSchema))
    operation_host: fields.Str = fields.Str()
    timeout: fields.Integer = fields.Integer()

    # default field used for short-hand grammar
    default_data_key: str = 'primary'

    @post_load
    def warn_about_ignored_keynames(self, data: dict, **kwargs) -> dict:
        """TOSCA 1.3's 'operation_host' and 'timeout' are accepted but not
        acted on, so say so rather than ignore them silently."""
        for keyname in ('operation_host', 'timeout'):
            if keyname in data:
                logger.warning("operation implementation keyname '%s' is not "
                               "supported and is ignored", keyname)
        return data
