"""
ToscaManagedDeclarationValidator class
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2014-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging supoprt
import logging
logger = logging.getLogger(__name__)

# Validator support
from . import get_validator
from .declaration import ToscaDeclarationValidator


class ToscaManagedDeclarationValidator(ToscaDeclarationValidator):
    """The ToscaManagedDeclarationValidator class validates TOSCA managed
    declarations.
    """


    def __init__(self) -> None:
        """Constructor
        """
        super(ToscaManagedDeclarationValidator, self).__init__()


    def complete_interface_refinements(self, containing_entity: object, relationship_declaration: object) -> dict:
        """Check and complete the interface refinements a managed
        declaration holds: each interface declaration that refines one its
        relationship type declares, and then the inputs, outputs and
        operations inside every interface declaration.

        'validate_for_type' then validates them without checking or
        merging them again.

        Args:
          containing_entity(ToscaType): entity that contains the
            declaration this relationship declaration belongs to
          relationship_declaration(ToscaRelationshipDeclaration):
            declaration whose interface refinements to complete

        Returns:
          (possibly empty) dict of validation errors, keyed the way
          'validate_for_type' keys them
        """
        interface_validator = get_validator('ToscaInterfaceDeclaration')
        errors = self.complete_augmentations(containing_entity, relationship_declaration,
                                             'interfaces', interface_validator)
        for interface_name, interface_declaration in (getattr(relationship_declaration, 'interfaces', None) or {}).items():
            if interface_name in errors:
                # The outer merge failed, so there is nothing complete for
                # the refinements inside it to be checked against
                continue
            try:
                nested = interface_validator.complete_refinements(interface_declaration)
                if nested:
                    self.add_line_number(nested, interface_declaration)
                    errors[interface_name] = nested
            except Exception as e:
                logger.error("'%s': error while completing interface '%s': %s",
                             relationship_declaration.name, interface_name, e)
                errors[interface_name] = "validation error ({0})".format(e)
        return errors


    def validate_for_type(self, requirement_declaration: object, relationship_declaration: object) -> dict:
        """Check if a requirement declaration has a valid relationship
        declaration

        Args: 
          node_type(ToscaNodeType): node type for which to validate
            the requirement declaration
          requirement_declaration(ToscaRequirement): Tosca requirement
            declaration to validate
        """

        # Is this a valid declaration. This will check type and
        # property augmentations
        validation_errors =  super(ToscaManagedDeclarationValidator, 
                                   self).validate_for_type(requirement_declaration,
                                                           relationship_declaration)

        # Does this declaration have valid interface augmentations?
        # 'complete_interface_refinements' checked and merged them before
        # validation began.
        validator = get_validator('ToscaInterfaceDeclaration')
        errors = self.validate_augmentations(requirement_declaration,
                                             relationship_declaration,
                                             'interfaces', validator)
        if errors:
            logger.error("%s: relationship has invalid interface augmentations",
                         requirement_declaration.name)
            validation_errors['interfaces'] = errors

        # Everything OK
        return validation_errors
