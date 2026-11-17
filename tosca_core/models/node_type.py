"""
Module definining Tosca Node Type entity
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

# SQL Alchemy support
from sqlalchemy.orm.collections import attribute_mapped_collection
from sqlalchemy.ext.orderinglist import ordering_list

# Exception support
import tosca_core.models.exceptions as te

# Path
from tosca_core.models.path import ToscaPath, split_requirement_step

# Cached lookups for TOSCA built-in data types
from tosca_core.models import builtin_types

# Type from which this type derives
import tosca_core.models.managed_type

# Types used in relationships
import tosca_core.models.property_declaration
import tosca_core.models.relationship_declaration
import tosca_core.models.capability_declaration


class ToscaNodeType(tosca_core.models.managed_type.ToscaManagedType):
    """The ToscaNodeType represents a named node type that can be used
    for declaring Tosca node templates in Tosca topologies.
    """

    ################################################################################
    # Polymorphic mapping
    ################################################################################

    __mapper_args__ = {
        'polymorphic_identity':'node',
    }

    ################################################################################
    # Relationships
    ################################################################################

    artifacts =   db.relationship('ToscaArtifact',
                                  collection_class=attribute_mapped_collection('name'),
                                  foreign_keys='ToscaArtifact._containing_type_id',
                                  cascade='all',
                                  back_populates='_containing_type')
    requirements = db.relationship('ToscaRelationshipDeclaration',
                                   collection_class=ordering_list('position'),
                                   order_by='ToscaRelationshipDeclaration.position',      
                                   foreign_keys='ToscaRelationshipDeclaration._containing_type_id',
                                   cascade='all',
                                   back_populates='_containing_type')
    capabilities = db.relationship('ToscaCapabilityDeclaration',
                                   collection_class=attribute_mapped_collection('name'),
                                   foreign_keys='ToscaCapabilityDeclaration._containing_type_id',
                                   cascade='all',
                                   back_populates='_containing_type')

    ################################################################################
    # Constructor
    ################################################################################

    def __init__(self,
                 requirements: Optional[list[Any]] = None,
                 capabilities: Optional[dict[str, Any]] = None,
                 artifacts: Optional[dict[str, Any]] = None,
                 **kwargs: Any
    ) -> None:
        """Instantiate a new Tosca Node Type instance"""

        # First, call superclass constructor
        super(ToscaNodeType, self).__init__(**kwargs)

        # ToscNodeType-specific initialization
        if requirements: self.requirements = requirements
        if capabilities: self.capabilities = capabilities
        if artifacts: self.artifacts = artifacts


    ################################################################################
    # Sub-entity retrieval functions. Sub-entities are retrieved from
    # this type as well as from any parent types(s)
    ################################################################################

    def get_artifacts(self) -> dict[str, Any]:
        return self.get_entity_declarations('artifacts')

    def get_implementation_artifact(self, artifact_name: str) -> Any:
        """Return the artifact an operation implementation names (TOSCA 2.0
        §11.8): an artifact of the node type or node template that contains
        the operation, here this one. This is not $get_artifact, which
        follows a path (get_artifact).

        Raises:
          KeyError: when no such artifact is found
        """
        return self.get_artifact(artifact_name)

    def get_artifact(self, artifact_name: Any) -> Any:
        """Return the artifact 'artifact_name' names: one of this node's, or,
        for a path [RELATIONSHIP, <requirement>, <index>, ...], the one the
        rest of the path reaches from that requirement's relationship, such
        as [RELATIONSHIP, host, TARGET, <artifact>]. With no index, ALL is
        implied, which reaches one relationship where the requirement's count
        range admits one, and several where it admits more: a $get_artifact
        returns one location, a string, so a path that reaches several is
        refused, as the count range decides and not how many are bound.

        Raises:
          KeyError: when the artifact is not found, or the path passes
            through anything but RELATIONSHIP
          ValueError: when the path reaches several relationships, or the
            index is a function
        """
        try:
            path = ToscaPath(artifact_name)
        except TypeError:
            path = None
        if path is None:
            return self.get_entity_declaration('artifacts', artifact_name)
        if path.entity != 'RELATIONSHIP':
            raise KeyError("'{0}': a node's artifact path passes through "
                           "RELATIONSHIP".format(artifact_name))
        name, index, rest = split_requirement_step(path.sub_entity)
        requirement_declaration = self.get_requirement_declaration(name)
        if index is None and requirement_declaration.supports_multiple():
            raise ValueError("'{0}': with no index, ALL is implied, and '{1}' admits several "
                             "relationships, so the path reaches several artifacts where "
                             "$get_artifact returns one: index one".format(artifact_name, name))
        return requirement_declaration.get_artifact(rest)


    def get_capability_declarations(self) -> dict[str, Any]:
        return self.get_entity_declarations('capabilities')

    def get_capability_declaration(self, capability_name: str) -> Any:
        return self.get_entity_declaration('capabilities', capability_name)

    def get_capability_to_augment(self, capability_name: str) -> Any:
        return self.get_entity_declaration_to_augment('capabilities',
                                                      capability_name)

    def get_capability_declarations_of_type(self, capability_type: Any) -> dict[str, Any]:
        return self.get_entity_declarations_of_type('capabilities',
                                                    capability_type)


    def get_requirement_declarations(self) -> list[Any]:
        """Get requirement declarations for type_entity. This operation
        merges with declarations retrieved from the parent type(s)
        """
        # First, get requirement declarations of parent type
        try:
            requirement_declarations = self.parent.get_requirement_declarations()
        except (AttributeError, te.TypeNotFound):
            # No parent type found or parent type doesn't
            # exist. Start with empty list.
            requirement_declarations = list()

        # Append list of requirements for our type. However, if this
        # type refines any requirements defined by the parent, replace
        # the parent's requirements with those requirements instead.
        try:
            requirements = self.requirements
            declarations = [ declaration.name for declaration in requirement_declarations ]
            for requirement in requirements:
                try:
                    index = declarations.index(requirement.name)
                    requirement_declarations[index] = requirement
                except ValueError:
                    # Item to replace is not in list
                    requirement_declarations.append(requirement)
        except AttributeError:
            # This type does not define requirements
            pass

        return requirement_declarations

    def get_requirement_declaration(self, requirement_name: str) -> Any:
        """Get requirement declaration by name for type_entity. This operation
        tries to get the declaration from the parent type(s) if it's
        not found in this type entity
        """
        # Do we have this requirement?
        if self.requirements:
            for requirement_declaration in self.requirements:
                if requirement_declaration.name == requirement_name:
                    return requirement_declaration

        # Node type doesn't have requirements, or requirement not
        # found. Check parent type.
        try:
            return self.parent.get_requirement_declaration(requirement_name)
        except (AttributeError, te.TypeNotFound, te.CircularInheritance):
            # This type entity doesn't have a parent class or parent
            # type doesn't exist.
            raise KeyError("Requirement {0} not found".format(requirement_name))

    def get_requirement_to_augment(self, requirement_name: str) -> Any:
        """get requirement to augment.

        This is a requirement declaration in a base class that is
        being augmented in this type entity

        Returns:
          ToscaRelationshipDeclaration for the requested requirement
            declaration

        Raises:
          KeyError: when no requirement declared with this name in any of
            the base classes
        """
        try:
            parent_type_entity = self.parent
        except (AttributeError, te.TypeNotFound):
            # No parent type or parent type doesn't exist
            raise KeyError("Requirement <{0}> not found".format(requirement_name))

        return parent_type_entity.get_requirement_declaration(requirement_name)

    def replace_requirement(self, requirement: Any, new_requirement: Any) -> None:
        """Replace a named requirement with a new requirement

        Returns:
          None

        Raises:
          KeyError: when no requirement declared with this name
        """
        # Do we have this requirement?
        try:
            requirements = self.requirements
            requirement_index = requirements.index(requirement)
            requirements[requirement_index] = new_requirement
        except (AttributeError, ValueError, TypeError):
            # This type entity doesn't have requirements or the named
            # requirement isn't found
            raise KeyError("Requirement {0} not found".format(requirement.name))


    def upgrade_tosca_path(self, tosca_path: str | list[str]) -> str | list[str]:
        """Upgrade the provided TOSCA Path to Version 2.0 syntax:

        - If the TOSCA Path references a capability, we insert the
          'CAPABILITY' keyword.
        - If the TOSCA Path references a relationship, we insert the
          'RELATIONSHIP' keyword.
        """
        try:
            # Is tosca_path a ToscaPath expression? 
            path = ToscaPath(tosca_path)
            try:
                # Is the entity specified in the path a requirement?
                # If so, propagate the 'get_attribute_or_property_declaration' call.
                requirement_declaration = self.get_requirement_declaration(path.entity)
                upgraded = [ 'RELATIONSHIP', path.entity ]
                upgraded.extend(requirement_declaration.propagate_upgrade_tosca_path(path.sub_entity))
                return upgraded
            except (AttributeError, KeyError):
                # We do not have a requirement with that name. Could
                # be a capability instead. If so, insert the
                # 'CAPABILITY' keyword.
                try:
                    capability_declaration = self.get_capability_declaration(path.entity)
                    upgraded = ['CAPABILITY']
                    upgraded.extend(tosca_path)
                    return upgraded
                except (AttributeError, KeyError):
                    # No capability with that name either.
                    pass
        except TypeError:
            # Not a ToscaPath. 
            pass

        # 'tosca_path' is not a TOSCA Path expression, or does not
        # reference a requirement or capability. Just delegate to our
        # base class.
        return super(ToscaNodeType, self).upgrade_tosca_path(tosca_path)


    def get_attribute_or_property_declaration(self, attr_or_prop: str, value_name: str | ToscaPath) -> Any:
        """Return the declaration for the property or attribute specified in
        'value_name' (where the 'attr_or_prop' flag specifies whether
        to look up a property declaration or an attribute
        declaration). Node types must check if 'value_name' is a TOSCA
        Path expression that specifies requirement or capabilities.

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

            # Does the path reference a relationship?
            if path.entity == 'RELATIONSHIP':

                # Find the named requirement. This will raise a
                # KeyError if the attribute or property is not found.
                try:
                    sub_entity = path.sub_entity
                    path = ToscaPath(sub_entity)
                    requirement_declaration = self.get_requirement_declaration(path.entity)
                except TypeError:
                    logger.error("%s: invalid requirement path %s", self.name, sub_entity)
                    raise KeyError(str(sub_entity))

                # Determine whether the remainder of the path
                # references a list of declarations or single
                # declaration.
                try:
                    # Check if sub_path references a single value or a list
                    sub_path = ToscaPath(path.sub_entity)
                    integer_type = builtin_types.get('integer')
                    declaration = integer_type.create_declaration(name='requirement_index')
                    try:
                        # Do we have an index that references single value?
                        index = declaration.validate_value(self, sub_path.entity)
                        use_list = False
                        path = sub_path
                    except Exception:
                        # Sub path entity is not an index.
                        if sub_path.entity == 'ALL':
                            # List of declarations
                            use_list = True
                            path = sub_path
                        else:
                            # No qualifying keyword. Use remainder of path
                            # as is and check count_range to decide
                            # whether to return a list or a single
                            # declaration.
                            use_list = requirement_declaration.supports_multiple()
                except TypeError:
                    # Not a TOSCA path. Use remainder of path as is
                    # and check count_range to decide whether to
                    # return a list or a single declaration.
                    use_list = requirement_declaration.supports_multiple()
                except Exception as e:
                    logger.error(str(e))
                # Get declaration for the rest of the path.
                value_declaration = requirement_declaration.get_attribute_or_property_declaration(
                    attr_or_prop, path.sub_entity)

                # Wrap inside list declaration if necessary.
                if use_list:
                    return tosca_core.models.property_declaration.as_list_declaration(
                        value_declaration, requirement_declaration.name, attr_or_prop)
                else:
                    return value_declaration

            # Does the path reference a capability?
            if path.entity == 'CAPABILITY':
                # Hand-off the 'get_attribute' or 'get_property' call
                # to the capability. This will raise a KeyError if the
                # attribute or property is not found.
                try:
                    sub_entity = path.sub_entity
                    path = ToscaPath(sub_entity)
                    capability_declaration = self.get_capability_declaration(path.entity)
                    return capability_declaration.get_attribute_or_property_declaration(
                        attr_or_prop, path.sub_entity)
                except TypeError:
                    logger.error("%s: invalid capability path %s", self.name, sub_entity)
                    raise KeyError(str(sub_entity))

        except TypeError:
            # Not a ToscaPath. 
            pass

        # 'value_name' is not a TOSCA Path expression, or does not
        # reference a requirement or capability. Just delegate to our
        # base class.
        return super(ToscaNodeType, self).get_attribute_or_property_declaration(attr_or_prop, value_name)


    ################################################################################
    # Create a declaration of this type
    ################################################################################

    def create_declaration(self, name: str = 'anonymous node') -> ToscaNodeDeclaration:
        """Synthesize a ToscaNodeDeclaration object for this
        node type

        Args:
          name(str): name for the node being declared

        Returns:
          ToscaNodeDeclaration: with the appropriate name and type. No
            other attributes are initialized.

        Raises:
          None
        """
        from tosca_core.models.node_declaration import ToscaNodeDeclaration
        node_declaration = ToscaNodeDeclaration(name=name, type=self.name)
        node_declaration.type_entity = self
        return node_declaration


    ################################################################################
    # Other stuff that needs to be organized. 
    ################################################################################

    def get_prereq_type_names(self) -> list[str]:
        """Return list of prerequisite entity names of the same type on which
        this entity depends. Node Type entities return the name of
        types on which they have requirements
        """

        prereq_type_names = super(ToscaNodeType, self).get_prereq_type_names()
        if self.requirements:
            for requirement_declaration in self.requirements:
                try:
                    # Is there a dependency on another node type?
                    node_type = requirement_declaration._node
                    prereq_type_names.append(node_type)
                except AttributeError:
                    # This requirement_declaration doesn't include a
                    # node type
                    pass
        return prereq_type_names


    ################################################################################
    # Query functions
    ################################################################################

    def query_nodes(self) -> list[Any]:
        """Return list of nodes of this type. This will return nodes of
        derived types as well.
        """

        # Recursively find nodes for our child node types
        target_nodes = list()
        for child in self.children:
            target_nodes.extend(child.query_nodes())
            
        # Next, find our own nodes
        try:
            nodes = self.nodes
            target_nodes.extend(nodes)
        except Exception as e:
            logger.error("Error finding target node candidates: %s", str(e))

        # All done
        return target_nodes

    
