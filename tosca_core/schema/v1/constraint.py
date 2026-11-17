"""
Constraint Schema classes
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2015-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# logging support
import logging
logger = logging.getLogger(__name__)

# Support for checking whether data to be loaded are a map

# Marshmallow support
from marshmallow import Schema, fields, pre_load

# Type hints
from typing import Any


class ConstraintSchema(Schema):

    # Note that ConstraintSchema doesn't inherit from BaseSchema,
    # since BaseSchema inserts context-specific data which will
    # interfere with the 'untangling'
    operation = fields.Str()
    value = fields.Raw()

    @pre_load
    def untangle_fields(self, data: Any, **kwargs) -> Any:
        """Replace 'key' : 'value' entry in the map with 'operation' : 'key'
        and 'value' : 'val'. Make sure to ignore line numbers and
        delete service ids

        """

        try:
            # Make sure we have dict
            keys = data.keys()

            # Parse
            if 'line' in data:
                try:
                    [(key1, val1), (key2, val2)] = list(data.items())
                    if key1 == 'line':
                        data['operation'] = key2
                        data['value'] = val2
                        del data[key2]
                    else:
                        data['operation'] = key1
                        data['value'] = val1
                        del data[key1]
                except ValueError:
                    logger.error("don't have 2 items")
                    pass
            else:
                try:
                    [(key, val)] = list(data.items())
                    data['operation'] = key
                    data['value'] = val
                    del data[key]
                except ValueError:
                    logger.error("Have more than 1 item")
                    pass
            return data

        except AttributeError:
            # No keys() attribute. Must be just a single value. Must
            # be an "equal" constraint
            untangled_data = {
                'operation' : 'equal',
                'value'     : data,
                }
            return untangled_data
