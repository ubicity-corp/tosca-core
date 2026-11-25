"""
Module definining Tosca Workflow Template entity
"""
from __future__ import annotations

__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2017-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Typing support
from typing import Any, Optional

# Logging support
import logging
logger: logging.Logger = logging.getLogger(__name__)

# Database support
from tosca_core import db

# SQL Alchemy support
from sqlalchemy.orm import backref
from sqlalchemy.orm.collections import attribute_mapped_collection
from sqlalchemy.ext.orderinglist import ordering_list

# Steps dicts are mutable
from sqlalchemy.ext.mutable import MutableDict

# Exception support
import tosca_core.models.exceptions as te
import tosca_core.models.input_values

# Support for TOSCA keywords that are shared between all entities
import tosca_core.models.entity

# Types used in workflow templates
import tosca_core.models.artifact


class ToscaWorkflowTemplate(tosca_core.models.entity.ToscaEntityMixin, db.Model):
    """ToscaWorkflowTemplate class. This class TOSCA imperative workflows.
    """

    ################################################################################
    # Keys
    ################################################################################
    
    # Primary key
    id =             db.Column(db.Integer, primary_key=True)

    # Foreign keys
    _service_id =    db.Column(db.Integer, 
                               db.ForeignKey('tosca_service_template.id'),
                               nullable=True)

    ################################################################################
    # Fields
    ################################################################################

    # Optional fields start with '_' and have corresponding getters
    # and setters to ensure that retrieving fields consistently raises
    # an AttributeError when not set.  Note that 'nullable' defaults
    # to True, but we explicitly set the 'nullable' flag for clarity.

    _preconditions = db.Column(db.PickleType, nullable=True)
    _steps =         db.Column(MutableDict.as_mutable(db.PickleType), nullable=True)

    @property
    def preconditions(self) -> Any:
        if not self._preconditions:
            raise AttributeError("'{0}' does not have 'preconditions'".format(self.name))
        return self._preconditions

    @preconditions.setter
    def preconditions(self, value: Any) -> None:
        if value: self._preconditions = value

    @property
    def steps(self) -> dict[str, Any]:
        if not self._steps:
            raise AttributeError("'{0}' does not have 'steps'".format(self.name))
        return self._steps


    ################################################################################
    # Collections
    ################################################################################

    inputs =         db.relationship('ToscaPropertyDeclaration',
                                     collection_class=attribute_mapped_collection('name'),
                                     primaryjoin="and_(ToscaWorkflowTemplate.id=="
                                     "remote(ToscaPropertyDeclaration._workflow_id),"
                                     "remote(ToscaPropertyDeclaration.role)=='INPUT')",
                                     back_populates='_containing_workflow',
                                     overlaps='inputs,outputs',
                                     cascade='all')
    outputs =        db.relationship('ToscaPropertyDeclaration',
                                     collection_class=attribute_mapped_collection('name'),
                                     primaryjoin="and_(ToscaWorkflowTemplate.id=="
                                     "remote(ToscaPropertyDeclaration._workflow_id),"
                                     "remote(ToscaPropertyDeclaration.role)=='OUTPUT')",
                                     back_populates='_containing_workflow',
                                     overlaps='inputs,outputs',
                                     cascade='all')


    ################################################################################
    # Relationships
    ################################################################################

    artifacts =      db.relationship('ToscaArtifact',
                                     foreign_keys='ToscaArtifact._workflow_template_id',
                                     collection_class=ordering_list('position'),
                                     order_by='ToscaArtifact.position',      
                                     backref=backref('_containing_workflow',
                                                     uselist=False),
                                     cascade='all')

    ################################################################################
    # Model Navigation
    ################################################################################

    # Get containing template if it exists. May return None
    _service =       db.relationship('ToscaServiceTemplate',
                                     foreign_keys='ToscaWorkflowTemplate._service_id')

    # The containing service template creates a '_service'
    # relationship back to itself when addint workflow templates.
    @property
    def service(self) -> Any:
        if not self._service:
            raise te.ModelCorruptionError("Workflow '{0}' does not have 'service'".format(
                                             self.name))
        return self._service

    @property
    def profile(self) -> Any:
        """Get profile. Workflows can only obtain their profile from the
        containing service
        """
        return self.service.profile

    @property
    def tosca_version(self) -> str:
        """Get tosca version from the profile.
        """
        return self.profile.tosca_version

    ################################################################################
    # Constructor
    ################################################################################

    def __init__(self,
                 preconditions: Optional[Any] = None,
                 inputs: Optional[dict[str, Any]] = None,
                 steps: Optional[dict[str, Any]] = None,
                 implementation: Optional[dict[str, Any]] = None,
                 outputs: Optional[dict[str, Any]] = None,
                 **kwargs: Any
    ) -> None:
        # First, call superclass constructor
        super(ToscaWorkflowTemplate, self).__init__(**kwargs)

        # ToscaTemplate-specific initialization
        if preconditions: self._preconditions = preconditions
        if steps: self._steps = steps
        self.implementation = implementation
        if inputs: self.inputs = inputs
        if outputs: self.outputs = outputs

    # Jump through hoops to map TOSCA "operation implementation"
    # grammar onto the database schema
    @property
    def implementation(self) -> dict[str, Any]:
        if self.artifacts:
            implementation: dict[str, Any] = dict()
            implementation['primary'] = self.artifacts[-1]
            implementation['dependencies'] = self.artifacts[:-1]
        else:
            raise AttributeError("Workflow {0} does not have 'implementation' attribute".format(self.name))
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
    # Workflow Inputs
    ################################################################################

    def get_input_declaration(self, input: str | list[str]) -> Any:
        """Return the declaration for the input specified by 'input'. This
        code is copied from the corresponding service template method
        and should be consolidated.

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
        
        
    def validate_input_values(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Validate inputs passed to this workflow template when instantiating
        a workflow, by the rules a service template's inputs follow
        (tosca_core.models.input_values).

        Args:
          inputs(dict): the input values to validate against the input
            declarations in this workflow template
        Returns:
          (possibly empty) dict of validation errors
        """
        return tosca_core.models.input_values.validate_input_values(self, self.inputs, inputs)


    ################################################################################
    # Ordering steps 
    ################################################################################

    def order_steps(self) -> list[str]:

        # Initialize
        ordered_steps: list[str] = []
        for step_name, step in self.steps.items():
            step['mark'] = None
        
        # Order
        for step_name, step in self.steps.items():
            self.add_ordered_steps(step, ordered_steps)

        # Clean up
        for step_name, step in self.steps.items():
            del step['mark']

        # All done
        return ordered_steps
        

    def add_ordered_steps(self, step: dict[str, Any], ordered_steps: list[str]) -> list[str]:
        """
        function visit(node n)
            if n has a temporary mark then stop (not a DAG)
            if n is not marked (i.e. has not been visited yet) then
                mark n temporarily
                for each node m with an edge from n to m do
                    visit(m)
                mark n permanently
                unmark n temporarily
                add n to head of L
        """

        logger.debug("Step <%s>", step['name'])
        # Check for loops
        if step['mark'] == 'processing':
            logger.debug("Step <%s>: loop detected", step['name'])
            raise RuntimeError("loop detected in '{0}' workflow".format(self.name))

        # Have we been here before?
        if step['mark'] == 'processed':
            logger.debug("Step <%s>: already processed", step['name'])
            return ordered_steps

        # Process
        step['mark'] = 'processing'
        try:
            # First, process any steps that are supposed to be executed on
            # success
            on_success_steps = step['on_success']
            for step_name in on_success_steps:
                on_success_step = self.steps[step_name]
                self.add_ordered_steps(on_success_step, ordered_steps)
        except KeyError:
            # No 'on_success' steps to process
            pass

        # Done processing this step
        logger.debug("Step <%s>: adding", step['name'])
        step['mark'] = 'processed'
        ordered_steps.insert(0, step['name'])


    ################################################################################
    # Sub-entity refinment support
    ################################################################################

    def get_entity_declaration_to_augment(self, entity_declaration_map_name: str, entity_name: str) -> Any:
        """Get declaration entity to augment. Workflows never have entity
        declarations to augment.

        """
        raise KeyError("Workflows don't augment entity declarations")
