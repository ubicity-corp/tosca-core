"""
ToscaPolicyTypeValidator class
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2018-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger = logging.getLogger(__name__)

# Type hint support
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from tosca_core.models.policy_type import ToscaPolicyType

# Exception support
import tosca_core.models.exceptions as te

# Types on which this validator depends
from .type import ToscaTypeValidator


class ToscaPolicyTypeValidator(ToscaTypeValidator):
    """The ToscaPolicyTypeValidator class validates TOSCA policy type
    definitions
    """

    def __init__(self) -> None:
        """Constructor
        """
        super(ToscaPolicyTypeValidator, self).__init__()


    def validate_type_specifics(self, policy_type: "ToscaPolicyType") -> dict:
        """Validate definitions that are specific to a policy type definition:

        - Call 'validate_type_specifics' for the parent type
        - Make sure the policy type has valid valid source types

        Args:
          policy_type(ToscaPolicyType): policy type
            definition to validate
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """

        logger.debug("Policy type '%s': validating", policy_type.name)

        # Is this a valid type entity?
        validation_errors = super(ToscaPolicyTypeValidator, 
                                  self).validate_type_specifics(policy_type)

        # Does this policy type have valid targets?
        errors = self.validate_targets(policy_type)
        if errors:
            logger.error("Policy type '%s': invalid targets", 
                         policy_type.name)
            validation_errors['targets'] = errors

        # Does this policy type have valid triggers?
        errors = self.validate_triggers(policy_type)
        if errors:
            logger.error("Policy type '%s': invalid triggers", 
                         policy_type.name)
            validation_errors['triggers'] = errors

        # All done
        return validation_errors


    def validate_targets(self, policy_type: "ToscaPolicyType") -> dict:
        """Check if a policy type definition has valid targets

        Args:
          policy_type(ToscaPolicyType): policy type
            definition for which to validate targets
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """

        validation_errors = {}

        # check targets field if present
        try:
            targets = policy_type.targets
        except AttributeError:
            # Optional targets attribute not present or
            # targets value is None
            logger.debug("Policy type '%s': no targets to validate", 
                         policy_type.name)
            return validation_errors

        # Validate each valid target
        for target in targets:
            try:
                logger.debug("Policy type '%s': validating target '%s'",
                             policy_type.name, target)

                # Make sure target represents a valid node type
                try:
                    profile = policy_type.profile
                    target_type = profile.get_node_type(target)
                except te.TypeNotFound:
                    # Target node type not found. Could be a group type.
                    try:
                        target_type = profile.get_group_type(target)
                    except te.TypeNotFound:
                        # Target group type not found either.
                        logger.error("Policy type %s has unknown target %s", 
                                     policy_type.name, target)
                        validation_errors[target] = 'not found'
                        continue

                # Make sure this target is a valid specialization of a
                # valid target type in the parent's class
                try:
                    parent_type = policy_type.parent
                    if not parent_type.is_valid_target(target_type):
                        logger.error("Policy type '%s' invalid target '%s'", 
                                     policy_type.name, target)
                        validation_errors[target] = "invalid specialization of parent's targets ({0})".format(parent_type.name)
                except (AttributeError, KeyError):
                    # No parent type
                    pass

            except Exception as e:
                logger.error("Policy type '%s': error while validating targets: %s", 
                             policy_type.name, e)
                validation_errors[target] = "validator error {0}".format(e)

        # Everything OK
        return validation_errors


    def validate_triggers(self, policy_type: "ToscaPolicyType") -> dict:
        """Check if a policy type definition has valid triggers

        Args:
          policy_type(ToscaPolicyType): policy type
            definition for which to validate triggers
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """

        validation_errors = {}

        # check triggers field if present
        try:
            triggers = policy_type.triggers
        except AttributeError:
            # Optional triggers attribute not present or
            # triggers value is None
            logger.debug("Policy type '%s': no triggers to validate", 
                         policy_type.name)
            return validation_errors

        return 'not implemented'
