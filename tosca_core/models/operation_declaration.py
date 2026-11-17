"""
Module definining Tosca Operation declaration entity
"""
from __future__ import annotations

__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2014-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Typing support
from typing import Any, Optional

# Logging support
import logging
logger: logging.Logger = logging.getLogger(__name__)

# Database support
from tosca_core import db

# Exception support
import tosca_core.models.exceptions as te

# SQL Alchemy support
from sqlalchemy.orm import backref
from sqlalchemy.orm.collections import attribute_mapped_collection
from sqlalchemy.ext.orderinglist import ordering_list

# Support for TOSCA keywords that are shared between all entities
import tosca_core.models.entity

# Types used in relationships
import tosca_core.models.artifact
import tosca_core.models.property_declaration
import tosca_core.models.interface_type


class ToscaOperationDeclaration(tosca_core.models.entity.ToscaEntityMixin, db.Model):
    """A ToscaOperationDeclaration object declares the presence of a
    named operation in a Tosca interface declaration.
    """

    ################################################################################
    # Keys
    ################################################################################
    
    # Primary key
    id =                        db.Column(db.Integer, primary_key=True)

    # Foreign keys
    _interface_type_id =        db.Column(db.Integer, 
                                          db.ForeignKey('tosca_type.id'),
                                          nullable=True)
    _interface_declaration_id = db.Column(db.Integer, 
                                          db.ForeignKey('tosca_declaration.id'),
                                          nullable=True)

    ################################################################################
    # Fields
    ################################################################################

    # Optional fields start with '_' and have corresponding getters
    # and setters to ensure that retrieving fields consistently raises
    # an AttributeError when not set.  Note that 'nullable' defaults
    # to True, but we explicitly set the 'nullable' flag for clarity.

    role =                      db.Column(db.Enum('OPERATION', 'NOTIFICATION', name='role'))


    ################################################################################
    # Relationships
    ################################################################################

    artifacts =                 db.relationship('ToscaArtifact',
                                                foreign_keys='ToscaArtifact._operation_declaration_id',
                                                collection_class=ordering_list('position'),
                                                order_by='ToscaArtifact.position',      
                                                backref=backref('_containing_operation_declaration', uselist=False),
                                                cascade='all')
    inputs =                    db.relationship('ToscaPropertyDeclaration',
                                                collection_class=attribute_mapped_collection('name'),
                                                primaryjoin="and_(ToscaOperationDeclaration.id=="
                                                "ToscaPropertyDeclaration._operation_declaration_id,"
                                                "ToscaPropertyDeclaration.role=='INPUT')",
                                                back_populates='_containing_operation_declaration',
                                                cascade='all',
                                                overlaps='outputs')
    outputs =                   db.relationship('ToscaPropertyDeclaration',
                                                collection_class=attribute_mapped_collection('name'),
                                                primaryjoin="and_(ToscaOperationDeclaration.id=="
                                                "ToscaPropertyDeclaration._operation_declaration_id,"
                                                "ToscaPropertyDeclaration.role=='OUTPUT')",
                                                back_populates='_containing_operation_declaration',
                                                cascade='all',
                                                overlaps='inputs')

    ################################################################################
    # Model Navigation
    ################################################################################

    _containing_interface_type = db.relationship('ToscaInterfaceType',
                                                 foreign_keys='ToscaOperationDeclaration._interface_type_id')
    _containing_interface_declaration = db.relationship('ToscaInterfaceDeclaration',
                                                 foreign_keys='ToscaOperationDeclaration._interface_declaration_id')

    @property
    def profile(self) -> Any:
        """Get profile.  We check if we're contained in some other
        declaration, and if so, get the profile from that
        declaration. If not, we'll call the base class.
        """
        if self._containing_interface_declaration:
            return self._containing_interface_declaration.profile
        elif self._containing_interface_type:
            return self._containing_interface_type.profile
        else:
            error = "No profile found for operation declaration '{0}'".format(self.name)
            raise te.ModelCorruptionError(error)

    @property
    def tosca_version(self) -> str:
        """Get tosca version from the profile.
        """
        return self.profile.tosca_version

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
        # First, call superclass constructor
        super(ToscaOperationDeclaration, self).__init__(**kwargs)

        # ToscaOperationDeclaration-specific initialization
        if role != None: self.role = role
        self.implementation = implementation
        if inputs: self.inputs = inputs
        if outputs: self.outputs = outputs

    # Jump through hoops to map TOSCA "operation implementation"
    # grammar onto the database schema
    @property
    def implementation(self) -> dict[str, Any]:
        if self.artifacts:
            implementation = dict()
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
    # Implementation of reserved keywords
    ################################################################################

    def SELF(self) -> Any:
        """Return the declaration for the entity referred to by SELF for this
        operation declaration. We get this from the containing
        interface declaration. Note that we can't retrieve SELF if
        this operation is declared in an Interface Type definition.

        Raises:
          AttributeError: if the operation template has no containing
            interface template
        """
        if self._containing_interface_declaration:
            return self._containing_interface_declaration.SELF()
        else:
            raise AttributeError("No containing node/relationshp type or definition found for '{0}'".format(self.name))


    def SOURCE(self) -> Any:
        """Return the declaration for the entity referred to by SOURCE for
        this operation declaration. We get this from the containing
        interface declaration. Note that we can't retrieve SOURCE if
        this operation is declared in an Interface Type definition.

        Raises:
          AttributeError: if the operation template has no containing
            interface template
        """
        if self._containing_interface_declaration:
            return self._containing_interface_declaration.SOURCE()
        else:
            raise AttributeError("No containing node/relationshp type or definition found for '{0}'".format(self.name))


    def TARGET(self) -> Any:
        """Return the declaration for the entity referred to by TARGET for
        this operation declaration. We get this from the containing
        interface declaration. Note that we can't retrieve TARGET if
        this operation is declared in an Interface Type definition.

        Raises:
          AttributeError: if the operation template has no containing
            interface template
        """
        if self._containing_interface_declaration:
            return self._containing_interface_declaration.TARGET()
        else:
            raise AttributeError("No containing node/relationshp type or definition found for '{0}'".format(self.name))
    

    ################################################################################
    # Sub-entity retrieval functions. Sub-entities are retrieved from
    # this declaration as well as from its types
    ################################################################################

    def get_input_declarations(self) -> dict[str, Any]:
        return self.get_entity_declarations('inputs')


    def get_input_declaration(self, input_name: str) -> Any:
        return self.get_entity_declaration('inputs', input_name)


    def set_input_declaration(self, input_name: str, input_declaration: Any) -> None:
        return self.set_entity_declaration('inputs', input_name, input_declaration)


    def get_input_to_augment(self, input_name: str) -> Any:
        return self.get_entity_declaration_to_augment('inputs',
                                                      input_name)



    def get_output_declarations(self) -> dict[str, Any]:
        return self.get_entity_declarations('outputs')


    def get_output_declaration(self, output_name: str) -> Any:
        return self.get_entity_declaration('outputs', output_name)


    def set_output_declaration(self, output_name: str, output_declaration: Any) -> None:
        return self.set_entity_declaration('outputs', output_name, output_declaration)


    def get_output_to_augment(self, output_name: str) -> Any:
        return self.get_entity_declaration_to_augment('outputs',
                                                      output_name)


    def get_entity_declarations(self, entity_declaration_map_name: str) -> dict[str, Any]:
        """get entity declarations kepts in the 'entity_declaration_map_name'
        for an operation declaration. This could mean 'inputs' or
        'outputs'
        """

        try:
            if self._containing_interface_declaration:
                # This operation declaration is inside an interface
                # declaration. Get any entities from the operation
                # declaration inside the type definition first.
                interface_type = self._containing_interface_declaration.type_entity
            elif self._containing_interface_type:
                # This operation declaration is inside an interface
                # type. Get any entities from the operation declaration
                # inside the parent type first.
                interface_type = self._containing_interface_type.parent
            # Get the operation or notification declaration
            if self.role == 'OPERATION':
                operation_declaration = interface_type.get_operation_declaration(self.name)
            elif self.role == 'NOTIFICATION':
                operation_declaration = interface_type.get_notification_declaration(self.name)
            entity_declarations = operation_declaration.get_entity_declarations(entity_declaration_map_name)
        except (AttributeError, KeyError):
            entity_declarations = dict()

        # Add entities declared by this operation declaration
        try:
            entities = getattr(self, entity_declaration_map_name)
            entity_declarations.update(entities)
        except AttributeError:
            # None defined. Return empty dict
            pass

        return entity_declarations


    def get_entity_declaration(self, entity_declaration_map_name: str, entity_name: str) -> Any:
        """Get entity declaration by name from the declaration map kept in the
        'entity_declaration_map_name' attribute of this operation
        declaration. Entity declarations could be 'inputs' or
        'outputs'. If this operation declaration does not have the
        named entity, this function tries to get the entity
        declaration from the operation declaration's containing
        interface declaration, or from its containing interface type
        entity.

        Args:
          entity_declaration_map_name(str): name of the attribute in
            this declaration entity that has the map of entity
            declarations
          entity_name(str): name of the entity for which to return the
            declaration

        Returns: 
          ToscaDeclaration for the requested entity declaration

        Raises:
          KeyError: when no entity declared with this name

        """
        # Do we have the named declaration?
        try:
            entities = getattr(self, entity_declaration_map_name)
            return entities[entity_name]
        except (AttributeError, KeyError):
            # This declaration does not have an attribute of the name
            # specified in 'entity_declaration_map_name or doesn't
            # have a declaration of the specified name.
            pass

        # Check the operation declaration in the interface type or the
        # parent interface type instead.
        try:
            if self._containing_interface_declaration:
                # We are part of an interface declaration. We'll get the
                # operation declaration from the interface type.
                interface_type = self._containing_interface_declaration.type_entity
            elif self._containing_interface_type:
                # We are part of an interface type. We'll get the
                # operation declaration from the parent interface type.
                interface_type = self._containing_interface_type.parent
            # Get the operation declaration to search next
            if self.role == 'OPERATION':
                operation_declaration = interface_type.get_operation_declaration(self.name)
            elif self.role == 'NOTIFICATION':
                operation_declaration = interface_type.get_notification_declaration(self.name)
            return operation_declaration.get_entity_declaration(entity_declaration_map_name,
                                                                entity_name)
        except (AttributeError, KeyError, te.TypeNotFound):
            raise KeyError("Operation '{0}': <{1}> not found in <{2}>".format(self.name, 
                                                                              entity_name,
                                                                              entity_declaration_map_name))


    def set_entity_declaration(self, entity_declaration_map_name: str, entity_name: str, entity_declaration: Any) -> None:
        """set entity declaration by name in the map stored in the
        'entity_declaration_map_name' attribute of this declaration
        entity.

        Args:
          entity_declaration_map_name(str): name of the attribute in
            this delcaration entity that has the map of entity
            declarations
          entity_name(str): name of the entity for which to return the
            declaration
        """

        try:
            entities = getattr(self, entity_declaration_map_name)
            entities[entity_name] = entity_declaration
        except AttributeError:
            # No entity map defined yet. Assign initial map
            setattr(self, entity_declaration_map_name, { entity_name : entity_declaration })


    def get_entity_declaration_to_augment(self, entity_declaration_map_name: str, entity_name: str) -> Any:
        """Get declaration entity to augment for this operation declaration.

        Returns the entity declaration of the operation declaration:

        - either from a parent interface type definition that contains
          this operation declaration

        - or from the interface type of the interface declaration that
          contains this operation declaration

        Args:
          entity_declaration_map_name(str): name of the attribute in
            the type entity that has the map of entity declarations
          entity_name(str): name of the entity for which to return the
            declaration to be augmented

        Returns:
          ToscaDeclaration for the requested entity declaration

        Raises:
          KeyError: when no entity declared with this name exists in
            the type entity
        """

        try:
            if self._containing_interface_declaration:
                # We are part of an interface declaration. We'll get the
                # operation declaration from the interface type.
                interface_type = self._containing_interface_declaration.type_entity
            elif self._containing_interface_type:
                # We are part of an interface type. We'll get the
                # operation declaration from the parent interface type.
                interface_type = self._containing_interface_type.parent
            # Get the operation declaration to augment
            if self.role == 'OPERATION':
                operation_declaration = interface_type.get_operation_declaration(self.name)
            elif self.role == 'NOTIFICATION':
                operation_declaration = interface_type.get_notification_declaration(self.name)
        except (AttributeError, KeyError, te.TypeNotFound):
            raise KeyError("Operation '{0}': <{1}> not found in <{2}>".format(self.name, 
                                                                              entity_name,
                                                                              entity_declaration_map_name))

        # Get the entity declaration that is to be augmented
        return operation_declaration.get_entity_declaration(entity_declaration_map_name,
                                                            entity_name)


    ################################################################################
    # Sub-Entity Refinement
    ################################################################################

    def merge_augmented_declaration(self, operation_declaration: ToscaOperationDeclaration) -> None:
        """Augment a operation with values from a second operation"""

        logger.debug("Operation declaration <%s>: augmenting", self.name)

        # Merge fields we don't already have
        self.merge_augmented_field('_description', operation_declaration)

        # Augment 'implementation' 
        self.merge_augmented_implementation(operation_declaration)

        # Augment 'inputs' 
        self.merge_augmented_inputs(operation_declaration)

        # Augment 'outputs' 
        self.merge_augmented_outputs(operation_declaration)


    def merge_augmented_field(self, field_name: str, augmented_entity: Any) -> None:
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


    def merge_augmented_implementation(self, operation_declaration: ToscaOperationDeclaration) -> None:
        """Complete a field in an augmentation by merging in the field from
        the declaration which it augments if necessary
        """

        # Is there anything to do?
        if self.artifacts or not operation_declaration.artifacts:
            # Artifacts already defined or nothing to merge
            return

        for artifact_to_copy in operation_declaration.artifacts:
            # Make a copy of the artifact to make sure all back
            # references are set up correctly.
            artifact = tosca_core.models.artifact.ToscaArtifact()
            artifact.complete_template_refinement(artifact_to_copy)
            self.artifacts.append(artifact)


    def merge_augmented_inputs(self, operation_declaration: ToscaOperationDeclaration) -> None:
        # First, complete each individual input augmentation
        try:
            for input_name, input_declaration in self.inputs.items():
                # Find the corresponding input declaration to
                # augment and extend.
                try:
                    augmented_input = operation_declaration.get_input_declaration(input_name)
                    input_declaration.merge_augmented_declaration(augmented_input)
                except (KeyError, AttributeError):
                    # This input hasn't been previously defined, which
                    # is fine. Must be a regular input declaration instead.
                    pass
                except Exception as e:
                    # Something went wrong
                    logger.error("%s: unable to augment: %s", self.name, e)
        except AttributeError as e:
            # We don't augment inputs
            pass

        # Then, merge in all other input declarations that haven't
        # been augmented
        try:
            inputs_to_merge = {}
            for input_name, input_declaration in operation_declaration.inputs.items():
                # Is this a declaration that has already been augmented?
                try:
                    augmented_input = self.inputs[input_name]
                    # Nothing further to do
                except (KeyError, AttributeError):
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


    def merge_augmented_outputs(self, operation_declaration: ToscaOperationDeclaration) -> None:
        # First, complete each individual output augmentation
        try:
            for output_name, output_declaration in self.outputs.items():
                # Find the corresponding output declaration to
                # augment and extend.
                try:
                    augmented_output = operation_declaration.get_output_declaration(output_name)
                    output_declaration.merge_augmented_declaration(augmented_output)
                except (KeyError, AttributeError):
                    # This output hasn't been previously defined, which
                    # is fine. Must be a regular output declaration instead.
                    pass
                except Exception as e:
                    # Something went wrong
                    logger.error("%s: unable to augment: %s", self.name, e)
        except AttributeError as e:
            # We don't augment outputs
            pass

        # Then, merge in all other output declarations that haven't
        # been augmented
        try:
            outputs_to_merge = {}
            for output_name, output_declaration in operation_declaration.outputs.items():
                # Is this a declaration that has already been augmented?
                try:
                    augmented_output = self.outputs[output_name]
                    # Nothing further to do
                except (KeyError, AttributeError):
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
