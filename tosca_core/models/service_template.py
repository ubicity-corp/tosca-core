"""
ToscaServiceTemplate class
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
from sqlalchemy import func
from sqlalchemy.orm import backref
from sqlalchemy.orm.collections import attribute_mapped_collection
from sqlalchemy.ext.orderinglist import ordering_list

# Substitution mapping dicts are mutable
from sqlalchemy.ext.mutable import MutableDict

# Exceptions
import tosca_core.models.exceptions as te

# Support for TOSCA keywords that are shared between all entities
import tosca_core.models.entity

# Types used in relationships
import tosca_core.models.workflow_template
import tosca_core.models.substitution_mappings


default_service_name: str = 'default'


class ToscaServiceTemplate(tosca_core.models.entity.ToscaEntityMixin, db.Model):
    """The ToscaServiceTemplate contains all the necessary information
    to orchestrate and manage a deployable TOSCA service.
    """

    ################################################################################
    # Keys
    ################################################################################
    
    # Primary key
    id =                      db.Column(db.Integer, primary_key=True)

    # Foreign keys
    _profile_id =             db.Column(db.Integer,
                                        db.ForeignKey('tosca_profile.id'),
                                        nullable=True)
    _substitutes_id =         db.Column(db.Integer, 
                                        db.ForeignKey('tosca_type.id'),
                                        nullable=True)
    @property
    # URL fields in TOSCA schemas need substitutes_id to raise an
    # AttributeError when the service template does not substitute
    def substitutes_id(self) -> int:
        if not self._substitutes_id:
            raise AttributeError("'{0}' does not have 'substitutes_id'".format(self.name))
        return self._substitutes_id
    
    ################################################################################
    # Fields
    ################################################################################

    # Optional fields start with '_' and have a corresponding getter
    # to ensure that retrieving fields consistently raises an
    # AttributeError when not set.  Note that 'nullable' defaults to
    # True, but we explicitly set the 'nullable' flag for clarity.
    creation_time =           db.Column(db.DateTime, server_default=func.now())

    # Substitution mappings are an entity rather than a dict on this
    # template: they own the expressions they contain, and an expression
    # context has to answer for the document an expression is written in
    # as well as the entity it refers to (tosca_core.models.context).
    _substitution_mappings =  db.relationship('ToscaSubstitutionMappings',
                                              foreign_keys='ToscaSubstitutionMappings._service_id',
                                              back_populates='_service',
                                              uselist=False,
                                              cascade='all')

    ################################################################################
    # Collections
    ################################################################################

    # For non-existing collections, we add getters if necessary to
    # make sure we always return empty maps or lists.
    
    node_templates =          db.relationship('ToscaNodeTemplate',
                                              collection_class=attribute_mapped_collection('name'),
                                              foreign_keys='ToscaNodeTemplate._service_id',
                                              back_populates='_service',
                                              overlaps='_service',
                                              cascade='all')
    relationship_templates =  db.relationship('ToscaRelationshipTemplate',
                                              collection_class=attribute_mapped_collection('name'),
                                              foreign_keys='ToscaRelationshipTemplate._service_id',
                                              back_populates='_service',
                                              overlaps='_service',
                                              cascade='all')
    groups =                  db.relationship('ToscaGroupTemplate',
                                              collection_class=attribute_mapped_collection('name'),
                                              foreign_keys='ToscaGroupTemplate._service_id',
                                              back_populates='_service',
                                              overlaps='_service',
                                              cascade='all')
    workflows =               db.relationship('ToscaWorkflowTemplate',
                                              collection_class=attribute_mapped_collection('name'),
                                              foreign_keys='ToscaWorkflowTemplate._service_id',
                                              back_populates='_service',
                                              overlaps='_service',
                                              cascade='all')
    policies =                db.relationship('ToscaPolicyTemplate',
                                              collection_class=ordering_list('position'),
                                              order_by='ToscaTemplate.position',      
                                              foreign_keys='ToscaPolicyTemplate._service_id',
                                              back_populates='_service',
                                              overlaps='_service',
                                              cascade='all')

    inputs =                  db.relationship('ToscaPropertyDeclaration',
                                              collection_class=attribute_mapped_collection('name'),
                                              primaryjoin="and_(ToscaServiceTemplate.id=="
                                              "remote(ToscaPropertyDeclaration._service_id),"
                                              "remote(ToscaPropertyDeclaration.role)=='INPUT')",
                                              back_populates='_containing_service',
                                              overlaps='inputs,outputs',
                                              cascade='all')
    outputs =                 db.relationship('ToscaPropertyDeclaration',
                                              collection_class=attribute_mapped_collection('name'),
                                              primaryjoin="and_(ToscaServiceTemplate.id=="
                                              "remote(ToscaPropertyDeclaration._service_id),"
                                              "remote(ToscaPropertyDeclaration.role)=='OUTPUT')",
                                              back_populates='_containing_service',
                                              overlaps='inputs,outputs',
                                              cascade='all')

    ################################################################################
    # Model Navigation
    ################################################################################

    profile =                 db.relationship('ToscaProfile',
                                              uselist=False,
                                              foreign_keys='ToscaServiceTemplate._profile_id',
                                              backref=backref('_service', uselist=False))

    substitutes =             db.relationship('ToscaNodeType',
                                              uselist=False,
                                              foreign_keys='ToscaServiceTemplate._substitutes_id',
                                              backref="substituted_by")

    @property
    def tosca_version(self) -> str:
        """Get tosca version from the profile.
        """
        return self.profile.tosca_version

    # Intrinsic functions need a context within which to operate. In
    # many cases (e.g. for 'get_input') they will try to retrieve the
    # service from their context. If the context is the service
    # itself, retrieving the service from that context should return
    # the service
    @property
    def service(self) -> ToscaServiceTemplate:
        return self

    # Tosca Path expressions may need to navigate to 'nodes' of a
    # service. For service templates, 'nodes' are obtained using the
    # 'node_templates' relationship.
    @property
    def nodes(self) -> dict[str, Any]:
        return self.node_templates

    ################################################################################
    # Constructor
    ################################################################################

    def __init__(self,
                 inputs: Optional[dict[str, Any]] = None,
                 outputs: Optional[dict[str, Any]] = None,
                 substitution_mappings: Optional[dict[str, Any]] = None,
                 node_templates: Optional[dict[str, Any]] = None,
                 relationship_templates: Optional[dict[str, Any]] = None,
                 groups: Optional[dict[str, Any]] = None,
                 workflows: Optional[dict[str, Any]] = None,
                 policies: Optional[list[Any]] = None,
                 **kwargs: Any
    ) -> None:
        """Constructor
        """

        # First, call superclass constructor
        super(ToscaServiceTemplate, self).__init__(**kwargs)

        # Initialize service name 
        if not self.name: self.name = default_service_name

        # ToscaServiceTemplate-specific initialization
        if inputs: self.inputs = inputs
        if outputs: self.outputs = outputs
        self.substitution_mappings = substitution_mappings
        if node_templates: self.node_templates = node_templates
        if groups: self.groups = groups
        if workflows: self.workflows = workflows
        if policies: self.policies = policies

        # We temporarily store defined relationship templates, but
        # these will get merged into the appropriate requirement
        # assignments during validation.
        if relationship_templates: self.relationship_templates = relationship_templates


    @property
    def substitution_mappings(self) -> Any:
        """The ToscaSubstitutionMappings entity for this template.

        Raises AttributeError when this template does not substitute,
        which is what callers test for.
        """
        if not self._substitution_mappings:
            logger.debug("service %s does not substitute", self.name)
            raise AttributeError("Service {0} does not have 'substitution_mappings' attribute".format(self.name))
        return self._substitution_mappings

    @substitution_mappings.setter
    def substitution_mappings(self, value: Optional[Any]) -> None:
        """Accepts either the parsed mapping dict or an already-built entity.

        The schema layer still produces a dict, so this is where that dict
        becomes the entity that owns it.
        """
        if not value:
            return
        if isinstance(value, dict):
            value = tosca_core.models.substitution_mappings.ToscaSubstitutionMappings(
                node_type=value.get('node_type'),
                substitution_filter=value.get('substitution_filter'),
                properties=value.get('properties'),
                attributes=value.get('attributes'),
                capabilities=value.get('capabilities'),
                requirements=value.get('requirements'),
                interfaces=value.get('interfaces'),
                line=value.get('line'))
        self._substitution_mappings = value


    ################################################################################
    # Sub-entity retrieval functions. Sub-entities are retrieved from
    # this type as well as from any parent types(s)
    ################################################################################

    def get_input_declaration(self, input: str | list[str]) -> Any:
        """Return the declaration for the input specified by 'input'.

        Args:
          input (string or ToscaPath): the input for which to return
            the declaration.

        Returns:
          ToscaPropertyDeclaration

        Raises:
          KeyError: when input not found

        """
        # Get input name. TODO: replace with ToscaPath at some point
        if isinstance(input, str):
            input_name = input
            sub_entity = None
        elif isinstance(input, list):
            input_name = input[0]
            if len(input) == 2:
                sub_entity = input[1]
            else:
                sub_entity = input[1:]
        else:
            raise KeyError("invalid input name '{0}'".format(str(input)))

        # Get the input declaration.
        try:
            input_declaration = self.inputs[input_name]
        except Exception:
            raise KeyError(input_name)

        # Get sub entity if necessary
        if sub_entity:
            return input_declaration.get_property_declaration(sub_entity)
        else:
            return input_declaration
        
        
    def get_entity_declaration_to_augment(self, entity_declaration_map_name: str, entity_name: str) -> Any:
        """Get declaration entity to augment. Topologies never have entity
        declarations to augment.

        """
        raise KeyError("Topologies don't augment entity declarations")


    def validate_input_values(self, inputs: dict[str, Any], check_required: bool = True) -> dict[str, Any]:
        """Validate inputs passed to this service template when deploying a
        service.

        TODO: try to reuse code from
        ToscaDeclaration::validate_property_templates

        Args:
          inputs(dict): the input values to validate against the input
            declarations in this service template
          check_required(bool): flag to indicate if we need to make
            sure that all required inputs are present. All required
            inputs must be present during initial service
            instantiation but not during service update.
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """
        # Validate all inputs against the input declarations
        input_declarations = self.inputs
        validation_errors = {}
        for input_name, input_value in inputs.items():
            logger.debug("%s: validating input '%s'", self.id, input_name)
            try:
                # Find input declaration
                input_declaration = input_declarations[input_name]

                # Make sure this input value doesn't override a fixed
                # value defined in the input declaration
                try:
                    value = input_declaration.value
                    validation_errors[input_name] = 'overriding value from definition is not allowed'
                except AttributeError:
                    # No fixed value defined in the
                    # declaration. 
                    # Validate input value against input declaration
                    try:
                        validated_input = input_declaration.validate_value(self, input_value)
                    except te.ValidationError as e:
                        logger.error("'%s' input '%s': '%s' is invalid value for %s",
                                     self.id, input_name, input_value,
                                     input_declaration.type)
                        validation_errors[input_name] = e.errors
                    except Exception as error:
                        logger.error("%s: error validating inputs: %s", self.id, error)
                        validation_errors[input_name] = "validator error ({0})".format(error)
            except KeyError:
                logger.error("'%s': undefined input '%s'", self.id, input_name)
                validation_errors[input_name] = 'not previously defined'

        # Make sure all required inputs are present if necessary
        if check_required:
            for input_name, input_declaration in input_declarations.items():
                if input_declaration.is_required():
                    logger.debug("Checking value for required input '%s'", 
                                 input_name)
                    try:
                        input_value = inputs[input_name]
                    except (KeyError, AttributeError):
                        error = input_declaration.validate_value_presence(self, inputs)
                        if error:
                            validation_errors[input_name] = error
                    except Exception as e:
                        logger.error("error checking required input '%s': %s",
                                     input_name, e)
                        validation_errors[input_name] = 'validator error <{0}>'.format(str(e))

        # Everything OK
        return validation_errors


    ################################################################################
    # Service Template Deletion
    ################################################################################

    def delete(self, check_only: bool = False) -> Optional[bool]:
        """Delete this service template, or under check_only say whether it
        can be deleted, which it always can: the core creates no services
        from a template. An application that does refuses to delete one
        while services created from it exist."""
        if check_only:
            return True
        db.session.delete(self)


################################################################################
# SERVICE LOOKUP FUNCTIONS
################################################################################

def get_service_template(service_id: int) -> ToscaServiceTemplate:
    """Return service entity by id

    Args:
      service_id(integer): ID of the service

    Raises:
      TemplateNotFound: when no service template with the specified
        ID is found
    """
    service: Optional[ToscaServiceTemplate] = ToscaServiceTemplate.query.get(service_id)
    if service: return service
    raise te.TemplateNotFound("Service template '{0}' not found".format(service_id))
