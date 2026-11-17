"""
ToscaInterfaceTemplateValidator class
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2014-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger = logging.getLogger(__name__)

# Type hint support
from typing import Any, Optional

# Validator support
from . import get_validator
from .template import ToscaTemplateValidator

# Exception support
import tosca_core.models.exceptions as te

# Types on which this validator depends
from tosca_core.models.path import ToscaPath
import tosca_core.models.recognized_names as rn


class ToscaInterfaceTemplateValidator(ToscaTemplateValidator):
    """The ToscaInterfaceTemplateValidator class validates TOSCA
    interface templates in Node Templates, Relationship Templates, or
    Requirements: these refine interfaces declared in the associated
    declarations and/or types by adding input values and operation
    implementations.
    """

    def __init__(self) -> None:
        """Constructor
        """
        super(ToscaInterfaceTemplateValidator, self).__init__()


    def validate_template(self, interface: "Any") -> dict:
        """Check if a interface template is valid for its interface
        declaration

        Args: 
          interface(ToscaInterfaceTemplate): Tosca interface template
            to validate
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """

        # Is this a valid template
        validation_errors = super(ToscaInterfaceTemplateValidator,
                                  self).validate_template(interface)

        # Does this interface have valid inputs? This is a hack for
        # now, but if the interface is the standard or the configure interface
        # (either spelling) then make sure all required inputs are provided,
        # since the declarative workflow won't provide any additional
        # input values.
        check_required = (rn.is_standard_interface(interface.declaration.name) or \
                          rn.is_configure_interface(interface.declaration.name))
        errors = self.validate_inputs(interface.declaration, interface, interface,
                                      check_required)
                                      
        if errors:
            logger.error("Interface %s: Invalid input definitions", interface.declaration.name)
            validation_errors['inputs'] = errors

        # Upgrade mappings in output values
        self.upgrade_mappings_in_outputs(interface, interface)

        # Does this interface have valid outputs?
        errors = self.validate_outputs(interface.declaration, interface, interface)
        if errors:
            logger.error("Interface %s: Invalid output definitions", interface.declaration.name)
            validation_errors['outputs'] = errors

        # Does this interface have valid operations?
        errors = self.validate_operations(interface)
        if errors:
            logger.error("Interface %s: Invalid operations", interface.declaration.name)
            validation_errors['operations'] = errors

        # Does this interface have valid notifications?
        errors = self.validate_notifications(interface)
        if errors:
            logger.error("Interface %s: Invalid notifications", interface.declaration.name)
            validation_errors['notifications'] = errors

        # Everything OK
        return validation_errors


    def validate_inputs(self, declaration: "Any", template: "Any", context: "Any", check_required: bool = True) -> dict:
        """Check if an interface or operation template defines valid input
        values for the specified declaration

        Args: 
          declaration(ToscaInterfaceDeclaration or
            ToscaOperationDeclaration): declaration for the Tosca
            interface template or operation template that has the
            inputs to validate
          template(ToscaInterfaceTemplate or ToscaOperationTemplate):
            interface template or operation template for which to
            validate inputs
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """
        # Get input declarations
        input_declarations = declaration.get_input_declarations()

        # Get inputs. Handle the case where the interface template or
        # operation template has not been specified (in which case the
        # 'template' argument is None
        try:
            inputs = template.inputs
        except AttributeError:
            # Interface or operation template is None
            inputs = dict()
            
        # Validate all inputs against the input declarations
        validated = dict()
        validation_errors = dict()
        for input_name, input_value in inputs.items():
            logger.debug("%s: validating input %s", declaration.name, input_name)
            try:
                # Find input declaration
                input_declaration = input_declarations[input_name]

                # Make sure this input doesn't override a fixed
                # value defined in the input declaration
                try:
                    value = input_declaration.value
                    validation_errors[input_name] = 'overriding value from definition is not allowed'
                except AttributeError:
                    # No fixed value defined in the
                    # declaration. Validate input value against input
                    # declaration. Note that 'validate_value' never
                    # raises an exception, so there is no need to
                    # protect it here.
                    try:
                        validated[input_name] = input_declaration.validate_value(
                            context, input_value, check_presence=True)
                    except te.ValidationError as e:
                        logger.error("'%s' input '%s': '%s' is invalid value for %s",
                                     declaration.name, input_name, input_value,
                                     input_declaration.type)
                        validated[input_name] = input_value
                        validation_errors[input_name] = e.errors
            except KeyError:
                logger.error("'%s': undefined input '%s'", declaration.name, input_name)
                validation_errors[input_name] = 'not previously defined'
            except Exception as e:
                validation_errors[input_name] = 'validator error ({0})'.format(str(e))

        # If necessary, make sure all required inputs are present
        if check_required:
            for input_name, input_declaration in input_declarations.items():
                try:
                    input_value = inputs[input_name]
                except KeyError:
                    # No input template
                    if input_declaration.is_required():
                        logger.debug("Checking value for required input '%s'", input_name)
                        error = input_declaration.validate_value_presence(context, inputs)
                        if error:
                            validation_errors[input_name] = error

        # All done
        if inputs: template.inputs = validated
        return validation_errors


    def validate_outputs(self, declaration: "Any", template: "Any", context: "Any") -> dict:
        """Check if an interface template or operation template has valid
        output mappings for the specified interface declaration or
        operation declaration.

        Args: 
          declaration(ToscaInterfaceDeclaration or
            ToscaOperationDeclaration): declaration for the Tosca
            interface template or operation template that has the
            outputs to validate
          template(ToscaInterfaceTemplate or ToscaOperationTemplate):
            interface template or operation template for which to
            validate outputs
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """

        # Get output declarations
        output_declarations = declaration.get_output_declarations()

        # Get outputs. Handle the case where the interface template or
        # operation template has not been specified (in which case the
        # 'template' argument is None
        try:
            outputs = template.outputs
        except AttributeError:
            outputs = dict()
            
        # Validate all outputs against the (optional) output declarations
        validation_errors = {}
        for output_name, output_mapping in outputs.items():
            logger.debug("%s: validating output %s", declaration.name, output_name)
            try:
                # Find output declaration:
                output_declaration = output_declarations[output_name]
            except KeyError:
                # Output not previously-defined, which is OK
                output_declaration = None
            # Make sure output value maps to a valid property or
            # attribute
            errors = self.validate_output(context, output_declaration, output_mapping)
            if errors:
                validation_errors[output_name] = errors

        # Per TOSCA 2.0 §9.8, 'mapping' on an incoming parameter
        # (operation/notification output) is optional -- if no
        # mapping is given the output value is simply not captured
        # into a node/relationship attribute. Don't demand a mapping
        # for every declared output.

        # All done
        return validation_errors
        

    def validate_output(self, context: "Any", output_declaration: "Any", output_mapping: "Any") -> Optional[str]:
        """Check if an output mapping is valid within the provided context and
        compatible with the provided output declaration.

        Args:
          context(ToscaInterfaceTemplate): context within which to
            evaluate the mapping
          output_declaration(ToscaPropertyDeclaration): declaration
            against which to validate the mapping. Note that this
            argument may be None.
          output_mapping(ToscaPath): output mapping to validate
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """

        # First, make sure mapping is a valid path expression.
        try:
            path = ToscaPath(output_mapping)
        except TypeError:
            return 'improperly-formatted output mapping'

        # Find the attribute referenced by the output mapping
        attribute_declaration, error = self._resolve_attribute_declaration(context, path)
        if error:
            return error

        # Make sure types are compatible
        if output_declaration and \
           not attribute_declaration.has_type(output_declaration.type_entity):
            error = "mapped attribute type '{0}' incompatible with declarated type '{1}'".format(
                attribute_declaration.type, output_declaration.type)
            return error

        # All done
        return None


    def validate_operations(self, interface: "Any") -> dict:
        """Check if an interface template has valid operation templates for the
        specified interface declaration

        Args: 
          interface(ToscaInterfaceTemplate): interface template for
            which to validate operations
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """
        # Get operation declarations
        operation_declarations = interface.declaration.get_operation_declarations()

        # Make sure all declared operations have a valid corresponding
        # operation template
        validation_errors = dict()
        operations = interface.operations
        for operation_name, operation_declaration in operation_declarations.items():
            logger.debug("'%s' (%s): validating operation '%s'", interface.declaration.name,
                         interface.declaration.type, operation_name)
            try:
                # Check if operation template is defined in the
                # interface template.
                operation = operations[operation_name]
            except (AttributeError, KeyError):
                # No operation template defined in the managed
                # template.
                operation = None
                
            # Validate operation template against the
            # declaration. Note that we do this even if no operation
            # template is defined to make sure we're not missing any
            # required inputs.
            try:
                errors = self.validate_operation(operation_declaration, operation, interface)
                if errors:
                    logger.error("interface template '%s': invalid operation '%s'", 
                                 interface.name, operation_name)
                    validation_errors[operation_name] = errors
            except Exception as e:
                logger.error("'%s': error while validating operation '%s': %s",
                             interface.declaration.name, operation_name, e)
                validation_errors[operation_name] = 'validator error <{0}>'.format(str(e))

        # Make sure we don't have any operations defined in the
        # interface template that don't have a corresponding
        # declaration.
        for operation_name, operation in operations.items():
            # Find operation declaration
            try:
                operation_declaration = operation_declarations[operation_name]
            except KeyError:
                logger.error("interface template '%s': '%s' does not declare operation '%s'", 
                             interface.name, interface.declaration.type, operation_name)
                validation_errors[operation_name] = 'not previously defined'

        # All done
        return validation_errors


    def validate_notifications(self, interface: "Any") -> dict:
        """Check if an interface template has valid notification templates for the
        specified interface declaration

        Args: 
          interface(ToscaInterfaceTemplate): interface template for
            which to validate notifications
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """
        # Get notification declarations
        notification_declarations = interface.declaration.get_notification_declarations()

        # Make sure all declared notifications have a valid corresponding
        # notification template
        validation_errors = {}
        notifications = interface.notifications
        for notification_name, notification_declaration in notification_declarations.items():
            logger.debug("'%s' (%s): validating notification '%s'", interface.declaration.name,
                         interface.declaration.type, notification_name)
            try:
                # Check if notification template is defined in the
                # interface template.
                notification = notifications[notification_name]
            except (AttributeError, KeyError):
                # No notification template defined in the managed
                # template.
                notification = None
                
            # Validate notification template against the
            # declaration. Note that we do this even if no
            # notification template is defined to make sure we're not
            # missing any required inputs.
            try:
                errors = self.validate_operation(notification_declaration, notification, interface)
                if errors:
                    logger.error("interface template '%s': invalid notification '%s'", 
                                 interface.name, notification_name)
                    validation_errors[notification_name] = errors
            except Exception as e:
                logger.error("'%s': error while validating notification '%s': %s",
                             interface.declaration.name, notification_name, e)
                validation_errors[notification_name] = 'validator error <{0}>'.format(str(e))

        # Make sure we don't have any notifications defined in the
        # interface template that don't have a corresponding
        # declaration.
        for notification_name, notification in notifications.items():
            # Find notification declaration
            try:
                notification_declaration = notification_declarations[notification_name]
            except KeyError:
                logger.error("interface template '%s': '%s' does not declare notification '%s'", 
                             interface.name, interface.declaration.type, notification_name)
                validation_errors[notification_name] = 'not previously defined'

        # All done
        return validation_errors


    def validate_operation(self, operation_declaration: "Any", operation: "Any", context: "Any") -> dict:
        """Check if a operation template is valid for a given operation
        declaration

        Args: 
          operation_declaration(ToscaOperationDeclaration):
            declaration of the Tosca operation to be validated
          operation(ToscaOperationTemplate): Tosca operation template
            to validate. Note that this can be None (when the
            interface template does not include a template for this
            operation)
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """

        validation_errors = dict()

        # Does this operation have valid inputs? This is a hack for
        # now, but if the containing interface is the standard or the
        # configure interface then make sure all required inputs are provided,
        # since the declarative workflow won't provide any additional
        # input values.
        if operation_declaration._containing_interface_declaration:
            interface_name = operation_declaration._containing_interface_declaration.name
        elif operation_declaration._containing_interface_type:
            interface_name = operation_declaration._containing_interface_type.name
        else:
            # Should not happen
            interface_name = None
        check_required = interface_name and (rn.is_standard_interface(interface_name) or rn.is_configure_interface(interface_name))
        errors = self.validate_inputs(operation_declaration, operation, context,
                                      check_required)
        if errors:
            logger.error("%s: Invalid input definitions", operation_declaration.name)
            validation_errors['inputs'] = errors

        # Upgrade mappings in output values
        if operation:
            self.upgrade_mappings_in_outputs(operation, context)

        # Validate outputs
        errors = self.validate_outputs(operation_declaration, operation, context)
        if errors:
            logger.error("%s: Invalid output definitions", operation_declaration.name)
            validation_errors['outputs'] = errors

        # Validate operation implementation if specified
        if operation:
            validator = get_validator('ToscaOperationImplementation')
            errors = validator.validate_implementation(operation, operation_declaration)
            if errors:
                logger.error("%s: Invalid implementation", operation_declaration.name)
                validation_errors['implementation'] = errors

        # Everything OK
        return validation_errors


    def upgrade_mappings_in_outputs(self, template: "Any", context: "Any") -> None:
        """Upgrade output mappings to the new TOSCA Path syntax.
        """
        if (not template.tosca_version or
            not template.tosca_version.startswith("tosca_simple_yaml")):
            # Nothing to do
            return 

        # We have a Version 1.x file. Upgrade each output declaration
        outputs = template.outputs
        upgraded = dict()
        for output_name, output_template in template.outputs.items():
            # Upgrade mapping to the Version 2.0 TOSCA Path syntax.
            try:
                path = ToscaPath(output_template)
                upgraded[output_name] = path.upgrade(context)
            except Exception as e:
                upgraded[output_name] = output_template
                pass

        # All done
        template.outputs = upgraded

