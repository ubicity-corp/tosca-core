"""
Module defining Tosca Data Type entity
"""
from __future__ import annotations

__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2014-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger: logging.Logger = logging.getLogger(__name__)

# Type hints
from typing import Any, Callable, Optional

# Database support
from tosca_core import db

# SQL Alchemy support
from sqlalchemy.orm import backref

# Type from which the TOSCA data type derives
import tosca_core.models.type
import tosca_core.models.exceptions as te

# Cached lookups for TOSCA built-in data types
from tosca_core.models import builtin_types

# Types used by this object
from tosca_core.models.property_declaration import ToscaPropertyDeclaration

# Function checking
from tosca_core.models.function import ToscaFunction
import tosca_core.models.unchecked as unchecked

# Definition of built-in data types
from tosca_core.builtin.data_types import data_type_validators
from tosca_core.builtin.comparison import equal_operators
from tosca_core.builtin.comparison import greater_than_operators
from tosca_core.builtin.comparison import greater_or_equal_operators
from tosca_core.builtin.comparison import less_than_operators
from tosca_core.builtin.comparison import less_or_equal_operators
from tosca_core.builtin.data_types import valid_values_operators
from tosca_core.builtin.data_types import list_has_entry_operators
from tosca_core.builtin.data_types import map_has_entry_operators
from tosca_core.builtin.arithmetic import arithmetic_operators


class ToscaDataType(tosca_core.models.type.ToscaType):
    """The ToscaDataType represents a named data type that can be used
    for declaring Tosca properties, attributes, parameters in other
    TOSCA type definitions or entity definitions.
    """

    ################################################################################
    # Polymorphic mapping
    ################################################################################

    __mapper_args__ = {
        'polymorphic_identity':'data',
    }


    ################################################################################
    # Keys
    ################################################################################
    
    # Foreign keys
    _entry_schema_id =     db.Column(db.Integer, 
                                     db.ForeignKey('tosca_declaration.id'),
                                     nullable=True)
    _key_schema_id =       db.Column(db.Integer, 
                                     db.ForeignKey('tosca_declaration.id'),
                                     nullable=True)
    _data_type_id = db.Column(db.Integer, 
                                     db.ForeignKey('tosca_declaration.id'),
                                     nullable=True)

    ################################################################################
    # Fields
    ################################################################################

    # Optional fields start with '_' and have corresponding getters
    # and setters to ensure that retrieving fields consistently raises
    # an AttributeError when not set.  Note that 'nullable' defaults
    # to True, but we explicitly set the 'nullable' flag for clarity.

    _validations =         db.Column(db.PickleType, nullable=True)
    _prefixes =            db.Column(db.PickleType, nullable=True)
    _units =               db.Column(db.PickleType, nullable=True)
    _canonical_unit =      db.Column(db.String, nullable=True)

    @property
    def prefixes(self) -> list[str]:
        # _prefixes holds the effective map after the type was
        # validated: the validator merges in any ancestor prefixes
        # so callers don't walk the derivation chain at runtime.
        if not self._prefixes:
            raise AttributeError(f"'{self.name}' does not have 'prefixes'")
        return self._prefixes

    @property
    def units(self) -> dict[str, Any]:
        # _units holds the effective map after the type was validated;
        # see the prefixes property comment.
        if not self._units:
            raise AttributeError(f"'{self.name}' does not have 'units'")
        return self._units
    @property
    def canonical_unit(self) -> str:
        if not self._canonical_unit:
            raise AttributeError(f"'{self.name}' does not have 'canonical_unit'")
        return self._canonical_unit

    @property
    def constraints(self) -> Any:
        if not self._constraints:
            raise AttributeError("'{0}' does not have 'constraints'".format(self.name))
        return self._constraints

    @property
    def validations(self) -> Any:
        if not self._validations:
            raise AttributeError("'{0}' does not have 'validations'".format(self.name))
        return self._validations

    @validations.setter
    def validations(self, value: Any) -> None:
        if value != None: self._validations = value


    ################################################################################
    # Relationships
    ################################################################################

    _entry_schema =        db.relationship('ToscaPropertyDeclaration',
                                           foreign_keys='ToscaDataType._entry_schema_id',
                                           back_populates='_entry_schema_for_type')
    _key_schema =          db.relationship('ToscaPropertyDeclaration',
                                           foreign_keys='ToscaDataType._key_schema_id',
                                           back_populates='_key_schema_for_type')
    _data_type =           db.relationship('ToscaPropertyDeclaration',
                                           foreign_keys='ToscaDataType._data_type_id',
                                           back_populates='_data_type_for_type')

    @property
    def entry_schema(self) -> ToscaPropertyDeclaration:
        if self._entry_schema == None:
            raise AttributeError("'{0}' does not have 'entry_schema'".format(self.name))
        return self._entry_schema

    @property
    def key_schema(self) -> ToscaPropertyDeclaration:
        if self._key_schema == None:
            raise AttributeError("'{0}' does not have 'key_schema'".format(self.name))
        return self._key_schema

    @property
    def data_type(self) -> ToscaPropertyDeclaration:
        if self._data_type == None:
            raise AttributeError("'{0}' does not have 'data_type'".format(self.name))
        return self._data_type

    
    ################################################################################
    # Constructor
    ################################################################################

    def __init__(self,
                 constraints: Any = None,
                 validations: Any = None,
                 entry_schema: Optional[ToscaPropertyDeclaration] = None,
                 key_schema: Optional[ToscaPropertyDeclaration] = None,
                 data_type: Optional[ToscaPropertyDeclaration] = None,
                 units: Optional[dict[str, Any]] = None,
                 canonical_unit: Optional[str] = None,
                 prefixes: Optional[list[str]] = None,
                 **kwargs: Any
    ) -> None:
        # First, call superclass constructor
        super(ToscaDataType, self).__init__(**kwargs)

        # ToscaDataType-specific initializations
        if constraints: self._constraints = constraints
        if validations: self._validations = validations
        if entry_schema: self._entry_schema = entry_schema
        if key_schema: self._key_schema = key_schema
        if data_type: self._data_type = data_type
        if units: self._units = units
        if canonical_unit: self._canonical_unit = canonical_unit
        if prefixes: self._prefixes = prefixes


    ################################################################################
    # Create a declaration of this type
    ################################################################################

    def create_declaration(self, name: str = 'anonymous') -> ToscaPropertyDeclaration:
        """Synthesize a ToscaPropertyDeclaration object for this
        data type

        Args:
          name(str): name for the property being declared

        Returns:
          ToscaPropertyDeclaration: with the appropriate name and type. No
            other attributes are initialized.

        Raises:
          None
        """
        property_declaration = ToscaPropertyDeclaration(name=name,
                                                        type=self.name)
        property_declaration.type_entity = self
        return property_declaration


    ################################################################################
    # Sub-entity retrieval functions. Sub-entities are retrieved from
    # this type as well as from any parent types(s)
    ################################################################################

    def get_entry_schema(self) -> Optional[ToscaPropertyDeclaration]:
        """Get entry_schema for this data type.  Check parent type if
        we don't have one.

        Returns
          entry_schema(ToscaPropertyDeclaration) or None

        Raises:
          None
        """
        # Return our own entry_schema if it exists
        try:
            return self.entry_schema
        except AttributeError:
            pass

        # This type does not specify an entry schema. Try
        # parent type instead.
        try:
            parent = self.parent
            return parent.get_entry_schema()
        except AttributeError:
            # No parent
            return None


    def get_key_schema(self) -> ToscaPropertyDeclaration:
        """Get key_schema for this data type.  Check parent type if
        we don't have one.

        Returns
          key_schema(ToscaPropertyDeclaration) or None

        Raises:
          None
        """
        # Return our own key_schema if it exists
        try:
            return self.key_schema
        except AttributeError:
            pass
        
        # This type does not specify an key schema. Try
        # parent type instead.
        try:
            parent = self.parent
            return parent.get_key_schema()
        except AttributeError:
            # No parent. We better be a map.
            if not (self.profile.name == 'builtin' and
                    self.name == 'map'):
                logger.error("%s: key schema not allowed", self.name)
                raise TypeError("Not a map")
            string_type = builtin_types.get('string')
            # TODO: fix. This could result in many string declarations
            # in the database.
            return string_type.create_declaration()


    ################################################################################
    # Other stuff that needs to be organized. 
    ################################################################################

    def is_builtin_type(self) -> bool:
        """Check if this type entity is a built-in TOSCA type. This method
        overrides the default defined in the base type object
        class. It needs to be extended to take profiles into
        account.
        """
        # Are we derived from a built-in type?
        try:
            return self.parent.is_builtin_type()
        except (AttributeError, te.CircularInheritance):
            # No parent.
            pass

        # Are we in the built-in profile?
        return self.profile.name == 'builtin'


    def is_list(self) -> bool:
        """Check if this type entity is a built-in TOSCA list type.
        """
        # Is our parent a list?
        try:
            return self.parent.is_list()
        except (AttributeError, te.CircularInheritance):
            # No parent.
            pass

        # Are we in the built-in profile?
        return self.profile.name == 'builtin' and self.name=='list'


    def is_map(self) -> bool:
        """Check if this type entity is a built-in TOSCA map type.
        """
        # Is our parent a map?
        try:
            return self.parent.is_map()
        except (AttributeError, te.CircularInheritance):
            # No parent.
            pass

        # Are we in the built-in profile?
        return self.profile.name == 'builtin' and self.name=='map'


    def get_prereq_type_names(self) -> list[str]:
        """Return list of entity names of the same type on which this entity
        depends. Data type entities return the types of the properties
        they include as well as their parent type.

        Returns
          ToscaDataType[]: ordered list of data type entities on which
            this type depends
        """

        prereq_type_names = super(ToscaDataType, self).get_prereq_type_names()
        # Add entry type if present
        try:
            entry_schema = self.entry_schema
            if entry_schema._type not in prereq_type_names:
                prereq_type_names.append(entry_schema._type)
        except AttributeError:
            pass
        # Add key type if present
        try:
            key_schema = self.key_schema
            if key_schema._type not in prereq_type_names:
                prereq_type_names.append(key_schema._type)
        except AttributeError:
            pass
        # Add data type if present
        try:
            data_type = self.data_type
            if data_type._type not in prereq_type_names:
                prereq_type_names.append(data_type._type)
        except AttributeError:
            pass
        for property_name, property_declaration in self.properties.items():
            try:
                # Add the property type
                property_type = property_declaration._type
                # Avoid duplicates. Replace with map later
                if property_type and property_type not in prereq_type_names:
                    prereq_type_names.append(property_type)
                # Add entry type if present
                try:
                    entry_schema = property_declaration.entry_schema
                    entry_type = entry_schema._type
                    if entry_type not in prereq_type_names:
                        prereq_type_names.append(entry_type)
                except AttributeError:
                    pass
                # Add key type if present
                try:
                    key_schema = property_declaration.key_schema
                    key_type = key_schema._type
                    if key_type not in prereq_type_names:
                        prereq_type_names.append(key_type)
                except AttributeError:
                    pass
            except AttributeError:
                # Property declaration does not include type
                pass
        return prereq_type_names


    ################################################################################
    # Validation
    ################################################################################

    def validate_value_for_type(self, value: Any) -> Optional[str]:
        """check if the provided value is compatible with this type. This
        method assumes that we're a simple ('built-in') TOSCA data
        type for which we have a 'compatible value checker'

        Returns:
          None: if value is compatible
          error(str): if value is not compatible

        Raises:
          TypeError: when we're a complex type
        """

        # First, find our 'compatible value checker'
        try:
            validator = self.get_operator(data_type_validators)
        except KeyError:
            # We're a complex data type. Raise a type error
            # exception.
            raise TypeError('not a built-in type')

        # We found a validator. Run it.
        try:
            return validator(self, value)
        except Exception as e:
            logger.error("Error checking value[%s] for type[%s]: %s",
                         value, self.name, e)
            error = 'validator error <{0}>'.format(str(e))
            return error


    def get_operator(self, operators: dict[str, Callable]) -> Callable:
        """Get a type-compatible validator. This method assumes that we're a
        simple ('built-in') TOSCA data type for which we have a
        'compatible value checker'

        Returns:
          validator
        Raises:
          TypeError: when we're a complex type
        """

        # Try to get validator from parent type
        try:
            return self.parent.get_operator(operators)
        except (AttributeError, te.CircularInheritance):
            # We don't have a parent type. Find our own validator.
            pass
        
        # First, find our 'compatible value checker'
        try:
            return operators[self.name]
        except KeyError:
            # We're a complex data type. Raise a type error
            # exception.
            raise TypeError('not a built-in type')


    def are_validations_satisfied(self, context: Any, value: Any, skip_validation_for: Optional[Any] = None) -> bool:
        """Does the provided value satisfy all validations defined in this
        declaration?

        Args:
          skip_validation_for: when set to a data type, skip evaluating
            that type's own validations (parent-chain validations still
            run). Used to break the recursion that arises when a type's
            validation references a literal that would re-trigger the
            same type's validation during signature matching.
        """
        # Check our parent type's validations first.
        try:
            if not self.parent.are_validations_satisfied(context, value, skip_validation_for=skip_validation_for):
                return False
        except AttributeError:
            # No parent
            pass

        # Skip our own validations if we're the type currently being
        # validated (the recursion guard).
        if skip_validation_for is self:
            return True

        # Next, check our own validations.
        try:
            validations = self.validations
            # Create a value declaration to be used for determining
            # templated types.
            try:
                value_declaration = self.parent.create_declaration('value_declaration')
            except AttributeError:
                # No parent. Must be a comlex type
                value_declaration = self.create_declaration('value_declaration')
            function = ToscaFunction(validations, context, value_declaration)
            # A clause that could not be evaluated here is recorded as
            # not checked, and does not fail the value
            return unchecked.verdict(
                function.evaluate(context, value=value, value_declaration=value_declaration),
                f"data type '{self.name}'", value)
        except AttributeError:
            # No validations
            return True
        except Exception as e:
            logger.error("%s: error validating %s: %s", self.name, str(value), str(e))
            return False

    ################################################################################
    # Type-specific functions
    ################################################################################

    def equal(self, args: list[Any]) -> Optional[bool]:
        """check if the two arguments are equal. Arguments are expected to be
        fully evaluated and of the same type.

        Returns:
          None: if one of the arguments is undefined
          (boolean): result of comparison
        Raises:
          ???
        """
        # Make sure we have two arguments
        if args[0] == None or args[1] == None: return None

        # Evaluate
        try:
            # Try simple type comparison
            return self.equal_simple(args)
        except TypeError:
            # Must be complex type.
            return self.equal_complex(args)

        
    def equal_simple(self, args: list[Any]) -> bool:
        """check if the two arguments of built-in types are equal. Neither
        arguments must be None.

        Returns:
          (boolean): result of comparison
        Raises:
          ???
        """
        # Find our compatible equal operator
        try:
            operator = self.get_operator(equal_operators)
        except KeyError:
            # No operator found. We must be complex data type. Raise a
            # type error exception.
            raise TypeError('not a built-in type')

        # We found an operator. Execute it.
        return operator(self, args)

    def equal_complex(self, args: list[Any]) -> Optional[bool]:
        """Check if two complex data values are equal. This assumes that the
        values are valid for this type (e.g., all required properties
        are present)

        Returns:
          (boolean): result of comparison
        Raises:
          ???
        """
        equal = None
        for property_name, property_declaration, in self.properties.items():
            try:
                value0 = args[0][property_name]
            except (AttributeError, KeyError):
                value0 = None
            try:
                value1 = args[1][property_name]
            except (AttributeError, KeyError):
                value1 = None
            property_equal = property_declaration.type_entity.equal([value0, value1])
            if property_equal == False: return False
            if property_equal == True: equal = True
        # All done
        return equal
    
    def greater_than(self, args: list[Any]) -> bool:
        """check if the first argument of a built-in types is greater_than the
        second.

        Returns:
          (boolean): result of comparison
        Raises:
          ???
        """
        # Find our compatible greater_than operator
        try:
            operator = self.get_operator(greater_than_operators)
        except KeyError:
            # No operator found. We must be complex data type. Raise a
            # type error exception.
            raise TypeError('not a built-in type')

        # We found an operator. Execute it.
        return operator(self, args)

    def greater_or_equal(self, args: list[Any]) -> bool:
        """check if the first argument of a built-in types is greater_or_equal the
        second.

        Returns:
          (boolean): result of comparison
        Raises:
          ???
        """
        # Find our compatible greater_or_equal operator
        try:
            operator = self.get_operator(greater_or_equal_operators)
        except KeyError:
            # No operator found. We must be complex data type. Raise a
            # type error exception.
            raise TypeError('not a built-in type')

        # We found an operator. Execute it.
        return operator(self, args)

    def less_than(self, args: list[Any]) -> bool:
        """check if the first argument of a built-in types is less_than the
        second.

        Returns:
          (boolean): result of comparison
        Raises:
          ???
        """
        # Find our compatible less_than operator
        try:
            operator = self.get_operator(less_than_operators)
        except KeyError:
            # No operator found. We must be complex data type. Raise a
            # type error exception.
            raise TypeError('not a built-in type')

        # We found an operator. Execute it.
        return operator(self, args)

    def less_or_equal(self, args: list[Any]) -> bool:
        """check if the first argument of a built-in types is less_or_equal the
        second.

        Returns:
          (boolean): result of comparison
        Raises:
          ???
        """
        # Find our compatible less_or_equal operator
        try:
            operator = self.get_operator(less_or_equal_operators)
        except KeyError:
            # No operator found. We must be complex data type. Raise a
            # type error exception.
            raise TypeError('not a built-in type')

        # We found an operator. Execute it.
        return operator(self, args)

    def valid_values(self, args: list[Any]) -> Optional[bool]:
        """check if the first argument is in the list of valid values in the
        second argument. Arguments are expected to be fully evaluated
        and valid values are expected to be of the same type.

        Returns:
          None: if one of the arguments is undefined
          (boolean): result of comparison
        Raises:
          ???

        """
        # Make sure we have two arguments
        if args[0] == None or args[1] == None: return None

        # Evaluate
        try:
            # Try simple type comparison
            return self.valid_values_simple(args)
        except TypeError:
            # Must be complex type.
            return self.valid_values_complex(args)

        
    def valid_values_simple(self, args: list[Any]) -> bool:
        """check if the two arguments of built-in types are valid_values. Neither
        arguments must be None.

        Returns:
          (boolean): result of comparison
        Raises:
          ???
        """
        # Find our compatible valid_values operator
        try:
            operator = self.get_operator(valid_values_operators)
        except KeyError:
            # No operator found. We must be complex data type. Raise a
            # type error exception.
            raise TypeError('not a built-in type')

        # We found an operator. Execute it.
        return operator(self, args)

    def valid_values_complex(self, args: list[Any]) -> bool:
        """Check if a complex data value specified in the first argument is in
        the list of valid values specified in the second
        arguent. This assumes that the values are valid for this
        type (e.g., all required properties are present)

        Returns:
          (boolean): result of comparison
        Raises:
          ???

        """
        for valid_value in args[1]:
            if self.equal([args[0], valid_value]):
                return True
        # No values matched
        return False

    def has_entry(self, args: list[Any]) -> Optional[bool]:
        """check if the second argument is in the list of valid values in the
        first argument. Arguments are expected to be fully evaluated
        and valid values are expected to be of the same type.

        Returns:
          None: if one of the arguments is undefined
          (boolean): result of comparison
        Raises:
          ???

        """
        # Make sure we have two arguments
        if args[0] == None or args[1] == None: return None

        # Evaluate
        try:
            # Try simple type comparison
            return self.has_entry_simple(args)
        except TypeError:
            # Must be complex type.
            return self.has_entry_complex(args)

        
    def has_entry_simple(self, args: list[Any]) -> bool:
        """check if the two arguments of built-in types are has_entry. Neither
        arguments must be None.

        Returns:
          (boolean): result of comparison
        Raises:
          ???
        """
        # Find our compatible has_entry operator
        try:
            if isinstance(args[0], list):
                operator = self.get_operator(list_has_entry_operators)
            elif isinstance(args[0], dict):
                operator = self.get_operator(map_has_entry_operators)
            else:
                raise TypeError('not a list or map type')
        except KeyError:
            # No operator found. We must be complex data type. Raise a
            # type error exception.
            raise TypeError('not a built-in type')

        # We found an operator. Execute it.
        return operator(self, args)

    def has_entry_complex(self, args: list[Any]) -> bool:
        """Check if a complex data value specified in the second argument is
        an entry the list of values specified in the second
        arguent. This assumes that the values are valid for this type
        (e.g., all required properties are present)

        Returns:
          (boolean): result of comparison
        Raises:
          ???
        """
        if isinstance(args[0], list):
            for entry in args[0]:
                if self.equal([args[1], entry]):
                    return True
        elif isinstance(args[0], dict):
            for entry_name, entry in args[0].items():
                if self.equal([args[1], entry]):
                    return True

        # No values matched
        return False

    # Arithmetic functions
    def arithmetic_function(self, function_name: str, args: list[Any]) -> Any:
        """Evaluate and arithmetic function

        Returns:
          Function return type.
        Raises:
          ???
        """
        # Find our type-compatible arithmetic operator
        try:
            operator = self.get_arithmetic_operator(function_name)
        except KeyError:
            # No operator found. Our type does not support arithmetic functions.
            raise TypeError(f"'{function_name}' not supported on '{self.name}'")
            
        # We found an operator. Execute it.
        return operator(self, args)


    def get_arithmetic_operator(self, function_name: str) -> Callable:
        """Get a type-compatible arithmetic operator.
        Returns:
          Operator
        Raises:
          TypeError: when we're a not supported type
        """

        # Try to get operator from parent type
        try:
            return self.parent.get_arithmetic_operator(function_name)
        except (AttributeError, te.CircularInheritance):
            pass
        
        # We don't have a parent type. Find our own operator.
        try:
            operator = arithmetic_operators[self.name][function_name]
            if operator: return operator
        except KeyError:
            # We're a unsupported type.
            pass

        # No operator found. Raise a type error exception.
        raise TypeError('not a compatible type')


    
