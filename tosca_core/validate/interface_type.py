"""
ToscaInterfaceTypeValidator class
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2014-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger = logging.getLogger(__name__)

# Type hint support
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from tosca_core.models.interface_type import ToscaInterfaceType

# Validator support
from . import get_validator
from .type import ToscaTypeValidator


class ToscaInterfaceTypeValidator(ToscaTypeValidator):
    """The ToscaInterfaceTypeValidator class validates TOSCA interface
    type definitions.
    """

    def __init__(self) -> None:
        """Constructor
        """
        super(ToscaInterfaceTypeValidator, self).__init__()


    def complete_type_refinements(self, interface_type: "ToscaInterfaceType") -> dict:
        """Check and complete an interface type's refinements: the inputs
        and outputs it refines, and the inputs and outputs of each of its
        operations and notifications that refine those of the same
        operation in the parent interface type.

        An operation is never merged itself; only its inputs and outputs
        are, and each finds what it refines by looking the operation up
        in the parent interface type. An operation the parent does not
        declare finds nothing, so its inputs and outputs are new.
        'validate_type_specifics' then validates all of them without
        checking or merging them again.

        Args:
          interface_type(ToscaInterfaceType): interface type whose
            refinements to complete

        Returns:
          (possibly empty) dict of validation errors, keyed the way
          'validate_type_specifics' keys them
        """
        errors = super(ToscaInterfaceTypeValidator, self).complete_type_refinements(interface_type)
        errors.update(self.complete_operation_refinements(interface_type))
        return errors


    def validate_type_specifics(self, interface_type: "ToscaInterfaceType") -> dict:
        """Validate definitions that are specific to a interface type
        definition:

        - Call 'validate_type_specifics' for the parent type
        - Make sure the interface type has valid inputs
        - Make sure the interface type has valid operation
          declarations

        Args:
          interface_type(ToscaInterfaceType): interface type
            definition to validate
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """

        logger.debug("Interface type '%s': validating", interface_type.name)

        # Is this a valid managed type entity?
        validation_errors = super(ToscaInterfaceTypeValidator, 
                                  self).validate_type_specifics(interface_type)

        # Does this interface type have valid input declarations?
        validator = get_validator('ToscaPropertyDeclaration')
        errors = self.validate_declarations(interface_type,
                                            'inputs', validator)
        if errors:
            logger.error("Interface %s: Invalid input declarations", 
                         interface_type.name)
            validation_errors['inputs'] = errors

        # Does this interface type have valid output declarations?
        errors = self.validate_declarations(interface_type,
                                            'outputs', validator)
        if errors:
            logger.error("Interface %s: Invalid output declarations", 
                         interface_type.name)
            validation_errors['outputs'] = errors

        # Does this interface type have valid operation declarations?
        validator = get_validator('ToscaOperationDeclaration')
        errors = self.validate_declarations(interface_type, 'operations', 
                                            validator)
        if errors:
            logger.error("Interface %s: Invalid operations", 
                         interface_type.name)
            validation_errors['operations'] = errors

        # Does this interface type have valid notification declarations?
        errors = self.validate_declarations(interface_type, 'notifications', 
                                            validator)
        if errors:
            logger.error("Interface %s: Invalid notifications", 
                         interface_type.name)
            validation_errors['notifications'] = errors

        # All done
        return validation_errors




