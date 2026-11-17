"""
Module definining Tosca Group Type entity
"""
from __future__ import annotations

__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2015-2026, Ubicity Corp."
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


class ToscaGroupType(tosca_core.models.type.ToscaType):
    """The ToscaGroupType represents a named group type that can be used
    for declaring Tosca groups in service templates.
    """

    ################################################################################
    # Polymorphic mapping
    ################################################################################
    __mapper_args__ = {
        'polymorphic_identity':'group',
    }

    ################################################################################
    # Fields
    ################################################################################

    # Optional fields start with '_' and have corresponding getters
    # and setters to ensure that retrieving fields consistently raises
    # an AttributeError when not set.  Note that 'nullable' defaults
    # to True, but we explicitly set the 'nullable' flag for clarity.
    _members = db.Column(db.PickleType, nullable=True)

    @property
    def members(self) -> list[str]:
        if not self._members:
            raise AttributeError("'{0}' does not have 'members'".format(self.name))
        return self._members


    ################################################################################
    # Constructor
    ################################################################################

    def __init__(self,
                 members: Optional[list[str]] = None,
                 **kwargs: Any
    ) -> None:
        # First, call superclass constructor
        super(ToscaGroupType, self).__init__(**kwargs)

        # ToscaGroupType-specific initialization
        if members: self._members = members


    ################################################################################
    # Create a declaration of this type
    ################################################################################

    def create_declaration(self, name: str) -> ToscaGroupDeclaration:
        """Synthesize a ToscaGroupDeclaration object for this group type

        Returns:
          ToscaGroupDeclaration: with the appropriate name and
            type. No other attributes are initialized.

        Raises:
          None
        """
        import tosca_core.models.group_declaration as tgd
        group_declaration = tgd.ToscaGroupDeclaration(name=name, type=self.name)
        group_declaration.type_entity = self
        return group_declaration


    ################################################################################
    # Other stuff that needs to be organized. 
    ################################################################################

    def is_valid_member(self, node: Any) -> bool:
        """Is the specified node type entity a valid member of this group
        type? Note that this method needs to be extended to take
        profiles into account.

        Args:
          node(ToscaNodeType or ToscaNodeTemplate): node for which to
            check if is a valid member of this group type

        Raises:
          None
        """

        # Do we restrict valid member types?
        try:
            # Is this node type (or one of its base classes) in the list
            # of valid member types?
            for member in self.members:
                member_type = self.profile.get_node_type(member)
                if node.has_type(member_type):
                    return True
                
             # Not a valid member
            return False
             
        except (AttributeError, TypeError):
            # We don't have a members attribute, or the members
            # attribute is set to None. This means we don't restrict
            # member types. Does our parent class?
            try:
                return self.parent.is_valid_member(node)
            except (AttributeError, te.CircularInheritance):
                # We don't have a parent, which means we don't
                # restrict member types
                return True
