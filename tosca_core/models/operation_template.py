"""
Module definining Tosca Operation entity
"""
from __future__ import annotations

__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2014-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Type hints
from typing import Any, Optional

# Logging support
import logging
logger: logging.Logger = logging.getLogger(__name__)

# SQL Alchemy support
from sqlalchemy.orm import backref
from sqlalchemy.ext.orderinglist import ordering_list

# Database support
from tosca_core import db

# Support for shared TOSCA keynames
import tosca_core.models.entity
import tosca_core.models.artifact
 
# Exception support
import tosca_core.models.exceptions as te


class ToscaOperationTemplate(tosca_core.models.entity.ToscaEntityMixin, db.Model):
    """A ToscaOperationTemplate object specifies a named operation
    template defined in a Tosca interface template.
    """

    ################################################################################
    # Keys
    ################################################################################
    
    # Primary key
    id =            db.Column(db.Integer, primary_key=True)

    # Foreign keys
    _containing_interface_id = db.Column(db.Integer, 
                                         db.ForeignKey('tosca_template.id'),
                                         nullable=True)

    ################################################################################
    # Fields
    ################################################################################

    # Optional fields start with '_' and have corresponding getters
    # and setters to ensure that retrieving fields consistently raises
    # an AttributeError when not set.  Note that 'nullable' defaults
    # to True, but we explicitly set the 'nullable' flag for clarity.

    role =                     db.Column(db.Enum('OPERATION', 'NOTIFICATION', name='role'))
    _inputs =                  db.Column(db.PickleType, nullable=True)
    _outputs =                 db.Column(db.PickleType, nullable=True)

    @property
    def inputs(self) -> dict[str, Any]:
        if self._inputs == None: self._inputs = dict()
        return self._inputs

    @inputs.setter
    def inputs(self, value: Optional[dict[str, Any]]) -> None:
        self._inputs = value

    @property
    def outputs(self) -> dict[str, Any]:
        if self._outputs == None: self._outputs = dict()
        return self._outputs

    @outputs.setter
    def outputs(self, value: Optional[dict[str, Any]]) -> None:
        self._outputs = value

    ################################################################################
    # Relationships
    ################################################################################

    artifacts =                db.relationship('ToscaArtifact',
                                               foreign_keys='ToscaArtifact._operation_template_id',
                                               collection_class=ordering_list('position'),
                                               order_by='ToscaArtifact.position',      
                                               backref=backref('_containing_operation_template', uselist=False),
                                               cascade='all')

    ################################################################################
    # Model Navigation
    ################################################################################

    containing_interface =     db.relationship('ToscaInterfaceTemplate',
                                               foreign_keys='ToscaOperationTemplate._containing_interface_id')

    @property
    def service(self) -> Any:
        try:
            return self.containing_interface.service
        except AttributeError:
            # No containing template
            error = "Unable to retrieve 'service' for {}: no containing interface template".format(self.name)
            raise te.ModelCorruptionError(error)


    @property
    def profile(self) -> Any:
        """Get profile from the containing interface.
        """
        if self.containing_interface:
            return self.containing_interface.profile
        else:
            error = "No profile found for operation '{0}'".format(self.name)
            raise te.ModelCorruptionError(error)

    @property
    def tosca_version(self) -> str:
        """Get tosca version from the profile.
        """
        return self.profile.tosca_version

    ################################################################################
    # Implementation of reserved keywords
    ################################################################################

    def SELF(self) -> Any:
        """Return the declaration for the entity referred to by SELF for this
        operation template. SELF refers to node templates or
        relationship templates only. Operation templates retrieve SELF
        from their containing interface template

        Returns:
          ToscaManagedDeclaration

        Raises:
          ModelCorruptionError: when containing_interface is 'None'
        """
        try:
            return self.containing_interface.SELF()
        except AttributeError:
            # No containing interface template
            error = "Unable to retrieve SELF for {}: no containing interface template".format(self.name)
            raise te.ModelCorruptionError(error)


    def SOURCE(self) -> Any:
        """Return the declaration for the entity referred to by SOURCE for
        this operation template. SOURCE refers to relationship
        templates only. Operation templates retrieve SOURCE from their
        containing interface template.

        Returns:
          ToscaNodeDeclaration

        Raises:
          ModelCorruptionError: when containing_interface is 'None'
        """
        try:
            return self.containing_interface.SOURCE()
        except AttributeError:
            # No containing interface template
            error = "Unable to retrieve SOURCE for {}: no containing interface template".format(self.name)
            raise te.ModelCorruptionError(error)


    def TARGET(self) -> Any:
        """Return the declaration for the entity referred to by TARGET for
        this operation template. TARGET refers to relationship
        templates only. Operation templates retrieve TARGET from their
        containing interface template.

        Returns:
          ToscaNodeDeclaration

        Raises:
          ModelCorruptionError: when containing_interface is 'None'
        """
        try:
            return self.containing_interface.TARGET()
        except AttributeError:
            # No containing interface template
            error = "Unable to retrieve TARGET for {}: no containing interface template".format(self.name)
            raise te.ModelCorruptionError(error)


    ################################################################################
    # Constructor
    ################################################################################

    def __init__(self,
                 role: Optional[str] = None,
                 implementation: Optional[dict[str, Any]] = None,
                 inputs: Optional[dict[str, Any]] = None,
                 outputs: Optional[dict[str, Any]] = None,
                 **kwargs: Any
    ) -> None:
        """Instantiate a new ToscaOperationTemplate instance"""

        # First, call superclass constructor
        super(ToscaOperationTemplate, self).__init__(**kwargs)

        # ToscaOperationTemplate-specific initialization
        if role != None: self.role = role
        self.implementation = implementation
        self.inputs = inputs
        self.outputs = outputs

    # Jump through hoops to map TOSCA "operation implementation"
    # grammar onto the database schema
    @property
    def implementation(self) -> dict[str, Any]:
        if self.artifacts:
            implementation: dict[str, Any] = dict()
            implementation['primary'] = self.artifacts[-1]
            implementation['dependencies'] = self.artifacts[:-1]
        else:
            raise AttributeError("Operation {0} does not have 'implementation' attribute".format(self.name))
        return implementation

    @implementation.setter
    def implementation(self, value: Optional[dict[str, Any]]) -> None:
        # make sure implementation is specified
        if value == None: return
        # Extract primary and dependencies
        try:
            if value['dependencies']: self.artifacts = value['dependencies']
        except KeyError:
            pass
        try:
            if value['primary']: self.artifacts.append(value['primary'])
        except KeyError:
            pass


    ################################################################################
    # Template refinement support
    ################################################################################

    def complete_template_refinement(self, operation: ToscaOperationTemplate) -> None:
        """Augment a operation with values from a second operation"""

        logger.debug("Operation <%s>: augmenting", self.name)

        # Merge fields we don't already have
        self.merge_augmented_field('name', operation)
        self.merge_augmented_field('_description', operation)

        # Augment 'implementation'
        self.merge_augmented_implementation(operation)

        # Augment 'inputs'
        self.merge_augmented_inputs(operation)

        # Augment 'outputs'
        self.merge_augmented_outputs(operation)


    def merge_augmented_implementation(self, operation: ToscaOperationTemplate) -> None:
        """Complete a field in an augmentation by merging in the field from
        the declaration which it augments if necessary
        """

        # Is there anything to do?
        if self.artifacts or not operation.artifacts:
            # Artifacts already defined or nothing to merge
            return

        for artifact_to_copy in operation.artifacts:
            # Make a copy of the artifact to make sure all back
            # references are set up correctly.
            artifact = tosca_core.models.artifact.ToscaArtifact()
            artifact.complete_template_refinement(artifact_to_copy)
            self.artifacts.append(artifact)


    def merge_augmented_inputs(self, operation: ToscaOperationTemplate) -> None:
        try:
            if not operation.inputs:
                # Augmented operation does not have inputs. Nothing
                # further to do.
                return
        except AttributeError:
            # Augmenting entity does not have a 'inputs'
            # attribute. Nothing further to do.
            return

        # Copy inputs dict
        inputs = dict(operation.inputs)

        # Add in our own inputs
        try:
            if self.inputs:
                inputs.update(self.inputs)
        except AttributeError:
            # We don't have inputs list. Nothing to do
            pass
        except Exception as e:
            logger.error("Operation <%s>: error augmenting inputs: %s",
                         self.name, e)
        # Update
        self.inputs = inputs


    def merge_augmented_outputs(self, operation: ToscaOperationTemplate) -> None:
        try:
            if not operation.outputs:
                # Augmented operation does not have outputs. Nothing
                # further to do.
                return
        except AttributeError:
            # Augmenting entity does not have a 'outputs'
            # attribute. Nothing further to do.
            return

        # Copy outputs dict
        outputs = dict(operation.outputs)

        # Add in our own outputs
        try:
            if self.outputs:
                outputs.update(self.outputs)
        except AttributeError:
            # We don't have outputs list. Nothing to do
            pass
        except Exception as e:
            logger.error("Operation <%s>: error augmenting outputs: %s",
                         self.name, e)
        # Update
        self.outputs = outputs


    def merge_augmented_field(self, field_name: str, augmented_entity: ToscaOperationTemplate) -> None:
        """Complete a field in an augmentation by merging in the field from
        the declaration which it augments if necessary
        """

        # Do we already have this field?
        try:
            if getattr(self, field_name) != None:
                # Field already set. No need to merge
                return
        except AttributeError:
            pass

        # We don't yet have this field. Merge if possible
        try:
            field = getattr(augmented_entity, field_name)
            if field != None:
                setattr(self, field_name, field)
        except AttributeError:
            pass
