"""
Module definining Tosca Capability entity
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


class ToscaCapabilityTemplate(tosca_core.models.template.ToscaTemplate):
    """The ToscaCapabilityTemplate object represents capability templates
    in Tosca node templates
    """

    ################################################################################
    # Polymorphic mapping
    ################################################################################

    __mapper_args__ = {
        'polymorphic_identity':'capability',
    }

    ################################################################################
    # Fields
    ################################################################################

    # '_directives' is declared on the shared ToscaTemplate base.

    @property
    def directives(self) -> list[str]:
        """TOSCA 2.0 capability directives. The spec leaves the default
        implementation-defined; we default to ['internal', 'external'] —
        both scopes are allowed, with internal sources tried first.
        """
        return self._directives if self._directives is not None else ['internal', 'external']

    # Directives currently supported for capability assignments
    valid_directives = ['internal', 'external']


    ################################################################################
    # Constructor
    ################################################################################

    def __init__(self,
                 attributes: Optional[Any] = None,
                 directives: Optional[list[str]] = None,
                 **kwargs: Any
    ) -> None:
        """Instantiate a new Tosca Capability template"""

        # First, call superclass constructor
        super(ToscaCapabilityTemplate, self).__init__(**kwargs)

        # ToscaCapabilityTemplate-specific initialization
        self.attributes = attributes
        if directives: self._directives = directives




        
