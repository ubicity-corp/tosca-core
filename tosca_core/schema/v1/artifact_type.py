"""
Artifact Type Schema
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2015-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# logging support
import logging
logger = logging.getLogger(__name__)

# Marshmallow support
from marshmallow import fields, post_load

# Schemas used by GroupTypeSchema
from .type import TypeSchema

# Object class for this schema
from tosca_core.models.artifact_type import ToscaArtifactType


def create_artifact_type(**kwargs) -> ToscaArtifactType:
    return ToscaArtifactType(**kwargs)


class ArtifactTypeSchema(TypeSchema):
    mime_type = fields.Str()
    file_ext = fields.List(fields.Str())

    @post_load
    def make_object(self, data: dict, **kwargs) -> ToscaArtifactType:
        return create_artifact_type(**data)


# Global artifact type schema
artifact_type_schema = ArtifactTypeSchema()
artifact_types_schema = ArtifactTypeSchema(many=True)
