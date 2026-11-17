"""
Module definining Tosca Managed Declaration Entities
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

# Types on which this declaration depends
import tosca_core.models.declaration 


class ToscaManagedDeclaration(tosca_core.models.declaration.ToscaDeclaration):
    """The Tosca managed declaration class is the base class for
    declarations of Tosca managed declarations. In theory, this
    includes declarations of Tosca node templates as well as Tosca
    relationship templates. In practice, however, the only Tosca
    entity that declares managed instances is the ToscaRequirement: it
    can declare a relationship template inline.  Tosca topologies
    never declare node templates or relationship templates
    directly. They just define them inline.
    """

    ################################################################################
    # Polymorphic mapping
    ################################################################################

    __mapper_args__ = {
        'polymorphic_identity':'managed',
    }

    ################################################################################
    # Relationships
    ################################################################################

    interfaces =  db.relationship('ToscaInterfaceDeclaration',
                                  collection_class=attribute_mapped_collection('name'),
                                  foreign_keys='ToscaInterfaceDeclaration._containing_declaration_id',
                                  cascade='all',
                                  back_populates='_containing_declaration',
                                  overlaps='_contained_declarations')


    ################################################################################
    # Constructor
    ################################################################################

    def __init__(self,
                 interfaces: Optional[dict[str, Any]] = None,
                 **kwargs: Any
    ) -> None:
        # First, call superclass constructor
        super(ToscaManagedDeclaration, self).__init__(**kwargs)

        # ToscaManagedDeclaration-specific initialization
        if interfaces: self.interfaces = interfaces


    ################################################################################
    # Implementation of reserved keywords
    ################################################################################

    def SELF(self) -> ToscaManagedDeclaration:
        """Return the declaration for the entity referred to by SELF for this
        declaration. SELF refers to nodes or relationships only, so we
        just return ourselves.

        Returns:
          ToscaManagedDeclaration
        """
        return self


    ################################################################################
    # Sub-entity retrieval functions. Sub-entities are retrieved from
    # this declaration as well as from its types
    ################################################################################

    def get_interface_declarations(self) -> dict[str, Any]:
        return self.get_entity_declarations('interfaces')


    def get_interface_declaration(self, interface_name: str) -> Any:
        return self.get_entity_declaration('interfaces', interface_name)


    def get_interface_to_augment(self, interface_name: str) -> Any:
        return self.get_entity_declaration_to_augment('interfaces',
                                                      interface_name)


    ################################################################################
    # Sub-Entity Refinement
    ################################################################################

    def merge_augmented_declaration(self, managed_declaration: Any) -> None:
        """Augment a managed declaration with attributes from a
        second managed declaration"""

        # First, call superclass augment method
        super(ToscaManagedDeclaration, self).merge_augmented_declaration(managed_declaration)

        # Merge interface declarations
        self.merge_augmented_interfaces(managed_declaration)


    def merge_augmented_interfaces(self, managed_declaration: Any) -> None:
        # First, complete each individual interface augmentation
        try:
            for interface_name, interface_declaration in self.interfaces.items():
                # Find the corresponding interface declaration to
                # augment and extend.
                try:
                    augmented_interface = managed_declaration.get_interface_declaration(interface_name)
                    interface_declaration.merge_augmented_declaration(augmented_interface)
                except Exception as e:
                    # Something went wrong
                    logger.error("%s: unable to augment: %s", self.name, e)
        except AttributeError as e:
            # We don't augment interfaces
            pass

        # Then, merge in all other interface declarations that haven't
        # been augmented
        try:
            interfaces_to_merge = {}
            own_interfaces = getattr(self, 'interfaces', None) or {}
            for interface_name, interface_declaration in managed_declaration.interfaces.items():
                # Is this a declaration that has already been augmented?
                # Only this declaration's own interfaces count: one its
                # type defines has not been augmented by the declaration
                # being merged in.
                if interface_name in own_interfaces:
                    # Nothing further to do
                    continue
                # Don't have this one yet. Start from the interface as
                # this declaration's type defines it, so the type keeps
                # precedence (its operations' implementations among
                # them), and fill in from the declaration being merged.
                from tosca_core.models.interface_declaration import ToscaInterfaceDeclaration
                merged_interface = ToscaInterfaceDeclaration()
                try:
                    merged_interface.merge_augmented_declaration(
                        self.get_interface_to_augment(interface_name))
                except KeyError:
                    # Our type does not define this interface
                    pass
                merged_interface.merge_augmented_declaration(interface_declaration)
                interfaces_to_merge[interface_name] = merged_interface
            # Merge in
            try:
                self.interfaces.update(interfaces_to_merge)
            except (AttributeError, TypeError):
                # Don't have interfaces or interfaces set to None
                self.interfaces = interfaces_to_merge
        except AttributeError as e:
            # We don't augment interfaces
            pass

        

