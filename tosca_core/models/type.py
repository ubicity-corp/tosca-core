"""
Module definining Tosca Type Entity
"""
from __future__ import annotations

__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2014-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger: logging.Logger = logging.getLogger(__name__)

# Database support
from tosca_core import db

# SQL Alchemy support
from sqlalchemy.orm.collections import attribute_mapped_collection
from sqlalchemy import or_, and_

# Type hints
from typing import Any, Optional

# Support for TOSCA keywords that are shared between all entities
import tosca_core.models.entity

# Cached lookups for TOSCA built-in data types
from tosca_core.models import builtin_types

# Path
from tosca_core.models.path import ToscaPath

# Exception support
import sqlalchemy.orm.exc
import tosca_core.models.exceptions as te


class ToscaType(tosca_core.models.entity.ToscaEntityMixin, db.Model):
    """A ToscaType defines a named type in a profile. The ToscaType
    class is the base class for all TOSCA types, specifically for:

    - ToscaCapabilityType
    - ToscaDataType (used for properties, attributes, and parameters)
    - ToscaGroupType
    - ToscaInterfaceType
    - ToscaManagedType
    - ToscaNodeType (derived from ToscaManagedType)
    - ToscaRelationshipType (derived from ToscaManagedType)
    - ToscaArtifactType
    - ToscaPolicyType
    """

    ################################################################################
    # Polymorphic mapping
    ################################################################################

    type_class =    db.Column(db.String, index=True)
    __mapper_args__ = {
        'polymorphic_identity': 'type',
        'polymorphic_on': type_class
    }

    ################################################################################
    # Keys
    ################################################################################
    
    # Primary key
    id =            db.Column(db.Integer, primary_key=True)

    # Foreign keys
    _profile_id =   db.Column(db.Integer,
                              db.ForeignKey('tosca_profile.id'),
                              nullable=False,
                              index=True)
    _parent_id =    db.Column(db.Integer,
                              db.ForeignKey('tosca_type.id'),
                              nullable=True,
                              index=True)

    __table_args__ = (
        db.Index('ix_tosca_type_profile_class', '_profile_id', 'type_class'),
    )
    @property
    # URL fields in TOSCA schemas need parent_id to raise an
    # AttributeError when the type has no parent.
    def parent_id(self) -> int:
        if not self._parent_id:
            raise AttributeError("'{0}' does not have 'parent_id'".format(self.name))
        return self._parent_id

    ################################################################################
    # Fields
    #
    # Optional fields start with '_' and have corresponding getters
    # (and optionally setters) to ensure that retrieving fields
    # consistently raises an AttributeError when not set.  Note that
    # 'nullable' defaults to True, but we explicitly set the
    # 'nullable' flag for clarity.
    ################################################################################

    _short_name =              db.Column(db.String,     nullable=True)
    _version =                 db.Column(db.String,     nullable=True)

    # Valid_source_node_types is supported for relationship types and
    # capability types. It is defined here to avoid name conflicts.
    _valid_source_node_types = db.Column(db.PickleType, nullable=True)

    @property
    def short_name(self) -> str:
        if not self._short_name:
            raise AttributeError("'{0}' does not have 'short_name'".format(self.name))
        return self._short_name

    @property
    def version(self) -> str:
        if not self._version:
            raise AttributeError("'{0}' does not have 'version'".format(self.name))
        return self._version

    @property
    def qualified_name(self) -> str:
        profile_name = self.profile.well_known_name
        if profile_name:
            return profile_name + ':' + self.name
        else:
            return self.name

    @property
    def valid_source_node_types(self) -> list[str]:
        if self._valid_source_node_types == None:
            raise AttributeError("'{0}' does not have 'valid_source_node_types'".format(self.name))
        return self._valid_source_node_types

    ################################################################################
    # Relationships
    ################################################################################

    properties =    db.relationship('ToscaPropertyDeclaration',
                                    collection_class=attribute_mapped_collection('name'),
                                    primaryjoin="and_(ToscaType.id==ToscaPropertyDeclaration._containing_type_id,"
                                    "ToscaPropertyDeclaration.role=='PROPERTY')",
                                    cascade='all',
                                    back_populates='_containing_type',
                                    overlaps='attributes')
    attributes =    db.relationship('ToscaPropertyDeclaration',
                                    collection_class=attribute_mapped_collection('name'),
                                    primaryjoin="and_(ToscaType.id==ToscaPropertyDeclaration._containing_type_id,"
                                    "ToscaPropertyDeclaration.role=='ATTRIBUTE')",
                                    cascade='all',
                                    back_populates='_containing_type',
                                    overlaps='properties')

    ################################################################################
    # Model Navigation
    ################################################################################

    # Every type belongs to a profile
    profile =     db.relationship('ToscaProfile',
                                    foreign_keys='ToscaType._profile_id')

    @property
    def tosca_version(self) -> str:
        """Get tosca version from the profile.
        """
        return self.profile.tosca_version

    # Types may have parent types
    _parent =       db.relationship('ToscaType', remote_side=[id], backref='children',
                                    post_update=True)

    @property
    def parent(self) -> ToscaType:
        """Return parent type entity for this type entity

        Under normal operation, this method returns the type stored in
        the '_parent' attribute. This attribute is set during type
        validation. Since it is possible for this method to be called
        before the type has been validated, we need to handle the case
        where the parent attribute has not yet been set. We do this by
        checking if a 'derived_from' attribute exists and if so, we
        look up the 'derived_from' type.

        Returns:
          ToscaType entity for the type from which this type is
            derived

        Raises:
          AttributeError: if the type doesn't have a parent type
          te.TypeNotFound: if the parent type doesn't exist
        """

        # Raise AttributeError if parent is not set or None
        if self._parent is None:
            parent = self.profile.get_type(self.derived_from,
                                           self.type_class)
            if parent is self:
                raise te.CircularInheritance(
                    "'{0}' derives from itself".format(self.name))
            self._parent = parent
        return self._parent


    # Declarations that use this type
    declarations =     db.relationship('ToscaDeclaration',
                                       foreign_keys='ToscaDeclaration._type_id',
                                       back_populates='_type_entity',
                                       cascade='all')


    ################################################################################
    # Constructor
    ################################################################################

    def __init__(self,
                 derived_from: Optional[str] = None,
                 version: Optional[str] = None,
                 properties: Optional[dict[str, Any]] = None,
                 attributes: Optional[dict[str, Any]] = None,
                 **kwargs: Any
    ) -> None:
        """Instantiate a new ToscaType instance"""

        # First, call superclass constructor
        super(ToscaType, self).__init__(**kwargs)

        # ToscaType-specific initializations. Preserve an explicit empty
        # 'derived_from' so the validator can flag it; only treat a truly
        # absent (None) value as "no parent".
        if derived_from is not None: self.derived_from = derived_from
        if version: self._version = version
        if properties: self.properties = properties
        if attributes: self.attributes = attributes


    ################################################################################
    # Add short name for simple profile types
    ################################################################################

    def add_short_name(self) -> None:
        """Add short name to type entity if necessary. This is a kludge"""

        # We only need to do this for TOSCA v1.x
        try:
            if not self.profile.tosca_version or \
               not self.profile.tosca_version.startswith("tosca_simple_yaml"):
                return
        except AttributeError:
            # No tosca version. Must be built-in profile
            return

        # And only if the type name starts with 'tosca'
        parts = self.name.split(".")
        if not len(parts) > 1 or not parts[0] == 'tosca':
            return

        # Handle thee exceptions first
        if self.name == "tosca.nodes.Storage.BlockStorage":
            self._short_name = "BlockStorage"
            return
        if self.name == "tosca.nodes.Storage.ObjectStorage":
            self._short_name = "ObjectStorage"
            return
        if self.name == "tosca.capabilities.network.Bindable":
            self._short_name = "network.Bindable"
            return
        
        # Not one of the exceptions. Use the heuristic where the short
        # names consists of only the parts that start wiht upper case.
        idx = len(parts) - 1
        while idx > -1:
            if parts[idx].islower():
                break
            idx -= 1
        short_name = ".".join(parts[idx+1:])
        if short_name:
            self._short_name = short_name
        

    ################################################################################
    # Sub-entity retrieval functions. Sub-entities are retrieved from
    # this type as well as from any parent types(s)
    ################################################################################

    def get_attribute_declarations(self) -> dict[str, Any]:
        return self.get_entity_declarations('attributes')

    def get_attribute_to_augment(self, attribute_name: str) -> Any:
        return self.get_entity_declaration_to_augment('attributes',
                                                      attribute_name)

    def get_attribute_declaration(self, attribute_name: str) -> Any:
        return self.get_attribute_or_property_declaration('attributes', attribute_name)

    def get_property_declarations(self) -> dict[str, Any]:
        return self.get_entity_declarations('properties')

    def get_property_to_augment(self, property_name: str) -> Any:
        return self.get_entity_declaration_to_augment('properties', property_name)

    def get_property_declaration(self, property_name: str) -> Any:
        return self.get_attribute_or_property_declaration('properties', property_name)

    def upgrade_tosca_path(self, path: str) -> str:
        """Upgrade the provided TOSCA Path to Version 2.0 syntax. In the
        general case, the unmodified path is returned. Derived classes
        can override this method to support type-specific TOSCA Path
        expressions.
        """
        return path

    def get_attribute_or_property_declaration(self, attr_or_prop: str, value_name: str | ToscaPath) -> Any:
        """Return the declaration for the property or attribute specified in
        'value_name' (where the 'attr_or_prop' flag specifies whether
        to look up a property declaration or an attribute
        declaration).

        Note that when the 'attr_or_prop' flag is set to 'attributes',
        we search not only the explicit attribute declarations, but
        also the automatically-reflected property declarations. This
        results in an assymetry as compared to the
        'get_attribute_declarations()' method, which only returns
        explicit attribute declarations.

        In the general case, we will just look up the value
        declaration locally. Derived classes can override this method
        to support type-specific TOSCA Path expressions.

        Args:
          value_name (string or ToscaPath): the property or attribute
            for which to return the declaration.
          attr_or_prop (either 'properties' or 'attributes'): flag
            that specifies whether to look for a property declaration
            or an attribute declaration.

        Returns:
          ToscaPropertyDeclaration 

        Raises:
          KeyError: when property or attribute declaration not found

        """
        try:
            # Is value_name a ToscaPath expression? If so, parse into
            # the real value name and a sub_value_name
            path = ToscaPath(value_name)
            value_name = path.entity
            sub_value_name = path.sub_entity
        except TypeError:
            # Not a Tosca Path expression.
            sub_value_name = None

        # ID attribute is built in
        if value_name == 'ID':
            string_type = builtin_types.get('string')
            # TODO: fix. This could result in many string declarations
            # in the database.
            return string_type.create_declaration()

        # Do we have the named declaration ourselves?
        declaration = None
        try:
            entities = getattr(self, attr_or_prop)
            declaration = entities[value_name]
        except (AttributeError, KeyError):
            # Value declaration not found locally. If 'attr_or_prop'
            # is 'attributes', we also check automatically-reflected
            # property declarations.
            if attr_or_prop == 'attributes':
                try:
                    entities = getattr(self, 'properties')
                    declaration = entities[value_name]
                except (AttributeError, KeyError):
                    # Property declaration not found either
                    pass
            # If we still haven't found a declaration, check our
            # parent type.
            if not declaration:
                try:
                    parent = self.parent
                    declaration = parent.get_attribute_or_property_declaration(
                        attr_or_prop, value_name)
                except (AttributeError, te.TypeNotFound, KeyError):
                    # No declaration found
                    error = "'{0}': '{1}' not found in {2}".format(
                        self.name, value_name, attr_or_prop)
                    raise KeyError(error)

        # If we get here, we have a valid declaration
        if sub_value_name != None:
            # Sub-entities are always properties
            return declaration.get_property_declaration(sub_value_name)
        else:
            return declaration


    def get_entity_declarations(self, entity_declaration_map_name: str) -> dict[str, Any]:
        """Get declarations kept in the 'entity_declaration_map_name'
        attribute of this type entity. This operation merges with
        declarations retrieved from the parent type(s)

        Args:
          entity_declaration_map_name(str): name of the attribute in
            the type entity that has the map of entity declarations

        Returns
          ToscaDeclaration map: map of entity declarations

        Raises:
          None
        """

        # First, get entity declarations from parent type
        try:
            parent = self.parent
            entity_declarations = parent.get_entity_declarations(entity_declaration_map_name)
        except AttributeError:
            # No parent type found. Create empty map
            entity_declarations = dict()
        except Exception as e:
            logger.error("'%s': error getting '%s' from parent: %s",
                         self.name, entity_declaration_map_name, str(e))
            entity_declarations = dict()

        # Update entity_declarations with declarations kept in this
        # type entity
        try:
            entities = getattr(self, entity_declaration_map_name)
            entity_declarations.update(entities)
        except AttributeError:
            # This type does not have an attribute of the name
            # specified in 'entity_declaration_map_name'
            pass

        return entity_declarations


    def get_entity_declarations_of_type(self, entity_declaration_map_name: str, type_entity: ToscaType) -> dict[str, Any]:
        """Get entity declarations of the type specified by 'type_entity' from
        the map stored in the 'entity_declaration_map_name' attribute
        of this type. This operation merges with declarations kept in
        the parent type(s).

        Args:
          entity_declaration_map_name(str): name of the attribute in
            this declaration entity that has the map of entity
            declarations
          type_entity(ToscaType): type entity for which to return the
            declarations
        """

        logger.debug("'%s': get %s declarations of type '%s'",
                     self.name, entity_declaration_map_name, type_entity.name)
        
        # First, get entity declarations of parent type
        try:
            parent = self.parent
            entity_declarations = parent.get_entity_declarations_of_type(entity_declaration_map_name,
                                                                         type_entity)
        except AttributeError:
            # No parent type found. Create empty map
            entity_declarations = dict()
        except Exception as e:
            logger.error("'%s': error getting '%s' of type '%s' from parent: %s",
                         self.name, entity_declaration_map_name,
                         type_entity.name, str(e))
            entity_declarations = dict()

        # Update entity_declarations with declarations of the
        # specified type kept in this type entity
        try:
            entities = getattr(self, entity_declaration_map_name)
            for entity_name, entity_declaration in entities.items():
                if entity_declaration.has_type(type_entity):
                    entity_declarations[entity_declaration.name] = entity_declaration
        except AttributeError:
            # This type does not have an attribute of the name
            # specified in 'entity_declaration_map_name'
            pass

        return entity_declarations


    def get_entity_declaration(self, entity_declaration_map_name: str, entity_name: str) -> Any:
        """Get entity declaration by name from the declaration map
        kept in the 'entity_declaration_map_name' attribute of this
        type entity. This operation tries to get the declaration from
        the parent type(s) if it's not found in this type entity

        Args:
          entity_declaration_map_name(str): name of the attribute in
            the type entity that has the map of entity declarations
          entity_name(str): name of the entity for which to return the
            declaration

        Returns: 
          ToscaDeclaration for the requested entity declaration

        Raises:
          KeyError: when no entity declared with this name
        """

        # Do we have this entity?
        try:
            entities = getattr(self, entity_declaration_map_name)
            return entities[entity_name]
        except (AttributeError, KeyError):
            # This type does not have an attribute of the name
            # specified in 'entity_declaration_map_name or doesn't
            # have a declaration of the specified name. Check parent
            # class.
            try:
                parent = self.parent
                return parent.get_entity_declaration(entity_declaration_map_name,
                                                     entity_name)
            except (AttributeError, te.CircularInheritance, te.TypeNotFound, KeyError):
                # This type entity doesn't have a parent class or the
                # type of the parent class is not found or the parent
                # class doesn't have the named entity declaration
                # either.
                raise KeyError("Type <{0}>: <{1}> not found in <{2}>".format(self.name,
                                                                             entity_name,
                                                                             entity_declaration_map_name))
        except TypeError:
            # entity_name is not a string
            raise KeyError("Type <{0}>: map index ({1}) is not a string".format(self.name,
                                                                                str(entity_name)))


    def get_entity_declaration_to_augment(self, entity_declaration_map_name: str, entity_name: str) -> Any:
        """Get declaration entity to augment.

        Returns the entity declaration from a base class that is to be
        augmented in this type entity

        Args:
          entity_declaration_map_name(str): name of the attribute in
            the type entity that has the map of entity declarations
          entity_name(str): name of the entity for which to return the
            declaration to be augmented

        Returns:
          ToscaDeclaration for the requested entity declaration

        Raises:
          KeyError: when no entity declared with this name exists in
            any of the base classes
        """

        # Get the parent type from which to retrieve the entity
        # declaration that is to be augmented
        try:
            parent_type_entity = self.parent
        except (AttributeError, te.TypeNotFound):
            raise KeyError("Type <{0}>: <{1}> not found in <{2}>".format(self.name, 
                                                                         entity_name,
                                                                         entity_declaration_map_name))

        # Get the entity declaration that is to be augmented
        return parent_type_entity.get_entity_declaration(entity_declaration_map_name,
                                                         entity_name)


    ################################################################################
    # Other stuff that needs to be organized. 
    ################################################################################

    def is_builtin_type(self) -> bool:
        """Check if this type entity is a built-in TOSCA type. By default,
        return False.  This method is only overridden by data type
        entities
        """
        return False


    def has_type(self, type_entity: ToscaType) -> bool:
        """Check if this type has the type specified by type_entity. Make sure
        to check parent types as well. 

        Args:
          type_entity(str): the type to check

        Raises:
          None
        """

        # Compare IDs if they are set
        if self.id and type_entity.id:
            if self.id == type_entity.id:
                return True
        else:
            # IDs not set yet. Check if profile name and type name
            # match.
            if self.name == type_entity.name and \
               self.profile.name == type_entity.profile.name and \
               self.type_class == type_entity.type_class:
                return True

            # Names dont' match. Does short name match?
            try:
                if self.short_name == type_entity.name and \
                   self.profile.name == type_entity.profile.name and \
                   self.type_class == type_entity.type_class:
                    return True
            except AttributeError:
                # no short name
                pass
        
        # Not an exact match. Try parent types
        try:
            return self.parent.has_type(type_entity)
        except (AttributeError, te.CircularInheritance, te.TypeNotFound):
            # No more parent types to check or parent type not found
            return False


    def get_prereq_type_names(self) -> list[str]:
        """Return list of prerequisite entity names of the same type
        on which this entity depends. Type entities return the name of
        the type they're derived from

        Returns
          ToscaType[]: ordered list of type entities on which this
            type depends
        """

        prereq_type_names: list[str] = []
        try:
            prereq_type_names.append(self.derived_from)
        except AttributeError:
            # No derived_from field.
            pass
        return prereq_type_names


################################################################################
# Global Type Lookup Functions
################################################################################

def get_type(type_name: str, type_class: str, profile_id: int) -> ToscaType:
    """Return type entity by name and class. Note that name lookups are
    case insensitive.

    Args:
      type_name(str): name of the type entity
      type_class(str): class of the type entity

    Raises:
      sqlalchemy.orm.exc.NoResultFound: when no type found with the
        specified name for the specified class
      sqlalchemy.orm.exc.MultipleResultsFound: when multiple type
        found with the specified name for the specified class (types
        are supposed to be unique)

    """
    type_entity = ToscaType.query.filter(
        and_(
            ToscaType.type_class == type_class,
            ToscaType._profile_id == profile_id,
            or_(
                ToscaType.name == type_name,
                ToscaType._short_name == type_name
            ),
        )
    ).one()
    return type_entity


def get_node_type(type_name: str, profile_id: int) -> ToscaType:
    return get_type(type_name, 'node', profile_id)

def get_relationship_type(type_name: str, profile_id: int) -> ToscaType:
    return get_type(type_name, 'relationship', profile_id)

def get_artifact_type(type_name: str, profile_id: int) -> ToscaType:
    return get_type(type_name, 'artifact', profile_id)

def get_group_type(type_name: str, profile_id: int) -> ToscaType:
    return get_type(type_name, 'group', profile_id)

def get_data_type(type_name: str, profile_id: int) -> ToscaType:
    return get_type(type_name, 'data', profile_id)

def get_capability_type(type_name: str, profile_id: int) -> ToscaType:
    return get_type(type_name, 'capability', profile_id)

def get_interface_type(type_name: str, profile_id: int) -> ToscaType:
    return get_type(type_name, 'interface', profile_id)


def get_types(type_class: str, profile_id: int) -> list[ToscaType]:
    """Return all type entity for a type class

    Args:
      type_class(str): class of the type entity

    """
    type_entities = ToscaType.query.filter(
        and_(
            ToscaType.type_class == type_class,
            ToscaType._profile_id == profile_id,
        )
    ).all()
    return type_entities


def get_node_types(profile_id: int) -> list[ToscaType]:
    return get_types('node', profile_id)

def get_relationship_types(profile_id: int) -> list[ToscaType]:
    return get_types('relationship', profile_id)

def get_artifact_types(profile_id: int) -> list[ToscaType]:
    return get_types('artifact', profile_id)

def get_group_types(profile_id: int) -> list[ToscaType]:
    return get_types('group', profile_id)

def get_data_types(profile_id: int) -> list[ToscaType]:
    return get_types('data', profile_id)

def get_capability_types(profile_id: int) -> list[ToscaType]:
    return get_types('capability', profile_id)

def get_interface_types(profile_id: int) -> list[ToscaType]:
    return get_types('interface', profile_id)


#####################
# TYPE ADDITION FUNCTIONS
#####################

def add_type(type_entity: ToscaType) -> None:
    """Add type entity. Make sure we don't already have types with this
    type's name or short name

    Args:
      type_entity(ToscaType): type entity to be added

    Raises:
      TypeAlreadyExists: if this type is already in the database

      sqlalchemy.orm.exc.MultipleResultsFound: when multiple types
        with this name are found in the database. This is a
        catastrophic error
    """
    # Add short name if necessary
    type_entity.add_short_name()
    
    # Check if type already exist with the same name
    try:
        name_filter = or_(
            ToscaType.name == type_entity.name,
            ToscaType._short_name == type_entity.name,
            ToscaType.name == type_entity.short_name,
            ToscaType._short_name == type_entity.short_name
        )
    except AttributeError:
        # type entity does not have short name
        name_filter = or_(
            ToscaType.name == type_entity.name,
            ToscaType._short_name == type_entity.name
        )


    type_filter =  and_(
        ToscaType.type_class == type_entity.type_class,
        ToscaType._profile_id == type_entity._profile_id,
        name_filter
    )

    try:
        existing_type = ToscaType.query.filter(type_filter).one()
        # Type already exists. Raise an error
        logger.debug("%s(%s) already in database", 
                     type_entity.type_class, 
                     type_entity.name)
        raise te.TypeAlreadyExists("'{0}' is already in repository".format(
            type_entity.name))

    except sqlalchemy.orm.exc.NoResultFound: 
        # Good. Type does not already exist.
        pass
        
    # Not a duplicate. Add
    db.session.add(type_entity)

    
#####################
# HELPERFUNCTIONS
#####################

def lowest_common_ancestor(a: Optional[ToscaType], b: Optional[ToscaType]) -> Optional[ToscaType]:
    """Find the lowest common parent of two types

    Args:
      a, b(ToscaType): types for which to return lowest common
        ancestor
    Returns:
      (ToscaType): lowest common ancestor
      None: if there is no common ancestor
    Raises:
      None
    """
    # Handle case where types are None
    if not a: return b
    if not b: return a
    
    # Are the two types in the same branch?
    if a.has_type(b): return b
    if b.has_type(a): return a
    # Different branches. Go up one level
    try:
        a = a.parent
        b = b.parent
        return lowest_common_ancestor(a, b)
    except AttributeError:
        # No more parents
        return None
