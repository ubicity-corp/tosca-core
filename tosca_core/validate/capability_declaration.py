"""
ToscaCapabilityDeclarationValidator class
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
from .declaration import ToscaDeclarationValidator
from tosca_core.models.capability_declaration import ToscaCapabilityDeclaration


class ToscaCapabilityDeclarationValidator(ToscaDeclarationValidator):
    """The ToscaCapabilityDeclarationValidator class validates capability
    declarations in Tosca Node Type definitions
    """


    def __init__(self) -> None:
        """Constructor
        """
        super(ToscaCapabilityDeclarationValidator, self).__init__()


    def validate_for_type(self, node_type: object, capability_declaration: object) -> dict:
        """Check if a capability declaration is valid

        Args: 
         node_type(ToscaNodeType): node type definition within which
           this capability is declared
         capability_declaration(ToscaCapabilityDeclaration): Tosca
          capability declaration to validate

        Returns:
          (possibly empty) dict of validation errors

        Raises:
          None
        """

        logger.debug("Node type '%s': validating capability declaration '%s'", 
                     node_type.name, capability_declaration.name)

        # Is this a valid declaration
        validation_errors = super(ToscaCapabilityDeclarationValidator,
                                  self).validate_for_type(node_type,
                                                          capability_declaration)

        # Does this capability declaration have valid valid source
        # node types?
        errors = self.validate_valid_source_node_types(capability_declaration.type_entity,
                                                       capability_declaration)
        if errors:
            logger.error("Capability '%s': invalid valid_source_node_types", 
                         capability_declaration.name)
            validation_errors['valid_source_node_types'] = errors

        # Does this capability declaration have valid valid
        # relationship types?
        errors = self.validate_valid_relationship_types(capability_declaration.type_entity,
                                                        capability_declaration)
        if errors:
            logger.error("Capability type '%s': invalid valid_relationship_types", 
                         capability_declaration.name)
            validation_errors['valid_relationship_types'] = errors

        # Does this capability declaration have valid occurrences?
        errors = self.validate_occurrences(node_type, capability_declaration)
        if errors:
            logger.error("%s: Capability '%s' has invalid occurrences",
                         node_type.name, capability_declaration.name)
            validation_errors['occurrences'] = errors

        # Everything OK
        return validation_errors


    def complete_augmentation(self, node_type: object, capability_name: str,
                              capability_to_augment: object, capability_declaration: object) -> dict:
        """Check that a capability declaration is a valid augmentation of
        the one it refines and, if it is, complete it by merging that
        declaration in.

        The merge brings in the refined declaration's type and its
        property and attribute declarations, so it comes before the
        capability's own property and attribute refinements are
        completed: a refinement that states no type has none until it is
        merged, and nested refinements find what they refine through it.

        Args: 
         node_type(ToscaNodeType): node type definition within which
           this capability is declared
         capability_name(str): name of the capability declaration
         capability_to_augment(ToscaCapabilityDeclaration): the
           declaration it augments
         capability_declaration(ToscaCapabilityDeclaration): Tosca
          capability augmentation to check and complete

        Returns:
          (possibly empty) dict of validation errors
        """
        # Does the capability augmentation have valid attribute values?
        errors = self.validate_capability_augmentation(capability_to_augment, capability_declaration)
        if errors:
            logger.error("Type '%s': capability '%s': invalid augmentation",
                         node_type.name, capability_name)
            self.add_line_number(errors, capability_declaration)
            return errors

        # Valid capability augmentation. Create new capability declaration
        # that reflects the capability augmentation
        capability_declaration.merge_augmented_declaration(capability_to_augment)
        return {}


    def validate_capability_augmentation(self, capability_to_augment: object,
                                         capability_declaration: object) -> dict:
        """Check if a capability declaration is a valid augmentation of a
        previous capability declaration:

        After these conditions are set, a new capability declaration
        must be created from the augmentation, and that new capability
        declaration must be validated separately

        Args: 
          capability_to_augment(ToscaCapabilityDeclaration): Tosca
            capability declaration to augment
          capability_declaration(ToscaCapabilityDeclaration): Tosca
            capability declaration to validate

        """

        validation_errors = {}
        # Make sure type of augmentation is compatible with type of
        # augmented capability declaration
        try:
            type = capability_declaration._type
            if not capability_declaration.has_type(capability_to_augment.type_entity):
                logger.error("Capability '%s': augmentation type '%s' incompatible with '%s'",
                             type, capability_to_augment.type,
                             capability_declaration.name)
                validation_errors['type'] = '{0} is not compatible with {1}'.format(
                    type, capability_to_augment.type)
        except AttributeError:
            # No type specified. Augmentation will have the same type
            # as the type of the augmented entity
            pass

        # Does this capability type have valid valid source node types?
        errors = self.validate_valid_source_node_types(capability_to_augment,
                                                       capability_declaration)
        if errors:
            logger.error("Capability '%s': invalid valid_source_node_types", 
                         capability_declaration.name)
            validation_errors['valid_source_node_types'] = errors

        # Does this capability type have valid valid relationship types?
        errors = self.validate_valid_relationship_types(capability_to_augment,
                                                        capability_declaration)
        if errors:
            logger.error("Capability '%s': invalid valid_relationship_types", 
                         capability_declaration.name)
            validation_errors['valid_relationship_types'] = errors

        # Everything OK
        return validation_errors


    def validate_valid_source_node_types(self, type_or_declaration: object,
                                         capability_declaration: object) -> dict:
        """Check if a capability declaration has valid
        valid_source_node_types. We consider two cases:

        1. The capability declaration is not a refinement. In that
           case, 'type_or_declaration' is the capability type used in
           the declaration.

        2. The capability declaration is a refinement. In that case
           'type_or_declaration' is the capability declaration that is
           being refined.

        Args:
          type_or_declaration(ToscaCapabilityType or
            ToscaCapabilityDeclaration): type for the declaration (if
            not a refinement) or capability declaration that is being
            refined (in case of refinement)
          capability_declaration(ToscaCapabilityDeclaration):
            capability declaration for which to validate
            valid_source_node_types
        """

        validation_errors = {}

        # check valid_source_node_types field if present
        try:
            valid_source_node_types = capability_declaration.valid_source_node_types
        except AttributeError:
            # Optional valid_source_node_types attribute not present
            logger.debug("capability '%s': no valid_source_node_types to validate", 
                         capability_declaration.name)
            return validation_errors

        # Validate each source type
        for node_type_name in valid_source_node_types:

            logger.debug("capability '%s': validating node_type_name '%s'",
                         capability_declaration.name, node_type_name)

            # Make sure node_type_name represents a valid node type
            try:
                profile = capability_declaration.profile
                node_type = profile.get_node_type(node_type_name)
            except te.TypeNotFound:
                # source type not found
                logger.error("capability %s has unknown node_type_name %s", 
                             capability_declaration.name, node_type_name)
                validation_errors[node_type_name] = 'not found'
                continue

            # Make sure this source type is a valid source type
            # for the capability declaration we are overriding
            if not type_or_declaration.is_valid_source_node_type(node_type):
                logger.error("capability '%s' invalid node_type_name '%s'", 
                             capability_declaration.name, node_type_name)
                validation_errors[node_type_name] = "invalid specialization of parent declaration's source types"

        # Everything OK
        return validation_errors


    def validate_valid_relationship_types(self, type_or_declaration: object,
                                         capability_declaration: object) -> dict:
        """Check if a capability declaration has valid
        valid_relationship_types. We consider two cases:

        1. The capability declaration is not a refinement. In that
           case, 'type_or_declaration' is the capability type used in
           the declaration.
        2. The capability declaration is a refinement. In that case
           'type_or_declaration' is the capability declaration that is
           being refined.

        Args:
          type_or_declaration(ToscaCapabilityType or
            ToscaCapabilityDeclaration): type for the declaration (if
            not a refinement) or capability declaration that is being
            refined (in case of refinement)
          capability_declaration(ToscaCapabilityDeclaration):
            capability declaration for which to validate
            valid_relationship_types
        """

        validation_errors = {}

        # check valid_relationship_types field if present
        try:
            valid_relationship_types = capability_declaration.valid_relationship_types
        except AttributeError:
            # Optional valid_relationship_types attribute not present
            logger.debug("capability '%s': no valid_relationship_types to validate", 
                         capability_declaration.name)
            return validation_errors

        # Validate each relationship type
        for relationship_type_name in valid_relationship_types:

            logger.debug("capability '%s': validating relationship_type_name '%s'",
                         capability_declaration.name, relationship_type_name)

            # Make sure relationship_type_name represents a valid
            # relationship type
            try:
                profile = capability_declaration.profile
                relationship_type = profile.get_relationship_type(relationship_type_name)
            except te.TypeNotFound:
                # source type not found
                logger.error("capability %s has unknown relationship_type_name %s", 
                             capability_declaration.name, relationship_type_name)
                validation_errors[relationship_type_name] = 'not found'
                continue

            # Make sure this source type is a valid source type
            # for the capability declaration we are overriding
            if not type_or_declaration.is_valid_relationship_type(relationship_type):
                logger.error("capability '%s' invalid relationship_type_name '%s'", 
                             capability_declaration.name, relationship_type_name)
                validation_errors[relationship_type_name] = "invalid specialization of parent declaration's source types"

        # Everything OK
        return validation_errors


    def validate_occurrences(self, node_type: object, capability_declaration: object) -> dict:
        """Check if a capability declaration has valid occurrences

        Args: 
          node_type(ToscaNodeType): node type for which to validate
            the capability declaration
          capability_declaration(ToscaCapabilityDeclaration): Tosca
            capability declaration to validate

        """
        try:
            occurrences = capability_declaration.occurrences
            logger.info("%s: Ubicity ignores occurrences in capability definitions (%s)",
                        node_type.name,  capability_declaration.name)
        except AttributeError:
            pass

        # Everything OK
        return {}



