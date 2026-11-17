"""
ToscaRelationshipTypeValidator class
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2014-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger = logging.getLogger(__name__)

# Type hint support
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from tosca_core.models.relationship_type import ToscaRelationshipType

# Types on which this validator depends
from .managed_type import ToscaManagedTypeValidator

# Exception support
import tosca_core.models.exceptions as te
import tosca_core.models.recognized_names as rn


class ToscaRelationshipTypeValidator(ToscaManagedTypeValidator):
    """The ToscaRelationshipTypeValidator class validates TOSCA
    relationship type definitions
    """

    def __init__(self) -> None:
        """Constructor
        """
        super(ToscaRelationshipTypeValidator, self).__init__()


    def validate_type_specifics(self, relationship_type: "ToscaRelationshipType") -> dict:
        """Validate definitions that are specific to relationship type
        definitions:

        - Call 'validate_type_specifics' for the parent type
        - Make sure the relationship type has valid vald targets

        Args:
          relationship_type(ToscaRelationshipType): relationship type
            definition to validate
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """

        logger.debug("Relationship type '%s': validating", relationship_type.name)

        # Is this a valid managed type entity?
        validation_errors = super(ToscaRelationshipTypeValidator, 
                                  self).validate_type_specifics(relationship_type)

        # Does this relationship type have valid valid capability types?
        errors = self.validate_valid_capability_types(relationship_type)
        if errors:
            logger.error("Relationship type '%s': invalid valid_capability_types", 
                         relationship_type.name)
            validation_errors['valid_capability_types'] = errors

        # Does this relationship type have valid valid source node types?
        errors = self.validate_valid_source_node_types(relationship_type)
        if errors:
            logger.error("Relationship type '%s': invalid valid_source_node_types", 
                         relationship_type.name)
            validation_errors['valid_source_node_types'] = errors

        # Does this relationship type have valid valid target node types?
        errors = self.validate_valid_target_node_types(relationship_type)
        if errors:
            logger.error("Relationship type '%s': invalid valid_target_node_types", 
                         relationship_type.name)
            validation_errors['valid_target_node_types'] = errors

        # Does this relationship type have valid valid target node types?
        errors = self.validate_kind(relationship_type)
        if errors:
            logger.error("Relationship type '%s': invalid kind", 
                         relationship_type.name)
            validation_errors['kind'] = errors

        # All done
        return validation_errors


    def validate_valid_capability_types(self, relationship_type: "ToscaRelationshipType") -> dict:
        """Check if a relationship type definition has valid
        valid_capability_types

        Args:
          relationship_type(ToscaRelationshipType): relationship type
            definition for which to validate valid_capability_types
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """

        validation_errors = {}

        # check valid_capability_types field if present
        try:
            target_capability_types = relationship_type.valid_capability_types
        except AttributeError:
            # Optional valid_capability_types attribute not present 
            logger.debug("Relationship type '%s': no valid_capability_types to validate", 
                         relationship_type.name)
            return validation_errors

        # Validate each target type
        for target_capability_type in target_capability_types:
            try:
                logger.debug("Relationship type '%s': validating target_capability_type '%s'",
                             relationship_type.name, target_capability_type)

                # Make sure target_capability_type represents a valid capability type
                try:
                    profile = relationship_type.profile
                    capability_type = profile.get_capability_type(target_capability_type)
                except te.TypeNotFound:
                    # capability type not found
                    logger.error("Relationship type %s has unknown target_capability_type %s", 
                                 relationship_type.name, target_capability_type)
                    validation_errors[target_capability_type] = 'not found'
                    continue

                # Make sure this target type is a valid specialization
                # of a target type in the parent's class
                try:
                    parent_type = relationship_type.parent
                    if not parent_type.is_valid_capability_type(capability_type):
                        logger.error("Relationship type '%s' invalid target_capability_type '%s'", 
                                     relationship_type.name, target_capability_type)
                        validation_errors[target_capability_type] =  "invalid specialization of parent's target types ({0})".format(parent_type.name)
                except (AttributeError, KeyError):
                    # No parent type
                    pass

            except Exception as e:
                logger.error("Relationship type '%s': error while validating target_capability_types: %s", 
                             relationship_type.name, e)
                validation_errors[target_capability_type] = "validator error {0}".format(e)

        # Everything OK
        return validation_errors


    def validate_valid_source_node_types(self, relationship_type: "ToscaRelationshipType") -> dict:
        """Check if a relationship type definition has valid
        valid_source_node_types

        Args:
          relationship_type(ToscaRelationshipType): relationship type
            definition for which to validate valid_source_node_types
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """

        validation_errors = {}

        # check valid_source_node_types field if present
        try:
            source_node_types = relationship_type.valid_source_node_types
        except AttributeError:
            # Optional valid_source_node_types attribute not present 
            logger.debug("Relationship type '%s': no valid_source_node_types to validate", 
                         relationship_type.name)
            return validation_errors

        # Validate each target type
        for source_node_type in source_node_types:
            try:
                logger.debug("Relationship type '%s': validating source_node_type '%s'",
                             relationship_type.name, source_node_type)

                # Make sure source_node_type represents a valid node type
                try:
                    profile = relationship_type.profile
                    node_type = profile.get_node_type(source_node_type)
                except te.TypeNotFound:
                    # node type not found
                    logger.error("Relationship type %s has unknown source_node_type %s", 
                                 relationship_type.name, source_node_type)
                    validation_errors[source_node_type] = 'not found'
                    continue

                # Make sure this source node type is a valid
                # specialization of a valid source node type in the
                # parent's class
                try:
                    parent_type = relationship_type.parent
                    if not parent_type.is_valid_source_node_type(node_type):
                        logger.error("Relationship type '%s' invalid source_node_type '%s'", 
                                     relationship_type.name, source_node_type)
                        validation_errors[source_node_type] =  "invalid specialization of parent's source node types ({0})".format(parent_type.name)
                except (AttributeError, KeyError):
                    # No parent type
                    pass

            except Exception as e:
                logger.error("Relationship type '%s': error while validating source_node_types: %s", 
                             relationship_type.name, e)
                validation_errors[source_node_type] = "validator error {0}".format(e)

        # Everything OK
        return validation_errors


    def validate_valid_target_node_types(self, relationship_type: "ToscaRelationshipType") -> dict:
        """Check if a relationship type definition has valid
        valid_target_node_types

        Args:
          relationship_type(ToscaRelationshipType): relationship type
            definition for which to validate valid_target_node_types
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """

        validation_errors = {}

        # check valid_target_node_types field if present
        try:
            target_node_types = relationship_type.valid_target_node_types
        except AttributeError:
            # Optional valid_target_node_types attribute not present 
            logger.debug("Relationship type '%s': no valid_target_node_types to validate", 
                         relationship_type.name)
            return validation_errors

        # Validate each target type
        for target_node_type in target_node_types:
            try:
                logger.debug("Relationship type '%s': validating target_node_type '%s'",
                             relationship_type.name, target_node_type)

                # Make sure target_node_type represents a valid node type
                try:
                    profile = relationship_type.profile
                    node_type = profile.get_node_type(target_node_type)
                except te.TypeNotFound:
                    # node type not found
                    logger.error("Relationship type %s has unknown target_node_type %s", 
                                 relationship_type.name, target_node_type)
                    validation_errors[target_node_type] = 'not found'
                    continue

                # Make sure this target node type is a valid
                # specialization of a valid target node type in the
                # parent's class
                try:
                    parent_type = relationship_type.parent
                    if not parent_type.is_valid_target_node_type(node_type):
                        logger.error("Relationship type '%s' invalid target_node_type '%s'", 
                                     relationship_type.name, target_node_type)
                        validation_errors[target_node_type] =  "invalid specialization of parent's target node types ({0})".format(parent_type.name)
                except (AttributeError, KeyError):
                    # No parent type
                    pass

            except Exception as e:
                logger.error("Relationship type '%s': error while validating target_node_types: %s", 
                             relationship_type.name, e)
                validation_errors[target_node_type] = "validator error {0}".format(e)

        # Everything OK
        return validation_errors


    def validate_kind(self, relationship_type: "ToscaRelationshipType") -> dict:
        """Check if a relationship type definition has a valid kind

        Args:
          relationship_type(ToscaRelationshipType): relationship type
            definition for which to validate kind
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """

        validation_errors = {}

        # The kind, if any, is stated in metadata, as the TOSCA community
        # does; the grammar has no keyname for it
        try:
            meta_data = relationship_type.meta_data
            kind = rn.relationship_kind(meta_data).upper()
            relationship_type._kind = kind
        except (AttributeError, KeyError):
            logger.debug("Relationship type '%s': no kind to validate",
                         relationship_type.name)
            return validation_errors

        # Do we have a valid kind?
        if not kind in relationship_type.valid_kinds:
            return '{0} is invalid'.format(kind)

        # Derived types can only make the kind more restrictive.
        # CONTAINMENT > DEPENDENCY > ASSOCIATION
        try:
            parent = relationship_type.parent
            parent_kind = parent.get_kind()
            if (parent_kind == 'DEPENDENCY' and kind == 'ASSOCIATION') or \
               (parent_kind == 'CONTAINMENT' and kind != 'CONTAINMENT'):
                return '{0} is invalid specialization of parent kind {1}'.format(kind, parent_kind)
        except AttributeError:
            # No parent
            pass
        
        return validation_errors
            
