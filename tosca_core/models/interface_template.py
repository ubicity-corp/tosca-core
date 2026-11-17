"""
Module definining Tosca Interface Entity
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

# Database support
from tosca_core import db

# SQL Alchemy support
from sqlalchemy.orm.collections import attribute_mapped_collection

# Types on which this instance depends
import tosca_core.models.template

# Types used in relationships
import tosca_core.models.operation_template


class ToscaInterfaceTemplate(tosca_core.models.template.ToscaTemplate):
    """A ToscaInterfaceTemplate object defines a named interface template
    that can be associated with a Node or Relationship Template
    """

    ################################################################################
    # Polymorphic mapping 
    ################################################################################

    __mapper_args__ = {
        'polymorphic_identity':'interface',
    }

    ################################################################################
    # Fields
    ################################################################################

    # Optional fields start with '_' and have corresponding getters
    # and setters to ensure that retrieving fields consistently raises
    # an AttributeError when not set.  Note that 'nullable' defaults
    # to True, but we explicitly set the 'nullable' flag for clarity.

    _inputs =       db.Column(db.PickleType, nullable=True)
    _outputs =      db.Column(db.PickleType, nullable=True)

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

    operations =    db.relationship('ToscaOperationTemplate',
                                    collection_class=attribute_mapped_collection('name'),
                                    primaryjoin="and_(ToscaInterfaceTemplate.id==ToscaOperationTemplate._containing_interface_id,"
                                    "ToscaOperationTemplate.role=='OPERATION')",
                                    back_populates='containing_interface',
                                    cascade='all',
                                    overlaps='notifications')
    
    notifications = db.relationship('ToscaOperationTemplate',
                                    collection_class=attribute_mapped_collection('name'),
                                    primaryjoin="and_(ToscaInterfaceTemplate.id==ToscaOperationTemplate._containing_interface_id,"
                                    "ToscaOperationTemplate.role=='NOTIFICATION')",
                                    back_populates='containing_interface',
                                    cascade='all',
                                    overlaps='operations')

    declaration =  db.relationship('ToscaInterfaceDeclaration',
                                    back_populates='templates',
                                    overlaps='_declaration,templates')

    ################################################################################
    # Constructor
    ################################################################################

    def __init__(self,
                 inputs: Optional[dict[str, Any]] = None,
                 outputs: Optional[dict[str, Any]] = None,
                 operations: Optional[dict[str, Any]] = None,
                 notifications: Optional[dict[str, Any]] = None,
                 **kwargs: Any
    ) -> None:
        """Instantiate a new ToscaInterfaceTemplate instance"""

        # First, call superclass constructor
        super(ToscaInterfaceTemplate, self).__init__(**kwargs)

        # ToscaInterfaceTemplate-specific initialization.
        if inputs: self.inputs = inputs
        if outputs: self.outputs = outputs
        if operations: self.operations = operations
        if notifications: self.notifications = notifications


    ################################################################################
    # Sub-entity retrieval functions. Sub-entities are retrieved from
    # this declaration as well as from its types
    ################################################################################

    def get_operation_implementation(self, operation_name: str) -> list[Any]:
        """Return the list of implementation artifacts for the operation
        specified by 'operation_name'. If we don't find a local
        implementation here, we query our interface declaration

        Args:
          operation_name(str): name of the operation for which to
            return an implementation

        Returns:
          (possibly empty) list of ToscaArtifact

        Raises:
          None
        """
        # Does this interface template define the operation
        # implementation?
        try:
            artifacts = self.operations[operation_name].artifacts
            if artifacts: return artifacts
        except (AttributeError, KeyError) as e:
            pass
        
        # No implementation in the interface template itself. Get
        # implementation from the interface declaration
        return self.declaration.get_operation_implementation(operation_name)


    def get_notification_implementation(self, notification_name: str) -> Any:
        """Return the implementation artifact for the notification specified by
        'notification_name'. If we don't find a local implementation
        here, we query our interface declaration

        Args:
          notification_name(str): name of the notification for which to
            return an implementation

        Raises:
          KeyError: if no notification template is defined for the
            specified notification name
          AttributeError: if no implementation is found
        """
        # Does this interface template define the notification
        # implementation?
        try:
            notification = self.notifications[notification_name]
            return notification.implementation
        except (AttributeError, KeyError) as e:
            # No implementation in the interface template itself. Get
            # implementation from the interface declaration
            return self.declaration.get_notification_implementation(notification_name)


    ################################################################################
    # Template refinement support
    ################################################################################

    def complete_template_refinement(self, interface: ToscaInterfaceTemplate) -> None:
        """Override a interface with values from a second interface"""

        # First, call superclass augment method
        super(ToscaInterfaceTemplate, self).complete_template_refinement(interface)

        # Then augment inputs
        self.merge_augmented_inputs(interface)

        # Then augment outputs
        self.merge_augmented_outputs(interface)

        # Augment operations
        self.merge_augmented_operations(interface)


    def merge_augmented_inputs(self, interface: ToscaInterfaceTemplate) -> None:
        try:
            if not interface.inputs:
                # Augmented instance does not have inputs. Nothing
                # further to do.
                return
        except AttributeError:
            # Augmenting entity does not have a 'inputs'
            # attribute. Nothing further to do.
            return

        # Copy inputs dict
        inputs = dict(interface.inputs)

        # Add in our own inputs
        try:
            if self.inputs:
                inputs.update(self.inputs)
        except AttributeError:
            # We don't have inputs list. Nothing to do
            pass
        except Exception as e:
            logger.error("Instance <%s>: error augmenting inputs: %s",
                         self.name, e)
        # Update
        self.inputs = inputs


    def merge_augmented_outputs(self, interface: ToscaInterfaceTemplate) -> None:
        try:
            if not interface.outputs:
                # Augmented instance does not have outputs. Nothing
                # further to do.
                return
        except AttributeError:
            # Augmenting entity does not have a 'outputs'
            # attribute. Nothing further to do.
            return

        # Copy outputs dict
        outputs = dict(interface.outputs)

        # Add in our own outputs
        try:
            if self.outputs:
                outputs.update(self.outputs)
        except AttributeError:
            # We don't have outputs list. Nothing to do
            pass
        except Exception as e:
            logger.error("Instance <%s>: error augmenting outputs: %s",
                         self.name, e)
        # Update
        self.outputs = outputs


    def merge_augmented_operations(self, interface: ToscaInterfaceTemplate) -> None:
        # Does the augmented instance have operations?
        try:
            if not interface.operations:
                # No operations to augment
                return
        except AttributeError:
            # No operations to augment
            return

        # Augment operations as necessary
        operations_to_merge = {}
        for operation_name, augmented_operation in interface.operations.items():
            # Is this a instance that must be augmented?
            try:
                operation = self.operations[operation_name]
                operation.complete_template_refinement(augmented_operation)
            except (AttributeError, KeyError):
                # We don't have this operation
                merged_operation = tosca_core.models.operation_template.ToscaOperationTemplate(
                    name=operation_name,role='OPERATION')
                merged_operation.complete_template_refinement(augmented_operation)
                operations_to_merge[operation_name] = merged_operation

        # Merge operations
        try:
            if self.operations:
                operations_to_merge.update(self.operations)
        except AttributeError:
            # Don't have operations or operations set to None
            pass

        # Set merged operations
        self.operations = operations_to_merge




        
