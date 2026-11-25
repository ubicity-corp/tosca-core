"""
Module definining Tosca File Data objects
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


class ToscaData(object):
    """A ToscaData object contains parsed Tosca file data

    Attributes:
      tosca_definitions_version(str): TOSCA version of the file from
        which these data were retrieved.
      meta_data: declares additional meta_data information.
        Domain-specific TOSCA profile specifications may define
        keynames that are required for their implementations
      description(str): description for the TOSCA file data
      namespace(str): namespace name for this template
      imports(ToscaImport[]): list of import objects that represent
        TOSCA files or profiles that need to be imported
      repositories(ToscaRepository map): list of external repositories
        which contain artifacts that are referenced in the service
        template along with their addresses and necessary credential
        information used to connect to them in order to retrieve the
        artifacts.
      service_template(ToscaServiceTemplate): service template defined
        in this TOSCA file
      artifact_types(ToscaArtifactType map): artifact type definitions
      capability_types(ToscaCapabilityType map): capability type
        definitions
      data_types(str): data type definitions
      group_types(str): group type definitions
      node_types(ToscaNodeType map): node type definitions
      relationship_types(ToscaRelationshipType): relationship type
        definitions
      interface_types(ToscaInterfaceType map): set of Interface Type
        definitions
      policy_types(ToscaPolicyType map): set of Policy Type
        definitions

    """

    def __init__(self,
                 line: Optional[int] = None,
                 tosca_definitions_version: Optional[str] = None,
                 meta_data: Optional[Any] = None,
                 description: Optional[str] = None,
                 profile: Optional[str] = None,
                 implements: Optional[str] = None,
                 repositories: Optional[dict[str, Any]] = None,
                 imports: Optional[list[Any]] = None,
                 artifact_types: Optional[dict[str, Any]] = None,
                 data_types: Optional[dict[str, Any]] = None,
                 capability_types: Optional[dict[str, Any]] = None,
                 interface_types: Optional[dict[str, Any]] = None,
                 relationship_types: Optional[dict[str, Any]] = None,
                 node_types: Optional[dict[str, Any]] = None,
                 group_types: Optional[dict[str, Any]] = None,
                 policy_types: Optional[dict[str, Any]] = None,
                 service_template: Optional[Any] = None,
                 dsl_definitions: Optional[Any] = None,
                 functions: Optional[dict[str, Any]] = None,
    ) -> None:
        """Constructor """

        # First, call superclass constructor
        super(ToscaData, self).__init__()

        # Set attributes
        if line != None: self.line = line
        if tosca_definitions_version: self.tosca_definitions_version = tosca_definitions_version
        if meta_data: self.meta_data = meta_data
        if description: self.description = description
        if profile: self.profile = profile
        if implements: self.implements = implements
        if dsl_definitions: self.dsl_definitions = dsl_definitions
        if repositories: self.repositories = repositories
        if imports: self.imports = imports
        if artifact_types: self.artifact_types = artifact_types
        if data_types: self.data_types = data_types
        if capability_types: self.capability_types = capability_types
        if interface_types: self.interface_types = interface_types
        if relationship_types: self.relationship_types = relationship_types
        if node_types: self.node_types = node_types
        if group_types: self.group_types = group_types
        if policy_types: self.policy_types = policy_types
        if functions: self.functions = functions
        if service_template: self.service_template = service_template


    def get_service_template(self) -> Any:
        """Return the service template from the TOSCA file data

        Returns
          service_template(ToscaServiceTemplate)
        Raises
          AttributeError: when no service template is found
          RunTimeError: when more than one service template is found
        """

        # First, check if the TOSCA file data include a service
        # template
        try:
            found_template = self.service_template
        except AttributeError:
            # No service template in this TOSCA file
            found_template = None

        # Raise an exception if we didn't find a service template
        if found_template == None:
            raise AttributeError("No service template defined")

        # All done
        return found_template
            

    def get_map(self, map_name: str) -> dict[str, Any]:
        """Return map of entities in the TOSCA file data. The specific
        entities are identified by the map name.

        Args:
          map_name(str): name of the attribute that contains the map
        Returns:
          (Possibly empty) map of TOSCA entities in the TOSCA file
          data
        Raises:
          None

        """

        # Create empty map
        returned_entities = {}

        # Then process entities from the TOSCA file data
        try:
            map_entities = getattr(self, map_name)
            returned_entities.update(map_entities)
        except AttributeError:
            # No map by this name
            pass

        return returned_entities


    def get_list(self, list_name: str) -> list[Any]:
        """Return list of entities stored in the TOSCA file data. The specific
        entities are identified by the list name.

        Args:
          list_name(str): name of the attribute that contains the list
        Returns:
          (Possibly empty) list of entities in the TOSCA file data
        Raises:
          None

        """

        # Create empty list
        returned_entities = []

        # Then process entities from these TOSCA file data
        try:
            list_entities = getattr(self, list_name)
            returned_entities.extend(list_entities)
        except AttributeError:
            # No list by this name
            pass

        return returned_entities


    def get_ordered_type_entity_list(self, map_name: str) -> list[Any]:
        """Return ordered list of type entities stored in the TOSCA file
        data. The specific type entities are identified by the map
        name.

        Args:
          map_name(str): name of the attribute that contains the map
            of type entities
        Returns:
          (Possibly empty) ordered List of TOSCA map entities.
        Raises:
          None
        """

        # Get all map entries
        map_entries = self.get_map(map_name)

        # Create ordered list
        ordered_list = []

        # Sort map entries into the list
        try:
            while True:
                # Remove an entity from the map
                type_entity_name, type_entity = map_entries.popitem()
                # Validate that type entity
                self.add_type_entity_to_ordered_list(ordered_list,
                                                     type_entity,
                                                     map_entries)
        except KeyError as error:
            # Map is now empty. All type_entities have been added
            # to the profile
            pass

        # All done
        return ordered_list


    def add_type_entity_to_ordered_list(self, ordered_list: list[Any],
                                        type_entity: Any, remaining_type_entities: dict[str, Any]) -> None:
        """Add an individual type entity to an ordered list Make sure to first
        add any type entities on which this type entity depends

        Args:

          ordered_list(list of ToscaType): list of type entities to
            which to add the type entity
          type_entity(ToscaType): type entity to add
          remaining_type_entities(dict of ToscaType): map of
            remaining type entities to add
        """

        # If this type entity is dependent on other entities that are
        # still in the remaining map, then add those other entities
        # first.
        prereq_type_names = type_entity.get_prereq_type_names()
        for prereq_type_name in prereq_type_names:
            try:
                prereq_type_entity = remaining_type_entities.pop(prereq_type_name)
                self.add_type_entity_to_ordered_list(ordered_list, 
                                                     prereq_type_entity,
                                                     remaining_type_entities)
            except KeyError:
                # Dependent entity not found in list. Just continue
                pass

        # Add this type entity
        ordered_list.append(type_entity)


    def get_repositories(self) -> dict[str, Any]:
        """return map of repositories defined in the TOSCA file data"""
        return self.get_map('repositories')

    def get_artifact_types(self) -> list[Any]:
        """return map of artifact_types defined in the TOSCA file data"""
        return self.get_ordered_type_entity_list('artifact_types')

    def get_capability_types(self) -> list[Any]:
        """return map of capability_types defined in the TOSCA file data"""
        return self.get_ordered_type_entity_list('capability_types')

    def get_node_types(self) -> list[Any]:
        """return map of node_types defined in the TOSCA file data"""
        return self.get_ordered_type_entity_list('node_types')

    def get_data_types(self) -> list[Any]:
        """return map of data_types defined in the TOSCA file data"""
        return self.get_ordered_type_entity_list('data_types')

    def get_group_types(self) -> list[Any]:
        """return map of group_types defined in the TOSCA file data"""
        return self.get_ordered_type_entity_list('group_types')

    def get_interface_types(self) -> list[Any]:
        """return map of interface_types defined in the TOSCA file data"""
        return self.get_ordered_type_entity_list('interface_types')

    def get_policy_types(self) -> list[Any]:
        """return map of policy_types defined in the TOSCA file data"""
        return self.get_ordered_type_entity_list('policy_types')

    def get_relationship_types(self) -> list[Any]:
        """return map of relationship_types defined in the TOSCA file data"""
        return self.get_ordered_type_entity_list('relationship_types')
