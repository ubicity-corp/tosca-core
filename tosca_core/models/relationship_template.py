"""
Module defining Tosca relationship template entity
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

# Types on which this type depends
import tosca_core.models.managed_template

# Types used in relationships
import tosca_core.models.node_template

# ToscaPath support
from tosca_core.models.path import ToscaPath

# Exceptions
import tosca_core.models.exceptions as te
import tosca_core.models.presence as presence


class ToscaRelationshipTemplate(tosca_core.models.managed_template.ToscaManagedTemplate):
    """The ToscaRelationshipTemplate entity represents relationships
    specified in TOSCA nodes and topologies
    """

    ################################################################################
    # Polymorphic mapping
    ################################################################################

    __mapper_args__ = {
        'polymorphic_identity':'relationship',
    }

    # '_directives' is declared on the shared ToscaTemplate base.

    @property
    def directives(self) -> list[str]:
        """TOSCA 2.0 requirement directives. Counterpart of the
        capability-side directives: the list orders which target scope
        (internal vs external to the source's service) the orchestrator
        tries first, and restricts the set of permitted scopes. The
        spec leaves the default implementation-defined; default to
        ['internal', 'external'] -- both allowed, internal preferred --
        matching what the capability side defaults to.
        """
        return self._directives if self._directives is not None else ['internal', 'external']

    # Directives currently supported for requirement assignments
    valid_directives = ['internal', 'external']

    ################################################################################
    # Keys
    ################################################################################
    
    # Foreign keys

    # Target node can be either a node template or a node
    # type. Support both, but only one can be non-null at the same
    # time.
    _target_node_id =      db.Column(db.Integer, 
                                     db.ForeignKey('tosca_template.id'),
                                     nullable=True)
    _target_node_type_id = db.Column(db.Integer, 
                                     db.ForeignKey('tosca_type.id'),
                                     nullable=True)
    
    ################################################################################
    # Fields
    ################################################################################

    # When targeting a node template with a 'count' value, specify the
    # index of the targeted node
    _target_node_index =      db.Column(db.PickleType, nullable=True)
    @property
    def target_node_index(self) -> Any:
        try:
            if self._target_node_index != None:
                return self._target_node_index
        except AttributeError:
            pass
        raise AttributeError(f"'{self.name}' does not have 'target_node_index'")
    @target_node_index.setter
    def target_node_index(self, value: Any) -> None:
        if value != None: self._target_node_index = value

    # Optional fields start with '_' and have corresponding getters
    # and setters to ensure that retrieving fields consistently raises
    # an AttributeError when not set.  Note that 'nullable' defaults
    # to True, but we explicitly set the 'nullable' flag for clarity.

    _optional =            db.Column(db.Boolean, nullable=True, default=False)
    @property
    def optional(self) -> bool:
        try:
            return self._optional
        except AttributeError:
            return False
    @optional.setter
    def optional(self, value: Optional[bool]) -> None:
        if value != None: self._optional = value

    _unique =            db.Column(db.Boolean, nullable=True, default=False)
    @property
    def unique(self) -> bool:
        try:
            return self._unique
        except AttributeError:
            return False
    @unique.setter
    def unique(self, value: Optional[bool]) -> None:
        if value != None: self._unique = value

    _capability =          db.Column(db.String, nullable=True)
    @property
    def capability(self) -> str:
        if not self._capability:
            raise AttributeError(f"'{self.name}' does not have 'capability'")
        return self._capability
    @capability.setter
    def capability(self, value: Optional[str]) -> None:
        if value: self._capability = value

    _allocation =          db.Column(db.PickleType, nullable=True)
    @property
    def allocation(self) -> Any:
        if not self._allocation:
            raise AttributeError(f"'{self.name}' does not have 'allocation' attribute")
        return self._allocation
    @allocation.setter
    def allocation(self, value: Any) -> None:
        if value: self._allocation = value

    ################################################################################
    # Model Navigation
    ################################################################################

    # Relationship templates can have a target node template or a
    # target node type, but not both.
    _target_node =         db.relationship('ToscaNodeTemplate',
                                           remote_side='ToscaNodeTemplate.id',
                                           foreign_keys='ToscaRelationshipTemplate._target_node_id',
                                           backref='targeted_by')

    @property
    def target_node(self) -> Any:
        if self._target_node:
            return self._target_node
        # Target node not set yet. Try to set it based on the
        # '_node' attribute?
        try:
            # Target node could be a Tosca Path expression
            try:
                path = ToscaPath(self._node)
                target_node = path.entity
                target_node_index = path.sub_entity
            except TypeError:
                target_node = self._node
                target_node_index = None
            self._target_node = self.service.node_templates[target_node]
            self._target_node_index = target_node_index
            return self._target_node
        except (AttributeError, KeyError):
            # No _node attribute or _node not found
            raise AttributeError(f"'{self.name}' does not have 'target_node'")

    @target_node.setter
    def target_node(self, value: Any) -> None:
        if value: self._target_node = value


    _target_node_type =    db.relationship('ToscaNodeType',
                                           remote_side='ToscaNodeType.id',
                                           foreign_keys='ToscaRelationshipTemplate._target_node_type_id')

    @property
    def target_node_type(self) -> Any:
        """return the target node type entity for this relationship template

        Under normal operation, this method returns the type stored in
        the '_target_node_type' attribute but we also need to handle
        the case where the _target_node_type attribute has not yet
        been set. We do this by checking if a '_node' attribute exists
        and if so, we look up the '_target_node_type' for the type
        name stored in '_node'

        Raises:
          AttributeError: when the template doesn't specify a node
            type
          te.TypeNotFound: when the node type specified in the
            relationship template cannot be found
        """
        if self._target_node_type:
            return self._target_node_type

        # Target node type not yet set. Try to set it based on the
        # '_node' attribute?
        node_type = self._node
        profile = self.profile
        self._target_node_type =  profile.get_node_type(node_type)
        return self._target_node_type

    @target_node_type.setter
    def target_node_type(self, value: Any) -> None:
        if value: self._target_node_type = value


    ################################################################################
    # Support for target query types
    ################################################################################

    def get_target_query_node_type(self) -> Optional[Any]:
        """Return the node type to be used to find nodes to fulfill a dangling
        requirement.
        """
        # Try target node type specified in the template
        try:
            return self.target_node_type
        except AttributeError:
            # No target node type specified in template
            try:
                return self.declaration.target_node_type
            except AttributeError:
                # No target node type
                return None

    def get_target_query_capability_type(self) -> Optional[Any]:
        """Return the capability type to be used to find nodes to fulfill a
        dangling requirement.
        """
        try:
            # Get the capability type specified in this relationship
            # template
            capability = self.capability
            return self.profile.get_capability_type(capability)
        except (AttributeError, KeyError, te.TypeNotFound):
            # No capability type specified in this relationship
            # template or the capability is a named capability. Just
            # use the capability type from the relationship
            # declaration
            try:
                return self.declaration.target_capability_type
            except Exception:
                return None


    ################################################################################
    # Constructor
    ################################################################################

    def __init__(self,
                 node: Optional[Any] = None,
                 relationship: Optional[dict[str, Any]] = None,
                 capability: Optional[str] = None,
                 optional: Optional[bool] = None,
                 unique: Optional[bool] = None,
                 occurrences: Optional[Any] = None,
                 allocation: Optional[Any] = None,
                 directives: Optional[list[str]] = None,
                 **kwargs: Any
    ) -> None:
        """Instantiate a new ToscaRelationshipTemplate instance. Note that we
        have to jump through hoops to get make sure TOSCA requirements
        syntax gets mapped to proper relationship templates. That is
        what the 'relationship' setter and getter are for.
        """

        # First, call superclass constructor
        super(ToscaRelationshipTemplate, self).__init__(**kwargs)

        # ToscaRelationshipTemplate-specific initialization
        self.capability = capability
        self.node = node
        self.relationship = relationship
        self.optional = optional
        self.unique = unique
        self.allocation = allocation
        if occurrences: self.occurrences = occurrences
        if directives: self._directives = directives

    # Fields a nested 'relationship:' block in a requirement
    # assignment can carry, beyond 'type' and 'type_class'. Mirrors
    # the field list exposed by ManagedTemplateSchema.
    _RELATIONSHIP_PASSTHROUGH_FIELDS = (
        'interfaces', 'properties', 'attributes',
        'description', 'meta_data',
    )

    @property
    def relationship(self) -> dict[str, Any]:
        relationship = {}
        relationship['type'] = self.type
        relationship['type_class'] = self.type_class
        relationship['_type_id'] = self._type_id
        for field in self._RELATIONSHIP_PASSTHROUGH_FIELDS:
            try:
                value = getattr(self, field)
                if value:
                    relationship[field] = value
            except AttributeError:
                pass
        return relationship

    @relationship.setter
    def relationship(self, value: Optional[dict[str, Any]]) -> None:
        if not value:
            return
        try:
            self.type = value['type']
        except KeyError:
            pass
        for field in self._RELATIONSHIP_PASSTHROUGH_FIELDS:
            try:
                setattr(self, field, value[field])
            except KeyError:
                pass


    ################################################################################
    # Implementation of reserved keywords
    ################################################################################

    def SOURCE(self) -> Any:
        """Return the node template referred to by SOURCE for this
        template. SOURCE applies to relationship templates
        only. Calling SOURCE() on other templates raises an
        InvalidPathError
        """
        try:
            return self.source_node
        except AttributeError:
            # No containing instance
            error = f"Unable to retrieve SOURCE for {self.name}: no source node"
            raise te.ModelCorruptionError(error)

        
    def TARGET(self) -> Any:
        """Return node template referred to by TARGET for this
        template. TARGET applies to relationship templates
        only. Calling TARGET() on other templates raises an
        InvalidPathError
        """
        try:
            return self.target_node.declaration
        except AttributeError:
            # Dangling requirement. Try to get the node declaration
            # from the target node type specified in the relationship
            # declaration.
            try:
                return self.target_node_type.create_declaration(
                    name=f"{self.name}_node")
            except AttributeError:
                # No target node type specified. Get it from the
                # relationship declaration
                try:
                    return self.declaration.get_target_node_declaration()
                except AttributeError:
                    # No target node type specified in the
                    # relationship declaration either.
                    error = f"No TARGET node type for requirement '{self.name}'"
                    raise te.InvalidPathError(error)
        

    ################################################################################
    # Helper functions
    ################################################################################

    def is_dangling(self) -> bool:
        """Return true if this relationship template represents a dangling
        requirement.
        """
        try:
            # A relationship template is dangling if it targets a selectable node.
            return self.target_node.is_selectable()
        except AttributeError:
            # A relationship template is dangling if it does not
            # define a target node.
            return True

    
    ################################################################################
    # Navigationfunctions
    ################################################################################

    def get_attribute_or_property_declaration(self, attr_or_prop: str, value_name: Any) -> Any:
        """Return the attribute or property value declaration for the property or
        attribute specified by 'value_name' (where the 'attr_or_prop'
        flag specifies whether to look up a property declaration or an
        attribute declaration). Relationship declarations must check if
        'value_name' is a TOSCA Path expression that specifies a
        source or target node or a target capability.

        Args:
          value_name (string or ToscaPath): the property or
            attribute for which to return the declaration.
          attr_or_prop (either 'properties' or 'attributes'): flag
            that specifies whether to look for a property declaration
            or an attribute declaration.

        Returns:
          Python value

        Raises:
          KeyError: when property or attribute_declaration not found
        """
        try:
            # Is value_name a ToscaPath expression? 
            path = ToscaPath(value_name)

            # Does the path reference a target node?
            if path.entity == 'TARGET':
                try:
                    # Try to hand-off the 'get_attribute' or
                    # 'get_property' call to the target node
                    # first. This will raise a KeyError if the
                    # attribute or property is not found.
                    return self.target_node.get_attribute_or_property_declaration(
                        attr_or_prop, path.sub_entity)
                except AttributeError:
                    # No target node specified. Try to hand off to
                    # the target node type instead. This will raise a
                    # KeyError if the attribute or property is not
                    # found.
                    target_node_type = self.get_target_query_node_type()
                    if target_node_type:
                        return target_node_type.get_attribute_or_property_declaration(
                            attr_or_prop, path.sub_entity)
                    else:
                        # No target node type found
                        raise KeyError(str(value_name))
                
            # Does the path reference a target capability?
            if path.entity == 'CAPABILITY':
                # Hand off to the target capability type
                target_capability_type = self.get_target_query_capability_type()
                if target_capability_type:
                    return target_capability_type.get_attribute_or_property_declaration(
                        attr_or_prop, path.sub_entity)
                else:
                    # No target node type found
                    raise KeyError(str(value_name))
                
            # Does the path reference a source node?
            if path.entity == 'SOURCE':
                # Hand-off the 'get_attribute' or 'get_property' call
                # to the source node of this relationship. This will
                # raise a KeyError if the attribute or property is not
                # found.
                return self.source_node.get_attribute_or_property_declaration(
                    attr_or_prop, path.sub_entity)

        except TypeError:
            # Not a ToscaPath. 
            pass

        # 'value_name' is not a TOSCA Path expression, or does not
        # reference a requirement or capability. Just delegate to our
        # base class.
        return super(ToscaRelationshipTemplate, self).get_attribute_or_property_declaration(
            attr_or_prop, value_name)


    def get_implementation_artifact(self, artifact_name: str) -> Any:
        """Return the artifact an operation implementation names (TOSCA 2.0
        §11.8): an artifact of the node type or node template that contains
        the operation. A relationship operation written in a requirement
        assignment is contained by the node template whose requirement it
        is; one in a relationship template of its own has no such node.

        Raises:
          KeyError: when no such artifact is found
        """
        try:
            node = self.source_node
        except AttributeError:
            raise KeyError("'{0}': no node template contains this relationship".format(artifact_name))
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
            return self.source_node.get_artifact(path.sub_entity)
        if path.entity == 'TARGET':
            return (self.target_node or self.TARGET()).get_artifact(path.sub_entity)
        raise KeyError("'{0}': a relationship's artifact path passes through SOURCE or "
                       "TARGET".format(artifact_name))
        

    ################################################################################
    # Support for checking if property value templates are available
    # in this template and for retrieving attribute and property value
    # templates from this relationship template.
    ################################################################################

    def is_property_template_present(self, property_path: Any, property_declaration: Any) -> bool:
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
        try:
            # Is property_path a ToscaPath expression? 
            path = ToscaPath(property_path)

            # Does the path reference a relationship?
            if path.entity == 'TARGET':
                # Hand-off to the target node template
                try:
                    return self.target_node.is_property_template_present(
                        path.sub_entity, property_declaration)
                except AttributeError:
                    # No target node
                    return False
                except Exception as e:
                    logger.error(str(e))
                    return presence.Undecided(f"cannot follow relationship '{self.name}': {e}")

            # Does the path reference a target capability?
            if path.entity == 'CAPABILITY':
                # Hand-off to the target capability.
                try:
                    capability = self.target_node.capabilities[self.capability]
                    return capability.is_property_template_present(
                        path.sub_entity, property_declaration)
                except AttributeError:
                    # No target node
                    return False
                except Exception as e:
                    logger.error(str(e))
                    return presence.Undecided(f"cannot follow relationship '{self.name}': {e}")

            # Does the path reference a source node?
            if path.entity == 'SOURCE':
                # Hand-off the 'get_attribute' or 'get_property' call
                # to the source node of this relationship. 
                return self.source_node.is_property_template_present(
                    path.sub_entity, property_declaration)

        except TypeError as e:
            # Not a ToscaPath.
            pass

        # 'property_path' is not a TOSCA Path expression, or does not reference
        # a requirement or capability. Just delegate to our base
        # class.
        return super(ToscaRelationshipTemplate, self).is_property_template_present(
            property_path, property_declaration)
    
    def get_attribute_or_property_template(self, attr_or_prop: str, value_name: Any) -> Optional[Any]:
        """Return the attribute or property value template for the property or
        attribute specified by 'value_name' (where the 'attr_or_prop'
        flag specifies whether to look up a property template or an
        attribute template). Relationship templates must check if
        'value_name' is a TOSCA Path expression that specifies a
        source or target node or a target capability.

        Args:
          value_name (string or ToscaPath): the property or
            attribute for which to return the template.
          attr_or_prop (either 'properties' or 'attributes'): flag
            that specifies whether to look for a property template
            or an attribute template.

        Returns:
          Python value

        Raises:
          None
        """
        try:
            # Is value_name a ToscaPath expression? 
            path = ToscaPath(value_name)

            # Does the path reference a relationship?
            if path.entity == 'TARGET':
                # Hand-off the 'get_attribute' or 'get_property' call
                # to the target node template
                try:
                    return self.target_node.get_attribute_or_property_template(
                        attr_or_prop, path.sub_entity)
                except AttributeError:
                    # No target node
                    return None
                except Exception as e:
                    logger.error(str(e))
                    return None

            # Does the path reference a target capability?
            if path.entity == 'CAPABILITY':
                # Hand-off the 'get_attribute' or 'get_property' call
                # to the target capability.
                try:
                    capability = self.target_node.capabilities[self.capability]
                    return capability.get_attribute_or_property_template(
                        attr_or_prop, path.sub_entity)
                except AttributeError:
                    # No target node
                    return None
                except Exception as e:
                    logger.error(str(e))
                    return None

            # Does the path reference a source node?
            if path.entity == 'SOURCE':
                # Hand-off the 'get_attribute' or 'get_property' call
                # to the source node of this relationship. 
                return self.source_node.get_attribute_or_property_template(
                    attr_or_prop, path.sub_entity)

        except TypeError as e:
            # Not a ToscaPath.
            pass

        # 'value_name' is not a TOSCA Path expression, or does not
        # reference a requirement or capability. Just delegate to our
        # base class.
        return super(ToscaRelationshipTemplate, self).get_attribute_or_property_template(
            attr_or_prop, value_name)


    ################################################################################
    # Other stuff that needs to be organized. These functions use type
    # names without a profile qualifier. This needs to get
    # addressed.
    ################################################################################

    @property
    def node(self) -> str:
        if self._target_node:
            return self._target_node.name
        elif self._target_node_type:
            return self._target_node_type.name
        else:
            raise AttributeError(f"requirement '{self.name}' does not have 'node' attribute")

    @node.setter
    def node(self, value: Optional[Any]) -> None:
        if value: self._node = value


    @property
    def source_node(self) -> Any:
        if not self.containing_template:
            raise AttributeError(f"Instance '{self.name}' does not have 'source_node' attribute")
        return self.containing_template

    @source_node.setter
    def source_node(self, value: Any) -> None:
        if value: self.containing_template = value


    ################################################################################
    # Template refinement support
    ################################################################################

    def complete_template_refinement(self, relationship: ToscaRelationshipTemplate) -> None:
        """Override a relationship with values from a second relationship"""

        # First, call superclass augment method
        super(ToscaRelationshipTemplate, self).complete_template_refinement(relationship)

        # Override 'capability' attribute
        self.merge_augmented_field('_capability', relationship)
        self.merge_augmented_field('_optional', relationship)
        self.merge_augmented_field('_unique', relationship)
        # Allocation and target-node-index are also opaque scalars
        # that 'copy' should carry over when self leaves them unset.
        self.merge_augmented_field('_allocation', relationship)
        self.merge_augmented_field('_target_node_index', relationship)

        # Override 'node' attribute
        self.merge_augmented_node(relationship)

        
    def merge_augmented_node(self, relationship: ToscaRelationshipTemplate) -> None:
        """Set the node for the augmented relationship"""

        # Do we already have a node?
        if self._target_node or self._target_node_type:
            # Nothing to do
            return

        # Copy target node type or target node from augmenting
        # relationship if it has it.
        if relationship._target_node_type:
            self.target_node_type = relationship._target_node_type
            return
        if relationship._target_node:
            self.target_node = relationship._target_node
            return

        # No target node or target node type yet. Just override 'node' attribute
        self.merge_augmented_field('_node', relationship)
