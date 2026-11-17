"""
Substitution Mappings Schema 
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2015-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger = logging.getLogger(__name__)

# Marshmallow support
from marshmallow import fields

# Type hints
from typing import Any, Optional
from tosca_core.schema.url_field import URLField

# Schemas on which this schema depends
from tosca_core.schema.base import BaseSchema


class RequirementMappingList(fields.List):
    """Serializes the internal requirements list, converting tuple keys
    of the form (requirement_name, index) back to plain string keys."""

    def _serialize(self, value: Any, attr: Any, obj: Any, **kwargs: Any) -> Optional[list]:
        if value is None:
            return None
        normalized = []
        for item in value:
            if isinstance(item, dict):
                normalized.append({
                    (':'.join(str(p) for p in k) if isinstance(k, tuple) else k): v
                    for k, v in item.items()
                })
            else:
                normalized.append(item)
        return super()._serialize(normalized, attr, obj, **kwargs)


class SubstitutionMappingsSchema(BaseSchema):

    node_type = fields.Str()
    substitutes = URLField('type', type_type='node', type_id='<substitutes_id>')
    substitution_filter =  fields.Dict()
    attributes = fields.Dict()
    properties = fields.Dict()
    capabilities = fields.Dict()
    requirements = RequirementMappingList(fields.Dict())
    interfaces = fields.Dict()

