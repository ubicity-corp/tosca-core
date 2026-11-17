"""
Module definining Tosca Group entity
"""
from __future__ import annotations

__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2014-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Type hints
from typing import Any, Optional

# Logging support
import logging
logger: logging.Logger = logging.getLogger(__name__)

# Database support
from tosca_core import db

# Types on which this instance depends
import tosca_core.models.template

# Types used in relationships
import tosca_core.models.group_declaration


class ToscaGroupTemplate(tosca_core.models.template.ToscaTemplate):
    """ToscaGroupTemplate class
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

    # TODO: add database fields to track members and policies
    @property
    def members(self) -> Any:
        if not self._members:
            raise AttributeError("'{0}' does not have 'members'".format(self.name))
        return self._members

    @property
    def policies(self) -> Any:
        if not self._policies:
            raise AttributeError("'{0}' does not have 'policies'".format(self.name))
        return self._policies


    ################################################################################
    # Constructor
    ################################################################################

    def __init__(self,
                 type: Optional[Any] = None,
                 members: Optional[Any] = None,
                 policies: Optional[Any] = None,
                 **kwargs: Any) -> None:
        """Instantiate a new ToscaGroupTemplate instance"""

        # First, call superclass constructor
        super(ToscaGroupTemplate, self).__init__(**kwargs)

        # ToscaGroupTemplate-specific initialization
        self.type = type
        if members: self._members = members
        if policies: self._policies = policies
