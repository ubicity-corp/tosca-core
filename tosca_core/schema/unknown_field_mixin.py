"""
Unknown Field Mixin
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2016-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# logging support
import logging
logger = logging.getLogger(__name__)

# Marshmallow support
from marshmallow import pre_load

# Type hints
from typing import Any

# Support for checking whether data to be loaded are a map
import collections.abc

def move_to_map(data: Any, map_name: Any, key: Any, value: Any) -> None:
    try:
        map = data[map_name]
    except Exception as e:
        # Map doesn't exist yet
        data[map_name] = {}
        map = data[map_name]

    map[key] = value


class UnknownFieldMixin(object):

    @pre_load
    def move_unknown_fields(self, data: Any, **kwargs) -> Any:

        # Make sure we have a map
        if not isinstance(data, collections.abc.Mapping):
            # Not a map. Return data unchanged
            return data

        # If the data already have an 'unknown_field_map', then
        # nothing needs to be moved. This can be the case for
        # interface definitions:
        #
        # 1. Interface definitions without 'notifications' can have
        #    'operations' defined without using the 'operations'
        #    keyname. These operations need to get moved
        #
        # 2. If interface definitions include 'notifications', then
        #    operations need to be defined under the 'operations'
        #    keyname. In that case, operations don't need to be moved.

        if self.unknown_field_map in data:
            return data

        # We need to move unknown fields. First, create empty
        # operations dict.
        processed_data = {}
        try:
            for key, value in data.items():
                if key not in self.fields and key not in self.exclude:
                    move_to_map(processed_data, self.unknown_field_map, key, value)
                else:
                    processed_data[key] = value
        except Exception as e:
            logger.info("%s", e)

        # Return results
        return processed_data


