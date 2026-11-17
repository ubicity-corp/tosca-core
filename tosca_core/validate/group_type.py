"""
ToscaGroupTypeValidator class
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2016-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger = logging.getLogger(__name__)

# Type hint support
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from tosca_core.models.group_type import ToscaGroupType

# Types on which this validator depends
from .managed_type import ToscaTypeValidator

# Exception support
import tosca_core.models.exceptions as te


class ToscaGroupTypeValidator(ToscaTypeValidator):
    """The ToscaGroupTypeValidator class validates TOSCA group type
    definitions
    """

    def __init__(self) -> None:
        """Constructor
        """
        super(ToscaGroupTypeValidator, self).__init__()


    def validate_type_specifics(self, group_type: "ToscaGroupType") -> dict:
        """Validate definitions that are specific to group type definitions:

        - Call 'validate_type_specifics' for the parent type
        - Make sure the group type has valid valid members

        Args:
          group_type(ToscaGroupType): group type
            definition to validate
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """

        logger.debug("Group type '%s': validating", group_type.name)

        # Is this a valid managed type entity?
        validation_errors = super(ToscaGroupTypeValidator, 
                                  self).validate_type_specifics(group_type)

        # Does this group type have valid member types?
        errors = self.validate_member_types(group_type)
        if errors:
            logger.error("Group type '%s': invalid member types", 
                         group_type.name)
            validation_errors['members'] = errors

        # All done
        return validation_errors


    def validate_member_types(self, group_type: "ToscaGroupType") -> dict:
        """Check if a group type definition has valid member_types

        Args: group_type(ToscaGroupType): group type definition for
          which to validate member types
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """

        validation_errors = {}

        # check members field if present
        try:
            members = group_type.members
        except AttributeError:
            # Optional member_types attribute not present
            logger.debug("Group type '%s': no member_types to validate", 
                         group_type.name)
            return validation_errors

        # Validate all members
        for member in members:

            try:
                logger.debug("Group type '%s': validating member type '%s'",
                             group_type.name, member)

                # Make sure member represents a valid node type
                try:
                    profile = group_type.profile
                    node_type = profile.get_node_type(member)
                except te.TypeNotFound:
                    # Node type not found
                    logger.error("group type %s has unknown member type %s", 
                                 group_type.name, member)
                    validation_errors[member] = 'not found'
                    continue

                # Make sure this member type is a valid member type
                # for the parent's class
                try:
                    parent_type = group_type.parent
                    if not parent_type.is_valid_member(node_type):
                        logger.error("Group type '%s' invalid member '%s'", 
                                     group_type.name, member)
                        validation_errors[member] = "invalid specialization of parent's members ({0})".format(parent_type.name)
                except (AttributeError, KeyError):
                    # No parent type
                    pass

            except Exception as e:
                logger.error("Group type '%s': error while validating members: %s", 
                             group_type.name, e)
                validation_errors[member] = "validator error {0}".format(e)

        # Everything OK
        return validation_errors



