"""
Marshmallow field for TOSCA 2.0 'validation' boolean function
expressions. Subclasses fields.Dict so we can replace the generic
"Not a valid mapping type." error with one that names the likely
cause: list-of-clauses syntax carried over from TOSCA 1.x
'constraints'.
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2026, Ubicity Corp."
__email__ = "info@ubicity.com"

from typing import Any

from marshmallow import ValidationError, fields


class ValidationField(fields.Dict):
    """Field for a TOSCA 2.0 'validation' boolean function expression.

    A 'validation' is a single function call (mapping), e.g.
    ``$valid_values: [$value, [...]]``. Marshmallow's generic "Not a
    valid mapping type." doesn't explain why a list is rejected, so
    we intercept and emit a TOSCA-flavoured hint instead.
    """

    def _deserialize(self, value: Any, attr, data, **kwargs):
        if isinstance(value, list):
            raise ValidationError(
                "expected a function expression (mapping), got a list"
            )
        return super()._deserialize(value, attr, data, **kwargs)
