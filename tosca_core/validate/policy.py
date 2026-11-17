"""
ToscaPolicyValidator class
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2018-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger = logging.getLogger(__name__)

# Type hint support
from typing import Any

# Validator support
from .template import ToscaTemplateValidator

# Validator
from . import get_validator
from .validator import ToscaValidator
from .activity import validate_activity as _validate_activity


class ToscaPolicyValidator(ToscaTemplateValidator):
    """The ToscaPolicyValidator class validates policies in Tosca
    service templates
    """

    def __init__(self) -> None:
        """Constructor
        """
        super(ToscaPolicyValidator, self).__init__()


    def validate_template(self, policy: "Any") -> dict:
        """Check if a policy is valid for the specified policy declaration.

        Args:
          policy: policy to validate

        Returns:
          (Possibly empty) dict of validation errors

        Raises:
          None
        """

        # Is this a valid  template
        validation_errors = super(ToscaPolicyValidator,
                                  self).validate_template(policy)

        # Does this policy have valid targets?
        errors = self.validate_targets(policy)
        if errors:
            logger.error("Policy '%s': invalid targets", policy.name)
            validation_errors['targets'] = errors

        # Does this policy have valid triggers?
        errors = self.validate_triggers(policy)
        if errors:
            logger.error("Policy '%s': invalid triggers", policy.name)
            validation_errors['triggers'] = errors

        # All done
        return validation_errors


    def validate_targets(self, policy: "Any") -> dict:
        """Check if a policy defines valid targets

        Args:
          policy(ToscaPolicy): policy for which to validate targets

        Returns:
          (Possibly empty) dict of validation errors

        Raises:
          None
        """

        validation_errors = {}

        # check targets field if present
        try:
            targets = policy.targets
        except AttributeError:
            # Optional targets attribute not present or
            # targets value is None
            logger.debug("Policy '%s': no targets to validate", policy.name)
            return validation_errors

        # Validate each target
        for target in targets:
            try:
                logger.debug("Policy '%s': validating target '%s'",
                             policy.name, target)
                try:
                    # Does target represent a valid node template?
                    target_node = policy.service.node_templates[target]

                    # Make sure this node is a valid target for the
                    # policy's type
                    target_type = target_node.declaration.type_entity
                    policy_type = policy.declaration.type_entity
                    if not policy_type.is_valid_target(target_type):
                        logger.error("Policy '%s' invalid target node '%s'", 
                                     policy.name, target)
                        validation_errors[target] = "invalid specialization <{0}> node targets".format(policy_type.name)
                except (AttributeError, KeyError):
                    # Not a reference to a node template defined in
                    # the service. Must be a group instead.
                    try:
                        target_group = policy.service.groups[target]
                        # Make sure this group is a valid target for the
                        # policy's type
                        group_type = target_group.declaration.type_entity
                        policy_type = policy.declaration.type_entity
                        if not policy_type.is_valid_target(group_type):
                            logger.error("Policy '%s' invalid target group '%s'", 
                                         policy.name, target)
                            validation_errors[target] = "invalid specialization of type's group targets ({0})".format(policy_type.name)
                    except (AttributeError, KeyError):
                        # Target group not found either.
                        logger.error("Policy '%s' has unknown target '%s'", 
                                     policy.name, target)
                        validation_errors[target] = 'not found'
                        continue
            except Exception as e:
                logger.error("Policy '%s': error while validating targets: %s", 
                             policy.name, e)
                validation_errors[target] = "validator error {0}".format(e)

        # Everything OK
        return validation_errors


    def validate_triggers(self, policy: "Any") -> dict:
        """Check if a policy template has valid triggers

        Args:
          policy(ToscaPolicyTemplate): policy template for which to
            validate triggers

        Returns:
          (Possibly empty) dict of validation errors

        Raises:
          None
        """

        validation_errors = {}
        
        # Get triggers field if present
        try:
            triggers = policy.triggers
        except AttributeError:
            # Optional triggers attribute not present or
            # triggers value is None
            logger.debug("Policy '%s': no triggers to validate", policy.name)
            return validation_errors

        # Validate each trigger individually
        for trigger_name, trigger in triggers.items():
            errors = self.validate_trigger(policy, trigger)
            if errors:
                validation_errors[trigger_name] = errors

        # All done
        return validation_errors
        

    def validate_trigger(self, policy: "Any", trigger: dict) -> dict:
        """Check if a policy template has a valid trigger. Triggers use an
         (event, condition, action) pattern. We validate each of these
         separately.

        Args:
          policy(ToscaPolicyTemplate): policy template for which to
            validate the (event, condition, action) trigger.

        Returns:
          (Possibly empty) dict of validation errors

        Raises:
          None
        """
        
        logger.debug("%s: validating trigger '%s'", policy.name, trigger['name'])
        validation_errors = {}

        # validate event
        errors = self.validate_event(policy, trigger)
        if errors:
            logger.error("Trigger %s: invalid event", trigger['name'])
            validation_errors["event"] = errors

        # validate condition
        errors = self.validate_condition(policy, trigger)
        if errors:
            logger.error("Trigger %s: invalid constraints", trigger['name'])
            validation_errors["condition"] = errors

        # validate action
        errors = self.validate_action(policy, trigger)
        if errors:
            logger.error("Trigger %s: invalid action", trigger['name'])
            validation_errors["action"] = errors
        
        # All done
        return validation_errors


    def validate_event(self, policy: "Any", trigger: dict) -> dict:
        """Check if a trigger has a valid event

        Args:
          policy(ToscaPolicy): policy definition for which to validate
            the trigger

        Returns:
          (Possibly empty) dict of validation errors

        Raises:
          None
        """

        validation_errors = {}

        # Make sure we have a trigger that defines a event
        try:
            event = trigger["event"]
        except KeyError:
            logger.debug("Trigger %s does not define a event.", trigger['name'])
            return 'no event specified'

        return validation_errors


    def validate_condition(self, policy: "Any", trigger: dict) -> dict:
        """Check if a trigger has valid condition

        Args:
          policy(ToscaPolicy): policy definition for which to validate
            the trigger conditions.

        Returns:
          (Possibly empty) dict of validation errors

        Raises:
          None
        """
        # Make sure we have a trigger that defines a condition
        try:
            condition = trigger["condition"]
        except KeyError:
            logger.debug("Trigger %s does not define a condition.", trigger['name'])
            return {}

        # Upgrade Version 1.3 conditions if necessary
        if (policy.tosca_version and
            policy.tosca_version.startswith("tosca_simple_yaml")):
            validator = get_validator('ToscaCondition')
            errors = validator.validate_and_upgrade_trigger_conditions(policy.service, trigger)
            if errors:
                return errors
            condition = trigger["condition"]

        errors, canonical = self._validate_boolean_expression(policy, condition, 'preconditions')
        if errors:
            return errors
        trigger['condition'] = canonical
        # 'triggers' is a MutableDict, but the assignment above is to a dict
        # nested inside it, and MutableDict only tracks its own keys. Without
        # this the canonical form is never written.
        policy.triggers.changed()

        # All done
        return {}


    def validate_action(self, policy: "Any", trigger: dict) -> dict:
        """Check if a trigger has a valid action

        Args:
          policy(ToscaPolicy): policy definition for which to validate
            the trigger
        Returns:
          (Possibly empty) dict of validation errors
        Raises:
          None
        """

        validation_errors = {}

        try:
            actions = trigger["action"]
        except KeyError:
            logger.debug("Trigger %s has no action.", trigger['name'])
            return validation_errors
        try:
            counter = 0
            for activity in actions:
                activity['name'] = str(counter)
                logger.debug("validating activity '%s'", activity['name'])
                counter = counter+1
                errors = self.validate_activity(policy, activity)
                if errors: validation_errors[activity['name']] = errors
        except TypeError:
            logger.debug("Trigger %s has an action that is not a list.", trigger['name'])
            return f"Trigger '{trigger['name']}' has an action that is not a list"

        return validation_errors


    def validate_activity(self, policy: "Any", activity: dict) -> "Any":
        """Check if policy activities are valid.

        Shares the action dispatch with workflow steps via
        ``validate.activity.validate_activity``. ``call_operation``
        passes no resolver because the orchestrator hasn't yet decided
        which entity a policy trigger calls the operation on, so the
        check stops at the syntactic level (operation present and
        formatted as ``<interface>.<operation>``).
        """
        return _validate_activity(
            policy, activity,
            owner_label='Policy',
            changed_collection=policy.triggers,
        )
