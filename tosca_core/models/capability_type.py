"""
Module definining Tosca Capability Type entity
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

# Types on which this type depends
import tosca_core.models.type

# Exception support
import tosca_core.models.exceptions as te


class ToscaCapabilityType(tosca_core.models.type.ToscaType):
    """The ToscaCapabilityType represents a new named capability type
    that can be used for declaring Tosca capabilities in other type
    definitions.
    """

    ################################################################################
    # Polymorphic mapping
    ################################################################################

    __mapper_args__ = {
        'polymorphic_identity':'capability',
    }

    ################################################################################
    # Fields
    #
    # Optional fields start with '_' and have corresponding getters
    # (and optionally setters) to ensure that retrieving fields
    # consistently raises an AttributeError when not set.  Note that
    # 'nullable' defaults to True, but we explicitly set the
    # 'nullable' flag for clarity.
    ################################################################################

    # valid source node types are defined in the base ToscaType class
    # since it is also used in ToscaRelationshipType

    _valid_relationship_types = db.Column(db.PickleType, nullable=True)
    @property
    def valid_relationship_types(self) -> list[str]:
        if self._valid_relationship_types == None:
            raise AttributeError("'{0}' does not have 'valid_relationship_types'".format(self.name))
        return self._valid_relationship_types


    ################################################################################
    # Constructor
    ################################################################################

    def __init__(self,
                 valid_source_node_types: Optional[list[str]] = None,
                 valid_relationship_types: Optional[list[str]] = None,
                 **kwargs: Any
    ) -> None:
        # First, call superclass constructor
        super(ToscaCapabilityType, self).__init__(**kwargs)

        # ToscaCapabilityType-specific initialization
        if valid_source_node_types != None: self._valid_source_node_types = valid_source_node_types
        if valid_relationship_types != None : self._valid_relationship_types = valid_relationship_types


    ################################################################################
    # Create a declaration of this type
    ################################################################################

    def create_declaration(self, name: str = 'anonymous capability') -> ToscaCapabilityDeclaration:
        """Synthesize a ToscaCapabilityDeclaration object for this
        capability type

        Returns:
          ToscaCapabilityDeclaration: with the appropriate name and type. No
            other attributes are initialized.

        Raises:
          None
        """
        from tosca_core.models.capability_declaration import ToscaCapabilityDeclaration
        capability_declaration = ToscaCapabilityDeclaration(name=name, type=self.name)
        capability_declaration.type_entity = self
        return capability_declaration


    ################################################################################
    # Other stuff that needs to be organized. 
    ################################################################################

    def is_valid_source_node_type(self, node_type: Any) -> bool:
        """Is the specified node type entity a valid source for this
        capability type?

        Args:
          node_type(ToscaNodeType): node type for which to check if
            this capability is a valid source

        Raises:
          None
        """
        # Do we restrict source node types?
        try:
            # Is this node type (or one of its base classes) in the
            # list of valid source node types?
            for valid_source_node in self.valid_source_node_types:
                valid_source_node_type = self.profile.get_node_type(valid_source_node)
                if node_type.has_type(valid_source_node_type):
                    return True
                
             # Not a valid source
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
                # have a parent who could do so either. All types are
                # valid.
                return True


    def is_valid_relationship_type(self, relationship_type: Any) -> bool:
        """Is the specified relationship type a valid incoming relationship
        for this capability type?

        Args:
          relationship_type(ToscaRelationshipType): relationship type
            for which to check if is is valid for this capability type

        Raises:
          None
        """
        # Do we restrict relationship types?
        try:
            # Is this relationship type (or one of its base classes)
            # in the list of valid relationship types?
            for valid_relationship in self.valid_relationship_types:
                valid_relationship_type = self.profile.get_relationship_type(valid_relationship)
                if relationship_type.has_type(valid_relationship_type):
                    return True
                
             # Not a valid source
            return False
             
        except (AttributeError, TypeError):
            # We don't restrict relationship types (since we don't
            # have a valid_relationship_types attribute or the
            # valid_relationship_types attribute is None). Does our
            # parent class?
            try:
                return self.parent.is_valid_relationship_type(relationship_type)
            except (AttributeError, te.CircularInheritance):
                # We don't restrict relationship types, and we don't
                # have a parent who could do so either. All types are
                # valid.
                return True


    def get_lowest_valid_relationship_types_ancestor(self) -> Optional[Any]:
        """Get the lowest common ancestor of the types in the valid relationship
        types list. Check parent type if valid relationship types not
        defined locally.

        Returns:
          (ToscaRelationshipType): lowest valid relationship types ancestor
          None: if no common ancestor for the valid relationship types
        Raises:
          None
        """
        # Do we restrict relationship types?
        try:
            valid_relationship_types = self.valid_relationship_types
        except (AttributeError, TypeError):
            # We don't restrict relationship types.  Does our parent
            # class?
            try:
                return self.parent.get_lowest_valid_relationship_types_ancestor()
            except (AttributeError, te.CircularInheritance):
                # No parent.
                return None

        # Start with the first type in the list
        from tosca_core.models.type import lowest_common_ancestor
        try:
            common_type = self.profile.get_relationship_type(valid_relationship_types[0])
        except Exception as e:
            logger.error("Error getting common valid relationship type: %s", str(e))
            return None

        # Then, iterate through the rest of the list
        for next_type_name in valid_relationship_types[1:]:
            try:
                next_type = self.profile.get_relationship_type(next_type_name)
            except Exception as e:
                logger.error("Error getting next valid relationship type: %s", str(e))
                return None
            common_type = lowest_common_ancestor(common_type, next_type)
            if not common_type: return None
                
        # All done
        return common_type


    def get_lowest_valid_source_node_types_ancestor(self) -> Optional[Any]:
        """Get the lowest common ancestor of the types in the valid source
        node types list. Check parent type if valid source node types
        not defined locally.

        Returns:
          (ToscaNodeType): lowest valid node type types ancestor
          None: if no common ancestor for the valid relationship types
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
            logger.error("Error getting common valid source node type: %s", str(e))
            return None

        # Then, iterate through the rest of the list
        for next_type_name in valid_source_node_types[1:]:
            try:
                next_type = self.profile.get_node_type(next_type_name)
            except Exception as e:
                logger.error("Error getting next valid source node type: %s", str(e))
                return None
            common_type = lowest_common_ancestor(common_type, next_type)
            if not common_type: return None
                
        # All done
        return common_type


    def get_lowest_source_node_types_ancestor_from_valid_relationships(self) -> Optional[Any]:
        """Get the lowest common ancestor of the valid source node types for
        each of the relationship types in the valid relationship types
        list. Check our parent type entity if valid relationship types are
        not defined locally.

        Returns:
          (ToscaNodeType): lowest valid source node types ancestor
          None: if no common ancestor for the valid relationship types
        Raises:
          None
        """
        # Do we restrict relationship types?
        try:
            valid_relationship_types = self.valid_relationship_types
        except (AttributeError, TypeError):
            # We don't restrict relationship types.  Does our parent
            # class?
            try:
                return self.parent.get_lowest_source_node_types_ancestor_from_valid_relationships()
            except (AttributeError, te.CircularInheritance):
                # No parent.
                return None

        # Iterate through the list of valid relationship types
        from tosca_core.models.type import lowest_common_ancestor
        common_type = None
        for relationship_type_name in valid_relationship_types:
            try:
                relationship_type = self.profile.get_relationship_type(relationship_type_name)
                node_type = relationship_type.get_lowest_valid_source_node_types_ancestor()
            except Exception as e:
                logger.error("Error getting valid relationship type: %s", str(e))
                return None
            common_type = lowest_common_ancestor(common_type, node_type)
            if not common_type: return None
                
        # All done
        return common_type


    ################################################################################
    # Query functions
    ################################################################################

    def query_nodes(self) -> list[Any]:
        """Return list of nodes that contain capabilities of this type. This
        method will return nodes with capabilities of derived
        capability types as well.

        returns: 
           (possibly empty) list of ToscaNode

        raises:
           None
        """

        # Recursively find nodes for child capability types
        target_nodes = list()
        for child in self.children:
            target_nodes.extend(child.query_nodes())
            
        # Next, find our own nodes
        logger.debug("Query nodes with capabilities of type '%s'", self.name)
        try:
            capabilities = self.capabilities
            logger.debug("Found %d capabilities of type '%s'", len(capabilities), self.name)
        except Exception as e:
            logger.error("Error finding target capability candidates: %s", str(e))
            return target_nodes
        
        # Return nodes that contain these capabilities
        for capability in capabilities:
            target_nodes.append(capability.containing_instance)

        # All done
        return target_nodes

    
