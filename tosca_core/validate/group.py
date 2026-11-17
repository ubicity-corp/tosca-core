"""
ToscaGroupValidator class
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2014-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger = logging.getLogger(__name__)

# Type hint support
from typing import Any

# Validator support
from .template import ToscaTemplateValidator



class ToscaGroupValidator(ToscaTemplateValidator):
    """The ToscaGroupValidator class validates group definitions in Tosca
    service templates
    """

    def __init__(self) -> None:
        """Constructor
        """
        super(ToscaGroupValidator, self).__init__()


    def validate_template(self, group: "Any") -> dict:
        """Check if a group is valid for a given group declaration

        Args: 
          group_declaration(ToscaGroupDeclaration): group declaration
            against which to validate the group
          group(ToscaGroup): group to validate

        Returns:
          (possibly empty) dict of validation errors

        Raises:
          None
        """

        # Is this a valid instance
        validation_errors = super(ToscaGroupValidator,
                                  self).validate_template(group)

        # Does the group have valid members?
        errors = self.validate_members(group)
        if errors:
            logger.error("Group '%s': invalid members", 
                         group.name)
            validation_errors['members'] = errors

        # Does the group have valid policies?
        errors = self.validate_policies(group)
        if errors:
            logger.error("Group '%s': invalid policies", 
                         group.name)
            validation_errors['policies'] = errors

        # Everything OK
        return validation_errors



    def validate_members(self, group: "Any") -> dict:
        """Check if a group has valid members

        Args: 
          group_declaration(ToscaGroupDeclaration): group declaration
            against which to validate the group
          group(ToscaGroup): group to validate

        Returns:
          (possibly empty) dict of validation errors

        Raises:
          None
        """

        validation_errors = {}

        try:
            members = group.members
        except AttributeError:
            logger.error("Group %s: no members defined", group.name)
            return validation_errors

        logger.debug("Group %s: validating members", group.name)

        for member in members:
            try:
                node = group.service.node_templates[member]
            except KeyError:
                logger.error("Group %s: member %s not found",
                             group.name, member)
                validation_errors[member] = 'not found'

            # Make sure the node is a valid member of the group
            if not group.declaration.is_valid_member(node):
                logger.error("Group '%s': node '%s' is not a valid member", 
                             group.name, node.name)
                validation_errors[member] = 'incompatible type'

        # Everything OK
        return validation_errors


    def validate_policies(self, group: "Any") -> dict:
        """Check if a group has valid policies

        Args: 
          group_declaration(ToscaGroupDeclaration): group declaration
            against which to validate the group
          group(ToscaGroup): group to validate

        Returns:
          True: if valid capability declaration
          False: if invalid capability declaration

        Raises:
          None
        """

        try:
            policies = group.policies
            logger.debug("Group %s: validating policies", group.name)
        except AttributeError:
            # TOSCA 2.0 declares a policy at the service template's level, naming
            # its targets, and never on the group, so a group without its own
            # policies is the normal case rather than an error.
            logger.debug("Group %s: no policies declared on the group", group.name)
            return {}

        # Everything OK
        return {}
