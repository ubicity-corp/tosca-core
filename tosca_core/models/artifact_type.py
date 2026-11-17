"""
Module definining Tosca Artifact Type entity
"""
from __future__ import annotations

__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2014-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger: logging.Logger = logging.getLogger(__name__)

# Type hints
from typing import Optional

# Database support
from tosca_core import db

# Types on which this type depends
import tosca_core.models.type


class ToscaArtifactType(tosca_core.models.type.ToscaType):
    """The ToscaArtifactType represents a named artifact type that can be
    used for declaring Tosca artifacts in node type definitions or in
    node templates.
    """

    ################################################################################
    # Polymorphic mapping
    ################################################################################

    __mapper_args__ = {
        'polymorphic_identity':'artifact',
    }

    ################################################################################
    # Fields
    ################################################################################

    # Optional fields start with '_' and have corresponding getters
    # and setters to ensure that retrieving fields consistently raises
    # an AttributeError when not set.  Note that 'nullable' defaults
    # to True, but we explicitly set the 'nullable' flag for clarity.

    _mime_type = db.Column(db.String, nullable=True)
    _file_ext =  db.Column(db.PickleType, nullable=True)

    @property
    def mime_type(self) -> str:
        if not self._mime_type:
            raise AttributeError("'{0}' does not have 'mime_type'".format(self.name))
        return self._mime_type

    @property
    def file_ext(self) -> list[str]:
        if not self._file_ext:
            raise AttributeError("'{0}' does not have 'file_ext'".format(self.name))
        return self._file_ext


    ################################################################################
    # Constructor
    ################################################################################

    def __init__(self, mime_type: Optional[str] = None, file_ext: Optional[list[str]] = None, **kwargs) -> None:
        # First, call superclass constructor
        super(ToscaArtifactType, self).__init__(**kwargs)

        # ToscaArtifactType-specific initialization
        if mime_type: self._mime_type = mime_type
        if file_ext: self._file_ext = file_ext


    ################################################################################
    # Create a declaration of this type
    ################################################################################

    def create_declaration(self, name: str) -> ToscaArtifactDeclaration:
        """Synthesize a ToscaArtifact declaration for this artifact type

        Returns:
          ToscaArtifactDeclaration: with the appropriate name and
            type. No other attributes are initialized.

        Raises:
          None
        """
        from tosca_core.models.artifact_declaration import ToscaArtifactDeclaration
        artifact_declaration = ToscaArtifactDeclaration(name=name, type=self.name)
        artifact_declaration.type_entity = self
        return artifact_declaration


    ################################################################################
    # Does this artifact type support a given file extension
    ################################################################################

    def supports_extension(self, ext: str) -> bool:
        """Does this type support the given file extension"""

        # Get list of supported extensions
        try:
            extensions = self.file_ext
        except AttributeError:
            return False

        return ext.lower() in extensions



