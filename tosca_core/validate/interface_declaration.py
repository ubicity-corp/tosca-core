"""
ToscaInterfaceDeclarationValidator class
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2014-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger = logging.getLogger(__name__)

# Type hint support
from typing import Any

# Validator support
from . import get_validator
from .declaration import ToscaDeclarationValidator

# Types on which this validator depends
from tosca_core.models.interface_declaration import ToscaInterfaceDeclaration


class ToscaInterfaceDeclarationValidator(ToscaDeclarationValidator):
    """The ToscaInterfaceDeclarationValidator class validates TOSCA
    interfaces declarations in Node Types, Relationship Types, Node
    Declarations, or Relationship Declarations. Interface declarations
    declare the presence of an interface of a given type. The can add
    input parameters and augmentation operations.
    """

    def __init__(self) -> None:
        """Constructor
        """
        super(ToscaInterfaceDeclarationValidator, self).__init__()


    def validate_for_type(self, managed_type_entity: "Any", interface_declaration: "ToscaInterfaceDeclaration") -> dict:
        """Check if a interface declaration is valid for a given
        managed type entity

        Args: 
         interface(ToscaInterfaces): Tosca interface declaration to
          validate
        """

        logger.debug("Managed type '%s': validating interface declaration '%s'",
                     managed_type_entity.name, interface_declaration.name)

        # Is this a valid declaration
        validation_errors = super(ToscaInterfaceDeclarationValidator, 
                                  self).validate_for_type(managed_type_entity,
                                                          interface_declaration)

        # Does this interface declaration have valid input
        # declarations? Note that interface declarations can either
        # define new inputs or refine inputs previously-defined. The
        # 'validate_declarations' method checks for both.
        validator = get_validator('ToscaPropertyDeclaration')
        errors = self.validate_declarations(interface_declaration, 'inputs', validator)
        if errors:
            logger.error("%s: interface %s: Invalid input declarations", 
                         managed_type_entity.name, interface_declaration.name)
            validation_errors['inputs'] = errors
        else:
            # Resolve functions in input values to the internal function syntax.
            self.resolve_functions_in_input_declarations(interface_declaration)
        
        # Upgrade mappings in output declarations to the Version 2.0
        # TOSCA Path syntax.
        validator = get_validator('ToscaPropertyDeclaration')
        self.upgrade_mappings_in_outputs(interface_declaration)

        # Does this interface declaration have valid output
        # declarations? Note that interface declarations can either
        # define new outputs or refine outputs previously-defined. The
        # 'validate_declarations' method checks for both.
        errors = self.validate_declarations(interface_declaration, 'outputs', validator)
        if errors:
            logger.error("%s: interface %s: Invalid output declarations", 
                         managed_type_entity.name, interface_declaration.name)
            validation_errors['outputs'] = errors
        
        # Does this interface declaration have valid operation
        # augmentations?
        validator = get_validator('ToscaOperationDeclaration')
        errors = self.validate_augmentations(managed_type_entity,
                                             interface_declaration,
                                             'operations', validator)
        if errors:
            logger.error("%s: interface %s: Invalid operations", 
                         managed_type_entity.name, interface_declaration.name)
            validation_errors['operations'] = errors

        # Does this interface declaration have valid notification
        # augmentations?
        validator = get_validator('ToscaOperationDeclaration')
        errors = self.validate_augmentations(managed_type_entity,
                                             interface_declaration,
                                             'notifications', validator)
        if errors:
            logger.error("%s: interface %s: Invalid notifications", 
                         managed_type_entity.name, interface_declaration.name)
            validation_errors['notifications'] = errors

        # Everything OK
        return validation_errors


    def complete_augmentation(self, entity: "Any", interface_name: str,
                              interface_to_augment: "ToscaInterfaceDeclaration", interface_declaration: "ToscaInterfaceDeclaration") -> dict:
        """Check an interface augmentation and complete it by merging in the
        declaration it augments, before anything is validated. The merge
        carries the augmented declaration's inputs, outputs, operations
        and notifications into this one.

        The check reads what the augmentation states, so it gives the
        same verdict before the merge as after it.

        Args:
         entity(ToscaManagedType or ToscaManagedDeclaration): entity
           within which this interface is declared
         interface_name(str): name of the interface declaration
         interface_to_augment(ToscaInterfaceDeclaration): the interface
           declaration this one augments
         interface_declaration(ToscaInterfaceDeclaration): interface
           declaration to check and complete

        Returns:
          (possibly empty) dict of validation errors
        """
        errors = self.validate_interface_augmentation(interface_to_augment,
                                                      interface_declaration)
        if errors:
            logger.error("'%s': interface '%s': invalid augmentation",
                         entity.name, interface_name)
            self.add_line_number(errors, interface_declaration)
            return errors

        # Merge augmented interface declaration
        interface_declaration.merge_augmented_declaration(interface_to_augment)

        # Everything OK
        return {}


    def complete_refinements(self, interface_declaration: "ToscaInterfaceDeclaration") -> dict:
        """Check and complete the refinements inside an interface
        declaration: the inputs and outputs it refines, and the inputs and
        outputs of each of its operations and notifications, each of which
        finds what it refines through the declaration's interface type.

        'validate_for_type' then validates all of them without checking or
        merging them again.

        Args:
          interface_declaration(ToscaInterfaceDeclaration): interface
            declaration whose refinements to complete

        Returns:
          (possibly empty) dict of validation errors, keyed the way
          'validate_for_type' keys them
        """
        return self.complete_operation_refinements(interface_declaration)


    def validate_interface_augmentation(self, interface_to_augment: "ToscaInterfaceDeclaration", interface_declaration: "ToscaInterfaceDeclaration") -> dict:
        """Check if a interface declaration is a valid augmentation of a
        previously declared interface:

        - Make sure the interface augmentation does not have properties
        - Make sure the interface augmentation does not redefine the entry schema

        Args: 
          interface_to_augment(ToscaInterfaceDeclaration): Tosca
            interface declaration to augment
          interface_declaration(ToscaInterfaceDeclaration): Tosca
            interface declaration to validate
        """

        validation_errors = {}

        # Make sure type of augmentation is compatible with type of
        # augmented interface declaration
        try:
            type = interface_declaration._type
            if not interface_declaration.has_type(interface_to_augment.type_entity):
                logger.error("Interface '%s': augmentation type '%s' incompatible with '%s'",
                             type, interface_to_augment.type,
                             interface_declaration.name)
                validation_errors['type'] = '{0} is not compatible with {1}'.format(
                    type, interface_to_augment.type)
        except AttributeError:
            # No type specified. Augmentation will have the same type
            # as the type of the augmented entity
            pass

        # Everything OK
        return validation_errors


    def resolve_functions_in_input_declarations(self, interface_declaration: "ToscaInterfaceDeclaration") -> None:
        """Resolve functions in input values to the internal function syntax.
        """
        # Upgrade each input declaration
        inputs = interface_declaration.inputs
        for input_name, input_declaration in inputs.items():
            input_declaration.resolve_functions_in_declared_values(interface_declaration)


    def upgrade_mappings_in_outputs(self, interface_declaration: "ToscaInterfaceDeclaration") -> None:
        """Upgrade output mappings to the new TOSCA Path syntax.
        """
        if (not interface_declaration.tosca_version or
            not interface_declaration.tosca_version.startswith("tosca_simple_yaml")):
            # Nothing to do
            return 

        # We have a Version 1.x file. Upgrade each output declaration
        outputs = interface_declaration.outputs
        for output_name, output_declaration in outputs.items():
            output_declaration.upgrade_tosca_path_in_mapping(interface_declaration)
