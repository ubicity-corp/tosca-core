"""
ToscaArtifactTypeValidator class
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2014-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger = logging.getLogger(__name__)

# Validator support
from .type import ToscaTypeValidator


class ToscaArtifactTypeValidator(ToscaTypeValidator):
    """The ToscaArtifactTypeValidator class validates TOSCA Artifact Type
    definitions
    """

    def __init__(self) -> None:
        """Constructor
        """
        super(ToscaArtifactTypeValidator, self).__init__()


    def validate_type_specifics(self, artifact_type: object) -> dict:
        """Validate definitions that are specific to relationship type
        definitions:

        - Call 'validate_type_specifics' for the parent type
        - Make sure the artifact type definition has a valid mime type
          and file extension

        Args:
          artifact_type(ToscaArtifactType): artifact type
            definition to validate
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """

        logger.debug("Artifact type '%s': validating", artifact_type.name)

        # Is this a valid managed type entity?
        validation_errors = super(ToscaArtifactTypeValidator, 
                                  self).validate_type_specifics(artifact_type)

        # Check mime type 
        errors = self.validate_mime_type(artifact_type)
        if errors:
            logger.error("Artifact type '%s': no valid mime type", 
                         artifact_type.name)
            validation_errors['mime_type'] = errors

        # Check file extension
        errors = self.validate_file_ext(artifact_type)
        if errors:
            logger.error("Artifact type '%s': no valid file extension", 
                         artifact_type.name)
            validation_errors['file_ext'] = errors

        # All done
        return validation_errors


    def validate_mime_type(self, artifact_type: object) -> dict:
        """Check if an artifact type definition has a valid mime type
        definition

        Args:
          artifact_type(ToscaArtifactType): artifact type definition
            to validate
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """

        validation_errors = {}

        # Check mime type 
        try:
            mime_type = artifact_type.mime_type
        except AttributeError:
            logger.debug("Artifact type %s does not have mime type", 
                         artifact_type.name)
            return validation_errors

        logger.debug("Artifact type '%s': validating mime type '%s'",
                     artifact_type.name, mime_type)

        # Everything valid
        return validation_errors


    def validate_file_ext(self, artifact_type: object) -> dict:
        """Check if an artifact type entity has a valid mime type

        Args:
          artifact_type(ToscaArtifactType): artifact type definition
            to validate
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """

        validation_errors = {}

        # Check file extension
        try:
            file_extensions = artifact_type.file_ext
        except AttributeError:
            logger.debug("Artifact type %s does not declare valid file extensions", 
                         artifact_type.name)
            return validation_errors

        # Validate all extensions
        for file_ext in file_extensions:
            logger.debug("Artifact type '%s': validating file extension '%s'",
                         artifact_type.name, file_ext)
            # Make sure this is a list of strings
            if not isinstance(file_ext, str):
                logger.error("Artifact type '%s': file extension is not a string", 
                             artifact_type.name)
                validation_errors[str(file_ext)] = 'not a string'

        # Everything valid
        return validation_errors


