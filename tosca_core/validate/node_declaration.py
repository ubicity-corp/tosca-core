"""
ToscaNodeDeclarationValidator class
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2015-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger = logging.getLogger(__name__)

# Type hint support
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from tosca_core.models.node_type import ToscaNodeType
    from tosca_core.models.node_declaration import ToscaNodeDeclaration

# Validator support
from .declaration import ToscaDeclarationValidator


class ToscaNodeDeclarationValidator(ToscaDeclarationValidator):
    """The ToscaNodeDeclarationValidator class validates TOSCA node
    declarations.  Note that node declarations are only ever
    synthesized as helper objects to allow node templates to be
    validated against a node declaration.
    """

    def __init__(self) -> None:
        """Constructor
        """

        # First, call superclass constructor
        super(ToscaNodeDeclarationValidator, self).__init__()


    def validate_for_type(self, node_type: "ToscaNodeType", node_declaration: "ToscaNodeDeclaration") -> dict:
        """Check if a node declaration if valid for the specified node type.

        Args: 
          node_type(ToscaNodeType): Tosca node type against which to
            validate the declaration
          node_declaration(ToscaNodeDeclaration): Tosca node
            declaration to validate
        """

        # Is this a valid managed instance declaration
        validation_errors = super(ToscaNodeDeclarationValidator,
                                  self).validate_for_type(node_type, 
                                                          node_declaration)

        # Anything else?

        # Everything OK
        return validation_errors


