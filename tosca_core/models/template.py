"""
Module defining base class for Tosca templates
"""
from __future__ import annotations

__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2014-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Type hints
from typing import Any, Optional

# Logging support
import logging
logger: logging.Logger = logging.getLogger(__name__)

# Database support
from tosca_core import db

# Support for TOSCA keywords that are shared between all entities
import tosca_core.models.entity

# Exception support
import tosca_core.models.exceptions as te
import tosca_core.models.presence as presence

# ToscaPath support 
from tosca_core.models.path import ToscaPath, extract_path_value


class ToscaTemplate(tosca_core.models.entity.ToscaEntityMixin, db.Model):
    """The ToscaTemplate class is the base class for all TOSCA template
    entities, specifically for:

    - ToscaArtifact
    - ToscaCapabilityTemplate
    - ToscaInterfaceTemplate
    - ToscaGroup
    - ToscaManagedTemplate
    - ToscaNodeTemplate (derived from ToscaManagedTemplate)
    - ToscaRelationshipTemplate (derived from ToscaManagedTemplate)

    We don't use template objects for attribute or property templates
    ("values"). Those are treated as regular Python data and stored in
    pickle fields.
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
    id =                      db.Column(db.Integer, primary_key=True)

    # Foreign keys
    _declaration_id =         db.Column(db.Integer,
                                        db.ForeignKey('tosca_declaration.id'),
                                        nullable=True)
    _service_id =             db.Column(db.Integer, 
                                        db.ForeignKey('tosca_service_template.id'),
                                        nullable=True)
    _containing_template_id = db.Column(db.Integer,
                                        db.ForeignKey('tosca_template.id'),
                                        nullable=True)

    ################################################################################
    # Fields
    ################################################################################

    # All templates must have a name, but that name may not be
    # assigned until after validation.
    name =                    db.Column(db.String)

    # For templates that are organized in lists, we keep a 'position' attribute
    position =                db.Column(db.Integer)

    # Optional fields start with '_' and have corresponding getters
    # and setters to ensure that retrieving fields consistently raises
    # an AttributeError when not set.  Note that 'nullable' defaults
    # to True, but we explicitly set the 'nullable' flag for clarity.
    _properties =             db.Column(db.PickleType, nullable=True)
    _attributes =             db.Column(db.PickleType, nullable=True)
    # Both node templates (TOSCA 1.x and 2.0) and capability templates
    # (TOSCA 2.0) carry directives. We share a single column on the
    # base table; each subclass defines its own 'directives' property
    # and 'valid_directives' class attribute.
    _directives =             db.Column(db.PickleType, nullable=True)

    @property
    def attributes(self) -> dict[str, Any]:
        if self._attributes == None: self._attributes = dict()
        return self._attributes

    @attributes.setter
    def attributes(self, value: Optional[dict[str, Any]]) -> None:
        self._attributes = value

    @property
    def properties(self) -> dict[str, Any]:
        if self._properties == None: self._properties = dict()
        return self._properties

    @properties.setter
    def properties(self, value: Optional[dict[str, Any]]) -> None:
        self._properties = value

    def get_attribute(self, attribute_path: str | Any) -> Any:
        """Return the referenced attribute value in a template. This method
        can be called when validating constraints on property values
        in templates.

        Args:
          attribute_path (str or ToscaPath): the name of the attribute
            or a Tosca path to the attribute for which to return the

        Returns:
          Python value or None if the value doesn't exist (when the
            attribute is optional)

        Raises:
          ??
        """
        return self.get_attribute_or_property_template('attributes', attribute_path)

    def get_property(self, property_path: str | Any) -> Any:
        """Return the referenced property value in a template. This method can
        be called when validating constraints on property values in
        templates.
        Args:
          property_path (str or ToscaPath): the name of the property
            or a Tosca path to the property for which to return the
            fully evaluated value.

        Returns:
          Python value or None if the value doesn't exist (when the
            property is optional)

        Raises:
          ??
        """
        return self.get_attribute_or_property_template('properties', property_path)
        

    ################################################################################
    # Model Navigation.  Relationship templates, interface templates,
    # capability templates, and artifacts have a containing
    # template. All other templates are contained by a service
    # template.
    ################################################################################

    # Get containing template if it exists. May return None
    containing_template =     db.relationship('ToscaTemplate',
                                              remote_side=[id],
                                              foreign_keys='ToscaTemplate._containing_template_id')

    # Get containing template if it exists. May return None
    _service =               db.relationship('ToscaServiceTemplate',
                                              foreign_keys='ToscaTemplate._service_id')

    # Get containing service.
    @property
    def service(self) -> Any:
        """Node templates, some relationship templates, workflow templates,
        groups, and policies have a '_service' relationship that was
        created as a 'backref' by the service_template that contains
        these templates. For those templates, we return the
        '_service' relationship. For all other templates, we retrieve
        the service from the containing template (or from the
        containing_operation_template in the case of artifacts)

        """
        try:
            if self._service: return self._service
        except AttributeError:
            # no _service relationship
            pass
        try:
            return self.containing_template.service
        except AttributeError:
            # No containing template
            error = "Unable to retrieve 'service' for {}: no containing template".format(self.name)
            raise te.ModelCorruptionError(error)

    # Instances that use this template: 'instances' is a backref
    # declared on ToscaInstance.template, and exists only when the
    # instance models are loaded.

    # All templates must have corresponding declarations
    _declaration =            db.relationship('ToscaDeclaration',
                                              back_populates='templates',
                                              foreign_keys='ToscaTemplate._declaration_id')

    @property
    def declaration(self) -> Any:
        """return the declaration for this template

        Under normal operation, this method returns the declaration
        stored in the '_declaration' attribute but we also need to
        handle the case where the _declaration attribute has not yet
        been set. We do this by checking if a '_type' attribute exists
        and if so, we look up the 'type_entity' for the type name
        stored in '_type' and synthesize a declaration for that
        type. Note that only "self-declaring" templates (e.g. node
        templates) have _type attributes when first created.

        Raises:
          AttributeError: when the template doesn't have a
            declaration
          te.TypeNotFound: if the type specified in the template is
            not found
        """
        if not self._declaration:
            self._declaration = self.create_declaration()
        return self._declaration

    @declaration.setter
    def declaration(self, value: Any) -> None:
        if value:
            db.session.add(self)
            self._declaration = value

    def create_declaration(self) -> Any:
        """Synthesize a ToscaDeclaration object for this template

        Returns: 
          Entity that is the appropriate subclass of ToscaDeclaration
          with its name and type attributes initialized. No other
          attributes are initialized.

        Raises:
          AttributeError: if name or type aren't set
          te.TypeNotFound: if the type specified in the template is
            not found
        """
        type_entity = self.profile.get_type(self._type, self.type_class)
        # Since we have a type entity, clean up the type string to
        # avoid confusion later.
        try:
            del self._type
        except AttributeError:
            pass
        return type_entity.create_declaration(self.name)

    @property
    def profile(self) -> Any:
        """Get profile. Top-level templates can only obtain their profile
        from the containing service. Derived classes may override
        this method
        """
        return self.service.profile

    @property
    def tosca_version(self) -> str:
        """Get tosca version from the profile.
        """
        return self.profile.tosca_version

    ################################################################################
    # Implementation of reserved keywords
    ################################################################################

    def SELF(self) -> Any:
        """Return the template for the entity referred to by SELF for this
        template. SELF refers to node templates or relationship
        templates only. All other templates retrieve SELF from their
        containing type or containing declaration.

        Returns:
          ToscaManagedTemplate

        Raises:
          ModelCorruptionError: when containing_template is 'None'
        """
        try:
            return self.containing_template.SELF()
        except AttributeError:
            # No containing template
            error = "Unable to retrieve SELF for {}: no containing template".format(self.name)
            raise te.ModelCorruptionError(error)

    def SOURCE(self) -> Any:
        """Return the template for the entity referred to by SOURCE for this
        template. SOURCE applies to relationship templates only. All
        other templates retrieve SOURCE from their containing
        relationship template.

        Returns:
          ToscaNodeTemplate

        Raises:
          ModelCorruptionError: when containing_template is 'None'
        """
        try:
            return self.containing_template.SOURCE()
        except AttributeError:
            # No containing template
            error = "Unable to retrieve SOURCE for {}: no containing template".format(self.name)
            raise te.ModelCorruptionError(error)

    def TARGET(self) -> Any:
        """Return the template for the entity referred to by TARGET for this
        template. TARGET applies to relationship templates only. All
        other templates retrieve TARGET from their containing
        relationship template.

        Returns:
          ToscaNodeTemplate

        Raises:
          ModelCorruptionError: when containing_template is 'None'
        """
        try:
            return self.containing_template.TARGET()
        except AttributeError:
            # No containing template
            error = "Unable to retrieve TARGET for {}: no containing template".format(self.name)
            raise te.ModelCorruptionError(error)


    ################################################################################
    # Get sub-entity declarations
    ################################################################################

    def get_property_declaration(self, property_name: str) -> Any:
        return self.get_attribute_or_property_declaration('properties', property_name)

    def get_attribute_declaration(self, attribute_name: str) -> Any:
        return self.get_attribute_or_property_declaration('attributes', attribute_name)

    def upgrade_tosca_path(self, path: Any) -> Any:
        return self.declaration.upgrade_tosca_path(path)
    
    ################################################################################
    # Constructor
    ################################################################################

    def __init__(self,
                 properties: Optional[dict[str, Any]] = None,
                 attributes: Optional[dict[str, Any]] = None,
                 **kwargs: Any
                 ) -> None:
        """Instantiate a new ToscaTemplate instance"""

        # First, call superclass constructor
        super(ToscaTemplate, self).__init__(**kwargs)

        # ToscaTemplate-specific initialization
        self.properties = properties
        self.attributes = attributes


    ################################################################################
    # Other stuff that needs to be organized. These functions use type
    # names without a profile qualifier. This needs to get
    # addressed.
    ################################################################################

    @property
    def type(self) -> Any:
        return self._declaration.type

    @type.setter
    def type(self, value: Any) -> None:
        if value: self._type = value

    @property
    def _type_id(self) -> int:
        return self._declaration._type_id


    def has_type(self, type_entity: Any) -> bool:
        """Check if this template is of the type specified by 'type_entity'
        """
        try:
            return self.declaration.has_type(type_entity)
        except AttributeError:
            # Node template doesn't have a type
            logger.error("Unable to check if '%s' has type '%s': no type defined",
                         self.name, type_entity)
            return False
        except te.TypeNotFound:
            # Declaration entity has invalid type
            logger.debug("Unable to check if '%s' has type '%s': type '%s' not found",
                         self.name, type_entity, type_entity)
            return False


    ################################################################################
    # Template refinement support
    ################################################################################

    def complete_template_refinement(self, source_template: ToscaTemplate) -> None:
        """Complete a refining template with definitions from the source
        template that it refines.
        """

        # Merge fields we don't already have
        self.merge_augmented_field('name', source_template)
        self.merge_augmented_field('_description', source_template)
        self.merge_augmented_field('_directives', source_template)

        # Merge in declaration if necessary
        self.merge_augmented_declaration(source_template)

        # Merge in dict-valued fields where keys present in self
        # override keys from the source.
        self.merge_augmented_properties(source_template)
        self.merge_augmented_dict_field('attributes', source_template)
        self.merge_augmented_dict_field('meta_data', source_template)


    def merge_augmented_dict_field(self, field_name: str, source_template: ToscaTemplate) -> None:
        """Merge a dict-valued field from the source template into self.
        Keys present in self take precedence over keys from the source --
        i.e. self overrides what it explicitly defines, and inherits the
        rest. Mirrors merge_augmented_properties, which predates this
        helper and is kept as-is for callers that reference it directly.
        """
        try:
            source_value = getattr(source_template, field_name)
            if not source_value:
                return
        except AttributeError:
            return
        merged = dict(source_value)
        try:
            own_value = getattr(self, field_name)
            if own_value:
                merged.update(own_value)
        except AttributeError:
            pass
        except Exception as e:
            logger.error("Instance <%s>: error augmenting %s: %s",
                         self.name, field_name, e)
        setattr(self, field_name, merged)


    def merge_augmented_declaration(self, source_template: ToscaTemplate) -> None:
        """Make sure the refining template has a _declaration or a _type. If
        not, get the _declaration or the _type from the source template that it
        refines.
        """
        # Does the refining template already have a declaration?
        if self._declaration:
            # Nothing to do
            return

        # We don't have a declaration yet, but do we have a _type from
        # which we could create a declaration?
        try:
            if self._type:
                # Nothing to do
                return
        except AttributeError:
            # No _type specified.
            pass

        # Get type from augmented declaration.
        if source_template._declaration != None:
            db.session.add(self)
            self._declaration = source_template._declaration
            # Nothing further to do
            return

        # Augmenting augmented entity does not have a
        # 'declaration' attribute. Copy _type attribute if
        # it has one
        try:
            self._type = source_template._type
        except AttributeError:
            # Augmenting augmented entity does not have a
            # '_type' attribute.
            pass


    def merge_augmented_properties(self, source_template: ToscaTemplate) -> None:
        try:
            if not source_template.properties:
                # Augmented instance does not have properties. Nothing
                # further to do.
                return
        except AttributeError:
            # Augmenting entity does not have a 'properties'
            # attribute. Nothing further to do.
            return

        # Copy properties dict
        properties = dict(source_template.properties)

        # Add in our own properties
        try:
            if self.properties:
                properties.update(self.properties)
        except AttributeError:
            # We don't have properties list. Nothing to do
            pass
        except Exception as e:
            logger.error("Instance <%s>: error augmenting properties: %s",
                         self.name, e)
        # Update
        self.properties = properties


    def merge_augmented_field(self, field_name: str, source_template: ToscaTemplate) -> None:
        """Complete a field in an augmentation by merging in the field from
        the instance which it augments if necessary
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
            field = getattr(source_template, field_name)
            if field != None:
                setattr(self, field_name, field)
        except AttributeError:
            pass


    ################################################################################
    # Support for retrieving attribute and property values from the
    # template based on the provided context. ToscaInstance objects do
    # not store property values themselves. Instead, property values
    # are always retrieved from the template with the ToscaInstance as
    # the context.
    ################################################################################

    def get_attribute_values(self, context: Any, **kwargs: Any) -> dict[str, Any]:
        """Return a map of initial attribute values within the provided
        context based on property and attribute definitions in this
        template. Note that we don't check whether values are
        required, since presumably that check has already been
        performed during template validation.

        Args:
          context(ToscaInstance): context within which to evaluate
            attributes
          no_tosca_path(bool): if true, do not evaluate functions with
            TOSCA Path arguments.
        Returns:
          (possibly empty) dict of fully evaluated attribute values
        Raises:
          ???
        """
        logger.debug("<%s>: getting attribute values", self.name)

        attributes = dict()
        attribute_declarations = self.declaration.get_attribute_declarations()
        for attribute_name, attribute_declaration in attribute_declarations.items():
            attribute_value = attribute_declaration.get_evaluated_value(
                context, self.attributes, **kwargs)
            if attribute_value != None:
                attributes[attribute_name] = attribute_value
        # All done
        return attributes

    
    def get_property_values(self, context: Any, **kwargs: Any) -> dict[str, Any]:
        """Return a map of initial property values within the provided
        context based on property and property definitions in this
        template. Note that we don't check whether values are
        required, since presumably that check has already been
        performed during template validation.

        Args:
          context(ToscaInstance): context within which to evaluate
            properties
          no_tosca_path(bool): if true, do not evaluate functions with
            TOSCA Path arguments.
        Returns:
          (possibly empty) dict of fully evaluated property values
        Raises:
          ???
        """
        logger.debug("<%s>: getting property values", self.name)

        properties = dict()
        property_declarations = self.declaration.get_property_declarations()
        for property_name, property_declaration in property_declarations.items():
            property_value = property_declaration.get_evaluated_value(
                context, self.properties, **kwargs)
            if property_value != None:
                properties[property_name] = property_value
        # All done
        return properties

            
    ################################################################################
    # Support for retrieving attribute and property value declarations
    # from this template. 
    ################################################################################

    def get_attribute_or_property_declaration(self, attr_or_prop: str, value_name: str | Any) -> Any:
        """Return the attribute or property declaration for the attribute or
        property specified in 'value_name' (where the 'attr_or_prop'
        flag specifies whether to look up an attribute template or a
        property template).

        In the general case, we will just look up the attribute or
        property declaration from this template's declaration. Derived
        classes can override this method to support type-specific
        TOSCA Path expressions.

        Args:
          attr_or_prop (either 'properties' or 'attributes'): flag
            that specifies whether to look for a property value or an
            attribute value.
          value_name (string or ToscaPath): the property or attribute
            for which to return the value declaration.

        Returns:
          Python value

        Raises:
          KeyError: when named property or attribute not found
        """
        return self.declaration.get_attribute_or_property_declaration(attr_or_prop, value_name)


    ################################################################################
    # Support for checking if property value templates are available
    # in this template and for retrieving attribute and property value
    # templates from this template.
    ################################################################################

    def is_property_template_present(self, property_path: str | Any, property_declaration: Any) -> bool:
        """Check if a property value exists for the property identified using path.
        Args:
          property_path (string or ToscaPath): the property for which
            to check if it exists
          property_declaration(ToscaPropertyDeclaration): declaration
            for the expected property value
        Returns:
          boolean
        Raises:
          ??
        """
        # If 'property_path' is a TOSCA path, parse the
        # 'property_path' into the name of the referenced property and
        # the sub-property path. Note that property_path can be None
        try:
            path = ToscaPath(property_path)
            property_path = path.entity
            sub_property_path = path.sub_entity
        except TypeError:
            # Not a TOSCA path expression 
            sub_property_path = None

        # Get property template locally
        try:
            property = self.properties[property_path]
        except KeyError:
            logger.debug("%s: optional %s not found", self.name, property_path)
            property = None
        except Exception as e:
            logger.error("Unable to get property '%s' from '%s': %s",
                         property_path, self.name, str(e))
            return presence.Undecided(f"cannot read '{property_path}' of '{self.name}': {e}")

        # Even when the property value is None, the property
        # definition might define a fixed value or a default that
        # returns a value within this context. And even if a property
        # value is defined, that value can itself be a function. We
        # need to check if that function is guaranteed to return a
        # value in the context of the template we just found.
        properties = dict()
        properties[property_declaration.name] = property
        error = property_declaration.validate_value_presence(self, properties)
        if error:
            # An answer, not a failure: whether an absent value matters is
            # the caller's to decide.
            logger.debug("%s: '%s' is not guaranteed: %s", self.name, str(property_path), error)
            # Pass on why, when the check could not decide or found a loop.
            return presence.answer_of(error)
        else:
            return True
        
    def get_attribute_or_property_template(self, attr_or_prop: str, attr_or_prop_path: str | Any) -> Any:
        """Return the attribute or property value defined in a template for
        the attribute or property specified in 'attr_or_prop_path' (where the
        'attr_or_prop' flag specifies whether to look up an attribute
        template or a property template).

        In the general case, we will just look up the attribute or
        property value from this template declaration. Derived classes
        can override this method to support type-specific TOSCA Path
        expressions.

        Args:
          attr_or_prop (either 'properties' or 'attributes'): flag
            that specifies whether to look for a property value or an
            attribute value.
          attr_or_prop_path (string or ToscaPath): the property or attribute
            for which to return the value declaration.

        Returns:
          Python value

        Raises:
          KeyError: when named property or attribute not found
        """
        # If 'attr_or_prop_path' is a TOSCA path, parse the
        # 'attr_or_prop_path' into the name of the referenced property and
        # the sub-property path
        try:
            path = ToscaPath(attr_or_prop_path)
            attr_or_prop_path = path.entity
            sub_property_path = path.sub_entity
        except TypeError:
            # Not a TOSCA path expression 
            sub_property_path = None

        # Next, get the templated value. We return 'None' if the
        # property or attribute is not found (since presumably it is
        # optional)
        if attr_or_prop == 'attributes':
            # ID attribute is handled as a special case
            if attr_or_prop_path == 'ID': return 'ID'
            try:
                return self.attributes[attr_or_prop_path]
            except KeyError:
                # No such attribute. Could be automatically-reflected property
                pass
        # Check properties
        try:
            return self.properties[attr_or_prop_path]
        except KeyError:
            logger.debug("%s: optional %s not found", self.name, attr_or_prop_path)
            return None


