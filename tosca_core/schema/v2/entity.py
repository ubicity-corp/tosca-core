"""
Entity Schema Definition
"""
from __future__ import annotations

__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2024-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger = logging.getLogger(__name__)

# Marshmallow support
from marshmallow import Schema, fields

class EntitySchema(Schema):
    """Base Ubicity entity schema. All entities have a name and an id
    """
    id = fields.Integer(dump_only=True)
    name = fields.Str()
