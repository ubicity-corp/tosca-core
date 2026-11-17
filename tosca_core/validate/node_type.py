"""
ToscaNodeTypeValidator class
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
    from tosca_core.models.node_type import ToscaNodeType

# Validator support
from . import get_validator

# Types on which this validator depends
from .managed_type import ToscaManagedTypeValidator


class ToscaNodeTypeValidator(ToscaManagedTypeValidator):
    """The ToscaNodeTypeValidator class validates TOSCA node type
    definitions
    """

    def __init__(self) -> None:
        """Constructor
        """
        super(ToscaNodeTypeValidator, self).__init__()


    def complete_type_refinements(self, node_type: "ToscaNodeType") -> dict:
        """Check and complete a node type's refinements: its requirement
        refinements and the interface refinements inside every
        requirement's relationship declaration, then its property and
        attribute refinements, as for any type, then its capability
        declarations -- each one that refines a capability the node type
        inherits, and then the property and attribute refinements inside
        each capability declaration, which find what they refine through
        the capability's type and so come after the merge that gives a
        refining declaration its type.

        A requirement that refines nothing still holds interface
        declarations, and property and attribute refinements, against the
        relationship type, so those are completed for every requirement.
        They come after the outer merge, which is what gives a refining
        requirement the relationship type they resolve through.

        'validate_type_specifics' then validates the completed
        declarations without checking or merging them again.

        Args:
          node_type(ToscaNodeType): node type whose refinements to
            complete

        Returns:
          (possibly empty) dict of validation errors, keyed the way
          'validate_type_specifics' keys them
        """
        errors = {}

        # Requirements, capabilities, and the type's own properties and
        # attributes are completed independently: each reads only what it
        # refines -- the parent requirement and the relationship type, the
        # inherited capability and the capability type, the parent type --
        # and nothing here evaluates an expression. The order below is not
        # significant.
        requirement_validator = get_validator('ToscaRelationshipDeclaration')
        requirement_errors = {}
        for requirement in (node_type.requirements or []):
            try:
                requirement_to_augment = node_type.get_requirement_to_augment(requirement.name)
            except KeyError:
                # A new requirement declaration, not a refinement. Its
                # relationship interfaces still refine the relationship
                # type's.
                requirement_to_augment = None
            try:
                if requirement_to_augment is not None:
                    outer = requirement_validator.complete_augmentation(
                        node_type, requirement.name, requirement_to_augment, requirement)
                    if outer:
                        logger.error("Node type '%s': requirement '%s': invalid augmentation",
                                     node_type.name, requirement.name)
                        if isinstance(outer, dict):
                            self.add_line_number(outer, requirement)
                        requirement_errors[requirement.name] = outer
                        continue
                nested = {}
                interface_errors = requirement_validator.complete_interface_refinements(
                    node_type, requirement)
                if interface_errors:
                    nested['interfaces'] = interface_errors
                for attribute in ('properties', 'attributes'):
                    attribute_errors = requirement_validator.complete_augmentations(
                        node_type, requirement, attribute,
                        get_validator('ToscaPropertyDeclaration'))
                    if attribute_errors:
                        nested[attribute] = attribute_errors
                if nested:
                    self.add_line_number(nested, requirement)
                    requirement_errors[requirement.name] = nested
            except Exception as e:
                logger.error("Type '%s': error while completing requirement augmentation '%s': %s", 
                             node_type.name, requirement.name, e)
                requirement_errors[requirement.name] = "validation error ({0})".format(e)
        if requirement_errors:
            errors['requirements'] = requirement_errors

        errors.update(super(ToscaNodeTypeValidator, self).complete_type_refinements(node_type))

        capability_validator = get_validator('ToscaCapabilityDeclaration')
        property_validator = get_validator('ToscaPropertyDeclaration')
        capability_errors = {}
        for capability_name, capability in (getattr(node_type, 'capabilities', None) or {}).items():
            try:
                capability_to_augment = node_type.get_entity_declaration_to_augment(
                    'capabilities', capability_name)
            except KeyError:
                # A new capability declaration, not a refinement
                capability_to_augment = None
            try:
                if capability_to_augment is not None:
                    outer = capability_validator.complete_augmentation(
                        node_type, capability_name, capability_to_augment, capability)
                    if outer:
                        if isinstance(outer, dict):
                            self.add_line_number(outer, capability)
                        capability_errors[capability_name] = outer
                        continue
                nested = {}
                for attribute in ('properties', 'attributes'):
                    attribute_errors = capability_validator.complete_augmentations(
                        node_type, capability, attribute, property_validator)
                    if attribute_errors:
                        nested[attribute] = attribute_errors
                if nested:
                    self.add_line_number(nested, capability)
                    capability_errors[capability_name] = nested
            except Exception as e:
                logger.error("Node type '%s': error while completing capability '%s': %s",
                             node_type.name, capability_name, e)
                capability_errors[capability_name] = "validation error ({0})".format(e)
        if capability_errors:
            errors['capabilities'] = capability_errors
        return errors


    def validate_type_specifics(self, node_type: "ToscaNodeType") -> dict:
        """Validate type specifics for a node type definition: what every
        managed type has, through the parent class, and then the
        capabilities and requirements a node type adds.

        Every refinement the type declares was checked and completed by
        'complete_type_refinements' before validation began, so each of
        these reads declarations that are already whole, whatever order
        they run in. The one order that still matters -- artifacts before
        the interfaces whose implementations name them -- is kept in the
        parent class, where both are validated.

        Args:
          node_type(ToscaNodeType): node type definition to validate
        Returns:
          (possibly empty) dict of validation errors
        Raises: 
          None

        """

        logger.debug("Node type '%s': validating", node_type.name)

        # Is this a valid managed type entity?
        validation_errors = super(ToscaNodeTypeValidator,
                                  self).validate_type_specifics(node_type)

        # Validate capabilities
        validator = get_validator('ToscaCapabilityDeclaration')
        errors = self.validate_declarations(node_type,
                                            'capabilities', validator)
        if errors:
            logger.error("Node type '%s': invalid capability declarations", 
                         node_type.name)
            validation_errors['capabilities'] = errors

        # Check requirements
        errors = self.validate_requirement_declarations(node_type)
        if errors:
            logger.error("Node type '%s': invalid requirement declarations", 
                         node_type.name)
            validation_errors['requirements'] = errors

        # All done
        return validation_errors


    def validate_requirement_declarations(self, node_type: "ToscaNodeType") -> dict:
        """Check if a node type definition has valid requirement
        declarations. Note that requirement refinements have already
        been validated and completed earlier.

        Args: 
          node_type(ToscaNodeType): node type definition for which to
            validate requirement declarations
        Returns:
          (possibly empty) dict of validation errors
        Raises: 
          None

        """
        
        validation_errors = {}

        # Validate each requirement declaration
        requirements = node_type.requirements
        if not requirements:
            logger.debug("Node type '%s': no requirement declarations to validate",
                         node_type.name)
            return validation_errors

        # First, check for duplicate names in list of locally-defined requirements
        requirement_names = [ requirement.name for requirement in requirements ]
        s = set()
        for requirement_name in requirement_names:
            if requirement_name in s:
                logger.error("Node type '%s': duplicate requirement '%s'",
                             node_type.name, requirement_name)
                validation_errors[requirement_name] = 'duplicate requirement'
            s.add(requirement_name)

        # Validate all requirement declarations
        validator = get_validator('ToscaRelationshipDeclaration')
        for requirement in requirements:
            logger.debug("Node type '%s': validating requirement declaration '%s'",
                         node_type.name, requirement.name)
            try:
                errors = validator.validate_declaration(node_type,
                                                        requirement)
                if errors:
                    logger.error("Node type <%s: invalid requirement declaration '%s'", 
                                 node_type.name, requirement.name)
                    validation_errors[requirement.name] = errors

            except Exception as e:
                logger.error("Node type '%s': error while validating requirement '%s': %s", 
                             node_type.name, requirement.name, e)
                validation_errors[requirement.name] = "validation error ({0})".format(e)
                
        # Requirement declarations valid
        return validation_errors


