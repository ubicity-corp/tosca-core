"""
ToscaServiceTemplateValidator class
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2014-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger = logging.getLogger(__name__)

# Validator
from . import get_validator
from .validator import ToscaValidator

from typing import TYPE_CHECKING, Any, Optional
if TYPE_CHECKING:
    from tosca_core.models.service_template import ToscaServiceTemplate
    from tosca_core.models.relationship_template import ToscaRelationshipTemplate


class ToscaServiceTemplateValidator(ToscaValidator):
    """ToscaServiceTemplateValidator class validates service templates
    defined in TOSCA files.
    """

    def __init__(self) -> None:
        """Constructor
        """
        super(ToscaServiceTemplateValidator, self).__init__()


    def validate_service_template(self, service_template: "ToscaServiceTemplate") -> dict:
        """Check if a service template is valid.

        Args:
          service_template(ToscaServiceTemplate): service template to
            validate
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None

        """
        logger.debug("Service Template '%s': validating", service_template.name)

        validation_errors = dict()

        # Validate relationship templates separately first, even
        # though they will be validated again later after they have
        # been copied into requirements. The reason is that this first
        # validation step will validate and set the type.
        errors = self.validate_relationship_templates(service_template)
        if errors:
            validation_errors['relationship_templates'] = errors

        # Does this service template define valid node templates?
        errors = self.validate_node_templates(service_template)
        if errors:
            validation_errors['node_templates'] = errors

        # Does this service template define valid groups?
        errors = self.validate_groups(service_template)
        if errors:
            validation_errors['groups'] = errors

        # Does this service template define valid workflows?
        errors = self.validate_workflow_templates(service_template)
        if errors:
            validation_errors['workflows'] = errors

        # Does this service template define valid policies?
        errors = self.validate_policies(service_template)
        if errors:
            validation_errors['policies'] = errors

        # Does this service template have valid input definitions?
        validator = get_validator('ToscaPropertyDeclaration')
        errors = self.validate_declarations(service_template, 'inputs', validator)
        if errors:
            validation_errors['inputs'] = errors

        # Does this service template have valid output definitions?
        errors = self.validate_declarations(service_template, 'outputs', validator)
        if errors:
            validation_errors['outputs'] = errors
        else:
            # Resolve functions in outputs to the internal function
            # syntax.
            self.resolve_functions_in_output_declarations(service_template)

        # Finally, validate substitution mappings
        errors = self.validate_substitution_mappings(service_template)
        if errors:
            validation_errors['substitution_mappings'] = errors

        # If there are errors, add line number if it exists
        self.add_line_number(validation_errors, service_template)

        # All done
        return validation_errors
        

    def validate_relationship_templates(self, service_template: "ToscaServiceTemplate") -> dict:
        """Validate relationship templates in this service template's topology
        graph.

        Args: 
          service_template(ToscaServiceTemplate): service template for
            which to validate relationship templates
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """

        validation_errors = dict()

        # Check if this service template declares relationship
        # templates.
        try:
            relationship_templates = service_template.relationship_templates
        except AttributeError:
            # This service template does not declare relationship
            # templates. Nothing to validate
            logger.debug("Service Template '%s': no relationship templates to validate", 
                         service_template.name)
            return validation_errors

        # Validate each relationship template.
        for relationship_template_name, relationship_template in relationship_templates.items():
            try:
                errors = self.validate_relationship_template(service_template, relationship_template)
                if errors:
                    logger.error("Service Template '%s': Invalid relationship template '%s'", 
                                 service_template.name, relationship_template_name)
                    validation_errors[relationship_template_name] = errors
            except Exception as error:
                # Something went wrong
                logger.error("Service Template '%s': error while validating relationship templates: %s", 
                             service_template.name, error)
                validation_errors[relationship_template_name] = "validator error ({0})".format(error)

        # All done
        return validation_errors


    def validate_relationship_template(self, service_template: "ToscaServiceTemplate", relationship_template: "ToscaRelationshipTemplate") -> dict:
        """Validate a relationship template defined in this service template's
        topology graph.

        Args: 
          service_template(ToscaServiceTemplate): service template for
            which to validate relationship templates
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """

        logger.debug("Service Template '%s': validating relationship template '%s'", 
                     service_template.name, relationship_template.name)

        # Get the relationship template validator
        validator = get_validator('ToscaRelationshipTemplate')

        # First, resolve any references to turn this into a proper
        # relationship template.
        errors = validator.resolve_indirections(relationship_template)
        if errors:
            logger.error("Service Template '%s': relationship template ''%s'' has invalid indirections",
                         service_template.name, relationship_template.name)
            return errors

        # Is this a valid relationship template? Validate just the
        # 'managed template' part, since a relationship validator will
        # treat the relationship template as if it were a requirement,
        # and it will complain about fields missing in the
        # declaration.
        validator = get_validator('ToscaManagedTemplate')
        return validator.validate_typed_template(relationship_template)


    def validate_node_templates(self, service_template: "ToscaServiceTemplate") -> dict:
        """Validate node templates defined in this service template.

        The validation is done in separate phases:

        - First, we validate those aspects of node templates that are
          related to the topology graph. This involves resolving the
          capabilities and relationships in node templates.

        - Next, we validate all value-related aspects of the node
          templates. We do this in a separate phase because these
          values may consist of functions that traverse the topology.

        Args: 
          service template(ToscaServiceTemplate): service template for
            which to validate node templates
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """

        validation_errors = dict()

        # Validate the service topology by validating each node
        # template's capabilities and requirements
        validator = get_validator('ToscaNodeTemplate')
        node_templates = service_template.node_templates
        for node_template_name, node_template in node_templates.items():
            try:
                errors = validator.validate_node_template_topology(node_template)
                if errors:
                    logger.error("Service Template '%s': Invalid node template '%s'", 
                                 service_template.name, node_template_name)
                    validation_errors[node_template_name] = errors
            except Exception as error:
                # Something went wrong
                logger.error("Service Template '%s': error while validating node templates: %s", 
                             service_template.name, error)
                validation_errors[node_template_name] = "validator error ({0})".format(error)

        if validation_errors:
            return validation_errors

        # A loop of explicit dependencies or containments has no order to
        # build or tear down in, so no service may hold one.
        loop = self.find_dependency_loop(node_templates)
        if loop:
            logger.error("Service Template '%s': dependency loop: %s",
                         service_template.name, ' -> '.join(loop))
            validation_errors[loop[0]] = "dependency loop: {0}".format(' -> '.join(loop))
            return validation_errors
        
        # Validate each node template's values
        for node_template_name, node_template in node_templates.items():
            try:
                errors = validator.validate_template(node_template)
                if errors:
                    logger.error("Service Template '%s': Invalid node template '%s'", 
                                 service_template.name, node_template_name)
                    validation_errors[node_template_name] = errors
            except Exception as error:
                # Something went wrong
                logger.error("Service Template '%s': error while validating node templates: %s", 
                             service_template.name, error)
                validation_errors[node_template_name] = "validator error ({0})".format(error)

        # All done
        return validation_errors


    def find_dependency_loop(self, node_templates: dict) -> Optional[list[str]]:
        """Return the node template names of a loop the explicit
        requirements form, first name repeated last, or None.

        An edge runs from a node template to the target its requirement
        names, for every requirement that is not dangling and orders its
        ends: associations order nothing, as in the service's node order.
        A loop between templates is a loop between every representation
        they yield. A dangling requirement's target is chosen at
        fulfillment, which never chooses one that closes a loop.
        """
        def targets(node_template: Any) -> list[str]:
            names = []
            for relationship_template in node_template.relationships:
                if relationship_template.is_dangling():
                    continue
                kind = relationship_template.declaration.type_entity.get_kind()
                if kind == 'ASSOCIATION':
                    continue
                names.append(relationship_template.target_node.name)
            return names

        marks: dict[str, str] = {}

        def visit(name: str, path: list[str]) -> Optional[list[str]]:
            if marks.get(name) == 'processing':
                return path[path.index(name):] + [name]
            if marks.get(name) == 'processed' or name not in node_templates:
                return None
            marks[name] = 'processing'
            path.append(name)
            for target in targets(node_templates[name]):
                loop = visit(target, path)
                if loop:
                    return loop
            path.pop()
            marks[name] = 'processed'
            return None

        for name in node_templates:
            loop = visit(name, [])
            if loop:
                return loop
        return None


    def validate_groups(self, service_template: "ToscaServiceTemplate") -> dict:
        """Check if a service template has valid group declarations.

        Args: 
          service_template(ToscaServiceTemplate): service template for
            which to validate group declarations.
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """

        validation_errors = dict()

        # Check if this service template declares groups
        try:
            groups = service_template.groups
        except AttributeError:
            # This service template does not declare groups. Nothing
            # to validate.
            logger.debug("Service Template '%s': no groups to validate", 
                         service_template.name)
            return validation_errors

        # Validate each group declaration
        validator = get_validator('ToscaGroup')
        for group_name, group in groups.items():
            logger.debug("Service Template '%s': validating group '%s'", 
                         service_template.name, group_name)
            try:
                errors = validator.validate_typed_template(group)
                if errors:
                    validation_errors['group_name'] = errors
            except Exception as error:
                # Something went wrong
                logger.error("Service Template '%s': error while validating groups: %s", 
                             service_template.name, error)
                validation_errors['group_name'] = "validator error ({0})".format(error)

        # All done
        return validation_errors


    def validate_workflow_templates(self, service_template: "ToscaServiceTemplate") -> dict:
        """Validate workflow templates defined in this service template.

        Args: 
          service_template(ToscaServiceTemplate): service template for
            which to validate workflow templates
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None

        """

        # Check if this service template declares workflows
        try:
            workflows = service_template.workflows
        except AttributeError:
            # This service template does not declare
            # workflows. Nothing to validate.
            logger.debug("Service Template '%s': no workflows to validate", 
                         service_template.name)
            return {}

        # Validate workflows
        validator = get_validator('ToscaWorkflowTemplate')
        validation_errors = dict()
        for workflow_name, workflow in workflows.items():
            try:
                logger.debug("Service Template '%s': validating workflow '%s'", 
                             service_template.name, workflow_name)
                errors = validator.validate_workflow_template(service_template, workflow)
                if errors:
                    validation_errors[workflow_name] = errors
            except Exception as error:
                # Something went wrong
                logger.error("Service Template '%s': error while validating workflow '%s': %s", 
                             service_template.name, workflow_name, error)
                validation_errors[workflow_name] = str(error)

        # All done
        return validation_errors


    def validate_substitution_mappings(self, service_template: "ToscaServiceTemplate") -> dict:
        """Check if a service template has valid substitution mappings.

        Args: 
          service_template(ToscaServiceTemplate): service template for
            which to validate substitution_mappings
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """

        # Check if this service template declares substitution_mappings.
        try:
            substitution_mappings = service_template.substitution_mappings
        except AttributeError:
            # This service template does not declare substitution
            # mappings. Nothing to validate.
            logger.debug("Service Template '%s': no substitution_mappings to validate", 
                         service_template.name)
            return {}

        # Validate substitution mappings
        validator = get_validator('ToscaSubstitutionMappings')
        try:
            logger.debug("Service Template '%s': validating substitution mappings", 
                         service_template.name)
            return validator.validate_substitution_mappings(service_template, substitution_mappings)

        except Exception as error:
            # Something went wrong
            logger.error("Service Template '%s': error while validating substitution_mappings: %s", 
                         service_template.name, error)
            return "validator error ({0})".format(str(error))

        # Substitution mappings valid
        return {}


    def validate_policies(self, service_template: "ToscaServiceTemplate") -> dict:
        """Check if a service template has valid policy declarations

        Args: 
          service_template(ToscaServiceTemplate): service template for
            which to validate policies.
        Returns:
          (Possibly empty) dict of validation errors
        Raises:
          None
        """

        # Check if this service template declares policies
        try:
            policies = service_template.policies
        except AttributeError:
            # This service template does not declare policies. Nothing
            # to validate.
            logger.debug("Service Template '%s': no policies to validate", 
                         service_template.name)
            return {}

        # Validate policies
        validation_errors = dict()
        validator = get_validator('ToscaPolicy')
        for policy in policies:
            try:
                logger.debug("Service Template '%s': validating policy '%s'", 
                             service_template.name, policy.name)
                errors = validator.validate_typed_template(policy)
                if errors:
                    validation_errors[policy.name] = errors
            except Exception as error:
                # Something went wrong
                logger.error("Service Template '%s': error while validating policy '%s': %s", 
                             service_template.name, policy.name, error)
                validation_errors[policy.name] = str(error)

        # All done
        return validation_errors


    def resolve_functions_in_output_declarations(self, service_template: "ToscaServiceTemplate") -> None:
        """Resolve functions in service template outputs to the internal
        function syntax.
        """
        # Upgrade each output declaration
        outputs = service_template.outputs
        for output_name, output_declaration in outputs.items():
            output_declaration.resolve_functions_in_declared_values(service_template)
