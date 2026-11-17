"""
ToscaArtifactValidator class
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2014-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger = logging.getLogger(__name__)

# SQLAlchemy exception support
import tosca_core.models.exceptions as te

# Repository helpers
import tosca_core.models.repository as tr

# Per-call validation options
from . import context

# Validator support
from .template import ToscaTemplateValidator


class ToscaArtifactValidator(ToscaTemplateValidator):
    """The ToscaArtifactValidator class validates artifact templates
    defined in Tosca Node Types or Node Templates or defined inline in
    operation implementations.
    """

    def __init__(self) -> None:
        """Constructor
        """
        super(ToscaArtifactValidator, self).__init__()


    def validate_typed_template(self, artifact: object) -> dict:
        """Check if an artifact template is valid. This method overrides the
        'validate_typed_template' method in the ToscaTemplateValidator
        because the ToscaTemplateValidator will attempt to determine
        the artifact type which shouldn't be done if the artifact file
        doesn't exist. We first need to check whether the artifact
        file exists in the repository, and then we can perform regular
        template validations.

        Args: 
         artifact(ToscaArtifact): Tosca artifact to validate
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """

        logger.debug("Artifact '%s': validating", artifact.name)

        validation_errors = dict()
        
        # First check if artifact file exists in the repository.
        errors = self.validate_repository(artifact)
        if errors:
            logger.error("Artifact '%s': invalid repository specified", 
                         artifact.name)
            validation_errors['repository'] = errors

        # Does the artifact define a valid file?
        errors = self.validate_file(artifact)
        if errors:
            logger.error("Artifact '%s': no valid file specified", 
                         artifact.name)
            validation_errors['file'] = errors

        # Does the artifact define a valid deploy_path?
        errors = self.validate_deploy_path(artifact)
        if errors:
            logger.error("Artifact '%s': invalid deploy_path specified", 
                         artifact.name)
            validation_errors['deploy_path'] = errors

        # Does the file match its checksum?
        if not validation_errors:
            errors = self.validate_checksum(artifact)
            if errors:
                logger.error("Artifact '%s': %s", artifact.name, errors)
                validation_errors['checksum'] = errors

        # No point in validating further if artifact file can't be
        # found.
        if validation_errors:
            return validation_errors
        else:
            return super(ToscaArtifactValidator, self).validate_typed_template(artifact)


    def validate_file(self, artifact: object) -> object:
        """Check if a artifact file location is valid for a given artifact
        declaration. At this point, we have already validated the
        repository.

        Args: 
          artifact(ToscaArtifact): Tosca artifact for which to
            validate the file location
        """

        logger.debug("Artifact '%s': validating file", artifact.name)
        try:
            file = artifact._file
            if not file: return 'not specified'
            logger.debug("Artifact '%s': validating file '%s'",
                         artifact.name, file)

            # If 'file' is an absolute URL and no repository was specified
            # for the artifact, create a synthetic repository from the
            # URL (mirrors the import flow in
            # import_tosca_file_from_repo).
            if not getattr(artifact, '_repository', None) and tr.is_uri(file):
                try:
                    artifact.repo, file = tr.create_repository_for_url(file)
                    artifact._file = file
                    relative_to = '/'
                except te.RepositoryNotFound as e:
                    logger.error("Artifact '%s': %s", artifact.name, e)
                    return "'{0}' is not a valid URL".format(file)
            elif getattr(artifact, '_repository', None):
                # A named repository supplies the base and 'file' the
                # path under it, whichever file in its archive the
                # declaring template is (mirrors the import flow).
                relative_to = '/'
            else:
                relative_to = artifact.profile.tosca_file_path

            # Get absolute file path for the artifact
            file = artifact.repo.get_absolute_path(file, relative_to)
            artifact._file = file

            # Find file in repo. The existence check can be suppressed
            # for the current ingestion run (e.g. when artifacts live
            # on a private network unreachable from the validator).
            if context.skip_file_checks():
                logger.debug("Artifact '%s': skipping existence check for '%s'",
                             artifact.name, file)
            elif not artifact.repo.exists(file):
                logger.error("Artifact '%s': file '%s' not found in repo '%s'",
                             artifact.name,
                             artifact.file, artifact.repo.name)
                return "'{}' not found".format(artifact.file)

        except AttributeError:
            # file is required
            logger.debug("Artifact '%s': no file specified",
                         artifact.name)
            return 'not specified'
            
        # All done
        return None


    def validate_repository(self, artifact: object) -> object:
        """Check if a artifact repository is valid for a given artifact
        declaration

        Args: 
          artifact_declaration(ToscaArtifactDeclaration): Tosca
            artifact declaration against which to validate the
            artifact
          artifact(ToscaArtifact): Tosca artifact for which to
            validate the repository
        """
        
        validation_errors = {}
        try:
            repository = artifact._repository
        except AttributeError:
            # No new repository name specified. Use repo that contains
            # the template that defines the artifact.
            artifact.repo = artifact.profile.repository
            return None

        logger.debug("Artifact '%s': validating repository '%s'", 
                     artifact.name, repository)
        try:
            artifact.repo = artifact.profile.get_repository(repository)
        except te.RepositoryNotFound: 
            logger.error("Artifact '%s': repository '%s' not found",
                         artifact.name, repository)
            validation_errors[repository] = 'not found'

        # Everything OK
        return validation_errors


    def validate_checksum(self, artifact: object) -> "Optional[str]":
        """Check an artifact's checksum (§12.2): a checksum needs a
        checksum_algorithm the orchestrator supports, and the file must match
        it. The file is not read when file checks are suppressed for this
        ingestion.

        Args:
          artifact(ToscaArtifact): Tosca artifact whose checksum to check
        Returns:
          None, or the reason the checksum is refused
        """
        from tosca_core.models.artifact import check_checksum, checksum_algorithm_name

        checksum = getattr(artifact, '_checksum', None)
        algorithm = getattr(artifact, '_checksum_algorithm', None)
        if not checksum:
            return None
        if not algorithm:
            return "a checksum needs a 'checksum_algorithm' (TOSCA 2.0 §12.2)"
        try:
            checksum_algorithm_name(algorithm)
        except ValueError as e:
            return str(e)
        if context.skip_file_checks():
            return None
        try:
            check_checksum(artifact.repo.retrieve(artifact.file), checksum, algorithm)
        except (IOError, ValueError) as e:
            return str(e)
        return None


    def validate_deploy_path(self, artifact: object) -> dict:
        """Check if a artifact deploy path is valid for a given artifact
        declaration

        Args: 
          artifact_declaration(ToscaArtifactDeclaration): Tosca
            artifact declaration against which to validate the
            artifact
          artifact(ToscaArtifact): Tosca artifact for which to
            validate the deploy path
        """

        try:
            deploy_path = artifact.deploy_path
        except AttributeError:
            # deploy_path is not required
            return {}

        # TOSCA 1.3 defines deploy_path; TOSCA 2.0 does not, and its grammar
        # refuses it before validation. Refuse it here too, rather than
        # accept a placement nothing is bound to make.
        logger.error("Artifact '%s': deploy_path '%s' is not supported",
                     artifact.name, deploy_path)
        return ("not supported: TOSCA 2.0 has no deploy_path; where an artifact "
                "is placed is up to what deploys it")
