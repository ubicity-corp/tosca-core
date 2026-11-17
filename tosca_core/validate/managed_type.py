"""
ToscaManagedTypeValidator class
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2014-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger = logging.getLogger(__name__)

# Validator support
from . import get_validator

# Types on which this validator depends
from .type import ToscaTypeValidator


class ToscaManagedTypeValidator(ToscaTypeValidator):
    """The ToscaManagedTypeValidator class validates TOSCA managed type
    definitions. It checks to make sure any interface declarations are
    valid.
    """

    def __init__(self) -> None:
        """Constructor
        """
        super(ToscaManagedTypeValidator, self).__init__()


    def complete_type_refinements(self, managed_type: object) -> dict:
        """Check and complete a managed type's refinements: its property
        and attribute refinements, as for any type, and then its interface
        declarations -- each one that refines a declaration the type
        inherits, and then the refinements inside every interface
        declaration, which find what they refine through the declaration's
        interface type and so come after the merge that gives a refining
        declaration its type. Node and relationship types are the only
        kinds that declare interfaces.

        'validate_type_specifics' then validates the completed
        declarations without checking or merging them again.

        Args:
          managed_type(ToscaManagedType): managed type whose refinements
            to complete

        Returns:
          (possibly empty) dict of validation errors, keyed the way
          'validate_type_specifics' keys them
        """
        errors = super(ToscaManagedTypeValidator, self).complete_type_refinements(managed_type)

        interface_validator = get_validator('ToscaInterfaceDeclaration')
        interface_errors = self.complete_declarations(managed_type, 'interfaces',
                                                      interface_validator)
        for interface_name, interface_declaration in (getattr(managed_type, 'interfaces', None) or {}).items():
            if interface_name in interface_errors:
                # The outer merge failed, so there is nothing complete for
                # the refinements inside it to be checked against
                continue
            try:
                nested = interface_validator.complete_refinements(interface_declaration)
                if nested:
                    self.add_line_number(nested, interface_declaration)
                    interface_errors[interface_name] = nested
            except Exception as e:
                logger.error("Managed type '%s': error while completing interface '%s': %s",
                             managed_type.name, interface_name, e)
                interface_errors[interface_name] = "validation error ({0})".format(e)
        if interface_errors:
            errors['interfaces'] = interface_errors
        return errors


    def validate_type_specifics(self, managed_type: object) -> dict:
        """Validate definitions that are specific to a managed type
        definition:

        - Call 'validate_type_specifics' for the parent type
        - Make sure the managed type has valid artifacts
        - Make sure the managed type has valid interface declarations,
          which 'complete_type_refinements' has already checked and
          completed

        Artifacts are validated before interfaces because an operation's
        implementation may name one, and that name is resolved against
        the type's artifacts as the interface is validated. The two are
        kept together here, where every type that declares interfaces
        passes through, so no type has to order them for itself.

        Args:
          managed_type(ToscaManagedType): managed type definition to
            validate
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None

        """

        # Is this a valid type entity?
        validation_errors = super(ToscaManagedTypeValidator,
                                  self).validate_type_specifics(managed_type)

        # Validate artifacts, which interfaces resolve implementations
        # against
        errors = self.validate_artifacts(managed_type)
        if errors:
            logger.error("Managed type '%s': invalid artifact declarations",
                         managed_type.name)
            validation_errors['artifacts'] = errors

        # Validate interfaces
        validator = get_validator('ToscaInterfaceDeclaration')
        errors = self.validate_declarations(managed_type,
                                            'interfaces', validator)
        if errors:
            logger.error("Managed type '%s': invalid interfaces declaration",
                         managed_type.name)
            validation_errors['interfaces'] = errors

        # Everything valid
        return validation_errors


    def validate_artifacts(self, managed_type: object) -> dict:
        """Check if a managed type has valid artifacts.

        Only node types declare artifacts today, so a type that declares
        none has nothing to validate.

        Args:
          managed_type(ToscaManagedType): Tosca managed type that
            includes the artifacts to validate
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """

        # Validate each artifact
        validator = get_validator('ToscaArtifact')
        validation_errors = {}
        for artifact_name, artifact in (getattr(managed_type, 'artifacts', None) or {}).items():

            logger.debug("Managed type '%s': validating artifact '%s'",
                         managed_type.name, artifact_name)

            # Is this a valid artifact
            errors = validator.validate_typed_template(artifact)
            if errors:
                logger.error("Managed type '%s': invalid artifact '%s'",
                             managed_type.name, artifact_name)
                if isinstance(errors, dict):
                    self.add_line_number(errors, artifact)
                validation_errors[artifact_name] = errors

        # All done
        return validation_errors
