"""
Substitution Mappings Schema
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
from .node_filter import NodeFilterSchema


class SubstitutionMappingsSchema(BaseSchema):

    node_type: fields.Str = fields.Str()
    substitution_filter: fields.Nested = fields.Nested(NodeFilterSchema)
    attributes: fields.Dict = fields.Dict()
    properties: fields.Dict = fields.Dict()
    capabilities: fields.Dict = fields.Dict()
    # A map here, keyed by requirement name, which is the 1.x grammar. TOSCA
    # 2.0 writes a list of single-key maps instead, so the two schemas differ
    # in this one field. See `make_object` for why the difference stops here.
    requirements: fields.Dict = fields.Dict()
    interfaces: fields.Dict = fields.Dict()

    @post_load
    def normalize_requirements(self, data: dict, **kwargs) -> dict:
        """Normalize 1.x requirement mappings to the internal representation.

        Not a `make_object` hook: this schema builds no model of its own -- the
        service template's setter constructs the entity later -- so this only
        reshapes a field and returns the data.

        The internal model is shared by both versions and holds requirement
        mappings as a LIST of single-key maps -- the 2.0 shape. Converting here
        means everything downstream sees one shape regardless of which version
        was parsed, and the model is spared a version-sensitive column type.

        This is a shape change only: each entry becomes a single-key map and
        the value passes through untouched.
        """
        requirements = data.get('requirements')
        if isinstance(requirements, dict):
            data['requirements'] = [{name: mapping}
                                    for name, mapping in requirements.items()]
        return data

