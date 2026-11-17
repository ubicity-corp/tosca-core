"""
Version 1.x condition validator class
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2018-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger = logging.getLogger(__name__)

# Validator
from .validator import ToscaValidator

# Types on which this validator depends
from tosca_core.models.path import ToscaPath


class ToscaConditionValidator(ToscaValidator):
    """The ToscaConditionValidator class validates Version 1.x condition
    statements in Tosca policies and workflows

    """

    def __init__(self) -> None:
        """Constructor
        """
        super(ToscaValidator, self).__init__()


    def validate_and_upgrade_trigger_conditions(self, service_template: object, trigger: dict) -> object:
        """Check if a policy trigger defines valid conditions and upgrade to
        Version 2.0 condition syntax.
        """
        # Validate
        logger.debug("Trigger '%s': validating condition", trigger['name'])
        validation_errors = {}

        # Make sure we have a condition that defines constraints.
        condition = trigger["condition"]
        try:
            constraints = condition["constraint"]
        except KeyError:
            logger.debug("Trigger %s does not define constraints.", trigger['name'])
            return 'no constraints specified'

        # Make sure we have a target filter with a target node.
        try:
            target_filter = trigger["target_filter"]
            node = target_filter["node"]
        except KeyError:
            logger.error("Trigger %s does not specify a target node", trigger['name'])
            return 'no target node specified'

        # Construct the target path
        target_path = [ node ]
        try:
            requirement = target_filter["requirement"]
            target_path.extend(['RELATIONSHIP', requirement, 'TARGET'])
        except KeyError:
            pass
        try:
            capability = target_filter["capability"]
            target_path.extend(['CAPABILITY', capability])
        except KeyError:
            pass

        # Validate condition for the target path
        errors = self.validate_conditions(service_template, target_path, constraints)
        if errors:
            logger.error("Trigger %s: invalid constraints.", trigger['name'])
            validation_errors["constraints"] = errors
            return validation_errors

        # Everything checks out. Upgrade.
        upgraded = self.upgrade_conditions(service_template, target_path, constraints)
        if len(upgraded) == 1:
            trigger['condition'] = upgraded[0]
        else:
            trigger['condition'] = { '$and': upgraded }

        # All done
        return validation_errors


    def validate_and_upgrade_workflow_preconditions(self, service_template: object, workflow: object) -> dict:
        """Check if a workflow has valid preconditions and upgrade to Version
        2.0 condition syntax.
        """

        # Validate
        logger.debug("Workflow '%s': validating preconditions", workflow.name)
        validation_errors = {}
        workflow.upgraded = list()
        counter = 0
        for precondition in workflow.preconditions:
            precondition['name'] = str(counter)
            logger.debug("validating precondition '%s'", precondition['name'])
            counter = counter+1
            errors = self.validate_and_upgrade_precondition(service_template, workflow, precondition)
            if errors: 
                logger.error("Workflow '%s': error validating precondition '%s'",
                             workflow.name, precondition['name'])
                validation_errors[precondition['name']] = errors

        # If there were no validation errors, use the upgraded preconditions
        if not validation_errors:
            if len(workflow.upgraded) == 1:
                workflow.preconditions = workflow.upgraded[0]
            else:
                workflow.preconditions = { '$and': workflow.upgraded }

        return validation_errors


    def validate_and_upgrade_precondition(self, service_template: object, workflow: object, precondition: dict) -> object:
        """Check if a workflow precondition is valid
        """

        validation_errors = {}

        # Make sure the precondition defines a condition
        try:
            condition = precondition["condition"]
        except KeyError:
            return 'no condition specified'

        # Make sure the precondition defines a target
        try:
            target = precondition['target']
        except KeyError:
            return 'No target defined'

        # Construct the target path
        target_path = [ target ]
        try:
            target_relationship = precondition["target_relationship"]
            target_path.extend(['RELATIONSHIP', target_relationship])
        except KeyError:
            pass

        # Validate condition for the target path
        errors = self.validate_conditions(service_template, target_path, condition)
        if errors:
            validation_errors['condition'] = errors

        # Everything checks out. Upgrade.
        c  = self.upgrade_conditions(service_template, target_path, condition)
        workflow.upgraded.extend(c)

        return validation_errors


    def validate_and_upgrade_workflow_step_filter(self, service_template: object, step: dict) -> object:
        """Check if a workflow step filter is valid and upgrade to Version
        2.0 condition syntax. Mirrors
        validate_and_upgrade_workflow_preconditions in shape, but a step
        filter is a single condition tree rather than a list of
        per-target records, so the target_path is built once from
        step['target'] (and step['target_relationship'] when present).
        Mutates step['filter'] in place on success.
        """
        logger.debug("Step '%s': validating filter", step['name'])

        target_path = [step['target']]
        target_relationship = step.get('target_relationship')
        if target_relationship:
            target_path.extend(['RELATIONSHIP', target_relationship])

        raw = step['filter']
        try:
            errors = self.validate_conditions(service_template, target_path, raw)
            if errors:
                return errors
        except Exception as e:
            return "validator error ({0})".format(e)

        upgraded = self.upgrade_conditions(service_template, target_path, raw)
        if len(upgraded) == 1:
            step['filter'] = upgraded[0]
        else:
            step['filter'] = {'$and': upgraded}

        return {}


    def validate_conditions(self, service_template, target_path, conditions):
        """Check if conditions are valid for the specified target path within
        the provide service_template.

        """
        
        validation_errors = {}
        
        # Validate each individual condition
        counter = 0
        for condition in conditions:
            condition['name'] = str(counter)
            counter = counter+1
            errors = self.validate_condition(service_template, target_path, condition)
            if errors: validation_errors[condition['name']] = errors

        return validation_errors


    def validate_condition(self, service_template, target_path, condition):
        """Check if a target_path has a valid condition

        Args:

          service_template(ToscaServiceTemplate): service_template
            template for which to validate the target_path
        Returns:
          (Possibly empty) dict of validation errors

        Raises:
          None

        """

        # A condition is either an 'and', an 'or', a 'not', or an
        # 'assert'. Make sure we only have one.
        conditions = [c for c in ['and_', 'or_', 'not_', 'assert_'] if c in condition]
        if len(conditions) != 1:
            logger.error("Condition '%s': multiple operands %s",
                         condition['name'], condition)
            return "multiple actions specified"

        validation_errors = {}

        if 'and_' in condition:
            errors = self.validate_conditions(service_template, target_path, condition['and_'])
            if errors: validation_errors['and'] = errors
            return validation_errors

        if 'or_' in condition:
            errors = self.validate_conditions(service_template, target_path, condition['or_'])
            if errors: validation_errors['or'] = errors
            return validation_errors

        if 'not_' in condition:
            errors = self.validate_conditions(service_template, target_path, condition['not_'])
            if errors: validation_errors['not'] = errors
            return validation_errors

        if 'assert_' in condition:
            try:
                errors = self.validate_assertions(service_template, target_path, condition['assert_'])
                if errors: validation_errors['assert'] = errors
                return validation_errors
            except Exception as e:
                logger.error("Error validating 'assert': %s", str(e))
                return "validator error {0}".format(str(e))

        # Unreachable: the exactly-one check above guarantees one branch matched.
        logger.error("UNKNOWN condition operation '%s'", str(condition))
        return 'unknown condition operation specified'


    def validate_assertions(self, service_template, target_path, assertions):
        """Check if target_path list of assertions is valid
        """
        validation_errors = {}
        counter = 0
        for assertion in assertions:
            name = str(counter)
            counter = counter+1
            errors = self.validate_assertion(service_template, target_path, assertion)
            if errors: validation_errors[name] = errors

        return validation_errors


    def validate_assertion(self, service_template, target_path, assertion):
        """Check if target_path assertions are valid
        """

        validation_errors = {}

        # Attribute is mandatory. No point in defining constraints
        # without attributes to which to apply the constraints
        try:
            attribute = assertion['attribute']
        except AttributeError:
            return 'No attribute defined'

        # Constraints are mandatory. No point in defining assertion
        # without constraints
        try:
            constraints = assertion['constraints']
            if not constraints: return 'No constraints defined'
        except AttributeError:
            return 'No constraints defined'

        # Make sure the attribute exists
        targeted_attribute = list(target_path)
        targeted_attribute.append(attribute)
        path = ToscaPath(targeted_attribute, head_index=True)
        try:
            node_declaration = path.get_entity_declaration(service_template)
            attribute_declaration = node_declaration.get_attribute_declaration(path.sub_entity)
            # A target naming several representations carries one value each,
            # so the constraints below are checked against a list of that
            # attribute rather than the attribute itself.
            if path.head_yields_list(node_declaration):
                from tosca_core.models.property_declaration import as_list_declaration
                attribute_declaration = as_list_declaration(
                    attribute_declaration, path.entity, 'attributes')
        except Exception:
            return "Attribute {0} not found".format(str(targeted_attribute))

        # Are constraints valid?
        try:
            errors = attribute_declaration.validate_constraints(service_template, constraints)
            if errors:
                logger.error("'%s': constraints are not compatible with type '%s'",
                             attribute_declaration.name,  
                             attribute_declaration.type_entity.name)
                return errors
        except Exception as e:
            logger.error("'%s': error while validating constraints: %s",
                         attribute_declaration.name, e)
            error = "validator error <{0}>".format(e)
            return error

        return None


    def upgrade_conditions(self, service_template, target_path, conditions):
        """Check if conditions are valid for the specified target path within
        the provide service_template.

        """
        # Upgrade each individual condition
        upgraded = list()
        for condition in conditions:
            c = self.upgrade_condition(service_template, target_path, condition)
            if isinstance(c, list):
                upgraded.extend(c)
            else:
                upgraded.append(c)
        return upgraded 


    def upgrade_condition(self, service_template, target_path, condition):
        """Upgrade a Version 1.x condition clause to Version 2.0 condition
        syntax. Note that the condition is known t be valid.

        Args:

          service_template(ToscaServiceTemplate): service_template
            template for which to upgrade the target_path
        Returns:
          boolean function

        Raises:
          None
        """

        # A condition is exactly one of and_/or_/not_/assert_ -- the
        # validator above has guaranteed that. Dispatch directly.

        if 'and_' in condition:
            conditions = self.upgrade_conditions(service_template, target_path, condition['and_'])
            if len(conditions) == 1:
                return conditions[0]
            return {'$and': conditions}

        if 'or_' in condition:
            conditions = self.upgrade_conditions(service_template, target_path, condition['or_'])
            if len(conditions) == 1:
                return conditions[0]
            return {'$or': conditions}

        if 'not_' in condition:
            conditions = self.upgrade_conditions(service_template, target_path, condition['not_'])
            if len(conditions) == 1:
                return {'$not': conditions[0]}
            return {'$not': {'$and': conditions}}

        if 'assert_' in condition:
            return self.upgrade_assertions(service_template, target_path, condition['assert_'])

        # Unreachable: validator guarantees one branch matches.
        return None


    def upgrade_assertions(self, service_template, target_path, assertions):
        """Upgrade a list of assertions to the Version 2.0 condition syntax
        """
        # Upgrade each individual assertion
        upgraded = list()
        for assertion in assertions:
            upgraded.extend(self.upgrade_assertion(service_template, target_path, assertion))
        return upgraded

    def upgrade_assertion(self, service_template, target_path, assertion):
        """Upgrade a condition assertion to the Version 2.0 condition syntax
        """

        attribute = assertion['attribute']
        constraints = assertion['constraints']

        # Make sure the attribute exists
        path = list(target_path)
        path.append(attribute)

        # Upgrade each constraint
        upgraded = list()
        for constraint in constraints:
            upgraded.append(self.upgrade_constraint(path, constraint))
        # All done
        return upgraded
        
    def upgrade_constraint(self, path, constraint):
        """Upgrade a Version 1.x constraint clause to the corresponding
        Version 2.0 boolean function on the attribute at 'path'.
        """
        from tosca_core.models.constraint import constraint_to_condition
        return constraint_to_condition({ '$get_attribute': path }, constraint)
