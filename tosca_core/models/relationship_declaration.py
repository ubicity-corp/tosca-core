"""
Module definining Tosca Relationship Declaration entity
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

# Types on which this declaration depends
import tosca_core.models.managed_declaration
from tosca_core.builtin.range import ToscaRange
from tosca_core.models.path import ToscaPath

# Types used in relationships
import tosca_core.models.capability_type


class ToscaRelationshipDeclaration(tosca_core.models.managed_declaration.ToscaManagedDeclaration):
    """The ToscaRelationshipDeclaration entity represents relationship
    declarations specified by the 'requirements' directive in TOSCA
    node types
    """

    ################################################################################
    # Polymorphic mapping
    ################################################################################

    __mapper_args__ = {
        'polymorphic_identity':'relationship',
    }

    ################################################################################
    # Fields
    ################################################################################
    
    allocation =                 db.Column(db.PickleType)

    _count_range =               db.Column(db.PickleType, nullable=True)
    @property
    def count_range(self) -> list[Any]:
        if not self._count_range:
            if self.profile.tosca_version.startswith("tosca_simple_yaml"):
                # Default for v1.x
                return [1, 1]
            else:
                return [0, 'UNBOUNDED']
        return self._count_range

    @count_range.setter
    def count_range(self, value: Optional[list[Any]]) -> None:
        if value: self._count_range = value

    # Node filters use symbolic names for functions
    _node_filter =               db.Column(db.PickleType, nullable=True)
    @property
    def node_filter(self) -> Any:
        if not self._node_filter:
            raise AttributeError(f"{self.name} does not have 'node_filter' attribute")
        return self._node_filter
    @node_filter.setter
    def node_filter(self, value: Any) -> None:
        if value: self._node_filter = value

    # Resolved filters use internal function syntax based on signature ID.
    _resolved_filter =               db.Column(db.PickleType, nullable=True)
    @property
    def resolved_filter(self) -> Any:
        if not self._resolved_filter:
            raise AttributeError(f"{self.name} does not have 'resolved_filter' attribute")
        return self._resolved_filter
    @resolved_filter.setter
    def resolved_filter(self, value: Any) -> None:
        if value: self._resolved_filter = value

    ################################################################################
    # Keys
    ################################################################################
    
    # Foreign keys
    _target_capability_type_id = db.Column(db.Integer, 
                                           db.ForeignKey('tosca_type.id'),
                                           nullable=True)
    _target_node_type_id =       db.Column(db.Integer, 
                                           db.ForeignKey('tosca_type.id'),
                                           nullable=True)

    ################################################################################
    # Model Navigation
    ################################################################################

    _target_capability_type =    db.relationship('ToscaCapabilityType',
                                                 remote_side='ToscaCapabilityType.id', 
                                                 foreign_keys='ToscaRelationshipDeclaration._target_capability_type_id')

    _target_node_type =          db.relationship('ToscaNodeType',
                                                 remote_side='ToscaNodeType.id', 
                                                 foreign_keys='ToscaRelationshipDeclaration._target_node_type_id')
    
    @property
    def target_capability_type(self) -> Any:
        """return the target capability type entity for this relationship
        declaration

        Under normal operation, this method returns the type stored in
        the '_target_capability_type' attribute but we also need to
        handle the case where the _target_capability_type attribute
        has not yet been set. We do this by checking if a
        '_capability' attribute exists and if so, we look up the
        '_target_capability_type' for the type name stored in
        '_capability'

        Raises:
          AttributeError: when the declaration doesn't specify a
            capability type
          te.TypeNotFound: when the capability type specified in the
            relationship declaration cannot be found
        """
        if self._target_capability_type == None:
            profile = self.profile
            self._target_capability_type = profile.get_capability_type(self._capability)
        return self._target_capability_type

    def get_target_capability_declaration(self) -> Any:
        """Return a capability declaration for the target capability type in
        this relationship
        """
        return self.target_capability_type.create_declaration(
            name="{0}_capability".format(self.name))


    @property
    def target_node_type(self) -> Any:
        """return the target node type entity for this relationship
        declaration

        Under normal operation, this method returns the type stored in
        the '_target_node_type' attribute but we also need to handle
        the case where the _target_node_type attribute has not yet
        been set. We do this by checking if a '_node' attribute exists
        and if so, we look up the '_target_node_type' for the type
        name stored in '_node'

        Raises:
          AttributeError: when the declaration doesn't specify a node
            type
          te.TypeNotFound: when the node type specified in the
            relationship declaration cannot be found
        """

        if self._target_node_type == None:
            profile = self.profile
            self._target_node_type = profile.get_node_type(self._node)
        return self._target_node_type

    @target_node_type.setter
    def target_node_type(self, value: Any) -> None:
        if value: self._target_node_type = value

    def get_target_node_declaration(self) -> Any:
        """Return a node declaration for the target node type in this
        relationship
        """
        return self.target_node_type.create_declaration(
            name="{0}_node".format(self.name))


    def augments(self) -> ToscaRelationshipDeclaration:
        """Return the relationship declaration for which this declaration is
        an augmentation.

        Returns:
          ToscaRelationshipDeclaration: declaration for which we are
            an augmentation

        Raises:
          KeyError: if we are not an augmentation
        """

        # Find the augmentation
        if self._containing_type:
            # This relationship declaration is inside a node type
            # definition. Get the declaration for which we are an
            # augmentation from the containing node type.
            return self._containing_type.get_requirement_to_augment(self.name)
        else:
            # The only declarations that don't have a containing type
            # nor a containing declaration are synthetically-created
            # declarations (using the create_declaration
            # function). However, these declarations are never augmentations.
            raise KeyError("relationship declaration '{}' is not an augmentation".format(self.name))


    ################################################################################
    # Constructor
    ################################################################################

    def __init__(self,
                 node: Optional[str] = None,
                 relationship: Optional[dict[str, Any]] = None,
                 capability: Optional[str] = None,
                 node_filter: Any = None,
                 count_range: Optional[list[Any]] = None,
                 allocation: Any = None,
                 **kwargs: Any
    ) -> None:
        """Instantiate a new ToscaRelationshipDeclaration instance. Note that
        we have to jump through hoops to get make sure TOSCA
        requirements syntax gets mapped to proper relationship
        declarations. That is what the 'relationship' setter and
        getter are for.
        """

        # First, call superclass constructor
        super(ToscaRelationshipDeclaration, self).__init__(**kwargs)

        # ToscaRelationshipDeclaration-specific initialization
        self.capability = capability
        self.node = node
        self.relationship = relationship
        self.node_filter = node_filter
        self.count_range = count_range
        if allocation is not None: self.allocation = allocation

    @property
    def relationship(self) -> dict[str, Any]:
        relationship = {}
        relationship['type'] = self.type
        relationship['type_class'] = self.type_class
        relationship['_type_id'] = self._type_id
        try:
            if self.properties: relationship['properties'] = self.properties
        except AttributeError:
            pass
        try:
            if self.interfaces: relationship['interfaces'] = self.interfaces
        except AttributeError:
            pass
        return relationship

    @relationship.setter
    def relationship(self, value: Optional[dict[str, Any]]) -> None:
        if value:
            try:
                self.type = value['type']
            except KeyError:
                pass
            try:
                self.properties = value['properties']
            except KeyError:
                pass
            try:
                self.interfaces = value['interfaces']
            except KeyError:
                pass


    ################################################################################
    # Implementation of reserved keywords
    ################################################################################

    def SOURCE(self) -> Any:
        """Return the declaration for the entity referred to by source for
        this relationship declaration. 

        Returns:
          ToscaManagedDeclaration or ToscaManagedType

        Raises:
          AttributeError: if the template has no containing managed
            type or managed declaration
        """
        if self._containing_type:
            return self._containing_type
        elif self._containing_declaration:
            return self._containing_declaration
        else:
            raise AttributeError("No containing node found for <{0}>".format(self.name))


    def TARGET(self) -> Any:
        """Return the declaration for the entity referred to by target for
        this relationship declaration. 

        Returns:
          ToscaManagedDeclaration or ToscaManagedType

        Raises:
          AttributeError: if the template has no containing managed
            type or managed declaration

        """
        return self.target_node_type


    def propagate_upgrade_tosca_path(self, tosca_path: Any) -> Any:
        """Propagate request to upgrade the provided TOSCA Path to Version 2.0 syntax. 

        - If the TOSCA Path references a target node, we insert the
          'TARGET' keyword.
        """
        # If we have a target node, insert a 'TARGET' keyword
        try:
            upgraded = ['TARGET']
            upgraded_path = self.target_node_type.upgrade_tosca_path(tosca_path)
            if isinstance(upgraded_path, list):
                upgraded.extend(upgraded_path)
            else:
                upgraded.append(upgraded_path)
            return upgraded
        except Exception:
            # No target node. Just return the tosca path as is.
            return tosca_path
        

    def get_attribute_or_property_declaration(self, attr_or_prop: str, value_name: Any) -> Any:
        """Return the declaration for the property or attribute specified in
        'value_name' (where the 'attr_or_prop' flag specifies whether
        to look up a property declaration or an attribute
        declaration). Relationship declarations must check if
        'value_name' is a TOSCA Path expression that specifies a
        source or target node or a target capability.

        Args:
          value_name (string or ToscaPath): the property or
            attribute for which to return the declaration.
          attr_or_prop (either 'properties' or 'attributes'): flag
            that specifies whether to look for a property declaration
            or an attribute declaration.

        Returns:
          ToscaPropertyDeclaration

        Raises:
          KeyError: when property or attribute_declaration not found
        """
        try:
            # Is value_name a ToscaPath expression? 
            path = ToscaPath(value_name)
            # Does the path reference a target node?
            if path.entity == 'TARGET':
                # Hand-off the 'get_attribute' or 'get_property' call
                # to the target node. This will raise a KeyError if
                # the attribute or property is not found.
                return self.target_node_type.get_attribute_or_property_declaration(
                    attr_or_prop, path.sub_entity)
            # Does the path reference a target capability?
            if path.entity == 'CAPABILITY':
                # Hand-off the 'get_attribute' or 'get_property' call
                # to the capability. This will raise a KeyError if the
                # attribute or property is not found.
                return self.target_capability_type.get_attribute_or_property_declaration(
                    attr_or_prop, path.sub_entity)
            # Does the path reference a source node?
            if path.entity == 'SOURCE':
                # Hand-off the 'get_attribute' or 'get_property' call
                # to the source node of this relationship. This will
                # raise a KeyError if the attribute or property is not
                # found.
                if self._containing_type:
                    source = self._containing_type
                elif self._containing_declaration:
                    source = self._containing_declaration
                return source.get_attribute_or_property_declaration(
                    attr_or_prop, path.sub_entity)
        except TypeError:
            # Not a ToscaPath. 
            pass

        # 'value_name' is not a TOSCA Path expression, or does not
        # reference a requirement or capability. Just delegate to our
        # base class.
        return super(ToscaRelationshipDeclaration, self).get_attribute_or_property_declaration(
            attr_or_prop, value_name)

    def get_implementation_artifact(self, artifact_name: str) -> Any:
        """Return the artifact an operation implementation names (TOSCA 2.0
        §11.8): an artifact of the node type or node template that contains
        the operation. A relationship operation written in a requirement
        definition is contained by the node type or declaration that
        declares the requirement, so the name is that node's artifact.

        Raises:
          KeyError: when no such artifact is found
        """
        node = self._containing_type or self._containing_declaration
        if node is None:
            raise KeyError("'{0}': no node contains this relationship".format(artifact_name))
        return node.get_implementation_artifact(artifact_name)

    def get_artifact(self, artifact_name: Any) -> Any:
        """Return the artifact a path through SOURCE or TARGET names, such as
        [SOURCE, <artifact>] from a $get_artifact path [SELF, SOURCE,
        <artifact>]. A relationship defines no artifacts (TOSCA 2.0 §7.3,
        §7.4), so a bare name is refused.

        Raises:
          KeyError: when the name is bare, the path passes through anything
            but SOURCE or TARGET, or that end declares no such artifact
        """
        try:
            path = ToscaPath(artifact_name)
        except TypeError:
            raise KeyError("'{0}': a relationship defines no artifacts".format(artifact_name))
        if path.entity == 'SOURCE':
            return self.SOURCE().get_artifact(path.sub_entity)
        if path.entity == 'TARGET':
            return self.TARGET().get_artifact(path.sub_entity)
        raise KeyError("'{0}': a relationship's artifact path passes through SOURCE or "
                       "TARGET".format(artifact_name))


    ################################################################################
    # Is this relationship required?
    ################################################################################

    def is_required(self) -> bool:
        """Must this requirement always be fulfilled?"""
        range = ToscaRange(self.count_range)
        if range.lower_bound == 0:
            return False
        else:
            return True

    def supports_multiple(self) -> bool:
        """Do we support multiple instances of this requirement?"""
        range = ToscaRange(self.count_range)
        if range.upper_bound == 'UNBOUNDED' or range.upper_bound > 1:
            return True
        else:
            return False

    ################################################################################
    # Create a template for this declaration
    ################################################################################

    def create_template(self) -> Any:
        """Create a relationship template from this declaration"""
        import tosca_core.models.relationship_template
        relationship = tosca_core.models.relationship_template.ToscaRelationshipTemplate()
        relationship.name = self.name
        relationship.declaration = self
        try:
            count_range = self.count_range
            # We only need the minimum required in the relationship
            # template. 
            relationship.count = count_range[0]
        except AttributeError:
            pass
        return relationship
    

    ################################################################################
    # Other stuff that needs to be organized. 
    ################################################################################

    @property
    def capability(self) -> str:
        return self.target_capability_type.name

    @capability.setter
    def capability(self, value: Optional[str]) -> None:
        if value: self._capability = value


    @property
    def node(self) -> str:
        return self.target_node_type.name

    @node.setter
    def node(self, value: Optional[str]) -> None:
        if value: self._node = value


    ################################################################################
    # Sub-Entity Refinement
    ################################################################################

    def merge_augmented_declaration(self, relationship_declaration: ToscaRelationshipDeclaration) -> None:
        """Augment a relationship declaration with attributes from a
        second relationship declaration"""

        # First, call superclass augment method
        super(ToscaRelationshipDeclaration, self).merge_augmented_declaration(relationship_declaration)

        # Merge count_range if not already set
        if not self._count_range:
            # Count range not set yet. Make sure to use the property
            # decorator to pick up the version-specific default.
            self.count_range = relationship_declaration.count_range

        # Merge 'capability' attribute if necessary
        try:
            capability = self._capability
            # Already have one. Nothing further to do.
        except AttributeError:
            # Not set. Check declaration that is being augmented
            try:
                self._target_capability_type = relationship_declaration._target_capability_type
                self.capability = relationship_declaration.capability
            except AttributeError:
                # Declaration we're augmenting doesn't have capability either
                pass

        # Merge 'node' attribute if necessary
        try:
            node = self._node
            # Already have one. Nothing further to do.
        except AttributeError:
            # Not set. Check declaration that is being augmented
            try:
                self._target_node_type = relationship_declaration._target_node_type
                self.node = relationship_declaration.node
            except AttributeError:
                # Declaration we're augmenting doesn't have node either
                pass
