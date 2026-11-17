"""
ToscaFunctionValidator class
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2022-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger = logging.getLogger(__name__)

# Type hint support
from typing import Any, Optional

# Validator support
from . import get_validator
from .validator import ToscaValidator


class ToscaFunctionValidator(ToscaValidator):
    """The ToscaFunctionValidator class validates function declarations in
    Tosca profiles
    """

    def __init__(self) -> None:
        """Constructor
        """
        super(ToscaFunctionValidator, self).__init__()


    def validate_function_declaration(self, function: "Any") -> dict:
        """Check if a function declaration is valid

        Args: 
          function(ToscaFunctionDeclaration): function declaration to
            validate

        Returns:
          (possibly empty) dict of validation errors

        Raises:
          None
        """

        validation_errors = {}

        # Does the function have valid signatures?
        errors = self.validate_signatures(function)
        if errors:
            logger.error("Function '%s': invalid signatures", function.name)
            validation_errors['signatures'] = errors

        # Everything OK
        self.add_line_number(validation_errors, function)
        return validation_errors


    def validate_signatures(self, function: "Any") -> dict:
        """Check if a function declaration has valid signatures

        Args: 
          function(ToscaFunctionDeclaration): function declaration for
            which to validate signatures

        Returns:
          (possibly empty) dict of validation errors

        Raises:
          None
        """

        # Make sure we have signatures for this function
        if not function.signatures:
            logger.error("Function %s: no signatures specified", function.name)
            return 'not defined'

        # Validate each signature
        count = 0
        validation_errors = dict()
        for signature in function.signatures:
            signature.name = str(count)
            errors = self.validate_signature(function, signature)
            if errors:
                validation_errors[signature.name] = errors
            count = count+1

        # Everything OK
        return validation_errors


    def validate_signature(self, function: "Any", signature: "Any") -> dict:
        """Check if a function signature is valid

        Args: 
          function(ToscaFunctionDeclaration): function declaration for
            which to validate the signature
          signature(ToscaSignature): signature to validate

        Returns:
          (possibly empty) dict of validation errors

        Raises:
          None
        """

        validation_errors = dict()

        # Validate arguments
        errors = self.validate_arguments(function, signature)
        if errors:
            validation_errors['arguments'] = errors

        # Validate result
        errors = self.validate_result(function, signature)
        if errors:
            validation_errors['result'] = errors

        # Validate implementation
        errors = self.validate_implementation(function, signature)
        if errors:
            validation_errors['implementation'] = errors

        # All done
        return validation_errors
    

    def validate_arguments(self, function: "Any", signature: "Any") -> Optional[dict]:
        """Check if a function signature has valid arguments

        Args: 
          function(ToscaFunctionDeclaration): function for which to
            validate arguments
          signature(ToscaSignature): function signature for which to
            validate arguments

        Returns:
          (possibly empty) dict of validation errors

        Raises:
          None
        """

        # Do we have arguments for this signature?
        if not signature.arguments:
            logger.debug("Function %s (signature %s): no arguments specified", function.name, signature.name)
            return None

        # Validate each parameter
        validator = get_validator('ToscaPropertyDeclaration')
        count = 0
        validation_errors = dict()
        for parameter in signature.arguments:
            parameter.name = str(count)
            error = validator.validate_declaration(signature, parameter)
            if error:
                validation_errors[parameter.name] = error
            count = count+1

        # Everything OK
        return validation_errors


    def validate_result(self, function: "Any", signature: "Any") -> Optional[dict]:
        """Check if a function signature has a valid result

        Args: 
          function(ToscaFunctionDeclaration): function declaration for
            which to validate result
          signature(ToscaSignature): function signature for which to
            validate result

        Returns:
          (possibly empty) dict of validation errors

        Raises:
          None
        """

        # Do we have a result defined for this signature?
        if not signature.result:
            logger.debug("Function %s (signature %s): no result specified", function.name, signature.name)
            return None

        # Validate the result
        validator = get_validator('ToscaPropertyDeclaration')
        result = signature.result
        result.name = 'result'
        errors = validator.validate_declaration(signature, result)
        if errors:
            return errors

        # Everything OK
        return None
    

    def validate_implementation(self, function: "Any", signature: "Any") -> Optional[dict]:
        """Check if a function signature has a valid implementation. The
        implementation follows TOSCA v2.0 operation-implementation
        grammar, so we delegate the per-artifact checks to the shared
        operation-implementation validator.

        Function implementations differ from operation implementations
        in one important way: a function returns a single value, so the
        "run every artifact and merge outputs" model that operations
        use has no meaning. Function signatures therefore must have at
        most one implementation artifact (the primary); any
        dependencies are rejected here.

        Args:
          function(ToscaFunctionDeclaration): function declaration for
            which to validate implementation
          signature(ToscaSignature): function signature for which to
            validate implementation

        Returns:
          (possibly empty) dict of validation errors

        Raises:
          None
        """

        # Do we have an implementation defined for this signature?
        if not signature.artifacts:
            logger.debug("Function %s (signature %s): no implementation specified",
                         function.name, signature.name)
            return None

        # Reject dependencies: a function returns one value, so only
        # the primary implementation artifact is meaningful.
        if len(signature.artifacts) > 1:
            return ("function implementations must not declare 'dependencies'; "
                    "a function returns a single value and has no use for "
                    "additional artifacts")

        # Delegate per-artifact validation to the operation-implementation
        # validator (typed-template checks).
        validator = get_validator('ToscaOperationImplementation')
        try:
            return validator.validate_implementation(signature) or None
        except Exception as e:
            return f"internal error <{e}>"
