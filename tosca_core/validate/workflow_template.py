"""
ToscaWorkflowTemplateValidator class
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2017-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger = logging.getLogger(__name__)

# Type hint support
from typing import Any, Optional

# Exception support
import tosca_core.models.exceptions as te

# Types on which this validator depends
from tosca_core.models.path import ToscaPath

# Validator
from . import get_validator
from .validator import ToscaValidator
from .activity import validate_activity as _validate_activity

# Cached lookups for TOSCA built-in data types
import tosca_core.models.builtin_types as builtin_types
import tosca_core.models.recognized_names as rn


class ToscaWorkflowTemplateValidator(ToscaValidator):
    """The ToscaWorkflowTemplateValidator class validates workflow
    templates in Tosca service templates
    """

    def __init__(self) -> None:
        """Constructor
        """
        super(ToscaWorkflowTemplateValidator, self).__init__()


    def validate_workflow_template(self, service_template: "Any", workflow: "Any") -> dict:
        """Check if a workflow is valid

        Args: 
          workflow(ToscaWorkflowTemplate): workflow template to
            validate
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """
        validation_errors = {}

        # Does this workflow have valid meta_data
        errors = self.validate_meta_data(service_template,workflow)
        if errors: validation_errors['meta_data'] = errors

        # Does this workflow have valid inputs
        errors = self.validate_inputs(service_template, workflow)
        if errors: validation_errors['inputs'] = errors

        # Does this workflow have valid preconditions
        errors = self.validate_preconditions(service_template, workflow)
        if errors: validation_errors['preconditions'] = errors

        # Does this workflow have valid steps
        errors = self.validate_steps(service_template, workflow)
        if errors: validation_errors['steps'] = errors

        # Does this workflow have a valid implementation
        errors = self.validate_implementation(service_template, workflow)
        if errors: validation_errors['implementation'] = errors

        # Does this workflow have valid outputs
        errors = self.validate_outputs(service_template, workflow)
        if errors: validation_errors['outputs'] = errors

        # Everything OK
        return validation_errors


    def validate_meta_data(self, service_template: "Any", workflow: "Any") -> dict:
        """Check if workflow inputs are valid
        """
        try:
            meta_data = workflow.meta_data
        except AttributeError:
            logger.debug("Workflow '%s': no meta_data to validate",
                         workflow.name)
            return {}

        logger.debug("Workflow '%s': validating meta_data",
                     workflow.name)
        validator = get_validator('ToscaMetaData')
        return validator.validate_meta_data(meta_data)


    def validate_inputs(self, service_template: "Any", workflow: "Any") -> dict:
        """Check if workflow inputs are valid
        """
        validator = get_validator('ToscaPropertyDeclaration')
        return self.validate_declarations(workflow, 
                                          'inputs', validator)


    def validate_preconditions(self, service_template: "Any", workflow: "Any") -> dict:
        """Check if workflow preconditions are valid
        """

        try:
            preconditions = workflow.preconditions
        except AttributeError:
            logger.debug("Workflow '%s': no preconditions to validate", workflow.name)
            return {}

        # Upgrade Version 1.3 preconditions if necessary
        if (workflow.tosca_version and
            workflow.tosca_version.startswith("tosca_simple_yaml")):
            validator = get_validator('ToscaCondition')
            errors = validator.validate_and_upgrade_workflow_preconditions(service_template, workflow)
            if errors:
                return errors
            preconditions = workflow.preconditions

        errors, canonical = self._validate_boolean_expression(workflow, preconditions, 'precondition')
        if errors:
            return errors
        workflow.preconditions = canonical
        return {}


    def validate_target(self, service_template: "Any", workflow: "Any", entity: dict) -> dict:
        """Check if workflow target are valid
        """

        # Target is mandatory. No point in defining a workflow entity
        # without target
        try:
            target = entity['target']
        except KeyError:
            return 'No target defined'

        # Validate target
        logger.debug("Workflow '%s' entity '%s': validating target '%s'",
                     workflow.name, entity['name'], target)
        
        # Find node with the specified target 
        try:
            target_node = workflow.service.node_templates[target]
        except AttributeError:
            # No node templates in service
            return "no node templates in service"
        except KeyError:
            # Not a node. If no target relationship is specified, this
            # could also be a group.
            try:
                target_relationship = entity['target_relationship']
                # Target cannot be a group.
                return "target node '{0}' not found".format(target)
            except KeyError:
                # Could be a group
                try:
                    target_group = workflow.service.groups[target]
                except (AttributeError, KeyError):
                    # Not a group either
                    return "target node or group '{0}' not found".format(target)

        # Everthing OK
        return {}


    def validate_target_relationship(self, service_template: "Any", workflow: "Any", target: "Any", entity: dict) -> dict:
        """Check if workflow target relationship is valid
        """

        # Target relationship is optional.
        try:
            target_relationship = entity['target_relationship']
            # Must only be specified if target is a 'node template'
            if target.type_class == 'group':
                return "'target_relationship' key is invalid for group targets"
        except KeyError:
            logger.debug("Workflow '%s' entity '%s': no target relationship to validate",
                         workflow.name, entity['name'])
            return {}

        # Validate 
        logger.debug("Workflow '%s' entity '%s': validating target_relationship '%s'",
                     workflow.name, entity['name'], target_relationship)
        try:
            # Make sure the target node declares a requirement with
            # the corresponding name
            requirement = target.declaration.get_requirement_declaration(target_relationship)
        except KeyError:
            return "target relationship '{0}' not found".format(target_relationship)

        validation_errors = {}
        return validation_errors


    def validate_steps(self, service_template: "Any", workflow: "Any") -> "Any":
        """Check if workflow steps are valid
        """

        # Steps are mandatory unless we have an external
        # implementation. No point in defining a workflow without
        # steps
        try:
            steps = workflow.steps
        except AttributeError:
            # No steps. This is OK as we have an implementation
            # specified
            try:
                implementation = workflow.implementation
                # It's OK to not have steps, since we have an
                # implementation.
                return None
            except AttributeError:
                # No implementation either. This is an error
                return 'No steps defined'

        # Validate each step
        validation_errors = {}
        for step_name, step in steps.items():
            try:
                logger.debug("Workflow '%s': validating step '%s'", 
                             workflow.name, step_name)
                errors = self.validate_step(service_template, workflow, step)
                if errors:
                    validation_errors[step_name] = errors
            except Exception as error:
                # Something went wrong
                logger.error("Workflow '%s': error while validating step '%s': %s", 
                             workflow.name, step_name, error)
                validation_errors[step_name] = str(error)

        # Make sure we don't have loops
        try:
            ordered_steps = workflow.order_steps()
        except Exception as e:
            logger.error("Workflow '%s': loop detected",
                         workflow.name)
            return str(e)

        # All done
        return validation_errors


    def validate_step(self, service_template: "Any", workflow: "Any", step: dict) -> dict:
        """Check if workflow steps are valid
        """

        validation_errors = {}

        # Does this step have a valid target
        errors = self.validate_target(service_template, workflow, step)
        if errors: 
            logger.error("Workflow '%s': error validating step '%s' target",
                         workflow.name, step['name'])
            validation_errors['target'] = errors
            # No point in continuing, since everything else depends on
            # having a valid target.
            return validation_errors

        # We need the target for the remaining validations. At this
        # point, we're sure target exists
        try:
            target = workflow.service.node_templates[step['target']]
        except Exception:
            target = workflow.service.groups[step['target']]

        # Does this step have a valid target_relationship
        errors = self.validate_target_relationship(service_template, workflow, target, step)
        if errors:
            validation_errors['target_relationship'] = errors
            # No point in continuing, since everything else depends on
            # having a valid target relationship
            return validation_errors

        # Does this step have a valid operation_host
        errors = self.validate_operation_host(service_template, workflow, target, step)
        if errors: validation_errors['operation_host'] = errors

        # Does this step have a valid filter
        errors = self.validate_filter(service_template, workflow, target, step)
        if errors: validation_errors['filter'] = errors

        # Does this step have valid activities
        errors = self.validate_activities(service_template, workflow, target, step)
        if errors: validation_errors['activities'] = errors

        # Does this step have a valid on_success
        errors = self.validate_on_success(service_template, workflow, step)
        if errors: validation_errors['on_success'] = errors

        # Does this step have a valid on_failure
        errors = self.validate_on_failure(service_template, workflow, step)
        if errors: validation_errors['on_failure'] = errors

        # Everything OK
        return validation_errors


    def validate_operation_host(self, service_template: "Any", workflow: "Any", target: "Any", step: dict) -> "Any":
        """Check if workflow operation host is valid.

        'operation_host' is a TOSCA 1.3 step keyname. A 2.0 step has six --
        'target', 'target_relationship', 'filter', 'activities', 'on_success'
        and 'on_failure' (section 13.2.2) -- so these rules are 1.3's, and a 2.0
        step that names a 'target_relationship' is complete without one.

        Where a relationship operation runs is not the step's to say in either
        version: the operation is implemented by an artifact, exactly as a node
        operation is, and a Bash artifact carries the 'host' property that names
        where it runs.
        """

        # These are TOSCA 1.3 rules about a TOSCA 1.3 keyname
        if (not workflow.tosca_version or
            not workflow.tosca_version.startswith("tosca_simple_yaml")):
            return {}

        try:
            operation_host = step['operation_host']
        except KeyError:
            # No operation host specified
            operation_host = None
        try:
            target_relationship = step['target_relationship']
        except KeyError:
            target_relationship = None

        # Is target a node template?
        if target.type_class == 'node':
            if target_relationship and not operation_host:
                return "no 'operation_host' specified for 'target_relationship'"
            if not target_relationship and operation_host:
                return "'operation_host' specified without 'target_relationship'" 
            # operation_host must be SOURCE or TARGET
            if operation_host and not operation_host in ['SOURCE', 'TARGET']:
                error = "invalid 'operation_host' value '{0}'".format(operation_host)
                return error
        elif target.type_class == 'group':
            logger.error("NOT IMPLEMENTED")

        validation_errors = {}
        return validation_errors


    def validate_filter(self, service_template: "Any", workflow: "Any", target: "Any", step: dict) -> dict:
        """Validate a workflow step's 'filter'. The model carries one
        shape -- a 2.0 boolean function expression -- so v1.3 filters
        get walked and rewritten via the existing upgrade machinery
        before the standard boolean-function validator runs (same
        pattern as workflow preconditions and node filters).
        """
        # filter is optional.
        try:
            filter = step['filter']
        except KeyError:
            logger.debug("Workflow '%s' step '%s': no filter to validate",
                         workflow.name, step['name'])
            return {}

        # v1.3 condition trees are a list of and / or / not / assert
        # records. Validate the legacy shape first, then rewrite into
        # a 2.0 boolean function so the rest of the orchestrator only
        # has to deal with one form.
        if (workflow.tosca_version and
                workflow.tosca_version.startswith("tosca_simple_yaml")):
            condition_validator = get_validator('ToscaCondition')
            errors = condition_validator.validate_and_upgrade_workflow_step_filter(
                service_template, step)
            if errors:
                return errors
            filter = step['filter']

        errors, canonical = self._validate_boolean_expression(workflow, filter, 'filter')
        if errors:
            return errors
        step['filter'] = canonical
        return {}


    def validate_activities(self, service_template: "Any", workflow: "Any", target: "Any", step: dict) -> "Any":
        """Check if workflow activities are valid
        """

        # Activities are mandatory. No point in defining a workflow
        # step without activities
        try:
            activities = step['activities']
            if not activities: return 'No activities defined'
        except KeyError:
            return 'No activities defined'

        # Get target_relationship if specified
        try:
            target_relationship = step['target_relationship']
        except KeyError:
            target_relationship = None

        # Validate each activity
        logger.debug("Workflow '%s' step '%s': validating activities '%s'",
                     workflow.name, step['name'], activities)
        validation_errors = {}

        counter = 0
        for activity in activities:
            activity['name'] = str(counter)
            logger.debug("validating activity '%s'", activity['name'])
            counter = counter+1
            errors = self.validate_activity(service_template, workflow, target, target_relationship, activity)
            if errors: validation_errors[activity['name']] = errors

        return validation_errors


    def validate_activity(self, service_template: "Any", workflow: "Any", target: "Any", target_relationship: "Any", activity: dict) -> "Any":
        """Check if workflow activities are valid
        """

        def resolve_call_operation(call_operation: dict, interface_name: str, operation_name: str) -> "Any":
            declaration = target.declaration
            if target_relationship:
                requirement = declaration.get_requirement_declaration(target_relationship)
                declaration = requirement
            try:
                interface = rn.lookup_interface(declaration.get_interface_declaration, interface_name)
            except KeyError:
                return "No interface '{0}' defined on '{1}'".format(interface_name, declaration.name)
            try:
                operation = rn.lookup_operation(interface.get_operation_declaration, operation_name)
            except KeyError:
                return "operation '{0}' not defined".format(operation_name)
            errors = self.validate_operation_inputs(service_template, workflow, target, target_relationship,
                                                    interface, operation, call_operation)
            if errors:
                return {'inputs': errors}
            return None

        return _validate_activity(
            workflow, activity,
            owner_label='Workflow',
            changed_collection=workflow.steps,
            call_operation_resolver=resolve_call_operation,
        )


    def validate_operation_inputs(self, service_template: "Any", workflow: "Any", target: "Any", target_relationship: "Any",
                                  interface_declaration: "Any", operation_declaration: "Any", call_operation: dict) -> dict:
        """Validate call operation activity inputs"""
        errors = dict()
        try:
            inputs = call_operation['inputs']
        except KeyError:
            inputs = dict()

        # Get interface and operation input declarations
        interface_input_declarations = interface_declaration.get_input_declarations()
        operation_input_declarations = operation_declaration.get_input_declarations()

        # Validate each individual input value
        validated = dict()
        for input_name, input_value in inputs.items():
            # Find corresponding input declaration
            try:
                # Is this an operation input
                input_declaration = operation_input_declarations[input_name]
            except KeyError:
                try:
                    # Is this an interface input
                    input_declaration = interface_input_declarations[input_name]
                except KeyError:
                    logger.error("'%s.%s': undefined input '%s'",
                                 interface_declaration.name, operation_declaration.name,
                                 input_name)
                    errors[input_name] = 'not previously defined'
                    continue
                    
            # Make sure this input doesn't override a fixed
            # value defined in the input declaration
            try:
                value = input_declaration.value
                errors[input_name] = 'overriding value from definition is not allowed'
            except AttributeError:
                # No fixed value defined in the declaration. Validate
                # input value against input declaration.
                try:
                    validated[input_name] = input_declaration.validate_value(
                        workflow, input_value, check_presence=True)
                except te.ValidationError as e:
                    logger.error("'%s.%s' input '%s': '%s' is invalid value for %s",
                                 interface_declaration.name, operation_declaration.name,
                                 input_name, input_value,
                                 input_declaration.type)
                    validated[input_name] = input_value
                    errors[input_name] = e.errors
            except Exception as e:
                errors[input_name] = 'validator error ({0})'.format(str(e))

        # Make sure all required inputs are provided. First, get the
        # inputs from the target node or target relationship template.
        # ``target_relationship`` is the requirement *name* from the
        # workflow YAML (a string); resolve it to the relationship
        # template on ``target`` before treating it as a managed
        # template. Falls back to ``target`` if the requirement name
        # doesn't resolve (validate_target_relationship has already
        # rejected unknown names, but be defensive).
        if target_relationship:
            managed_template = target.get_requirement(target_relationship) or target
        else:
            managed_template = target
        try:
            interface_template = managed_template.interfaces[interface_declaration.name]
            interface_inputs = interface_template.inputs
            try:
                operation_template = interface_template.operations[operation_declaration.name]
                operation_inputs = operation_template.inputs
            except (TypeError, KeyError):
                # No operation template
                operation_inputs = dict()
        except (TypeError, KeyError):
            # No interface template
            interface_inputs = dict()
            operation_inputs = dict()

        # Make sure all required interface inputs are provided. Skip
        # inputs the per-value loop already flagged: the earlier error
        # (e.g. "$get_input: [...] not found") is strictly more
        # informative than a generic presence complaint.
        for input_name, input_declaration in interface_input_declarations.items():
            if input_name in errors:
                continue
            # Is this a required input?
            if input_declaration.is_required():
                # First, check if this input value is defined in the
                # service template
                error = input_declaration.validate_value_presence(managed_template, interface_inputs)
                if error:
                    # Is this input value defined in the workflow?
                    try:
                        value = validated[input_name]
                        if not input_declaration.is_value_present(value, workflow):
                            errors[input_name] = 'required but input is optional'
                    except (TypeError, KeyError):
                        # Not defined in the workflow either
                        errors[input_name] = error

        # Make sure all required operation inputs are provided.
        for input_name, input_declaration in operation_input_declarations.items():
            if input_name in errors:
                continue
            # Is this a required input?
            if input_declaration.is_required():
                # First, check if this input value is defined in the
                # service template
                error = input_declaration.validate_value_presence(managed_template, operation_inputs)
                if error:
                    # Is this input value defined in the workflow?
                    try:
                        value = validated[input_name]
                        if not input_declaration.is_value_present(value, workflow):
                            errors[input_name] = 'required but input is optional'
                    except (TypeError, KeyError):
                        # Not defined in the workflow either
                        errors[input_name] = error

        # All done
        if inputs:
            call_operation['inputs'] = validated
            # 'steps' is a MutableDict, but this assigns into a dict nested
            # inside it, which MutableDict does not track.
            workflow.steps.changed()
        return errors

    
    def validate_on_success(self, service_template: "Any", workflow: "Any", step: dict) -> dict:
        """Check if workflow on_success is valid
        """

        # on_success is optional.
        try:
            on_success = step['on_success']
        except KeyError:
            logger.debug("Workflow '%s' step '%s': no on_success to validate",
                         workflow.name, step['name'])
            return {}

        # Validate 
        validation_errors = {}
        for step_name in on_success:
            logger.debug("Workflow '%s' step '%s': validating 'on_success' step '%s'",
                         workflow.name, step['name'], step_name)
            try:
                step = workflow.steps[step_name]
            except Exception as e:
                # Step not found
                validation_errors[step_name] = 'step not found'

        return validation_errors


    def validate_on_failure(self, service_template: "Any", workflow: "Any", step: dict) -> dict:
        """Check if workflow on_failure is valid
        """

        # on_failure is optional.
        try:
            on_failure = step['on_failure']
        except KeyError:
            logger.debug("Workflow '%s' step '%s': no on_failure to validate",
                         workflow.name, step['name'])
            return {}

        # Validate 
        validation_errors = {}
        for step_name in on_failure:
            logger.debug("Workflow '%s' step '%s': validating 'on_failure' step '%s'",
                         workflow.name, step['name'], step_name)
            try:
                failure_step = workflow.steps[step_name]
            except Exception as e:
                # Step not found
                logger.error("Workflow '%s' step '%s': 'on_failure' step '%s' not found",
                             workflow.name, step['name'], step_name)
                validation_errors[step_name] = 'step not found'

        return validation_errors


    def validate_implementation(self, service_template: "Any", workflow: "Any") -> "Any":
        """Check if workflow implementation is valid
        """
        
        try:
            implementation = workflow.implementation
        except AttributeError:
            # No implementation. That's OK
            return None

        # We have an implementation, which means we must not have
        # 'steps'
        try:
            steps = workflow.steps
            # Can't have both implementation and steps
            return "not allowed here since workflow defines 'steps'"
        except AttributeError:
            pass

        # Validate operation implementation
        validation_errors = {}
        validator = get_validator('ToscaOperationImplementation')
        try:
            errors = validator.validate_implementation(workflow)
            if errors:
                logger.error("Workflow %s: Invalid implementation", 
                             workflow.name)
                return errors
        except Exception as e:
            return 'internal error <{0}>'.format(str(e))

        # Everything OK
        return validation_errors

    
    def validate_outputs(self, service_template: "Any", workflow: "Any") -> "Any":
        """Check if a workflow has valid output mappings.
        """

        # Do we have outputs?
        outputs = workflow.outputs
        if not outputs:
            logger.debug("%s: no outputs to validate", workflow.name)
            return None

        # An output of a workflow defined by an implementation is incoming
        # (§9.8): the implementation returns the value and the output maps it
        # onto an attribute, so it takes a mapping -- written out, or as the
        # short notation of a list -- and never a value. An output of a
        # workflow defined by steps is outgoing and takes a value, never a
        # mapping.
        try:
            implementation = workflow.implementation
            external = True
        except AttributeError:
            external = False
        form_errors = {}
        for output_name, output_declaration in outputs.items():
            has_value = output_declaration._value is not None
            has_mapping = output_declaration._mapping is not None
            if external:
                if has_value and (has_mapping or not isinstance(output_declaration._value, list)):
                    form_errors[output_name] = (
                        "an output of a workflow defined by an implementation is set "
                        "by that implementation: give the attribute mapping that "
                        "stores it, not a value")
            elif has_mapping:
                form_errors[output_name] = (
                    "an output of a workflow defined by steps is set by the "
                    "workflow: give its value, not an attribute mapping")
        if form_errors:
            return form_errors
        if external:
            self.fixup_mappings_in_outputs(workflow)

        # Validate all outputs 
        validator = get_validator('ToscaPropertyDeclaration')
        errors = self.validate_declarations(workflow, 'outputs', validator)

        # Resolve any functions in output definitions
        if not errors:
            for output_name, output_declaration in outputs.items():
                output_declaration.resolve_functions_in_declared_values(workflow)

        # All done
        return errors


    def validate_output(self, context: "Any", output_mapping: "Any") -> Optional[str]:
        """Check if an output mapping is valid within the provided context and
        compatible with the provided output declaration.
        Args:
          context(ToscaServiceTemplate): context within which to
            evaluate the mapping
          output_mapping(ToscaPath): output mapping to validate
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """
        # First, make sure mapping is a valid path expression.
        try:
            path = ToscaPath(output_mapping)
        except TypeError:
            return 'improperly-formatted output mapping'

        # Find the attribute referenced by the output mapping
        _, error = self._resolve_attribute_declaration(context, path)
        if error:
            return error


    def fixup_mappings_in_outputs(self, template: "Any") -> None:
        """Fix up output mappings. This is a KLUDGE: by default the parser
        uses the 'value' keyword for outputs even when they are
        supposed to be output mappings. This method assings the value
        of the 'value' keyword to the 'mapping' keyword. If necessary,
        it also upgrades the mapping to the new TOSCA Path syntax.

        """
        if (not template.tosca_version or
            not template.tosca_version.startswith("tosca_simple_yaml")):
            # Nothing to do
            upgrade = False
        else:
            upgrade = True

        # We have a Version 1.x file. Upgrade each output declaration
        outputs = template.outputs
        for output_name, output_declaration in outputs.items():
            # A mapping written out needs nothing moved
            if output_declaration._value is None:
                continue
            # Move value to mapping
            output_declaration._mapping = output_declaration._value
            output_declaration._value = None
            # Upgrade if necessary
            if upgrade:
                output_declaration.upgrade_tosca_path_in_mapping(template)
