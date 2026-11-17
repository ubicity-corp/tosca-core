"""
ToscaTypeValidator class
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2014-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger = logging.getLogger(__name__)

# Types used by this validator
from tosca_core.builtin.version import ToscaVersion

# Exception support
import tosca_core.models.exceptions as te

# Validator
from . import get_validator
from .validator import ToscaValidator


class ToscaTypeValidator(ToscaValidator):
    """The ToscaTypeValidator class validates TOSCA type entities
    """

    def __init__(self) -> None:
        """Constructor
        """
        super(ToscaTypeValidator, self).__init__()


    def validate_types(self, type_entities: list) -> dict:
        """Check if all type entities in a list are valid

        Args:
          type_entities(ToscaType[]): ordered list of type entities to
            validate

        Returns:
          (possibly empty) dict of validation errors

        Raises:
          None
        """

        validation_errors = {}
        for type_entity in type_entities:
            # Validate type entity
            errors = self.validate_type(type_entity)
            if errors:
                self.add_line_number(errors, type_entity)
                validation_errors[type_entity.name] = errors

        # All done
        return validation_errors


    def complete_refinements(self, type_entities: list) -> dict:
        """Check and complete the property and attribute refinements of each
        type, before any type is validated.

        A node type validates its capabilities, artifacts and requirements
        before its properties, so an expression in one of those would
        otherwise read a refined property before it has been completed.
        Completing every refinement first removes that dependence on
        order. 'validate_type_specifics' then validates the completed
        declarations without checking or merging them again.

        A type whose 'derived_from' is empty or names a type that cannot
        be resolved is left alone: 'validate_type' reports it and
        validates nothing further. A type that derives from nothing is
        not: it inherits nothing to refine, but the declarations it holds
        can still refine the types they use -- the properties inside a
        capability declaration refine those of the capability type.

        Args:
          type_entities(ToscaType[]): list of type entities, parents
            before the types that derive from them

        Returns:
          (possibly empty) dict of validation errors, keyed the way
          'validate_types' keys them
        """
        validation_errors = {}
        for type_entity in type_entities:
            if type_entity.is_builtin_type():
                continue
            try:
                derived_from = type_entity.derived_from
            except AttributeError:
                # Derives from nothing
                derived_from = None
            else:
                if not derived_from:
                    continue
                try:
                    type_entity.parent
                except Exception:
                    # A parent that cannot be resolved
                    continue
            errors = self.complete_type_refinements(type_entity)
            if errors:
                self.add_line_number(errors, type_entity)
                validation_errors[type_entity.name] = errors
        return validation_errors


    def complete_type_refinements(self, type_entity: object) -> dict:
        """Check and complete the refinements one type declares. For the
        ToscaType base class, these are its property and attribute
        refinements; derived classes extend this with their own.

        Args:
          type_entity(ToscaType): type entity whose refinements to
            complete

        Returns:
          (possibly empty) dict of validation errors, keyed the way
          'validate_type_specifics' keys them
        """
        errors = {}
        validator = get_validator('ToscaPropertyDeclaration')
        for attribute in ('properties', 'attributes'):
            attribute_errors = self.complete_declarations(type_entity, attribute, validator)
            if attribute_errors:
                errors[attribute] = attribute_errors
        return errors


    def validate_type(self, type_entity: object) -> dict:
        """Validate a type definition.

        Derived validators do not override this method; they override
        'validate_type_specifics', which this method calls. It validates
        what every type needs -- its version and its parent type -- and
        runs the type-specific validations only when the parent
        resolves, since they read declarations inherited through it.
        An override of 'validate_type_specifics' calls its parent
        class's first and then validates what its own class adds.

        The decision not to run the type-specific validations is why
        this is a separate method: a derived class overriding
        'validate_type' and calling super() first could not be stopped
        by an early return here, which exits only this method.

        Args: 
          type_entity(ToscaTypeEntity): type entity to validate
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None

        """

        validation_errors = {}

        # Make sure we have a valid version
        errors = self.validate_version(type_entity)
        if errors:
            validation_errors['version'] = errors

        # Make sure we have a valid parent type
        errors = self.validate_parent_type(type_entity)
        if errors:
            validation_errors['derived_from'] = errors
            # Don't validate any further if we have an invalid parent
            # type.
            return validation_errors

        # Validate type-specific definitions. Subclasses of ToscaType
        # are expected to override this method.
        errors = self.validate_type_specifics(type_entity)
        if errors:
            validation_errors.update(errors)
            
        # All done
        return validation_errors


    def validate_parent_type(self, type_entity: object) -> object:
        """If the type entity has a parent type, make sure the parent type
        exists.

        Args:
          type_entity(ToscaTypeEntity): type entity to validate
        Returns:
          - empty dict if there is no parent or the parent is valid
          - non-empty dict {<parent_name>: <reason>} for circular
            inheritance or a missing parent
          - a plain string when the 'derived_from' value itself is
            malformed (e.g. an empty string)
        Raises:
          None
        """

        try:
            derived_from = type_entity.derived_from
        except AttributeError:
            # No 'derived_from' specified. Nothing to validate.
            return {}

        # An explicit empty 'derived_from' is ambiguous: a 'derived_from'
        # key was supplied but with no value to derive from.
        if not derived_from:
            logger.error("Type '%s': 'derived_from' must not be empty",
                         type_entity.name)
            return 'must not be empty'

        validation_errors = {}
        try:
            logger.debug("Type '%s': validating parent type '%s'",
                         type_entity.name, derived_from)
            # Attempt to get the parent type
            type_entity.parent
        except te.CircularInheritance:
            logger.error("Type '%s': circular inheritance: type derives from itself",
                         type_entity.name)
            validation_errors[derived_from] = 'circular inheritance'
        except te.TypeNotFound:
            # Parent type not found
            logger.error("Type '%s': parent type %s not found",
                         type_entity.name, derived_from)
            validation_errors[derived_from] = 'not found'

        # parent type valid
        return validation_errors


    def validate_version(self, type_entity: object) -> dict:
        """If the type entity has a version, make sure it is valid

        Args: 
          type_entity(ToscaTypeEntity): type entity to validate
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """

        validation_errors = {}
        # Does version string parse into valid version object?
        try: 
            version_object = ToscaVersion(type_entity.version)
        except AttributeError:
            # The type entity does not have a version. Nothing to
            # validate
            logger.debug("Type '%s': no version specified", type_entity.name)
            pass
        except ValueError:
            logger.error("Type '%s': incorrectly formatted version string %s", 
                         type_entity.name, type_entity.version)
            validation_errors[type_entity.version] = 'incorrectly formatted'

        # Everything OK
        return validation_errors


    def validate_type_specifics(self, type_entity: object) -> dict:
        """Validate type definitions that are specific to each type of
        type. For the ToscaType base class, this means validating
        property and attribute declarations.

        Args: 
          type_entity(ToscaTypeEntity): type entity to validate
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """

        validation_errors = {}

        # Validate property and attribute declarations. Note that only
        # complex types are allowed to have properties and attributes
        if not type_entity.is_builtin_type():

            # Validate property declarations
            validator = get_validator('ToscaPropertyDeclaration')
            errors = self.validate_declarations(type_entity, 'properties', validator)
            if errors:
                validation_errors['properties'] = errors
            else:
                # Resolve functions in property values to the internal
                # function syntax.
                self.resolve_functions_in_property_declarations(type_entity)
                
            # Validate attribute declarations
            errors = self.validate_declarations(type_entity, 'attributes', validator)
            if errors:
                validation_errors['attributes'] = errors
            else:
                # Resolve functions in attribute values to the internal
                # function syntax.
                self.resolve_functions_in_attribute_declarations(type_entity)

            # A property is also an attribute of the same name, so no
            # attribute may be declared under a property's name, nor a
            # property under an inherited attribute's.
            errors = self.validate_attribute_names(type_entity)
            for keyname, clashes in errors.items():
                existing = validation_errors.setdefault(keyname, {})
                if isinstance(existing, dict):
                    existing.update(clashes)

        else:
            # Built-in types must not have properties
            if type_entity.properties:
                validation_errors['properties'] = "Built-in types can not be extended with properties"
            # Built-in types must not have attributes
            if type_entity.attributes:
                validation_errors['attributes'] = "Built-in types can not be extended with attributes"

        # All done
        return validation_errors


    def validate_attribute_names(self, type_entity: object) -> dict:
        """Check that no attribute this type declares has the name of a
        property of this type or an ancestor, and that no property it
        declares has the name of an attribute an ancestor declares. Every
        property is also an attribute of the same name, whose initial value
        is the property's value (TOSCA 2.0 §9.6); a second declaration of
        that attribute would contradict the first.

        Returns:
          (possibly empty) dict of validation errors, keyed by
          'attributes' and 'properties'
        """
        try:
            parent = type_entity.parent
        except (AttributeError, te.TypeNotFound):
            parent = None
        inherited_properties = parent.get_property_declarations() if parent else {}
        inherited_attributes = parent.get_attribute_declarations() if parent else {}
        own_properties = type_entity.properties or {}
        own_attributes = type_entity.attributes or {}

        errors = {}
        for name in own_attributes:
            if name in own_properties:
                errors.setdefault('attributes', {})[name] = \
                    "has the name of a property of this type, which is already an attribute"
            elif name in inherited_properties:
                errors.setdefault('attributes', {})[name] = \
                    "has the name of an inherited property, which is already an attribute"
        for name in own_properties:
            if name in inherited_attributes:
                errors.setdefault('properties', {})[name] = \
                    "has the name of an inherited attribute; a property is also an attribute"
        return errors


    def resolve_functions_in_property_declarations(self, type_entity: object) -> None:
        """Resolve functions in property values to the internal function
        syntax.
        """
        # Upgrade each property declaration
        properties = type_entity.properties
        for property_name, property_declaration in properties.items():
            property_declaration.resolve_functions_in_declared_values(type_entity)


    def resolve_functions_in_attribute_declarations(self, type_entity: object) -> None:
        """Resolve functions in attribute values to the internal function
        syntax.
        """
        # Upgrade each attribute declaration
        attributes = type_entity.attributes
        for attribute_name, attribute_declaration in attributes.items():
            attribute_declaration.resolve_functions_in_declared_values(type_entity)
