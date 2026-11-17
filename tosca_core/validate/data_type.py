"""
ToscaDataTypeValidator class
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2014-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger = logging.getLogger(__name__)

# Type hint support
from typing import Optional, TYPE_CHECKING
if TYPE_CHECKING:
    from tosca_core.models.data_type import ToscaDataType

# Types on which this validator depends
from .type import ToscaTypeValidator

# Exception support
import tosca_core.models.exceptions as te

# Validator support
from . import get_validator

# Cached lookups for TOSCA built-in data types
import tosca_core.models.builtin_types as builtin_types

class ToscaDataTypeValidator(ToscaTypeValidator):
    """The ToscaDataTypeValidator class validates TOSCA data type
    definitions
    """

    def __init__(self) -> None:
        """Constructor
        """
        super(ToscaDataTypeValidator, self).__init__()


    def validate_type_specifics(self, data_type: "ToscaDataType") -> dict:
        """Validate definitions that are specific to a data type definition:

        - Call 'validate_type_specifics' for the parent type
        - Make sure the data type has valid constraints
        - Make sure the data type has valid entry schema and key
          schema

        Args:
          data_type(ToscaDataType): data type definition to validate
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """

        logger.debug("Data type '%s': validating", data_type.name)

        # Is this a valid managed type entity?
        validation_errors = super(ToscaDataTypeValidator, 
                                  self).validate_type_specifics(data_type)

        # Version 1.x template may define constraints. Validate and
        # upgrade these here. Version 2.x validations will be
        # validated in a separate pass, since they may use functions
        # that are defined in the same profile and that need to be
        # validated first.
        errors = self.validate_and_upgrade_constraints(data_type)
        if errors:
            logger.error("Data type '%s': invalid constraints",
                         data_type.name)
            validation_errors['constraints'] = errors

        """
        # Are validations valid
        errors = self.validate_validations(data_type)
        if errors:
            logger.error("Data type '%s': invalid validations",
                         data_type.name)
            validation_errors['validations'] = errors
        """
        # Is entry schema valid
        errors = self.validate_entry_schema(data_type)
        if errors:
            logger.error("Data type '%s': invalid entry schema",
                         data_type.name)
            validation_errors['entry_schema'] = errors
            
        # Is key schema valid
        errors = self.validate_key_schema(data_type)
        if errors:
            logger.error("Data type '%s': invalid key schema",
                         data_type.name)
            validation_errors['key_schema'] = errors
            
        # Are scalar keyword values valid
        if not data_type.name == 'scalar':
            errors = self.validate_scalar_keywords(data_type)
            if errors:
                logger.error("Data type '%s': invalid scalar definition",
                             data_type.name)
                validation_errors.update(errors)
            
        # All done
        return validation_errors


    def validate_and_upgrade_constraints(self, data_type: "ToscaDataType") -> Optional[dict]:
        """Check if a data type entity has valid constraints on its parent
        type, and if so, upgrade to Version 2.0 validation function syntax.

        Args: 
          data_type(ToscaDataType): data type entity for which to
            validate constraints
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """

        # Does this data type define constraints?
        try:
            constraints = data_type.constraints
        except AttributeError:
            logger.debug("Data type '%s': no constraints to validate",
                         data_type.name)
            return None

        # Make sure we have a parent type to which to apply
        # constraints
        try:
            parent_type = data_type.parent
        except Exception as e:
            logger.error("Data type '%s': no parent type to which to apply constraints: %s",
                         data_type.name, e)
            return 'no parent data type to constrain'

        # Check if constraints are valid and upgrade.
        declaration = data_type.create_declaration(name='constraints')
        # Note that we set 'context' to None, since data types do
        # not define a context for functions.
        errors = declaration.validate_constraints(None, constraints)
        if errors:
            logger.error("'%s': incompatible constraints", data_type.name)
            return errors

        # Upgrade constraints
        data_type.validations = declaration.upgrade_constraints(constraints)

        # All done
        return None


    def validate_validation_for_data_types(self, data_types: dict) -> dict:
        """Check if all type entities in a list are valid

        Args:
          data_types(ToscaDataType[]): ordered list of data type
            entities for which to validate validations
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """

        validation_errors = {}
        for name, data_type in data_types.items():
            # Validate type entity
            errors = self.validate_validation_for_data_type(data_type)
            if errors:
                if isinstance(errors, dict):
                    self.add_line_number(errors, data_type)
                validation_errors[name] = errors

        # All done
        return validation_errors


    def validate_validation_for_data_type(self, data_type: "ToscaDataType") -> Optional[dict]:
        """Check if a data type entity has valid validations.

        Args: 
          data_type(ToscaDataType): data type entity for which to
            validate validations
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """
        # Does this data type define validations?
        try:
            validations = data_type.validations
        except AttributeError:
            logger.debug("Data type '%s': no validations to validate",
                         data_type.name)
            return None

        # Unless we're a complex type, make sure we have a parent type
        # to which to apply constraints.
        validation_errors = dict()
        try:
            data_type.parent
        except Exception as e:
            if data_type.is_builtin_type():
                logger.error("Data type '%s': no parent type to which to apply constraints: %s",
                             data_type.name, e)
                validation_errors['validation'] = 'no parent data type to constrain'
                return validation_errors

        # Use the data type itself (not the parent) as the value
        # declaration so the `<T>` / abstract-scalar resolution path
        # specializes to the derived type -- otherwise a scalar
        # literal like `0.0 bps` can't be validated against the
        # abstract `scalar` parameter type, which has no units.
        value_declaration = data_type.create_declaration('value_declaration')

        # A constraint expression must be a valid boolean expression
        declaration = builtin_types.get('boolean').create_declaration('validations')

        # Validate the validations. ``skip_validation_for=data_type``
        # breaks the recursion that would otherwise occur when a value
        # being matched against a parameter triggers the same type's
        # validations again.
        try:
            # Validate
            validations = data_type.validations
            validations = declaration.validate_function_value(data_type, validations,
                                                              value_declaration=value_declaration,
                                                              skip_validation_for=data_type)
            data_type.validations = validations
        except te.ValidationError as e:
            validation_errors['validation'] = e.errors
        except TypeError:
            validation_errors['validation'] =  'not a boolean function'
        except Exception as e:
            validation_errors['validation'] = 'validator error ({})'.format(str(e))

        # All done
        return validation_errors
                        

    def validate_entry_schema(self, data_type: "ToscaDataType") -> dict:
        """Check if a data type definition has a valid entity schema

        Args: 
          data_type(ToscaDataType): data type entity for which to
            validate constraints
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """

        # Does this data type have an entry schema
        try:
            entry_schema = data_type.entry_schema
        except AttributeError:
            # No entry schema to validate. Do nothing
            return {}

        logger.debug("%s: validating entry schema declaration",
                     data_type.name)

        # Get parent type to which to apply constraints
        try:
            parent_type = data_type.parent
        except Exception as e:
            logger.error("Data type '%s': no parent type to which to apply entry schema: %s",
                         data_type.name, e)
            return 'no parent data type specified'

        # We should only have an entry schema if the parent type is a
        # map or a list
        list_type = builtin_types.get('list')
        map_type = builtin_types.get('map')
        if not data_type.has_type(list_type) and not data_type.has_type(map_type):
            logger.error("%s is not a valid type to use with entry_schema",
                         data_type.name)
            return "not allowed for type '{0}'".format(data_type.name)

        # Entry schemas are just like property declarations, so
        # validate using property declaration validator
        validator = get_validator('ToscaPropertyDeclaration')

        # Note that property declaration needs a name
        setattr(entry_schema, 'name', "{0}-entry-schema".format(data_type.name))

        # Check to see if this is a valid property declaration
        try:
            errors = validator.validate_declaration(data_type, 
                                                    entry_schema)
            if errors:
                logger.error("data type '%s': invalid entry schema",
                             data_type.name)
                return errors
        except Exception as e:
            logger.error("data type '%s': error validating entry schema: %s",
                         data_type.name, e)
            return "validator error ({0})".format(e)

        # All done
        return {}


    def validate_key_schema(self, data_type: "ToscaDataType") -> dict:
        """Check if a data type definition has a valid entity schema

        Args: 
          data_type(ToscaDataType): data type entity for which to
            validate constraints
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """

        # Does this data type have an key sch
        try:
            key_schema = data_type.key_schema
            # No key schema to validate. Do nothing
        except AttributeError:
            return {}

        logger.debug("%s: validating key schema declaration",
                     data_type.name)

        # Get parent type to which to apply constraints
        try:
            parent_type = data_type.parent
        except Exception as e:
            logger.error("Data type '%s': no parent type to which to apply key schema: %s",
                         data_type.name, e)
            return 'no parent data type specified'

        # We should only have an key schema if the parent type is a
        # map or a list
        map_type = builtin_types.get('map')
        if not data_type.has_type(map_type):
            logger.error("%s is not a valid type to use with key_schema",
                         data_type.name)
            return "not allowed for type '{0}'".format(data_type.name)

        # Key schemas are just like property declarations, so
        # validate using property declaration validator
        validator = get_validator('ToscaPropertyDeclaration')

        # Note that property declaration needs a name
        setattr(key_schema, 'name', "{0}-key-schema".format(data_type.name))

        # Check to see if this is a valid property declaration
        try:
            errors = validator.validate_declaration(data_type, 
                                                    key_schema)
            if errors:
                logger.error("data type '%s': invalid key schema",
                             data_type.name)
                return errors
        except Exception as e:
            logger.error("data type '%s': error validating key schema: %s",
                         data_type.name, e)
            return "validator error ({0})".format(e)

        # All done
        return {}

    def validate_scalar_keywords(self, data_type: "ToscaDataType") -> dict:
        """Check if a data type definition has a valid scalar keyword values.

        Args: 
          data_type(ToscaDataType): data type entity for which to
            validate scalar keywords
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """
        validation_errors = dict()
        
        # Check to see if we're a scalar type
        scalar_type = builtin_types.get('scalar')
        if not data_type.has_type(scalar_type):
            # We're not a scalar. None of the scalar keywords are
            # allowed
            try:
                self.assert_not_present(data_type, '_units')
            except Exception:
                validation_errors['units'] = "only allowed for 'scalar' types"
            try:
                self.assert_not_present(data_type, '_data_type')
            except Exception:
                validation_errors['data_type'] = "only allowed for 'scalar' types"
            try:
                self.assert_not_present(data_type, '_canonical_unit')
            except Exception:
                validation_errors['canonical_unit'] = "only allowed for 'scalar' types"
            try:
                self.assert_not_present(data_type, '_prefixes')
            except Exception:
                validation_errors['prefixes'] = "only allowed for 'scalar' types"
            return validation_errors

        # Validate the scalar data type declaration
        integer_type = builtin_types.get('integer')
        float_type = builtin_types.get('float')

        # Per the spec, data_type MUST NOT be modified during scalar
        # derivation. Walk the chain to see whether an ancestor scalar
        # type already pinned the data_type (either explicitly or via
        # the float default applied when that ancestor was validated).
        ancestor_data_type = None
        ancestor = data_type
        while True:
            try:
                ancestor = ancestor.parent
            except (AttributeError, te.TypeNotFound):
                break
            if ancestor._data_type is not None:
                ancestor_data_type = ancestor._data_type
                break

        if data_type._data_type is not None and ancestor_data_type is not None:
            validation_errors['data_type'] = "must not be modified when deriving from another scalar type"
            return validation_errors

        try:
            scalar_data_declaration = data_type.data_type
            # Validate using property declaration validator. Note that
            # property declaration needs a name
            validator = get_validator('ToscaPropertyDeclaration')
            setattr(scalar_data_declaration, 'name', f"{data_type.name}-scalar-data")
            errors = validator.validate_declaration(data_type,
                                                    scalar_data_declaration)
            if errors:
                # No point in validating further
                validation_errors['data_type'] = errors
                return validation_errors
        except AttributeError:
            # No local scalar data type. Inherit from ancestor when
            # available; fall back to the spec default ('float').
            if ancestor_data_type is not None:
                scalar_data_declaration = ancestor_data_type
            else:
                scalar_data_declaration = float_type.create_declaration('scalar_data_type')
            # Cache the effective scalar data type on the derived
            # type so callers don't have to walk the chain.
            data_type._data_type = scalar_data_declaration

        # Only integer and floats are supported.
        if not scalar_data_declaration.type_entity.has_type(integer_type) and \
           not scalar_data_declaration.type_entity.has_type(float_type):
            validation_errors['data_type'] = f"invalid scalar data type '{scalar_data_declaration.type}'"
            return validation_errors
        
        # The spec lets a derived scalar type add entries to the units
        # map without redeclaring it. Locate ancestor units so we can
        # tell 'absent everywhere in the chain' (an error) from
        # 'inherited' (fine -- the ancestor was validated when it was).
        local_units = data_type._units or {}
        ancestor_units = {}
        ancestor = data_type
        while True:
            try:
                ancestor = ancestor.parent
            except (AttributeError, te.TypeNotFound):
                break
            if ancestor._units:
                ancestor_units = ancestor._units
                break

        if not local_units and not ancestor_units:
            validation_errors['units'] = "mandatory but not specified"
            return validation_errors

        # Validate only the locally-added entries. Per the spec, a
        # derived scalar type may ADD entries but MUST NOT override
        # entries declared in an ancestor type, so a key that already
        # exists upstream is an error here.
        units_errors = dict()
        integer_only = scalar_data_declaration.type_entity.has_type(integer_type)
        for unit, multiplier in local_units.items():
            if not isinstance(unit, str):
                units_errors[str(unit)] = "not a string"
                continue
            if unit in ancestor_units:
                units_errors[unit] = "already defined by an ancestor scalar type"
                continue
            try:
                value = scalar_data_declaration.validate_simple_value(data_type, multiplier)
            except te.ValidationError as e:
                units_errors[unit] = e.errors
        if units_errors:
            validation_errors['units'] = units_errors
            return validation_errors

        # 'At least one entry MUST have a multiplier value of one'
        # applies to the effective units. When local entries don't
        # carry one, the ancestor's must -- which was enforced when
        # the ancestor was validated. Skip when ancestor units exist.
        if not ancestor_units:
            if 1 not in local_units.values():
                if integer_only or 1.0 not in local_units.values():
                    validation_errors['units'] = "no multiplier value of '1' specified"

        # Cache the effective units map on the type itself so callers
        # (the runtime scalar-value parser, etc.) don't have to walk
        # the derivation chain on every access. Collisions were
        # rejected above, so the local and ancestor maps are disjoint.
        units = {**local_units, **ancestor_units}
        data_type._units = units

        # Does this scalar type define prefixes? Same chain semantics
        # as units: a derived type may ADD entries but MUST NOT
        # override an ancestor's. Walk to find the nearest ancestor
        # prefixes (already validated when the ancestor was).
        local_prefixes = data_type._prefixes or {}
        ancestor_prefixes = {}
        ancestor = data_type
        while True:
            try:
                ancestor = ancestor.parent
            except (AttributeError, te.TypeNotFound):
                break
            if ancestor._prefixes:
                ancestor_prefixes = ancestor._prefixes
                break

        if local_prefixes or ancestor_prefixes:
            prefixes_errors = dict()
            for prefix, multiplier in local_prefixes.items():
                if not isinstance(prefix, str):
                    prefixes_errors[str(prefix)] = "not a string"
                    continue
                if prefix in ancestor_prefixes:
                    prefixes_errors[prefix] = "already defined by an ancestor scalar type"
                    continue
                try:
                    value = scalar_data_declaration.validate_simple_value(data_type, multiplier)
                except te.ValidationError as e:
                    prefixes_errors[prefix] = e.errors
            if prefixes_errors:
                validation_errors['prefixes'] = prefixes_errors
                return validation_errors

            # Cache the effective prefix map on the type itself (same
            # rationale as units above). Local and ancestor maps are
            # disjoint after the override check.
            prefixes = {**local_prefixes, **ancestor_prefixes}
            data_type._prefixes = prefixes

            # 'Multiplier of 1' applies to the effective prefix map.
            # When ancestor prefixes exist, the ancestor's own
            # validation already enforced the rule; skip here.
            if not ancestor_prefixes:
                if 1 not in local_prefixes.values():
                    if integer_only or 1.0 not in local_prefixes.values():
                        validation_errors['prefixes'] = "no multiplier value of '1' specified"

            # If we have prefixes, only one unit allowed
            if not len(units) == 1:
                validation_errors['units'] = "only 1 value allowed when 'prefixes' are specified"
            if validation_errors: return validation_errors

            # Create new units from the effective prefix map.
            unit = next(iter(units.keys()))
            units = {key + unit: value for key, value in prefixes.items()}
        else:
            # No prefixes.
            prefixes = None

        # Does this scalar type define a canonical_unit?
        try:
            canonical_unit = data_type.canonical_unit
            # Make sure canonical unit is valid
            try:
                canonical_value = units[canonical_unit]
                if not canonical_value == 1:
                    validation_errors['canonical_unit'] = f"'{canonical_unit}' does not have a multiplier of 1"
            except KeyError:
                validation_errors['canonical_unit'] = f"'{canonical_unit}' not found"
        except AttributeError:
            # No canonical_unit. We need one if we have more than one
            # multiplier value of one.
            count = sum(1 for v in units.values() if v == 1.0)
            if count > 1:
                validation_errors['canonical_unit'] = "required when more than one multiplier value '1'"
            
        return validation_errors

    
