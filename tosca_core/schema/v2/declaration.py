"""
Declaration Schema
"""
from __future__ import annotations

__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2015-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# logging support
import logging
logger = logging.getLogger(__name__)

# Marshmallow support
from marshmallow import fields

# Schemas on which this schema depends
from tosca_core.schema.base import BaseSchema


class DeclarationSchema(BaseSchema):
    name = fields.Str()
    type = fields.Str()
