"""
Module definining Tosca Policy entity
"""
from __future__ import annotations

__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2018-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Type hints
from typing import Any, Optional

# Logging support
import logging
logger: logging.Logger = logging.getLogger(__name__)

# Database support
from tosca_core import db

# Trigger dicts are mutable
from sqlalchemy.ext.mutable import MutableDict

# Types on which this instance depends
import tosca_core.models.template

# Types used in relationships
import tosca_core.models.policy_declaration


class ToscaPolicyTemplate(tosca_core.models.template.ToscaTemplate):
    """The ToscaPolicyTemplate object represents policy templates in
    Tosca node templates. Which nodes a policy applies to at runtime, and
    what its triggers do when an event reaches it, are for an application
    that runs services to decide.
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
    _targets =       db.Column(db.PickleType, nullable=True)
    _triggers =      db.Column(MutableDict.as_mutable(db.PickleType), nullable=True)

    @property
    def targets(self) -> Any:
        if not self._targets:
            raise AttributeError("Template {0} does not have 'targets' attribute".format(self.name))
        return self._targets

    @property
    def triggers(self) -> dict[str, Any]:
        if not self._triggers:
            raise AttributeError("Template {0} does not have 'triggers' attribute".format(self.name))
        return self._triggers


    ################################################################################
    # Constructor
    ################################################################################

    def __init__(self,
                 type: Optional[Any] = None,
                 targets: Optional[Any] = None,
                 triggers: Optional[dict[str, Any]] = None,
                 **kwargs: Any
    ) -> None:
        """Instantiate a new Tosca Policy instance"""

        # First, call superclass constructor
        super(ToscaPolicyTemplate, self).__init__(**kwargs)

        # ToscaPolicyTemplateType-specific initialization
        self.type = type
        if targets: self._targets = targets
        if triggers: self._triggers = triggers
