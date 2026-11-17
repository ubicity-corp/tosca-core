"""
ToscaDeclarationValidator class
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2014-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger = logging.getLogger(__name__)

# Exception support
import tosca_core.models.exceptions as te

# Validator support
from . import get_validator
from .validator import ToscaValidator


class ToscaDeclarationValidator(ToscaValidator):
    """The ToscaDeclarationValidator class validates TOSCA declarations
    in type definitions or in other declarations.
    """

    def __init__(self) -> None:
        """Constructor
        """
        super(ToscaDeclarationValidator, self).__init__()


    def validate_declaration(self, type_entity: object, declaration: object) -> dict:
        """Check if a declaration is valid for the specified type_entity

        Args: 
          type_entity(ToscaType): entity within which this declaration
            occurs
          declaration(ToscaDeclaration): declaration to validate

        Returns:
          (possibly empty) dict of validation errors

        Raises:
          None
        """

        validation_errors = {}

        # First, check to see if this declaration has a valid type
        errors = self.validate_type(type_entity, declaration)
        if errors:
            logger.error("Declaration '%s': invalid type", declaration.name)
            validation_errors['type'] = errors
        else:
            # The declaration has a valid type. Validate against that
            # type
            validation_errors = self.validate_for_type(type_entity, declaration)
            
        # If there are errors, add line number if it exists
        self.add_line_number(validation_errors, declaration)

        # All done
        return validation_errors


    def validate_type(self, type_entity: object, declaration: object) -> dict:
        """Check if the type of a declaration is valid.

        Args: 
          type_entity(ToscaType): entity within which this declaration
            occurs
          declaration(ToscaDeclaration): declaration to validate

        Returns:
          (possibly empty) dict of validation errors

        Raises:
          None
        """

        validation_errors = {}

        # Does this declaration have type?
        try:
            # Set the type based on the 'type' keyname
            declaration_type_entity = declaration.type_entity
        except te.TypeNotFound:
            # type not found
            logger.error("Declaration '%s': type %s not found", 
                         declaration.name, declaration._type)
            validation_errors[declaration._type] = 'not found'
        except AttributeError as e:
            # declaration entity doesn't have a type
            logger.debug("Declaration '%s': no type declared: %s", 
                         declaration.name, str(e))
            # Try to find the implied type
            errors = self.validate_implied_type(type_entity, declaration)
            if errors:
                logger.error("Declaration '%s': no type declared and unable to determine implied type", 
                             declaration.name)
                return errors
        except Exception as e:
            logger.error("Declaration '%s': error getting type: %s", 
                         declaration.name, e)
            return "validator error ({0})".format(e)

        # Everything OK
        return validation_errors


    def validate_implied_type(self, type_entity: object, declaration: object) -> object:
        """Called when there is no type specified in the declaration with the
        goal of determining the implied type from the rest of the
        declaration.

        Validators for declarations that support implied types should
        override this method.

        Args: 
          type_entity(ToscaType): entity within which this declaration
            occurs
          declaration(ToscaDeclaration): declaration to validate

        Returns:
          (possibly empty) dict of validation errors

        Raises:
          None
        """
        logger.debug("Declaration '%s': getting implied type", 
                     declaration.name)
        return 'not specified'


    def validate_for_type(self, type_entity: object, declaration: object) -> dict:
        """Check if a declaration is valid for the given type. The declaration
        must reference a type that has already been validated. 

        Args: 
          type_entity(ToscaType): entity within which this declaration
            occurs
          declaration(ToscaDeclaration): declaration to validate

        Returns:
          (possibly empty) dict of validation errors

        Raises:
          None

        """

        validation_errors = {}

        # Does this declaration have valid property augmentations?
        validator = get_validator('ToscaPropertyDeclaration')
        errors = self.validate_augmentations(type_entity, declaration,
                                             'properties', validator)
        if errors:
            logger.error("Declaration '%s': invalid property augmentations", 
                         declaration.name)
            validation_errors['properties'] = errors
        else:
            self.resolve_functions_in_property_declarations(declaration)
            
        # Does this declaration have valid attribute augmentations?
        errors = self.validate_augmentations(type_entity, declaration,
                                             'attributes', validator)
        if errors:
            logger.error("Declaration '%s': invalid attribute augmentations", 
                         declaration.name)
            validation_errors['attributes'] = errors
        else:
            self.resolve_functions_in_attribute_declarations(declaration)
            
        # Everything OK
        return validation_errors


    def complete_augmentations(self, containing_entity: object, declaration: object, attribute: str, validator: object) -> dict:
        """Check and complete each augmentation in the specified attribute
        of a declaration, before anything is validated.

        An augmentation inside a declaration refines the declaration of
        the same name in the declaration's type. One that refines nothing
        is left for 'validate_augmentations' to report, as is a
        declaration whose type cannot be resolved.

        Args: 
          containing_entity(ToscaType): entity that contains the
            declaration within which the augmentations occur
          declaration(ToscaDeclaration): declaration that contains the
            augmentations to complete
          attribute(str): name of the declaration attribute that stores
            them
          validator(ToscaValidator): validator for the augmentations,
            which checks and completes each one

        Returns:
          (possibly empty) dict of validation errors, keyed the way
          'validate_augmentations' keys them
        """
        validation_errors = {}
        augmentations = getattr(declaration, attribute, None) or {}
        for augmentation_name, augmentation in augmentations.items():
            try:
                entity_to_augment = declaration.get_entity_declaration_to_augment(
                    attribute, augmentation_name)
            except KeyError:
                # Reported by validation. What it holds may still refine
                # the declarations of its own type.
                entity_to_augment = None
            try:
                if entity_to_augment is not None:
                    errors = validator.complete_augmentation(declaration,
                                                             augmentation_name,
                                                             entity_to_augment,
                                                             augmentation)
                    if errors:
                        logger.error("'%s': '%s': invalid %s augmentation '%s'",
                                     containing_entity.name, declaration.name,
                                     attribute, augmentation_name)
                        validation_errors[augmentation_name] = errors
                        continue
                errors = validator.complete_nested_refinements(declaration, augmentation)
                if errors:
                    logger.error("'%s': '%s': invalid nested refinement in %s '%s'",
                                 containing_entity.name, declaration.name,
                                 attribute, augmentation_name)
                    validation_errors[augmentation_name] = errors
            except Exception as e:
                logger.error("'%s': '%s': error while completing %s augmentation '%s': %s", 
                             containing_entity.name, declaration.name,
                             attribute, augmentation_name, e)
                validation_errors[augmentation_name] = "validator error ({0})".format(e)
        return validation_errors


    def validate_augmentations(self, containing_entity: object, declaration: object, attribute: str, validator: object) -> dict:
        """Check if a declaration entity has valid augmentations in the
        specified attribute.

        Every augmentation is checked and completed by
        'complete_augmentations' before anything is validated, so nothing
        is merged here.

        Args:
          containing_entity(ToscaType): entity that contains the
            declaration within which this augmentation occurs
          declaration(ToscaDeclaration): declaration that contains the
            augmentation to validate
          attribute(str): name of the containing entity attribute that
            stores the augmentations to validate
          validator(ToscaValidator): validator to use for each of the
            augmentations

        Returns:
          (possibly empty) dict of validation errors

        Raises:
          None
        """

        validation_errors = {}

        # Does this declaration augment entities in the specified
        # attribute?
        try:
            augmentations = getattr(declaration, attribute)
        except AttributeError:
            # No property augmentations
            return validation_errors

        # Validate each augmentation
        for augmentation_name, augmentation in augmentations.items():
            try:
                # First, find the entity to augment
                entity_to_augment = declaration.get_entity_declaration_to_augment(
                    attribute, augmentation_name)
            except KeyError:
                validation_errors[augmentation_name] = 'not found in {0} to augment'.format(attribute)
                continue
            try:
                # Validate the augmentation, which was checked and merged
                # before validation began
                self.assert_augmentation_complete(
                    declaration, attribute, augmentation_name,
                    entity_to_augment, augmentation)
                errors = validator.validate_completed_augmentation(
                    declaration, augmentation_name, entity_to_augment, augmentation)
                if errors:
                    logger.error("'%s': '%s': invalid %s augmentation '%s'",
                                 containing_entity.name, declaration.name, 
                                 attribute, augmentation_name)
                    validation_errors[augmentation_name] = errors

            except Exception as e:
                logger.error("'%s': '%s': error while validating %s augmentation '%s': %s", 
                             containing_entity.name, declaration.name,
                             attribute, augmentation_name, e)
                validation_errors[augmentation_name] = "validator error ({0})".format(e)

        # Everything OK
        return validation_errors


    def resolve_functions_in_property_declarations(self, declaration: object) -> None:
        """Resolve functions in property values to the internal function
        syntax if necessary. TODO: move to property declaration
        validator.
        """
        # Upgrade each property declaration
        properties = declaration.properties
        for property_name, property_declaration in properties.items():
            property_declaration.resolve_functions_in_declared_values(declaration)


    def resolve_functions_in_attribute_declarations(self, declaration: object) -> None:
        """Resolve functions in attribute values to the internal function
        syntax if necessary.
        """
        # Upgrade each attribute declaration
        attributes = declaration.attributes
        for attribute_name, attribute_declaration in attributes.items():
            attribute_declaration.resolve_functions_in_declared_values(declaration)
