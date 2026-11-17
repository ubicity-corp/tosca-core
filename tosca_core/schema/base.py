"""
Base Schema for TOSCA entities 
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2016-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger = logging.getLogger(__name__)

# Marshmallow support
from marshmallow import Schema, fields, pre_load

# Type hints
from typing import Any

# Support for checking whether data to be loaded are a map
import collections.abc


class BaseSchema(Schema):
    """Top-level schema with key names that must be supported by all TOSCA
    entities.
    """

    # Context fields that apply to all schemas
    line = fields.Integer(load_only=True)

    # TOSCA fields that apply to all schemas
    description = fields.Str(allow_none=True)

    # The TOSCA key name for meta data is 'metadata', but that name
    # conflicts with a field name used by SQLAlchemy, so we convert it
    # to meta_data.
    meta_data = fields.Dict(data_key='metadata')

    """
    # Enable for debugging purposes
    def __init__(self, **data):
        super(BaseSchema, self).__init__(**data)
        logger.debug("SCHEMA  %s", self)
    """

    @pre_load
    def fix_data(self, data: Any, **kwargs) -> Any:
        """Fix up data before they can be parsed. This may involve:
           - Expanding short-hand grammars into expanded grammars
             (using the 'default_data_key' attribute in the schema)
           - Extracting a 'line' value
        """
        # Do the data potentially use short-hand grammar?
        if not isinstance(data, collections.abc.Mapping):
            try:
                default_data_key = self.default_data_key
                new_data = dict()
                new_data[default_data_key] = data
                return new_data
            except AttributeError:
                # No default field specified
                return data

        # Data are a dict. Extract a line number.
        try:
            line = data.lc.line
            data['line'] = line
        except Exception as e:
            # no line found
            logger.debug("No line found.")
            #pass

        return data




