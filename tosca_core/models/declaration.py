"""
Module definining Tosca Declaration Entities
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
from sqlalchemy.orm.collections import attribute_mapped_collection

# Support for TOSCA keywords that are shared between all entities
import tosca_core.models.entity
import tosca_core.models.context

# Path
from tosca_core.models.path import ToscaPath

# Exception support
import tosca_core.models.exceptions as te


# The expression-context contract goes LAST, so it supplies only the members
# this class and its subclasses do not define themselves.
class ToscaDeclaration(tosca_core.models.entity.ToscaEntityMixin, db.Model,
                       tosca_core.models.context.ToscaContextMixin):
    """A ToscaDeclaration declares the presence of a named entity of a
    given type. The ToscaDeclaration class is the base class for all
    TOSCA entity declarations, specifically for:

    - ToscaAttributeDeclaration
    - ToscaPropertyDeclaration (derived from
        ToscaAttributeDeclaration)
    - ToscaCapabilityDeclaration
    - ToscaInterfaceDeclaration
    - ToscaManagedDeclaration
    - ToscaNodeDeclaration (derived from ToscaManagedDeclaration)
    - ToscaRelationshipDeclaration (derived from
        ToscaManagedDeclaration)
    - ToscaGroupDeclaration 
    - ToscaArtifactDeclaration
    """

    ################################################################################
    # Polymorphic mapping 
    ################################################################################

    type_class = db.Column(db.String, index=True)
    __mapper_args__ = {
        'polymorphic_identity': 'type',
        'polymorphic_on': type_class
    }

    ################################################################################
    # Keys
    ################################################################################
    
    # Primary key
    id =                         db.Column(db.Integer, primary_key=True)

    # Foreign keys
    # All declarations must have a type, but that type may not be
    # assigned until after validation.
    _type_id =                   db.Column(db.Integer, 
                                           db.ForeignKey('tosca_type.id'),
                                           nullable=True)
    _containing_type_id =        db.Column(db.Integer, 
                                           db.ForeignKey('tosca_type.id'),
                                           nullable=True)
    _containing_declaration_id = db.Column(db.Integer, 
                                           db.ForeignKey('tosca_declaration.id'),
                                           nullable=True)

    ################################################################################
    # Fields.  Optional fields start with '_' and have corresponding
    # getters and setters to ensure that retrieving fields
    # consistently raises an AttributeError when not set.  Note that
    # 'nullable' defaults to True, but we explicitly set the
    # 'nullable' flag for clarity.
    ################################################################################

    # Some declarations are kept in an ordered list. The 'position'
    # field tracks this declaration's position in the list.
    position =                   db.Column(db.Integer)

    ################################################################################
    # Relationships
    ################################################################################

    properties =                 db.relationship('ToscaPropertyDeclaration',
                                                 collection_class=attribute_mapped_collection('name'),
                                                 primaryjoin="and_(ToscaDeclaration.id=="
                                                 "remote(ToscaPropertyDeclaration._containing_declaration_id),"
                                                 "remote(ToscaPropertyDeclaration.role)=='PROPERTY')",
                                                 cascade='all',
                                                 back_populates='_containing_declaration',
                                                 overlaps='attributes')
    attributes =                 db.relationship('ToscaPropertyDeclaration',
                                                 collection_class=attribute_mapped_collection('name'),
                                                 primaryjoin="and_(ToscaDeclaration.id=="
                                                 "remote(ToscaPropertyDeclaration._containing_declaration_id),"
                                                 "remote(ToscaPropertyDeclaration.role)=='ATTRIBUTE')",
                                                 cascade='all',
                                                 back_populates='_containing_declaration',
                                                 overlaps='properties')
    
    ################################################################################
    # Model Navigation
    ################################################################################

    # Declarations could be used in a type definition
    _containing_type =           db.relationship('ToscaType',
                                                 remote_side='ToscaType.id',
                                                 foreign_keys='ToscaDeclaration._containing_type_id')

    # Declarations could also be used as refinements in another
    # declaration
    _containing_declaration =    db.relationship('ToscaDeclaration',
                                                 viewonly=True,
                                                 remote_side='ToscaDeclaration.id',
                                                 foreign_keys='ToscaDeclaration._containing_declaration_id',
                                                 back_populates='_contained_declarations')

    # This relationship's collection should not be modified directly. Its only purpose is to
    # provide a cascade path for deleting child objects.
    _contained_declarations =    db.relationship('ToscaDeclaration',
                                                 foreign_keys='ToscaDeclaration._containing_declaration_id',
                                                 back_populates='_containing_declaration',
                                                 overlaps='attributes, properties',
                                                 cascade='all')

    # Every declaration must have a type
    _type_entity =               db.relationship('ToscaType',
                                                 back_populates='declarations',
                                                 foreign_keys='ToscaDeclaration._type_id')
    @property
    def type_entity(self) -> Any:
        """return the type entity for this declaration

        This method returns the type stored in the '_type_entity'
        relationship, looking it up from the name in '_type' the first
        time. A refinement that states no type of its own carries the
        type of the declaration it refines, which the pass that runs
        before validation merged into it.

        Raises:
          AttributeError: when the declaration doesn't specify a type
          te.TypeNotFound: when the type specified in the declaration
            cannot be found
        """

        if self._type_entity == None:
            try:
                profile = self.profile
                self._type_entity = profile.get_type(self._type,
                                                     self.type_class)
            except AttributeError:
                raise AttributeError("{0} declaration '{1}': no type".format(
                    self.type_class, self.name))

        return self._type_entity

    @type_entity.setter
    def type_entity(self, value: Any) -> None:
        if value:
            db.session.add(self)
            self._type_entity = value


    @property
    def type(self) -> str:
        """Return the type name for this declaration.

        Raises:
          AttributeError: when there is no type defined
        """
        try:
            return self.type_entity.name
        except te.TypeNotFound:
            # The declaration has a _type defined but not found
            return self._type

    @type.setter
    def type(self, value: Optional[str]) -> None:
        if value: self._type = value


    def has_type(self, type_entity: Any) -> bool:
        """Check if this declaration's type has the type specified by
        type_entity.

        Args:
          type_entity(ToscaType): the type to check

        Raises:
          None
        """

        try:
            return self.type_entity.has_type(type_entity)
        except (AttributeError, te.TypeNotFound):
            # declaration entity doesn't have a type or type not found
            logger.error("Declaration '%s': no type declared", self.name)
            return False

    @property
    def profile(self) -> Any:
        """Get profile. Top-level declarations can only obtain their
        profile from the containing type or from the containing
        declaration. Derived declaration classes will override this
        method
        """
        if self._containing_type:
            return self._containing_type.profile
        elif self._containing_declaration:
            return self._containing_declaration.profile 
        else:
            # The only declarations that don't have a containing type
            # nor a containing declaration are synthetically-created
            # declarations (using the create_declaration
            # function). Retrieve the profile from that type.
            try:
                return self.type_entity.profile
            except Exception:
                error = "No profile found for declaration '{0}'".format(self.name)
                raise te.ModelCorruptionError(error)

    @property
    def tosca_version(self) -> str:
        """Get tosca version from the profile.
        """
        return self.profile.tosca_version

    # Fields 'merge_augmented_declaration' copies from the declaration
    # this one refines. 'get_unmerged_fields' checks them.
    merged_fields = ('name', '_description')

    def get_unmerged_fields(self, augmented_entity: ToscaDeclaration) -> list[str]:
        """Return the fields a merge with 'augmented_entity' would still
        copy into this declaration.

        A completed refinement carries everything the declaration it
        refines states, so merging again changes nothing and this list is
        empty. A non-empty list means some pass did not complete this
        declaration, and reading it answers less than the model says.

        Validations are not checked: 'merge_augmented_validations'
        combines rather than fills, so it always has something to do.

        Args:
          augmented_entity(ToscaDeclaration): the declaration this one
            refines

        Returns:
          (possibly empty) list of field names
        """
        unmerged = []
        for field in self.merged_fields:
            if getattr(self, field, None) is not None:
                continue
            if getattr(augmented_entity, field, None) is not None:
                unmerged.append(field)
        # The type is merged through 'merge_augmented_type', which reads
        # '_type' and '_type_entity' rather than a single field.
        if self._type_entity is None and getattr(self, '_type', None) is None:
            if (augmented_entity._type_entity is not None or
                getattr(augmented_entity, '_type', None) is not None):
                unmerged.append('type')
        return unmerged


    def augments(self) -> ToscaDeclaration:
        """Return the declaration for which this declaration is an
        augmentation. This method must be overwritten by the
        subclasses of ToscaDeclaration.

        Returns:
          ToscaDeclaration: declaration for which we are an augmentation

        Raises:
          KeyError: if we are not an augmentation
        """
        error = "'{0}' augmentation not supported".format(self.type_class)
        logger.error("%s", error)
        raise KeyError(error)
        

    # Templates that are based on this declaration
    templates =     db.relationship('ToscaTemplate',
                                    foreign_keys='ToscaTemplate._declaration_id',
                                    back_populates='_declaration')
        
    ################################################################################
    # Constructor
    ################################################################################

    def __init__(self,
                 type: Optional[str] = None,
                 attributes: Optional[dict[str, Any]] = None,
                 properties: Optional[dict[str, Any]] = None,
                 **kwargs: Any
    ) -> None:
        """Instantiate a new ToscaDeclaration declaration"""

        # First, call superclass constructor
        super(ToscaDeclaration, self).__init__(**kwargs)
        
        # ToscaDeclaration-specific initialization
        self.type = type
        if properties: self.properties = properties
        if attributes: self.attributes = attributes


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
        if self._containing_type:
            return self._containing_type.SELF()
        elif self._containing_declaration:
            return self._containing_declaration.SELF()
        else:
            raise AttributeError("No containing node/relationsihp type or definition found for <{0}>".format(self.name))

    
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
        if self._containing_type:
            return self._containing_type.SOURCE()
        elif self._containing_declaration:
            return self._containing_declaration.SOURCE()
        else:
            raise AttributeError("No containing node/relationship type or definition found for <{0}>".format(self.name))

    
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
        if self._containing_type:
            return self._containing_type.TARGET()
        elif self._containing_declaration:
            return self._containing_declaration.TARGET()
        else:
            raise AttributeError("No containing node/relationshp type or definition found for <{0}>".format(self.name))

    
    ################################################################################
    # Sub-entity retrieval functions. Sub-entities are retrieved from
    # this declaration as well as from its types
    ################################################################################

    def get_attribute_declarations(self) -> dict[str, Any]:
        return self.get_entity_declarations('attributes')

    def get_attribute_declaration(self, attribute_name: str) -> Any:
        return self.get_attribute_or_property_declaration('attributes', attribute_name)

    def get_property_declarations(self) -> dict[str, Any]:
        return self.get_entity_declarations('properties')

    def get_property_to_augment(self, property_name: str) -> Any:
        return self.get_entity_declaration_to_augment('properties', property_name)

    def get_property_declaration(self, property_name: str) -> Any:
        return self.get_attribute_or_property_declaration('properties', property_name)

    def upgrade_tosca_path(self, path: Any) -> Any:
        """Upgrade the provided TOSCA Path to Version 2.0 syntax. In the
        general case, the unmodified path is returned. Derived classes
        can override this method to support type-specific TOSCA Path
        expressions.
        """
        return path

    def get_attribute_or_property_declaration(self, attr_or_prop: str, value_name: Any) -> Any:
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
            # TODO: fix. This could result in many string declarations
            # in the database.
            import tosca_core.models.profile
            builtin = tosca_core.models.profile.get_profile('1')
            string_type = builtin.get_data_type('string')
            return string_type.create_declaration(name='ID')

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
            # type. Note that this can raise a KeyError.
            if not declaration:
                try:
                    declaration = self.type_entity.get_attribute_or_property_declaration(
                        attr_or_prop, value_name)
                except (AttributeError, te.TypeNotFound):
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
        """Get "sub" declarations kept in the
        'entity_declaration_map_name' attribute of this declaration
        entity. This operation merges with declarations kept in the
        declaration's type entity

        Args:
          entity_declaration_map_name(str): name of the attribute in
            this declaration entity that has the map of entity
            declarations
        """

        # Fist, get entity declarations from this declaration's type
        # entity
        try:
            entity_declarations = self.type_entity.get_entity_declarations(entity_declaration_map_name)
        except (AttributeError, te.TypeNotFound):
            # declaration entity doesn't have a type or type not found
            entity_declarations = dict()

        # Update entity_declarations with declarations kept in this
        # declaration entity
        try:
            entities = getattr(self, entity_declaration_map_name)
            entity_declarations.update(entities)
        except AttributeError:
            pass

        return entity_declarations


    def get_entity_declarations_of_type(self, entity_declaration_map_name: str, type_entity: Any) -> dict[str, Any]:
        """Get "sub" declarations of the type specified by 'type_entity' from
        the map stored in the 'entity_declaration_map_name' attribute
        of this declaration entity. This operation merges with
        declarations kept in the declaration's type_entity

        Args:
          entity_declaration_map_name(str): name of the attribute in
            this declaration entity that has the map of entity
            declarations
          type_entity(ToscaType): type entity for which to return the
            declarations
        """

        logger.debug("'%s': get %s declarations of type '%s'",
                     self.name, entity_declaration_map_name, type_entity.name)
        
        # Fist, get entity declarations from this declaration's type
        # entity
        try:
            entity_declarations = self.type_entity.get_entity_declarations_of_type(entity_declaration_map_name,
                                                                                   type_entity)
        except (AttributeError, te.TypeNotFound):
            # declaration entity doesn't have a type or type not found
            entity_declarations = dict()

        # Update entity_declarations with declarations of the
        # specified type kept in this declaration entity
        try:
            entities = getattr(self, entity_declaration_map_name)
            for entity_name, entity_declaration in entities.items():
                if entity_declaration.has_type(type_entity):
                    entity_declarations[entity_declaration.name] = entity_declaration
        except AttributeError:
            # This declaration does not have an attribute of the name
            # specified in 'entity_declaration_map_name'
            pass

        return entity_declarations


    def set_entity_declaration(self, entity_declaration_map_name: str, entity_name: str, entity_declaration: Any) -> None:
        """set entity declaration by name in the map stored in the
        'entity_declaration_map_name' attribute of this declaration
        entity.

        Args:
          entity_declaration_map_name(str): name of the attribute in
            this delcaration entity that has the map of entity
            declarations
          entity_name(str): name of the entity for which to return the
            declaration
        """

        try:
            entities = getattr(self, entity_declaration_map_name)
            entities[entity_name] = entity_declaration
        except AttributeError:
            # No entity map defined yet. Assign initial map
            setattr(self, entity_declaration_map_name, { entity_name : entity_declaration })


    def get_entity_declaration(self, entity_declaration_map_name: str, entity_name: str) -> ToscaDeclaration:
        """Get entity declaration by name from the declaration map
        kept in the 'entity_declaration_map_name' attribute of this
        declaration entity. This operation tries to get the
        declaration from the declaration's type entity if it's not
        found in this declaration entity

        Args:
          entity_declaration_map_name(str): name of the attribute in
            this delcaration entity that has the map of entity
            declarations
          entity_name(str): name of the entity for which to return the
            declaration

        Returns: 
          ToscaDeclaration for the requested entity declaration

        Raises:
          KeyError: when no entity declared with this name
        """

        # Do we have the named declaration?
        try:
            entities = getattr(self, entity_declaration_map_name)
            return entities[entity_name]
        except (AttributeError, KeyError):
            # This declaration does not have an attribute of the name
            # specified in 'entity_declaration_map_name or doesn't
            # have a declaration of the specified name. Check type
            # entity instead.
            try:
                return self.type_entity.get_entity_declaration(entity_declaration_map_name,
                                                               entity_name)
            except (AttributeError, te.TypeNotFound):
                # declaration entity doesn't have a type or type not found
                raise KeyError("Declaration <{0}>: <{1}> not found in <{2}>".format(self.name, 
                                                                                    entity_name,
                                                                                    entity_declaration_map_name))
        except TypeError:
            # entity_name is not a string
            raise KeyError("Declaration <{0}>: map index ({1}) is not a string".format(self.name,
                                                                                       str(entity_name)))
                

    def get_entity_declaration_to_augment(self, entity_declaration_map_name: str, entity_name: str) -> ToscaDeclaration:
        """Get declaration entity to augment.

        Returns the entity declaration from the type entity that is to
        be augmented in this declaration entity

        Args:
          entity_declaration_map_name(str): name of the attribute in
            the type entity that has the map of entity declarations
          entity_name(str): name of the entity for which to return the
            declaration to be augmented

        Returns:
          ToscaDeclaration for the requested entity declaration

        Raises:
          KeyError: when no entity declared with this name exists in
            the type entity
        """

        # Get the type entity from which to retrieve the entity
        # declaration that is to be augmented
        try:
            type_entity = self.type_entity
        except Exception as e:
            raise KeyError(
                "Type <{0}>: <{1}> not found in <{2}>: {3}".format(self.name,
                                                                  entity_name,
                                                                  entity_declaration_map_name,
                                                                  e))

        # Get the entity declaration that is to be augmented
        return type_entity.get_entity_declaration(entity_declaration_map_name,
                                                  entity_name)


    ################################################################################
    # Sub-Entity Refinement
    ################################################################################

    def merge_augmented_declaration(self, augmented_entity: ToscaDeclaration) -> None:
        """Complete an augmentation by merging in data from the declaration
        which it augments
        """

        # Merge fields we don't already have
        self.merge_augmented_field('name', augmented_entity)
        self.merge_augmented_field('_description', augmented_entity)

        # Merge type if we don't already have one
        self.merge_augmented_type(augmented_entity)

        # Merge property declarations
        self.merge_augmented_properties(augmented_entity)


    def merge_augmented_type(self, augmented_entity: ToscaDeclaration) -> None:
        # Do we already have a type?
        if self._type_entity != None:
            # Nothing to do
            return

        try:
            if self._type:
                # Nothing to do
                return
        except AttributeError:
            # No type specified.
            pass

        # Augmenting augmented entity does not have a 'type'
        # attribute. Copy type_entity from augmented entity it has one
        try:
            self.type_entity = augmented_entity.type_entity
        except AttributeError:
            # Augmenting augmented entity does not have a
            # 'type' attribute.
            pass


    def merge_augmented_properties(self, augmented_entity: ToscaDeclaration) -> None:
        # First, complete each individual property augmentation
        for property_name, property_declaration in self.properties.items():
            # Find the corresponding property declaration to
            # augment and extend.
            try:
                augmented_property = augmented_entity.get_property_declaration(property_name)
                property_declaration.merge_augmented_declaration(augmented_property)
            except Exception as e:
                # Something went wrong
                logger.error("%s: unable to augment: %s", self.name, e)

        # Then, merge in all other property declarations that haven't
        # been augmented
        properties_to_merge = dict()
        own_properties = getattr(self, 'properties', None) or {}
        for property_name, property_declaration in augmented_entity.properties.items():
            # Is this a declaration that has already been augmented?
            # Only this declaration's own properties count: one its
            # type defines has not been augmented by the declaration
            # being merged in.
            if property_name in own_properties:
                # Nothing further to do
                continue
            # Don't have this one yet. Start from the property as this
            # declaration's type defines it, so the type keeps
            # precedence, and fill in from the declaration being
            # merged.
            from tosca_core.models.property_declaration import ToscaPropertyDeclaration
            merged_property = ToscaPropertyDeclaration()
            try:
                merged_property.merge_augmented_declaration(
                    self.get_property_to_augment(property_name))
            except KeyError:
                # Our type does not define this property
                pass
            merged_property.merge_augmented_declaration(property_declaration)
            properties_to_merge[property_name] = merged_property
        # Merge in
        try:
            self.properties.update(properties_to_merge)
        except (AttributeError, TypeError):
            # Don't have properties or properties set to None
            self.properties = properties_to_merge
        

    def merge_augmented_field(self, field_name: str, augmented_entity: ToscaDeclaration) -> None:
        """Complete a field in an augmentation by merging in the field from
        the declaration which it augments if necessary
        """

        # Do we already have this field?
        try:
            if getattr(self, field_name) != None:
                # Field already set. No need to merge
                return
        except AttributeError:
            pass

        # We don't yet have this field. Merge if possible
        try:
            field = getattr(augmented_entity, field_name)
            if field != None:
                setattr(self, field_name, field)
        except AttributeError:
            pass


    ################################################################################
    # Validation of Property Value Templates
    ################################################################################

    def validate_property_templates(self, context: Any, properties: dict[str, Any],
                                    check_required_fields: bool = True) -> dict[str, Any]:
        """Check if the property templates (or 'property assignments' as they
        are called in the spec) in a TOSCA template are valid for
        their declarations within the specified context. 

        Note that this method is defined on 'ToscaDeclaration' rather
        than on 'ToscaTemplate' because it is also used to validate
        sub-properties of property values with complex data types, and
        these complex property values are just Python data rather than
        instances of type ToscaTemplate.

        This is the main entry point for most property template
        validations. Properties are always validated as a map of
        name-value pairs rather than as an individual property values.

        There are some property value scenarios that focus on
        individual property values (e.g. to validate default values or
        constraint values in property declarations or node
        filters). Those validations do not use this method. In fact,
        they may validate directly against the type definition.

        Context is typically the (outermost) instance or template that
        contains the entity for which to validate the properties.

        Args:
          context(ToscaInstance or ToscaTemplate): context within
            which to validate the property values. This information is
            necessary to allow us to evaluate intrinsic functions.
          properties(dict): property assignment values to validate
          check_required_fields(bool): if false, required properties may
            be missing, here and in the values of complex properties.
        Returns:
          (Python dict) fully-validated property values
        Raises:
          ValidationError: when property values are invalid
        """
        # Get property declarations defined in this declaration.
        property_declarations = self.get_property_declarations()

        # First, validate each property value against its property
        # declaration.
        validated = dict()
        validation_errors = dict()
        try:
            for property_name, property_value in properties.items():
                logger.debug("'%s': validating property '%s'",
                             self.name, property_name)
                try:
                    # Find corresponding declaration
                    property_declaration = property_declarations[property_name]
                    
                    # Make sure this property doesn't override a fixed
                    # value defined in the property declaration
                    try:
                        value = property_declaration.value
                        validation_errors[property_name] = 'overriding value from definition is not allowed'
                    except AttributeError:
                        # No fixed value defined in the
                        # declaration. Make sure the property value is
                        # valid for the property declaration. Note
                        # that 'validate_value' never raises any
                        # exceptions, so no need to protect it here.
                        try:
                            validated[property_name] = property_declaration.validate_value(
                                context, property_value, check_presence=True,
                                check_required_fields=check_required_fields)
                        except te.ValidationError as e:
                            logger.error("'%s' property '%s': '%s' is invalid value for %s",
                                         self.name,
                                         property_name, property_value,
                                         property_declaration.type)
                            validation_errors[property_name] = e.errors
                except KeyError:
                    logger.error("'%s': undefined property '%s'",
                                 self.name, property_name)
                    validation_errors[property_name] = 'not previously defined'
                except Exception as e:
                    validation_errors[property_name] = 'validator error ({0})'.format(str(e))
        except AttributeError:
            # Not a map
            raise te.ValidationError('invalid properies', 'not a map')
                    
        # Next, check if all required properties are present -- unless the
        # caller accepts a value that lacks some (see 'validate_value').
        for property_name, property_declaration in property_declarations.items():
            if not check_required_fields:
                break
            try:
                property_value = properties[property_name]
                # None values don't count
                if property_value == None:
                    raise KeyError(property_name)
            except KeyError:
                # No property template
                logger.debug("%s: checking property '%s'", self.name, property_name)
                if property_declaration.is_required():
                    logger.debug("'%s' (%s): checking value for required property '%s'",
                                 self.name, self.type, property_name)
                    error = property_declaration.validate_value_presence(context, properties)
                    if error:
                        validation_errors[property_name] = error

        # All done
        if validation_errors:
            raise te.ValidationError('invalid properties', validation_errors)
        return validated
