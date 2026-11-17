"""
ToscaOperationDeclarationValidator class
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2016-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger = logging.getLogger(__name__)

# Type hint support
from typing import Any, Optional

# Exception support
import tosca_core.models.exceptions as te

# Validator support
from . import get_validator
from .validator import ToscaValidator

"""
 Operation declarations can exist in:

 1. Interface type definitions. Operation declarations inside
    interface type definitions can either be:

    - Operation definitions that define new operations. 
    - Operation refinements that refine operations that were
      previously defined inside a base type

    We need to check if the operation already exists to determine
    whether an operation declaration is a new operation definition or
    an operation refinement. This is done inside the
    'validate_declarations' method in the base ToscaValidator
    class. The 'validate_declarations' method calls either the
    'validate_declaration' method (for new declarations) or the
    'validate_augmentation' method (for refinements)
 
 2. Interface declarations inside node type or relationship type
    definitions. In this case, operation declarations are *always*
    operation refinements and they will always be validated using the
    'validate_augmentation' method.

The following rules apply:

Operation Definitions
---------------------
- There must not be an implementation
- Input declarations are always new input definitions, never input
  refinements. Input declarations must follow property declaration
  syntax, not parameter declaration syntax. This means that:
  - A type is always required
  - A fixed value assignment is not allowed

Operation Refinements
---------------------
- Operation implementations are allowed but not required
- Input declarations can either be:
  - A new input definition. Input definition syntax is as follows:
    - For operation refinements inside interface type definitions,
      input definitions follow property declaration syntax
    - For operation refinements inside interface definitions in node
      or relationship type definitions, input definitions follow the
      parameter declaration syntax.
  - An input refinement that refines an input previously defined for
    the operation. Input refinements always follow the parameter
    declaration syntax

"""

class ToscaOperationDeclarationValidator(ToscaValidator):
    """The ToscaOperationDeclarationValidator class validates new TOSCA
    operation declarations in interface types
    """

    def __init__(self) -> None:
        """Constructor
        """
        super(ToscaOperationDeclarationValidator, self).__init__()


    def validate_declaration(self, interface_type: "Any", operation: "Any") -> dict:
        """Check if a operation declaration is valid. This method is called
        for a declaration of a new operation in an interface type
        definition. This means that all input and output definitions
        in this declaration are new definitions as well, not
        refinements. This also means there must not be any operation
        implementation definitions.

        Args: 
         interface_type(ToscaInterfaceType): the interface type that
           defines this operation
         operation(ToscaOperationDeclaration): Tosca operation
          declaration to validate
        """

        logger.debug("'%s': validating operation declaration %s",
                     interface_type.name, operation.name)

        validation_errors = {}

        # Validate input declarations
        errors = self.validate_inputs(interface_type, operation)
        if errors:
            logger.error("Interface %s operation %s: Invalid input declarations", 
                         interface_type.name, operation.name)
            validation_errors['inputs'] = errors

        # Validate output declarations
        errors = self.validate_outputs(interface_type, operation)
        if errors:
            logger.error("Interface %s operation %s: Invalid output declarations", 
                         interface_type.name, operation.name)
            validation_errors['outputs'] = errors

        # Make sure there is not operation implementation definition
        try:
            self.assert_not_present(operation, 'implementation')
        except Exception:
            validation_errors['implementation'] = 'not allowed here'

        # Everything OK
        self.add_line_number(validation_errors, operation)
        return validation_errors


    def validate_augmentation(self, interface_declaration: "Any", operation_name: str,
                              operation_declaration_to_augment: "Any", operation: "Any") -> dict:
        """Check if a operation declaration is a valid refinement of a
        previously-defined operation. The refinement can be defined in:

        1. A derived interface type
        2. An interface definition inside a node type or relationship
           type definition

        In the first case, the refinement can:
        - add new input definitions
        - refine previously-defined inputs

        In the second case, the refinement can also add output mappings

        Args: 
         operation(ToscaOperationDeclaration): Tosca operation
          declaration to validate
        """

        validation_errors = {}

        # Validator expects 'name' attribute to be set
        setattr(operation, 'name', operation_name)

        # Validate inputs
        errors = self.validate_inputs(interface_declaration, operation)
        if errors:
            logger.error("Interface '%s' operation '%s': Invalid input declarations", 
                         interface_declaration.name, operation_name)
            validation_errors['inputs'] = errors

        # Validate outputs
        errors = self.validate_outputs(interface_declaration, operation)
        if errors:
            logger.error("Interface '%s' operation '%s': Invalid output declarations", 
                         interface_declaration.name, operation_name)
            validation_errors['outputs'] = errors

        # Validate operation implementation
        validator = get_validator('ToscaOperationImplementation')
        try:
            errors = validator.validate_implementation(operation)
            if errors:
                logger.error("Interface %s operation %s: Invalid implementation", 
                             interface_declaration.name, operation.name)
                validation_errors['implementation'] = errors
        except Exception as e:
            validation_errors['implementation'] = 'internal error <{0}>'.format(str(e))
        # Everything OK
        self.add_line_number(validation_errors, operation)
        return validation_errors

        
    def validate_completed_augmentation(self, interface: "Any", operation_name: str,
                                        operation_declaration_to_augment: "Any", operation: "Any") -> dict:
        """Validate an operation refinement whose input and output
        refinements pass one has already checked and completed.

        An operation refinement is not validated as a new operation would
        be -- 'validate_declaration' refuses an implementation, which a
        refinement may carry -- so this takes the refinement path, with
        the nested inputs and outputs neither checked nor merged again.
        The operation itself is never merged: only its inputs and outputs
        are.
        """
        return self.validate_augmentation(interface, operation_name,
                                          operation_declaration_to_augment, operation)


    def validate_inputs(self, interface: "Any", operation_declaration: "Any") -> Optional[dict]:
        """Check if an operation declaration in an interface has valid input
        declarations. The refinements among them were checked and
        completed by pass one.
        """

        # Make sure we have inputs
        try:
            inputs = operation_declaration.inputs
        except AttributeError:
            logger.debug("%s: no inputs to validate", operation_declaration.name)
            return None

        # Make sure inputs are not already defined at the interface
        # level
        errors = {}
        for input_name, input_declaration in inputs.items():
            try:
                interface_input = interface.get_input_declaration(input_name)
                errors[input_name] = 'already defined at interface level'
            except KeyError:
                # Not defined at interface level
                pass
        if errors: return errors

        # Validate input declarations. Input declarations can define
        # new inputs or refine previously-defined inputs. The
        # 'validate_declarations' method handles both.
        validator = get_validator('ToscaPropertyDeclaration')
        errors = self.validate_declarations(operation_declaration, 'inputs', validator)
        if not errors:
            # resolve functions in inputs if necessary
            self.resolve_functions_in_input_declarations(interface, operation_declaration)

        # All done
        return errors


    def validate_outputs(self, interface: "Any", operation_declaration: "Any") -> Optional[dict]:
        """Check if an operation declaration in an interface has valid output
        declarations. The refinements among them were checked and
        completed by pass one.
        """

        # Make sure we have outputs
        try:
            outputs = operation_declaration.outputs
        except AttributeError:
            logger.debug("%s: no outputs to validate", operation_declaration.name)
            return None

        # Make sure outputs are not already defined at the interface
        # level
        errors = {}
        for output_name, output_declaration in outputs.items():
            try:
                interface_output = interface.get_output_declaration(output_name)
                errors[output_name] = 'already defined at interface level'
            except KeyError:
                # Not defined at interface level
                pass
        if errors: return errors

        # Upgrade mappings in output declarations to the Version 2.0
        # TOSCA Path syntax.
        self.upgrade_mappings_in_outputs(interface, operation_declaration)

        # Validate output declarations. Output declarations can define
        # new outputs or refine previously-defined outputs. The
        # 'validate_declarations' method handles both.
        validator = get_validator('ToscaPropertyDeclaration')
        errors = self.validate_declarations(operation_declaration, 'outputs', validator)

        # All done
        return errors
    

    def resolve_functions_in_input_declarations(self, interface: "Any", operation_declaration: "Any") -> None:
        """Resolve functions in inputs to the internal function syntax if necessary.
        """
        # Resolve each input declaration
        inputs = operation_declaration.inputs
        for input_name, input_declaration in inputs.items():
            input_declaration.resolve_functions_in_declared_values(interface)


    def upgrade_mappings_in_outputs(self, interface: "Any", operation_declaration: "Any") -> None:
        """Upgrade output mappings to the new TOSCA Path syntax.
        """
        if (not interface.tosca_version or
            not interface.tosca_version.startswith("tosca_simple_yaml")):
            # Nothing to do
            return 

        # We have a Version 1.x file. Upgrade each output declaration
        outputs = operation_declaration.outputs
        for output_name, output_declaration in outputs.items():
            output_declaration.upgrade_tosca_path_in_mapping(interface)
