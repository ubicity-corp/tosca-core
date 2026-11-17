"""
ToscaRepositoryValidator class
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
    from tosca_core.models.repository import ToscaRepository

# URL parser
from urllib.parse import urlparse

# Validator support
from .validator import ToscaValidator

# Types on which this validator depends
from tosca_core.models.property_declaration import ToscaPropertyDeclaration


class ToscaRepositoryValidator(ToscaValidator):
    """The ToscaRepositoryValidator class validates repository
    definitions in Tosca profiles
    """

    def __init__(self) -> None:
        """Constructor
        """
        super(ToscaRepositoryValidator, self).__init__()


    def validate_repository(self, repository: "ToscaRepository") -> dict:
        """Check if a repository is valid

        Args: 
          repository(ToscaRepository): repository to validate

        Returns:
          (possibly empty) dict of validation errors

        Raises:
          None
        """

        validation_errors = {}

        # Does the repository have a valid url?
        errors = self.validate_url(repository)
        if errors:
            logger.error("Repository '%s': invalid url", 
                         repository.name)
            validation_errors['url'] = errors

        # Does the repository have a valid credential?
        errors = self.validate_credential(repository)
        if errors:
            logger.error("Repository '%s': invalid credential", 
                         repository.name)
            validation_errors['credential'] = errors

        # Everything OK
        self.add_line_number(validation_errors, repository)
        return validation_errors



    def validate_url(self, repository: "ToscaRepository") -> dict:
        """Check if a repository has a valid url

        Args: 
          repository(ToscaRepository): repository for which to
            validate url

        Returns:
          (possibly empty) dict of validation errors

        Raises:
          None

        """

        # Make sure we have a valid url for this repository
        try:
            url = repository.url
        except AttributeError:
            logger.error("Repository %s: no url specified", repository.name)
            return 'not specified'

        logger.debug("Repository '%s': validating url '%s'", 
                     repository.name, url)

        validation_errors = {}
        try:
            # Make sure we have the basic elements in this URL
            parsed_url = urlparse(url)
            if not bool(parsed_url.scheme):
                logger.error("Repository '%s': %s does not have scheme",
                             repository.name, url)
                validation_errors[url] = 'no schema'
            # 'file:' URIs are allowed to omit the host: '/local/path'
            # is the common form. Other schemes still need an explicit
            # location.
            elif parsed_url.scheme != 'file' and not bool(parsed_url.netloc):
                logger.error("Repository '%s': %s does not have location",
                             repository.name, url)
                validation_errors[url] = 'no location'
#            if not bool(parsed_url.path):
#                logger.error("Repository '%s': %s does not have path", 
#                             repository.name, url)
#                validation_errors[url] = 'no path'
        except Exception as e:
            logger.error("Repository %s: error validating url %s: %s",
                         repository.name, url, e)
            validation_errors[url] = "validator error ({0})".format(e)

        # Everything OK
        return validation_errors



    def validate_credential(self, repository: "ToscaRepository") -> dict:
        """Check if a repository has a valid credential

        Args: 
          repository(ToscaRepository): repository for which to
            validate credential

        Returns:
          (possibly empty) dict of validation errors

        Raises:
          None

        """

        # Make sure we have a valid credential for this repository
        try:
            credential = repository.credential
        except AttributeError:
            # credential is optional
            logger.debug("Repository %s: no credential specified", repository.name)
            return {}

        # Nothing to do for now beyond what Marshmallow has already checked.
        return {}
