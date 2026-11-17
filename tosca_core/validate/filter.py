"""
ToscaFilterValidator class
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2014-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger = logging.getLogger(__name__)

# Type hint support
from typing import Any

# Validator support
from . import get_validator


class ToscaFilterValidator(object):
    """The ToscaFilterValidator class validates Version 1.x node filters
    and upgrades them to Version 2.x syntax.
    """

    def __init__(self) -> None:
        """Constructor"""
        super(ToscaFilterValidator, self).__init__()


    def validate_and_upgrade_filter(self, template: "Any", type_entity: "Any", node_filter: "Any") -> dict:
        """Check if a Version 1.x filter defined in a template is valid for
        the specified type and if so, upgrade to Version 2.0 syntax.
 
        Args: 
          template: template within which the filter is defined.
          type_entity(ToscaType): type to which to apply the filter
          node_filter(ToscaFilter): Version 1.x node filter to
            validate and upgrade

        Returns:
          (possibly empty) dict of validation errors

        Raises:
          None
        """
        # First, validate the node filter
        try:
            errors = self.validate_filter(template, type_entity, node_filter)
            if errors:
                return errors
        except Exception as e:
            logger.error("'%s': error validating node filter: %s", template.name, e)
            return "validator error ({0})".format(e)

        # We have a valid node filter. Upgrade to a Version 2.0
        # boolean function (which will be validated again later and
        # resolved to internal function syntax).
        template.node_filter = self.upgrade_filter(template, node_filter)
        
        # Everything OK
        return {}


    def upgrade_filter(self, context: "Any", filter: "Any") -> "Any":
        """Upgrade Version 1.x node filter to a Version 2.0 boolean
        function
        """
        upgraded = self.upgrade_property_filters(context, filter)
        upgraded.extend(self.upgrade_capability_filters(context, filter))
        if not upgraded:
            return filter
        elif len(upgraded) == 1:
            return upgraded[0]
        else:
            return { '$and': upgraded }
        
    def upgrade_property_filters(self, context: "Any", filter: "Any") -> list:
        """Upgrade property filters to a boolean function
        """
        upgraded = list()
        try:
            # Does this filter include property filters?
            property_filters = filter['properties']
        except KeyError:
            return upgraded

        # Upgrade all property filters
        for property_filter in property_filters:
            filter = self.upgrade_property_filter(context, property_filter)
            upgraded.append(filter)
        # All done
        return upgraded


    def upgrade_property_filter(self, context: "Any", property_filter: dict) -> dict:
        """Upgrade a property filter to a boolean function.
        """
        function = '$' + property_filter['operation']
        if context.type_class == 'relationship':
            path = ['SELF', 'TARGET',  property_filter['name'] ]
        elif context.type_class == 'node':
            path = ['SELF', property_filter['name'] ]
        else:
            logger.error("unsupported type class %s", context.type_class)
        arg0 = { '$get_property': path }
        arg1 = property_filter['value']
        return { function: [ arg0, arg1] }


    def upgrade_capability_filters(self, context: "Any", filter: "Any") -> list:
        """Upgrade a capability filter to a boolean expression
        """
        upgraded = list()
        try:
            # Does the filter include capability filters?
            capability_filters = filter['capabilities']
        except KeyError:
            return upgraded

        # Upgrade all capability filters
        for capability_filter in capability_filters:
            filter = self.upgrade_capability_filter(context, capability_filter)
            upgraded.extend(filter)

        # All done
        return upgraded

    def upgrade_capability_filter(self, context: "Any", filter: "Any") -> list:
        """Upgrade property filters to a boolean function
        """
        upgraded = list()
        try:
            # Does this filter include property filters?
            property_filters = filter['properties']
        except KeyError:
            return upgraded

        # Upgrade all property filters
        for property_filter in property_filters:
            upgraded.append(self.upgrade_capability_property_filter(context, filter['name'], property_filter))
        # All done
        return upgraded


    def upgrade_capability_property_filter(self, context: "Any", capability: str, property_filter: dict) -> dict:
        """Upgrade a property filter to a boolean function.
        """
        function = '$' + property_filter['operation']
        if context.type_class == 'relationship':
            path = ['SELF', 'TARGET',  'CAPABILITY', capability, property_filter['name'] ]
        elif context.type_class == 'node':
            path = ['SELF', 'CAPABILITY', capability, property_filter['name'] ]
        else:
            logger.error("unsupported type class %s", context.type_class)
        arg0 = { '$get_property': path }
        arg1 = property_filter['value']
        return { function: [ arg0, arg1] }


    def validate_filter(self, context: "Any", type_entity: "Any", tosca_filter: "Any") -> dict:
        """Check if a filter is valid for the specified type within the
        provided context.
 
        Args: 
          context: context within which the filter is defined. This is
            used for error logging only.
          type_entity(ToscaType): type to which to apply the filter
          tosca_filter(ToscaFilter): filter to validate
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """

        validation_errors = {}

        # Are property filters valid?
        errors = self.validate_property_filters(context, type_entity, tosca_filter)
        if errors:
            validation_errors['properties'] = errors

        # Are capability filters valid?
        errors = self.validate_capability_filters(context, type_entity, tosca_filter)
        if errors:
            validation_errors['capabilities'] = errors

        # Everything checks out
        return validation_errors


    def validate_property_filters(self, context: "Any", type_entity: "Any", tosca_filter: "Any") -> dict:
        """Check if a filter has valid property filters for the specified type
        within the provided context.
 
        Args: 
          context: context within which the filter is defined. This is
            used for error logging only.
          type_entity(ToscaType): type to which the filter applies
          tosca_filter(ToscaFilter): filter for which to validate
            property filters
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """

        validation_errors = {}

        try:
            # Does this filter include property filters?
            property_filters = tosca_filter['properties']
        except KeyError:
            # No node filters
            logger.debug("'%s': no properties in filter", context.name)
            return validation_errors

        # Check all property filters
        for property_filter in property_filters:
            logger.debug("'%s': validating property filter '%s'",
                         context.name, property_filter['name'])
            try:
                errors = self.validate_property_filter(context, type_entity, property_filter)
                if errors:
                    logger.error("'%s': invalid property '%s' in filter", 
                                 context.name, property_filter['name'])
                    validation_errors[property_filter['name']] = errors
            except Exception as e:
                validation_errors[property_filter['name']] = "validator error ({0})".format(e)

        # Everything OK
        return validation_errors


    def validate_property_filter(self, context: "Any", type_entity: "Any", property_filter: dict) -> dict:
        """Check if a filter has a valid property filter for the specified type
        within the provided context.
 
        Args: 
          context: context within which the filter is defined. This is
            used for error logging only.
          type_entity(ToscaType): type to which the filter applies
          tosca_filter(ToscaFilter): filter for which to validate the
            property filter
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """

        logger.debug("'%s': validating property constraint '%s' (%s)", 
                     context.name, property_filter['name'], property_filter['operation'])

        # Get the property declaration to which the filter applies
        try:
            property_declaration = type_entity.get_property_declaration(property_filter['name'])
        except KeyError:
            logger.error("'%s': no property '%s' in node type %s", 
                         context.name, property_filter['name'], type_entity.name)
            return "not defined in type {0}".format(type_entity.name)
        except Exception as e:
            return "validator error '{0}'".format(str(e))

        try:
            # Are property filter constraints valid for the property type?
            errors = property_declaration.validate_constraints(context, [ property_filter ])
            if errors:
                logger.error("'%s': property constraint '%s' invalid", 
                             context.name, property_filter['name'])
                return errors
        except Exception as e:
            logger.error("error while validating node filter: %s", str(e))
            return "validator error '{0}'".format(e)

        # Everything OK
        return {}


    def validate_capability_filters(self, context: "Any", type_entity: "Any", tosca_filter: "Any") -> dict:
        """Check if a filter has valid capabiity filters for the specified
        type within the provided context.
 
        Args: 
          context: context within which the filter is defined. This is
            used for error logging only.
          type_entity(ToscaType): type to which the filter applies
          tosca_filter(ToscaFilter): filter for which to validate
            capability filters
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """

        validation_errors = {}

        try:
            # Does the filter include capability filters?
            capability_filters = tosca_filter['capabilities']
        except KeyError:
            # No capability filters
            logger.debug("'%s': no capabilities in filter",  context.name)
            return validation_errors

        # Check all capability filters
        for capability_filter in capability_filters:
            logger.debug("'%s': validating capability filter '%s'",
                         context.name, capability_filter['name'])
            try:
                errors = self.validate_capability_filter(context, type_entity, capability_filter)
                if errors:
                    logger.error("'%s': invalid capability '%s' in filter", 
                                 context.name, capability_filter['name'])
                    validation_errors[capability_filter['name']] = errors
            except Exception as e:
                validation_errors[capability_filter['name']] = "validator error ({0})".format(e)

        # Everything OK
        return validation_errors


    def validate_capability_filter(self, context: "Any", type_entity: "Any", capability_filter: dict) -> dict:
        """Check if a filter has a valid capability filter for the specified
        type within the provided context.
 
        Args: 
          context: context within which the filter is defined. This is
            used for error logging only.
          type_entity(ToscaType): type to which the filter applies
          tosca_filter(ToscaFilter): filter for which to validate the
            capability filter
        Returns:
          (possibly empty) dict of validation errors
        Raises:
          None
        """

        # Get the capability declaration to which the filter applies
        try:
            capability_declaration = type_entity.get_capability_declaration(capability_filter['name'])
        except KeyError:
            logger.error("'%s': no capability '%s' in type %s", 
                         context.name, capability_filter['name'], type_entity.name)
            return "not defined in type {0}".format(type_entity.name)
        except Exception as e:
            logger.error("'%s': error finding capability '%s': %s",
                         context.name, capability_filter['name'], e)
            return "validator error ({0})".format(e)

        # Are property filters valid?
        errors = self.validate_filter(context, capability_declaration.type_entity, capability_filter)
        if errors:
            return errors

        # Everything checks out
        return {}
