"""
ToscaRelationshipDeclarationValidator class
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2014-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger = logging.getLogger(__name__)

# Type hint support
from typing import Any, TYPE_CHECKING
if TYPE_CHECKING:
    from tosca_core.models.node_type import ToscaNodeType

# Types on which this validator depends
from tosca_core.models.relationship_declaration import ToscaRelationshipDeclaration

# Cached lookups for TOSCA built-in data types
import tosca_core.models.builtin_types as builtin_types

# Validator support
from . import get_validator
from .managed_declaration import ToscaManagedDeclarationValidator

# Exception support
import tosca_core.models.exceptions as te


class ToscaRelationshipDeclarationValidator(ToscaManagedDeclarationValidator):
    """The ToscaRelationshipDeclarationValidator class validates TOSCA
    requirement declarations in Node Types: these declare the presence
    of a requirement in all node templates of the specified type. Note
    that in this file, we use the terms 'relationship declaration' and
    'requirement declaration' interchangeably.
    """


    def __init__(self) -> None:
        """Constructor
        """
        super(ToscaRelationshipDeclarationValidator, self).__init__()


    def validate_implied_type(self, node_type: "ToscaNodeType", requirement_declaration: "ToscaRelationshipDeclaration") -> dict:
        """Try to obtain implied relationship type for the requirement
        declaration. In v1.3 of the TOSCA spec, relationship types are
        not mandatory, but the Ubicity implementation requires that
        all entities have types. This method attemtps to find a
        compatible relationship type

        Note that there is a chicken-and-egg problem here: we attempt
        to find the relationship type based on the capability type,
        but the capability type has not yet been validated.

        Args: 
          node_type(ToscaNodeType): node type for which to validate
            the requirement declaration
          requirement_declaration(ToscaRelationshipDeclaration): Tosca
            requirement declaration for which to find a relationship
            type

        Returns:
          (str): error message

        Raises:
          None

        """

        logger.debug("%s: Get implied type for requirement '%s'",
                     node_type.name, requirement_declaration.name)

        # Only TOSCA 1.3 leaves a requirement's relationship type for the
        # orchestrator to find. A TOSCA 2.0 requirement definition must
        # name it (section 8.4); a refinement of an inherited requirement
        # has already taken its parent's by the time this runs.
        version = getattr(requirement_declaration, 'tosca_version', None) or ''
        if not version.startswith('tosca_simple_yaml'):
            logger.error("%s: Requirement '%s' does not name its relationship type",
                         node_type.name, requirement_declaration.name)
            return "no relationship type"

        # No relationship type specified in the requirement
        # declaration. Find a unique relationship type that has the
        # capability type as a valid target. First, find the
        # capability type
        try:
            capability_type = requirement_declaration.target_capability_type
            capability = capability_type.name
        except Exception as e:
            return "invalid capability type from which to find relationship type"

        # Find all the relationship types in this profile for which
        # the specified capability type is a valid target
        valid_relationships = {}
        profile = node_type.profile
        types = profile.get_relationship_types()
        for relationship_name, relationship_type in profile.get_relationship_types().items():
            if relationship_type.is_valid_capability_type(capability_type):
                # Make sure to enter using fully qualified (canonical)
                # name to avoid duplicates. TODO: canonical name
                # should include profile name as well as type name
                valid_relationships[relationship_type.name] = relationship_type

        # Did we find exactly one?
        if len(valid_relationships) == 0:
            logger.error("%s: Requirement '%s': no relationship type for capability '%s'",
                         node_type.name, requirement_declaration.name, 
                         capability)
            error = "no compatible relationship type found for capability type '{0}'".format(
                capability)
            return error
        elif len(valid_relationships) > 1:
            logger.debug("%s: Requirement '%s': no unique relationship type for capability '%s'",
                         node_type.name, requirement_declaration.name, 
                         capability)
            logger.debug("%s: Requirement '%s': using the first relationship type from the following list:",
                         node_type.name, requirement_declaration.name)
            for valid_relationship in valid_relationships:
                logger.debug("  %s", valid_relationship)

        # We have at least one valid type. Use the first type from the list
        relationship_type_name, relationship_type = list(valid_relationships.items())[0]
        logger.debug("%s: Requirement '%s': synthesize relationship declaration of of type <%s",
                     node_type.name, requirement_declaration.name,
                     relationship_type_name)
        # Set the type
        requirement_declaration.type_entity = relationship_type

        return {}


    ################################################################################
    # Declaration Validation. 
    ################################################################################

    def validate_for_type(self, node_type: "ToscaNodeType",
                          requirement_declaration: "ToscaRelationshipDeclaration") -> dict:
        """Check if a requirement declaration is valid for the
        specified node type

        Args: 
          node_type(ToscaNodeType): node type for which to validate
            the requirement declaration
          requirement_declaration(ToscaRelationshipDeclaration): Tosca
            requirement declaration to validate
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """

        logger.debug("Node type '%s': validating requirement declaration '%s'", 
                     node_type.name, requirement_declaration.name)

        # First, check if the requirement declaration is a valid
        # managed instance declaration
        validation_errors = super(ToscaRelationshipDeclarationValidator,
                                  self).validate_for_type(node_type, 
                                                          requirement_declaration)

        # Make sure that this is a valid relationship for the source node
        if not requirement_declaration.type_entity.is_valid_source_node_type(node_type):
            logger.error("Node type '%s' is not a valid source type for relationship type '%s'",
                         node_type.name, requirement_declaration.type)
            error = f"'{node_type.name}' is not a valid source node type for '{requirement_declaration.type}'"
            validation_errors['source_node'] = error
        
        # Make sure that the requirement declaration has a valid
        # target capability type
        errors = self.validate_target_capability_type(node_type, 
                                                      requirement_declaration)
        if errors:
            logger.error("%s: Requirement '%s' has invalid target capability type",
                         node_type.name, requirement_declaration.name)
            validation_errors['capability'] = errors
        else:
            # If there is a valid capability type specified, make sure
            # that the requirement declaration has a valid target node
            # type
            errors = self.validate_target_node_type(node_type, 
                                                    requirement_declaration)
            if errors:
                logger.error("%s: Requirement '%s' has invalid target node type",
                             node_type.name, requirement_declaration.name)
                validation_errors['node'] = errors

        # Make sure that the requirement declaration has a valid node
        # filter
        errors = self.validate_node_filter(node_type, requirement_declaration)
        if errors:
            logger.error("%s: Requirement '%s' has invalid node_filter",
                         node_type.name, requirement_declaration.name)
            validation_errors['node_filter'] = errors

        # Make sure that the requirement declaration has valid
        # count_range
        errors = self.validate_count_range(node_type, requirement_declaration)
        if errors:
            logger.error("%s: Requirement '%s' has invalid count_range",
                         node_type.name, requirement_declaration.name)
            validation_errors['count_range'] = errors

        # All done
        return validation_errors


    def validate_target_capability_type(self, node_type: "ToscaNodeType", requirement_declaration: "ToscaRelationshipDeclaration") -> dict:
        """Check if a requirement declaration has a valid target capability
        type. If it does, also check whether the target capability
        type is compatible with the type of the requirement
        declaration.

        Args: 
          node_type(ToscaNodeType): node type for which to validate
            the requirement declaration
          requirement_declaration(ToscaRelationshipDeclaration): Tosca
            requirement declaration for which to validate the target
            capability type

        Returns:
          (possibly empty) dict of validation errors

        Raises:
          None
        """
        validation_errors = {}

        # Get the capability type entity. This will raise
        # AttributeError if no capability is specified or a
        # TypeNotFound exception if the capability type doesn't exist
        try:
            capability_type = requirement_declaration.target_capability_type
            capability = capability_type.name
        except AttributeError:
            logger.error("%s: Requirement '%s' does not specify capability",
                         node_type.name, requirement_declaration.name)
            return 'not specified'
        except te.TypeNotFound:
            # type not found
            capability = requirement_declaration._capability
            logger.error("Requirement '%s': capability type %s not found", 
                         requirement_declaration.name, 
                         capability)
            validation_errors[capability] = 'type not found'
            return validation_errors

        # Make sure the target capability type is a valid target
        # for the specified relationship type
        relationship_type = requirement_declaration.type_entity
        if not relationship_type.is_valid_capability_type(capability_type):
            logger.error("%s: Requirement '%s': capability type '%s' is not a valid target for '%s'",
                         node_type.name, requirement_declaration.name, 
                         capability, requirement_declaration.type)
            error = 'invalid target for relationship type ({0})'.format(relationship_type.name)
            validation_errors[capability] = error

        # Make sure the source node type is valid for the specified
        # capability type
        if not capability_type.is_valid_source_node_type(node_type):
            logger.error("%s: Requirement '%s': not a valid source node type for capability type '%s'",
                         node_type.name, requirement_declaration.name, 
                         capability)
            error = "invalid source node type '{0}'".format(node_type.name)
            validation_errors[capability] = error

        # Make sure the relationship type is valid for the specified
        # capability type
        if not capability_type.is_valid_relationship_type(relationship_type):
            logger.error("%s: Requirement '%s': not a valid relationship type for capability type '%s'",
                         relationship_type.name, requirement_declaration.name, 
                         capability)
            error = "invalid relationship type '{0}'".format(relationship_type.name)
            validation_errors[capability] = error

        # Everything OK
        return validation_errors


    def validate_target_node_type(self, node_type: "ToscaNodeType", requirement_declaration: "ToscaRelationshipDeclaration") -> dict:
        """Check if a requirement declaration has a valid target node
        type. This method will only get called if there is a valid
        target capability type specified in the requirement
        declaration.

        Args: 
          node_type(ToscaNodeType): node type for which to validate
            the requirement declaration
          requirement_declaration(ToscaRelationshipDeclaration): Tosca
            requirement declaration for which to validate the target
            node type

        Returns:
          (possibly empty) dict of validation errors

        Raises:
          None
        """

        validation_errors = {}

        # Get the node type entity. This will raise AttributeError if
        # no node is specified or a TypeNotFound error if the node
        # type doesn't exist
        try:
            target_node_type = requirement_declaration.target_node_type
            node = target_node_type.name
        except AttributeError:
            # No node specified. Nothing further to validate
            logger.debug("%s: Requirement '%s' does not specify node",
                         node_type.name, requirement_declaration.name)
            return validation_errors
        except te.TypeNotFound:
            # Node type not found
            node = requirement_declaration._node
            logger.error("%s: Requirement '%s': invalid node type '%s'",
                         node_type.name, requirement_declaration.name, 
                         node)
            validation_errors[node] = 'type not found'
            return validation_errors

        # Make sure the target node type is valid for the specified
        # relationship type
        relationship_type = requirement_declaration.type_entity
        if not relationship_type.is_valid_target_node_type(target_node_type):
            logger.error("%s: Requirement '%s': target_node type '%s' is not a valid target for '%s'",
                         node_type.name, requirement_declaration.name, 
                         target_node_type.name, requirement_declaration.type)
            error = 'invalid target node type for relationship type ({0})'.format(relationship_type.name)
            validation_errors[node] = error

        # Check if the target node type defines capabilities of the
        # type specified in the requirement declaration
        capability_type = requirement_declaration.target_capability_type
        target_capabilities = target_node_type.get_capability_declarations_of_type(capability_type)
        if len(target_capabilities) == 0:
            logger.error("%s: Requirement '%s': node type '%s' does not have capability of type '%s'",
                         node_type.name, requirement_declaration.name, 
                         node, requirement_declaration.capability)
            error = 'no capability of type {0}'.format(requirement_declaration.capability)
            validation_errors[node] = error

        # Make sure the target node type has at least one capability
        # with a valid source node type and a valid capability type.
        valid_capabilities=list()
        relationship_type = requirement_declaration.type_entity
        for capability_name, target_capability_declaration in target_capabilities.items():
            if (target_capability_declaration.is_valid_source_node_type(node_type) and
                (target_capability_declaration.is_valid_relationship_type(relationship_type))):
                valid_capabilities.append(capability_name)
        if len(valid_capabilities) == 0:
            logger.error("%s: Requirement '%s': target node type '%s' does not have capability of type '%s' for which '%s' is a valid source node type and '%s' is a valid relationship type",
                         node_type.name, requirement_declaration.name, node,
                         requirement_declaration.capability, node_type.name, relationship_type.name)
            error = "target node type '{0}' has no capability of type '{1}' for which '{2}' is valid source node type and '{3}' is valid relationship type".format(
                node, capability_type.name, node_type.name, relationship_type.name)
            return error

#        elif len(valid_capabilities) > 1:
#            logger.error("%s: Requirement '%s': node type '%s' does not have unique capability of type '%s'",
#                         node_type.name, requirement_declaration.name, 
#                         node,
#                         requirement_declaration.capability)
#            error = 'no unique capability of type {0}'.format(requirement_declaration.capability)
#            validation_errors[node] = error 

        # Everything OK
        return validation_errors


    def validate_node_filter(self, node_type: "ToscaNodeType", requirement_declaration: "ToscaRelationshipDeclaration") -> dict:
        """Check if a requirement declaration within a node type defines a
        valid node filter.

        Args: 
          node_type(ToscaNodeType): node type for which to validate
            the requirement declaration
          requirement_declaration(ToscaRelationshipDeclaration): Tosca
            requirement declaration to validate
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None

        """

        # Do we have a node filter?
        try:
            node_filter = requirement_declaration.node_filter
            if not node_filter: return {}
        except AttributeError:
            # No node filter to validate
            return {}

        # Validate and upgrade Version 1.x node filters if necessary
        if (requirement_declaration.tosca_version and
            requirement_declaration.tosca_version.startswith("tosca_simple_yaml")):
            # Make sure we have a target node type
            try:
                node = requirement_declaration._node
            except AttributeError:
                # Node filters are not allowed without node type
                return "not allowed without target node type"
            # Validate and upgrade
            validator = get_validator('ToscaFilter')
            errors =  validator.validate_and_upgrade_filter(requirement_declaration,
                                                            requirement_declaration.target_node_type, node_filter)
            if errors:
                return errors

        node_filter = requirement_declaration.node_filter
        errors, canonical = self._validate_boolean_expression(requirement_declaration, node_filter, 'node_filter')
        if errors:
            return errors
        requirement_declaration.resolved_filter = canonical
        return {}


    def validate_count_range(self, node_type: "ToscaNodeType", requirement_declaration: "ToscaRelationshipDeclaration") -> dict:
        """Check if a requirement declaration has valid count_range

        Args: 
          node_type(ToscaNodeType): node type for which to validate
            the requirement declaration
          requirement_declaration(ToscaRelationshipDeclaration): Tosca requirement
            declaration to validate
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """

        # Avoid using the count_range 'getter' since it creates a
        # default value if count_range were not explicitly set. This
        # would interfere with relationship refinements.
        try:
            count_range = requirement_declaration._count_range
            if not count_range: return {}
        except AttributeError:
            # No count_range to validate
            return {}

        # count_range is a TOSCA 2.0 grammar element, not the legacy
        # 1.3 'range' data type, so we validate it inline rather than
        # going through ToscaRange (which is 1.3-only and accepts
        # floats for its other callers).
        parsed = self._parse_count_range(count_range)
        if isinstance(parsed, str):
            return parsed
        return {}


    def _parse_count_range(self, count_range: Any) -> Any:
        """Parse and validate a count_range list. Returns the
        (lower, upper) tuple on success or a single string describing
        the failure. 'UNBOUNDED' is permitted as the upper bound.
        """
        if not isinstance(count_range, list) or len(count_range) != 2:
            return 'not a valid count_range'

        lower, upper = count_range
        if isinstance(lower, bool) or not isinstance(lower, int):
            return "lower bound '{0}' is not an integer".format(lower)
        if lower < 0:
            return 'negative lower bound'

        if upper == 'UNBOUNDED':
            return (lower, upper)
        if isinstance(upper, bool) or not isinstance(upper, int):
            return "upper bound '{0}' is not an integer".format(upper)
        if upper < lower:
            return "upper bound '{0}' less than lower bound '{1}'".format(upper, lower)
        return (lower, upper)


    ################################################################################
    # Augmentation Validation
    ################################################################################

    def complete_augmentation(self, node_type: "ToscaNodeType", requirement_name: str,
                              requirement_to_augment: "ToscaRelationshipDeclaration", requirement_declaration: "ToscaRelationshipDeclaration") -> dict:
        """Check that a requirement declaration is a valid augmentation of
        the one it refines and, if it is, complete it by merging that
        declaration in. The completed declaration is validated with the
        node type's other requirements.

        Args: 
         node_type(ToscaNodeType): node type definition within which
           this requirement is declared
         requirement_name(str): name of the requirement declaration
         requirement_to_augment(ToscaRelationshipDeclaration): Tosca
          requirement that is augmented
         requirement_declaration(ToscaRelationshipDeclaration): Tosca
          requirement augmentation to validate

        Returns:
          (possibly empty) dict of validation errors

        Raises:
          None
        """

        logger.debug("Node type '%s': validating requirement augmentation '%s'",
                     node_type.name, requirement_name)

        # Does the requirement augmentation have valid attribute values?
        errors = self.validate_requirement_augmentation(requirement_to_augment, requirement_declaration)
        if errors:
            logger.error("Type '%s': requirement '%s': invalid augmentation",
                         node_type.name, requirement_name)
            self.add_line_number(errors, requirement_declaration)
            return errors

        # Valid requirement augmentation. Augment the requirement
        # declaration with information from the refined requirement
        # declaration.
        requirement_declaration.merge_augmented_declaration(requirement_to_augment)

        # Everthing OK
        return {}


    def validate_requirement_augmentation(self, requirement_to_augment: "ToscaRelationshipDeclaration",
                                          requirement_declaration: "ToscaRelationshipDeclaration") -> dict:
        """Check if a requirement declaration is a valid augmentation of a
        previous requirement declaration:

        After these conditions are set, a new requirement declaration
        must be created from the augmentation, and that new requirement
        declaration must be validated separately

        Args: 
          requirement_to_augment(ToscaRelationshipDeclaration): Tosca
            requirement declaration to augment
          requirement_declaration(ToscaRelationshipDeclaration): Tosca
            requirement declaration to validate

        Returns:
          (possibly empty) dict of validation errors

        Raises:
          None
        """

        validation_errors = {}

        # Make sure the capability type augmentation is valid
        errors = self.validate_capability_augmentation(requirement_to_augment, 
                                                       requirement_declaration)
        if errors:
            logger.error("Requirement '%s': augmentation has invalid capability",
                         requirement_declaration.name)
            validation_errors['capability'] = errors
            
        # Make sure the relationship type augmentation is valid
        errors = self.validate_relationship_augmentation(requirement_to_augment, 
                                                         requirement_declaration)
        if errors:
            logger.error("Requirement '%s': augmentation has invalid relationship",
                         requirement_declaration.name)
            validation_errors['relationship'] = errors
            
        # Make sure the node type augmentation is valid
        errors = self.validate_node_augmentation(requirement_to_augment, 
                                                 requirement_declaration)
        if errors:
            logger.error("Requirement '%s': augmentation has invalid node",
                         requirement_declaration.name)
            validation_errors['node'] = errors

        # Make sure the count_range augmentation is valid
        errors = self.validate_count_range_augmentation(requirement_to_augment, 
                                                        requirement_declaration)
        if errors:
            logger.error("Requirement '%s': augmentation has invalid count_range",
                         requirement_declaration.name)
            validation_errors['count_range'] = errors

        # Everything OK
        return validation_errors


    def validate_capability_augmentation(self, requirement_to_augment: "ToscaRelationshipDeclaration",
                                         requirement_declaration: "ToscaRelationshipDeclaration") -> dict:
        """Check if a requirement augmentation has a valid capability
        type augmentation

        Args: 
          requirement_to_augment(ToscaRelationshipDeclaration): Tosca
            requirement declaration to augment
          requirement_declaration(ToscaRelationshipDeclaration): Tosca
            requirement declaration to validate

        Returns:
          (possibly empty) dict of validation errors

        Raises:
          None
        """

        validation_errors = {}

        # Get the capability type entity. This will raise
        # AttributeError if no capability is specified or a
        # TypeNotFound error if the capability type doesn't exist
        try:
            capability = requirement_declaration._capability
            logger.debug("Requirement augmentation '%s': validating capability type '%s'",
                         requirement_declaration.name,
                         capability)
            profile = requirement_declaration.profile
            capability_type = profile.get_capability_type(capability)
        except AttributeError:
            # No capability specified. That's OK.
            logger.debug("Requirement augmentation '%s' does not specify capability",
                         requirement_declaration.name)
            return validation_errors
        except te.TypeNotFound:
            # type not found
            logger.error("Declaration '%s': type %s not found", 
                         requirement_declaration.name, 
                         capability)
            validation_errors[capability] = 'not found' 
            return validation_errors

        # Make sure the capability type is a valid subclass of the
        # target capability type specified in the requirement being
        # augmented.
        try:
            capability_type_to_augment = requirement_to_augment.target_capability_type
            if not capability_type.has_type(capability_type_to_augment):
                logger.error("Requirement augmentation '%s': capability type '%s' does not subclass '%s'",
                             requirement_declaration.name, 
                             capability,
                             capability_type_to_augment.name)
                error = "not a valid subclass of {0}".format(capability_type_to_augment.name)
                validation_errors[capability] = error
        except AttributeError:
            # No capability to augment
            pass

        # Everything OK
        return validation_errors


    def validate_relationship_augmentation(self, requirement_to_augment: "ToscaRelationshipDeclaration",
                                           requirement_declaration: "ToscaRelationshipDeclaration") -> dict:
        """Check if a requirement augmentation has a valid relationship
        type augmentation

        Args: 
          requirement_to_augment(ToscaRelationshipDeclaration): Tosca
            requirement declaration to augment
          requirement_declaration(ToscaRelationshipDeclaration): Tosca
            requirement declaration to validate

        Returns:
          (possibly empty) dict of validation errors

        Raises:
          None
        """

        validation_errors = {}

        # Get the relationship type entity from the augmentation. If
        # the augmentation doesn't specify a type, use the type from
        # the requirement for which we are an augmentation. This will
        # raise a TypeNotFound error if the relationship type doesn't
        # exist
        try:
            logger.debug("Requirement augmentation '%s': validating relationship type '%s'",
                         requirement_declaration.name,
                         requirement_declaration._type)
            profile = requirement_declaration.profile
            relationship_type = profile.get_relationship_type(requirement_declaration._type)
        except AttributeError:
            logger.debug("Requirement augmentation '%s' does not specify relationship",
                         requirement_declaration.name)
            relationship_type = requirement_to_augment.type_entity
        except te.TypeNotFound:
            # type not found
            logger.error("Declaration '%s': type %s not found", 
                         requirement_declaration.name, 
                         requirement_declaration._type)
            validation_errors['type'] = { requirement_declaration._type : 'not found' }
            return validation_errors

        # Make sure the relationship type is a valid subclass of the
        # relationship type specified in the requirement being
        # augmented.
        try:
            if not relationship_type.has_type(requirement_to_augment.type_entity):
                logger.error("Requirement augmentation '%s': relationship type '%s' does not subclass '%s'",
                             requirement_declaration.name, 
                             requirement_declaration.type,
                             requirement_to_augment.type)
                error = "not a valid subclass of {0}".format(requirement_to_augment.type)
                validation_errors['type'] = { requirement_declaration._type : error }
        except AttributeError:
            # No relationship to augment
            pass

        # Everything OK
        return validation_errors


    def validate_node_augmentation(self, requirement_to_augment: "ToscaRelationshipDeclaration",
                                   requirement_declaration: "ToscaRelationshipDeclaration") -> dict:
        """Check if a requirement augmentation has a valid node
        type augmentation

        Args: 
          requirement_to_augment(ToscaRelationshipDeclaration): Tosca
            requirement declaration to augment
          requirement_declaration(ToscaRelationshipDeclaration): Tosca
            requirement declaration to validate

        Returns:
          (possibly empty) dict of validation errors

        Raises:
          None
        """

        validation_errors = {}

        # Get the node type entity. This will raise AttributeError if
        # no node is specified or a TypeNotFound error if the node
        # type doesn't exist
        try:
            node = requirement_declaration._node
            logger.debug("Requirement augmentation '%s': validating node type '%s'",
                         requirement_declaration.name,
                         node)
            profile = requirement_declaration.profile
            node_type = profile.get_node_type(node)
        except AttributeError:
            # No node specified. That's OK.
            logger.debug("Requirement augmentation '%s' does not specify node",
                         requirement_declaration.name)
            return validation_errors
        except te.TypeNotFound:
            # type not found
            logger.error("Declaration '%s': type %s not found", 
                         requirement_declaration.name, 
                         node)
            validation_errors[node] = 'not found' 
            return validation_errors

        # Make sure the node type is a valid subclass of the node type
        # specified in the requirement being augmented.
        try:
            node_type_to_augment = requirement_to_augment.target_node_type
            if not node_type.has_type(node_type_to_augment):
                logger.error("Requirement augmentation '%s': node type '%s' does not subclass '%s'",
                             requirement_declaration.name, 
                             node,
                             node_type_to_augment.name)
                error = "not a valid subclass of {0}".format(node_type_to_augment.name)
                validation_errors[node] = error
        except AttributeError:
            # No node to augment
            pass

        # Everything OK
        return validation_errors


    def validate_count_range_augmentation(self, requirement_to_augment: "ToscaRelationshipDeclaration",
                                          requirement_declaration: "ToscaRelationshipDeclaration") -> dict:
        """Check if a requirement augmentation has a valid count_range
        augmentation

        Args: 
          requirement_to_augment(ToscaRelationshipDeclaration): Tosca
            requirement declaration to augment
          requirement_declaration(ToscaRelationshipDeclaration): Tosca
            requirement declaration to validate

        Returns:
          (possibly empty) dict of validation errors

        Raises:
          None
        """

        # Do we have count_range
        try:
            count_range = requirement_declaration._count_range
            if not count_range: return {}
        except AttributeError:
            # No count_range to validate
            return {}

        # Validate the augmenting count_range itself
        parsed = self._parse_count_range(count_range)
        if isinstance(parsed, str):
            return parsed
        lower, upper = parsed

        # The augmented declaration's count_range should already be
        # valid (it was checked when that declaration was processed),
        # but guard against the unusual case where it's not.
        parsed_decl = self._parse_count_range(requirement_to_augment.count_range)
        if isinstance(parsed_decl, str):
            return 'augmented declaration has invalid count_range'
        decl_lower, decl_upper = parsed_decl

        # Augmentation must further constrain the augmented range:
        #   decl_lower <= lower and upper <= decl_upper
        if lower < decl_lower:
            return 'invalid refinement of declaration'
        if decl_upper != 'UNBOUNDED':
            if upper == 'UNBOUNDED' or upper > decl_upper:
                return 'invalid refinement of declaration'

        return {}

