"""
Condition Schema class
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2019-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger = logging.getLogger(__name__)

# Marshmallow support
from marshmallow import Schema, fields, pre_load

# Type hints
from typing import Any

# Schemas used by WorkflowSchema
from tosca_core.schema.base import BaseSchema
from .constraint import ConstraintSchema


class AssertionSchema(Schema):

    attribute = fields.Raw()
    constraints = fields.List(fields.Nested(ConstraintSchema))

    @pre_load
    def untangle_fields(self, data: Any, **kwargs) -> Any:
        """Replace 'key' : 'value' entry in the map with 'attribute' : 'key'
        and 'constraints' : 'val'. Make sure to ignore line numbers
        and delete service ids
        """

        try:
            # Make sure we have dict
            keys = data.keys()
        except AttributeError:
            # Nothing to untangle
            pass

        # Parse
        try:
            [(key, val)] = data.items()
            data['attribute'] = key
            data['constraints'] = val
            del data[key]
        except ValueError:
            logger.error("Assertion schema: dict has more than 1 item")
            pass
                        
        return data



class ConditionSchema(Schema):

    and_ = fields.List(fields.Nested('ConditionSchema'), data_key='and')
    or_ = fields.List(fields.Nested('ConditionSchema'), data_key='or')
    not_ = fields.List(fields.Nested('ConditionSchema'), data_key='not')
    assert_ = fields.List(fields.Nested(AssertionSchema), data_key='assert')


    @pre_load
    def explicit_assert(self, data: Any, **kwargs) -> Any:
        """For direct assertion statements, insert an explicit 'assert'
        keyname to allow for correct parsing
        """

        try:
            # Make sure we have dict
            keys = data.keys()
        except AttributeError:
            # Nothing to untangle
            pass

        try:
            # Parse
            [(key, val)] = data.items()
            # Find direct assertion statement
            if key not in ['and', 'or', 'not', 'assert']:
                # Insert explict 'assert' statement
                data['assert'] = [{ key: val } ]
                del data[key]
        except ValueError:
            logger.error("Assertion schema: dict has more than 1 item")
            pass
                        
        return data

