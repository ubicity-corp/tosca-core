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
from marshmallow import fields

# Schemas on which this schema depends
from tosca_core.schema.base import BaseSchema
from .artifact_template import ArtifactTemplateSchema


class OperationImplementationSchema(BaseSchema):
    primary = fields.Nested(ArtifactTemplateSchema)
    dependencies = fields.List(fields.Nested(ArtifactTemplateSchema))

    # default field used for short-hand grammar
    default_data_key: str = 'primary'
