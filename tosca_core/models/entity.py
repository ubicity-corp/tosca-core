"""
Module definining Tosca Entity mixin
"""
from __future__ import annotations

__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2020-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Type hints
from typing import Any, Optional

# Logging support
import logging
logger: logging.Logger = logging.getLogger(__name__)

# Database support
from tosca_core import db


class ToscaEntityMixin(object):
    """The ToscaEntityMixin object defines model fields that are common
    to all TOSCA entities.
    """

    ################################################################################
    # Fields
    ################################################################################

    # Optional fields start with '_' and have corresponding getters
    # and setters to ensure that retrieving fields consistently raises
    # an AttributeError when not set.  Note that 'nullable' defaults
    # to True, but we explicitly set the 'nullable' flag for clarity.

    name =          db.Column(db.String,     nullable=True)
    _description =  db.Column(db.String,     nullable=True)
    _meta_data =    db.Column(db.PickleType, nullable=True)

    @property
    def description(self) -> str:
        if not self._description:
            raise AttributeError("'{0}' does not have 'description'".format(self.name))
        return self._description

    @property
    def meta_data(self) -> dict[str, Any]:
        if not self._meta_data:
            raise AttributeError("'{0}' does not have 'meta_data'".format(self.name))
        return self._meta_data

    @meta_data.setter
    def meta_data(self, value: Optional[dict[str, Any]]) -> None:
        if value:
            if self._meta_data:
                self._meta_data.update(value)
            else:
                self._meta_data = value
        else:
            self._meta_data = None


    ################################################################################
    # Constructor
    ################################################################################

    def __init__(self,
                 line: Optional[int] = None,
                 name: Optional[str] = None,
                 description: Optional[str] = None,
                 meta_data: Optional[dict[str, Any]] = None,
    ) -> None:
        """Instantiate a new ToscaRepository instance"""

        # First, call superclass constructor
        super(ToscaEntityMixin, self).__init__()

        # ToscaRepository-specific initialization
        if line != None: self.line = line
        if description: self._description = description
        if name: self.name = name
        self.meta_data = meta_data
