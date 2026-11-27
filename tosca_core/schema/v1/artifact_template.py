"""
Artifact Schema
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2015-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger = logging.getLogger(__name__)

# Marshmallow support
from marshmallow import fields, post_load

# Schemas used by ArtifactTemplateSchema
from .template import TemplateSchema

# Support for checking whether data to be loaded are a map
import collections

# Object class for this schema
from tosca_core.models.artifact import ToscaArtifact


def create_artifact_template(**kwargs) -> ToscaArtifact:
    return ToscaArtifact(**kwargs)


class ArtifactTemplateSchema(TemplateSchema):
    type =              fields.Str()
    repository =        fields.Str()
    file =              fields.Str()
    deploy_path =       fields.Str()
    artifact_version=   fields.Str()    
    checksum=           fields.Str()
    checksum_algorithm= fields.Str()

    # default field used for short-hand grammar
    default_data_key = 'file'

    @post_load
    def make_object(self, data: dict, **kwargs) -> ToscaArtifact:
        return create_artifact_template(**data)
