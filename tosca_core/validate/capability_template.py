"""
ToscaCapabilityTemplateValidator class
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2014-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger = logging.getLogger(__name__)

# Validator support
from .template import ToscaTemplateValidator


class ToscaCapabilityTemplateValidator(ToscaTemplateValidator):
    """The ToscaCapabilityTemplateValidator class validates capability
    templates defined in node templates in Tosca service templates
    """

    def __init__(self) -> None:
        """Constructor
        """
        super(ToscaCapabilityTemplateValidator, self).__init__()


    def validate_template(self, capability: object) -> dict:
        """Check if a capability template is valid for the given capability
        declaration

        Args:
          capability(ToscaCapabilityTemplate): capability to validate

        Returns:
          (possibly empty) dict of validation errors
        """

        # Is this a valid  instance_entity
        validation_errors = super(ToscaCapabilityTemplateValidator,
                                  self).validate_template(capability)

        # Are the capability directives (if any) valid?
        errors = self.validate_directives(capability)
        if errors:
            validation_errors['directives'] = errors

        # All done
        return validation_errors


    def validate_directives(self, capability: object) -> dict:
        """Check that capability directives are valid TOSCA 2.0 values.
        Only 'internal' and 'external' are permitted, and each may
        appear at most once. Order is significant and preserved by the
        caller.

        Args:
          capability(ToscaCapabilityTemplate): capability template
            whose directives to validate
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """
        validation_errors = {}
        directives = capability.directives

        for directive in directives:
            if directive not in capability.valid_directives:
                logger.error("Capability '%s': invalid directive '%s'",
                             capability.name, directive)
                validation_errors[directive] = 'not a valid directive'

        for directive in capability.valid_directives:
            if directives.count(directive) > 1:
                logger.error("Capability '%s': multiple '%s' directives",
                             capability.name, directive)
                validation_errors[directive] = 'defined multiple times'

        return validation_errors
