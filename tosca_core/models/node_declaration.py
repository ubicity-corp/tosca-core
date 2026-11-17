"""
Module definining Tosca Node Declaration entity
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
import tosca_core.models.property_declaration
import tosca_core.models.managed_declaration
from tosca_core.models.path import ToscaPath, split_requirement_step
from tosca_core.models import builtin_types


class ToscaNodeDeclaration(tosca_core.models.managed_declaration.ToscaManagedDeclaration):
    """A ToscaNodeDeclaration declares the presence of a Tosca node
    template. Since Tosca topologies never declare node templates
    (node templates are initialized without having been declared
    first), this object is only ever created synthetically for
    purposes of node template validation.
    """

    ################################################################################
    # Polymorphic mapping
    ################################################################################

    __mapper_args__ = {
        'polymorphic_identity':'node',
    }


    ################################################################################
    # Constructor
    ################################################################################

    def __init__(self,
                 **kwargs: Any
    ) -> None:
        # First, call superclass constructor
        super(ToscaNodeDeclaration, self).__init__(**kwargs)
        # ToscaNodeDeclaration-specific initialization


    ################################################################################
    # Sub-entity retrieval functions. Sub-entities are retrieved from
    # this declaration as well as from the types
    ################################################################################

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
        """get requirement declarations for a node declaration"""

        # Get requirement declarations from type enity
        requirement_declarations = self.type_entity.get_requirement_declarations()
        return requirement_declarations

    def get_requirement_declaration(self, requirement_name: str) -> Any:
        """get requirement declaration by name for a node
        declaration"""
        return self.type_entity.get_requirement_declaration(requirement_name)


    def upgrade_tosca_path(self, tosca_path: Any) -> list[Any]:
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
        return super(ToscaNodeDeclaration, self).upgrade_tosca_path(tosca_path)


    def get_attribute_or_property_declaration(self, attr_or_prop: str, value_name: Any) -> Any:
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
                        # Sub path is not an index
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

                # Get declaration for the rest of the path.
                value_declaration = requirement_declaration.get_attribute_or_property_declaration(
                    attr_or_prop, path.sub_entity)

                # List of declarations or single declaration?
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
        return super(ToscaNodeDeclaration, self).get_attribute_or_property_declaration(
            attr_or_prop, value_name)


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
            # Declarations don't have artifacts. Get artifacts from node
            # type.
            return self.type_entity.get_artifact(artifact_name)
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
