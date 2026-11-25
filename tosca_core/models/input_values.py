"""
Input values supplied for a service template or a workflow, validated against
the input parameter definitions that receive them.

Both are incoming parameters (TOSCA 2.0, Parameter Definition), with the same
keynames and the same rules: a value is supplied only for a declared input; an
input with a fixed `value` takes no supplied value, since a fixed value cannot
be changed; and a required input that is not supplied is satisfied by a fixed
value or by a default that is guaranteed to produce one.
"""
from __future__ import annotations

import logging
from typing import Any

import tosca_core.models.exceptions as te

logger = logging.getLogger(__name__)


def validate_input_values(context: Any, input_declarations: dict[str, Any],
                          inputs: dict[str, Any], check_required: bool = True) -> dict[str, Any]:
    """Validate the input values supplied to 'context', the service template or
    workflow template whose input declarations are 'input_declarations'.

    Args:
      context: the template that declares the inputs, in which values are
        validated and presence is decided
      input_declarations(dict): the template's input declarations by name
      inputs(dict): the supplied input values by name
      check_required(bool): whether every required input must be satisfied;
        True when a service or workflow is instantiated, False for a service
        update, which supplies only the inputs that change
    Returns:
      (possibly empty) dict of validation errors by input name
    """
    validation_errors: dict[str, Any] = {}
    for input_name, input_value in inputs.items():
        logger.debug("%s: validating input '%s'", context.id, input_name)
        try:
            input_declaration = input_declarations[input_name]
        except KeyError:
            logger.error("'%s': undefined input '%s'", context.id, input_name)
            validation_errors[input_name] = 'not previously defined'
            continue

        # A fixed value cannot be changed
        try:
            input_declaration.value
        except AttributeError:
            pass
        else:
            validation_errors[input_name] = 'overriding value from definition is not allowed'
            continue

        try:
            input_declaration.validate_value(context, input_value)
        except te.ValidationError as e:
            logger.error("'%s' input '%s': '%s' is invalid value for %s",
                         context.id, input_name, input_value, input_declaration.type)
            validation_errors[input_name] = e.errors
        except Exception as error:
            logger.error("%s: error validating inputs: %s", context.id, error)
            validation_errors[input_name] = "validator error ({0})".format(error)

    if check_required:
        for input_name, input_declaration in input_declarations.items():
            if input_name in inputs or not input_declaration.is_required():
                continue
            logger.debug("Checking value for required input '%s'", input_name)
            try:
                error = input_declaration.validate_value_presence(context, inputs)
            except Exception as e:
                logger.error("error checking required input '%s': %s", input_name, e)
                error = 'validator error <{0}>'.format(str(e))
            if error:
                validation_errors[input_name] = error

    return validation_errors
