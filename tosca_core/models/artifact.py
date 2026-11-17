"""
Module defining Tosca Artifact entity
"""
from __future__ import annotations

__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2015-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Typing support
from typing import Any, Optional

# Logging support
import logging
logger: logging.Logger = logging.getLogger(__name__)

# OS support
import os

# Checksums
import hashlib

# Database support
from tosca_core import db

# Types on which this instance depends
import tosca_core.models.template

# Types used in relationships
import tosca_core.models.artifact_declaration
import tosca_core.models.csar_repository
import tosca_core.models.exceptions as te


################################################################################
# Checksums (TOSCA 2.0 §12.2)
################################################################################

# SHAKE digests take a length and name no single checksum, so they are left out.
_CHECKSUM_ALGORITHMS = sorted(name for name in hashlib.algorithms_guaranteed
                              if not name.startswith('shake'))


def checksum_algorithm_name(name: str) -> str:
    """Return hashlib's name for the checksum algorithm a template names.

    Case and hyphens do not matter, so 'SHA-256', 'sha256' and 'SHA3-256'
    are accepted. A bare 'SHA', which §12.2 gives as an example, names no
    particular algorithm and is refused.

    Raises:
      ValueError: when the name is not an algorithm the orchestrator has
    """
    normalized = str(name).strip().lower().replace('-', '').replace('_', '')
    if normalized.startswith('sha3') and len(normalized) > 4:
        normalized = 'sha3_' + normalized[4:]
    if normalized not in _CHECKSUM_ALGORITHMS:
        raise ValueError(
            f"checksum algorithm '{name}' is not supported; use one of MD5, SHA-1, "
            f"SHA-224, SHA-256, SHA-384, SHA-512, SHA3-224, SHA3-256, SHA3-384, "
            f"SHA3-512, BLAKE2b or BLAKE2s")
    return normalized


def file_checksum(path: str, algorithm: str) -> str:
    """Return the hex digest of the file at 'path' under hashlib's
    'algorithm'."""
    digest = hashlib.new(algorithm)
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 16), b''):
            digest.update(chunk)
    return digest.hexdigest()


def check_checksum(path: str, checksum: str, algorithm: str) -> None:
    """Check the file at 'path' against a hex 'checksum' computed with
    'algorithm', as a template names it. Case does not matter.

    Raises:
      ValueError: when the algorithm is not supported or the file does not
        match
    """
    name = checksum_algorithm_name(algorithm)
    actual = file_checksum(path, name)
    if actual.lower() != str(checksum).strip().lower():
        raise ValueError(
            f"'{os.path.basename(path)}' does not match its checksum: its {algorithm} "
            f"is {actual}, and the artifact gives {checksum}")


class ToscaArtifact(tosca_core.models.template.ToscaTemplate):
    """Tosca artifact  class

    A ToscaArtifact specifies a named artifact of a given artifact
    type.
    """

    ################################################################################
    # Polymorphic mapping
    ################################################################################

    __mapper_args__ = {
        'polymorphic_identity':'artifact',
    }


    ################################################################################
    # Keys
    ################################################################################
    
    # Foreign keys
    _repo_id =                  db.Column(db.Integer, 
                                          db.ForeignKey('tosca_repository.id'),
                                          nullable=True)
    _containing_type_id =       db.Column(db.Integer, 
                                          db.ForeignKey('tosca_type.id'),
                                          nullable=True)
    _operation_template_id =    db.Column(db.Integer,
                                          db.ForeignKey('tosca_operation_template.id'),
                                          nullable=True)
    _operation_declaration_id = db.Column(db.Integer,
                                          db.ForeignKey('tosca_operation_declaration.id'),
                                          nullable=True)
    _workflow_template_id =     db.Column(db.Integer,
                                          db.ForeignKey('tosca_workflow_template.id'),
                                          nullable=True)
    _signature_id =             db.Column(db.Integer,
                                          db.ForeignKey('tosca_signature.id'),
                                          nullable=True)

    ################################################################################
    # Fields
    ################################################################################

    # Track whether this artifact is a copy of an artifact defined in
    # a node type or node template (in which case we need to use the
    # node context to evaluate artifact properties).
    is_copy =                         db.Column(db.Boolean, default=False)

    ################################################################################
    # Relationships
    ################################################################################

    # Every artifact has a repository
    repo =               db.relationship('ToscaRepository',
                                          uselist=False,
                                          foreign_keys='ToscaArtifact._repo_id',
                                          overlaps='templates')

    @property
    def repository(self) -> str:
        return self.repo.name

    
    ################################################################################
    # Fields
    ################################################################################

    # Optional fields start with '_' and have corresponding getters
    # and setters to ensure that retrieving fields consistently raises
    # an AttributeError when not set.  Note that 'nullable' defaults
    # to True, but we explicitly set the 'nullable' flag for clarity.
    _file =               db.Column(db.String, nullable=True)
    _deploy_path =        db.Column(db.String, nullable=True)
    _artifact_version =   db.Column(db.String, nullable=True)    
    _checksum =           db.Column(db.String, nullable=True)
    _checksum_algorithm = db.Column(db.String, nullable=True)

    @property
    def file(self) -> str:
        if not self._file:
            raise AttributeError("'{0}' does not have 'file'".format(self.name))
        return self._file

    @property
    def deploy_path(self) -> str:
        if not self._deploy_path:
            raise AttributeError("'{0}' does not have 'deploy_path'".format(self.name))
        return self._deploy_path

    @property
    def artifact_version(self) -> str:
        if not self._artifact_version:
            raise AttributeError("'{0}' does not have 'artifact_version'".format(self.name))
        return self._artifact_version

    @property
    def checksum(self) -> str:
        if not self._checksum:
            raise AttributeError("'{0}' does not have 'checksum'".format(self.name))
        return self._checksum

    @property
    def checksum_algorithm(self) -> str:
        if not self._checksum_algorithm:
            raise AttributeError("'{0}' does not have 'checksum_algorithm'".format(self.name))
        return self._checksum_algorithm


    ################################################################################
    # Implementation of reserved keywords
    ################################################################################

    @property
    def service(self) -> Any:
        """Artifacts are templates, which means they normally get their
        service from the 'containing_template'. However, artifacts
        can be contained by an operation template, which is not a
        subclass of ToscaTemplate, so we need to check the containing
        template as well.
        """
        if self._containing_operation_template:
            return self._containing_operation_template.service
        return super(ToscaArtifact, self).service
    
        
    def SELF(self) -> Any:
        """Return the declaration for the entity referred to by SELF for this
        artifact.

        Returns:
          ToscaManagedDeclaration

        Raises:
          ModelCorruptionError: when containing_template is 'None'
        """
        if self._containing_type:
            return self._containing_type.SELF()
        elif self._containing_operation_declaration:
            return self._containing_operation_declaration.SELF()
        elif self._containing_operation_template:
            return self._containing_operation_template.SELF()
        elif self._containing_workflow:
            return self._containing_workflow.SELF()
        elif self._containing_signature:
            # Function-implementation artifacts have no SELF: there is
            # no node / relationship / interface context.
            raise AttributeError(
                "Function-implementation artifact '{0}' has no SELF context".format(
                    self.name))
        else:
            return super(ToscaArtifact, self).SELF()

        
    ################################################################################
    # Model navigation
    ################################################################################

    # Artifacts are the only templates that can be contained by a type
    _containing_type =   db.relationship('ToscaManagedType',
                                         uselist=False,
                                         foreign_keys='ToscaArtifact._containing_type_id')

    @property
    def profile(self) -> Any:
        """Get profile. Artifacts can obtain their profile from the
        containing node type, from the containing operation
        declaration, from the containing node template, from the
        containing operation template, from the containing workflow,
        or from the containing function signature. Note that the
        _containing_operation_declaration,
        _containing_operation_template, _containing_workflow, and
        _containing_signature relationships are created as a
        'backref' and not defined here.
        """
        if self._containing_type:
            return self._containing_type.profile
        elif self._containing_operation_declaration:
            return self._containing_operation_declaration.profile
        elif self._containing_operation_template:
            return self._containing_operation_template.profile
        elif self._containing_workflow:
            return self._containing_workflow.profile
        elif self._containing_signature:
            return self._containing_signature.profile
        else:
            return super(ToscaArtifact, self).profile

    def create_declaration(self) -> Any:
        """Synthesize a ToscaDeclaration object for this instance. This
        overrides the 'create_declaration' method in the base class,
        since for some artifacts, we may need to get the type from the
        file extension rather than from a _type attribute.

        Returns:
          Entity that is the appropriate subclass of ToscaDeclaration
          with its name and type attributes initialized. No other
          attributes are initialized.
        """

        # First, try the base class
        try:
            return super(ToscaArtifact, self).create_declaration()
        except AttributeError:
            # No type defined. Try to determine artifact type based on
            # the file extension.
            pass

        # Only TOSCA 1.3 determines an artifact's type from its file
        # extension. A TOSCA 2.0 artifact must name its type (section
        # 12.2); one that does not is left without a declaration, so it
        # takes the type of the artifact it refines, if any, and its
        # validation otherwise reports that it does not name its type.
        version = getattr(self.profile, 'tosca_version', None) or ''
        if not version.startswith('tosca_simple_yaml'):
            raise te.TypeNotNamed("does not name its type")

        # Get file extension
        ext = self.get_file_ext()
        if ext:
            try:
                artifact_types = self.profile.get_artifact_types_for_ext(ext)
                if len(artifact_types) == 1:
                    # Create declaration for this type
                    return artifact_types[0].create_declaration(self.name)
                else:
                    error = "Artifact '{0}' has multiple types for extension '{1}'".format(
                        self.name, ext)
            except Exception as e:
                logger.error("Unable to get artifact type for '%s': %s", ext, str(e))
                raise AttributeError(str(e))
        else:
            # No file extension, so can't determine type
            error = "Artifact '{0}' no file extension from which to determine type".format(
                self.name)

        # No type from which to create declaration. Raise error
        raise AttributeError(error)


    ################################################################################
    # Constructor
    ################################################################################

    def __init__(self,
                 type: Optional[str] = None,
                 repository: Optional[str] = None,
                 file: Optional[str] = None,
                 deploy_path: Optional[str] = None,
                 artifact_version: Optional[str] = None,
                 checksum: Optional[str] = None,
                 checksum_algorithm: Optional[str] = None,
                 **kwargs: Any
    ) -> None:
        # First, call superclass constructor
        super(ToscaArtifact, self).__init__(**kwargs)

        # ToscaArtifact-specific initialization
        self.type = type
        if repository: self._repository = repository
        if file: self._file = file
        if deploy_path: self._deploy_path = deploy_path
        if artifact_version: self._artifact_version = artifact_version
        if checksum: self._checksum = checksum
        if checksum_algorithm: self._checksum_algorithm = checksum_algorithm


    def retrieve(self) -> str:
        """Return a local copy of the artifact's file, fetched from its
        repository and, when the artifact gives a checksum, checked against
        it (§12.2).

        Raises:
          IOError: when the file cannot be retrieved
          ValueError: when the file does not match its checksum
        """
        local_file = self.repo.retrieve(self.file)
        if self._checksum:
            if not self._checksum_algorithm:
                raise ValueError(f"artifact '{self.name}' gives a checksum "
                                 f"without a checksum_algorithm")
            check_checksum(local_file, self._checksum, self._checksum_algorithm)
        return local_file


    def get_file_ext(self) -> str:
        """Get extension of the file of the artifact"""

        # Split file name
        filename, file_extension = os.path.splitext(self.file)
        # Remove leading '.'
        if file_extension: file_extension = file_extension[1:]
        return file_extension


    ################################################################################
    # Template refinement support
    ################################################################################

    def complete_template_refinement(self, source_artifact: Any) -> None:
        """Complete a refining template with definitions from the source
        template that it refines.
        """

        # First, call superclass augment method
        super(ToscaArtifact, self).complete_template_refinement(source_artifact)

        # Merge fields we don't already have
        if source_artifact.repo:
            self.repo = source_artifact.repo
        else:
            self.merge_augmented_field('_repo_id', source_artifact)
        self.merge_augmented_field('_file', source_artifact)
        self.merge_augmented_field('_deploy_path', source_artifact)
        self.merge_augmented_field('_artifact_version', source_artifact)
        self.merge_augmented_field('_checksum', source_artifact)
        self.merge_augmented_field('_checksum_algorithm', source_artifact)
