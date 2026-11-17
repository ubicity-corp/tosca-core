"""
NamedObjectMap 
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2015-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger = logging.getLogger(__name__)

# Support for checking if we have a Map
import collections

# Marshmallow support
from marshmallow import fields
from marshmallow.exceptions import ValidationError

# Type hints
from typing import Any


class NamedObjectMap(fields.Dict):
    """A NamedObjectMap acts like a Dict field, with one difference: it
    reflects each entry's key in the 'name' attribute of the value.
    Null entries are rejected like any other null value -- a key with
    no body is treated as a typo, not as an implicit request for a
    default-constructed entry.
    """

    def __init__(self, field: Any, **kwargs: Any) -> None:
        super(NamedObjectMap, self).__init__(values=field, **kwargs)


    def _deserialize(self, value: Any, attr: Any, data: Any, **kwargs: Any) -> dict:
        """Deserialize a named object map and set the 'name' attribute
        on each value to its key.
        """

        # Call _deserialize method on Dict
        result = super()._deserialize(value, attr, data, **kwargs)

        # Each entry's key is the name the value will be looked up
        # by. An empty / whitespace-only key isn't a valid name, and
        # silently letting it through assigns the value an unusable
        # identity that downstream lookups can't reach.
        for k in result:
            if not isinstance(k, str) or not k.strip():
                raise ValidationError({k: 'name must not be empty'})

        # Annotate each value with its key as 'name'.
        for k, v in result.items():
            try:
                v.name = k
            except AttributeError:
                # Not an object. A dict perhaps?
                try:
                    v['name'] = k
                except Exception:
                    logger.debug("Object is not a dictionary.")
        return result
