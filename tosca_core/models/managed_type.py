"""
Module definining Tosca Managed Type Entity
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
from sqlalchemy.orm.collections import attribute_mapped_collection

# Types on which this type depends
import tosca_core.models.type
import tosca_core.models.context

# Types used in relationships
import tosca_core.models.interface_declaration


# The expression-context contract goes LAST: it supplies refusals for members
# nobody defines, and must never shadow a mapped attribute such as 'profile'.
class ToscaManagedType(tosca_core.models.type.ToscaType,
                       tosca_core.models.context.ToscaContextMixin):
    """A ToscaManagedType defines a named managed type. A managed type in
    TOSCA is a type that declares interfaces for managing the
    lifecycle of instances of that type. The ToscaManagedType class is
    the base class for ToscaNodeType and ToscaRelationshipType.
    """

    ################################################################################
    # Polymorphic mapping
    ################################################################################

    __mapper_args__ = {
        'polymorphic_identity':'managed',
    }


    ################################################################################
    # Relationships
    ################################################################################

    interfaces = db.relationship('ToscaInterfaceDeclaration',
                                 collection_class=attribute_mapped_collection('name'),
                                 foreign_keys='ToscaInterfaceDeclaration._containing_type_id',
                                 cascade='all',
                                 back_populates='_containing_type')


    ################################################################################
    # Constructor
    ################################################################################

    def __init__(self,
                 interfaces: Optional[dict[str, Any]] = None,
                 **kwargs: Any
    ) -> None:
        # First, call superclass constructor
        super(ToscaManagedType, self).__init__(**kwargs)

        # ToscNodeType-specific initialization
        if interfaces: self.interfaces = interfaces


    ################################################################################
    # Implementation of reserved keywords
    ################################################################################

    def SELF(self) -> ToscaManagedType:
        """Return the type for the entity referred to by SELF for this
        type. SELF refers to nodes or relationships only, so we just
        return ourselves.

        Returns:
          ToscaManagedType

        Raises:
          AttributeError: if the template has no containing managed
            type or managed declaration

        """
        return self


    ################################################################################
    # Sub-entity retrieval functions. Sub-entities are retrieved from
    # this type as well as from any parent types(s)
    ################################################################################

    def get_interface_declarations(self) -> dict[str, Any]:
        return self.get_entity_declarations('interfaces')

    def get_interface_declaration(self, interface_name: str) -> Any:
        return self.get_entity_declaration('interfaces', interface_name)

    def get_interface_to_augment(self, interface_name: str) -> Any:
        return self.get_entity_declaration_to_augment('interfaces',
                                                      interface_name)

    
