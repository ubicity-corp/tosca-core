"""
Module definining Tosca Policy Type entity
"""
from __future__ import annotations

__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2018-2026, Ubicity Corp."
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


class ToscaPolicyType(tosca_core.models.type.ToscaType):
    """The ToscaPolicyType represents a named policy type that can be
    used for declaring Tosca policies in service templates.
    """

    ################################################################################
    # Polymorphic mapping
    ################################################################################

    __mapper_args__ = {
        'polymorphic_identity':'policy',
    }

    ################################################################################
    # Fields
    ################################################################################

    # Optional fields start with '_' and have corresponding getters
    # and setters to ensure that retrieving fields consistently raises
    # an AttributeError when not set.  Note that 'nullable' defaults
    # to True, but we explicitly set the 'nullable' flag for clarity.
    _targets = db.Column(db.PickleType, nullable=True)
    _triggers = db.Column(db.PickleType, nullable=True)

    @property
    def targets(self) -> list[str]:
        if not self._targets:
            raise AttributeError("'{0}' does not have 'targets'".format(self.name))
        return self._targets

    @property
    def triggers(self) -> Any:
        if not self._triggers:
            raise AttributeError("'{0}' does not have 'triggers'".format(self.name))
        return self._triggers


    ################################################################################
    # Constructor
    ################################################################################

    def __init__(self,
                 targets: Optional[list[str]] = None,
                 triggers: Any = None,
                 **kwargs: Any
    ) -> None:
        # First, call superclass constructor
        super(ToscaPolicyType, self).__init__(**kwargs)

        # ToscaPolicyType-specific initialization
        if targets: self._targets = targets
        if triggers: self._triggers = triggers


    ################################################################################
    # Create a declaration of this type
    ################################################################################

    def create_declaration(self, name: str) -> ToscaPolicyDeclaration:
        """Synthesize a ToscaPolicyDeclaration object for this
        policy type

        Args:
          name(str): name for the policy being declared

        Returns:
          ToscaPolicyDeclaration: with the appropriate name and type. No
            other attributes are initialized.

        Raises:
          None
        """
        from tosca_core.models.policy_declaration import ToscaPolicyDeclaration
        policy_declaration = ToscaPolicyDeclaration(name=name, type=self.name)
        policy_declaration.type_entity = self
        return policy_declaration


    ################################################################################
    # Other stuff that needs to be organized. 
    ################################################################################

    def is_valid_target(self, target_type: Any) -> bool:
        """Is the specified target type entity a valid target for this
        policy? 

        Args:
          target_type(ToscaNodeType or ToscaGroupType): node type for
            which to check if it is a valid target for this policy type.
        Raises:
          None
        """
        logger.debug("Check if '%s' is valid target for policy type '%s'",
                     target_type.name, self.name)

        # Do we restrict target types?
        try:
            # Is this node type or group type (or one of its base
            # classes) in the list of target types?
            for target in self.targets:
                try:
                    # Check if target is a node type
                    target_node_type = self.profile.get_node_type(target)
                    if target_type.has_type(target_node_type):
                        return True
                except te.TypeNotFound:
                    # Target is not a node type. Must be a group type instead.
                    target_group_type = self.profile.get_group_type(target)
                    if target_type.has_type(target_group_type):
                        return True
                    
             # Not a valid target
            return False
             
        except (AttributeError, TypeError):
            # We don't restrict target types (since we don't have a
            # targets attribute or the targets attribute is
            # None). Does our parent class?
            try:
                return self.parent.is_valid_target(target_type)
            except (AttributeError, te.CircularInheritance):
                # We don't restrict target types, and we don't
                # have a parent who could do so either. All target
                # types are OK.
                return True
