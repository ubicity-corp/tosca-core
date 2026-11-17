"""
ToscaRelationshipTemplateValidator class
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2014-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger = logging.getLogger(__name__)

# Type hint support
from typing import Any, Optional

# Validator
from . import get_validator
from .managed_template import ToscaManagedTemplateValidator

# Exception support
import tosca_core.models.exceptions as te

# Types on which this validator depends
from tosca_core.models.relationship_template import ToscaRelationshipTemplate
from tosca_core.builtin.range import ToscaRange

# Cached lookups for TOSCA built-in data types
import tosca_core.models.builtin_types as builtin_types


class ToscaRelationshipTemplateValidator(ToscaManagedTemplateValidator):
    """The ToscaRelationshipTemplateValidator class validates relationship
    templates defined in Tosca service templates. Note that in this
    file, we use the terms 'requirement' and 'relationship template'
    interchangeably. We also use the terms 'relationship declaration'
    and 'requirement declaration' interchangeably.
    """

    def __init__(self) -> None:
        """Constructor
        """
        super(ToscaRelationshipTemplateValidator, self).__init__()


    def complete_relationship_template(self, requirement_declaration: "Any", requirement: "ToscaRelationshipTemplate") -> dict:
        """Check a requirement template's refinement of the declaration it
        refines, and complete it by merging that declaration in, before
        any of the node template's requirements is validated.

        A relationship template may refine the relationship type the
        declaration names, so the type it states is checked for
        compatibility first. A template that states no type of its own
        takes the declaration as it stands.

        Args:
          requirement_declaration(ToscaRelationshipDeclaration):
            requirement declaration the requirement refines
          requirement(ToscaRelationshipTemplate): requirement whose
            refinement to complete

        Returns:
          (possibly empty) dict of validation errors
        """
        errors = self.validate_template_type_refinement(requirement_declaration, requirement)
        if errors:
            logger.error("Requirement '%s' specifies invalid relationship type",
                         requirement.name)
            return {'type': errors}

        # Everything OK
        return {}


    def validate_relationship_template(self, requirement_declaration: "Any", requirement: "ToscaRelationshipTemplate") -> dict:
        """Check if a template is valid for the specified declaration. The
        template's refinement of that declaration was checked and
        completed by 'complete_relationship_template', before any of the
        node template's requirements was validated.

        Args:
          requirement_declaration(ToscaRelationshipDeclaration):
            requirement declaration against which to validate the
            requirement
          requirement(ToscaRelationshipTemplate): requirement to
            validate
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None

        """
        validation_errors = {}

        # Is the specified relationship target valid?
        errors = self.validate_target(requirement)
        if errors:
            validation_errors.update(errors)

        # All done
        return validation_errors


    def validate_template(self, requirement: "ToscaRelationshipTemplate") -> dict:
        """Check if a requirement in a node template is valid for the
        relationship declaration in the associated node type

        Args:
          requirement(ToscaRelationshipTemplate): Tosca requirement to
            validate
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """
        validation_errors = dict()

        # Is this a valid managed instance_entity
        validation_errors = super(ToscaRelationshipTemplateValidator,
                                  self).validate_template(requirement)

        # Are the requirement directives (if any) valid?
        errors = self.validate_directives(requirement)
        if errors:
            validation_errors['directives'] = errors

        # Check interfaces. Note that the 'validate_interfaces' method
        # is defined in the ToscaManagedTemplateValidator class, but
        # it is called here to ensure proper sequencing of the
        # validation steps.
        errors = self.validate_interfaces(requirement)
        if errors:
            logger.error("Service '%s': requirement '%s' has invalid interfaces",
                         requirement.service.name, requirement.declaration.name)
            validation_errors['interfaces'] = errors

        # Validate node filter if it is present. Note that we may have
        # to upgrade the node filter first. At this point, we have
        # already verified that node filters are only present where
        # they are allowed.
        errors = self.upgrade_target_node_query_node_filter(requirement)
        if errors:
            validation_errors['node_filter'] = errors
        else:
            errors = self.validate_target_query_filter(requirement)
            if errors:
                validation_errors['node_filter'] = errors
        
        # All done
        return validation_errors


    def validate_directives(self, requirement: "ToscaRelationshipTemplate") -> dict:
        """Validate requirement directives: only 'internal' / 'external'
        are permitted, and each may appear at most once. Mirrors the
        capability-template validator for the counterpart keyname.
        """
        validation_errors = {}
        directives = requirement.directives
        for directive in directives:
            if directive not in requirement.valid_directives:
                logger.error("Requirement '%s': invalid directive '%s'",
                             requirement.name, directive)
                validation_errors[directive] = 'not a valid directive'
        for directive in requirement.valid_directives:
            if directives.count(directive) > 1:
                logger.error("Requirement '%s': multiple '%s' directives",
                             requirement.name, directive)
                validation_errors[directive] = 'defined multiple times'
        return validation_errors


    def resolve_indirections(self, relationship_template: "ToscaRelationshipTemplate") -> dict:
        """Resolve references and copy statements in a relationship template
        to turn this into a fully-resolved relationship template

        Args: 
          relationship_template(ToscaRelationshipTemplate): Tosca
            relationship template that containes indirections that
            need to be resolved.

        Returns:
          (possibly empty) dict of validation errors

        Raises:
          None
        """

        logger.debug("Requirement '%s': resolving indirections",
                     relationship_template.name)

        # is this relationship template a reference to some other
        # relationship template defined elsewhere in the service
        # template? If so, the name of the referenced relationship
        # template is stored in the _type attribute
        try:
            relationship_name = relationship_template._type
            referenced_template = relationship_template.service.relationship_templates[relationship_name]
            logger.debug("Requirement '%s': resolving referenced template '%s'",
                         relationship_template.name, relationship_name)
            # This relationship template is a reference to a
            # relationship template defined elsewhere in the
            # service. Make sure it's a valid reference
            errors = self.validate_reference(relationship_template)
            if errors: return errors

            # Everything checks out. Augment the relationship template
            # with the referenced relationship template. Note that
            # this will also set an updated relationshp
            # declaration. Make sure to remove the referenced
            # relationship template name first to make sure the
            # declaration will be merged in.
            del relationship_template._type 
            relationship_template.complete_template_refinement(referenced_template)

        except (AttributeError, KeyError):
            # Not a reference to a relationship template defined in
            # the service. Must be a relationship template that is
            # defined in-line. Nothing further to do here
            pass

        except Exception as e:
            return "validator error ({0})".format(e)

        # A relationship template can also be declared as a copy of
        # another relationship template in the service. If so, copy
        # and validate
        try:
            relationship_name = relationship_template.copy
            # This relationship template starts as a copy of a
            # relationship template defined elsewhere in the
            # service. Make sure it's a valid copy statement
            logger.debug("Requirement '%s': resolving template to copy '%s'",
                        relationship_template.name, relationship_name)

            errors = self.validate_copy(relationship_template)
            if errors:
                logger.error("%s: invalid copy", relationship_template.name)
                return errors

            # Everything checks out. Replace the relationship template
            # with its augmented copy
            referenced_template = relationship_template.service.relationship_templates[relationship_name]
            del relationship_template.copy
            relationship_template.complete_template_refinement(referenced_template)

        except AttributeError:
            # Not a copy. Just proceed
            pass

        except KeyError:
            # Relationship template to copy not found
            errors = { 'copy': 'Relationship template <{0}> not found'.format(relationship_name) }
            return errors

        except Exception as e:
            return "validator error ({0})".format(e)

        # All done
        return {}


    def validate_reference(self, relationship_template: "ToscaRelationshipTemplate") -> dict:
        """Check if a relationship template is a valid reference to another
        template in its service

        Args:
          relationship_template(ToscaRelationshipTemplate):
            relationship template for which to validate the reference

        Returns:
          validation_errors(dict): possibly empty dict of validation
            errors

        Raises:
          None
        """

        validation_errors = {}

        # A relationship_template reference must not include a 'copy'
        # statement and must not define properties or interfaces
        try:
            self.assert_not_present(relationship_template, 'properties')
        except Exception as e:
            validation_errors['properties'] = 'not allowed'
        try:
            self.assert_not_present(relationship_template, 'interfaces')
        except Exception as e:
            validation_errors['interfaces'] = 'not allowed'
        try:
            self.assert_not_present(relationship_template, 'copy')
        except Exception as e:
            validation_errors['copy'] = 'not allowed'

        return validation_errors


    def validate_copy(self, relationship_template: "ToscaRelationshipTemplate") -> dict:
        """Check if a relationship template has a valid copy definition in its
        service

        Args:
          relationship_template(ToscaRelationshipTemplate):
            relationship template for which to validate copy

        Returns:
          validation_errors(dict): possibly empty dict of validation
            errors

        Raises:
          None
        """

        validation_errors = {}
        try:
            self.assert_not_present(relationship_template, '_type')
        except Exception as e:
            validation_errors['type'] = 'not allowed'
        return validation_errors


    ################################################################################
    # Target Validation. 
    ################################################################################

    def validate_target(self, requirement: "ToscaRelationshipTemplate") -> dict:
        """Check if a requirement includes a target that is valid for the
        corresponding requirement declaration. This method is called
        during initial validation of the service topology.

        A target in a requirement could either be a:

        1. A reference to another node. 
        2. Or it could be a 'target query' that includes node type
           and/or capability type as well as any filters to apply to
           the target query.

        Args: 
          requirement(ToscaRelationshipTemplate): Tosca requirement that
            includes the target to validate
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """

        try:
            # Check if the requirement specifies a target node
            # template. This will raise an AttributeError if no target
            # node template is specified.
            node = requirement.target_node
            try:
                # We have a target node template. Validate it.
                errors = self.validate_target_node(requirement)
                if errors:
                    logger.error("Requirement '%s': invalid target node '%s'",
                                 requirement.name, node.name)
                    return errors
            except Exception as e:
                logger.error("Requirement '%s': error validating target node: %s",
                             requirement.name, e)
                return { 'node' : "validator error ({0})".format(e) }

        except (AttributeError, KeyError):
            # The requirement does not specify a target
            # node template defined in the service. Must be a target
            # query instead.
            try:
                errors = self.validate_target_query(requirement)
                if errors:
                    logger.error("Requirement '%s': invalid target query",
                                 requirement.name)
                    return errors
            except Exception as e:
                logger.error("Requirement '%s': error validating target query: %s",
                             requirement.name, e)
                return { 'node' : "validator error ({0})".format(e) }

        # Everything OK
        return {}


    ################################################################################
    # Target Node Validation
    ################################################################################

    def validate_target_node(self, requirement: "ToscaRelationshipTemplate") -> dict:
        """Check if a target node specified in a requirement is a valid target
        node specification for the corresponding requirement
        declaration.

        Args: 
          requirement(ToscaRelationshipTemplate): Tosca requirement that
            includes the target node to validate
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """

        logger.debug("Requirement %s: validating target node '%s'",
                     requirement.name, requirement.target_node.name)
        validation_errors = {}

        # Do we have a valid target node index
        errors = self.validate_target_node_index(requirement)
        if errors:
            validation_errors['index'] = errors
        
        # Make sure we don't specify a count value.
        errors = self.validate_target_node_count(requirement)
        if errors:
            validation_errors['count'] = errors

        # Make sure we don't specify a node filter
        errors = self.validate_target_node_node_filter(requirement)
        if errors:
            validation_errors['node_filter'] = errors

        # Is the type of the target node template valid?
        errors = self.validate_target_node_type(requirement)
        if errors:
            logger.error("Requirement '%s' of type '%s': invalid target node type",
                         requirement.name, requirement.declaration.type)
            validation_errors['node'] = errors
            return validation_errors
        
        # Is the capability valid for the specified node template?
        # We can only check this if the specified target node has
        # a valid type
        errors = self.validate_target_node_capability(requirement)
        if errors:
            logger.error("Requirement '%s': invalid target node capability",
                         requirement.name)
            validation_errors['capability'] = errors
            return validation_errors

        # Do the target capability's directives permit this fixed
        # requirement? Fixed requirements always target a node in the
        # same service template, so the relationship is internal.
        errors = self.validate_target_node_capability_directives(requirement)
        if errors:
            logger.error("Requirement '%s': target capability directives forbid this requirement",
                         requirement.name)
            validation_errors['directives'] = errors
            return validation_errors

        # Do we specify valid allocations?
        errors = self.validate_target_node_allocation(requirement)
        if errors:
            logger.error("Requirement '%s': invalid target node allocation",
                         requirement.name)
            validation_errors['allocation'] = errors
        
        # All done
        return validation_errors


    def validate_target_node_type(self, requirement: "ToscaRelationshipTemplate") -> dict:
        """Check if a target node specified in a requirement has a valid type
        for the corresponding requirement declaration.

        Args: 
          requirement(ToscaRelationshipTemplate): Tosca requirement
            that includes the target node for which to validate the
            type.
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """

        logger.debug("Requirement %s: check if target node has correct type",
                     requirement.name)

        # Get the node type from the requirement declaration
        try:
            node_type = requirement.declaration.node
        except AttributeError:
            # No node type specified in the relationship
            # declaration. Make sure the type of this node is valid
            # for the relationship type.
            validation_errors = {}
            relationship_type = requirement.declaration.type_entity
            target_node_type = requirement.target_node.declaration.type_entity
            if not relationship_type.is_valid_target_node_type(target_node_type):
                logger.error("Requirement '%s': target_node type '%s' is not a valid target for '%s'",
                             requirement.declaration.name, 
                             target_node_type.name, requirement.declaration.type)
                error = 'invalid target node type for relationship type ({0})'.format(relationship_type.name)
                validation_errors[requirement.target_node.name] = error
            return validation_errors
        except te.TypeNotFound:
            # The type specified in the relationship declaration does
            # not exist.
            logger.error("Requirement %s: target node type not found",
                        requirement.name)
            return 'target node type not found'
        except Exception as e:
            logger.error("Requirement %s: error finding target node type: %s",
                         requirement.name, str(e))
            error = 'validator error ({0})'.format(str(e))
            return error

        # The node template must have the type specified in the
        # requirement declaration
        if not requirement.target_node.has_type(requirement.declaration.target_node_type):
            logger.error("Requirement '%s': node template %s is not of type %s",
                         requirement.name, requirement.target_node.name, 
                         requirement.declaration.node)
            error = "<{0}> is not of type <{1}>".format(
                requirement.target_node.name,
                requirement.declaration.node)
            return error

        # Everything OK
        return {}


    def validate_target_node_capability(self, requirement: "ToscaRelationshipTemplate") -> dict:
        """Check if a requirement that contains a target node has a valid
        target capability

        Args: 
          requirement(ToscaRelationshipTemplate): Tosca requirement that
            includes the target node for which to validate the capability.
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """

        logger.debug("Requirement %s: check target node capability",
                     requirement.name)

        # This method is only called if the specified target node has
        # a valid type, so we should be able to create a declaration
        # for this target node.
        try:
            node_declaration = requirement.target_node.declaration
        except Exception as e:
            # This should never happen.
            error = 'validator error ({0})'.format(str(e))
            return error

        # We need source node type to make sure the node type
        # containing the requirement is a valid source for the
        # capability
        try:
            source_node_type = requirement.source_node.declaration.type_entity
        except Exception as e:
            error = "Error getting source node type for '{0}': {1}".format(
                requirement.declaration.name, str(e))
            return error
            
        # Get the named capability specified in the relationship
        try:
            capability = requirement.capability
            # Does the target node have this capability?
            capability_declaration = node_declaration.get_capability_declaration(capability)

            # Make sure the target capability has the right type
            if not capability_declaration.has_type(requirement.declaration.target_capability_type):
                error = "<{0}> does not have type {1}".format(capability, 
                                                              requirement.declaration.capability)
                return error

            # Make sure the node type containing the requirement is a
            # valid source for the capability.
            if not capability_declaration.is_valid_source_node_type(source_node_type):
                error = "'{0}' is invalid source type for target capability '{1}'".format(
                    source_node_type.name, capability)
                return error
                                                      
            # Make sure the relationship type for this requirement is
            # valid for the capability.
            if not capability_declaration.is_valid_relationship_type(requirement.declaration.type_entity):
                error = "'{0}' is invalid incoming relationship type for target capability '{1}'".format(
                    requirement.declaration.type_entity.name, capability)
                return error
                                                      
        except KeyError:
            # This exception is raised by get_capability_declaration
            # if there is no capability by that name in the
            # node_declaration.
            logger.error("Requirement '%s': unknown capability '%s' for node template '%s'",
                         requirement.name, capability, requirement.target_node.name)
            error = "unknown capability {0}".format(capability)
            return error

        except AttributeError:
            # The requirement declaration doesn't specify a
            # capability.  Make sure that the referenced node template
            # has a capability of the required type.
            capability_type = requirement.declaration.target_capability_type
            target_capabilities = node_declaration.get_capability_declarations_of_type(capability_type)
            # Make sure there is at least one matching capability
            if len(target_capabilities) == 0:
                logger.error("Requirement '%s': node  '%s' does not have capability of type '%s'",
                             requirement.declaration.name, 
                             requirement.target_node.name,
                             requirement.declaration.capability)
                error = "no capability of type {0}".format(requirement.declaration.capability)
                return error

            # Make sure we have exactly one target capability with
            # valid source node type and valid relationship type.
            relationship_type = requirement.declaration.type_entity
            valid_capabilities = list()
            for capability_name, target_capability_declaration in target_capabilities.items():
                if (target_capability_declaration.is_valid_source_node_type(source_node_type) and
                    (target_capability_declaration.is_valid_relationship_type(relationship_type))):
                    valid_capabilities.append(capability_name)
                    
            if len(valid_capabilities) == 0:
                logger.error("Requirement '%s': node  '%s' does not have capability of type '%s' for which '%s' is a valid source node type and '%s' is a valid relationship type",
                             requirement.declaration.name, 
                             requirement.target_node.name,
                             requirement.declaration.capability,
                             source_node_type.name, relationship_type.name)
                error = "no capability of type '{0}' for which '{1}' is valid source node type and '{2}' is valid relationship type".format(
                    requirement.declaration.capability, source_node_type.name, relationship_type.name)
                return error
            if len(valid_capabilities) > 1:
                logger.error("Requirement '%s': node type '%s' does not have unique capability of type '%s'",
                             requirement.declaration.name, 
                             requirement.target_node.name,
                             requirement.declaration.capability)
                error = "no unique capability of type {0}".format(requirement.declaration.capability)
                return error
            else:
                # Found exactly one. Track the capability name
                requirement.capability = valid_capabilities[0]

        # Everything OK
        return {}


    def validate_target_node_capability_directives(self, requirement: "ToscaRelationshipTemplate") -> Optional[str]:
        """Make sure both sides of the directives pairing admit this
        fixed requirement. Fixed requirements always target a node in
        the same service template, so the relationship is internal --
        BOTH the target capability's directives AND the requirement's
        own directives must include 'internal'.

        Args:
          requirement(ToscaRelationshipTemplate): Tosca requirement
            whose target capability directives to validate
        Returns:
          None when allowed, or an error string when forbidden
        Raises:
          None
        """
        # Requirement side. Default directives include 'internal' so
        # an unspecified directives list always permits internal.
        if 'internal' not in requirement.directives:
            return "'internal' not in requirement directives"
        # Capability templates only exist on the node template when the
        # author explicitly assigned the capability. If there is no
        # assignment the default directives apply (which include
        # 'internal'), so there is nothing to forbid.
        try:
            capability = requirement.target_node.capabilities[requirement.capability]
        except KeyError:
            return None
        if 'internal' not in capability.directives:
            return "'internal' not in directives of target capability '{0}'".format(
                requirement.capability)
        return None


    def validate_target_node_allocation(self, requirement: "ToscaRelationshipTemplate") -> Optional[dict]:
        """Check if a requirement that specifies a target node template
        has valid allocation values: each entry must name an existing
        property of the target capability, that property must be of an
        allocation-compatible type (integer, float, or scalar), and
        the value must validate against that property's type.

        Args:
          requirement(ToscaRelationshipTemplate): Tosca requirement
            that includes the allocation values
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """
        try:
            allocation = requirement.allocation
        except AttributeError:
            return None

        # Resolve the capability declaration on the target node.
        # validate_target_node_capability has run earlier and would
        # have flagged any inability to resolve this; if we still
        # can't get here, just skip the allocation check.
        try:
            node_declaration = requirement.target_node.declaration
            capability_declaration = node_declaration.get_capability_declaration(
                requirement.capability)
        except (AttributeError, KeyError):
            return None

        errors = self._validate_allocation_entries(
            requirement, allocation, capability_declaration)
        return errors if errors else None


    def _validate_allocation_entries(self, requirement: "ToscaRelationshipTemplate",
                                     allocation: dict,
                                     capability_declaration: Any) -> dict:
        """For each allocation entry, verify the named property exists
        on the target capability, that its type is allocation-
        compatible (integer / float / scalar), and that the supplied
        value validates against the property's type.
        """
        integer_type = builtin_types.get('integer')
        float_type = builtin_types.get('float')
        scalar_type = builtin_types.get('scalar')

        errors = {}
        for name, value in allocation.items():
            try:
                property_declaration = capability_declaration.get_property_declaration(name)
            except KeyError:
                logger.error("Requirement '%s': allocation '%s' not a property of target capability",
                             requirement.name, name)
                errors[name] = 'not a property of the target capability'
                continue

            type_entity = property_declaration.type_entity
            is_compatible = (
                type_entity.has_type(integer_type)
                or type_entity.has_type(float_type)
                or type_entity.has_type(scalar_type)
            )
            if not is_compatible:
                logger.error("Requirement '%s': allocation '%s' property type '%s' is not allocation-compatible",
                             requirement.name, name, property_declaration.type)
                errors[name] = (
                    "property type '{0}' is not allocation-compatible; "
                    "must be integer, float, or scalar"
                ).format(property_declaration.type)
                continue

            try:
                property_declaration.validate_value(requirement, value)
            except te.ValidationError as e:
                errors[name] = e.errors
            except Exception as e:
                errors[name] = 'validator error ({0})'.format(str(e))

        return errors
    
        
    def validate_target_node_index(self, requirement: "ToscaRelationshipTemplate") -> Optional[str]:
        """Check if a requirement that specifies a target node template has
        valid target node index value

        Args: 
          requirement(ToscaRelationshipTemplate): Tosca requirement that
            includes the target node index
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """
        # A count value is not allowed here.
        try:
            target_node_index = requirement.target_node_index
        except AttributeError:
            return None

        logger.debug(f"Requirement '{requirement.name}': validating target node index '{str(target_node_index)}'")

        # Make sure target node isn't selectable
        if requirement.target_node.is_selectable():
            return "Indexing selectable target node is not allowed"
        
        # Index must evaluate to an integer value. Create 'integer'
        # declaration against which to validate target node index.
        integer_type = builtin_types.get('integer')
        declaration = integer_type.create_declaration(name='target_node_index')

        # Validate index value
        try:
            index = declaration.validate_value(requirement, target_node_index)
            requirement.target_node_index = index
        except te.ValidationError as e:
            return e.errors
        except Exception as e:
            return str(e)

        # All done
        return None

    def validate_target_node_count(self, requirement: "ToscaRelationshipTemplate") -> Optional[str]:
        """Check if a requirement that specifies a target node template has
        valid count value (or 'occurrences' in v1.3)

        Args: 
          requirement(ToscaRelationshipTemplate): Tosca requirement that
            includes the count value
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """
        # A count value is not allowed here.
        try:
            self.assert_not_present(requirement, '_count')
        except Exception as e:
            return 'not allowed here'
        return None
        # v1.3 used 'occurrences' instead of count.
        try:
            self.assert_not_present(requirement, '_occurrences')
        except Exception as e:
            return 'not allowed here'
        return None


    def validate_target_node_node_filter(self, requirement: "ToscaRelationshipTemplate") -> dict:
        """Check if a requirement that specifies a target node 
        template has a valid node filter

        Args: 
          requirement(ToscaRelationshipTemplate): Tosca requirement that
            includes the node filter
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """
        validation_errors = {}
        # node filter is not allowed here.
        try:
            self.assert_not_present(requirement, 'node_filter')
        except Exception as e:
            validation_errors = 'not allowed here'
        return validation_errors


    ################################################################################
    # Target Query Validation
    ################################################################################

    def validate_target_query(self, requirement: "ToscaRelationshipTemplate") -> dict:
        """Check if a requirement includes is a valid target query for the
        corresponding requirement declaration.

        A target query could be:

        1. A target node query: a query for a target node of a
           specified target node type
        2. A target capability query: a query for a node that contains
           a capability of a specified target capability type

        Args: 
          requirement(ToscaRelationshipTemplate): Tosca requirement that
            includes the target query to validate
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """

        validation_errors = {}

        # Is count value valid?
        errors = self.validate_target_query_count(requirement)
        if errors:
            validation_errors['count'] = errors

        # We either have a target node query or a target capability
        # query
        try:
            # Do we have a valid target node query?
            errors = self.validate_target_node_query(requirement)
            if errors:
                validation_errors.update(errors)
        except AttributeError:
            # Not a target node query. Must be a target capability
            # query
            errors = self.validate_target_capability_query(requirement)
            if errors:
                validation_errors.update(errors)

        # No point in continuing if we have errors
        if validation_errors:
            return validation_errors
        
        # Does the target query specify valid allocations?
        errors = self.validate_target_query_allocation(requirement)
        if errors:
            logger.error("Requirement '%s': invalid target query allocation",
                         requirement.name)
            validation_errors['allocation'] = errors
        
        # All done
        return validation_errors
        
            
    def validate_target_query_count(self, requirement: "ToscaRelationshipTemplate") -> dict:
        """Check if a requirement defines a target node query that includes a
        valid count value (or occurrences range in v1.3) for the
        corresponding requirement declaration.

        Args: 
          requirement(ToscaRelationshipTemplate): Tosca requirement
            that includes the target query for which to validate the
            count value.
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """

        # Check the 'count' value
        errors = self.validate_count_value(requirement)
        if errors:
            return errors
        # No 'count' value or 'count' value is valid. Check occurrences.
        errors = self.validate_occurrences_range(requirement)
        if errors:
            return errors

        # Nothing further to do here. The actual 'count' value will be
        # validated in the node template, since there may be other
        # relationship templates with the same name.
        return {}


    def validate_occurrences_range(self, requirement: "ToscaRelationshipTemplate") -> dict:
        """Check if a relationship template includes a valid count value.

        Args: 
          requirement(ToscaRelationshipTemplate): Tosca
            relationship_template that includes the occurrences range
            to validate
        Returns:
          (Possibly empty) dict of validation errors
        Raises:
          None
        """
        try:
            occurrences = requirement.occurrences
        except AttributeError:
            # No occurrences to validate
            return {}

        # Validate
        try:
            range = ToscaRange(occurrences)
        except TypeError:
            return 'not an array'
        except ValueError:
            return 'not a valid range'
        except Exception as e:
            return str(e)

        # Upper bound of the range must not be zero
        if range.upper_bound == 0:
            return 'upper bound of range must not be 0'

        # Everything OK
        return {}


    ################################################################################
    # Target Node Query Validation
    ################################################################################

    def validate_target_node_query(self, requirement: "ToscaRelationshipTemplate") -> dict:
        """Check if a requirement includes a valid target node query for the
        corresponding requirement declaration. This method raises an
        AttributeError if this not a target node query.

        Args: 
          requirement(ToscaRelationshipTemplate): Tosca requirement that
            includes the target node query to validate
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          AttributeError: when the query does not define a node type
            (in which case we don't have a target node query)
        """

        validation_errors = {}
        
        # Does the target node query define a valid target node type?
        # Note that this method will raise an AttributeError if there
        # is no target node type defined.
        errors = self.validate_target_query_node_type(requirement)
        logger.debug("Requirement %s: validating target node query",
                    requirement.name)
        if errors:
            validation_errors['node'] = errors
            # Target node type is invalid. No point in validating
            # anything else.
            return validation_errors

        # Is the capability type of the target node query valid?
        errors = self.validate_target_node_query_capability(requirement)
        if errors:
            validation_errors['capability'] = errors
            # No point in validating anything else
            return validation_errors
 
        # All done
        return validation_errors


    def validate_target_query_node_type(self, requirement: "ToscaRelationshipTemplate") -> dict:
        """Check if a requirement that defines a target node query has a valid
        target node type. Note that this method will raise an
        AttributeError if there # is no target node type defined.

        Args: 
          requirement(ToscaRelationshipTemplate): Tosca requirement
            that includes the target node query for which to validate
            the target node type
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          AttributeError: when the query does not define a node type
        """

        # Get the node type name specified in the relationship
        try:
            node_type = requirement.target_node_type
        except AttributeError:
            # No node type specified in the requirement. Use the node
            # type from the corresponding requirement declaration
            # instead. Note that this will raise an AttributeError if
            # the requirement declaration does not define a target
            # node type either.
            requirement.target_node_type = requirement.declaration.target_node_type
            # Nothing further to validate
            return {}
        except te.TypeNotFound:
            # type not found
            logger.error("Requirement '%s': node type %s not found", 
                         requirement.declaration.name, requirement._node)
            return '<{0}> not found'.format(requirement._node)
        except Exception as e:
            logger.error("Requirement '%s': error getting  node type '%s': %s",
                         requirement.declaration.name, requirement._node, str(e))
            return 'validator error {}'.format(str(e))

        # Is the target node type a valid subtype of the node type
        # specified in the relationship declaration?
        try:
            if not node_type.has_type(requirement.declaration.target_node_type):
                logger.error("Requirement '%s': node type '%s' does not derive from '%s'",
                             requirement.declaration.name, node,
                             requirement.declaration.node)
                error = "{0} is not a valid subclass of {1}".format(
                    node, requirement.declaration.node)
                return error
        except AttributeError:
            # Relationship declaration doesn't specify a node type.
            # Make sure target node type is valid for relationship
            # type.
            relationship_type = requirement.declaration.type_entity
            if not relationship_type.is_valid_target_node_type(node_type):
                logger.error("Requirement '%s': target_node type '%s' is not a valid target for '%s'",
                             requirement.declaration.name, 
                             node_type.name, requirement.declaration.type)
                error = 'invalid target node type for relationship type ({0})'.format(relationship_type.name)
                return error

        # Everything OK
        return {}

            
    def validate_target_node_query_capability(self, requirement: "ToscaRelationshipTemplate") -> Optional[str]:
        """Check if a requirement definition with a target node query defines a
        valid target capability

        Args: 
          requirement(ToscaRelationshipTemplate): Tosca requirement
            that includes the target node query for which to validate
            the target capability
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """

        # We need source node type to make sure the node type
        # containing the requirement is a valid source for the
        # capability
        try:
            source_node_type = requirement.source_node.declaration.type_entity
        except Exception as e:
            error = "Error getting source node type for '{0}': {1}".format(
                requirement.declaration.name, str(e))
            return error
        
        try:
            # Get the capability specified in the requirement
            capability = requirement.capability
            # The requirement specifies a capability which could be a
            # capability type or a capability name. First, check if it
            # is a capability name.
            try:
                capability_declaration = requirement.target_node_type.get_capability_declaration(capability)
                # Found a target capability based on the capability
                # name in the requirement. Make sure the target
                # capability has the right type and that the source
                # node type and relationship type are valid
                if not capability_declaration.has_type(requirement.declaration.target_capability_type):
                    error = "<{0}> does not have type {1}".format(capability, 
                                                                  requirement.declaration.capability)
                    return error
                if not (capability_declaration.is_valid_source_node_type(source_node_type)):
                    error = "'{0}' is not a valid source node type for capability '{1}'".format(
                        source_node_type.name, capability)
                    return error
                if not (capability_declaration.is_valid_relationship_type(requirement.declaration.type_entity)):
                    error = "'{0}' is not a valid relationship type for capability '{1}'".format(
                        requirement.declaration.type_entity.name, capability)
                    return error
                # Everything checks out
                return None
            
            except KeyError:
                # No such capability declared in the target node
                # type. The target capability in the requirement must
                # refer to a capability type.
                pass

            # If we get here, then the capability in the target node
            # query specifies a capabilty type. Find the corresponding
            # target capability type entity. This will raise a
            # TypeNotFound exception if the capability type doesn't
            # exist
            try:
                capability_type = requirement.profile.get_capability_type(capability)
            except te.TypeNotFound:
                logger.error("Requirement '%s': capability type %s not found", 
                             requirement.declaration.name, capability)
                return '<{0}> not found'.format(capability)
        except AttributeError:
            # No capability or capability type specified in the
            # requirement. Just use the capability type from the
            # declaration.
            capability_type = requirement.declaration.target_capability_type

        # At this point, we have a target capability type. Validate the type.
        logger.debug("Requirement '%s': validating capability type '%s'",
                     requirement.declaration.name, capability_type.name)

        # Is this a valid subtype?
        if not capability_type.has_type(requirement.declaration.target_capability_type):
            logger.error("Requirement '%s': capability type '%s' does not derive from '%s'",
                         requirement.declaration.name, capability_type.name,
                         requirement.declaration.capability)
            error = "{0} is not a valid subclass of {1}".format(
                capability_type.name, requirement.declaration.capability)
            return error

        # Make sure the target node type has at least one capability
        # of this type
        node_type = requirement.target_node_type
        target_capabilities = node_type.get_capability_declarations_of_type(capability_type)
        if len(target_capabilities) == 0:
            logger.error("Requirement '%s': node type '%s' does not have capability of type '%s'",
                         requirement.declaration.name,
                         node_type.name, capability_type.name)
            error = "'{0}' has no capability of type '{1}'".format(
                node_type.name, capability_type.name)
            return error

        # Make sure we have exactly one target capability with
        # valid source node type and valid relationship type
        valid_capabilities=list()
        relationship_type = requirement.declaration.type_entity
        for capability_name, target_capability_declaration in target_capabilities.items():
            if (target_capability_declaration.is_valid_source_node_type(source_node_type) and
                (target_capability_declaration.is_valid_relationship_type(relationship_type))):
                valid_capabilities.append(capability_name)
        if len(valid_capabilities) == 0:
            logger.error("Requirement '%s': node type '%s' does not have capability of type '%s' for which '%s' is a valid source node type and '%s' is valid relationship type",
                         requirement.declaration.name, node_type.name,
                         capability_type.name, source_node_type.name, relationship_type.name)
            error = "'{0}' has no capability of type '{1}' for which '{2}' is valid source node type".format(
                node_type.name, capability_type.name, source_node_type.name)
            return error
        if len(valid_capabilities) > 1:
            logger.error("Requirement '%s': node type '%s' has multiple capabilities of type '%s'",
                         requirement.declaration.name,
                         node_type.name, capability_type.name)
            error = "'{0}' has multiple capabilities of type '{1}'".format(
                node_type.name, capability_type.name)
            return error

        # We have exactly one capability. Replace the capability type
        # name in the relationship template with the actual target
        # capability name.
        requirement.capability = valid_capabilities[0]

        # Is this a valid target for the relationship type? Note that
        # we check against the relationship type in the declaration,
        # since the template itself may not define a type.
        if not requirement.declaration.type_entity.is_valid_capability_type(capability_type):
            logger.error("Requirement '%s': capability type '%s' is not a valid target for '%s'",
                         requirement.declaration.name, 
                         capability_type.name, requirement.type)
            error = '{0} is invalid target for relationship type ({1})'.format(
                capability_type.name, requirement.type)
            return error

        # Everything OK
        return {}


    def upgrade_target_node_query_node_filter(self, requirement: "ToscaRelationshipTemplate") -> dict:
        """Check if a requirement with a target node query defines a valid
        node filter.

        Args: 
          requirement(ToscaRelationshipTemplate): Tosca requirement
            that includes the target node query for which to validate
            the node filter
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """

        # Do we have a node filter?
        try:
            node_filter = requirement.node_filter
            if not node_filter: return {}
        except AttributeError:
            # No node filter to validate
            return {}

        # This validation step only applies to Version 1.x templates
        if not (requirement.tosca_version and
                requirement.tosca_version.startswith("tosca_simple_yaml")):
            return {}

        # Validate and upgrade the node filter.
        validator = get_validator('ToscaFilter')
        return validator.validate_and_upgrade_filter(requirement, requirement.target_node_type, node_filter)


    def validate_target_query_allocation(self, requirement: "ToscaRelationshipTemplate") -> Optional[dict]:
        """Check if a requirement that specifies a target node query
        has valid allocation values. The target capability is known
        from the requirement declaration's target_capability_type; we
        synthesise a capability declaration from that type so the
        same per-entry rules apply.

        Args:
          requirement(ToscaRelationshipTemplate): Tosca requirement
            that includes the allocation values
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """
        try:
            allocation = requirement.allocation
        except AttributeError:
            return None

        try:
            capability_type = requirement.declaration.target_capability_type
            capability_declaration = capability_type.create_declaration('<query>')
        except (AttributeError, KeyError):
            return None

        errors = self._validate_allocation_entries(
            requirement, allocation, capability_declaration)
        return errors if errors else None
    
        
    ################################################################################
    # Target Capbility Query Validation
    ################################################################################

    def validate_target_capability_query(self, requirement: "ToscaRelationshipTemplate") -> dict:
        """Check if a requirement includes a valid target capability query for
        the corresponding requirement declaration. 

        Args: 
          requirement(ToscaRelationshipTemplate): Tosca requirement that
            includes the target capability query to validate
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """

        logger.debug("Requirement %s: validating target capability query",
                     requirement.name)
        validation_errors ={}
        
        # Does the target capability query define a valid target capability type?
        errors = self.validate_target_query_capability_type(requirement)
        if errors:
            validation_errors['capability'] = errors
            # Target capability type is invalid. No point in
            # validating anything else.
            return validation_errors

        # Make sure we don't specify a node filter
        errors = self.validate_target_capability_query_node_filter(requirement)
        if errors:
            validation_errors['node_filter'] = errors

        # All done
        return validation_errors


    def validate_target_query_capability_type(self, requirement: "ToscaRelationshipTemplate") -> dict:
        """Check if a requirement definition with a target capability query
        defines a valid target capability type

        Args: 
          requirement(ToscaRelationshipTemplate): Tosca requirement
            that includes the target capability query for which to
            validate the target capability type
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """

        try:
            # Get the capability type specified in the requirement
            capability = requirement.capability
        except AttributeError:
            # No capability type specified in the
            # requirement. Requirement fulfillment will just use the
            # capability type from the requirement declaration if it
            # exists.
            try:
                capability_type = requirement.declaration.target_capability_type
            except Exception as e:
                return "invalid capability type in requirement declaration"
            # Nothing further to validate
            return {}

        # Get the capability type entity. This will raise a
        # TypeNotFound exception if the capability type doesn't exist.
        try:
            logger.debug("Requirement '%s': validating capability type '%s'",
                         requirement.declaration.name, capability)
            capability_type = requirement.profile.get_capability_type(capability)
        except te.TypeNotFound:
            # type not found
            logger.error("Requirement '%s': capability type %s not found", 
                         requirement.declaration.name, capability)
            return "'{0}' not found".format(capability)
        except Exception:
            logger.error("Requirement '%s': error getting  capability type '%s'",
                         requirement.declaration.name, capability)
            return 'validator error'

        # Is this a valid subtype of the capability type defined in
        # the requirement declaration?
        if not capability_type.has_type(requirement.declaration.target_capability_type):
            logger.error("Requirement '%s': capability type '%s' does not derive from '%s'",
                         requirement.declaration.name, capability_type.name,
                         requirement.declaration.capability)
            error = "{0} is not a valid subclass of {1}".format(
                capability_type.name, requirement.declaration.capability)
            return error

        # Is the containing node type a valid soure for this capability type? 
        try:
            source_node_type = requirement.source_node.declaration.type_entity
        except Exception as e:
            error = "Error getting source node type for '{0}': {1}".format(
                requirement.declaration.name, str(e))
            return error
        if not capability_type.is_valid_source_node_type(requirement.declaration.target_capability_type):
                error = "'{0}' is invalid source type for target capability type '{1}'".format(
                    source_node_type.name, capability_type.name)
                return error
        # Is the incoming relationship valid for this capability type? 
        relationship_type = requirement.declaration.type_entity
        if not capability_type.is_valid_relationship_type(relationship_type):
                error = "'{0}' is invalid source type for target capability type '{1}'".format(
                    source_node_type.name, capability_type.name)
                return error

        # Do we need to check if this a valid target for the
        # relationship type? Presumably this check was already done
        # for the capability type in the requirement declaration.

        # Everything OK
        return {}


    def validate_target_capability_query_node_filter(self, requirement: "ToscaRelationshipTemplate") -> dict:
        """Check if a requirement that specifies a target capability query has
        a valid node filter

        Args: 
          requirement(ToscaRelationshipTemplate): Tosca requirement that
            includes the node filter
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """
        validation_errors = {}
        # If this is a Version 1.x template, a node filter is not
        # allowed here.
        try:
            self.assert_not_present(requirement, 'node_filter')
        except Exception as e:
            if (requirement.tosca_version and
                requirement.tosca_version.startswith("tosca_simple_yaml")):
                validation_errors = 'not allowed without target node type'
        return validation_errors
