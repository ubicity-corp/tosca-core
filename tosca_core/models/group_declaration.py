"""
Module definining Tosca Group Declaration entity
"""
from __future__ import annotations

__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2015-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Type hints
from typing import Any

# Logging support
import logging
logger: logging.Logger = logging.getLogger(__name__)

# Database support
from tosca_core import db

# Types on which this declaration depends
import tosca_core.models.declaration


class ToscaGroupDeclaration(tosca_core.models.declaration.ToscaDeclaration):
    """A ToscaGroupDeclaration declares the presence of a named group of
    a given group type. The name and type of the declared group are
    stored in the ToscaDeclaration base class.  Since Tosca topologies
    never declare groups (groups are defined without having been
    declared first), this object is only ever created synthetically
    for purposes of group validation.
    """

    ################################################################################
    # Polymorphic mapping
    ################################################################################

    __mapper_args__ = {
        'polymorphic_identity':'group',
    }


    ################################################################################
    # Constructor
    ################################################################################

    def __init__(self,
                 **kwargs: Any) -> None:
        # First, call superclass constructor
        super(ToscaGroupDeclaration, self).__init__(**kwargs)

        # ToscaGroupDeclaration-specific initialization


    ################################################################################
    # Other stuff that needs to be organized. 
    ################################################################################

    def is_valid_member(self, node_template: Any) -> bool:
        """Is the specified node template a valid member for this group
        declaration? This method needs to be extended to take
        profiles into account.

        Args:
          node_template(ToscaNodeTemplate): node template for which to
            check if it is a valid member of this group

        Raises:
          None
        """

        # Do we restrict valid member types?
        try:
            members = self.members
            # Is the node template (or one of its base classes) in the
            # list of valid member types?
            for member in members:
                member_type = self.profile.get_node_type(member)
                if node_template.has_type(member_type):
                    return True

            # Not a valid member
            return False
        except AttributeError:
            # We don't restrict member types. Does our type?
            return self.type_entity.is_valid_member(node_template)
