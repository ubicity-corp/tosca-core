"""
Module definining Tosca Interface declarations
"""
from __future__ import annotations

from typing import Any, Optional

__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2014-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger: logging.Logger = logging.getLogger(__name__)

# Database support
from tosca_core import db

# SQL Alchemy support
from sqlalchemy.orm.collections import attribute_mapped_collection

# Types on which this declaration depends
import tosca_core.models.declaration

# Types used in relationships
import tosca_core.models.property_declaration 
import tosca_core.models.operation_declaration 

class ToscaInterfaceDeclaration(tosca_core.models.declaration.ToscaDeclaration):
    """A ToscaInterfaceDeclaration object declares the presence of a
    named interface in a managed type definition (i.e. Node Type or
    Relationship Type) or in a declaration of a managed object
    (specifically a relationship template declaration)
    """

    ################################################################################
    # Polymorphic mapping
    ################################################################################

    __mapper_args__ = {
        'polymorphic_identity':'interface',
    }


    ################################################################################
    # Relationships
    ################################################################################

    inputs =        db.relationship('ToscaPropertyDeclaration',
                                    collection_class=attribute_mapped_collection('name'),
                                    primaryjoin="and_(ToscaInterfaceDeclaration.id=="
                                    "remote(ToscaPropertyDeclaration._containing_declaration_id),"
                                    "remote(ToscaPropertyDeclaration.role)=='INPUT')",
                                    back_populates='_containing_declaration',
                                    overlaps='outputs,attributes,properties,_contained_declarations')
    outputs =       db.relationship('ToscaPropertyDeclaration',
                                    collection_class=attribute_mapped_collection('name'),
                                    primaryjoin="and_(ToscaInterfaceDeclaration.id=="
                                    "remote(ToscaPropertyDeclaration._containing_declaration_id),"
                                    "remote(ToscaPropertyDeclaration.role)=='OUTPUT')",
                                    back_populates='_containing_declaration',
                                    overlaps='inputs,attributes,properties,_contained_declarations')
    operations =    db.relationship('ToscaOperationDeclaration',
                                    collection_class=attribute_mapped_collection('name'),
                                    primaryjoin="and_(ToscaInterfaceDeclaration.id=="
                                    "ToscaOperationDeclaration._interface_declaration_id,"
                                    "ToscaOperationDeclaration.role=='OPERATION')",
                                    back_populates='_containing_interface_declaration',
                                    cascade='all',
                                    overlaps='notifications')
    notifications = db.relationship('ToscaOperationDeclaration',
                                    collection_class=attribute_mapped_collection('name'),
                                    primaryjoin="and_(ToscaInterfaceDeclaration.id=="
                                    "ToscaOperationDeclaration._interface_declaration_id,"
                                    "ToscaOperationDeclaration.role=='NOTIFICATION')",
                                    back_populates='_containing_interface_declaration',
                                    cascade='all',
                                    overlaps='operations')
    # This relationship's collection should not be modified directly. Its only purpose is to
    # provide a cascade path for deleting child objects.
    templates =     db.relationship('ToscaInterfaceTemplate',
                                    back_populates='declaration',
                                    cascade='all',
                                    overlaps='_declaration')


    ################################################################################
    # Model navigation
    ################################################################################

    def augments(self) -> ToscaInterfaceDeclaration:
        """Return the interface declaration for which this declaration is an
        augmentation.

        Returns:
          ToscaInterfaceDeclaration: declaration for which we are an
            augmentation

        Raises:
          KeyError: if we are not an augmentation
        """

        # Find the augmentation
        if self._containing_type:
            # This interface declaration is inside a type
            # definition. Get the declaration for which we are an
            # augmentation from the containing type.
            return self._containing_type.get_entity_declaration_to_augment(
                'interfaces', self.name)
        elif self._containing_declaration:
            # This declaration is inside another declaration. Get the
            # declaration for which we are an augmentation from the
            # containing declaration.
            return self._containing_declaration.get_entity_declaration_to_augment(
                'interfaces', self.name)
        else:
            # The only declarations that don't have a containing type
            # nor a containing declaration are synthetically-created
            # declarations (using the create_declaration
            # function). However, these declarations are never augmentations.
            raise KeyError("interface declaration '{}' is not an augmentation".format(self.name))


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
        # First, call superclass constructor
        super(ToscaInterfaceDeclaration, self).__init__(**kwargs)

        # ToscaInterfaceDeclaration-specific initialization. 
        if inputs: self.inputs = inputs
        if outputs: self.outputs = outputs
        if operations: self.operations = operations
        if notifications: self.notifications = notifications


    ################################################################################
    # Sub-entity retrieval functions. Sub-entities are retrieved from
    # this declaration as well as from its types
    ################################################################################

    def get_input_declarations(self) -> dict[str, Any]:
        return self.get_entity_declarations('inputs')

    def set_input_declaration(self, input_name: str, input_declaration: Any) -> None:
        return self.set_entity_declaration('inputs', input_name, input_declaration)

    def get_input_declaration(self, input_name: str) -> Any:
        return self.get_entity_declaration('inputs', input_name)

    def get_input_to_augment(self, input_name: str) -> Any:
        return self.get_entity_declaration_to_augment('inputs',
                                                      input_name)


    def get_output_declarations(self) -> dict[str, Any]:
        return self.get_entity_declarations('outputs')

    def set_output_declaration(self, output_name: str, output_declaration: Any) -> None:
        return self.set_entity_declaration('outputs', output_name, output_declaration)

    def get_output_declaration(self, output_name: str) -> Any:
        return self.get_entity_declaration('outputs', output_name)

    def get_output_to_augment(self, output_name: str) -> Any:
        return self.get_entity_declaration_to_augment('outputs',
                                                      output_name)


    def get_operation_declarations(self) -> dict[str, Any]:
        return self.get_entity_declarations('operations')

    def set_operation_declaration(self, operation_name: str, operation_declaration: Any) -> None:
        return self.set_entity_declaration('operations', operation_name, operation_declaration)

    def get_operation_declaration(self, operation_name: str) -> Any:
        return self.get_entity_declaration('operations', operation_name)

    def get_operation_to_augment(self, operation_name: str) -> Any:
        return self.get_entity_declaration_to_augment('operations',
                                                      operation_name)
    
    def get_operation_implementation(self, operation_name: str) -> list[Any]:
        """Return the implementation artifacts for the operation specified by
        'operation_name'.

        Args:
          operation_name(str): name of the operation for which to
            return an implementation

        Returns:
          (possibly emtpy) list of ToscaArtifact

        Raises:
          None
  
        """
        # Does this interface declaration have a definition for the
        # operation?
        try:
            artifacts = self.get_operation_declaration(operation_name).artifacts
            if artifacts: return artifacts
        except (AttributeError, KeyError) as e:
            pass
        return []


    def get_notification_declarations(self) -> dict[str, Any]:
        return self.get_entity_declarations('notifications')

    def set_notification_declaration(self, notification_name: str, notification_declaration: Any) -> None:
        return self.set_entity_declaration('notifications', notification_name, notification_declaration)

    def get_notification_declaration(self, notification_name: str) -> Any:
        return self.get_entity_declaration('notifications', notification_name)

    def get_notification_to_augment(self, notification_name: str) -> Any:
        return self.get_entity_declaration_to_augment('notifications',
                                                      notification_name)

    def get_notification_implementation(self, notification_name: str) -> Any:
        """Return the implementation artifact for the notification specified by
        'notification_name'.

        Args:
          notification_name(str): name of the notification for which to
            return an implementation

        Raises:
          KeyError: if no notification declaration is defined for the
            specified notification name
          AttributeError: if no implementation is found for the
            notification
        """
        # Does this interface declaration have a definition for the
        # notification?
        notification_declaration = self.get_notification_declaration(notification_name)
        return notification_declaration.implementation


    ################################################################################
    # Create a template for this declaration
    ################################################################################

    def create_template(self) -> Any:
        """Create a interface template from this declaration"""
        import tosca_core.models.interface_template
        interface = tosca_core.models.interface_template.ToscaInterfaceTemplate()
        interface.name = self.name
        interface.declaration = self
        return interface
    

    ################################################################################
    # Sub-Entity Refinement
    ################################################################################

    def merge_augmented_declaration(self, interface_declaration: ToscaInterfaceDeclaration) -> None:
        """Augment a interface with values from a second interface"""

        logger.debug("Interface declaration <%s>: augmenting", self.name)

        # First, call superclass augment method
        super(ToscaInterfaceDeclaration, self).merge_augmented_declaration(interface_declaration)

        # Augment 'inputs' 
        self.merge_augmented_inputs(interface_declaration)
        # Augment 'outputs' 
        self.merge_augmented_outputs(interface_declaration)
        # Augment 'operations' 
        self.merge_augmented_operations(interface_declaration)
        # Augment 'notifications' 
        self.merge_augmented_notifications(interface_declaration)


    def merge_augmented_inputs(self, interface_declaration: ToscaInterfaceDeclaration) -> None:
        # First, complete each individual input augmentation
        try:
            for input_name, input_declaration in self.inputs.items():
                # Find the corresponding input declaration to
                # augment and extend.
                try:
                    augmented_input = interface_declaration.get_input_declaration(input_name)
                    input_declaration.merge_augmented_declaration(augmented_input)
                except (KeyError, AttributeError):
                    # This input hasn't been previously defined, which
                    # is fine. Must be a regular input declaration instead.
                    pass
                except Exception as e:
                    # Something went wrong
                    logger.error("%s: unable to augment inputs: %s", self.name, e)
        except AttributeError as e:
            # We don't augment inputs
            pass

        # Then, merge in all other input declarations that haven't
        # been augmented
        try:
            inputs_to_merge = {}
            for input_name, input_declaration in interface_declaration.inputs.items():
                # Is this a declaration that has already been augmented?
                try:
                    augmented_input = self.inputs[input_name]
                    # Nothing further to do
                except (AttributeError, KeyError):
                    # Don't have this one yet
                    merged_input = tosca_core.models.property_declaration.ToscaPropertyDeclaration()
                    merged_input.merge_augmented_declaration(input_declaration)
                    inputs_to_merge[input_name] = merged_input
            # Merge in
            try:
                self.inputs.update(inputs_to_merge)
            except (AttributeError, TypeError):
                # Don't have inputs or inputs set to None
                self.inputs = inputs_to_merge
        except AttributeError as e:
            # We don't augment inputs
            pass
        

    def merge_augmented_outputs(self, interface_declaration: ToscaInterfaceDeclaration) -> None:
        # First, complete each individual output augmentation
        try:
            for output_name, output_declaration in self.outputs.items():
                # Find the corresponding output declaration to
                # augment and extend.
                try:
                    augmented_output = interface_declaration.get_output_declaration(output_name)
                    output_declaration.merge_augmented_declaration(augmented_output)
                except (KeyError, AttributeError):
                    # This output hasn't been previously defined, which
                    # is fine. Must be a regular output declaration instead.
                    pass
                except Exception as e:
                    # Something went wrong
                    logger.error("%s: unable to augment outputs: %s", self.name, e)
        except AttributeError as e:
            # We don't augment outputs
            pass

        # Then, merge in all other output declarations that haven't
        # been augmented
        try:
            outputs_to_merge = {}
            for output_name, output_declaration in interface_declaration.outputs.items():
                # Is this a declaration that has already been augmented?
                try:
                    augmented_output = self.outputs[output_name]
                    # Nothing further to do
                except (AttributeError, KeyError):
                    # Don't have this one yet
                    merged_output = tosca_core.models.property_declaration.ToscaPropertyDeclaration()
                    merged_output.merge_augmented_declaration(output_declaration)
                    outputs_to_merge[output_name] = merged_output
            # Merge in
            try:
                self.outputs.update(outputs_to_merge)
            except (AttributeError, TypeError):
                # Don't have outputs or outputs set to None
                self.outputs = outputs_to_merge
        except AttributeError as e:
            # We don't augment outputs
            pass
        

    def merge_augmented_operations(self, interface_declaration: ToscaInterfaceDeclaration) -> None:
        # Track container for debugging purposes
        if (self._containing_type):
            containing_entity = self._containing_type.name
        elif (self._containing_declaration):
            containing_entity = self._containing_declaration.name
        else:
            containing_entity = '?'
        # First, complete each individual operation augmentation
        try:
            for operation_name, operation_declaration in self.operations.items():
                # Find the corresponding operation declaration to
                # augment and extend.
                try:
                    augmented_operation = interface_declaration.get_operation_declaration(operation_name)
                    operation_declaration.merge_augmented_declaration(augmented_operation)
                except KeyError:
                    # No augmenting operation found. Nothing to do.
                    pass
                except Exception as e:
                    # Something went wrong
                    logger.error("%s: unable to augment operations: %s", self.name, e)
        except AttributeError as e:
            # We don't augment operations
            pass

        # Then, merge in all other operation declarations that haven't
        # been augmented
        try:
            for operation_name, operation_declaration in interface_declaration.operations.items():
                # Is this a declaration that has already been augmented?
                try:
                    augmented_operation = self.operations[operation_name]
                    # Nothing further to do
                except (AttributeError, KeyError):
                    # The interface merged in need not belong to a type
                    # (a requirement's refinement does not), and an
                    # error here would end the loop for every remaining
                    # operation.
                    defined_in = getattr(getattr(interface_declaration, '_containing_type', None), 'name', '?')
                    logger.debug("'%s': merging '%s' operation '%s' defined in '%s'",
                                 containing_entity, self.name, operation_name,
                                 defined_in)
                    # Don't have this one yet
                    merged_operation = tosca_core.models.operation_declaration.ToscaOperationDeclaration(
                        name=operation_name,role='OPERATION')
                    self.operations[operation_name] = merged_operation
                    merged_operation.merge_augmented_declaration(operation_declaration)
        except AttributeError as e:
            # We don't augment operations
            pass


    def merge_augmented_notifications(self, interface_declaration: ToscaInterfaceDeclaration) -> None:
        # First, complete each individual notification augmentation
        try:
            for notification_name, notification_declaration in self.notifications.items():
                # Find the corresponding notification declaration to
                # augment and extend.
                try:
                    augmented_notification = interface_declaration.get_notification_declaration(notification_name)
                    notification_declaration.merge_augmented_declaration(augmented_notification)
                except KeyError:
                    # No augmenting notification found. Nothing to do.
                    pass
                except Exception as e:
                    # Something went wrong
                    logger.error("%s: unable to augment notifications: %s", self.name, e)
        except AttributeError as e:
            # We don't augment notifications
            pass

        # Then, merge in all other notification declarations that haven't
        # been augmented
        try:
            for notification_name, notification_declaration in interface_declaration.notifications.items():
                # Is this a declaration that has already been augmented?
                try:
                    augmented_notification = self.notifications[notification_name]
                    # Nothing further to do
                except (AttributeError, KeyError):
                    # Don't have this one yet
                    merged_notification = tosca_core.models.operation_declaration.ToscaOperationDeclaration(
                        name=notification_name, role='NOTIFICATION')
                    self.notifications[notification_name] = merged_notification
                    merged_notification.merge_augmented_declaration(notification_declaration)
        except AttributeError as e:
            # We don't augment notifications
            pass


################################################################################
# Operation outputs
################################################################################
# What an operation must produce, read from declarations and templates
# alone. The presence check in the core needs them, and the runtime
# (ubicity's interface.py) uses them to hold an operation to its outputs.


def operation_output_mappings(interface_declaration: Any, operation_name: str,
                              interface_template: Any = None) -> dict[str, Any]:
    """The output mappings of an operation, by output name: those the
    interface template maps for the interface and for the operation, then
    those the interface declaration and the operation declaration map that
    the template does not. Without a template, only the declared mappings.
    Empty when the interface declares no such operation.
    """
    try:
        operation_declaration = interface_declaration.get_operation_declaration(
            operation_name
        )
    except KeyError:
        # No such operation defined
        return dict()

    outputs = dict()
    if interface_template is not None:
        # First, get output mappings defined at the interface level
        outputs.update(dict(interface_template.outputs))

        # Add output mappings defined in the operation template
        try:
            operation_template = interface_template.operations[operation_name]
            outputs.update(dict(operation_template.outputs))
        except KeyError:
            # No template for this operation, which means there are no
            # output mappings defined.
            pass

    # Add mappings from the declarations the template does not map: those
    # of the interface first, then those of the operation.
    for output_declarations in (interface_declaration.get_output_declarations(),
                                operation_declaration.get_output_declarations()):
        for output_name, output in output_declarations.items():
            if output_name in outputs:
                continue
            try:
                outputs[output_name] = output.mapping
            except AttributeError:
                # No mapping defined.
                logger.error(
                    "No mapping defined for declared output '%s'", output_name
                )

    # All done
    return outputs


def required_operation_outputs(interface_declaration: Any, operation_name: str,
                               interface_template: Any = None) -> dict[str, Any]:
    """The outputs an operation must produce when it succeeds, with their
    mappings: every output mapped for it (operation_output_mappings), except
    one whose declaration -- on the operation, or on the interface, which
    applies to each of its operations -- says it is not required. An output
    a template maps with no declaration has nothing to say otherwise, so it
    is required, the default.
    """
    mapped = operation_output_mappings(interface_declaration, operation_name,
                                       interface_template)
    try:
        operation_declaration = interface_declaration.get_operation_declaration(
            operation_name
        )
    except KeyError:
        return dict()
    declarations = dict(interface_declaration.get_output_declarations())
    declarations.update(operation_declaration.get_output_declarations())
    return {name: mapping for name, mapping in mapped.items()
            if name not in declarations or declarations[name].is_required()}
