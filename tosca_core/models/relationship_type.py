"""
Module definining Tosca Relationship Type definitions
"""
from __future__ import annotations

__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2014-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger: logging.Logger = logging.getLogger(__name__)

# Type hints
from typing import Any, Optional

# Database support
from tosca_core import db

# Path
from tosca_core.models.path import ToscaPath

# Types on which this type depends
import tosca_core.models.managed_type

# Exception support
import tosca_core.models.exceptions as te
import tosca_core.models.recognized_names as rn


class ToscaRelationshipType(tosca_core.models.managed_type.ToscaManagedType):
    """The ToscaRelationshipType represents a named relationship type
    that can be used for declaring Tosca relationship templates in
    other type definitions.
    """

    ################################################################################
    # Polymorphic mapping
    ################################################################################

    __mapper_args__ = {
        'polymorphic_identity':'relationship',
    }

    ################################################################################
    # Fields.  Optional fields start with '_' and have corresponding
    # getters (and optionally setters) to ensure that retrieving
    # fields consistently raises an AttributeError when not set.  Note
    # that 'nullable' defaults to True, but we explicitly set the
    # 'nullable' flag for clarity.
    ################################################################################

    valid_kinds = ['ASSOCIATION', 'DEPENDENCY', 'CONTAINMENT' ]
    default_kind = 'DEPENDENCY'

    # The kind the type states in its metadata (relationship_kind), copied
    # here by validation. TOSCA defines no kinds and no keyname for one; the
    # column stays because it is part of the database format.
    _kind = db.Column(db.String)
    @property
    def kind(self) -> str:
        if self._kind == None:
            raise AttributeError("'{0}' does not have 'kind'".format(self.name))
        return self._kind

    _valid_capability_types = db.Column(db.PickleType, nullable=True)
    @property
    def valid_capability_types(self) -> list[str]:
        if self._valid_capability_types == None:
            raise AttributeError("'{0}' does not have 'valid_capability_types'".format(self.name))
        return self._valid_capability_types

    # valid source node types are defined in the base ToscaType class
    # since it is also used in ToscaCapabilityType

    _valid_target_node_types = db.Column(db.PickleType, nullable=True)
    @property
    def valid_target_node_types(self) -> list[str]:
        if self._valid_target_node_types == None:
            raise AttributeError("'{0}' does not have 'valid_target_node_types'".format(self.name))
        return self._valid_target_node_types

    ################################################################################
    # Constructor
    ################################################################################

    def __init__(self,
                 valid_capability_types: Optional[list[str]] = None,
                 valid_target_node_types: Optional[list[str]] = None,
                 valid_source_node_types: Optional[list[str]] = None,
                 **kwargs: Any
    ) -> None:
        # First, call superclass constructor
        super(ToscaRelationshipType, self).__init__(**kwargs)

        # ToscaRelationshipType-specific initialization
        if valid_capability_types != None: self._valid_capability_types = valid_capability_types
        if valid_target_node_types != None: self._valid_target_node_types = valid_target_node_types
        if valid_source_node_types != None: self._valid_source_node_types = valid_source_node_types
        
    ################################################################################
    # Create a declaration of this type
    ################################################################################

    def create_declaration(self, name: str = 'anonymous relationship') -> ToscaRelationshipDeclaration:
        """Synthesize a ToscaRelationshipDeclaration object for this
        relationship type

        Args:
          name(str): name for the relationship being declared
        Returns:
          ToscaRelationshipDeclaration: with the appropriate name and
            type. No other attributes are initialized.

        Raises:
          None
        """
        from tosca_core.models.relationship_declaration import ToscaRelationshipDeclaration
        relationship_declaration = ToscaRelationshipDeclaration(name=name, type=self.name)
        relationship_declaration.type_entity = self
        return relationship_declaration


    ################################################################################
    # Other stuff that needs to be organized. 
    ################################################################################

    def is_valid_capability_type(self, capability_type: Any) -> bool:
        """Is the specified target capability type entity valid for this
        relationship type?

        Args:
          capability_type(ToscaCapabilityType): capability type for
            which to check if it is a valid target capability type for
            this relationship type

        Raises:
          None
        """

        # Do we restrict capability types?
        try:
            # Is the specified capability type (or one of its base
            # classes) in the list of valid capability types?
            for valid_target in self.valid_capability_types:
                valid_target_type = self.profile.get_capability_type(valid_target)
                if capability_type.has_type(valid_target_type):
                    return True
             # Not a valid target
            return False
             
        except (AttributeError, TypeError):
            # We don't restrict capability types (since we don't have
            # a valid_capability_types attribute or the
            # valid_capability_types attribute is None). Does our
            # parent class?
            try:
                return self.parent.is_valid_capability_type(capability_type)
            except (AttributeError, te.CircularInheritance):
                # We don't restrict capability types, and we don't
                # have a parent who could do so either. All capability
                # types are OK.
                return True


    def is_valid_source_node_type(self, node_type: Any) -> bool:
        """Is the specified node type entity a valid source node type for this
        relationship type?

        Args:
          node_type(ToscaNodeType): node type for which to check if it
            is a valid source node type for this relationship type

        Raises:
          None
        """

        # Do we restrict source node types?
        try:
            # Is the specified node type (or one of its base classes)
            # in the list of valid source node types?
            for valid_source in self.valid_source_node_types:
                valid_source_type = self.profile.get_node_type(valid_source)
                if node_type.has_type(valid_source_type):
                    return True
             # Not a valid source node type
            return False
             
        except (AttributeError, TypeError):
            # We don't restrict source node types (since we don't have
            # a valid_source_node_types attribute or the
            # valid_source_node_types attribute is None). Does our
            # parent class?
            try:
                return self.parent.is_valid_source_node_type(node_type)
            except (AttributeError, te.CircularInheritance):
                # We don't restrict source node types, and we don't
                # have a parent who could do so either. All source
                # node types are OK.
                return True
            

    def is_valid_target_node_type(self, node_type: Any) -> bool:
        """Is the specified node type entity a valid target node type for this
        relationship type?

        Args:
          node_type(ToscaNodeType): node type for which to check if it
            is a valid target node type for this relationship type

        Raises:
          None
        """

        # Do we restrict target node types?
        try:
            # Is the specified node type (or one of its base classes)
            # in the list of valid target node types?
            for valid_target in self.valid_target_node_types:
                valid_target_type = self.profile.get_node_type(valid_target)
                if node_type.has_type(valid_target_type):
                    return True
             # Not a valid target node type
            return False
             
        except (AttributeError, TypeError):
            # We don't restrict target node types (since we don't have
            # a valid_target_node_types attribute or the
            # valid_target_node_types attribute is None). Does our
            # parent class?
            try:
                return self.parent.is_valid_target_node_type(node_type)
            except (AttributeError, te.CircularInheritance):
                # We don't restrict target node types, and we don't
                # have a parent who could do so either. All target
                # node types are OK.
                return True
            

    def get_lowest_valid_capability_types_ancestor(self) -> Optional[Any]:
        """Get the lowest common ancestor of the types in the valid capability
        types list. Check parent type if valid capability types not
        defined locally.

        Returns:
          (ToscaCapabilityType): lowest valid capability types ancestor
          None: if no common ancestor for the valid capability types
        Raises:
          None
        """
        # Do we restrict capability types?
        try:
            valid_capability_types = self.valid_capability_types
        except (AttributeError, TypeError):
            # We don't restrict capability types.  Does our parent
            # class?
            try:
                return self.parent.get_lowest_valid_capability_types_ancestor()
            except (AttributeError, te.CircularInheritance):
                # No parent.
                return None

        # Start with the first type in the list
        from tosca_core.models.type import lowest_common_ancestor
        try:
            common_type = self.profile.get_capability_type(valid_capability_types[0])
        except Exception as e:
            logger.error("Error getting common valid capability type: %s", str(e))
            return None

        # Then, iterate through the rest of the list
        for next_type_name in valid_capability_types[1:]:
            try:
                next_type = self.profile.get_capability_type(next_type_name)
            except Exception as e:
                logger.error("Error getting next valid capability type: %s", str(e))
                return None
            common_type = lowest_common_ancestor(common_type, next_type)
            if not common_type: return None
                
        # All done
        return common_type

    def get_lowest_valid_target_node_types_ancestor(self) -> Optional[Any]:
        """Get the lowest common ancestor of the types in the valid target_node
        types list. Check parent type if valid target_node types not
        defined locally.

        Returns:
          (ToscaNodeType): lowest valid target node types ancestor
          None: if no common ancestor for the valid target node types
        Raises:
          None
        """
        # Do we restrict target node types?
        try:
            valid_target_node_types = self.valid_target_node_types
        except (AttributeError, TypeError):
            # We don't restrict target_node types.  Does our parent
            # class?
            try:
                return self.parent.get_lowest_valid_target_node_types_ancestor()
            except (AttributeError, te.CircularInheritance):
                # No parent.
                return None

        # Start with the first type in the list
        from tosca_core.models.type import lowest_common_ancestor
        try:
            common_type = self.profile.get_node_type(valid_target_node_types[0])
        except Exception as e:
            logger.error("Error getting common valid target_node type: %s", str(e))
            return None

        # Then, iterate through the rest of the list
        for next_type_name in valid_target_node_types[1:]:
            try:
                next_type = self.profile.get_node_type(next_type_name)
            except Exception as e:
                logger.error("Error getting next valid target_node type: %s", str(e))
                return None
            common_type = lowest_common_ancestor(common_type, next_type)
            if not common_type: return None
                
        # All done
        return common_type

    def get_lowest_valid_source_node_types_ancestor(self) -> Optional[Any]:
        """Get the lowest common ancestor of the types in the valid source_node
        types list. Check parent type if valid source_node types not
        defined locally.

        Returns:
          (ToscaNodeType): lowest valid source node types ancestor
          None: if no common ancestor for the valid source node types
        Raises:
          None
        """
        # Do we restrict source node types?
        try:
            valid_source_node_types = self.valid_source_node_types
        except (AttributeError, TypeError):
            # We don't restrict source_node types.  Does our parent
            # class?
            try:
                return self.parent.get_lowest_valid_source_node_types_ancestor()
            except (AttributeError, te.CircularInheritance):
                # No parent.
                return None

        # Start with the first type in the list
        from tosca_core.models.type import lowest_common_ancestor
        try:
            common_type = self.profile.get_node_type(valid_source_node_types[0])
        except Exception as e:
            logger.error("Error getting common valid source_node type: %s", str(e))
            return None

        # Then, iterate through the rest of the list
        for next_type_name in valid_source_node_types[1:]:
            try:
                next_type = self.profile.get_node_type(next_type_name)
            except Exception as e:
                logger.error("Error getting next valid source_node type: %s", str(e))
                return None
            common_type = lowest_common_ancestor(common_type, next_type)
            if not common_type: return None
                
        # All done
        return common_type


    def get_kind(self) -> str:
        """Return the kind of relationship this is: the one its metadata
        states ('metadata: {relationship_kind: ...}', or
        'relationship-kind'), else its parent type's kind, else the default.
        """
        try:
            return self.kind
        except AttributeError:
            pass
        # Validation copies the metadata's kind into 'kind'; reading it here
        # as well gives a type its kind whether or not it has been validated.
        try:
            return rn.relationship_kind(self.meta_data).upper()
        except (AttributeError, KeyError, TypeError):
            pass
        # No kind defined. Get kind from parent type.
        try:
            parent = self.parent
            return parent.get_kind()
        except (AttributeError, te.CircularInheritance):
            # No parent. Return default
            return self.default_kind

    ################################################################################
    # Implementation of reserved keywords
    ################################################################################

    def SOURCE(self) -> Any:
        """Return the node type for the entity referred to by SOURCE in
        this relationship type: the lowest common ancestor of its valid
        source node types, as get_attribute_or_property_declaration
        resolves a SOURCE path. Every source the type admits is of that
        type, so what a path declares on it holds for each of them.

        Raises:
          ModelCorruptionError: if the type and its parents declare no
            valid source node types, or the declared types share no
            ancestor
        """
        common_type = self.get_lowest_valid_source_node_types_ancestor()
        if common_type is None:
            raise te.ModelCorruptionError(
                "{0} cannot resolve SOURCE: it declares no valid_source_node_types "
                "with a common ancestor".format(self.name))
        return common_type

    def TARGET(self) -> Any:
        """Return the node type for the entity referred to by TARGET in
        this relationship type: the lowest common ancestor of its valid
        target node types, as for SOURCE.

        Raises:
          ModelCorruptionError: if the type and its parents declare no
            valid target node types, or the declared types share no
            ancestor
        """
        common_type = self.get_lowest_valid_target_node_types_ancestor()
        if common_type is None:
            raise te.ModelCorruptionError(
                "{0} cannot resolve TARGET: it declares no valid_target_node_types "
                "with a common ancestor".format(self.name))
        return common_type

    def get_implementation_artifact(self, artifact_name: str) -> Any:
        """An operation implementation names an artifact of the node type or
        node template that contains the operation (TOSCA 2.0 §11.8). No node
        contains an operation of a relationship type, so its implementation
        is an inline artifact definition and a name refers to nothing.

        Raises:
          KeyError: always
        """
        raise KeyError("'{0}': no node contains an operation of relationship type "
                       "'{1}'".format(artifact_name, self.name))

    def get_artifact(self, artifact_name: Any) -> Any:
        """Return the artifact a path through SOURCE or TARGET names, such
        as [SOURCE, <artifact>] from a $get_artifact path [SELF, SOURCE,
        <artifact>]: an artifact of the lowest common ancestor of the type's
        valid source or target node types, which must declare it. A
        relationship defines no artifacts (TOSCA 2.0 §7.3, §7.4), so a bare
        name is refused.

        Raises:
          KeyError: when the name is bare, the path passes through anything
            but SOURCE or TARGET, the type declares no valid node types for
            the end the path reaches, or that end declares no such artifact
        """
        try:
            path = ToscaPath(artifact_name)
        except TypeError:
            raise KeyError("'{0}': a relationship type holds no artifacts".format(artifact_name))
        if path.entity not in ('SOURCE', 'TARGET'):
            raise KeyError("'{0}': a relationship's artifact path passes through SOURCE or "
                           "TARGET".format(artifact_name))
        try:
            end = self.SOURCE() if path.entity == 'SOURCE' else self.TARGET()
        except te.ModelCorruptionError as e:
            raise KeyError(str(e))
        return end.get_artifact(path.sub_entity)


    def get_attribute_or_property_declaration(self, attr_or_prop: str, value_name: str | ToscaPath) -> Any:
        """Return the declaration for the property or attribute specified in
        'value_name' (where the 'attr_or_prop' flag specifies whether
        to look up a property declaration or an attribute
        declaration). Relationship types must check if 'value_name' is
        a TOSCA Path expression that specifies target capabilities or
        source or target nodes.

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
            # Does the path reference a target node type?
            if path.entity == 'CAPABILITY':
                # Find lowest common ancestor for valid target capability types.
                common_type = self.get_lowest_valid_capability_types_ancestor()
                if not common_type:
                    logger.error("%s: no common ancestor for list of valid capability types", self.name)
                    raise KeyError("No common ancestor type for list of valid capability types")
                return common_type.get_attribute_or_property_declaration(attr_or_prop, path.sub_entity)
            # Does the path reference a target node type?
            elif path.entity == 'TARGET':
                # Find lowest common ancestor for valid target node types.
                common_type = self.get_lowest_valid_target_node_types_ancestor()
                if not common_type:
                    logger.error("%s: no common ancestor for list of valid target node types", self.name)
                    raise KeyError("No common ancestor type for list of valid target node types")
                return common_type.get_attribute_or_property_declaration(attr_or_prop, path.sub_entity)
            # Does the path reference a source node type?
            elif path.entity == 'SOURCE':
                # Find lowest common ancestor for valid source node types.
                common_type = self.get_lowest_valid_source_node_types_ancestor()
                if not common_type:
                    logger.error("%s: no common ancestor for list of valid source node types", self.name)
                    raise KeyError("No common ancestor type for list of valid source node types")
                return common_type.get_attribute_or_property_declaration(attr_or_prop, path.sub_entity)
            else:
                # Not a TOSCA Path keyword. Fall through
                pass
            
        except TypeError:
            # Not a ToscaPath. 
            pass
            
        # 'value_name' is not a TOSCA Path expression, or does not
        # reference a node or capability. Just delegate to our base
        # class.
        return super(ToscaRelationshipType, self).get_attribute_or_property_declaration(attr_or_prop, value_name)
