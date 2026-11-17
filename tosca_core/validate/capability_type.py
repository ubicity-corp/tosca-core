"""
ToscaCapabilityTypeValidator class
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2014-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger = logging.getLogger(__name__)

# Exception support
import tosca_core.models.exceptions as te

# Types on which this validator depends
from .type import ToscaTypeValidator


class ToscaCapabilityTypeValidator(ToscaTypeValidator):
    """The ToscaCapabilityTypeValidator class validates TOSCA capability
    type definitions
    """


    def __init__(self) -> None:
        """Constructor
        """
        super(ToscaCapabilityTypeValidator, self).__init__()


    def validate_type_specifics(self, capability_type: object) -> dict:
        """Validate definitions that are specific to capability type
        definitions:

        - Call 'validate_type_specifics' for the parent type
        - Make sure the capability type has valid valid source node
          types
        - Make sure the capability type has valid valid relationship
          types

        Args:
          capability_type(ToscaCapabilityType): capability type
            definition to validate
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None

        """

        logger.debug("Capability type '%s': validating", capability_type.name)

        # Is this a valid managed type entity?
        validation_errors = super(ToscaCapabilityTypeValidator, 
                                  self).validate_type_specifics(capability_type)

        # Does this capability type have valid valid source node
        # types?
        errors = self.validate_valid_source_node_types(capability_type)
        if errors:
            logger.error("Capability type '%s': invalid valid_source_node_types", 
                         capability_type.name)
            validation_errors['valid_source_node_types'] = errors

        # Does this capability type have valid valid relationship
        # types?
        errors = self.validate_valid_relationship_types(capability_type)
        if errors:
            logger.error("Capability type '%s': invalid valid_relationship_types", 
                         capability_type.name)
            validation_errors['valid_relationship_types'] = errors

        # All done
        return validation_errors


    def validate_valid_source_node_types(self, capability_type: object) -> dict:
        """Check if a capability type definition has valid
        valid_source_node_types

        Args:
          capability_type(ToscaCapabilityType): capability type
            definition for which to validate valid_source_node_types
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """

        validation_errors = {}

        # check valid_source_node_types field if present
        try:
            valid_source_node_types = capability_type.valid_source_node_types
        except AttributeError:
            # Optional valid_source_node_types attribute not present
            # or valid_source_node_types value is None
            logger.debug("Capability type '%s': no valid_source_node_types to validate", 
                         capability_type.name)
            return validation_errors

        # Validate each valid source node type
        for node_type_name in valid_source_node_types:
            try:
                logger.debug("Capability type '%s': validating source node type '%s'",
                             capability_type.name, node_type_name)

                # Make sure node_type_name represents a valid node type
                try:
                    profile = capability_type.profile
                    node_type = profile.get_node_type(node_type_name)
                except te.TypeNotFound:
                    # source type not found
                    logger.error("Capability type %s has unknown source node type %s", 
                                 capability_type.name, node_type_name)
                    validation_errors[node_type_name] = 'not found'
                    continue

                # Make sure this source type is a valid source node
                # type for the parent's class
                try:
                    parent_type = capability_type.parent
                    if not parent_type.is_valid_source_node_type(node_type):
                        logger.error("Capability type '%s' invalid source node type '%s'", 
                                     capability_type.name, node_type_name)
                        validation_errors[node_type_name] = "invalid specialization of 'valid_source_node_types' in {0}".format(parent_type.name)
                except (AttributeError, KeyError):
                    # No parent type
                    pass

            except Exception as e:
                logger.error("Capability type '%s': error while validating valid source node types: %s", 
                             capability_type.name, e)
                validation_errors[node_type_name] = "validator error {0}".format(e)

        # Everything OK
        return validation_errors


    def validate_valid_relationship_types(self, capability_type: object) -> dict:
        """Check if a capability type definition has valid
        valid_relationship_types

        Args:
          capability_type(ToscaCapabilityType): capability type
            definition for which to validate valid_relationship_types
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """

        validation_errors = {}

        # check valid_relationship_types field if present
        try:
            valid_relationship_types = capability_type.valid_relationship_types
        except AttributeError:
            # Optional valid_relationship_types attribute not present
            # or valid_relationship_types value is None
            logger.debug("Capability type '%s': no valid_relationship_types to validate", 
                         capability_type.name)
            return validation_errors

        # Validate each valid relationship type
        for relationship_type_name in valid_relationship_types:
            try:
                logger.debug("Capability type '%s': validating relationship type '%s'",
                             capability_type.name, relationship_type_name)

                # Make sure relationship_type_name represents a valid
                # relationship type
                try:
                    profile = capability_type.profile
                    relationship_type = profile.get_relationship_type(relationship_type_name)
                except te.TypeNotFound:
                    # relationship type not found
                    logger.error("Capability type %s has unknown valid relationship type %s", 
                                 capability_type.name, relationship_type_name)
                    validation_errors[relationship_type_name] = 'not found'
                    continue

                # Make sure this relationship type is a valid
                # relationship type for the parent's class
                try:
                    parent_type = capability_type.parent
                    if not parent_type.is_valid_relationship_type(relationship_type):
                        logger.error("Capability type '%s' invalid relationship type '%s'", 
                                     capability_type.name, relationship_type_name)
                        validation_errors[relationship_type_name] = "invalid specialization of 'valid_relationship_types' in {0}".format(parent_type.name)
                except (AttributeError, KeyError):
                    # No parent type
                    pass

            except Exception as e:
                logger.error("Capability type '%s': error while validating valid relationship types: %s", 
                             capability_type.name, e)
                validation_errors[relationship_type_name] = "validator error {0}".format(e)

        # Everything OK
        return validation_errors
