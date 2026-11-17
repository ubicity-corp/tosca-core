"""
Module definining Tosca Policy Declaration entity
"""
from __future__ import annotations

__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2018-2026, Ubicity Corp."
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


class ToscaPolicyDeclaration(tosca_core.models.declaration.ToscaDeclaration):
    """A ToscaPolicyDeclaration declares the presence of a named policy
    of a given policy type. The name and type of the declared policy
    are stored in the ToscaDeclaration base class.  Since Tosca
    topologies never declare policies (policies are defines without
    having been declared first), this object is only ever created
    synthetically for purposes of policy validation.
    """

    ################################################################################
    # Polymorphic mapping
    ################################################################################

    __mapper_args__ = {
        'polymorphic_identity':'policy',
    }


    ################################################################################
    # Constructor
    ################################################################################

    def __init__(self,
                 **kwargs: Any
    ) -> None:
        # First, call superclass constructor
        super(ToscaPolicyDeclaration, self).__init__(**kwargs)
