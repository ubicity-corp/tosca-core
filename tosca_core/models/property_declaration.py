"""
Module definining Tosca Property Declaration entities
"""
from __future__ import annotations

__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2014-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Typing support
from typing import Any, Optional

# Logging support
import logging
logger: logging.Logger = logging.getLogger(__name__)

# Database support
from tosca_core import db

# SQL Alchemy support
from sqlalchemy.orm import backref

# Exception support
import tosca_core.models.exceptions as te

# Function checking
from tosca_core.models.function import ToscaFunction
from tosca_core.models.function_declaration import is_function, pretty

# Declarations on which this declaration depends
import tosca_core.models.declaration

# Path
from tosca_core.models.path import ToscaPath
import tosca_core.models.presence as presence
import tosca_core.models.unchecked as unchecked

# Cached lookups for TOSCA built-in data types
from tosca_core.models import builtin_types

# Types used in relationships
import tosca_core.models.service_template


def as_list_declaration(value_declaration: Any, name: str, attr_or_prop: str) -> Any:
    """Wrap a value declaration in a declaration of a LIST of that value.

    A TOSCA path that reaches several entities returns one value per entity,
    so the declared result is a list whose entry schema is what a single
    entity would have returned.

    Every place that decides a path is multi-valued builds this declaration,
    and they have to keep building the same one: it is the type a template is
    checked against, so a divergence shows up as the same expression accepted
    in one position and rejected in another.

    Args:
      value_declaration: what one entity would have returned.
      name: what the list is named after -- a requirement or a type.
      attr_or_prop: 'properties' or 'attributes', which fixes the role
        when the value declaration has neither.

    The list takes the role and the required-ness of what it lists: a list of
    a property read through $get_attribute -- a reflected attribute -- is a
    list of that property, not of an attribute declared as one.
    """
    role = getattr(value_declaration, 'role', None)
    if role not in ('PROPERTY', 'ATTRIBUTE'):
        if attr_or_prop == 'properties':
            role = 'PROPERTY'
        elif attr_or_prop == 'attributes':
            role = 'ATTRIBUTE'
        else:
            role = 'ERROR'
    declaration = ToscaPropertyDeclaration(name='value_' + name, role=role)
    declaration._required = getattr(value_declaration, '_required', None)
    declaration.type_entity = builtin_types.get('list')
    # Copy the value declaration into the entry schema of the newly-created
    # declaration.
    declaration._entry_schema = ToscaPropertyDeclaration(role='SCHEMA')
    declaration._entry_schema.merge_augmented_declaration(value_declaration)
    return declaration


class ToscaPropertyDeclaration(tosca_core.models.declaration.ToscaDeclaration):
    """A ToscaPropertyDeclaration declares the presence of a Tosca
    property entity of a given name and type within other Tosca
    entities.

    A ToscaPropertyDeclaration can also be used to augment properties
    derived in a base class or in another declaration. In that case,
    the augmentation can do the following:
    - add validations
    - change the default value
    - assign a fixed value
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
    _entry_schema_id =                  db.Column(db.Integer, 
                                                  db.ForeignKey('tosca_declaration.id'),
                                                  nullable=True)
    _key_schema_id =                    db.Column(db.Integer, 
                                                  db.ForeignKey('tosca_declaration.id'),
                                                  nullable=True)
    # For input declarations in operation declarations.
    _operation_declaration_id =         db.Column(db.Integer, 
                                                  db.ForeignKey('tosca_operation_declaration.id'),
                                                  nullable=True)
    # For input declarations in workflow templates
    _workflow_id =                      db.Column(db.Integer, 
                                                  db.ForeignKey('tosca_workflow_template.id'),
                                                  nullable=True)
    # For input and output declarations in service templates
    _service_id =                       db.Column(db.Integer, 
                                                  db.ForeignKey('tosca_service_template.id'),
                                                  nullable=True)

    # For input and output parameters in function signatures
    _signature_id =                     db.Column(db.Integer, 
                                                  db.ForeignKey('tosca_signature.id'),
                                                  nullable=True)

    ################################################################################
    # Fields
    ################################################################################

    # Optional fields start with '_' and have corresponding getters
    # and setters to ensure that retrieving fields consistently raises
    # an AttributeError when not set.  Note that 'nullable' defaults
    # to True, but we explicitly set the 'nullable' flag for clarity.

    # To distinguish between different types of property declarations
    # within the same entity
    role =                              db.Column(db.Enum('ATTRIBUTE',
                                                          'PROPERTY',
                                                          'INPUT',
                                                          'OUTPUT',
                                                          'SCHEMA',
                                                          name='parameter'))

    _status =                           db.Column(db.String, nullable=True)
    _default =                          db.Column(db.PickleType, nullable=True)
    _validations =                      db.Column(db.PickleType, nullable=True)
    _required =                         db.Column(db.Boolean, nullable=True)
    _value =                            db.Column(db.PickleType, nullable=True)
    _mapping =                          db.Column(db.PickleType, nullable=True)

    @property
    def status(self) -> str:
        if self._status == None:
            raise AttributeError("'{0}' does not have 'status'".format(self.name))
        return self._status

    @property
    def default(self) -> Any:
        if self._default == None:
            raise AttributeError("'{0}' does not have 'default'".format(self.name))
        return self._default

    @default.setter
    def default(self, value: Any) -> None:
        if value != None: self._default = value

    @property
    def required(self) -> bool:
        if self._required == None:
            raise AttributeError("'{0}' does not have 'required'".format(self.name))
        return self._required

    @property
    def constraints(self) -> Any:
        if self._constraints == None:
            raise AttributeError("'{0}' does not have 'constraints'".format(self.name))
        return self._constraints

    @constraints.setter
    def constraints(self, value: Any) -> None:
        if value != None: self._constraints = value

    @property
    def validations(self) -> Any:
        if self._validations == None:
            raise AttributeError("'{0}' does not have 'validations'".format(self.name))
        return self._validations

    @validations.setter
    def validations(self, value: Any) -> None:
        if value != None: self._validations = value

    @property
    def value(self) -> Any:
        if self._value == None:
            raise AttributeError("'{0}' does not have 'value'".format(self.name))
        return self._value

    @value.setter
    def value(self, value: Any) -> None:
        if value != None: self._value = value

    @property
    def mapping(self) -> Any:
        if self._mapping == None:
            raise AttributeError("'{0}' does not have 'mapping'".format(self.name))
        return self._mapping

    @mapping.setter
    def mapping(self, mapping: Any) -> None:
        if mapping != None: self._mapping = mapping


    ################################################################################
    # Relationships
    ################################################################################

    # Optional relationships start with '_' and have corresponding
    # getters to ensure that retrieving the relationship consistently
    # raises an AttributeError when not present.

    _entry_schema =                     db.relationship('ToscaPropertyDeclaration',
                                                        remote_side=[tosca_core.models.declaration.ToscaDeclaration.id],
                                                        foreign_keys='ToscaPropertyDeclaration._entry_schema_id',
                                                        back_populates='_entry_schema_for')
    _key_schema =                       db.relationship('ToscaPropertyDeclaration',
                                                        remote_side=[tosca_core.models.declaration.ToscaDeclaration.id],
                                                        foreign_keys='ToscaPropertyDeclaration._key_schema_id',
                                                        back_populates='_key_schema_for')
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


    _entry_schema_for =                 db.relationship('ToscaPropertyDeclaration',
                                                        foreign_keys='ToscaPropertyDeclaration._entry_schema_id',
                                                        back_populates='_entry_schema')
    _entry_schema_for_type =            db.relationship('ToscaDataType',
                                                        foreign_keys='ToscaDataType._entry_schema_id',
                                                        back_populates='_entry_schema')
    _key_schema_for =                   db.relationship('ToscaPropertyDeclaration',
                                                        foreign_keys='ToscaPropertyDeclaration._key_schema_id',
                                                        back_populates='_key_schema')
    _key_schema_for_type =              db.relationship('ToscaDataType',
                                                        foreign_keys='ToscaDataType._key_schema_id',
                                                        back_populates='_key_schema')
    _data_type_for_type =               db.relationship('ToscaDataType',
                                                        foreign_keys='ToscaDataType._data_type_id',
                                                        back_populates='_data_type')
    ################################################################################
    # Model Navigation
    ################################################################################

    _containing_service =               db.relationship('ToscaServiceTemplate',
                                                        foreign_keys='ToscaPropertyDeclaration._service_id')
    _containing_operation_declaration = db.relationship('ToscaOperationDeclaration',
                                                        foreign_keys='ToscaPropertyDeclaration._operation_declaration_id')
    _containing_workflow =              db.relationship('ToscaWorkflowTemplate',
                                                        foreign_keys='ToscaPropertyDeclaration._workflow_id')
    _containing_function =              db.relationship('ToscaSignature',
                                                        foreign_keys='ToscaPropertyDeclaration._signature_id')


    @property
    def profile(self) -> Any:
        """Get profile. This overrides the 'profile' property defined in the
        base declaration class. We check if we're contained in some
        other declaration, and if so, get the profile from that
        declaration. If not, we'll call the base class.
        """
        if self._containing_service:
            return self._containing_service.profile
        elif self._containing_operation_declaration:
            return self._containing_operation_declaration.profile
        elif self._entry_schema_for:
            return self._entry_schema_for[0].profile
        elif self._key_schema_for:
            return self._key_schema_for[0].profile
        elif self._entry_schema_for_type:
            return self._entry_schema_for_type[0].profile
        elif self._key_schema_for_type:
            return self._key_schema_for_type[0].profile
        elif self._data_type_for_type:
            return self._data_type_for_type[0].profile
        elif self._containing_function:
            return self._containing_function.profile
        elif self._containing_workflow:
            return self._containing_workflow.profile
        else:
            # We're not part of some other declaration
            return super(ToscaPropertyDeclaration, self).profile


    ################################################################################
    # Constructor
    ################################################################################

    def __init__(self,
                 role: Optional[str] = None,
                 status: Optional[str] = None,
                 entry_schema: Optional[ToscaPropertyDeclaration] = None,
                 key_schema: Optional[ToscaPropertyDeclaration] = None,
                 default: Any = None,
                 constraints: Any = None,
                 validations: Any = None,
                 required: Optional[bool] = None,
                 value: Any = None,
                 mapping: Any = None,
                 **kwargs: Any
    ) -> None:
        """Instantiate a new ToscaPropertyDeclaration instance"""

        # First, call superclass constructor
        super(ToscaPropertyDeclaration, self).__init__(**kwargs)

        # ToscaPropertyDeclaration-specific initialization. 
        if role != None: self.role = role
        if status != None: self._status = status
        if default != None: self._default = default
        if required!= None: self._required = required
        if constraints: self._constraints = constraints
        if validations: self._validations = validations
        if value != None: self._value = value
        if mapping: self._mapping = mapping
        if entry_schema: self._entry_schema = entry_schema
        if key_schema: self._key_schema = key_schema


    ################################################################################
    # Implementation of reserved keywords
    ################################################################################

    def SELF(self) -> Any:
        """Return the type or declaration for the entity referred to by SELF
        for this declaration. SELF refers to nodes or relationships
        only. All other declarations retrieve SELF from their
        containing declaration or containing type.

        Returns:
          ToscaManagedDeclaration or ToscaManagedType

        Raises:
          AttributeError: if the template has no containing managed
            type or managed declaration
        """
        if self._containing_operation_declaration:
            return self._containing_operation_declaration.SELF()
        else:
            return super(ToscaPropertyDeclaration, self).SELF()

    
    def SOURCE(self) -> Any:
        """Return the type or declaration for the entity referred to by SOURCE
        for this template. SOURCE applies to relationships only. All
        other entities retrieve SOURCE from their containing type or
        declaration. If the declaration is not ultimately contained by
        a relationship type or relationship declaration, an
        AttributeError will be raised.

        Returns:
          ToscaRelationshipType or ToscaRelationshipDeclaration

        Raises:
          AttributeError: if the declaration has no containing
            relationship type or relationship declaration
        """
        if self._containing_operation_declaration:
            return self._containing_operation_declaration.SOURCE()
        else:
            return super(ToscaPropertyDeclaration, self).SOURCE()

    
    def TARGET(self) -> Any:
        """Return the type or declaration for the entity referred to by TARGET
        for this template. TARGET applies to relationships only. All
        other entities retrieve TARGET from their containing type or
        declaration. If the declaration is not ultimately contained by
        a relationship type or relationship declaration, an
        AttributeError will be raised.

        Returns:
          ToscaRelationshipType or ToscaRelationshipDeclaration

        Raises:
          AttributeError: if the declaration has no containing
            relationship type or relationship declaration
        """
        if self._containing_operation_declaration:
            return self._containing_operation_declaration.TARGET()
        else:
            return super(ToscaPropertyDeclaration, self).TARGET()

    
    ################################################################################
    # Convenience functions
    ################################################################################

    def is_required(self) -> bool:
        """Is this property required?"""
        try:
            return self.required
        except AttributeError:
            # No 'required' attribute present, which means the
            # property is required
            return True

    def has_templated_type(self) -> bool:
        """Does this property declaration use a templated type -- the type
        parameter '<T>' or the base 'scalar' type, whose concrete
        scalar-unit type is resolved from context (see
        resolve_templated_type)?

        TODO: this is a fragile
        string match -- a custom profile that defines a data type
        literally named 'scalar' (or '<T>') would be misclassified as
        templated. Identify templated types structurally instead.
        """
        return self.type == 'scalar' or self.type == '<T>'

    ################################################################################
    # Sub-entity retrieval functions. Sub-entities are retrieved from
    # this declaration as well as from the declaration's types
    ################################################################################

    def get_entry_schema(self) -> Optional[ToscaPropertyDeclaration]:
        """Get the entry_schema for this property declaration.  Check our type
        entity if we don't have one.

        Returns
          entry_schema(ToscaPropertyDeclaration) or None if no entry
            schema defined

        Raises:
          None
        """
        # Return our own entry_schema if it exists
        try:
            return self.entry_schema
        except AttributeError:
            pass

        # This declaration does not specify an entry schema. Try
        # our type instead. A refinement that states no entry schema of
        # its own carries the one it refines, which the pass that runs
        # before validation merged into it.
        return self.type_entity.get_entry_schema()


    def get_key_schema(self) -> Optional[ToscaPropertyDeclaration]:
        """Get the key_schema for this property declaration.  Check our type
        entity if we don't have one.

        Returns
          key_schema(ToscaPropertyDeclaration) or None of no key
            schema defined

        Raises:
          None
        """
        # Return our own key_schema if it exists
        try:
            return self.key_schema
        except AttributeError:
            pass

        # This declaration does not specify an key schema. Try
        # our type instead.
        return self.type_entity.get_key_schema()


    def is_required_along(self, path: list) -> bool:
        """Whether the value 'path' reaches within this declaration's value is
        required at every step: each field on the way is required, and no step
        selects an entry of a list or map, which may be absent. An empty path
        is the value itself, which this declaration answers for.

        Args:
          path (list): the steps below this declaration's value
        Returns:
          bool
        Raises:
          KeyError: when a step names no field
        """
        declaration = self
        for step in path:
            if declaration.type_entity.is_list() or declaration.type_entity.is_map():
                return False
            declaration = declaration.get_property_declaration(step)
            if not declaration.is_required():
                return False
        return True

    def get_property_declaration(self, property_name: Any) -> ToscaPropertyDeclaration:
        """Return the declaration for the property specified in
        'property_name'. We override the 'get_property_declaration'
        method defined in the base ToscaDeclaration class to support
        TOSCA Path expressions that retrieve sub-entities from lists
        or maps.

        Args:
          property_name (integer, string, or ToscaPath): the property for
            which to return the declaration.
        Returns:
          ToscaPropertyDeclaration
        Raises:
          KeyError: when property not found
        """
        # Unless we are a list or a map, just delegate to our base class
        if not self.type_entity.is_list() and not self.type_entity.is_map():
            return super(ToscaPropertyDeclaration, self).get_property_declaration(property_name)

        # First, check if we have a ToscaPath
        try:
            path = ToscaPath(property_name)
            index = path.entity
            sub_property_name = path.sub_entity
        except TypeError:
            # Not a path
            index = property_name
            sub_property_name = None

        # Make sure index is valid for our type
        if self.type_entity.is_list():
            integer_type = builtin_types.get('integer')
            declaration = integer_type.create_declaration(name='list_index')
            try:
                validated_index = declaration.validate_value(self, index)
            except Exception:
                # Not a valid list index
                error = "'{0}': '{1}' is not a valid list index".format(
                    self.name, index)
                logger.error(error)
                raise KeyError(error)
        elif self.type_entity.is_map():
            if not isinstance(index, str):
                # Not a valid map key
                error = "'{0}': '{1}' is not a valid map key".format(
                    self.name, index)
                logger.error(error)
                raise KeyError(error)

        # Return declaration, resolved through 'get_entry_schema' so
        # that a descending path into a refined map or list answers:
        # an augmentation carries only what it changes until its
        # containing type's properties are validated, and for a node
        # type that is after its capabilities, artifacts and
        # requirements. Reading the raw field here failed such a path
        # with a 'not found' naming neither the refinement nor the
        # cause. The raw field is still what raises when there is no
        # entry schema anywhere, so that case reports as it always has.
        entry_schema = self.get_entry_schema()
        if entry_schema == None:
            entry_schema = self.entry_schema
        if sub_property_name:
            return entry_schema.get_property_declaration(sub_property_name)
        else:
            return entry_schema
        
    ################################################################################
    # Entity Refinement and Augmentation Supports
    ################################################################################

    def get_augmented_declaration(self) -> ToscaPropertyDeclaration:
        """Return the property declaration for which this declaration is an
        augmentation. Note that only property and attribute
        declarations can get augmented.

        Returns:
          ToscaPropertyDeclaration: declaration for which we are an
            augmentation
        Raises:
          KeyError: if we are not an augmentation
        """

        # Get entity declaration map based on our role
        if self.role == 'PROPERTY':
            declaration_map_name = 'properties'
        elif self.role == 'ATTRIBUTE':
            declaration_map_name = 'attributes'
        else:
            # Other 'data' declarations can not be augmentations
            raise KeyError("{0} declaration '{1}' is not an augmentation".format(
                self.role, self.name))

        # Find the augmentation
        if self._containing_type:
            # This property declaration is inside a type
            # definition. Get the declaration for which we are an
            # augmentation from the containing type.
            return self._containing_type.get_entity_declaration_to_augment(
                declaration_map_name, self.name)
        elif self._containing_declaration:
            # This declaration is inside another declaration. Get the
            # declaration for which we are an augmentation from the
            # containing declaration.
            return self._containing_declaration.get_entity_declaration_to_augment(
                declaration_map_name, self.name)
        else:
            # The only declarations that don't have a containing type
            # nor a containing declaration are synthetically-created
            # declarations (using the create_declaration
            # function). However, these declarations are never augmentations.
            raise KeyError("property declaration '{}' is not an augmentation".format(self.name))

    # Fields 'merge_augmented_declaration' below copies, checked by
    # 'get_unmerged_fields'. The schemas are checked with them.
    merged_fields = tosca_core.models.declaration.ToscaDeclaration.merged_fields + (
        'role', '_status', '_default', '_required', '_value', '_mapping',
        '_entry_schema', '_key_schema',
    )

    def merge_augmented_declaration(self, property_declaration: ToscaPropertyDeclaration) -> None:
        """Override a attribute with values from a second attribute"""

        # First, call superclass augment method
        super(ToscaPropertyDeclaration, self).merge_augmented_declaration(property_declaration)

        # Merge fields we don't already have
        self.merge_augmented_field('role', property_declaration)
        self.merge_augmented_field('_status', property_declaration)
        self.merge_augmented_field('_default', property_declaration)
        self.merge_augmented_field('_required', property_declaration)
        self.merge_augmented_field('_value', property_declaration)
        self.merge_augmented_field('_mapping', property_declaration)
        self.merge_augmented_entry_schema(property_declaration)
        self.merge_augmented_key_schema(property_declaration)
        self.merge_augmented_validations(property_declaration)

    def merge_augmented_validations(self, property_declaration: ToscaPropertyDeclaration) -> None:
        """Augment validations if necessary"""
        try:
            augmented_validations = property_declaration.validations
        except AttributeError:
            # Augmented property declaration not have
            # 'validations'. Nothing to do
            return

        # Augmented declaration has validations that are not
        # empty. Combine with our own validations if we have any.
        try:
            validations = self.validations
            self.validations = { '$and': [ augmented_validations, validations ] }
        except (AttributeError, TypeError):
            # We don't have our own validations.
            self.validations = augmented_validations

    def merge_augmented_entry_schema(self, property_declaration: ToscaPropertyDeclaration) -> None:
        # Does property declaration have an entry schema
        try:
            entry_schema= property_declaration.entry_schema
        except AttributeError:
            # Nothing to do
            return

        # Already merged: the entry schema we hold is the augmented
        # declaration's own, referenced by an earlier merge. Merging
        # it into itself would alter a declaration that belongs to
        # the one we augment.
        try:
            if self.entry_schema is entry_schema:
                return
        except AttributeError:
            pass

        # Augment entry schema if we have 
        try:
            self.entry_schema.merge_augmented_declaration(entry_schema)
        except AttributeError:
            # We don't augment the entry schema. Just reference entry
            # schema of the declaration we're augmenting.
            self._entry_schema = entry_schema

        # All don
        return

    def merge_augmented_key_schema(self, property_declaration: ToscaPropertyDeclaration) -> None:
        # Does property declaration have an key schema
        try:
            key_schema= property_declaration.key_schema
        except AttributeError:
            # Nothing to do
            return

        # Already merged: the key schema we hold is the augmented
        # declaration's own, referenced by an earlier merge. Merging
        # it into itself would alter a declaration that belongs to
        # the one we augment.
        try:
            if self.key_schema is key_schema:
                return
        except AttributeError:
            pass

        # Augment key schema if we have 
        try:
            self.key_schema.merge_augmented_declaration(key_schema)
        except AttributeError:
            # We don't augment the key schema. Just reference key
            # schema of the declaration we're augmenting.
            self._key_schema = key_schema

        # All don
        return

    ################################################################################
    # Property template validation functions
    ################################################################################

    def validate_value(self, context: Any, property_value: Any, is_default: bool = False, check_presence: bool = False,
                       check_required_fields: bool = True) -> Any:
        """Check if the provided property value template is valid for the
        specified property declaration.

        This is the main method called for validating a property value
        against a property declaration. Note that 'None' is always
        considered a valid value for any declaration.

        This method does the following:

        1. First, we try to validate the provided 'property_value' as
           a TOSCA function. This will raise a TypeError if the value
           is not a function.
        2. If the value is not a function, we try to find the
           validator for this property declaration based on the
           assumption that it has a 'simple' (built-in) type. If we
           find a validator, we use it to validate the property
           value. This will raise a TypeError if no validator is
           found, in which case this property declaration must have a
           complex type.
        3. If the value does not have a simple type, we validate using
           the complex type validator, which will recursively validate
           sub-properties.

        Args:
          context(ToscaTemplate, ToscaDeclaration, or ToscaType): the
            context within which to validate function values. Note
            that if the function is a $value function (used only
            for constraints), the context has to be the data type or
            property declaration for which the constraints are
            defined.
          property_value (Python value): the property value template
            to validate against this property declaration.
          is_default(boolean): set to true when validating default
            values.
          check_presence(boolean): if set to true and this property is
            required, check if the property value is guaranteed to
            always return a value.
          check_required_fields(boolean): if set to false, a value of a
            complex type -- at any depth, and in the entries of a list or
            map -- may lack fields its type declares required. Its type is
            checked all the same.
        Returns:
          (python value): fully validated and resolved property value
        Raises:
          ValidationError: when the property value is invalid for this
            property declaration.
        """
        # 'None' is always considered a valid value for any
        # declaration.
        if property_value == None: return None

        # Validate and resolve
        try:
            # Is the property value a function?
            return self.validate_function_value(context, property_value,
                                                is_default=is_default, check_presence=check_presence)
        except TypeError:
            # Not a function. Must be an actual (python) property
            # value.
            try:
                # Does the property have a simple type?
                return self.validate_simple_value(
                    context, property_value, check_required_fields=check_required_fields)
            except TypeError:
                # Must have a complex type
                return self.validate_complex_value(
                    context, property_value, check_required_fields=check_required_fields)


    def validate_function_value(self, context: Any, property_value: Any,
                                is_default: bool = False, check_presence: bool = False, value_declaration: Optional[ToscaPropertyDeclaration] = None,
                                **kwargs: Any) -> Any:
        """Check if the provided property value is a valid function value for
        this property declaration.

          context(ToscaTemplate, ToscaDeclaration, or ToscaType): the
            context within which to validate function values. Note
            that if the function is a $value function (used only
            for constraints), the context has to be the data type or
            property declaration to which the constraints are
            applied.
          property_value (Python value): the property value template
           that has the function that needs to be validated.
          is_default(boolean): set to true when validating default
            values.
          check_presence(boolean): if set to true and this property is
            required, check if the function value is guaranteed to
            always return a value.
        Returns:
          (python value): fully validated and resolved function value
        Raises:
          TypeError: if 'property_value' is not a function
          ValidationError: when the property value is invalid for this
            property declaration.
        """
        logger.debug("'%s': validating function value '%s'",
                     self.name, str(property_value))

        # First, check if the property value is a function. This check
        # will raise a TypeError if 'property_value' is not a function
        # or a ValidationError if there are errors in the function
        # expression. We handle other possible exceptions here.
        try:
            function = ToscaFunction(property_value, context, value_declaration=value_declaration, **kwargs)
        except (te.FunctionNotFound, te.SignatureNotFound, ValueError) as e:
            logger.error("Property '%s': %s", self.name, str(e))
            raise te.ValidationError('invalid function', str(e))

        # The function value is valid. Validate the declaration for
        # the function return value.
        try:
            result = function.get_result_declaration(context, value_declaration=value_declaration)
            if not result:
                # Function can return any result. Defer validation
                # until runtime.
                return function.expression        
        except Exception as e:
            raise te.ValidationError('invalid function result', str(e))

        # Make sure the function return declaration is compatible with
        # this property declaration. Normally the function's result type
        # must be the property's type or a subtype of it. But when the
        # result type is an unresolved templated/abstract type -- e.g.
        # to_scalar declares its result as the abstract 'scalar' because
        # the concrete scalar-unit type cannot be resolved from its
        # (magnitude, units) arguments -- reverse the check: the
        # property's concrete type must be a subtype of the function's
        # abstract result type (is 'Length' a 'scalar'?), not the other
        # way round.
        if result.has_templated_type():
            compatible = self.type_entity.has_type(result.type_entity)
        else:
            compatible = result.has_type(self.type_entity)
        if not compatible:
            logger.debug("Property '%s' of type '%s': %s returns value of type '%s'",
                         self.name, self.type, function.name, result.type)
            error = "'${0}' return type '{1}' incompatible with '{2}'".format(function.name,
                                                                              result.type,
                                                                              self.type)
            raise te.ValidationError('invalid function result', error)

        # If the property declaration defines an entry schema, the
        # type of the function return value must have a compatible
        # entry schema. The return declaration is read through
        # 'get_entry_schema', which answers through an augmentation:
        # the declaration a function resolves to may be a refinement
        # whose entry schema is merged in only when its containing
        # type's properties are validated, and a node type validates
        # its capabilities, artifacts and requirements before that.
        # Reading the raw field here would report a refinement as
        # having no entry schema at all.
        try:
            entry_schema_type = self.entry_schema.type_entity
        except AttributeError:
            # Either we declare no entry schema, or the one we declare
            # resolves to no type -- an entry schema augmentation that
            # restates only a validation, say. Nothing to check a
            # return value against in either case.
            entry_schema_type = None
        if entry_schema_type != None:
            try:
                result_entry_schema = result.get_entry_schema()
            except (AttributeError, te.TypeNotFound):
                # The return declaration has no type, so no entry
                # schema can be resolved from it either.
                result_entry_schema = None
            if result_entry_schema == None:
                # The property declaration defines an entry schema,
                # but the type of the function return value doesn't.
                logger.error("Property '%s' of type '%s': %s returns type '%s' without entry schema",
                             self.name, self.type, function.name, result.type)
                error = "{0} returns <{1}> without entry_schema".format(function.name,
                                                                        result.type)
                raise te.ValidationError('invalid function result', error)
            if not result_entry_schema.has_type(entry_schema_type):
                logger.debug("Property '%s' of type '%s': %s returns '%s' with incompatible entry schema '%s'",
                             self.name, self.type, 
                             function.name, result.type,
                             result_entry_schema.type)
                error = "{0} returns <{1}> with incompatible entry schema <{2}>".format(function.name,
                                                                                        result.type,
                                                                                        result_entry_schema.type)
                raise te.ValidationError('invalid function result', error)

        # If we don't need to check return value presence or this is
        # an optional property there is nothing further to validate. An
        # attribute declared only as an attribute is never required:
        # TOSCA gives attribute definitions no 'required' keyname, and an
        # operation reading one is checked where it reads it.
        if not check_presence or not self.is_required() or self.role == 'ATTRIBUTE':
            return function.expression

        # Property value must be present. If there is a default
        # defined and we're not that default value, a value is always
        # available.
        try:
            default = self.default
            # We have a default. Only check if we are that
            # default.
            check_required = is_default
        except AttributeError:
            # No default. Make sure return value is present.
            check_required = True
        if not check_required:
            return function.expression

        # Make sure the function return value is always present. Pass
        # the result declaration to avoid having to look it up again.
        function.result_declaration = result
        with presence.checking(self, context):
            present = function.is_return_value_present(context)
        if not present:
            raise te.ValidationError(
                'invalid function result',
                presence.explain(present, str(function),
                                 f"required but {function} returns optional value"))
            
        # Everything OK
        return function.expression


    def validate_simple_value(self, context: Any, property_value: Any,
                              check_required_fields: bool = True, **kwargs: Any) -> Any:
        """Check if the provided value is valid for the property type
        specified in this property declaration. This method assumes
        that the property type is a 'simple' (built-in) TOSCA
        type. This method raises a TypeError if the property has a
        complex type.

        Args:
          context(ToscaTemplate, ToscaDeclaration, or ToscaType): the
            context within which to validate function values. Note
            that if the function is a $value function (used only
            for constraints), the context has to be the data type or
            property declaration for which the constraints are
            defined.
          property_value (Python value): the property value template
            to validate against this property declaration.

        ``**kwargs`` forwards flags like ``skip_validation_for`` down to
        ``are_validations_satisfied``.

        Returns:
          (Python value): validated and resolved property value
        Raises:
          TypeError: if this property declaration has a complex type
          ValidationError: when the property value is invalid for this
            property declaration.
        """
        # Get the property type
        type_entity = self.type_entity
        logger.debug("Property '%s': validating '%s' for '%s'",
                     self.name, property_value, type_entity.name)

        # Assuming a built-in type, validate the property value
        # against this type. This will raise a TypeError if the
        # type is a complex data type.
        error = type_entity.validate_value_for_type(property_value)
        if error:
            logger.debug("%s is incompatible value for property %s of type %s",
                         property_value, self.name, self.type)
            raise te.ValidationError('invalid value', error)

        # Does the value satisfy the specified validations?
        if not self.are_validations_satisfied(context, property_value, **kwargs):
            raise te.ValidationError('invalid value', 'validations not satisfied')

        # Are the map keys valid for the key_schema (when one is
        # declared)? This can raise a ValidationError.
        self.validate_keys_for_key_schema(context, property_value)

        # Are list or map values valid for the entry_schema. This can
        # raise a ValidationError.
        return self.validate_values_for_entry_schema(
            context, property_value, check_required_fields=check_required_fields)


    def validate_values_for_entry_schema(self, context: Any, property_value: Any,
                                         check_required_fields: bool = True) -> Any:
        """If property value is a list or a map, validate the provided value
        for this declaration's entry schema.

        Args:
          context(ToscaTemplate, ToscaDeclaration, or ToscaType): the
            context within which to validate function values. Note
            that if the function is a $value function (used only
            for constraints), the context has to be the data type or
            property declaration for which the constraints are
            defined.
          property_value (Python value): the property value template
            to validate against this property declaration.
        Returns:
          (Python value): validated and resolved property value
        Raises:
          TypeError: if this property declaration has a complex type
          ValidationError: when the property value is invalid for this
            property declaration.
        """
        # First, try to get entry schema.
        entry_schema_declaration = self.get_entry_schema()
        if not entry_schema_declaration:
            # No entry schema defined. This is the common occurrence,
            # since entry schemas are only valid for lists or maps
            return property_value

        validation_errors = dict()
        try:
            # Do we have a map?
            validated_value = dict()
            for key, value in property_value.items():
                try:
                    validated_value[key] = entry_schema_declaration.validate_value(
                        context, value, check_required_fields=check_required_fields)
                except te.ValidationError as e:
                    logger.error("'%s': '%s' is invalid for entry_schema '%s'",
                                 self.name, value, entry_schema_declaration.type_entity.name)
                    validated_value[key] = value
                    validation_errors[key] = e.errors
        except AttributeError:
            # Not a map. Must be a list
            validated_value = list()
            try:
                count = 0
                for value in property_value:
                    try:
                        validated_value.append(entry_schema_declaration.validate_value(
                            context, value, check_required_fields=check_required_fields))
                    except te.ValidationError as e:
                        logger.debug("'%s': '%s' is invalid for entry_schema '%s'",
                                     self.name, value, entry_schema_declaration.type_entity.name)
                        validated_value.append(value)
                        validation_errors[count] = e.errors
                    count = count+1
            except Exception as e:
                # Validator error
                raise te.ValidationError('validator error', str(e))
        except Exception as e:
            # Validator error
            raise te.ValidationError('validator error', str(e))

        # All done
        if validation_errors:
            raise te.ValidationError('invalid entries for entry schema', validation_errors)
        return validated_value


    def validate_keys_for_key_schema(self, context: Any, property_value: Any) -> None:
        """If a key_schema is declared (only meaningful for maps),
        validate every key in property_value against that schema.
        Mirrors validate_values_for_entry_schema but only checks keys
        and never rewrites the value; the property value itself is
        returned by the entry_schema validator.

        Args:
          context: validation context for resolving function values.
          property_value: the map (or any other value) to inspect.
        Raises:
          ValidationError: when one or more keys violate the
            key_schema.
        """
        # key_schema only matters for maps; non-map values fall to the
        # entry-schema or type-level validator. Check that first so we
        # don't call get_key_schema (and trip its "key schema not
        # allowed" logger) for integers, lists, scalars, etc.
        try:
            keys = property_value.keys()
        except AttributeError:
            return

        key_schema_declaration = self.get_key_schema()
        if key_schema_declaration is None:
            return

        validation_errors = dict()
        for key in keys:
            try:
                key_schema_declaration.validate_value(context, key)
            except te.ValidationError as e:
                logger.error("'%s': key '%s' is invalid for key_schema '%s'",
                             self.name, key, key_schema_declaration.type_entity.name)
                validation_errors[key] = e.errors

        if validation_errors:
            raise te.ValidationError('invalid keys for key schema', validation_errors)


    def validate_complex_value(self, context: Any, property_value: Any,
                               check_required_fields: bool = True) -> Any:
        """Check if the provided value is valid for the property type
        specified in this property declaration. This method assumes
        that the property type is a 'complex' TOSCA data type, so it
        will validate sub-properties against their property
        declarations.

        Args:
          context(ToscaTemplate, ToscaDeclaration, or ToscaType): the
            context within which to validate function values. Note
            that if the function is a $value function (used only
            for constraints), the context has to be the data type or
            property declaration for which the constraints are
            defined.
          property_value (Python value): the property value template
            to validate against this property declaration.
        Returns:
          (Python value): validated and resolved property value
        Raises:
          ValidationError: when the property value is invalid for this
            property declaration.
        """
        # Validate sub-properties. This can raise a ValidationError
        validated_value = self.validate_property_templates(
            context, property_value, check_required_fields=check_required_fields)

        # Validate against any local validations
        if not self.are_validations_satisfied(context, validated_value):
            raise te.ValidationError('invalid value', 'validations not satisfied')

        # All done
        return validated_value


    def are_validations_satisfied(self, context: Any, value: Any, **kwargs: Any) -> bool:
        """Does the provided value satisfy all validations defined in this
        declaration?

        ``**kwargs`` forwards flags like ``skip_validation_for`` down to
        the underlying type's ``are_validations_satisfied`` so the
        recursion guard works.
        """
        # First check our type's validations.  Note that we need to
        # pass this property declaration as context because the $value
        # function needs it.
        if not self.type_entity.are_validations_satisfied(context, value, **kwargs):
            return False

        # Then check our own validations.
        try:
            validations = self.validations
            function = ToscaFunction(validations, context, self)
            # A clause that could not be evaluated here is recorded as
            # not checked, and does not fail the value
            return unchecked.verdict(
                function.evaluate(context, value=value, value_declaration=self),
                f"property '{self.name}'", value)
        except AttributeError:
            # No validations
            return True
        except Exception as e:
            logger.error("%s: error validating %s: %s", self.name, str(value), str(e), stack_info=False)
            return False

    ################################################################################
    # Support for resolving and upgrading property declarations
    # (before validation)
    ################################################################################

    def resolve_functions_in_declared_values(self, context: Any) -> None:
        """Resolve funtions in the 'default' and 'value' fields of this property
        declaration to the internal function syntax.

        Raises:
          None
        """
        # If this property declaration assigns a value, make sure that
        # value is resolved to the internal function syntax
        try:
            value = self.value
            try:
                self.value = self.resolve_functions_in_value(context, value)
            except Exception as e:
                logger.error("Error resolving function value %s: %s", str(value), str(e))
        except AttributeError:
            # No value to resolve
            pass
        # If this property declaration assigns a default, make sure
        # that default is upgraded to the new syntax
        try:
            default = self.default
            try:
                self.default = self.resolve_functions_in_value(context, default)
            except Exception as e:
                logger.error("Error resolving default function value %s: %s", str(default), str(e))
        except AttributeError:
            # No default to resolve
            pass


    def upgrade_tosca_path_in_mapping(self, context: Any) -> None:
        """This method only gets called after it has been established that old
        syntax was used
        """
        # Check if output defines a mapping
        try:
            mapping = self.mapping
        except AttributeError:
            # No mapping to resolve
            return

        # Upgrade mapping to the Version 2.0 TOSCA Path syntax.
        try:
            path = ToscaPath(mapping)
            self.mapping = path.upgrade(context)
        except Exception as e:
            logger.error("Error upgrading mapping %s: %s", str(mapping), str(e))
            pass


    ################################################################################
    # Support for validating templated property values
    ################################################################################

    def validate_value_presence(self, context: Any, value_templates: Optional[dict[str, Any]]) -> Optional[str]:
        """Check whether a fully evaluated value for this property declaration
        is guaranteed to be present within the provided context based
        on the provided dict of property value templates.
        """
        with presence.checking(self, context):
            return self._validate_value_presence(context, value_templates)

    def _validate_value_presence(self, context: Any, value_templates: Optional[dict[str, Any]]) -> Optional[str]:
        # First, check this property declaration's default, since if
        # the default is guaranteed to return a value then it doesn't
        # matter if the property value template does. Only the lookup
        # sits in the 'try': an AttributeError from the check itself is
        # not "no default".
        undecided = None
        try:
            property_value = self.default
            has_default = True
        except AttributeError:
            # No default value defined.
            has_default = False
        if has_default:
            answer = self.is_value_present(property_value, context)
            if answer:
                return None
            if isinstance(answer, presence.NotDecided):
                undecided = answer
            pass

        # There is no default, or the default is not guaranteed to
        # return a value. Check either the fixed value or the property
        # value template.
        try:
            property_value = self.value
            has_fixed_value = True
        except AttributeError:
            # No fixed value
            has_fixed_value = False
            try:
                if self.name in value_templates:
                    property_value = value_templates[self.name]
                    # An explicit 'prop: null' assignment satisfies
                    # presence only when the declared type is 'nil',
                    # for which null is the sole legal value. For
                    # every other type 'null' still means "no value"
                    # and falls through to the absent path -- this
                    # preserves the historical behavior at the five
                    # non-property callers.
                    if property_value is None and \
                       self.type_entity.has_type(builtin_types.get('nil')):
                        return None
                else:
                    property_value = None
            except (AttributeError, TypeError):
                # value_templates is None or not a mapping
                property_value = None

        # Check if property value is present
        if property_value != None:
            answer = self.is_value_present(property_value, context)
            if answer:
                return None
            if isinstance(answer, presence.NotDecided):
                undecided = answer

        # Not present. When the check could not decide, or found a loop,
        # say so rather than blame an optional parameter.
        if undecided is not None:
            return presence.Message(undecided.describe(f"the value of '{self.name}'"), undecided)

        # Return appropriate error message
        if property_value:
            if has_fixed_value:
                if has_default:
                    return "required but fixed value and default reference optional parameters"
                else: 
                    return "required but fixed value references optional parameter"
            else:
                if has_default:
                    return "required but value and default reference optional parameters"
                else: 
                    return "required but value references optional parameter"
        else:
            if has_default:
                return "required but default references optional parameter"
            else:
                return 'required but not specified'


    def is_value_present(self, parameter_value: Any, context: Any) -> Any:
        """If a parameter value is a function, make sure its return value
        exists within the given context. This function is only called
        during validation of service templates, so context is always a
        ToscaTemplate.

        Args:
          parameter_value(Python value): value for which to check
            presence
          context(ToscaTemplate): context within which to evaluate
            functions.

        Returns:
          True: if parameter is guaranteed to be present
          False: if parameter is optional
          Undecided or Circular (both false): when the check could not
            decide, or found the value defined in terms of itself

        Raises:
          None
        """
        # Check if parameter value represents a function. Only the
        # construction's TypeError means "not a function": one raised while
        # checking the function is not a reason to call it present.
        try:
            function = ToscaFunction(parameter_value, context)
        except TypeError:
            # Not a function. Value is always present.
            return True
        except Exception as e:
            # Function doesn't exist or has invalid arguments
            logger.error("%s FUNCTION ERROR %s", str(parameter_value), str(e))
            return presence.Undecided(f"{parameter_value} is not a function this check can read: {e}")
        try:
            return function.is_return_value_present(context)
        except Exception as e:
            logger.error("%s PRESENCE CHECK %s", str(parameter_value), str(e))
            return presence.Undecided(f"{type(e).__name__} while checking {parameter_value}: {e}")


    ################################################################################
    # Property template evaluation functions
    ################################################################################

    def get_evaluated_value(self, context: Any, value_templates: Any, **kwargs: Any) -> Any:
        """Get a fully evaluated value for this property declaration within
        the provided context based on the provided dict of property
        value templates.

        Args:
          context(ToscaInstance): the context within which to validate
            function values.
          value_templates: (dict of Python values): the property value
            templates from which to find the value to evaluate against
            this property declaration.
        Keyword Args:
          no_inputs(bool): if true, do not evaluate $get_input
            functions TOSCA Path arguments.
          no_tosca_path(bool): if true, do not evaluate functions with
            TOSCA Path arguments.
        Raises:
          ??
        """
        # Always use the fixed value if it exists
        try:
            value_to_evaluate = self.value
        except AttributeError:
            # No fixed value. Is there a value assigned in the
            # template?
            try:
                value_to_evaluate = value_templates[self.name]
            except KeyError:
                # No value assignment in the template.
                value_to_evaluate = None

        # Evaluate the value if we found one.
        if value_to_evaluate != None:
            try:
                evaluated_value = self.evaluate_value(context, value_to_evaluate, **kwargs)
            except Exception as e:
                logger.error("Error evaluating value '%s': %s", pretty(value_to_evaluate), str(e), exc_info=False)
                raise
        else:
            evaluated_value = None

        if evaluated_value == None:
            # Either we didn't find a value to evaluate, or the value
            # evaluated to None (e.g. because it references an
            # optional input or optional attribute). In that case, use
            # the default if there is one.
            try:
                value_to_evaluate = self.default
                evaluated_value = self.evaluate_value(context, value_to_evaluate, **kwargs)
            except AttributeError:
                # No value found
                evaluated_value = None
            except Exception as e:
                logger.error("Error evaluating value '%s': %s", pretty(value_to_evaluate), str(e))
                raise

        """
        # TODO: do we need to check if constraints are satisfied?
        if evaluated_value != None and not self.are_validations_satisfied(context, evaluated_value):
            logger.error("%s: evaluated value '%s' does not satisfy validation constraints",
                         self.name, str(evaluated_value))
            raise te.ValidationError("validations not satisfied")
        """
        
        # Everything OK
        return evaluated_value

        
    def evaluate_value(self, context: Any, property_value: Any, **kwargs: Any) -> Any:
        """Evaluate a templated property value by evaluating all functions.

        This is the main method called for evaluating a property value
        against a property declaration.  This method does the
        following:

        1. First, we assume the provided 'property_value' is an
           intrinsic function. We evaluate that function within the
           provided context. This will raise a TypeError if the value
           is not a function.
        2. Then, we assume the property has a 'simple' (built-in)
           type. We validate for that type. This will raise a
           TypeError if the property has a complex type.
        3. Finally, we evaluate for a complex type.

        Args:
          context(ToscaInstance): the context within which to validate
            function values.
          property_value (Python value): the property value template
            to evaluate against this property declaration.
        Keyword Args:
          no_inputs(bool): if true, do not evaluate $get_input
            functions TOSCA Path arguments.
          no_tosca_path(bool): if true, do not evaluate functions with
            TOSCA Path arguments.
          value(Python value): Has the value for $value function. This
            value is used when a property value includes a $value
            function. Defaults to None.
          value_declaration(ToscaPropertyDeclaration): Has the
            declaration for the value returned by the $value
            function. This is used in function evaluation code to
            determine the type of templated function
            arguments. Defaults to None.

        Raises:
          KeyError: if value not found
          ValueError: if entity not found
          ValidationError: if value is invalid for this declaration
        """

        # Make sure there is something to evaluate
        if property_value == None: return None

        # Evaluate based on the type
        try:
            # Is the property value a function?
            function_value = self.evaluate_function_value(context, property_value, **kwargs)
            return function_value
        except TypeError:
            # Not a function. Must be an actual (python) property
            # value.
            try:
                # Does the property have a simple built-in type?
                return self.evaluate_simple_value(context, property_value, **kwargs)
            except TypeError:
                # Must have a complex type
                return self.evaluate_complex_value(context, property_value, **kwargs)
        except Exception as e:
            logger.error("Unable to evaluate '%s': %s", pretty(property_value), str(e), exc_info=False)
            raise

    def evaluate_function_value(self, context: Any, property_value: Any, value_declaration: Optional[ToscaPropertyDeclaration] = None,
                                check_required_fields: bool = True, **kwargs: Any) -> Any:
        """Evaluate a function property value.

        Keyword Args:
          no_tosca_path(bool): if true, do not evaluate functions with
            TOSCA Path arguments.
          check_required_fields(bool): if false, the value the function
            returns may lack fields its type declares required.
        Raises:
          TypeError: when property value is not a function
          KeyError: if function value not found
          ValueError: if entity referred to by function is not found
          ValidationError: if the function value is invalid for this
            declaration
        """
        # Parse the function. This will raise a TypeError if the
        # property_value is not a function.
        function = ToscaFunction(property_value, value_declaration=value_declaration)

        # Evaluate the function and validate the value against the
        # property declaration. This can return KeyError or ValueError
        evaluated_value = function.evaluate(context, value_declaration=value_declaration, **kwargs)

        # If we're not traversing TOSCA Path or we're not evaluating
        # inputs, we may have a partially-evaluated function value
        # here. If so, don't validate.
        if is_function(evaluated_value):
            return evaluated_value
        
        # Don't validate '$value' function values, since the $value
        # function is only used inside validations themselves, so this
        # could result in inifinite loops.
        if not function.name == 'value':
            # Validate. This will raise a ValidationError if the
            # evaluated value is not valid for this property
            # declaration.
            validated_value = self.validate_value(
                self, evaluated_value, check_required_fields=check_required_fields)

        # All done
        return evaluated_value

            
    def evaluate_simple_value(self, context: Any, property_value: Any, **kwargs: Any) -> Any:
        """Evaluate a property values based on the assumption that the
        property type is a 'simple' (built-in) TOSCA type. This method
        raises a TypeError if the property has a complex type.

        Raises:
          TypeError: if this property declaration has a complex type
        """

        # Make sure we're a built-in type.  This will raise a
        # TypeError if the type is a complex data type.
        type_entity = self.type_entity
        if not type_entity.is_builtin_type():
            raise TypeError("Not a built-in type")

        if type_entity.is_map():
            # Evaluate all map entries if we have an entry schema
            if self.get_entry_schema():
                evaluated_value = dict()
                for entry_name, entry_value in property_value.items():
                    evaluated_value[entry_name] = self.get_entry_schema().evaluate_value(
                        context, entry_value, **kwargs)
            else:
                evaluated_value = property_value
        elif type_entity.is_list():
            # Evaluate all list entries if we have an entry schema
            if self.get_entry_schema():
                evaluated_value = list()
                for entry_value in property_value:
                    evaluated_value.append(self.get_entry_schema().evaluate_value(
                        context, entry_value, **kwargs))
            else:
                evaluated_value = property_value
        else:
             evaluated_value = property_value
        
        # Everything OK
        return evaluated_value


    def evaluate_complex_value(self, context: Any, property_value: Any, value: Any = None, value_declaration: Optional[ToscaPropertyDeclaration] = None, **kwargs: Any) -> dict[str, Any]:
        """Evaluate a property values based on the assumption that the
        property type is a 'complex' TOSCA type. 

        Raises:
          TypeError: if this property declaration does not have a complex type
        """
        # First, get property declarations
        property_declarations = self.get_property_declarations()

        # Evaluate each property
        evaluated_value = dict()
        for property_name, property_declaration, in property_declarations.items():
            try:
                try:
                    sub_value=value[property_name]
                except (KeyError, TypeError):
                    sub_value=None
                # Evaluate the sub_value
                evaluated = property_declaration.get_evaluated_value(
                    context, property_value, value=sub_value, value_declaration=property_declaration,
                    **kwargs)
                # A field without a value is absent, required or not.
                # Whether a required one may be missing is for
                # validation to decide, which treats absent and None
                # alike.
                if evaluated != None:
                    evaluated_value[property_name] = evaluated
            except Exception as e:
                logger.error(str(e))
                raise
        return evaluated_value

    
    ################################################################################
    # Support for resolving functions in templated property values
    ################################################################################

    def resolve_functions_in_value(self, context: Any, property_value: Any) -> Any:
        """Upgrade a value template that contains functions to the v2.0
        function syntax. Note that the caller will have already
        checked that old syntax was used

        Args:
          context(ToscaTemplate or ToscaDeclaration): the context
            within which to upgrade function values.
          property_value (Python value): the property value template
            to upgrade

        Returns:
          (Python value): upgraded property value

        Raises:
          None. If errors are encounterd, the original value is
            returned.
        """
        if property_value == None: return None
        
        try:
            # Is the property value a function?
            return self.resolve_function_value(context, property_value)
        except TypeError:
            # Not a function. Must be an actual (python) property
            # representing a TOSCA value.
            try:
                # Does the property have a simple type?
                return self.resolve_functions_in_simple_value(context, property_value)
            except TypeError:
                # Must have a complex type
                return self.resolve_functions_in_complex_value(context, property_value)
        except Exception as error:
            logger.error("Property '%s': error while upgrading '%s': %s", 
                         self.name, str(property_value), error)
            return property_value

    def resolve_function_value(self, context: Any, property_value: Any) -> Any:
        """Resolve a function property value to internal function syntax.

        Raises:
          TypeError: if the property value is not a function
        """
        
        # Resolve the function. This will raise a TypeError if the
        # property_value is not a function.
        function = ToscaFunction(property_value, context)

        # Return resolved function expression.
        return function.expression

    def resolve_functions_in_simple_value(self, context: Any, property_value: Any) -> Any:
        """Upgrade a property values based on the assumption that the
        property type is a 'simple' (built-in) TOSCA type. This method
        raises a TypeError if the property has a complex type.

        Raises:
          TypeError: if this property declaration has a complex type
        """

        # Make sure we're a built-in type.  This will raise a
        # TypeError if the type is a complex data type.
        type_entity = self.type_entity
        if not type_entity.is_builtin_type():
            raise TypeError("Not a built-in type")

        # Handle list and map
        if type_entity.is_map():
            entry_schema = self.get_entry_schema()
            if entry_schema:
                upgraded_value = dict()
                for name, value in property_value.items():
                    upgraded_value[name] = entry_schema.resolve_functions_in_value(
                        context, value)
            else:
                upgraded_value = property_value
        elif type_entity.is_list():
            entry_schema = self.get_entry_schema()
            if entry_schema:
                upgraded_value = list()
                for value in property_value:
                    upgraded_value.append(self.get_entry_schema().resolve_functions_in_value(
                        context, value))
            else:
                upgraded_value = property_value
        else:
             upgraded_value = property_value
        
        # Everything OK
        return upgraded_value

    def resolve_functions_in_complex_value(self, context: Any, property_value: Any) -> dict[str, Any]:
        """Upgrade a property values based on the assumption that the
        property type is a 'complex' TOSCA type. 

        Raises:
          TypeError: if this property declaration does not have a
            complex type
        """

        # First, get property declarations
        property_declarations = self.get_property_declarations()

        # Upgrade each property
        upgraded_value = dict()
        for name, value in property_value.items():
            property_declaration = property_declarations[name]
            upgraded_value[name] = property_declaration.resolve_functions_in_value(context, value)
        return upgraded_value

    
    ################################################################################
    # Support for validating constraints
    ################################################################################

    def validate_constraints(self, context: Any, constraints: list[dict[str, Any]]) -> dict[str, str]:
        """Check if the provided Version 1.x constraint expressions are
        valid. This check is performed before we upgrade Version 2.x
        constraint expressions to Version 2.x boolean functions. Since
        we will validate these boolean functions in a later step, all
        we need to do here is to check whether the constraint
        expression is valid.
        """
        v1_constraint_operators = [
            "equal",
            "greater_than",
            "greater_or_equal",
            "less_than",
            "less_or_equal",
            "in_range",
            "valid_values",
            "length",
            "min_length",
            "max_length",
            "pattern",
        ]

        # Validate each constraint
        validation_errors = {}
        for constraint in constraints:
            operation = constraint['operation']
            if operation == 'schema':
                # 'schema' is a valid 1.x constraint but has no TOSCA 2.0
                # boolean-function equivalent, so it cannot be upgraded.
                validation_errors[operation] = ("the 'schema' constraint has no "
                                                "TOSCA 2.0 equivalent and cannot "
                                                "be upgraded")
            elif operation not in v1_constraint_operators:
                validation_errors[operation] = 'invalid constraint operation'

        # All done
        return validation_errors

    def upgrade_constraints(self, constraints: list[dict[str, Any]]) -> dict[str, Any]:
        """Upgrade Version 1.x constraint expressions to Version 2.x boolean
        functions.
        """
        # Validate each constraint
        upgraded = list()
        for constraint in constraints:
            upgraded.append(self.upgrade_constraint(constraint))

        if len(upgraded) == 1:
            return upgraded[0]
        else:
            return { '$and': upgraded }

    def upgrade_constraint(self, constraint: dict[str, Any]) -> dict[str, Any]:
        """Upgrade a Version 1.x constraint expression to the corresponding
        Version 2.x boolean function on this property/attribute ($value).
        """
        from tosca_core.models.constraint import constraint_to_condition
        return constraint_to_condition('$value', constraint)
