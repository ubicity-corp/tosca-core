"""
Module definining Tosca Capability Declaration entity
"""
from __future__ import annotations

__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2014-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Type hints
from typing import Any, Optional

# Logging suport
import logging
logger: logging.Logger = logging.getLogger(__name__)

# Database support
from tosca_core import db

# Types on which this declaration depends
import tosca_core.models.declaration
import tosca_core.models.property_declaration
from tosca_core.models.path import ToscaPath
from tosca_core.models import builtin_types

# For finding common base types
from tosca_core.models.type import lowest_common_ancestor

class ToscaCapabilityDeclaration(tosca_core.models.declaration.ToscaDeclaration):
    """A ToscaCapabilityDeclaration declares the presence of a named
    capability of a given capability type. The name and type of the
    declared capability are stored in the ToscaDeclaration base class.
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

    _valid_source_node_types = db.Column(db.PickleType, nullable=True)
    @property
    def valid_source_node_types(self) -> list[Any]:
        if self._valid_source_node_types == None:
            raise AttributeError("'{0}' does not have 'valid_source_node_types'".format(self.name))
        return self._valid_source_node_types

    _valid_relationship_types = db.Column(db.PickleType, nullable=True)
    @property
    def valid_relationship_types(self) -> list[Any]:
        if self._valid_relationship_types == None:
            raise AttributeError("'{0}' does not have 'valid_relationship_types'".format(self.name))
        return self._valid_relationship_types

    ################################################################################
    # Model navigation
    ################################################################################

    def augments(self) -> ToscaCapabilityDeclaration:
        """Return the capability declaration for which this declaration is an
        augmentation.

        Returns:
          ToscaCapabilityDeclaration: declaration for which we are an
            augmentation

        Raises:
          KeyError: if we are not an augmentation
        """

        # Find the augmentation
        if self._containing_type:
            # This capability declaration is inside a node type
            # definition. Get the declaration for which we are an
            # augmentation from the containing node type.
            return self._containing_type.get_entity_declaration_to_augment(
                'capabilities', self.name)
        elif self._containing_declaration:
            # This capablity declaration is inside another
            # declaration. Get the declaration for which we are an
            # augmentation from the containing declaration.
            return self._containing_declaration.get_entity_declaration_to_augment(
                'capabilities', self.name)
        else:
            # The only declarations that don't have a containing type
            # nor a containing declaration are synthetically-created
            # declarations (using the create_declaration
            # function). However, these declarations are never augmentations.
            raise KeyError("capability declaration '{}' is not an augmentation".format(self.name))


    ################################################################################
    # Constructor
    ################################################################################

    def __init__(self,
                 valid_source_node_types: Optional[list[Any]] = None,
                 valid_relationship_types: Optional[list[Any]] = None,
                 occurrences: Optional[Any] = None,
                 **kwargs: Any
    ) -> None:
        # First, call superclass constructor
        super(ToscaCapabilityDeclaration, self).__init__(**kwargs)

        # ToscaCapabilityDeclaration-specific initialization
        if valid_source_node_types != None: self._valid_source_node_types = valid_source_node_types
        if valid_relationship_types != None: self._valid_relationship_types = valid_relationship_types

        # Ubicity ignores 'occurrences' in capability definitions. 


    ################################################################################
    # Sub-entity retrieval functions. Sub-entities are retrieved from
    # this type as well as from any parent types(s)
    ################################################################################

    def get_attribute_or_property_declaration(self, attr_or_prop: str, value_name: Any) -> Any:
        """Return the declaration for the property or attribute specified in
        'value_name' (where the 'attr_or_prop' flag specifies whether
        to look up a property declaration or an attribute
        declaration). Capability declarations must check if
        'value_name' is a TOSCA Path expression that specifies an
        incoming relationships.

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

            # Does the path reference an incoming relationship?
            if path.entity == 'RELATIONSHIP':
                # Hand-off the 'get_attribute' or 'get_property' call
                # to the incoming relationship.  First, determine
                # whether the remainder of the path references a list
                # of declarations or a single declaration.
                try:
                    # Check if sub_path references a single value or a list
                    sub_entity = path.sub_entity
                    sub_path = ToscaPath(sub_entity)
                    integer_type = builtin_types.get('integer')
                    declaration = integer_type.create_declaration(name='requirement_index')
                    try:
                        # Do we have an index that references a single
                        # value?
                        index = declaration.validate_value(self, sub_path.entity)
                        use_list = False
                        sub_entity = sub_path.sub_entity
                    except Exception:
                        # Sub path is not an index
                        use_list = True
                except TypeError:
                    # Not a TOSCA path, which means a property value
                    # from the relationship is accessed. This will
                    # always return a list.
                    use_list = True

                # We either traverse straight to the source node, or
                # we retrieve a value from the incoming
                # relationship. Figure out which one it is.
                try:
                    sub_path = ToscaPath(sub_entity)
                    if sub_path.entity == 'SOURCE':
                        jump_to_source = True
                        sub_entity = sub_path.sub_entity
                    else:
                        jump_to_source = False
                except TypeError:
                    # Not a TOSCA Path.
                    jump_to_source = False

                # Find the appropriate type to query next
                if jump_to_source:
                    # Get the remainder of the path from the source
                    # node types
                    next_type = self.get_lowest_common_source_node_type()
                    if not next_type:
                        logger.error("%s: no common source types defined for %s", self.name, str(value_name))
                        raise KeyError(str(value_name))

                else:
                    # Get the value from the incoming relationship
                    # type
                    next_type = self.get_lowest_valid_relationship_types_ancestor()
                    if not next_type:
                        logger.error("%s: no common incoming relationship types defined for %s", self.name, str(value_name))
                        raise KeyError(str(value_name))

                # Proceed
                try:
                    value_declaration = next_type.get_attribute_or_property_declaration(
                        attr_or_prop, sub_entity)
                except Exception as e:
                    logger.error("OOPS: %s", str(e))
                    raise

                # List of declarations or single declaration?
                if use_list:
                    return tosca_core.models.property_declaration.as_list_declaration(
                        value_declaration, next_type.name, attr_or_prop)
                else:
                    return value_declaration

        except TypeError:
            # Not a ToscaPath. 
            pass

        # 'value_name' is not a TOSCA Path expression, or does not
        # reference an incoming relationship. Just delegate to our
        # base class.
        return super(ToscaCapabilityDeclaration, self).get_attribute_or_property_declaration(
            attr_or_prop, value_name)


    ################################################################################
    # Create a template for this declaration
    ################################################################################

    def create_template(self) -> Any:
        """Create a capability template from this declaration"""
        import tosca_core.models.capability_template
        capability = tosca_core.models.capability_template.ToscaCapabilityTemplate()
        capability.name = self.name
        capability.declaration = self
        return capability
    

    ################################################################################
    # Sub-Entity Refinement
    ################################################################################

    def merge_augmented_declaration(self, capability_declaration: ToscaCapabilityDeclaration) -> None:
        """Override a capability declaration with attributes from a
        second capability"""

        # First, call superclass augment method
        super(ToscaCapabilityDeclaration, self).merge_augmented_declaration(capability_declaration)

        # Override 'valid_source_node_types' attribute
        self.merge_augmented_field('_valid_source_node_types', capability_declaration)
        self.merge_augmented_field('_valid_relationship_types', capability_declaration)


    ################################################################################
    # Other stuff that needs to be organized. 
    ################################################################################

    def is_valid_source_node_type(self, node_type: Any) -> bool:
        """Is the specified node type a valid source node type for this
        capability declaration?

        Args:
          node_type(ToscaNodeType): node type for which to check if it
            is a valid source node type for this capability

        Raises:
          None
        """

        # Do we restrict source node types?
        try:
            valid_source_node_types = self.valid_source_node_types
            # Is this node type (or one of its base classes) in the list
            # of valid source node types?
            for valid_source in valid_source_node_types:
                valid_source_type = self.profile.get_node_type(valid_source)
                if node_type.has_type(valid_source_type):
                    return True
            # Not a valid node type
            logger.info("No source node types match")
            return False
             
        except AttributeError:
            # We don't restrict source types. Delegate checking to our
            # type.
            return self.type_entity.is_valid_source_node_type(node_type)


    def is_valid_relationship_type(self, relationship_type: Any) -> bool:
        """Is the specified relationship type a valid relationship type for
        this capability declaration?

        Args:
          relationship_type(ToscaRelationshipType): relationship type
            for which to check if it is a valid relationship type for
            this capability.

        Raises:
          None
        """
        # Do we restrict relationship types?
        try:
            valid_relationship_types = self.valid_relationship_types
            # Is this relationship type (or one of its base classes) in the list
            # of valid relationship types?
            for valid_source in valid_relationship_types:
                valid_source_type = self.profile.get_relationship_type(valid_source)
                if relationship_type.has_type(valid_source_type):
                    return True
            # Not a valid relationship
            logger.info("No relationship types match")
            return False
             
        except AttributeError:
            # We don't restrict relationship types. Delegate checking
            # to our type.
            return self.type_entity.is_valid_relationship_type(relationship_type)


    def get_lowest_valid_relationship_types_ancestor(self) -> Optional[Any]:
        """Get the lowest common ancestor of the types in the valid
        relationship types list. Check our type entity if valid
        relationship types not defined locally.

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
            # We don't restrict relationship types. Delegate to our type
            # entity
            return self.type_entity.get_lowest_valid_relationship_types_ancestor()

        # Get common ancestor. Start with the first type in the list
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
            # We don't restrict relationship types. Delegate to our type
            # entity
            try:
                return self.type_entity.get_lowest_valid_source_node_types_ancestor()
            except Exception as e:
                logger.error(str(e))
                return None

        # Start with the first type in the list
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
        list. Check our type entity if valid relationship types are
        not defined locally.
        """
        # Do we restrict relationship types?
        try:
            valid_relationship_types = self.valid_relationship_types
        except (AttributeError, TypeError):
            # We don't restrict relationship types. Delegate to our type
            # entity
            return self.type_entity.get_lowest_source_node_types_ancestor_from_valid_relationships()

        # Iterate through valid relationship types
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


    def get_lowest_common_source_node_type(self) -> Optional[Any]:
        """Get the lowest common ancestor of all the valid source node
        types. This includes the types in the valid source types list
        as well as the types defined in the valid source node types
        lists for each of the relationship types in the valid
        relationship types list.  Check our type entity if valid types
        not defined locally.

        Returns:
          (ToscaRelationshipType): lowest valid relationship types ancestor
          None: if no common ancestor for the valid relationship types
        Raises:
          None
        """
        # Get valid source node types
        common_source_node_type = self.get_lowest_valid_source_node_types_ancestor()
        common_relationship_source_node_type = self.get_lowest_source_node_types_ancestor_from_valid_relationships()
        return lowest_common_ancestor(common_source_node_type,
                                      common_relationship_source_node_type)
        


    
