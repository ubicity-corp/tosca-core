"""
NamedObjectList field to be used with Marshmallow

Adapted from:
https://github.com/marshmallow-code/marshmallow/issues/120
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2015-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger = logging.getLogger(__name__)

# Support for checking if we have a List
from marshmallow import utils

# Marshmallow support
from marshmallow import fields
from marshmallow.exceptions import ValidationError

# Type hints
from typing import Any


class NamedObjectList(fields.Field):

    default_error_messages = {
        'invalid': 'Not a valid list type.',
        'format': 'Not a valid named list entry.',
    }

    def __init__(self, nested_field: Any, *args: Any, **kwargs: Any) -> None:
        fields.Field.__init__(self, *args, **kwargs)
        self.name_field = fields.Str()
        self.nested_field = nested_field


    def _add_to_schema(self, field_name: Any, schema: Any) -> None:
        super(NamedObjectList, self)._add_to_schema(field_name, schema)
        self.nested_field.parent = self
        self.nested_field.name = field_name


    def _deserialize(self, values: Any, attr: Any, data: Any, **kwargs: Any) -> list:
        # Make sure we have a list
        if not utils.is_collection(values):
            raise ValidationError('Not a valid list type')

        ret = []
        errors = []
        for value in values:
            try:
                [(key, val)] = list(value.items())
                k = self.name_field.deserialize(key)
                try:
                    v = self.nested_field.deserialize(val, **kwargs)
                except ValidationError as e:
                    error = {key : e.messages }
                    errors.append(error)
                    logger.debug("Unable to deserialize value.")
                    continue
                # If we deserialize into an object, set object name
                try:
                    v.name = k
                except AttributeError:
                    # Not an object. A dict perhaps?
                    try:
                        v['name'] = k
                    except Exception:
                        logger.debug("Object is not a dictionary.")
                        #pass
                ret.append(v)
            except (ValueError, AttributeError):
                 # Not a single key-value map
                raise ValidationError('Not a valid named list entry.')

        if errors:
            raise ValidationError(errors)

        return ret

    def _serialize(self, values: Any, attr: Any, obj: Any, **kwargs: Any) -> list:
        ret = []
        for value in values:
            entry = {}
            try:
                k = self.name_field._serialize(value.name, attr, obj)
            except AttributeError:
                # Not an object. A dict perhaps?
                try:
                    k = self.name_field._serialize(value['name'], attr, obj)
                except Exception:
                    # No name. Skip this
                    logger.debug("No name found, skipping this...")
                    continue
            v = self.nested_field._serialize(value, attr, obj, **kwargs)
            entry[k] = v
            ret.append(entry)
        return ret

