"""
ToscaPropertyDeclarationValidator class
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

# Exception support
import tosca_core.models.exceptions as te

# Types on which this validator depends
from tosca_core.models.path import ToscaPath
from tosca_core.models.node_type import ToscaNodeType
from tosca_core.models.relationship_type import ToscaRelationshipType
from .declaration import ToscaDeclarationValidator

# Cached lookups for TOSCA built-in data types
import tosca_core.models.builtin_types as builtin_types
from tosca_core.models.function import ToscaFunction
from tosca_core.models.function_declaration import ToscaSignature
from tosca_core.models.property_declaration import ToscaPropertyDeclaration


class ToscaPropertyDeclarationValidator(ToscaDeclarationValidator):
    """The ToscaPropertyDeclarationValidator class validates attribute
    declarations in Tosca type definitions
    """

    def __init__(self) -> None:
        """Constructor
        """
        super(ToscaPropertyDeclarationValidator, self).__init__()


    def validate_implied_type(self, type_entity: "Any", parameter_declaration: "ToscaPropertyDeclaration") -> Optional[str]:
        """Try to obtain implied property type"""

        # We can only get implied type if the parameter declaration
        # includes a fixed 'value'
        try:
            value = parameter_declaration.value
            return self.validate_value_type(type_entity, parameter_declaration, value)
        except AttributeError:
            # no value defined. A mapping perhaps?
            try:
                mapping = parameter_declaration.mapping
                return self.validate_mapping_type(type_entity, parameter_declaration, mapping)
            except AttributeError:
                return super(ToscaPropertyDeclarationValidator, self).validate_implied_type(
                    type_entity, parameter_declaration)


    def validate_value_type(self, type_entity: "Any", parameter_declaration: "ToscaPropertyDeclaration", value: "Any") -> Optional[str]:
        """Try to obtain implied property type from value"""
        logger.debug("%s: find type for parameter '%s(%s)'",
                     type_entity.name, parameter_declaration.name, str(value))

        # First, make sure value is a valid get_attribute or get_property function.
        try:
            function = ToscaFunction(value, type_entity)
        except Exception as e:
            logger.error("Unable to obtain implied type: %s", str(e))
            return "'{0}' is not a valid function".format(str(value))

        # Get a declaration for the function result
        try:
            declaration = function.get_result_declaration(type_entity)
        except ValueError as e:
            return "unable to find function value: {0}".format(str(e))
        
        # Merge 'type' and '_required' from referenced declaration. An
        # attribute declared as one has no required-ness, so a parameter
        # that takes its value from one is not required; nor is one whose
        # value is optional at some step of its path -- an optional property,
        # or an entry of a list or map (is_value_required). A parameter that
        # states its own 'required' keeps it.
        stated = parameter_declaration._required
        parameter_declaration.merge_augmented_type(declaration)
        parameter_declaration.merge_augmented_field('_required', declaration)
        if declaration.role == 'ATTRIBUTE' and parameter_declaration._required is None:
            parameter_declaration._required = False
        if stated is None:
            try:
                if not function.is_value_required(type_entity, declaration):
                    parameter_declaration._required = False
            except Exception as e:
                logger.debug("Parameter declaration '%s': required-ness along the path "
                             "not found (%s)", parameter_declaration.name, str(e))
        logger.debug("Parameter declaration '%s': implied type '%s'",
                     parameter_declaration.name, parameter_declaration.type)

        # All done
        return None
    

    def validate_mapping_type(self, context: "Any", parameter_declaration: "ToscaPropertyDeclaration", mapping: "Any") -> Optional[str]:
        """Try to obtain implied property type from mapping"""
        logger.debug("%s: find type for parameter '%s(%s)'",
                     context.name, parameter_declaration.name, str(mapping))

        # First, make sure mapping is a valid path expression.
        try:
            path = ToscaPath(mapping)
        except TypeError:
            return 'improperly-formatted output mapping'

        # Find the attribute declaration referenced by the output
        # mapping
        attribute_declaration, error = self._resolve_attribute_declaration(context, path)
        if error:
            return error

        # Merge type from referenced declaration
        parameter_declaration.merge_augmented_type(attribute_declaration)
        logger.debug("Parameter declaration '%s': implied type '%s'",
                     parameter_declaration.name, parameter_declaration.type)

        # All done
        return None


    def validate_for_type(self, type_entity: "Any", property_declaration: "ToscaPropertyDeclaration") -> dict:
        """Check if a attribute declaration is valid

        - Make sure the attribute declaration is a valid instance entity
        - Make sure the attribute declaration has a valid default
        - Make sure the attribute declaration has valid entry schema

        Args: 
          type_entity(ToscaType): type definition within which this
            attribute is declared
          property_declaration(ToscaPropertyDeclaration): Tosca
            attribute declaration to validate
        """

        logger.debug("'%s': validating attribute declaration '%s'",
                     type_entity.name, property_declaration.name)

        if property_declaration.has_templated_type() and \
           not isinstance(type_entity, ToscaSignature):
            errors = dict()
            errors['type'] = f"abstract type '{property_declaration.type}' must not be used"
            return errors
        
        # Is this a valid declaration
        validation_errors = super(ToscaPropertyDeclarationValidator,
                                  self).validate_for_type(type_entity,
                                                          property_declaration)

        # Version 1.x template may define constraints. Validate and
        # upgrade.
        errors = self.validate_and_upgrade_constraints(type_entity, property_declaration)
        if errors:
            logger.error("Property declaration '%s': invalid constraints", 
                         property_declaration.name)
            validation_errors['constraints'] = errors
                
        # Are validations valid?
        errors = self.validate_validations(type_entity, property_declaration)
        if errors:
            logger.error("Property declaration '%s': invalid validations",
                         property_declaration.name)
            validation_errors['validations'] = errors

        # Is default value valid
        errors = self.validate_default(type_entity, property_declaration)
        if errors:
            logger.error("Attribute declaration %s has invalid default", 
                         property_declaration.name)
            validation_errors['default'] = errors

        # Is fixed value valid?
        errors = self.validate_fixed_value(type_entity, property_declaration)
        if errors:
            logger.error("Attribute declaration '%s': invalid value", 
                         property_declaration.name)
            validation_errors['value'] = errors

        # Is output mapping valid?
        errors = self.validate_mapping(type_entity, property_declaration)
        if errors:
            logger.error("Property declaration '%s': invalid output mapping", 
                         property_declaration.name)
            validation_errors['mapping'] = errors

        # Is entry schema valid
        errors = self.validate_entry_schema(type_entity, property_declaration)
        if errors:
            logger.error("Attribute declaration %s has invalid entry schema",
                         property_declaration.name)
            validation_errors['entry_schema'] = errors

        # Is key schema valid
        errors = self.validate_key_schema(type_entity, property_declaration)
        if errors:
            logger.error("Attribute declaration %s has invalid key schema",
                         property_declaration.name)
            validation_errors['key_schema'] = errors

        return validation_errors


    def validate_and_upgrade_constraints(self, type_entity: "Any", property_declaration: "ToscaPropertyDeclaration") -> Optional[dict]:
        """Check if a property declaration has valid constraint values, and if
        so, upgrade to version 2.0 boolean expression.

        Args: 
          property_declaration(ToscaPropertyDeclaration): property
            entity to validate
        """
        # Does this property declaration have constraints
        try:
            constraints = property_declaration.constraints
        except AttributeError:
            # The type entity does not have constraints or constraints
            # set to None. Nothing to validate
            logger.debug("Property declaration '%s': no constraints to validate ",
                         property_declaration.name)
            return None

        # Must be a Version 1.x template. Check if constraints are
        # valid.
        errors = property_declaration.validate_constraints(type_entity, constraints)
        if errors:
            logger.error("Property declaration '%s': invalid constraints", 
                         property_declaration.name)
            return errors

        # Upgrade constraints
        property_declaration.validations = property_declaration.upgrade_constraints(constraints)

        # All done
        return None


    def validate_validations(self, type_entity: "Any", property_declaration: "ToscaPropertyDeclaration") -> Optional[dict]:
        """Check if a property declaration has valid validations.

        Args: 
          property_declaration(ToscaPropertyDeclaration): property
            entity to validate
        """
        # Does this property declaration have validations
        try:
            validations = property_declaration.validations
        except AttributeError:
            # The type entity does not have validations or validations
            # set to None. Nothing to validate
            logger.debug("Property declaration '%s': no validations to validate ",
                         property_declaration.name)
            return None

        validations = property_declaration.validations
        errors, canonical = self._validate_boolean_expression(
            property_declaration, validations, 'validations',
            value_declaration=property_declaration)
        if errors:
            return errors
        property_declaration.validations = canonical
        return None


    def validate_default(self, type_entity: "Any", property_declaration: "ToscaPropertyDeclaration") -> dict:
        """Check if an attribute declaration has a valid default value

        Args: 
          type_entity(ToscaType): type definition within which this
            attribute is declared
          property_declaration(ToscaPropertyDeclaration): attribute
            entity for which to validate the default value
        """

        validation_errors = {}

        try:
            default = property_declaration.default
        except AttributeError:
            # No default value to validate
            return validation_errors

        # Make sure the default value is valid for the attribute
        # declaration.
        try:
            property_declaration.default = property_declaration.validate_value(
                type_entity, default, is_default=True, check_presence=True)
        except te.ValidationError as e:
            logger.error("'%s': '%s' is invalid value for %s",
                         property_declaration.name, default,
                         property_declaration.type)
            validation_errors[str(default)] = e.errors
        except Exception as e:
            logger.error("Attribute declaration '%s': error validating default: %s",
                         property_declaration.name, e)
            validation_errors[str(default)] = "validator error ({0})".format(e)

        # All done
        return validation_errors


    def validate_fixed_value(self, type_entity: "Any", property_declaration: "ToscaPropertyDeclaration") -> dict:
        """Check if a property declaration has a valid fixed value

        Args: 
          property_declaration(ToscaPropertyDeclaration): property
            entity to validate
        """
        
        validation_errors = {}

        # If declaration assigns a value, make sure that value is
        # valid for the declaration
        try:
            property_value = property_declaration.value
        except AttributeError:
            # No value augmentation
            logger.debug("Property declaration '%s': no value to validate ",
                         property_declaration.name)
            return validation_errors

        # Is the property value valid?
        try:
            # If a function is specified as the fixed value, we
            # provide the property declaration itself as the context.
            property_declaration.value = property_declaration.validate_value(
                type_entity, property_value, check_presence=True)
        except te.ValidationError as e:
            logger.error("Property '%s': '%s' is invalid value for %s",
                         property_declaration.name, property_value,
                         property_declaration.type)
            validation_errors[str(property_value)] = e.errors
        except Exception as e:
            logger.error("Property '%s': error while validating value augmentation: %s",
                         property_declaration.name, e)
            validation_errors[str(property_value)] = "validator error ({0})".format(e)

        # Everything OK
        return validation_errors


    def validate_mapping(self, context: "Any", property_declaration: "ToscaPropertyDeclaration") -> dict:
        """Check if a property declaration has a valid mapping

        Args: 
          property_declaration(ToscaPropertyDeclaration): property
            entity to validate
        """
        
        validation_errors = {}

        # If declaration assigns a mapping, make sure that mapping is
        # valid for the declaration
        try:
            mapping = property_declaration.mapping
        except AttributeError:
            # No value augmentation
            logger.debug("Property declaration '%s': no mapping to validate ",
                         property_declaration.name)
            return validation_errors

        # Are output mappings allowed:
        if not property_declaration.role == 'OUTPUT':
            return 'not allowed here'
        
        # First, make sure mapping is a valid path expression.
        try:
            path = ToscaPath(mapping)
        except TypeError:
            return 'improperly-formatted output mapping'

        # Find the attribute referenced by the output mapping
        attribute_declaration, error = self._resolve_attribute_declaration(context, path)
        if error:
            return error

        # Make sure types are compatible
        if not attribute_declaration.has_type(property_declaration.type_entity):
            error = "mapped attribute type '{0}' incompatible with declarated type '{1}'".format(
                attribute_declaration.type, property_declaration.type)
            return error

        # All done
        return validation_errors


    def validate_entry_schema(self, type_entity: "Any", property_declaration: "ToscaPropertyDeclaration") -> dict:
        """Check if an attribute declaration has a valid entity schema

        Args: 
          property_declaration(ToscaPropertyDeclaration): attribute
            entity for which to validate entry schema
        """

        # Does this attribute declaration have an entry sch
        try:
            entry_schema = property_declaration.entry_schema
        except AttributeError:
            # No entry schema to validate. Do nothing
            return {}

        logger.debug("%s: validating entry schema declaration",
                     property_declaration.name)

        # We should only have an entry schema if the attribute
        # entity is a map or a list
        list_type = builtin_types.get('list')
        map_type = builtin_types.get('map')
        if not property_declaration.has_type(list_type) and not property_declaration.has_type(map_type):
            logger.error("%s: %s is not a valid type to use with entry_schema",
                         property_declaration.name, property_declaration.type)
            return "not allowed for type {0}".format(property_declaration.type)

        # Entry schemas are just like property declarations, so
        # validate using property declaration validator
        validator = get_validator('ToscaPropertyDeclaration')

        # Note that property declaration needs a name
        setattr(entry_schema, 'name', "{0}-entry-schema".format(property_declaration.name))

        # Check to see if this is a valid property declaration
        try:
            errors = validator.validate_declaration(type_entity, entry_schema)
            if errors:
                logger.error("Attribute declaration '%s': invalid entry schema",
                             property_declaration.name)
                return errors
        except Exception as e:
            logger.error("Attribute declaration '%s': error validating entry schema: %s",
                         property_declaration.name, e)
            return "validator error ({0})".format(e)

        # All done
        return {}


    def validate_key_schema(self, type_entity: "Any", property_declaration: "ToscaPropertyDeclaration") -> dict:
        """Check if an attribute declaration has a valid key schema
        """
        try:
            key_schema = property_declaration.key_schema
        except AttributeError:
            return {}

        logger.debug("%s: validating key schema declaration",
                     property_declaration.name)

        # Key schemas only apply to maps
        map_type = builtin_types.get('map')
        if not property_declaration.has_type(map_type):
            logger.error("%s: %s is not a valid type to use with key_schema",
                         property_declaration.name, property_declaration.type)
            return "not allowed for type {0}".format(property_declaration.type)

        # Key schemas are property declarations, so validate using the
        # property declaration validator.
        validator = get_validator('ToscaPropertyDeclaration')
        setattr(key_schema, 'name', "{0}-key-schema".format(property_declaration.name))

        try:
            errors = validator.validate_declaration(type_entity, key_schema)
            if errors:
                logger.error("Attribute declaration '%s': invalid key schema",
                             property_declaration.name)
                return errors
        except Exception as e:
            logger.error("Attribute declaration '%s': error validating key schema: %s",
                         property_declaration.name, e)
            return "validator error ({0})".format(e)

        return {}


    def validate_augmentation(self, entity: "Any", property_name: str,
                              property_to_augment: "ToscaPropertyDeclaration", property_declaration: "ToscaPropertyDeclaration") -> dict:
        """Check if a property declaration is a valid augmentation of a
        previously declared property.

        We first check if the augmentation attributes are valid. If they
        are, a new property declaration is created from the augmentation,
        and that new property declaration is then validated separately

        Args: 
          entity(ToscaType or ToscaDeclaration): entity definition
            within which this property declaration occurs. Could be a
            type or a declaration.
          property_name(str): name of property to augment
          property_declaration(ToscaPropertyDeclaration): Tosca
            property augmentation to validate
        """

        logger.debug("'%s': validating property augmentation '%s'",
                     entity.name, property_name)

        # Make sure this is a valid property augmentation, and complete it
        errors = self.complete_augmentation(entity, property_name,
                                            property_to_augment, property_declaration)
        if errors:
            return errors

        # Validate the newly created property declaration
        errors = self.validate_declaration(entity, property_declaration)
        if errors:
            logger.error("'%s': invalid augmented property declaration '%s'", 
                         entity.name, property_name)
            return errors

        # Everthing OK
        return {}


    def complete_augmentation(self, entity: "Any", property_name: str,
                              property_to_augment: "ToscaPropertyDeclaration", property_declaration: "ToscaPropertyDeclaration") -> dict:
        """Check that a property declaration is a valid augmentation of a
        previously declared property and, if it is, complete it by merging
        that declaration in.

        The checks read what the augmentation itself states, so they run
        before the merge and never after it: a merged declaration also
        carries what it inherited, and a fixed value it inherited would
        read as one it restates. This is what lets an augmentation be
        completed before anything else in its containing type is
        validated, and then validated like any other declaration.

        Args: 
          entity(ToscaType or ToscaDeclaration): entity definition
            within which this property declaration occurs.
          property_name(str): name of property to augment
          property_to_augment(ToscaPropertyDeclaration): the declaration
            it augments
          property_declaration(ToscaPropertyDeclaration): Tosca
            property augmentation to check and complete

        Returns:
          (possibly empty) dict of validation errors
        """
        errors = self.validate_property_augmentation(property_to_augment, property_declaration)
        if errors:
            logger.error("'%s': property '%s': invalid augmentation",
                         entity.name, property_name)
            self.add_line_number(errors, property_declaration)
            return errors

        # Valid property augmentation. Create new property
        # declaration that reflects the property augmentation
        property_declaration.merge_augmented_declaration(property_to_augment)

        return {}


    def complete_nested_refinements(self, containing_entity: "Any", property_declaration: "ToscaPropertyDeclaration") -> dict:
        """Check and complete the property and attribute refinements inside
        a property declaration of a complex data type.

        Each refines what the declaration's data type declares, and finds
        it through that type -- which a refining declaration only has once
        its own merge has given it one, so this runs after that merge. It
        runs for every property declaration, not only those that refine an
        inherited property: a property declared for the first time can
        still refine the properties of its own data type, as
        `io.kubernetes`'s `PodTemplate.metadata` refines `labels`.

        Nested declarations are completed the same way, to whatever depth
        the data types nest.

        Args:
          containing_entity(ToscaType or ToscaDeclaration): entity that
            contains this declaration
          property_declaration(ToscaPropertyDeclaration): declaration
            whose nested refinements to complete

        Returns:
          (possibly empty) dict of validation errors
        """
        errors = {}
        for attribute in ('properties', 'attributes'):
            attribute_errors = {}
            for name, nested in (getattr(property_declaration, attribute, None) or {}).items():
                try:
                    to_augment = property_declaration.get_entity_declaration_to_augment(
                        attribute, name)
                except KeyError:
                    # A new declaration, not a refinement. What it holds
                    # may still refine the data type's own declarations.
                    to_augment = None
                except Exception:
                    # A type that cannot be resolved is reported by validation
                    continue
                try:
                    if to_augment is not None:
                        nested_errors = self.complete_augmentation(
                            property_declaration, name, to_augment, nested)
                        if nested_errors:
                            attribute_errors[name] = nested_errors
                            continue
                    nested_errors = self.complete_nested_refinements(property_declaration, nested)
                    if nested_errors:
                        attribute_errors[name] = nested_errors
                except Exception as e:
                    logger.error("'%s': error while completing %s '%s': %s",
                                 property_declaration.name, attribute, name, e)
                    attribute_errors[name] = "validation error ({0})".format(e)
            if attribute_errors:
                errors[attribute] = attribute_errors
        if errors:
            self.add_line_number(errors, property_declaration)
        return errors


    def validate_property_augmentation(self, property_to_augment: "ToscaPropertyDeclaration", property_declaration: "ToscaPropertyDeclaration") -> dict:
        """Check if a property declaration is a valid augmentation of a
        previous property declaration:

        - Make sure the property augmentation does not have properties
        - Make sure the property augmentation does not redefine the entry schema

        Args: 
          property_to_augment(ToscaPropertyDeclaration): Tosca
            property declaration to augment
          property_declaration(ToscaPropertyDeclaration): Tosca
            property declaration to validate
        """

        validation_errors = {}

        # Make sure type of augmentation is compatible with type of
        # augmented property declaration
        try:
            type = property_declaration._type
            if not property_declaration.has_type(property_to_augment.type_entity):
                logger.error("Property '%s': augmentation type '%s' incompatible with '%s'",
                             type, property_to_augment.type,
                             property_declaration.name)
                validation_errors['type'] = '{0} is not compatible with {1}'.format(
                    type, property_to_augment.type)
        except AttributeError:
            # No type specified. Augmentation will have the same type
            # as the type of the augmented entity
            pass

        # Validate required augmentation
        errors = self.validate_required_augmentation(property_to_augment, property_declaration)
        if errors:
            logger.error("Property '%s': invalid 'required' augmentation", 
                         property_declaration.name)
            validation_errors['required'] = errors
            
        # Validate value augmentation
        errors = self.validate_value_augmentation(property_to_augment, property_declaration)
        if errors:
            logger.error("Property '%s': invalid value augmentation", 
                         property_declaration.name)
            validation_errors['value'] = errors
            
        # Validate mapping augmentation
        errors = self.validate_mapping_augmentation(property_to_augment, property_declaration)
        if errors:
            logger.error("Property '%s': invalid mapping augmentation", 
                         property_declaration.name)
            validation_errors['mapping'] = errors
            
        # Validate entry schema augmentation
        errors = self.validate_entry_schema_augmentation(property_to_augment, property_declaration)
        if errors:
            logger.error("Property '%s': invalid entry schema augmentation", 
                         property_declaration.name)
            validation_errors['entry_schema'] = errors
            
        # Everything OK
        return validation_errors


    def validate_required_augmentation(self, property_to_augment: "ToscaPropertyDeclaration", property_declaration: "ToscaPropertyDeclaration") -> Optional[str]:
        """If augmentation specifies the property is optional, make sure the
        augmented declaration doesn't define the property as required

        Args: 
          property_declaration(ToscaPropertyDeclaration): property
            entity for which to validate the 'required' flag
        """
        if not property_declaration.is_required() and property_to_augment.is_required():
            return "redefining required property as optional is not allowed"
        return None


    def validate_mapping_augmentation(self, property_to_augment: "ToscaPropertyDeclaration", property_declaration: "ToscaPropertyDeclaration") -> Optional[str]:
        """If augmentation defines a mapping, make sure mapping is allowed.

        Args: 
          property_declaration(ToscaPropertyDeclaration): property
            entity for which to validate mapping
        """
        # Does the augmentation define a mapping?
        try:
            mapping = property_declaration.mapping
        except AttributeError:
            # Not fixed mapping defined
            return None

        # Make sure the property role allows a fixed mapping.
        if not property_declaration.role == 'OUTPUT':
            return 'not allowed here'

        # Make sure the property we're augmenting doesn't already define a mapping
        try:
            mapping_to_augment = property_to_augment.mapping
            return 'already set by earlier definition'
        except AttributeError:
            # No mapping yet. Good!
            pass

        # All done
        return None
        

    def validate_value_augmentation(self, property_to_augment: "ToscaPropertyDeclaration", property_declaration: "ToscaPropertyDeclaration") -> Optional[str]:
        """If augmentation defines a fixed value, make sure value is allowed.

        Args: 
          property_declaration(ToscaPropertyDeclaration): property
            entity for which to validate value
        """
        # Does the augmentation define a fixed value?
        try:
            value = property_declaration.value
        except AttributeError:
            # Not fixed value defined
            return None

        # Make sure the property role allows a fixed value.
        if not (property_declaration.role == 'INPUT' 
                or property_declaration.role == 'PROPERTY'
                or property_declaration.role == 'ATTRIBUTE'):
            return 'not allowed here'

        # Make sure the property we're augmenting doesn't already define a fixed value
        try:
            value_to_augment = property_to_augment.value
            return 'already set by earlier definition'
        except AttributeError:
            # No value yet. Good!
            pass

        # All done
        return None
        

    def validate_entry_schema_augmentation(self, property_to_augment: "ToscaPropertyDeclaration", property_declaration: "ToscaPropertyDeclaration") -> dict:
        """If augmentation defines entry schema, make sure entry_schema is
         compatible with entry schema declared in augmented property
         declaration.

        Args: 
          property_declaration(ToscaPropertyDeclaration): property
            entity for which to validate entry schema

        """

        # Does this property augmentation have an entry schema
        try:
            entry_schema = property_declaration.entry_schema
        except AttributeError:
            # No entry schema to validate. Do nothing
            return {}

        logger.debug("%s: validating entry schema augmentation",
                     property_declaration.name)

        # We should only have an entry schema if the property entity
        # we're augmenting is a map or a list
        list_type = builtin_types.get('list')
        map_type = builtin_types.get('map')
        if not property_to_augment.has_type(list_type) and not property_to_augment.has_type(map_type):
            logger.error("%s: %s is not a valid type to use with entry_schema",
                         property_to_augment.name, property_to_augment.type)
            return "not allowed for type {0}".format(property_to_augment.type)

        # Make sure the entry schema type is compatible with any entry
        # schema that is defined in the property to agument
        entry_declaration_to_augment = property_to_augment.get_entry_schema()
        if entry_declaration_to_augment:
            # Make sure the entry schema augmentation is valid for the
            # entry schema to augment
        
            # Check to see if this is a valid property declaration
            try:
                errors = self.validate_augmentation(property_declaration,
                                                    entry_declaration_to_augment.name,
                                                    entry_declaration_to_augment,
                                                    entry_schema)
                if errors:
                    logger.error("property augmentation '%s': invalid entry schema augmentation",
                                 property_declaration.name)
                    return errors
            except Exception as e:
                logger.error("property augmentation '%s': error validating entry schema: %s",
                             property_declaration.name, e)
                return "validator error ({0})".format(e)

        # All done
        return {}
