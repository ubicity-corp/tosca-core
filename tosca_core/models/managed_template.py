"""
Module definining template classes for Tosca managed entities
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

# Types on which this instance depends
import tosca_core.models.template
from tosca_core.models.function import ToscaFunction

# Types used in relationships
import tosca_core.models.interface_template 


class ToscaManagedTemplate(tosca_core.models.template.ToscaTemplate):
    """The Tosca managed template class is the base class for TOSCA
    managed templates, specifically TOSCA node templates and
    relationship templates
    """

    ################################################################################
    # Polymorphic mapping
    ################################################################################

    __mapper_args__ = {
        'polymorphic_identity':'managed',
    }

    ################################################################################
    # Fields.  Optional fields start with '_' and have corresponding
    # getters and setters to ensure that retrieving fields
    # consistently raises an AttributeError when not set.  Note that
    # 'nullable' defaults to True, but we explicitly set the
    # 'nullable' flag for clarity.
    ################################################################################

    # Both node templates and relationship templates define
    # 'count'. The '_count' value can be an integer or a function.
    _count =     db.Column(db.PickleType, nullable=True)
    @property
    def count(self) -> Any:
        if self._count == None:
            return 1
        return self._count
    @count.setter
    def count(self, value: Any) -> None:
        if not value==None: self._count = value

    # Node filters use symbolic names for functions
    _node_filter =      db.Column(db.PickleType, nullable=True)
    @property
    def node_filter(self) -> Any:
        if not self._node_filter:
            raise AttributeError(f"{self.name} does not have 'node_filter' attribute")
        return self._node_filter
    @node_filter.setter
    def node_filter(self, value: Any) -> None:
        if value: self._node_filter = value

    # Resolved filters use internal function syntax based on signature ID.
    _resolved_filter =      db.Column(db.PickleType, nullable=True)
    @property
    def resolved_filter(self) -> Any:
        if not self._resolved_filter:
            raise AttributeError(f"{self.name} does not have 'resolved_filter' attribute")
        return self._resolved_filter
    @resolved_filter.setter
    def resolved_filter(self, value: Any) -> None:
        if value: self._resolved_filter = value

    ################################################################################
    # Relationships
    ################################################################################

    interfaces =       db.relationship('ToscaInterfaceTemplate',
                                       collection_class=attribute_mapped_collection('name'),
                                       foreign_keys='ToscaInterfaceTemplate._containing_template_id',
                                       cascade='all',
                                       back_populates='containing_template')


    ################################################################################
    # Implementation of reserved keywords
    ################################################################################

    def SELF(self) -> ToscaManagedTemplate:
        """Return the entity referred to by SELF. SELF applies to node
        templates or relationship templates only. All other templates
        retrieve SELF from their containing template
        """
        return self
        
        
    ################################################################################
    # Constructor
    ################################################################################

    def __init__(self,
                 interfaces: Optional[dict[str, Any]] = None,
                 type: Optional[Any] = None,
                 copy: Optional[Any] = None,
                 node_filter: Optional[Any] = None,
                 count: Optional[Any] = None,
                 **kwargs: Any) -> None:
        # First, call superclass constructor
        super(ToscaManagedTemplate, self).__init__(**kwargs)

        # ToscaManagedTemplate-specific initialization
        self.type = type
        if copy: self.copy = copy
        if interfaces: self.interfaces = interfaces
        self.node_filter = node_filter
        self.count = count


    ################################################################################
    # Template refinement support
    ################################################################################

    def complete_template_refinement(self, managed_instance: Any) -> None:
        """Complete a managed_instance with values from the managed_instance
        that it extends"""

        # First, call superclass augment method
        super(ToscaManagedTemplate, self).complete_template_refinement(managed_instance)

        # Merge fields we don't already have
        self.merge_augmented_field('_node_filter', managed_instance)
        self.merge_augmented_field('_resolved_filter', managed_instance)
        self.merge_augmented_field('_count', managed_instance)

        # Augment 'interfaces'
        self.merge_augmented_interfaces(managed_instance)


    def merge_augmented_interfaces(self, managed_instance: Any) -> None:
        # Does the augmented instance have interfaces?
        try:
            if not managed_instance.interfaces:
                # No interfaces to augment
                return
        except AttributeError:
            # No interfaces to augment
            return

        # Augment interfaces as necessary
        interfaces_to_merge = {}
        for interface_name, augmented_interface in managed_instance.interfaces.items():
            # Is this a instance that must be augmented?
            try:
                interface = self.interfaces[interface_name]
                try:
                    interface.complete_template_refinement(augmented_interface)
                except Exception as e:
                    logger.error("%s: error merging interface '%s': %s",
                                 self.name, interface_name, str(e))
            except (AttributeError, KeyError):
                # We don't have this interface
                try:
                    merged_interface = tosca_core.models.interface_template.ToscaInterfaceTemplate()
                    merged_interface.complete_template_refinement(augmented_interface)
                    interfaces_to_merge[interface_name] = merged_interface
                except Exception as e:
                    logger.error("%s: creating interface '%s': %s",
                                 self.name, interface_name, str(e))

        # Merge interfaces
        try:
            if self.interfaces:
                interfaces_to_merge.update(self.interfaces)
        except AttributeError:
            # Don't have interfaces or interfaces set to None
            pass

        # Set merged interfaces
        self.interfaces = interfaces_to_merge
