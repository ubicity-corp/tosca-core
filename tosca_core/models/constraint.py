"""
Shared upgrade of TOSCA 1.x constraint clauses to TOSCA 2.0 boolean-function
conditions. Used by both property/attribute constraint declarations
(ToscaPropertyDeclaration) and workflow condition clauses (the condition
validator), which differ only in the operand the constraint tests.
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2014-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

from typing import Any


def constraint_to_condition(operand: Any, constraint: dict[str, Any]) -> dict[str, Any]:
    """Upgrade a Version 1.x constraint clause to the corresponding Version
    2.0 boolean function, applied to ``operand`` -- the expression the
    constraint tests (``'$value'`` for a property/attribute constraint, or
    ``{'$get_attribute': path}`` for a workflow condition).

    Most 1.x operators share the name and ``[operand, value]`` shape of their
    2.0 function. The length family (``length`` / ``min_length`` /
    ``max_length``) has no dedicated 2.0 function, so it composes the
    ``$length`` function with a comparison, and ``pattern`` maps to the
    ``$matches`` regular-expression function. (``schema`` has no 2.0
    equivalent and is rejected upstream during constraint validation.)
    """
    operation = constraint['operation']
    value = constraint['value']

    if operation == 'pattern':
        return {'$matches': [operand, value]}
    elif operation == 'length':
        return {'$equal': [{'$length': [operand]}, value]}
    elif operation == 'min_length':
        return {'$greater_or_equal': [{'$length': [operand]}, value]}
    elif operation == 'max_length':
        return {'$less_or_equal': [{'$length': [operand]}, value]}
    else:
        return {'$' + operation: [operand, value]}
