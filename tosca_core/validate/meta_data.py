"""
ToscaMetadataValidator class
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2015-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger = logging.getLogger(__name__)

# Type hint support
from typing import Any

# Types used by this validator
from tosca_core.builtin.version import ToscaVersion

# type checking support
import numbers


class ToscaMetadataValidator(object):
    """The ToscaMetadataValidator class validates metadata definitions in
    Tosca service templates
    """

    def __init__(self) -> None:
        """Constructor
        """
        super(ToscaMetadataValidator, self).__init__()


    def validate_meta_data(self, meta_data: "Any") -> dict:
        """Check if a meta_data is valid

        Args: 
          meta_data(ToscaMetadata): meta_data to validate

        Returns:
          (possibly empty) dict of validation errors

        Raises:
          None
        """

        validation_errors = {}

        # Iterate over meta data
        try:
            for meta_name, meta_value in meta_data.items():
                # Make sure name is a string
                if not isinstance(meta_name, str):
                    logger.debug("Meta data name (%s) is not a string", meta_name)
                    validation_errors[meta_name] = "Key '{}' is not a string".format(meta_name)
                    continue

                # Per the spec a null value is legal here (YAML 1.2
                # null is one of the recommended scalar types), but
                # in practice it's never useful and 'key:' with no
                # value is almost always a typo. Flag it -- if a real
                # use case turns up, this will surface in spec errata
                # discussion rather than slip through silently.
                if meta_value is None:
                    validation_errors[meta_name] = "value is missing"
                    continue

                # Make sure value is a string or a number or metadata
                if not isinstance(meta_value, str) and \
                   not isinstance(meta_value, numbers.Number):
                    errors = self.validate_meta_data(meta_value)
                    if errors:
                        logger.debug("Meta data value (%s) is not a string or metadata", meta_value)
                        validation_errors[meta_name] = errors
                    continue

                # Make sure we have a valid version string
                if meta_name == 'template_version':
                    try: 
                        version_object = ToscaVersion(meta_value)
                    except ValueError:
                        logger.error("Incorrectly formatted template_version string %s", 
                                     meta_value)
                        validation_errors[meta_name] = 'incorrectly formatted version ({})'.format(meta_value)
        except AttributeError:
            return 'Value is not a string or metadata'

        # Everything OK
        return validation_errors
