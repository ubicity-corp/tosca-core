"""
ToscaManagedTemplateValidator class
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2014-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger = logging.getLogger(__name__)

# Exception support
import tosca_core.models.exceptions as te

# For count range checking
from tosca_core.models.function import ToscaFunction

# Cached lookups for TOSCA built-in data types
import tosca_core.models.builtin_types as builtin_types

# Validator support
from . import get_validator
from .template import ToscaTemplateValidator


class ToscaManagedTemplateValidator(ToscaTemplateValidator):
    """The ToscaManagedTemplateValidator class validates TOSCA managed
    templates (i.e. node templates and relationship
    templates). Specifically, it makes sure that any interface
    definitions in the node or relationship templates are valid.
    """

    def __init__(self) -> None:
        """Constructor
        """
        super(ToscaManagedTemplateValidator, self).__init__()


    def validate_template(self, managed_template: object) -> dict:
        """Check if a managed template is valid for the specified managed
        declaration

        Args:
          managed_declaration(ToscaManagedDeclaration): declaration
            for the managed template to validate
          managed_template(ToscaManagedTemplate): managed template to
            validate
        Returns:
          (possibly empty) dict of validation errors

        """

        # Is this a valid template?
        validation_errors = super(ToscaManagedTemplateValidator,
                                  self).validate_template(managed_template)

        # Everything OK
        return validation_errors


    def validate_count_value(self, managed_template: object) -> object:
        """Check if a managed template includes a valid count value. This
        method is defined in the managed template validator, but it is
        only called in the node template validator and the
        relationship template validator.

        Args: 
          managed_declaration(ToscaManagedDeclaration): Tosca managed
            declaration against which to validate the managed_template
          managed_template(ToscaManagedTemplate): Tosca
            managed_template that includes the count value to validate
        Returns:
          (Possibly empty) dict of validation errors
        Raises:
          None
        """

        # Do we have a count value?
        try:
            count = managed_template.count
        except AttributeError:
            # No count value to validate
            return {}

        # Create 'integer' declaration against which to validate 'count'.
        integer_type = builtin_types.get('integer')
        declaration = integer_type.create_declaration(name='count')

        # Count function values in requirement definitions must be
        # evaluated in the context of the source node, since there can
        # only be one single count value for all requirements of the
        # same name.
        try:
            context = managed_template.SOURCE()
        except Exception:
            context = managed_template
        
        # Validate count value
        try:
            managed_template.count =  declaration.validate_value(context, count)
        except te.ValidationError as e:
            return e.errors

        # All done
        return None

    
    def validate_interfaces(self, managed_template: object) -> dict:
        """Make sure a managed template has valid interface templates for all
        interfaces defined in the managed type. This may require
        synthesizing interface templates. 

        Note that this method is part of the ToscaManagedTemplate
        class, but it must be called explicitly by the subclasses to
        ensure proper sequencing of the validation steps.

        Args:
          managed_declaration(ToscaManagedDeclaration): managed
            declaration for the managed template for which to validate
            interfaces
          managed_template(ToscaManagedTemplate): managed template for
            which to validate interfaces

        Returns:
          (possibly empty) dict of validation errors

        Raises:
          None
        """
        # Get interface template validator
        validator = get_validator('ToscaInterfaceTemplate')

        # Get interface declarations
        interface_declarations = managed_template.declaration.get_interface_declarations()

        # Make sure all declared interfaces have a valid corresponding
        # interface template
        validation_errors = {}
        interfaces = managed_template.interfaces
        for interface_name, interface_declaration in interface_declarations.items():
            logger.debug("'%s' (%s): validating interface '%s'",
                         managed_template.declaration.name, managed_template.declaration.type,
                         interface_name)
            try:
                # Check if interface template is defined in the
                # managed template.
                interface = interfaces[interface_name]
                # Track service and declaration in interface template
                interface.declaration = interface_declaration
            except (AttributeError, KeyError):
                # No interface template defined in the managed
                # template. Create a template for this declared
                # interface. Note that this assumes that the interface
                # declaration does not include any required properties
                # without a default value.
                logger.debug("'%s': synthesizing required interface '%s'",
                             managed_template.declaration.name, interface_name)
                interface = interface_declaration.create_template()
                managed_template.interfaces[interface_name] = interface
                
            # Validate interface template against the
            # declaration. Note that we do this for synthesized
            # interface templates as well to make sure we're not
            # missing any required properties.
            try:
                errors = validator.validate_template(interface)
                if errors:
                    logger.error("Managed template '%s': invalid interface '%s'", 
                                 managed_template.name, interface_name)
                    validation_errors[interface_name] = errors
            except Exception as e:
                logger.error("'%s': error while validating interface '%s': %s",
                             managed_template.declaration.name, interface_name, e)
                validation_errors[interface_name] = 'validator error <{0}>'.format(str(e))


        # Make sure we don't have any interfaces defined in the
        # managed template that don't have a corresponding
        # declaration.
        for interface_name, interface in interfaces.items():
            # Find interface declaration
            try:
                interface_declaration = interface_declarations[interface_name]
            except KeyError:
                logger.error("Managed template '%s': '%s' does not declare interface '%s'", 
                             managed_template.name, managed_template.declaration.type, interface_name)
                validation_errors[interface_name] = 'not previously defined'

        # Everything OK
        return validation_errors


    def validate_target_query_filter(self, managed_template: object) -> dict:
        """Check if a managed template defines a valid node filter.

        Args: 
          managed_declaration(ToscaManagedDeclaration): Tosca
            requirement or node declaration against which to validate
            the template
          managed_template(ToscaManagedTemplate): Tosca template that
            includes the target query for which to validate the filter

        Returns:
          (possibly empty) dict of validation errors

        Raises:
          None
        """
        # Do we have a node filter?
        try:
            node_filter = managed_template.node_filter
            if not node_filter: return {}
        except AttributeError:
            # No node_filter to validate
            return {}

        errors, canonical = self._validate_boolean_expression(managed_template, node_filter, 'node_filter')
        if errors:
            return errors
        managed_template.resolved_filter = canonical
        return {}

