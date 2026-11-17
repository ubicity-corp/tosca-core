"""
ToscaNodeTemplateValidator class
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2014-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger = logging.getLogger(__name__)

# Type hint support
from typing import Any, Optional

# Validator support
from . import get_validator
from .managed_template import ToscaManagedTemplateValidator

# For count range checking
from tosca_core.models.function import ToscaFunction

# Cached lookups for TOSCA built-in data types
import tosca_core.models.builtin_types as builtin_types


class ToscaNodeTemplateValidator(ToscaManagedTemplateValidator):
    """The ToscaNodeTemplateValidator class validates node templates
    defined in TOSCA topologies
    """

    def __init__(self) -> None:
        """Constructor
        """
        super(ToscaNodeTemplateValidator, self).__init__()

    def validate_node_template_topology(self, node_template: "Any") -> dict:
        """Check if a node template's topology is valid. This involves
        checking capabilities and requirements.

        Args:
          node_template(ToscaNodeTemplate): node template to validate
        Returns:
          (Possibly empty) dict of validation errors
        Raises:
          None
        """
        validation_errors = dict()

        # Resolve any 'copy:' indirection before any other validation,
        # so subsequent checks see the merged template rather than the
        # bare stub. Mirrors the relationship-template flow in
        # relationship_template.py:176-200.
        errors = self.resolve_copy(node_template)
        if errors:
            self.add_line_number(errors, node_template)
            return errors

        # First, validate the node template type
        error = self.validate_template_type(node_template)
        if error:
            validation_errors['type'] = error
            self.add_line_number(validation_errors, node_template)
            return validation_errors

        # Next check directives, since remaining validation depends on
        # them.
        errors = self.validate_directives(node_template)
        if errors:
            validation_errors['directives'] = errors
            self.add_line_number(validation_errors, node_template)
            return validation_errors

        # Validate selectable node templates first
        if node_template.is_selectable():
            # Selectable nodes don't make sense without at least one
            # incoming relationship
            if not node_template.targeted_by:
                return f"'select' node {node_template.name} does not have incoming relationships"
            # Make sure select-only node templates don't define
            # additional fields.
            if node_template.directives == ['select']:
                errors = self.validate_select_only_node_template(node_template)
                if errors: return errors

        # Validate capabilities next.
        errors = self.validate_node_template_capabilities(node_template)
        if errors:
            logger.error("Service '%s': node '%s' has invalid capabilities", 
                         node_template.service.name, node_template.name)
            validation_errors['capabilities'] = errors

        # Finally, validate requirements
        errors = self.validate_node_template_requirements(node_template)
        if errors:
            logger.error("Service '%s': node '%s' has invalid requirements", 
                         node_template.service.name, node_template.name)
            validation_errors['requirements'] = errors

        # Validate node filter last, since it may depend on validated
        # requirements.
        errors = self.validate_node_filter(node_template)
        if errors:
            logger.error("Service '%s': node '%s' has invalid node_filter", 
                         node_template.service.name, node_template.name)
            validation_errors['node_filter'] = errors

        # All done
        self.add_line_number(validation_errors, node_template)
        return validation_errors


    def resolve_copy(self, node_template: "Any") -> dict:
        """If a node template has a 'copy:' keyname, look up the source
        template in the containing service and refine self in place.
        Anything self already declared overrides what's merged in; the
        rest is inherited. Returns a validation-error dict when the
        copy reference is broken; empty dict (or no-op) otherwise.
        """
        try:
            source_name = node_template.copy
        except AttributeError:
            return {}
        try:
            source = node_template.service.node_templates[source_name]
        except KeyError:
            return {'copy': "node template '{0}' not found".format(source_name)}
        logger.debug("Node '%s': resolving copy of '%s'",
                     node_template.name, source_name)
        del node_template.copy
        node_template.complete_template_refinement(source)
        return {}


    def validate_select_only_node_template(self, node_template: "Any") -> dict:
        """Check if a node template is a valid for "select only" use.

        Args:
          node_template(ToscaNodeTemplate): node template to validate
        Returns:
          (Possibly empty) dict of validation errors
        Raises:
          None
        """
        validation_errors = dict()
        # Default 'count' is 1. 'count' > 1 not allowed in select_only
        # node templates
        if node_template.count > 1:
            validation_errors['count'] = 'not allowed in select-only node templates'
        # attributes not allowed in select_only node templates
        try:
            self.assert_not_present(node_template, 'attributes')
        except Exception as e:
            validation_errors['attributes'] = 'not allowed in select-only node templates'
        # properties not allowed in select_only node templates
        try:
            self.assert_not_present(node_template, 'properties')
        except Exception as e:
            validation_errors['properties'] = 'not allowed in select-only node templates'
        # capabilities not allowed in select_only node templates
        try:
            self.assert_not_present(node_template, 'capabilities')
        except Exception as e:
            validation_errors['capabilities'] = 'not allowed in select-only node templates'
        # requirements not allowed in select_only node templates
        try:
            self.assert_not_present(node_template, 'requirements')
        except Exception as e:
            validation_errors['requirements'] = 'not allowed in select-only node templates'
        # artifacts not allowed in select_only node templates
        try:
            self.assert_not_present(node_template, 'artifacts')
        except Exception as e:
            validation_errors['artifacts'] = 'not allowed in select-only node templates'
        # interfaces not allowed in select_only node templates
        try:
            self.assert_not_present(node_template, 'interfaces')
        except Exception as e:
            validation_errors['interfaces'] = 'not allowed in select-only node templates'

        # All done
        return validation_errors
    

    def validate_node_template_capabilities(self, node_template: "Any") -> dict:
        """Make sure a node template has capability templates for all
        capabilities defined in the node type. This may require
        synthesizing capability templates. Note that the actual
        validation of each capability template will be done in a
        separate step.

        Args:
          node_template(ToscaNodeTemplate): node template for which to
            validate capabilities
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """
        validation_errors = {}

        # Get capability validator
        validator = get_validator('ToscaCapabilityTemplate')

        # Get capability declarations
        capability_declarations = node_template.declaration.get_capability_declarations()

        # Make sure all declared capabilities have a valid
        # corresponding capability template
        capabilities = node_template.capabilities
        for capability_name, capability_declaration in capability_declarations.items():
            logger.debug("'%s' (%s): validating capability '%s'",
                         node_template.declaration.name, node_template.declaration.type,
                         capability_name)
            try:
                # Check if capability template is defined in the node
                # template.
                capability = capabilities[capability_name]
                # Set capability declaration in capability template
                capability.declaration = capability_declaration
            except (AttributeError, KeyError):
                # No capability template defined in the node
                # template. Create a template for this declarated
                # capability. Note that this assumes that the
                # capability declaration does not include any required
                # properties without a default value.
                logger.debug("'%s': synthesizing required capability '%s'",
                             node_template.declaration.name, capability_name)
                capability = capability_declaration.create_template()
                node_template.capabilities[capability_name] = capability
                
        # Make sure we don't have any capabilities defined in the node
        # template that don't have a corresponding declaration.
        for capability_name, capability in capabilities.items():
            # Find capability declaration
            try:
                capability_declaration = capability_declarations[capability_name]
            except KeyError:
                logger.error("Node '%s': '%s' does not declare capability '%s'", 
                             node_template.name, node_template.declaration.type, capability_name)
                validation_errors[capability_name] = 'not previously defined'

        # Everything OK
        return validation_errors


    def validate_node_template_requirements(self, node_template: "Any") -> dict:
        """Make sure a node template has relationship templates for all
        requirements declared in the type. Requirement validation is
        quite involved. It involves the following steps:

        1. Check the integrity of the list of requirement templates in
           this node template. This involves the following:

           a. Make sure every requirement template in a node template
              has a corresponding requirement declaration in the node
              type

           b. Make sure the order of the requirement templates in the
              node template is consistent with the order of the
              requirement declarations in the node type.

        2. For v1.3 requirements that use the 'occurrences' keyword,
           split off an optional requirement if the occurrences range
           includes an optional component.

        3. Add templates for all mandatory requirements that don't
           already have a corresponding requirement template.

        4. Validate each individual requirement template.  Requirement
           templates in node templates can represent two possible
           constructs:

           a. A fully qualified relationship template that specifies a
              target node template within the service template

           b. A dangling requirement that just specifies a target node
              or capability type (and optionally a capability and or
              node filter)

           The requirement validation code must handle both cases.

        5. Make sure the sum of count values for requirement templates
           with the same name is within the count range specified in
           the corresponding requirement definitions.

        6. Make sure a requirement that holds at most one relationship
           names which representation it targets, where the target node
           template may yield several.

        Args:
          node_template(ToscaNodeTemplate): node template for which to
            validate requirements
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None

        """

        # Check the integrity of the list of requirement templates.
        errors = self.validate_requirements_list(node_template)
        if errors: return errors

        # Add templates for implicit mandatory requirements
        self.add_mandatory_requirements(node_template)

        # Resolve indirections and complete each requirement template's
        # refinement of the declaration it refines, before any of them is
        # validated
        errors = self.complete_requirement_templates(node_template)
        if errors: return errors

        # Validate each individual requirement template
        errors = self.validate_requirement_templates(node_template)
        if errors: return errors

        # Add optional requirements for v1.3 requirements that use the
        # 'occurrences' keyword. We do this here to make sure
        # requirements have been fully validated. Note that this may
        # create a new requirement list.
        self.split_off_optional_occurrences(node_template)

        # Validate the count value for each requirement.
        errors = self.validate_requirement_count_values(node_template)
        if errors: return errors

        # Make sure a requirement that holds at most one relationship names
        # which representation of a plural target it means.
        errors = self.validate_requirement_target_qualifiers(node_template)
        if errors: return errors

        # Everything OK
        return {}


    def validate_requirements_list(self, node_template: "Any") -> Optional[dict]:
        """Validate the integrity of the list of requirement templates in the
        specified node template:

        1. Make sure all requirement templates in the node template
           have a corresponding requirement declaration in the
           corresponding node type

        2. Make sure all requirement templates in the node template
           are ordered correctly. Specifically, they must obey the
           order of the corresponding requirement definitions in the
           corresponding node type

        """
        # Get list of requirement declaration names
        requirement_declarations = node_template.declaration.get_requirement_declarations()
        declarations = [ declaration.name for declaration in requirement_declarations ]

        # Get list of requirement template names
        requirements = node_template.requirements
        templates = [ template.name for template in requirements ]

        # Make sure all templates have declarations:
        errors = {}
        for template in templates:
            if not template in declarations:
                logger.error("Node '%s': '%s' does not define requirement '%s'", 
                             node_template.name, node_template.declaration.type, template)
                error = "not defined in '{0}'".format(node_template.declaration.type)
                errors[template] = error
        if errors: return errors

        # Check if the order of the templates matches the order of the
        # declarations
        if declarations:
            d = iter(declarations)
            declaration = next(d)
            try:
                for template in templates:
                    while template != declaration:
                        declaration = next(d)
            except StopIteration:
                # Requirement template out of order
                logger.error("Node '%s': requirement '%s' out of order",
                             node_template.name, template)
                error = "order doesn't match order of requirements defined in '{0}'".format(node_template.declaration.type)
                return { template: error }
        
        # Everything checks out
        return None


    def split_off_optional_occurrences(self, node_template: "Any") -> None:
        """For v1.3 requirements that include an 'occurrences' keyword where
        the upper bound is greater than the lower bound, split that
        requirement into a mandatory and an optional requirement.
        """
        # Create a new empty requirement list (since we can't add
        # elements to a list over which we're iterating)
        expand = False
        expanded = list()
        
        # Copy requirements to the new list and append split-off
        # requirements as necessary
        for requirement in node_template.requirements:
            # Track in the new list
            expanded.append(requirement)
            try:
                occurrences = requirement.occurrences
                if occurrences[0] == 0:
                    # These requirements are all optional
                    requirement.optional = True
                    requirement.count = occurrences[1]
                else:
                    # We have mandatory requirements
                    requirement.optional = False
                    requirement.count = occurrences[0]
                    # Do we need to split off an optional requirement?
                    if occurrences[1] > occurrences[0]:
                        try:
                            # Copy the requirement into a new template
                            optional = requirement.declaration.create_template()
                            optional.complete_template_refinement(requirement)
                            optional.optional = True
                            optional.count = occurrences[1] - occurrences[0]
                            expanded.append(optional)
                            expand = True
                        except Exception as e:
                            logger.error("%s: unable to split requirement %s: %e",
                                         node_template.name, requirement.name, str(e))
            except AttributeError:
                # No occurrences. Nothing to split off.
                pass

        # Do we need to use the new list?
        if expand:
            node_template.relationships = expanded
        

    def add_mandatory_requirements(self, node_template: "Any") -> None:
        """Insert templates for any missing mandatory requirements into the
        requirements list of the specified node template. Note that at
        this point the requirement template list is guaranteed to be
        in the correct order.

        We do this before validing each requirement template
        individually, since the 'inserted' requirement templates for
        the mandatory requirements may have properties or interface
        operation inputs that need to be validated as well.
        """

        # Get list of requirement declaration names
        requirement_declarations = node_template.declaration.get_requirement_declarations()

        # Get list of requirement template names
        requirements = node_template.requirements
        templates = [ template.name for template in requirements ]

        # Make sure all mandatory requirements are present
        insert_after = None
        for requirement_declaration in requirement_declarations:
            if requirement_declaration.name in templates:
                # There is a template for this requirement. Insert any
                # further mandatory requirements after this
                # requirement
                insert_after = requirement_declaration.name
            else:
                if requirement_declaration.is_required():
                    # This mandatory requirement does not exist. Synthesize one.
                    logger.debug("Node '%s': synthesizing requirement '%s' of type '%s' after %s",
                                 node_template.name, requirement_declaration.name,
                                 requirement_declaration.type, insert_after)
                    requirement = requirement_declaration.create_template()
                    # insert in the appropriate slot
                    node_template.insert_requirement(insert_after, requirement)
                    insert_after = requirement_declaration.name

        # Everything checks out
        return None


    def complete_requirement_templates(self, node_template: "Any") -> dict:
        """Resolve each requirement template's indirections and complete its
        refinement of the declaration it refines, before any requirement
        of this node template is validated.

        A requirement template states only what it changes, and is
        completed by merging in the declaration it refines. Doing that for
        every requirement first means a requirement validated afterwards
        reads a declaration that is whole, whichever requirement it
        belongs to. Indirections are resolved here because a reference is
        not a template to merge into until they are.

        Args:
          node_template(ToscaNodeTemplate): node template whose
            requirement templates to complete

        Returns:
          (possibly empty) dict of validation errors, keyed the way
          'validate_requirement_templates' keys them
        """

        validator = get_validator('ToscaRelationshipTemplate')
        validation_errors = {}
        for requirement in node_template.requirements:
            try:
                logger.debug("Node '%s': completing requirement '%s'",
                             node_template.name, requirement.name)
                errors = validator.resolve_indirections(requirement)
                if errors:
                    logger.error("Node '%s': requirement ''%s'' has invalid indirections",
                                 requirement.name, requirement.name)
                    validation_errors[requirement.name] = errors
                    continue
                requirement_declaration = node_template.declaration.get_requirement_declaration(
                    requirement.name)
                errors = validator.complete_relationship_template(requirement_declaration,
                                                                  requirement)
                if errors:
                    logger.error("Node '%s': invalid requirement '%s'",
                                 node_template.name, requirement.name)
                    validation_errors[requirement.name] = errors
            except Exception as error:
                logger.error("Node '%s': error while completing requirements: %s",
                             node_template.name, error)
                validation_errors[requirement.name] = "validator error ({0})".format(error)

        # All done
        return validation_errors


    def validate_requirement_templates(self, node_template: "Any") -> dict:
        """Validate all requirement templates in a list

        We have previously made sure that all requirements have a
        corresponding declaration, resolved their indirections, and
        completed each one's refinement of the declaration it refines.
        """

        # Get requirement validator
        validator = get_validator('ToscaRelationshipTemplate')
        validation_errors = {}
        requirements = node_template.requirements
        for requirement in requirements:

            # Get the the requirement declaration
            requirement_declaration = node_template.declaration.get_requirement_declaration(requirement.name)

            try:
                # Validate against declaration
                logger.debug("Node '%s': validating requirement '%s'",
                             node_template.name, requirement.name)
                errors = validator.validate_relationship_template(requirement_declaration,
                                                                  requirement)
                if errors:
                    logger.error("Node '%s': invalid requirement '%s'",
                                 node_template.name, requirement.name)
                    validation_errors[requirement.name] = errors
            except Exception as error:
                logger.error("Node '%s': error while validating requirements: %s",
                             node_template.name, error)
                validation_errors[requirement.name] = "validator error ({0})".format(error)

        # All done
        return validation_errors


    def validate_requirement_count_values(self, node_template: "Any") -> dict:
        """Make sure the sum of all count values for each requirement is
        within the count range specified in the corresponding
        requirement definition.

        Note that we do this after individual requirement templates
        have been validated to make sure the value of the
        'count' keyword is valid for each requirement template.
        """
        errors = {}

        # First, count the number of mandatory and optional templates
        # for each requirement whose declaration restricts the count
        # range.
        requirements = node_template.requirements
        mandatory = dict()
        optional = dict()
        # Keep track of relationships that use function count values,
        # since those cannot be validated at design time.
        uses_function = set()
        for requirement in requirements:
            count_range = requirement.declaration.count_range
            if count_range[0] == 0 and count_range[1] == 'UNBOUNDED':
                # Count not restricted.
                continue
            count = requirement.count
            try:
                function = ToscaFunction(count, node_template)
                uses_function.add(requirement.name)
            except (TypeError, AttributeError):
                # Not a function. Add to totals so far.
                if requirement.optional:
                    try:
                        optional[requirement.name] = optional[requirement.name] + count
                    except KeyError:
                        mandatory[requirement.name] = 0
                        optional[requirement.name] = count
                else:
                    try:
                        mandatory[requirement.name] = mandatory[requirement.name] + count
                    except KeyError:
                        mandatory[requirement.name] = count
                        optional[requirement.name] = 0

        # Make sure the number of requirement templates is within the
        # range defined by the corresponding requirement definition.
        for name, mandatory_count in mandatory.items():
            if name in uses_function:
                continue
            optional_count = optional[name]
            requirement_declaration = node_template.declaration.get_requirement_declaration(name)
            count_range = requirement_declaration.count_range
            if mandatory_count < count_range[0]:
                error = "node type {0} requires a minimum of {1} but only {2} specified".format(
                    node_template.declaration.type, str(count_range[1]), str(mandatory_count))
                logger.error(error)
                errors[name] = error
            if count_range[1] != 'UNBOUNDED' and (mandatory_count + optional_count) > count_range[1]:
                error = "node type {0} allows a maximum of {1} but {2} requested".format(
                    node_template.declaration.type, str(count_range[1]), str((mandatory_count + optional_count)))
                logger.error(error)
                errors[name] = error

        # All done
        return errors


    def validate_requirement_target_qualifiers(self, node_template: "Any") -> dict:
        """Make sure a requirement that holds at most one relationship says
        WHICH representation of its target it means.

        A requirement whose declared 'count_range' has an upper bound of 1
        holds exactly one relationship. Assigned to a node template that may
        yield several representations, it says "exactly one" while pointing at
        something that may be many, and never says which. Naming one resolves
        it -- '[server, 0]' -- and stays legal; only the unqualified form is
        refused.

        The requirement-side half of a rule TOSCA paths already enforce: a
        qualifier is required where there are several representations and
        forbidden where there is exactly one.

        Both facts are static, so no count is evaluated. The upper bound comes
        from the declaration; whether the target may yield several comes from
        its own 'count' keyname. An expression count means "may yield several"
        however it evaluates, which is what 'supports_multiple' means
        everywhere else -- such a template registers its representations as
        'name:0', 'name:1', ... whatever number it produces, so an unqualified
        target could not be resolved even when the expression yields one.

        Args:
          node_template(ToscaNodeTemplate): node template whose requirements
            to check
        Returns:
          (possibly empty) dict of validation errors, keyed by requirement name
        Raises:
          None
        """
        errors = {}
        for requirement in node_template.requirements:
            if requirement.declaration.count_range[1] != 1:
                # Holds more than one relationship, so several targets are
                # what it asked for.
                continue
            try:
                target_node = requirement.target_node
            except AttributeError:
                # Names no target node template. A dangling requirement is
                # fulfilled from inventory, where there is no template here to
                # ask about.
                continue
            try:
                # Reading 'target_node' above is what parses a path-form
                # assignment and records its index, so this must come after it.
                requirement.target_node_index
                # Qualified: the author named the representation.
                continue
            except AttributeError:
                pass
            if target_node.supports_multiple():
                error = ("requirement '{0}' holds at most one relationship but targets "
                         "node template '{1}', which may yield several representations. "
                         "Name the one it targets, as '[{1}, 0]'".format(
                             requirement.name, target_node.name))
                logger.error(error)
                errors[requirement.name] = error

        # All done
        return errors


    def validate_count_not_zero(self, node_template: "Any") -> Optional[str]:
        """Refuse a 'count' that is fixed at zero.

        A node template counted at a literal zero yields nothing under every
        input, which makes it dead content carrying a type reference rather
        than a template. The way to not have a node is to not write one, so
        this is refused instead of instantiated into nothing. Disabling a
        template by setting its count to zero is deliberately not supported,
        whatever that means in other languages: a service template is a design
        artifact, not a configuration file with entries switched off in place.

        Only a LITERAL zero. A count written as an expression is a
        per-deployment value, and one that evaluates to zero is legal and
        useful -- the template contributes no representations, a path to it is
        the empty list, and ``$length`` over it is 0, which is how a
        realization covers the empty case. The validator does not, and may
        not, try to predict such a value.

        Stricter than TOSCA 2.0 as written, whose node template 'count'
        keyname is a non-negative integer (§7.3.1).

        Args:
          node_template(ToscaNodeTemplate): node template whose count to check
        Returns:
          An error string, or None when the count is acceptable
        Raises:
          None
        """
        count = node_template.count
        # A bool is an int in Python, and 'count: false' is a malformed count
        # rather than a zero -- validate_count_value owns that diagnostic.
        if isinstance(count, bool) or not isinstance(count, int):
            return None
        if count != 0:
            return None
        return ("'count' is fixed at 0, so this node template can never yield a "
                "node. Remove the template instead, or use an expression if the "
                "number is meant to depend on the deployment.")


    def validate_template(self, node_template: "Any") -> dict:
        """Check if a node template is valid.

        Args:
          node_template(ToscaNodeTemplate): node template to validate
        Returns:
          (Possibly empty) dict of validation errors
        Raises:
          None
        """
        # The order of these validations matter:
        #
        # 1. Validate artifacts before requirements, since interface
        #    templates in requirements may refer to those artifacts.
        # 2. Validate interfaces last, since interface templates may
        #    depend on all the other entities. Interface validation is
        #    provided by the ToscaManagedTemplate class, but is called
        #    here to ensure proper sequencing of the validations.

        # Nothing to validate for select-only templates
        if node_template.directives == ['select']: return {}
        
        # Is this a valid managed template?
        validation_errors = super(ToscaNodeTemplateValidator,
                                  self).validate_template(node_template)

        # Check the 'count' value
        errors = self.validate_count_value(node_template)
        if not errors:
            # Only worth asking of a count that validated. A count that
            # did not is already reported, and reporting it twice under
            # the same key would replace the real diagnostic.
            errors = self.validate_count_not_zero(node_template)
        if errors:
            logger.error("Service '%s': node '%s' has an invalid count value",
                         node_template.service.name, node_template.name)
            validation_errors['count'] = errors

        # Check capabilities
        errors = self.validate_capabilities(node_template)
        if errors:
            logger.error("Service '%s': node '%s' has invalid capabilities", 
                         node_template.service.name, node_template.name)
            validation_errors['capabilities'] = errors

        # Check artifacts before requirements, since requirements may
        # include interface templates that refer to these artifacts.
        errors = self.validate_artifacts(node_template)
        if errors:
            logger.error("Service '%s': node '%s' has invalid artifacts", 
                         node_template.service.name, node_template.name)
            validation_errors['artifacts'] = errors

        # Check requirements
        errors = self.validate_requirements(node_template)
        if errors:
            logger.error("Service '%s': node '%s' has invalid requirements",
                         node_template.service.name, node_template.name)
            validation_errors['requirements'] = errors
        elif node_template.is_abstract():
            self.warn_operations_on_substituted_requirements(node_template)

        # Check interfaces. Note that the 'validate_interfaces' method
        # is defined in the ToscaManagedTemplateValidator class, but
        # it is called here to ensure proper sequencing of the
        # validation steps.
        errors = self.validate_interfaces(node_template)
        if errors:
            logger.error("Service '%s': node template '%s' has invalid interfaces", 
                         node_template.service.name, node_template.name)
            validation_errors['interfaces'] = errors

        # Everything valid
        return validation_errors


    def validate_directives(self, node_template: "Any") -> dict:
        """Check if the directives of a node template are valid for
        the specified declaration.

        Args:
          node_template(ToscaTemplate): node template for which to
            validate directives
        Returns:
          (Possibly empty) dict of validation errors
        Raises:
          None
        """
        # Make sure we only have valid directives
        validation_errors = {}
        directives = node_template.directives
        for directive in directives:
            if not directive in node_template.valid_directives:
                logger.error("Node template '%s': invalid directive '%s'",
                             node_template.declaration.name, directive)
                validation_errors[directive] = 'not a valid directive'

        # Make sure each directive is only set once
        for directive in node_template.valid_directives:
            if directives.count(directive) > 1:
                logger.error("Node template '%s': multiple '%s' directives ",
                             node_template.declaration.name, directive)
                validation_errors[directive] = 'defined multiple times'

        # All done
        return validation_errors


    def validate_capabilities(self, node_template: "Any") -> dict:
        """Make sure a node template has valid capability templates for all
        capabilities defined in the node type. This may require
        synthesizing capability templates.

        Args:
          node_template(ToscaNodeTemplate): node template for which to
            validate capabilities
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """
        validation_errors = {}

        # Get capability validator
        validator = get_validator('ToscaCapabilityTemplate')

        # Validate all capability templates. Note that we do this for
        # synthesized capability templates as well to make sure
        # we're not missing any required properties.
        capabilities = node_template.capabilities
        for capability_name, capability in capabilities.items():
            logger.debug("'%s' (%s): validating capability '%s'",
                         node_template.declaration.name, node_template.declaration.type,
                         capability_name)
            try:
                errors = validator.validate_template(capability)
                if errors:
                    logger.error("Node '%s': invalid capability '%s'", 
                                 node_template.name, capability_name)
                    validation_errors[capability_name] = errors
            except Exception as e:
                logger.error("'%s': error while validating capability '%s': %s",
                             node_template.declaration.name, capability_name, e)
                validation_errors[capability_name] = 'validator error <{0}>'.format(str(e))

        # Everything OK
        return validation_errors


    def validate_requirements(self, node_template: "Any") -> dict:
        """Validate all requirement templates in a list

        We have previously resolved all indirections and have made
        sure that all requirements have a corresponding declaration.
        """

        # Get requirement validator
        validator = get_validator('ToscaRelationshipTemplate')
        validation_errors = {}
        requirements = node_template.requirements
        for requirement in requirements:
            try:
                # Validate against declaration
                logger.debug("Node '%s': validating requirement '%s'",
                             node_template.name, requirement.name)
                errors = validator.validate_template(requirement)
                if errors:
                    logger.error("Node '%s': invalid requirement '%s'", 
                                 node_template.name, requirement.name)
                    validation_errors[requirement.name] = errors
            except Exception as error:
                logger.error("Node '%s': error while validating requirements: %s", 
                             node_template.name, error)
                validation_errors[requirement.name] = "validator error ({0})".format(error)

        # All done
        return validation_errors


    def warn_operations_on_substituted_requirements(self, node_template: "Any") -> None:
        """Warn about each requirement of a substituted node whose
        relationship implements an operation, from its type or from the
        template's own interface assignments.

        An outer relationship to a substituted source records its target's
        state, and the relationships mapped into the substituting service do
        the work. An operation on it has no resource of the source's to act
        on: the substituted node holds none.

        Args:
          node_template(ToscaNodeTemplate): a node template with the
            'substitute' directive, whose requirements have validated
        """
        for requirement in node_template.requirements:
            operations = list()
            for interface_name, interface in (requirement.interfaces or {}).items():
                try:
                    names = set(interface.declaration.get_operation_declarations())
                except AttributeError:
                    names = set()
                names.update(getattr(interface, 'operations', None) or {})
                operations.extend(f"{interface_name}.{name}" for name in sorted(names)
                                  if interface.get_operation_implementation(name))
            if operations:
                logger.warning("Node '%s' is substituted; its requirement '%s' has a relationship "
                               "that implements %s, which has no resource of the source's to act on",
                               node_template.name, requirement.name,
                               ", ".join(f"'{operation}'" for operation in operations))


    def validate_node_filter(self, node_template: "Any") -> dict:
        """Check if a node_template includes a valid target node filter.

        Args: 
          node_template(ToscaNodeTemplate): Tosca node that includes
            the node filter to validate
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """

        # Do we have a node filter?
        try:
            node_filter = node_template.node_filter
            if not node_template.is_selectable():
                return 'node filter not allowed here: node is not selectable'
        except AttributeError:
            # No node filter to valiate
            return {}

        # Validate and upgrade Version 1.x node filter if necessary.
        if (node_template.tosca_version and
                node_template.tosca_version.startswith("tosca_simple_yaml")):
            validator = get_validator('ToscaFilter')
            errors =  validator.validate_and_upgrade_filter(node_template, node_template.declaration.type_entity, node_filter)
            if errors:
                return errors

        # Validate the Version 2.x node filter
        errors =  self.validate_target_query_filter(node_template)
        if errors:
            return errors

        # We have a valid node_filter. Next, we change the scope of
        # the node filter function to the scope of the relationships
        # that target this selectable node. This is necessary because
        # when we evaluate the node filter we must do so withing the
        # scope of the service that defines the node filter. We can't
        # obtain that scope from the selected node, since that node
        # was created in the context of some other service. However,
        # we can obtain the correct service scope from the
        # relationship that targets the selected node.  As an added
        # benefit, this will also allow us to use the same code to
        # find selectable nodes as well as fulfill regular dangling
        # requirements.
        rescoped_filter = None
        for relationship_template in node_template.targeted_by:
            if not rescoped_filter:
                rescoped_filter = self.rescope_filter(relationship_template, node_template.node_filter)
            relationship_template.resolved_filter = rescoped_filter
        return {}

    
    def rescope_filter(self, relationship_template: "Any", filter: "Any") -> "Any":
        """Rewrite a node filter function in a selectable node to an
        equivalent function in the scope of relationships that target
        that selectable node. We do this by updating TOSCA Paths in
        'get_attribute' and 'get_property' functions as
        necessary. This function is only called after the node filter
        in the selectable node has been validated.
        """
        try:
            # Do we have a function?
            [(function, args)] = list(filter.items())
        except (AttributeError, ValueError):
            # Not a function. Nothing to do
            return filter

        # Do we have a'get_property' or 'get_attribute' function?
        if function in ['$get_property', '$get_attribute']:
            if args[0] == 'SELF':
                # Rewrite TOSCA Path in the scope of a relationship.
                rescoped_args = ['SELF', 'TARGET']
                rescoped_args.extend(args[1:])
                return { function: rescoped_args }
            else:
                # TOSCA Path references starting node by name. Nothing
                # to do.
                return filter

        # Not a 'get_attribute' or 'get_property' function. Rescope
        # function arguments if necessary.
        if not isinstance(args, list):
            # Short notation used by 'get_input'. Nothing to do.
            return filter

        # Rescope any function arguments by calling this method
        # recursively.
        rescoped_args = list()
        for arg in args:
            rescoped_args.append(self.rescope_filter(relationship_template, arg))
        rescoped_filter = { function: rescoped_args }
        
        # Resolve the rescoped filter function to internal function
        # syntax.
        declaration = builtin_types.get('boolean').create_declaration('node_filter')
        resolved_filter = declaration.resolve_function_value(relationship_template, rescoped_filter)
        return resolved_filter


    def validate_artifacts(self, node_template: "Any") -> dict:
        """Check if a node template has valid artifacts

        Args: 
          node_template(ToscaNodeTemplate): Tosca node that includes
            the artifacts to validate
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """
        validation_errors = {}

        # Iterate over artifacts stored in node 
        validator = get_validator('ToscaArtifact')
        artifacts = node_template.artifacts
        for artifact_name, artifact in artifacts.items():

            logger.debug("node '%s': validating artifact '%s'", 
                         node_template.name, artifact.name)

            # Validate
            errors = validator.validate_typed_template(artifact)
            if errors:
                logger.error("Node '%s': invalid artifact '%s'", 
                             node_template.name, artifact.name)
                validation_errors[artifact_name] = errors

        # Artifacts valid
        return validation_errors
