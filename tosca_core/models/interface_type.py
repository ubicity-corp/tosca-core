"""
Module definining Tosca Interface type
"""
from __future__ import annotations

__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2014-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger: logging.Logger = logging.getLogger(__name__)

# Type hints
from typing import Any, Optional

# Database support
from tosca_core import db

# SQL Alchemy support
from sqlalchemy import and_
from sqlalchemy.orm.collections import attribute_mapped_collection

# Type from which this type derives
import tosca_core.models.type

# For evaluating preconditions
from tosca_core.models.function import ToscaFunction


class ToscaInterfaceType(tosca_core.models.type.ToscaType):
    """A ToscaInterfaceType object defines an interface type entity that
    can be used to define interfaces in node types and relationship
    types. An interface type defines a set of operations and
    notifications as well as input definitions that are shared by all
    operations and notifications.
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
                                    primaryjoin="and_(ToscaInterfaceType.id==ToscaPropertyDeclaration._containing_type_id,"
                                    "ToscaPropertyDeclaration.role=='INPUT')",
                                    cascade='all',
                                    back_populates='_containing_type',
                                    overlaps='outputs,attributes,properties')
    outputs =       db.relationship('ToscaPropertyDeclaration',
                                    collection_class=attribute_mapped_collection('name'),
                                    primaryjoin="and_(ToscaInterfaceType.id==ToscaPropertyDeclaration._containing_type_id,"
                                    "ToscaPropertyDeclaration.role=='OUTPUT')",
                                    cascade='all',
                                    back_populates='_containing_type',
                                    overlaps='inputs,attributes,properties')
    operations =    db.relationship('ToscaOperationDeclaration',
                                    collection_class=attribute_mapped_collection('name'),
                                    primaryjoin="and_(ToscaInterfaceType.id==ToscaOperationDeclaration._interface_type_id,"
                                    "ToscaOperationDeclaration.role=='OPERATION')",
                                    back_populates='_containing_interface_type',
                                    cascade='all',
                                    overlaps='notifications')
    notifications = db.relationship('ToscaOperationDeclaration',
                                    collection_class=attribute_mapped_collection('name'),
                                    primaryjoin="and_(ToscaInterfaceType.id==ToscaOperationDeclaration._interface_type_id,"
                                    "ToscaOperationDeclaration.role=='NOTIFICATION')",
                                    back_populates='_containing_interface_type',
                                    cascade='all',
                                    overlaps='operations')

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
        """Instantiate a new ToscaInterfaceType instance"""

        # First, call superclass constructor
        super(ToscaInterfaceType, self).__init__(**kwargs)

        # ToscaInterfaceType-specific initialization.
        if inputs: self.inputs = inputs
        if outputs: self.outputs = outputs
        if operations: self.operations = operations
        if notifications: self.notifications = notifications


    ################################################################################
    # Sub-entity retrieval functions. Sub-entities are retrieved from
    # this type as well as from any parent types(s)
    ################################################################################

    def get_input_declarations(self) -> dict[str, Any]:
        return self.get_entity_declarations('inputs')

    def get_input_declaration(self, input_name: str) -> Any:
        return self.get_entity_declaration('inputs', input_name)

    def get_input_to_augment(self, input_name: str) -> Any:
        return self.get_entity_declaration_to_augment('inputs',
                                                      input_name)

    def get_output_declarations(self) -> dict[str, Any]:
        return self.get_entity_declarations('outputs')

    def get_output_declaration(self, output_name: str) -> Any:
        return self.get_entity_declaration('outputs', output_name)

    def get_output_to_augment(self, output_name: str) -> Any:
        return self.get_entity_declaration_to_augment('outputs',
                                                      output_name)


    def get_operation_declarations(self) -> dict[str, Any]:
        return self.get_entity_declarations('operations')

    def get_operation_declaration(self, operation_name: str) -> Any:
        return self.get_entity_declaration('operations', operation_name)

    def get_operation_to_augment(self, operation_name: str) -> Any:
        return self.get_entity_declaration_to_augment('operations',
                                                      operation_name)


    def get_notification_declarations(self) -> dict[str, Any]:
        return self.get_entity_declarations('notifications')

    def get_notification_declaration(self, notification_name: str) -> Any:
        return self.get_entity_declaration('notifications', notification_name)

    def get_notification_to_augment(self, notification_name: str) -> Any:
        return self.get_entity_declaration_to_augment('notifications',
                                                      notification_name)
