"""
ToscaSubstitutionMappingsValidator class
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2015-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger = logging.getLogger(__name__)

# Type hint support
from typing import Any, Optional

# Exception support
import tosca_core.models.exceptions as te

# Function-key parsing, to spot a '$get_input' after canonicalization
import tosca_core.models.function_declaration as fd

# Shared with the substitution path: what a requirement mapping target is
import tosca_core.models.substitution_mappings as sm

# Validator support
from . import get_validator
from .validator import ToscaValidator


class ToscaSubstitutionMappingsValidator(ToscaValidator):
    """The ToscaSubstitutionMappingsValidator class validates
    substitution mappings defined in Tosca service templates against
    the node templates defined in those service templates.
    """

    def __init__(self) -> None:
        """Constructor
        """
        super(ToscaSubstitutionMappingsValidator, self).__init__()


    def validate_substitution_mappings(self, service: "Any", substitution_mappings: dict) -> dict:
        """Check if substitution mappings are valid within the
        specified service template

        Args: 
          service(ToscaServiceTemplate): service template within
            which to validate the instance
          substitution_mappings(dict): substitution mappings to
            validate
        """

        validation_errors = {}

        # Check node type
        errors = self.validate_node_type(service, substitution_mappings)
        if errors:
            logger.error("Substitution mappings do not specify valid node type")
            validation_errors['node_type'] = errors
            if substitution_mappings.line is not None:
                validation_errors = {'line': substitution_mappings.line, **validation_errors}
            return validation_errors

        # Node type is OK. Check the actual mappings
        node_type = service.substitutes

        # Upgrade attribute mappings if necessary
        self.upgrade_attribute_mappings(service, node_type, substitution_mappings)
        
        # Check attribute mappings
        errors = self.validate_attribute_mappings(service, node_type, substitution_mappings)
        if errors:
            logger.error("Substitution mappings have invalid attribute mappings")
            validation_errors['attributes'] = errors

        # Upgrade property mappings if necessary
        self.upgrade_property_mappings(service, node_type, substitution_mappings)
        
        # Check property mappings
        errors = self.validate_property_mappings(service, node_type, substitution_mappings)
        if errors:
            logger.error("Substitution mappings have invalid property mappings")
            validation_errors['properties'] = errors

        # Check capability mappings
        errors = self.validate_capability_mappings(service, node_type, substitution_mappings)
        if errors:
            logger.error("Substitution mappings have invalid capability mappings")
            validation_errors['capabilities'] = errors

        # Check requirement mappings
        errors = self.validate_requirement_mappings(service, node_type, substitution_mappings)
        if errors:
            logger.error("Substitution mappings have invalid requirement mappings")
            validation_errors['requirements'] = errors
        else:
            self.warn_unmapped_containment(node_type, substitution_mappings)

        # Check interface mappings
        errors = self.validate_interface_mappings(service, node_type, substitution_mappings)
        if errors:
            logger.error("Substitution mappings have invalid interface mappings")
            validation_errors['interfaces'] = errors

        # Check substitution filter
        errors = self.validate_substitution_filter(service, node_type, substitution_mappings)
        if errors:
            logger.error("Substitution mappings have invalid substitution filter")
            validation_errors['substitution_filter'] = errors

        # Everything OK
        if validation_errors:
            line = substitution_mappings.line
            if line is not None:
                items = list(validation_errors.items())
                validation_errors.clear()
                validation_errors['line'] = line
                validation_errors.update(items)
        return validation_errors


    def validate_node_type(self, service: "Any", substitution_mappings: dict) -> Optional[Any]:
        """Check if substitution mappings specify a valid node type

        Args: 
          service(ToscaServiceTemplate): service within which to validate
            the instance
          substitution_mappings(dict):
            substitution mappings to validate
        """

        try:
            logger.debug("Substitution mappings: validating node type '%s'", 
                         substitution_mappings.node_type)
            node_type = service.profile.get_node_type(substitution_mappings.node_type)
        except (AttributeError, KeyError):
            # No type
            logger.debug("Substitution mappings: no node type specified")
            return 'not specified'
        except te.TypeNotFound:
            # node type not found
            logger.debug("Substitution mappings: invalid node type '%s'", 
                         substitution_mappings.node_type)
            return { substitution_mappings.node_type: 'not found' }
        except Exception as e:
            logger.error("Substitution mappings: error validating node type: %s",
                         e)
            return str(e)

        # Keep track of node type
        service.substitutes = node_type
        return None


    def validate_substitution_filter(self, service: "Any", node_type: "Any", substitution_mappings: dict) -> dict:
        """Check if substitution mappings have a valid substitution filter for
        the substituted type

        Args: 
          service(ToscaServiceTemplate): service within which to validate
            the instance
          node_type(ToscaNodeType): type of the node for which this
            service is a substitution
          substitution_mappings(dict):
            substitution mappings to validate
        """
        # Do the substitution mappings include a substitution filter?
        try:
            substitution_filter = substitution_mappings.substitution_filter
        except (AttributeError, KeyError):
            # No type
            logger.debug("'%s' substitution mappings: no substitution filter specified",
                         node_type.name)
            return {}

        # Validate and upgrade Version 1.x substitution filter if necessary.
        if (service.tosca_version and
                service.tosca_version.startswith("tosca_simple_yaml")):
            validator = get_validator('ToscaFilter')
            try:
                errors = validator.validate_filter(service, node_type, substitution_filter)
                if errors:
                    return errors
            except Exception as e:
                logger.error("'%s': error validating substitution filter: %s", service.name, e)
                return "validator error ({0})".format(e)

            # We have a valid substitution filter. Upgrade to a
            # Version 2.0 boolean function (which will be validated
            # again later and resolved to internal function syntax).
            substitution_filter = validator.upgrade_filter(node_type, substitution_filter)

        # The context is the substitution mappings, not the substituted node
        # type. A context answers for both the document an expression is
        # written in -- namespaces, grammar, the inputs and named nodes it may
        # reach -- and the entity it refers to, and only the mappings know
        # both: the containing service template supplies the first, the node
        # type they substitute for supplies SELF. Passing the node type
        # supplied only the second, so a filter calling a profile function
        # failed with 'not found in namespace' (tosca_core.models.context).
        errors, canonical = self._validate_boolean_expression(
            substitution_mappings, substitution_filter, 'substitution_filter')
        if errors:
            return errors

        # A filter decides whether to instantiate this template, so it runs
        # before the template's inputs exist. Reading one can be validated but
        # never evaluated, so reject it here rather than resolve it to
        # something plausible.
        errors = self._reject_get_input(canonical)
        if errors:
            return errors

        substitution_mappings.substitution_filter = canonical
        return {}


    def _reject_get_input(self, expression: "Any") -> dict:
        """Refuse a '$get_input' anywhere in a substitution filter.

        Returns an error dict when one is present, an empty dict otherwise.
        """
        if isinstance(expression, dict):
            for key, args in expression.items():
                try:
                    name = fd.get_signature(fd.parse_function_key(key)[0]).function.name
                except Exception:
                    name = None
                if name == 'get_input':
                    return {'substitution_filter':
                            "'$get_input' cannot be used in a substitution filter: the filter "
                            "decides whether to instantiate this template, so its inputs do not "
                            "exist yet"}
                errors = self._reject_get_input(args)
                if errors:
                    return errors
        elif isinstance(expression, list):
            for item in expression:
                errors = self._reject_get_input(item)
                if errors:
                    return errors
        return {}


    def validate_attribute_mappings(self, service: "Any", node_type: "Any", substitution_mappings: dict) -> dict:
        """Check if substitution mappings have valid attribute
        mappings within the specified service

        Args: 
          service(ToscaServiceTemplate): service template within
            which to validate the instance
          node_type(ToscaNodeType): type of the node for which this
            service is a substitution
          substitution_mappings(dict): substitution mappings to
            validate
        """

        validation_errors = {}

        # Do the substitution mappings reference a type?
        try:
            attributes = substitution_mappings.attributes
        except (AttributeError, KeyError):
            # No type
            logger.debug("Substitution mappings: no attribute mappings specified")
            return validation_errors


        # Validate each attribute mapping
        for attribute_name, attribute_mapping in attributes.items():
            logger.debug("Substitution mappings: validating attribute mapping '%s'",
                         attribute_name)
            try:
                errors = self.validate_attribute_mapping(service, node_type, 
                                                        attribute_name, attribute_mapping)
                if errors:
                    logger.debug("Substitution mappings: invalid attribute mapping '%s'",
                                 attribute_name)
                    validation_errors[str(attribute_name)] = errors
            except Exception as e:
                logger.debug("Substitution mappings: error validating attribute mappings: '%s'",
                             str(e))
                validation_errors[attribute_name] = "validator error ({0})".format(str(e))

        # Everything OK
        return validation_errors


    def validate_attribute_mapping(self, service: "Any", node_type: "Any", attribute_name: str, attribute_mapping: "Any") -> "Any":
        """Check if substitution mappings have valid attribute
        mappings within the specified service

        Args: 
          service(ToscaServiceTemplate): service template within
            which to validate the instance
          node_type(ToscaNodeType): type of the node for which this
            service is a substitution
          attribute_name(str): name of the attribute in the node type
          attribute_mappings([]): attribute mapping to validate
        """

        # Make sure the node type declares this attribute
        try:
            attribute_declaration = node_type.get_attribute_declaration(attribute_name)
        except KeyError:
            # Could be automatically-reflected property declaration
            try:
                attribute_declaration = node_type.get_property_declaration(attribute_name)
            except KeyError:
                # Not a property declaration either
                logger.debug("Substitution mappings: '%s' does not have attribute '%s'",
                             node_type.name, attribute_name)
                return 'not previously defined'

        # Found the attribute declaration. Validate the
        # output-to-attribute mapping
        try:
            return self.validate_output_to_attribute_mapping(service,
                                                             attribute_declaration,
                                                             attribute_mapping)
        except Exception as e:
            return "validator error ({0})".format(str(e))
        
        # Everything OK
        return {}


    def validate_output_to_attribute_mapping(self, service: "Any", attribute_declaration: "Any", output_name: str) -> "Any":
        """Check if substitution mappings have a valid output-to-attribute
        mapping within the specified service

        Args: 

          service(ToscaServiceTemplate): service template within
            which to validate the instance
          attribute_declaration (ToscaAttributeDeclaration): attribute
            declaration in the node type
          output_name(str): name of the output to map
        """

        # Find the output to map
        try:
            output_declaration = service.outputs[output_name]
        except KeyError:
            return "output '{0}' not found".format(str(output_name))
        except Exception as e:
            return "'{0}' is not a valid ouput name".format(str(output_name))

        # Make sure types match
        if not output_declaration.has_type(attribute_declaration.type_entity):
            logger.debug("Attribute mapping '%s': output '%s' type '%s' not compatible with attribute type '%s'",
                         output_declaration.name, output_declaration.type, attribute_declaration.type)
            return "output type '{0}' incompatible with attribute type '{1}'".format(output_declaration.type, 
                                                                                     attribute_declaration.type)
        return {}
            

    def validate_property_mappings(self, service: "Any", node_type: "Any", substitution_mappings: dict) -> dict:
        """Check if substitution mappings have valid property
        mappings within the specified service

        Args: 
          service(ToscaServiceTemplate): service within which to validate
            the instance
          node_type(ToscaNodeType): type of the node for which this
            service is a substitution
          substitution_mappings(dict):
            substitution mappings to validate
        """

        validation_errors = {}

        # Do the substitution mappings include property mappings?
        try:
            properties = substitution_mappings.properties

            # Validate each property mapping
            for property_name, property_mapping in properties.items():
                logger.debug("Substitution mappings: validating property mapping '%s'",
                             property_name)
                try:
                    errors = self.validate_property_mapping(service, node_type,
                                                            property_name, 
                                                            property_mapping)
                    if errors:
                        logger.debug("Substitution mappings: invalid property mapping '%s'",
                                     property_name)
                        validation_errors[str(property_name)] = errors
                except Exception as e:
                    logger.debug("Substitution mappings: error validating property mappings: '%s'",
                                 e)
                    validation_errors[str(property_name)] = "validator error ({0})".format(e)

        except (AttributeError, KeyError):
            # No property mappings to validate
            properties = {}
            logger.debug("Substitution mappings: no property mappings specified")
            pass

        # We still need to make sure all required inputs have
        # mappings. First, make sure our service defines inputs.
        try:
            inputs = service.inputs
        except AttributeError:
            # No inputs. We're all done.
            return validation_errors

        # Next, create a list of all properly-mapped inputs.
        mapped_inputs = []
        for property_name, property_mapping in properties.items():
            try:
                input_name = property_mapping
                mapped_inputs.append(input_name)
            except ValueError:
                pass

        # Finally, make sure all required inputs have mappings
        for input_name, input in inputs.items():
            if input.is_required() and not input_name in mapped_inputs:
                # Required input not mapped. An input that gives its own
                # value, or has a default, needs no mapping.
                if not (hasattr(input, 'value') or hasattr(input, 'default')):
                    # validation_errors[input_name] = 'required input not mapped'
                    logger.warning("Required input '%s' not mapped", input_name)

        # Everything OK
        return validation_errors


    def validate_property_mapping(self, service: "Any", node_type: "Any", property_name: str, property_mapping: "Any") -> "Any":
        """Check if substitution mappings have valid property
        mapping within the specified service

        Args: 
          service(ToscaServiceTemplate): service within which to validate
            the instance
          property_declaration (ToscaPropertyDeclaration): property
            declaration in the node type
          property_mapping: property mapping to validate
        """

        # Make sure the node type declares this property
        try:
            property_declaration = node_type.get_property_declaration(property_name)
        except KeyError:
            logger.debug("Substitution mappings: '%s' does not have property '%s'",
                         node_type.name, property_name)
            return 'not previously defined'

        # Validate the mapping
        try:
            return self.validate_property_to_input_mapping(service,
                                                           property_declaration,
                                                           property_mapping)
        except ValueError as e:
            # Not a property-to-input mapping. Property-to-property
            # mapping perhaps?
            if isinstance(property_mapping, list) and \
               not isinstance(property_mapping, str):
                return "deprecated 'property-to-property' mapping"

            # Not a property-to-property mapping. Must be a
            # property-to-fixed-value mapping.
            return self.validate_property_to_value_mapping(service,
                                                           property_declaration,
                                                           property_mapping)
                
        # Everything OK
        return {}


    def validate_property_to_input_mapping(self, service: "Any", property_declaration: "Any", input_name: str) -> Optional[str]:
        """Check if substitution mappings have valid property to input
        mapping within the specified service

        Args: 
          service(ToscaServiceTemplate): service within which to validate
            the instance
          property_declaration (ToscaPropertyDeclaration): property
            declaration in the node type
        """
        try:
            input_declaration = service.inputs[input_name]
        except KeyError:
            return "undefined input '{0}'".format(input_name)
        except Exception as e:
            logger.error(f"Unable to find mapped input {str(input_name)}")
            return f"invalid input '{str(input_name)}'"
        
        # Make sure types match
        if not property_declaration.has_type(input_declaration.type_entity):
            logger.debug("Property mapping '%s': property '%s' type '%s' not compatible with input type '%s'",
                         property_declaration.name, property_declaration.type, input_declaration.type)
            return "property type '{0}' incompatible with input type '{1}'".format(property_declaration.type, 
                                                                                 input_declaration.type)

        # Warn when an optional property feeds a required input. Validation sees only
        # the TYPE, never the values a service template supplies at deployment time, so
        # it cannot tell whether this mapping will be satisfied -- only that it need
        # not be.
        #
        # The condition is not necessarily a defect: a substituting template can make
        # itself inapplicable to nodes that lack the value by testing for it in its
        # substitution_filter, in which case the mapping cannot run without one. That
        # guarantee is expressed with functions the PROFILES define, which validation
        # deliberately knows nothing about, so the warning stands either way.
        #
        # The two ways out -- exclude such nodes in the substitution_filter, or make
        # the input optional and handle its absence -- are recorded here rather than
        # in the message. A template that trips this trips it once per mapping, and
        # remediation prose repeated on every line buries the ones that matter.
        if input_declaration.is_required() and not property_declaration.is_required():
            logger.warning("optional property '%s' maps to required input '%s'",
                           property_declaration.name, input_name)

        # All done
        return None


    def validate_property_to_value_mapping(self, service: "Any", property_declaration: "Any", value: "Any") -> str:
        """Check if substitution mappings have valid property to input
        mapping within the specified service

        Args: 
          service(ToscaServiceTemplate): service within which to validate
            the instance
          property_declaration (ToscaPropertyDeclaration): property
            declaration in the node type
        """
        return "deprecated 'property-to-value' mapping"


    def validate_capability_mappings(self, service: "Any", node_type: "Any", substitution_mappings: dict) -> dict:
        """Check if substitution mappings have valid capability
        mappings within the specified service

        Args: 
          service(ToscaServiceTemplate): service within which to validate
            the instance
          node_type(ToscaNodeType): type of the node for which this
            service is a substitution
          substitution_mappings(dict):
            substitution mappings to validate
        """

        validation_errors = {}

        # Do the substitution mappings include capability mappings?
        try:
            capabilities = substitution_mappings.capabilities
        except (AttributeError, KeyError):
            # No type
            logger.debug("Substitution mappings: no capability mappings specified")
            return validation_errors

        # Validate each capability mapping
        for capability_name, capability_mapping in capabilities.items():
            logger.debug("Substitution mappings: validating capability mapping '%s'",
                         capability_name)
            try:
                errors = self.validate_capability_mapping(service, node_type, 
                                                          capability_name, capability_mapping)
                if errors:
                    logger.debug("Substitution mappings: invalid capability mapping '%s'",
                                 capability_name)
                    validation_errors[capability_name] = errors
            except Exception as e:
                logger.debug("Substitution mappings: error validating capability mappings: '%s'",
                             e)
                validation_errors[capability_name] = "validator error ({0})".format(e)

        # Everything OK
        return validation_errors


    def validate_capability_mapping(self, service: "Any", node_type: "Any", capability_name: str, capability_mapping: "Any") -> "Any":
        """Check if substitution mappings have valid capability
        mappings within the specified service

        Args: 
          service(ToscaServiceTemplate): service within which to validate
            the instance
          node_type(ToscaNodeType): type of the node for which this
            service is a substitution
          capability_name(str): name of the capability in the node type
          capability_mappings([]): capability mapping to validate
        """

        # Make sure the node type declares this capability
        try:
            capability_declaration = node_type.get_capability_declaration(capability_name)
        except KeyError:
            logger.debug("Substitution mappings: '%s' does not have capability '%s'",
                         node_type.name, capability_name)
            return 'not previously defined'

        # Parse the mapping
        try:
            [node, capability] = capability_mapping
        except ValueError as e:
            logger.error("Substitution mappings: Invalid capability mapping '%s'",
                         node_type.name, capability_name)
            return 'invalid mapping'
        
        # Are node and capability valid in this service?
        try:
            node_template = service.node_templates[node]
        except KeyError:
            logger.debug("Capability mapping '%s': service does not have node '%s'",
                         capability_name, node)
            return "the substituting service has no node named '{0}'".format(node)

        try:
            node_capability = node_template.declaration.get_capability_declaration(capability)
        except KeyError:
            logger.debug("Capability mapping '%s': node '%s' does not have capability '%s'",
                         capability_name, node, capability)
            return "node '{0}' has no capability named '{1}'".format(node, capability)

        # Everything OK
        logger.debug("Capability mapping '%s': found capability '%s' in node '%s'",
                     capability_name, node_capability.name, node_template.name)
        return {}


    def validate_requirement_mappings(self, service: "Any", node_type: "Any", substitution_mappings: dict) -> dict:
        """Check if substitution mappings have valid requirement
        mappings within the specified service

        Args: 
          service(ToscaServiceTemplate): service within which to validate
            the requirement mappings
          node_type(ToscaNodeType): type of the node for which this
            service is a substitution
          substitution_mappings(dict): substitution mappings that
            contain the requirement mappings to validate
        """

        validation_errors = {}

        # Do the substitution mappings include requirement mappings?
        try:
            requirements = substitution_mappings.requirements
        except (AttributeError, KeyError):
            # No requirement mappings
            logger.debug("Substitution mappings: no requirement mappings specified")
            return validation_errors

        # Make sure the list contains valid requirement
        # mappings. While we're at it, group requirement mappings for
        # requirements with the same name together (while maintaining
        # the order in which these mappings occur).
        count = 0
        grouped_mappings = dict()
        for mapping in requirements:
            try:
                # A mapping is a single-key dictionary.
                [(requirement, requirement_mapping)] = list(mapping.items())
                # Each requirement can 
                # 1. Map onto a list of requirement mappings, where
                #    each requirement mapping is itself a list with
                #    two elements (the mapped node and mapped
                #    requirement).
                # 2. Map onto a single selectable node.
                if not isinstance(requirement_mapping, list):
                    # Not a list. Must be a mapping to a selectable
                    # node.
                    if not isinstance(requirement_mapping, str):
                        error = f"'{str(mapping)}' is not a valid requirement mapping"
                        logger.error(error)
                        validation_errors[str(count)] = error
                    else:
                        # Turn into a list for consistency.
                        mapping[requirement] = [requirement_mapping]
                else:
                    # The TOSCA grammar allows for simple one-to-one
                    # mappings that don't use list syntax. Convert
                    # such a single mapping into a list with one entry.
                    if not self.is_target_sequence(service, requirement_mapping):
                        mapping[requirement] = [requirement_mapping]
            except (AttributeError, ValueError):
                error = f"'{str(mapping)}' is not a valid requirement mapping"
                logger.error(error)
                validation_errors[str(count)] = error

            # Group this mapping with other mappings with the same
            # name so we can count them later. First, parse
            # requirements that have a name and a count.
            # Only a [name, count] pair is unpacked. A name is a string, and
            # unpacking one would split it into its characters, so that a
            # two-letter name such as 'to' read as a name and a count.
            if isinstance(requirement, (list, tuple)) and len(requirement) == 2:
                [requirement_name, requirement_count] = requirement
            else:
                requirement_name = requirement
                requirement_count = 1
            if not isinstance(requirement_name, str) or not \
               (isinstance(requirement_count, int) or requirement_count == 'UNBOUNDED'):
                error = f"'{str(mapping)}' is not a valid requirement mapping"
                logger.error(error)
                validation_errors[str(count)] = error
            else:
                try:
                    grouped_mappings[requirement_name].append(
                        [mapping[requirement], requirement_count])
                except KeyError:
                    # We don't have a mapping for this requirement name
                    # yet.
                    grouped_mappings[requirement_name] = list()
                    grouped_mappings[requirement_name].append(
                        [mapping[requirement], requirement_count])
                count += 1

        # Don't proceed if there are errors
        if validation_errors: return validation_errors

        # Validate each group of requirement mappings
        for requirement, requirement_mappings in grouped_mappings.items():
            logger.debug("Substitution mappings: validating requirement mapping '%s'",
                         requirement)
            try:
                errors = self.validate_requirement_mapping_group(
                    service, node_type, requirement, requirement_mappings)
                if errors:
                    logger.debug("Substitution mappings: invalid requirement mapping '%s'",
                                 requirement)
                    validation_errors[str(requirement)] = errors
            except Exception as e:
                logger.error("Substitution mappings: error validating requirement mappings: '%s'",
                             e)
                validation_errors[requirement] = "validator error ({0})".format(e)

        # Ungroup
        requirements = list()
        for requirement, mappings in grouped_mappings.items():
            for mapping in mappings:
                requirements.append({(requirement, mapping[1]): mapping[0]})
        # Guarded because the accessor raises when nothing is stored, and
        # because there is nothing to write when no mappings were built.
        if requirements:
            substitution_mappings.requirements = requirements

            # The loop above normalized these mappings in place before rebuilding
            # them, so the rebuilt value can compare equal to the one already held
            # and the write would be skipped. A path-form key -- '[service, 2]',
            # which ruamel parses to a tuple subclass -- is the case that shows it.
            # Flag the change explicitly, as policy triggers and workflow steps do.
            substitution_mappings.requirements.changed()

        # Everything OK
        return validation_errors


    def warn_unmapped_containment(self, node_type: "Any", substitution_mappings: "Any") -> None:
        """Warn about each containment requirement of the substituted node
        type that these mappings do not map.

        A containment to a substituted source whose requirement is mapped
        reaches the inner nodes that run on its target. One that is not
        mapped applies to the substituted node as a whole: its target's
        failure fails the substituted node, and its recovery rebuilds the
        whole substituting service.

        The kind read is the requirement definition's. A node template
        that assigns a stricter relationship type, making a dependency a
        containment, is not known when its realization is onboarded.

        Args:
          node_type(ToscaNodeType): type of the node for which this
            service is a substitution
          substitution_mappings(ToscaSubstitutionMappings): the
            validated substitution mappings
        """
        try:
            mappings = substitution_mappings.requirements or []
        except (AttributeError, KeyError):
            mappings = []
        mapped = set()
        for mapping in mappings:
            for requirement in mapping:
                # A key is a requirement name, or a (name, count) pair
                mapped.add(requirement if isinstance(requirement, str) else requirement[0])

        for requirement_declaration in node_type.get_requirement_declarations():
            if requirement_declaration.name in mapped:
                continue
            try:
                kind = requirement_declaration.type_entity.get_kind()
            except (AttributeError, te.TypeNotFound):
                continue
            if kind == 'CONTAINMENT':
                logger.warning("substituting for '%s': containment requirement '%s' is not "
                               "mapped; a failure of its target fails the whole substituted node",
                               node_type.name, requirement_declaration.name)


    def is_target_sequence(self, service: "Any", value: list) -> bool:
        """Is this requirement mapping's value a SEQUENCE of targets, rather
        than a single target written without list syntax?

        The two are told apart by resolving the names against the substituting
        service, not by the shape of the list, because the shapes overlap: a
        '[node, requirement]' pair and a two-name selectable sequence are the
        same YAML, and a list of three names is either three selectable nodes
        or a path someone wrote in the wrong grammar.

        Resolving decides it, and decides it the way the author meant, because
        the readings are not equally likely. Mapping onto a list of selectable
        nodes is rare; a path is what people write. So a list of names is a
        sequence only when every name really does name a select-only node
        template, and anything else is read as an attempted path and reported
        as one.

        Args:
          service(ToscaServiceTemplate): the substituting service template
          value(list): the value of one requirement mapping entry
        Returns:
          True if 'value' is a list of targets, False if it is one target
        """
        if not value:
            # No targets at all. Not a sequence; the dispatch reports it.
            return False

        # A nested list can only be a '[node, requirement]' pair, so its
        # presence settles this without any lookup: the value is a sequence
        # whose string elements name selectable nodes and whose list elements
        # are pairs. This is the mixed form 15.5 admits, in either order.
        if any(isinstance(element, list) for element in value):
            return True

        if not all(isinstance(element, str) for element in value):
            return False

        if len(value) == 2 and self.names_requirement_pair(service, value):
            # The one length at which both readings are well-formed. The pair
            # reading wins wherever it resolves, which is what implementations
            # do today; only when it does not, and both names are selectable,
            # is this a two-name sequence. See oasis-tcs/tosca-specs#363, which
            # asks the TC to settle the collision rather than leave it to each
            # implementation.
            return False

        return all(self.names_selectable_node(service, element) for element in value)


    def names_selectable_node(self, service: "Any", name: "Any") -> bool:
        """Does 'name' name a select-only node template in this service?

        Args:
          service(ToscaServiceTemplate): the substituting service template
          name: the candidate name
        """
        if not isinstance(name, str):
            return False
        try:
            node_template = service.node_templates[name]
        except (KeyError, TypeError):
            return False
        return node_template.directives == ['select']


    def names_requirement_pair(self, service: "Any", value: "Any") -> bool:
        """Does 'value' resolve as a '[node, requirement]' pair in this service?

        Args:
          service(ToscaServiceTemplate): the substituting service template
          value: the candidate pair
        """
        if not (isinstance(value, list) and len(value) == 2
                and all(isinstance(element, str) for element in value)):
            return False
        [node, requirement] = value
        try:
            node_template = service.node_templates[node]
            node_template.declaration.get_requirement_declaration(requirement)
        except Exception:
            return False
        return True


    def validate_requirement_mapping_group(self, service: "Any", node_type: "Any", requirement_name: str, requirement_mappings: list) -> "Any":
        """Check if a group of mappings from a named requirement is valid
        within the specified service

        Args: 
          service(ToscaServiceTemplate): service within which to validate
            the group of requirement mappings
          node_type(ToscaNodeType): type of the node for which this
            service is a substitution
          requirement_name(str): name of the requirement to map in the
            substituted node type
          requirement_mappings([]): list of requirement mappings to validate
        """
        # Make sure the node type declares the named requirement
        try:
            requirement_declaration = node_type.get_requirement_declaration(requirement_name)
        except KeyError:
            logger.debug("Substitution mappings: '%s' does not have requirement '%s'",
                         node_type.name, requirement_name)
            
            return f"no requirement '{requirement_name}' defined in '{node_type.name}'"

        # Validate each requirement mapping
        mapped_count = 0
        unbounded_set = False
        outer_count = 0
        validation_errors = dict()
        for requirement_mapping in requirement_mappings:
            inner_count = 0
            mapping_errors = dict()
            # First, check mappings
            for mapping in requirement_mapping[0]:
                try:
                    errors = self.validate_requirement_mapping(
                        service, requirement_declaration, mapping)
                    if errors:
                        logger.debug("Substitution mappings: invalid requirement mapping '%s'",
                                     requirement_name)
                        mapping_errors[str(inner_count)] = errors
                except Exception as e:
                    logger.error("Substitution mappings: error validating requirement mappings: '%s'",
                                 str(e))
                    mapping_errors[str(inner_count)] = f"validator error ({str(e)})"
                inner_count += 1
            if mapping_errors:
                validation_errors[str(outer_count)] = mapping_errors
            else:
                # If no errors, add to total mapping count
                if unbounded_set:
                    error = 'not allowed after UNBOUNDED mapping' 
                    validation_errors[str(outer_count)] = error
                else:
                    if requirement_mapping[1] == 'UNBOUNDED':
                        unbounded_set = True
                    else:
                        mapped_count = mapped_count + requirement_mapping[1]
            outer_count += 1

        # Stop here if any individual mapping in this group was rejected. The
        # checks below are arithmetic over the group as a whole -- how many
        # assignments it consumes, how many it needs -- and both return a
        # single string, which would replace the per-entry errors collected
        # above. An entry the loop already refused is also an entry whose
        # contribution to those totals is meaningless.
        if validation_errors:
            return validation_errors

        # Make sure we're not mapping more instances than
        # allowed. This is independent of whether requirements are
        # mandatory or not.
        supported_instances = requirement_declaration.count_range[1]
        if not supported_instances == 'UNBOUNDED' and \
           (mapped_count != 'UNBOUNDED' and mapped_count > supported_instances):
            logger.debug("Requirement %s supports only %d instances but %d mappings specified",
                         requirement_name, supported_instances, len(requirement_mappings))
            return f"{mapped_count} mappings specified but only {supported_instances} allowed"

        # §15.5.4 rule 2: the assignments this group needs must not exceed
        # the number the substituted node guarantees. Reported rather than
        # refused -- see the method for why the comparison it can make here is
        # weaker than the one the rule wants.
        error = self.validate_mandatory_mapping_count(
            service, requirement_declaration, requirement_name, requirement_mappings)
        if error:
            logger.warning("substituting for '%s': requirement '%s' may not be fulfilled: %s",
                           node_type.name, requirement_name, error)

        # §15.5.4: what a target receives must fit the count range it declares.
        error = self.validate_target_mapping_counts(
            service, requirement_declaration, requirement_name, requirement_mappings)
        if error:
            return error

        # All done
        return validation_errors

    
    def validate_mandatory_mapping_count(self, service: "Any", requirement_declaration: "Any", requirement_name: str, requirement_mappings: list) -> "Any":
        """Check TOSCA 2.0 §15.5.4 rule 2 for one group of requirement mappings.

        The rule: the number of requirements mapped onto MANDATORY requirements
        in the substituting template must not exceed the lower bound of the
        substituted requirement's 'count_range'. §15.5.4 states its own reason
        at example s147 -- a template needing three service requirements
        "cannot be guaranteed, since the count_range ... specifies a lower bound
        of one".

        So the quantity to compare is how many assignments the realization
        NEEDS, and the arithmetic follows from what an entry does:

        - an entry consumes the number of assignments its key states, one when
          the key states none;
        - every target in that entry receives each consumed assignment, which
          is why fanning out to several targets costs no more assignments than
          fanning out to one. §15.5.2's s142 maps a single assignment onto two
          mandatory targets and is valid, so counting targets rather than
          entries would reject a published example;
        - an entry with no mandatory target needs nothing, since an optional
          target is satisfied by receiving nothing.

        An UNBOUNDED entry consumes however many remain, which cannot be known
        here, so it is left out of the total rather than guessed at. That makes
        this check conservative: it reports what is certainly too many, never
        what merely might be.

        **Reported as a warning, not an error.** The lower bound is a floor on
        what every node of the type supplies, so a realization written for the
        nodes that supply more than the floor trips this rule while being
        correct for every node it is ever chosen for. The comparison the rule
        is really after is against the node ACTUALLY being substituted, whose
        assignments are known at substitution and not here. Until that check
        exists, refusing on the type's numbers would refuse correct
        realizations, so this reports and lets validation proceed; the rule
        belongs where a node is substituted, in the application that does it.

        Args:
          service(ToscaServiceTemplate): the substituting service template
          requirement_declaration(ToscaRequirementDeclaration): declaration of
            the substituted requirement being mapped
          requirement_name(str): name of that requirement
          requirement_mappings([]): the [mappings, count] pairs for this name
        Returns:
          An error string, or None
        """
        try:
            guaranteed = requirement_declaration.count_range[0]
        except (TypeError, IndexError, AttributeError):
            return None

        needed = 0
        mandatory_targets = list()
        for mappings, count in requirement_mappings:
            if count == 'UNBOUNDED' or not isinstance(count, int):
                continue
            # Which targets are mandatory is one question with one answer,
            # shared with the substitution-time form of this rule.
            entry_targets = sm.mandatory_mapping_targets(service.node_templates, mappings)

            if entry_targets:
                # This entry needs assignments. One entry needs them once,
                # however many targets share them -- the count is per entry,
                # while the names are all of them, since a realization is
                # recognised in a log by the node templates it maps onto.
                needed += count
                mandatory_targets.extend(entry_targets)

        if needed > guaranteed:
            # Name the targets: several realizations of one abstract type reach
            # this with the same requirement name, and the node templates are
            # what tell them apart in a log.
            error = ("{0} assignments are needed to fill the mandatory requirements mapped from "
                     "'{1}' ({2}), but the substituted node type guarantees only {3}".format(
                         needed, requirement_name, ', '.join(mandatory_targets), guaranteed))
            logger.debug(error)
            return error
        return None

    def validate_target_mapping_counts(self, service: "Any", requirement_declaration: "Any", requirement_name: str, requirement_mappings: list) -> "Any":
        """Check that no target receives more relationships than it can hold.

        The mirror of rule 2. That one asks whether the substituted node
        guarantees enough assignments to fill the mandatory targets; this asks
        whether each target can hold what the mappings will send it. Both are
        decidable from declarations the validator already has, and neither
        needs a deployment.

        How many a target receives follows from the same reading of an entry:
        an entry consumes the number of assignments its key states, and every
        target in it receives each of them. A target named by several entries
        accumulates across them, which is how a requirement declared
        'count_range: [2, 2]' is legitimately filled by two separate entries.

        An UNBOUNDED entry consumes "all the remaining assignments", which is
        bounded when the substituted requirement declares a finite upper bound:
        what remains is that bound less what the counted entries take. Where
        the substituted bound is itself UNBOUNDED the number cannot be known,
        and such an entry is left out.

        Only the upper bound is checked here. A target may also carry its own
        requirement assignment in the substituting template, which adds
        relationships this count does not see, so a total computed here can be
        lower than the real one but never higher -- safe for detecting too
        many, unsafe for detecting too few. Whether a mandatory target is
        filled at all is rule 2's question, asked from the supply side.

        Args:
          service(ToscaServiceTemplate): the substituting service template
          requirement_declaration(ToscaRequirementDeclaration): declaration of
            the substituted requirement being mapped
          requirement_name(str): name of that requirement
          requirement_mappings([]): the [mappings, count] pairs for this name
        Returns:
          An error string, or None
        """
        try:
            supported = requirement_declaration.count_range[1]
        except (TypeError, IndexError, AttributeError):
            return None

        # What an UNBOUNDED entry takes, when that can be established.
        counted = sum(count for mappings, count in requirement_mappings
                      if isinstance(count, int))
        remaining = None
        if supported != 'UNBOUNDED' and isinstance(supported, int):
            remaining = supported - counted
            if remaining < 0:
                # Rule 3 already reported this group; nothing to add.
                return None

        received = dict()
        for mappings, count in requirement_mappings:
            if isinstance(count, int):
                contribution = count
            elif remaining is not None:
                contribution = remaining
            else:
                continue
            for mapping in mappings:
                # Only a '[node, requirement]' target accumulates. A selectable
                # node names no requirement, and an INDEXED target sends each
                # assignment to a different representation, so what any one of
                # them receives is one rather than the entry's whole
                # contribution -- the arithmetic below does not describe it.
                if not sm.is_requirement_pair(mapping):
                    continue
                [node_name, target_requirement] = mapping
                key = (node_name, target_requirement)
                received[key] = received.get(key, 0) + contribution

        for (node_name, target_requirement), total in received.items():
            try:
                node_template = service.node_templates[node_name]
                target = node_template.declaration.get_requirement_declaration(
                    target_requirement)
                allowed = target.count_range[1]
            except Exception:
                # Unresolvable targets are reported by the per-mapping
                # validation; nothing to add here.
                continue
            if allowed != 'UNBOUNDED' and isinstance(allowed, int) and total > allowed:
                error = ("mappings from '{0}' would give '{1}' {2} relationships on requirement "
                         "'{3}', which allows at most {4}".format(
                             requirement_name, node_name, total, target_requirement, allowed))
                logger.error(error)
                return error
        return None

    def validate_requirement_mapping(self, service: "Any", requirement_declaration: "Any", requirement_mapping: "Any") -> "Any":
        """Check if a requirement mapping is valid within the specified
        service.

        Args: 
          service(ToscaServiceTemplate): service within which to validate
            the requirement mapping.
          requirement_declaration(ToscaRequirementDeclaration):
            declaration of the requirement to map in the substituted
            node type.
          requirement_mapping(list or str): requirement mapping to validate
        """
        # Three constructs are accepted here, and they are told apart BY KIND
        # rather than by whether unpacking one raises:
        #
        #   'node_name'                        onto a selectable node
        #   [node_name, requirement]           onto a requirement of a node
        #   [node_name, index, requirement]    onto one representation of a
        #                                      counted node template
        #
        # A bare string arrives as itself, either because it was written that
        # way or because 'is_target_sequence' resolved it out of a list of
        # selectable names. A single target that was written without list
        # syntax has been wrapped by the caller and arrives as the list.
        # Anything else is malformed, and saying so is the point. Dispatching
        # on a ValueError from the unpack sent every other arity into the
        # selectable-node branch, which then used the whole value as a
        # dictionary key -- so a three-element target was reported as
        # "unhashable type: 'CommentedSeq'" from inside the validator rather
        # than as a bad mapping.
        #
        # The two list forms are recognised by 'models/substitution_mappings',
        # which is what the substitution path asks as well, so what is accepted
        # here and what is acted on there cannot drift apart.
        if isinstance(requirement_mapping, str):
            return self.validate_requirement_to_node_mapping(
                service, requirement_declaration, requirement_mapping)

        if sm.is_requirement_pair(requirement_mapping):
            [node, requirement] = requirement_mapping
            return self.validate_requirement_to_requirement_mapping(
                service, requirement_declaration, node, requirement)

        # The index selects which representation this assignment binds to, so
        # that the assignments of one requirement are distributed across the
        # instances rather than piled onto a single node. It is evaluated at
        # substitution, against the relationship being mapped, not here.
        if sm.is_indexed_target(requirement_mapping):
            [node, index, requirement] = requirement_mapping
            error = self.validate_mapping_target_index(
                service, requirement_declaration, requirement_mapping)
            if error:
                return error
            return self.validate_requirement_to_requirement_mapping(
                service, requirement_declaration, node, requirement)

        # Neither form. A list of names that reaches here was already put to
        # the substituting service by 'is_target_sequence' and did not come
        # back as a sequence of selectable nodes, so report against whichever
        # reading the author was more likely attempting.
        return self.report_unclassifiable_target(
            service, requirement_declaration, requirement_mapping)


    def validate_mapping_target_index(self, service: "Any", requirement_declaration: "Any", target: list) -> "Any":
        """Check the index in a '[node, index, requirement]' mapping target.

        The position holds an index, so it is validated as an integer, the same
        way 'validate/relationship_template.py' validates the index in a
        '[node, index]' requirement assignment. A function is validated rather
        than evaluated: an index expression has no answer until there is a
        relationship to ask.

        **What is deliberately NOT checked is which function was written.** The
        index is evaluated against the substituted node's relationship, and
        '$relationship_index' is the one that answers "which assignment of the
        substituted requirement is this" -- but declaring that the only
        admissible function would put the validator in the business of ruling
        on the language it is parsing, and would refuse a function a profile
        defines for itself. The type says an integer belongs here; the language
        says which expressions yield one; the context says what each can
        answer. Where the result is not the index the author had in mind, the
        model catches it: several assignments resolving to the same
        representation exceed that requirement's 'count_range' and
        the application substituting the node refuses them by name.

        **The validated value is written back into the target.** A function
        validated here comes back RESOLVED -- bound to its declaration -- and
        only a resolved function can be evaluated later without a context to
        look the declaration up in. Storing the raw text instead leaves
        substitution to fail with "no context provided" the first time it
        evaluates the index. 'validate/relationship_template.py' writes the
        same value back for the same reason, and the rebuild at the end of
        'validate_requirement_mappings' persists this one.

        Args:
          service(ToscaServiceTemplate): the substituting service template
          requirement_declaration(ToscaRequirementDeclaration): declaration of
            the substituted requirement being mapped
          target([node, index, requirement]): the target whose index to check,
            rewritten in place with the validated index
        Returns:
          An error string, or None
        """
        from tosca_core.models import builtin_types
        index = target[1]
        integer_type = builtin_types.get('integer')
        declaration = integer_type.create_declaration(name='target_node_index')
        try:
            index = declaration.validate_value(service, index)
        except te.ValidationError as e:
            return e.errors
        except Exception as e:
            return ("'{0}' is not a valid index for requirement mapping '{1}': {2}".format(
                str(index), requirement_declaration.name, str(e)))

        # A negative index addresses nothing. This is a property of an index
        # rather than a ruling about the language, so it belongs here; a
        # function that yields a negative value fails at substitution instead.
        if isinstance(index, int) and not isinstance(index, bool) and index < 0:
            return ("{0} is not a valid index for requirement mapping '{1}': an index is a "
                    "non-negative integer".format(index, requirement_declaration.name))

        target[1] = index
        return None


    def report_unclassifiable_target(self, service: "Any", requirement_declaration: "Any", target: "Any") -> str:
        """Report a requirement mapping target that is neither a selectable
        node name nor a '[node, requirement]' pair.

        Which reading to lead with follows from what resolved. A list none of
        whose names is a selectable node template was almost certainly meant
        as a path -- that is the form people write, and the selectable-node
        list is rare -- so the message states the path grammar and explains
        the other reading in passing. Where SOME names are selectable the
        author was writing a list of them and one name is wrong, and being
        told to write a two-element pair would be no help at all, so the
        message names what failed instead.

        Args:
          service(ToscaServiceTemplate): the substituting service template
          requirement_declaration(ToscaRequirementDeclaration): declaration of
            the substituted requirement being mapped
          target: the target that could not be classified
        Returns:
          An error string
        """
        names = [element for element in target
                 if isinstance(element, str)] if isinstance(target, list) else []
        unresolved = [name for name in names
                      if not self.names_selectable_node(service, name)]

        if names and len(unresolved) < len(names):
            error = ("'{0}' is not a valid mapping for requirement '{1}': mapping onto "
                     "selectable nodes needs every name to be a node template carrying "
                     "'directives: [select]', and {2} {3} not".format(
                         str(target), requirement_declaration.name,
                         self.quote_names(unresolved),
                         'is' if len(unresolved) == 1 else 'are'))
        elif names:
            error = ("'{0}' is not a valid mapping for requirement '{1}': expected "
                     "'[<node template>, <requirement>]'. (A list of names can instead map "
                     "onto selectable nodes, but {2} {3} not node templates carrying "
                     "'directives: [select]' in this service.)".format(
                         str(target), requirement_declaration.name,
                         self.quote_names(unresolved),
                         'is' if len(unresolved) == 1 else 'are'))
        else:
            error = ("'{0}' is not a valid mapping for requirement '{1}': expected the name "
                     "of a selectable node, or a two-element '[node, requirement]' list of "
                     "names".format(str(target), requirement_declaration.name))
        logger.error(error)
        return error


    def quote_names(self, names: list) -> str:
        """Render names for a message: 'a', 'b' and 'c'.

        Args:
          names([]): the names to render
        """
        quoted = ["'{0}'".format(name) for name in names]
        if len(quoted) < 2:
            return ''.join(quoted)
        return '{0} and {1}'.format(', '.join(quoted[:-1]), quoted[-1])
        

    def validate_requirement_to_requirement_mapping(self, service: "Any", requirement_declaration: "Any", node: str, requirement: str) -> "Any":
        """Check if a requirement to requirement mapping is valid within the
        specified service.

        Args: 
          service(ToscaServiceTemplate): service within which to validate
            the instance
          requirement_declaration(ToscaRequirementDeclaration):
            declaration of the requirement to map in the substituted
            node type.
          node: name of the node in the subsituting service that has
            the requirement onto which to map.
          requirement: name of the requirement onto which to map
        """
        # Are node and requirement valid in this service?
        try:
            node_template = service.node_templates[node]
        except KeyError:
            logger.debug("Requirement mapping '%s': service does not have node '%s'",
                         requirement_declaration.name, node)
            return "the substituting service has no node named '{0}'".format(node)

        # A selectable node is found in inventory rather than created here, so
        # this service never instantiates it and it has no requirement of its
        # own for a mapping to fill. The mirror of the check in
        # 'validate_requirement_to_node_mapping', which requires a bare-name
        # target to BE select-only: a [node, requirement] target must not be.
        #
        # Without this the mapping is accepted and fails during mapping, where
        # 'map_requirement_to_requirement' looks the node up among the service's
        # instances, does not find it, and reports the KeyError's text -- a
        # quoted node name and nothing else.
        if node_template.directives == ['select']:
            error = ("node '{0}' is select-only, so this service does not instantiate it and it "
                     "has no requirement '{1}' to map onto. Map onto the node itself instead, as "
                     "'{2}: {0}'".format(node, requirement, requirement_declaration.name))
            logger.error(error)
            return error

        # Make sure requirement exists
        try:
            node_requirement = node_template.declaration.get_requirement_declaration(requirement)
        except KeyError:
            logger.debug("Requirement mapping '%s': node '%s' does not have requirement '%s'",
                         requirement_declaration.name, node, requirement)
            return "node '{0}' has no requirement named '{1}'".format(node, requirement)

        # §15.5.4 rule 1: "Requirements from a substituted node can only be
        # mapped onto dangling requirements in the substituting template."
        #
        # A requirement the substituting template has already assigned has its
        # target chosen. Mapping onto it as well makes the substituted node's
        # target compete with that one for a requirement that may admit a
        # single relationship, and which of them wins is not something either
        # template states.
        #
        # Only the requirement NAMED by this mapping is examined: a node may
        # assign its other requirements freely. Declaring none is the ordinary
        # case and is what makes the requirement dangling -- a mandatory one is
        # synthesized without a target, an optional one is created on demand.
        # So the error is raised only where templates for this name exist AND
        # every one of them names a target, meaning there is nothing left for
        # the mapping to fill.
        assigned = []
        dangling = 0
        for relationship_template in node_template.requirements:
            if relationship_template.name != requirement:
                continue
            try:
                target = relationship_template.target_node
            except (AttributeError, KeyError):
                # No target named, or one that does not resolve. The second is
                # reported elsewhere; treating it as dangling here keeps this
                # check from claiming a second, wrong reason for it.
                dangling += 1
                continue
            assigned.append(getattr(target, 'name', str(target)))
        if assigned and not dangling:
            error = ("node '{0}' already assigns requirement '{1}' to '{2}', so it has no dangling "
                     "requirement for this mapping to fill".format(
                         node, requirement, "', '".join(assigned)))
            logger.error(error)
            return error

        # Type compatibility is NOT checked here, and is not a gap. TOSCA 2.0
        # requires it of property mappings (§15.2) and attribute mappings
        # (§15.3) and says nothing of the kind for requirement mappings (§15.5)
        # or capability mappings (§15.4). Nor could it be checked here: a
        # mapping names a REQUIREMENT, and which capability satisfies it is
        # found by searching the target node for one of a compatible type once
        # a target exists -- 'ToscaRelationship.set_target'.

        # Everything OK
        logger.debug("Requirement mapping '%s': found requirement '%s' in node '%s'",
                     requirement_declaration.name, node_requirement.name, node_template.name)

        return {}


    def validate_requirement_to_node_mapping(self, service: "Any", requirement_declaration: "Any", node: str) -> "Any":
        """Check if a requirement to selectable node mapping is valid within
        the specified service.

        Args: 
          service(ToscaServiceTemplate): service within which to validate
            the instance
          requirement_declaration(ToscaRequirementDeclaration):
            declaration of the requirement to map in the substituted
            node type.
          node: name of the selectable node in the subsituting service
            onto which to map.
        """
        # Is node valid in this service?
        try:
            node_template = service.node_templates[node]
        except KeyError:
            logger.debug("Requirement mapping '%s': service does not have selectable node '%s'",
                         requirement_declaration.name, node)
            return "the substituting service has no node named '{0}'".format(node)

        # Is this a select-only node?
        if node_template.directives != ['select']:
            return f"node '{node}' is not select-only"

        # Make sure the selectable node has a capability with a type
        # that matches
        capability_type = requirement_declaration.target_capability_type
        node_type = node_template.declaration.type_entity
        capability_declarations = node_type.get_capability_declarations()
        for capability, capability_declaration in capability_declarations.items():
            if capability_declaration.has_type(capability_type):
                # Found a capability with a matching type
                return {}

        # No matching capability type found
        return f"node '{node}' has no capability of type '{capability_type.name}'"
            
    
    def validate_interface_mappings(self, service: "Any", node_type: "Any", substitution_mappings: dict) -> dict:
        """Check if substitution mappings have valid interface
        mappings within the specified service

        Args: 
          service(ToscaServiceTemplate): service within which to validate
            the instance
          node_type(ToscaNodeType): type of the node for which this
            service is a substitution
          substitution_mappings(dict):
            substitution mappings to validate
        """

        validation_errors = {}

        # Do the substitution mappings reference a type?
        try:
            interfaces = substitution_mappings.interfaces
        except (AttributeError, KeyError):
            # No type
            logger.debug("Substitution mappings: no interface mappings specified")
            return validation_errors

        # Validate each interface mapping
        for interface_name, interface_mapping in interfaces.items():
            logger.debug("Substitution mappings: validating interface mapping '%s'",
                         interface_name)
            try:
                errors = self.validate_interface_mapping(service, node_type, 
                                                        interface_name, interface_mapping)
                if errors:
                    logger.debug("Substitution mappings: invalid interface mapping '%s'",
                                 interface_name)
                    validation_errors[interface_name] = errors
            except Exception as e:
                logger.debug("Substitution mappings: error validating interface mappings: '%s'",
                             e)
                validation_errors[interface_name] = "validator error ({0})".format(e)

        # Everything OK
        return validation_errors


    def validate_interface_mapping(self, service: "Any", node_type: "Any", interface_name: str, interface_mapping: "Any") -> "Any":
        """Check if substitution mappings have valid interface
        mappings within the specified service

        Args: 
          service(ToscaServiceTemplate): service within which to validate
            the instance
          node_type(ToscaNodeType): type of the node for which this
            service is a substitution
          interface_name(str): name of the interface in the node type
          interface_mappings([]): interface mapping to validate
        """

        # Make sure the node type declares this interface
        try:
            interface_declaration = node_type.get_interface_declaration(interface_name)
        except KeyError:
            logger.debug("Substitution mappings: '%s' does not have interface '%s'",
                         node_type.name, interface_name)
            return 'not previously defined'

        # Per the v2.0 spec an interface mapping is a map of
        # operation_name -> workflow_name. Reject other shapes
        # explicitly so callers get a useful error instead of
        # tripping on a missing .items() further down.
        if not isinstance(interface_mapping, dict):
            return "must be a map of operation_name -> workflow_name"

        # Validate the mappings
        validation_errors = {}
        for operation_name, workflow_name in interface_mapping.items():
            # Does the interface define the operation?
            try:
                operation = interface_declaration.get_operation_declaration(operation_name)
            except KeyError:
                validation_errors[operation_name] = 'operation not defined in interface {}'.format(interface_name)
            try:
                workflow_template = service.workflows[workflow_name]
            except KeyError:
                # Could be an automatically-generated workflow
                if not workflow_name in ['deploy', 'delete']: 
                    validation_errors[workflow_name] = 'workflow not defined in service template'

        # All done
        return validation_errors


    def upgrade_attribute_mappings(self, service: "Any", node_type: "Any", substitution_mappings: dict) -> None:
        """Upgrade attribute mappings in a substitution mapping section to
        v2.0 syntax if necessary.

        Args: 
          service(ToscaServiceTemplate): service template for
            which to upgrade attribute mappings
          node_type(ToscaNodeType): type of the node for which this
            service is a substitution
          substitution_mappings(dict): substitution mappings to
            upgrade
        """

        # Do the substitution mappings define attribute mappings
        try:
            attributes = substitution_mappings.attributes
        except (AttributeError, KeyError):
            # No attribute mappings
            return

        # Is this a Version 1.x service template?
        if (not service.tosca_version or
            not service.tosca_version.startswith("tosca_simple_yaml")):
            # Nothing to do
            return 
        
        # Upgrade each attribute mapping
        upgraded = dict()
        for attribute_name, attribute_mapping in attributes.items():
            name = node_type.upgrade_tosca_path(attribute_name)
            if isinstance(name, list):
                name = tuple(name)
            upgraded[name] = attribute_mapping

        substitution_mappings.attributes = upgraded


    def upgrade_property_mappings(self, service: "Any", node_type: "Any", substitution_mappings: dict) -> None:
        """Upgrade property mappings in a substitution mapping section to
        v2.0 syntax if necessary.

        Args: 
          service(ToscaServiceTemplate): service template for
            which to upgrade property mappings
          node_type(ToscaNodeType): type of the node for which this
            service is a substitution
          substitution_mappings(dict): substitution mappings to
            upgrade
        """
        # Is this a Version 1.x service template?
        if (not service.tosca_version or
            not service.tosca_version.startswith("tosca_simple_yaml")):
            # Nothing to do
            return 
        
        # Do the substitution mappings define property mappings
        try:
            properties = substitution_mappings.properties
        except (AttributeError, KeyError):
            # No property mappings
            return

        # Upgrade each property mapping
        upgraded = dict()
        for property_name, property_mapping in properties.items():
            # Convert property paths if necessary
            name = node_type.upgrade_tosca_path(property_name)
            if isinstance(name, list):
                name = tuple(name)
            # Convert mappings                
            try:
                # 1.x maps to a single-value list
                [ input_name] = property_mapping
            except ValueError:
                # Not a single value list
                input_name = property_mapping

            upgraded[name] = input_name

        substitution_mappings.properties = upgraded
