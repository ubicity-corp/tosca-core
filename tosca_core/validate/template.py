"""
ToscaTemplateValidator class
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2014-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger = logging.getLogger(__name__)

# Validator support
from .validator import ToscaValidator

# Exception support
import tosca_core.models.exceptions as te


class ToscaTemplateValidator(ToscaValidator):
    """The ToscaTemplateValidator class validates template entities in
    Tosca service templates against their declarations. 
    """

    def __init__(self) -> None:
        """Constructor
        """
        super(ToscaTemplateValidator, self).__init__()


    def validate_typed_template(self, template: object) -> dict:
        """Validate a template that is 'self-declaring' (meaning it declares
        its own type). Node templates, relationship templates,
        workflows, groups, policies, and artifacts fall in this
        category. 

        The validator first obtains and validates a declaration for
        the template, and then validates the template against that
        declaration.

        Args: 
          template(ToscaTemplate): template to validate
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """

        validation_errors = {}

        # First, get the template declaration
        error = self.validate_template_type(template)
        if error:
            validation_errors['type'] = error
            self.add_line_number(validation_errors, template)
            return validation_errors
        
        # Is this a valid template for its declaration?
        try:
            validation_errors = self.validate_template(template)
        except Exception as e:
            logger.error("error while validating typed template '%s': %s", 
                         template.declaration.name, e)
            return "validator error ({0})".format(str(e))

        # All done
        self.add_line_number(validation_errors, template)
        return validation_errors


    def validate_template_type(self, template: object) -> object:
        """Validate the type for a template by creating a corresponding
        declaration.

        Args: 
          template(ToscaTemplate): template to validate
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """
        # Get the template declaration based on its type.
        try:
            declaration = template.declaration
        except te.TypeNotNamed as e:
            # A template whose type must be named and is not
            logger.debug("'%s' does not name its type", template.name)
            return str(e)
        except AttributeError as e:
            # Self-declaring template without a type
            logger.debug("'%s' does not have type: %s", template.name, e)
            return 'not specified' 
        except te.TypeNotFound:
            # Type not found
            logger.error("'%s' has unknown type '%s'", template.name, template._type)
            return 'not found' 
        except Exception as e:
            logger.error("'%s' error finding type: %s", template.name, str(e))
            return str(e) 

        # Everything OK
        return None


    def validate_template_type_refinement(self, declaration: object, template: object) -> dict:
        """Check if the type of the template is valid for the
        specified declaration.

        Note that templates don't have to define a type, but if they
        do that type has to be compatible with the type of the
        declaration.

        Args:
          declaration(ToscaDeclaration): declaration for the template
            for which to validate the type
          template(ToscaTemplate): template for which to validate the
            type

        Returns:
          (possibly empty) dict of validation errors

        Raises:
          None
        """
        validation_errors = {}

        # Check if this template includes a declaration
        try:
            template_declaration = template.declaration
        except AttributeError:
            # No declaration defined in the template, which is
            # OK. Just use the provided declaration from now on.
            template.declaration = declaration
            return validation_errors
        except te.TypeNotFound:
            # Type not found
            logger.error("'%s' has unknown type '%s'", template.name, template._type)
            validation_errors[template._type] = 'not found'
        except Exception as e:
            logger.error("'%s' error finding type: %s", template.name, str(e))
            validation_errors[template._type] = str(e) 

        # Make sure new type is compatible with the type in the
        # original declaration
        if not template_declaration.has_type(declaration.type_entity):
            logger.error("Template '%s': type '%s' incompatible with '%s'",
                         declaration.name, template_declaration.type,
                         declaration.type)
            error = "incompatible with {0}".format(declaration.type)
            validation_errors[template_declaration.type] = error
            return validation_errors
        
        # Augment the template's declaration with the declaration
        # against which to validate the template.
        template.declaration.merge_augmented_declaration(declaration)

        # Everything OK
        return validation_errors


    def validate_template(self, template: object) -> dict:
        """Check if a template is valid for the specified declaration

        Args: 
          declaration(ToscaDeclaration): declaration for the template
            that needs to be validated
          template(ToscaTemplate): template to validate
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """
        validation_errors = {}

        # Check property templates against the declaration
        errors = self.validate_properties(template)
        if errors:
            logger.error("Template '%s' of type '%s' has invalid properties",
                         template.declaration.name, template.declaration.type)
            validation_errors['properties'] = errors

        # Check attribute templates against the declaration
        errors = self.validate_attributes(template)
        if errors:
            logger.error("Template '%s' of type '%s' has invalid attributes",
                         template.declaration.name, template.declaration.type)
            validation_errors['attributes'] = errors

        # Everything OK
        return validation_errors


    def validate_properties(self, template: object) -> object:
        """Check if the properties defined in the template are valid for the
        specified declaration. If so, update any function values to
        the internal function syntax.

        Args:
          declaration(ToscaDeclaration): declaration for the
            template for which to validate properties
          template(ToscaTemplate): template for which to
            validate properties
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """
        logger.debug("%s: validating properties", template.name)
        properties = template.properties

        # Validate property values against the template
        # declaration. We call this even when the template does not
        # define properties since we need to check if all required
        # properties are present. We need to pass the template as the
        # context within which to evaluate any intrinsic function
        # calls.
        try:
            template.properties = template.declaration.validate_property_templates(template, properties)
        except te.ValidationError as e:
            return e.errors
        except Exception as e:
            error = 'validator error ({0})'.format(str(e))
            return error
        # All done
        return None


    def validate_attributes(self, template: object) -> dict:
        """Check if the attributes defined by the template are valid for the
        specified declaration. If so, update any function values to
        the internal function syntax.

        Args:
          declaration(ToscaDeclaration): declaration for the
             template for which to validate attributes
          template(ToscaTemplate):  template for which to
            validate attributes
        Return:
          (possibly empty) dict of valiation errors
        Raises:
          None
        """
        # Get attribute declarations
        attribute_declarations = template.declaration.get_attribute_declarations()

        # Validate each attribute against its attribute declaration
        validation_errors = dict()
        validated = dict()
        attributes = template.attributes
        for attribute_name, attribute_value in attributes.items():
            logger.debug("Template '%s': validating attribute '%s'", 
                         template.declaration.name, attribute_name)
            try:
                # Find corresponding declaration
                attribute_declaration = attribute_declarations[attribute_name]

                # Make sure the attribute value is valid for the
                # attribute declaration.
                try:
                    validated[attribute_name] = attribute_declaration.validate_value(
                        template, attribute_value)
                except te.ValidationError as e:
                    validated[attribute_name] = attribute_value
                    logger.error("'%s' attribute '%s': '%s' is invalid value for %s",
                                 template.declaration.name, attribute_name,
                                 attribute_value, attribute_declaration.type)
                    validation_errors[attribute_name] = e.errors
            except KeyError:
                logger.error("'%s': undefined attribute '%s'", 
                             template.declaration.name, attribute_name)
                validation_errors[attribute_name] = 'not previously defined'

        # All done
        template.attributes = validated
        return validation_errors
