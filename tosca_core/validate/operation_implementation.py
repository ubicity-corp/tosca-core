"""
ToscaOperationImplementationValidator class
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2017-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger = logging.getLogger(__name__)

# Type hint support
from typing import Any

# Validator support
from . import get_validator

# What an embedding application adds to validation
from tosca_core import extensions


class ToscaOperationImplementationValidator(object):
    """The ToscaOperationImplementationValidator class validates operation
    implementations defined in operation templates or operation
    declarations
    """

    def __init__(self) -> None:
        """Constructor
        """
        super(ToscaOperationImplementationValidator, self).__init__()


    def validate_implementation(self, operation: "Any", declaration: "Any" = None) -> dict:
        """Check if an interface definition has a valid implementation
        for the specified operation

        Args: 
          operation(ToscaOperationDeclaration or ToscaOperationTemplate):
            operation entity for which to validate implementation
          declaration(ToscaOperationDeclaration): the operation's
            declaration, where operation is a template; a declaration is its
            own
        """

        validation_errors = {}

        # An operation implementation consists of a list of
        # artifacts. Validate each artifact.
        for artifact in operation.artifacts:
            errors = self.validate_artifact(operation, artifact, declaration or operation)
            if errors:
                logger.error("Operation %s: Invalid implementation artifact [%s]", 
                             operation.name, str(artifact.position))
                validation_errors[str(artifact.position)] = errors

        # Everything OK
        return validation_errors


    def validate_artifact(self, operation: "Any", artifact: "Any", declaration: "Any" = None) -> dict:
        """Check if an interface definition has a valid implementation
        artifact for the specified operation

        Args: 
          operation_declaration(ToscaOperationDeclaration):
            declaration of the Tosca operations that have the
            implementation to validate
          operation(ToscaOperationTemplate): operation entity for which to
            validate implementation
          artifact(ToscaArtifact): implementation artifact to validate
        """

        # If this artifact has previously been validated (e.g. in the
        # case of an operation refinement) there is nothing further to
        # do. We can check if an artifact is fully validated by
        # checking if it has a valid repository.
        if artifact.repo:
            logger.debug("Operation %s: implementation '%s' is already validated",
                         operation.name, artifact.file)
            return {}

        # Make sure this artifact has a name.
        artifact.name = operation.name + "_implementation_" + str(artifact.position)
        logger.debug("Operation %s: Validating implementation artifact '%s' with file '%s'", 
                     operation.name, artifact.name, artifact.file)

        # First, check to see if this is a reference to an artifact
        # defined in the node template or node type
        referenced_artifact = self.get_referenced_artifact(operation, artifact)
        if referenced_artifact:
            # Copy the referenced artifact as the implementation
            # artifact. Make sure to clear the "file" field first to
            # make sure it gets copied from the referenced artifact.
            artifact._file = None
            artifact.complete_template_refinement(referenced_artifact)
            artifact.is_copy = True
            # The copy is what runs, so it is checked against the named
            # artifact's checksum when its file is fetched.
            artifact._checksum = referenced_artifact._checksum
            artifact._checksum_algorithm = referenced_artifact._checksum_algorithm
            # Nothing further to validate but the application's checks.
            return self.check_implementation(artifact, referenced_artifact,
                                             operation, declaration)

        # Validate inline artifact definition
        validator = get_validator('ToscaArtifact')
        errors = validator.validate_typed_template(artifact)
        if errors:
            return errors
        return self.check_implementation(artifact, None, operation, declaration)


    def check_implementation(self, artifact: "Any", referenced_artifact: "Any" = None,
                             operation: "Any" = None, declaration: "Any" = None) -> dict:
        """Run the embedding application's implementation checks on an
        implementation artifact (tosca_core.extensions), so what it cannot
        run is reported when the profile or service template is onboarded
        rather than when the operation or function runs. An artifact of any
        type is valid TOSCA: with no checks registered there is nothing to
        refuse.

        Args:
          artifact(ToscaArtifact): implementation artifact to check
          referenced_artifact(ToscaArtifact): the node artifact the
            implementation names, where it names one
          operation, declaration: the operation the artifact implements and
            its declaration; None for a function's implementation

        Returns:
          (possibly empty) dict of validation errors
        """
        checks = extensions.implementation_checks()
        if not checks:
            return {}

        type_entity = None
        for candidate in (artifact, referenced_artifact):
            if candidate is None:
                continue
            try:
                type_entity = candidate.declaration.type_entity
                break
            except Exception:
                continue
        if type_entity is None:
            # The artifact's own validation reports a type it cannot resolve.
            return {}

        errors = {}
        for check in checks:
            errors.update(check(artifact, type_entity.qualified_name, operation, declaration) or {})
        return errors


    def get_referenced_artifact(self, operation: "Any", artifact: "Any") -> "Any":
        """Check if an interface definition has a valid implementation
        for the specified operation

        Args: 
          operation(ToscaOperationTemplate): operation entity for which to
            get referenced artifact
          artifact(ToscaArtifact): artifact definition that contains
            the artifact reference

        Returns:
          ToscaArtifact: artifact that is referenced by the artifact
            parameter
          None: if there is no valid reference

        Raises:
          None
        """

        # Is artifact structured as a valid artifact reference?
        try:
            type = artifact._type
            # Artifact references don't have a type attribute. This
            # must be a real artifact definition.
            return None
        except AttributeError:
            pass
        try:
            repository = artifact._repository
            # Artifact references must not have repository attribute
            return None
        except AttributeError:
            pass
        # Referenced artifacts also don't define properties.
        if artifact.properties: return None

        # Should we check if file attribute is structured as a URL?
        try:
            artifact_name = artifact.file
        except AttributeError:
            # No file attribute. 
            return None

        # This could potentially be a valid artifact reference: an artifact
        # of the node type or node template that contains the operation
        # (TOSCA 2.0 §11.8), which for a relationship operation is the node
        # whose requirement it is written in.
        try:
            return operation.SELF().get_implementation_artifact(artifact_name)
        except (AttributeError, KeyError):
            # No such artifact
            return None


def operation_output_names(operation: "Any", declaration: "Any" = None) -> list:
    """The names of the outputs an operation's implementation returns: those
    its declaration and its interface declare, and those a template maps.

    Args:
      operation: the operation declaration or template
      declaration: the operation's declaration, where operation is a
        template; a declaration is its own
    """
    names = []
    declaration = declaration or operation
    sources = (declaration,
               getattr(declaration, '_containing_interface_declaration', None),
               getattr(declaration, '_containing_interface_type', None))
    for source in sources:
        try:
            names.extend(source.get_output_declarations())
        except Exception:
            continue
    try:
        names.extend(operation.outputs or {})
    except Exception:
        pass
    return list(dict.fromkeys(names))


def operation_input_names(operation: "Any", declaration: "Any" = None) -> list:
    """The names of the inputs an operation's implementation receives: those
    its declaration and its interface declare, and those a template assigns.

    Args:
      operation: the operation declaration or template
      declaration: the operation's declaration, where operation is a
        template; a declaration is its own
    """
    names = []
    declaration = declaration or operation
    sources = (declaration,
               getattr(declaration, '_containing_interface_declaration', None),
               getattr(declaration, '_containing_interface_type', None))
    for source in sources:
        try:
            names.extend(source.get_input_declarations())
        except Exception:
            continue
    try:
        names.extend(operation.inputs or {})
    except Exception:
        pass
    return list(dict.fromkeys(names))
