"""
Module defining Tosca node template entity
"""
from __future__ import annotations

from typing import Any, Optional

__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2014-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging

logger: logging.Logger = logging.getLogger(__name__)

# Database support
from tosca_core import db

# SQL Alchemy support
from sqlalchemy.orm import backref
from sqlalchemy.orm.collections import attribute_mapped_collection
from sqlalchemy.ext.orderinglist import ordering_list

# Exceptions
import tosca_core.models.exceptions as te
import tosca_core.models.presence as presence


# Types on which this type depends
import tosca_core.models.managed_template
from tosca_core.models.path import ToscaPath, split_requirement_step
from tosca_core.models import builtin_types

# Types used in relationships
import tosca_core.models.capability_template
import tosca_core.models.relationship_template
import tosca_core.models.property_declaration
import tosca_core.models.node_declaration
import tosca_core.models.artifact
import tosca_core.models.function


class ToscaNodeTemplate(tosca_core.models.managed_template.ToscaManagedTemplate):
    """The TOSCA node template entity represents node templates specified
    in TOSCA service templates
    """

    ################################################################################
    # Polymorphic mapping 
    ################################################################################

    __mapper_args__ = {
        'polymorphic_identity': 'node',
    }

    ################################################################################
    # Fields
    ################################################################################

    # Optional fields start with '_' and have corresponding getters
    # and setters to ensure that retrieving fields consistently raises
    # an AttributeError when not set.  Note that 'nullable' defaults
    # to True, but we explicitly set the 'nullable' flag for clarity.

    # '_directives' is declared on the shared ToscaTemplate base.
    @property
    def directives(self) -> list[str]:
        return (self._directives if self._directives != None else ['create'])

    # Directives currently supported
    valid_directives = [ 'select', 'create', 'substitute', 'onboard' ]

    # Relationshps
    artifacts =     db.relationship('ToscaArtifact',
                                    collection_class=attribute_mapped_collection('name'),
                                    foreign_keys='ToscaArtifact._containing_template_id',
                                    back_populates='containing_template',
                                    cascade='all')
    capabilities =  db.relationship('ToscaCapabilityTemplate',
                                    collection_class=attribute_mapped_collection('name'),
                                    foreign_keys='ToscaCapabilityTemplate._containing_template_id',
                                    back_populates='containing_template',
                                    cascade='all')
    requirements =  db.relationship('ToscaRelationshipTemplate',
                                    collection_class=ordering_list('position'),
                                    order_by='ToscaRelationshipTemplate.position',      
                                    foreign_keys='ToscaRelationshipTemplate._containing_template_id',
                                    back_populates='containing_template',
                                    cascade='all')

    # Make 'relationships' the same as 'requirements'
    @property
    def relationships(self) -> list[Any]:
        return self.requirements

    @relationships.setter
    def relationships(self, value: Optional[list[Any]]) -> None:
        if value:
            # Set 'position' attributes to maintain the correct order
            position = 0
            for requirement in value:
                requirement.position = position
                position = position + 1
            self.requirements = value

    def get_requirement(self, name: str) -> Optional[Any]:
        """Get a named requirement. TODO: this should return a list if more
        than one requirement with the same name is found
        """
        for requirement in self.requirements:
            if requirement.name == name:
                return requirement
        return None

    def get_requirement_by_index(self, name: str, index: int) -> Optional[Any]:
        """Get the Nth requirement with the given name."""
        count = 0
        for requirement in self.requirements:
            if requirement.name == name:
                if count == index:
                    return requirement
                count += 1
        return None
    
    ################################################################################
    # Model Navigation
    ################################################################################

    def get_implementation_artifact(self, artifact_name: str) -> Any:
        """Return the artifact an operation implementation names (TOSCA 2.0
        §11.8): an artifact of the node type or node template that contains
        the operation, here this one. This is not $get_artifact, which
        follows a path (get_artifact).

        Raises:
          KeyError: when no such artifact is found
        """
        return self.get_artifact(artifact_name)

    def get_artifact(self, artifact_name: Any) -> Any:
        """Return the artifact 'artifact_name' names: one of this node's, or,
        for a path [RELATIONSHIP, <requirement>, <index>, ...], the one the
        rest of the path reaches from that requirement's relationship, such
        as [RELATIONSHIP, host, TARGET, <artifact>]. With no index, ALL is
        implied, which reaches one relationship where the requirement's count
        range admits one, and several where it admits more: a $get_artifact
        returns one location, a string, so a path that reaches several is
        refused, as the count range decides and not how many are bound.

        Raises:
          KeyError: when the artifact is not found, or the path passes
            through anything but RELATIONSHIP
          ValueError: when the path reaches several relationships, or the
            index is a function
        """
        try:
            path = ToscaPath(artifact_name)
        except TypeError:
            # First, try to find the artifact within the node template's
            # artifact definitions.
            try:
                return self.artifacts[artifact_name]
            except KeyError:
                # Not found. Try node type instead. Get to node type
                # through node declaration.
                return self.declaration.get_artifact(artifact_name)
        if path.entity != 'RELATIONSHIP':
            raise KeyError("'{0}': a node's artifact path passes through "
                           "RELATIONSHIP".format(artifact_name))
        name, index, rest = split_requirement_step(path.sub_entity)
        if index is None and self.declaration.get_requirement_declaration(name).supports_multiple():
            raise ValueError("'{0}': with no index, ALL is implied, and '{1}' admits several "
                             "relationships, so the path reaches several artifacts where "
                             "$get_artifact returns one: index one".format(artifact_name, name))
        requirement = (self.get_requirement(name) if index is None
                       else self.get_requirement_by_index(name, index))
        if not requirement:
            # Dangling: no relationship template here, so the declaration's
            return self.declaration.get_artifact(artifact_name)
        return requirement.get_artifact(rest)


    ################################################################################
    # Implementation of reserved keywords
    ################################################################################

    def SOURCE(self) -> None:
        """Return the declaration of the SOURCE node_template. SOURCE is only
        supported on relationship templates. Calling SOURCE on a node
        template results in an 'InvalidPathError'
        """
        error = f"Invalid SOURCE keyword on node template {self.name}"
        raise te.InvalidPathError(error)

    def TARGET(self) -> None:
        """Return the declaration of the TARGET node_template. TARGET is only
        supported on relationship templates. Calling TARGET on a node
        template results in an 'InvalidPathError'
        """
        error = f"Invalid TARGET keyword on node template {self.name}"
        raise te.InvalidPathError(error)


    ################################################################################
    # Constructor
    ################################################################################

    def __init__(self,
                 directives: Optional[list[str]] = None,
                 requirements: Optional[list[Any]] = None,
                 capabilities: Optional[dict[str, Any]] = None,
                 artifacts: Optional[dict[str, Any]] = None,
                 **kwargs: Any
                 ) -> None:
        """Create a new Tosca Node Template object"""

        # attributes is handled by ToscaTemplate.__init__ (the column
        # lives on the base), so it just passes through via **kwargs.

        # First, call superclass constructor
        super(ToscaNodeTemplate, self).__init__(**kwargs)

        # ToscaNodeType-specific initialization
        if directives: self._directives = directives

        # We don't have 'setters' for the following, so make sure to
        # check if not 'None'
        if requirements: self.requirements = requirements
        if capabilities: self.capabilities = capabilities
        if artifacts: self.artifacts = artifacts


    ################################################################################
    # Helper functions
    ################################################################################

    def is_abstract(self) -> bool:
        """Return true if this is an abstract node. A node is abstract if is
        has a 'substitute' directive (or 'substitutable' for backward
        compatibility)
        """
        return ('substitute' in self.directives)

    def is_onboard(self) -> bool:
        """Return true if this is an onboard node -- i.e. it carries
        the 'onboard' directive.
        """
        return ('onboard' in self.directives)

    def is_selectable(self) -> bool:
        """Return true if this node can be selected from inventory (i.e. it
        has has 'select' in its list of directives (or 'selectable'
        for backward compatibility)
        """
        return ('select' in self.directives)


    ################################################################################
    # Template refinement support
    ################################################################################

    def complete_template_refinement(self, source_template: Any) -> None:
        """Carry node-template-specific collections (capabilities,
        requirements, artifacts) over from the source template. Per the
        TOSCA copy semantics: anything self already declares wins; the
        rest is inherited from the source. Each inherited entry is
        materialised as a fresh child template via
        complete_template_refinement, so the original source's children
        keep their SQLAlchemy parent ownership.
        """
        super(ToscaNodeTemplate, self).complete_template_refinement(source_template)
        self._merge_augmented_capabilities(source_template)
        self._merge_augmented_artifacts(source_template)
        self._merge_augmented_requirements(source_template)


    def _merge_augmented_capabilities(self, source_template: Any) -> None:
        try:
            source_capabilities = source_template.capabilities
        except AttributeError:
            return
        if not source_capabilities:
            return
        for name, source_capability in source_capabilities.items():
            try:
                own = self.capabilities[name]
                own.complete_template_refinement(source_capability)
            except (AttributeError, KeyError):
                merged = tosca_core.models.capability_template.ToscaCapabilityTemplate()
                merged.complete_template_refinement(source_capability)
                self.capabilities[name] = merged


    def _merge_augmented_artifacts(self, source_template: Any) -> None:
        try:
            source_artifacts = source_template.artifacts
        except AttributeError:
            return
        if not source_artifacts:
            return
        for name, source_artifact in source_artifacts.items():
            try:
                own = self.artifacts[name]
                own.complete_template_refinement(source_artifact)
            except (AttributeError, KeyError):
                merged = tosca_core.models.artifact.ToscaArtifact()
                merged.complete_template_refinement(source_artifact)
                self.artifacts[name] = merged


    def _merge_augmented_requirements(self, source_template: Any) -> None:
        """Requirements are an ordered list, not a dict, but they are
        addressed by name. For copy semantics treat names like keys:
        a requirement self already declares stays as-is, and for every
        source requirement whose name is unknown, take a fresh copy.
        The merged list is then re-ordered to match the order of
        requirement declarations in self's node type, since
        validate_requirements_list enforces that ordering downstream.
        """
        try:
            source_requirements = source_template.requirements
        except AttributeError:
            return
        if not source_requirements:
            return

        own_names = {r.name for r in self.requirements}
        extra: list[Any] = []
        for source_requirement in source_requirements:
            if source_requirement.name in own_names:
                continue
            merged = tosca_core.models.relationship_template.ToscaRelationshipTemplate()
            merged.complete_template_refinement(source_requirement)
            extra.append(merged)
            own_names.add(source_requirement.name)

        if not extra:
            return

        combined = list(self.requirements) + extra
        try:
            decl_order = [d.name for d in
                          self.declaration.get_requirement_declarations()]
        except Exception:
            decl_order = []
        if decl_order:
            order_map = {name: idx for idx, name in enumerate(decl_order)}
            sentinel = len(decl_order)
            combined.sort(key=lambda r: order_map.get(r.name, sentinel))
        # Use the relationships setter so positions get reassigned to
        # match the new list order.
        self.relationships = combined


    ################################################################################
    # Manipulate requirements list
    ################################################################################

    def get_required_node_names(self) -> list[str]:
        """Return list of entity names of the same type on which this
        entity depends. Node Template entities return the names of the
        entities specified in the requirements"""

        required_node_names: list[str] = []
        for requirement in self.requirements:
            try:
                required_node_names.append(requirement.node)
            except AttributeError:
                # No node specified in this requirement
                pass
        return required_node_names


    def insert_requirement(self, after: Optional[str], requirement: Any) -> None:
        """Append a requirement template after a the last requirement with the
        specified name

        Args:

          after(string): name of the requirement template after which
            to insert the new requirement (or None)
          requirement(ToscaRelationshipTemplate): template to insert
        """
        # First, find position in the list
        if after==None:
            position = 0
        else:
            # Find position right after the last element with name
            # 'after'
            names = [ r.name for r in self.requirements ]
            position = len(names) - names[::-1].index(after) 

        # Insert at that position
        self.requirements.insert(position, requirement)

    
    ################################################################################
    # Instantiation support
    ################################################################################

    def supports_multiple(self) -> bool:
        """Can this template yield more than one node representation?

        The counterpart of ``ToscaRelationshipDeclaration.supports_multiple``,
        which reads a requirement's declared ``count_range``. A node type
        declares no count, so the bound comes from the template instead: a
        literal ``count`` is its own upper bound, and an expression is
        unbounded because nothing can know its value before deployment.

        Answered WITHOUT evaluating, so the shape of a path is fixed at design
        time. An expression that happens to yield one representation is still
        multiple, exactly as a ``[0, UNBOUNDED]`` requirement with a single
        binding is. The ``count`` accessor reports 1 when the keyname is
        absent, so one test covers the unset case, the explicit ``count: 1``
        case, and every expression -- a function value never equals 1.
        """
        return self.count != 1


    ################################################################################
    # Support for retrieving attribute and property value declarations
    # from this node template. 
    ################################################################################

    def get_attribute_or_property_declaration(self, attr_or_prop: str, value_name: Any) -> Any:
        """Return the attribute or property value declaration for the property or
        attribute specified in 'value_name' (where the 'attr_or_prop'
        flag specifies whether to look up a property declaration or an
        attribute declaration). This method overrides the
        'get_attribute_or_property_declaration' method defined in the base
        class. It checks value declarations defined in capabilities and
        requirements.

        Args:
          attr_or_prop (either 'properties' or 'attributes'): flag
            that specifies whether to look for a property value or an
            attribute value.
          value_name (string or ToscaPath): the property or attribute
            for which to return the value declaration.

        Returns:
          Python value

        Raises:
          KeyError: when named property or attribute not found
        """
        try:
            # Is value_name a ToscaPath expression? 
            path = ToscaPath(value_name)

            # Does the path reference a relationship?
            if path.entity == 'RELATIONSHIP':
                # First, try to hand-off the 'get_attribute' or
                # 'get_property' call to the locally-defined
                # relationship template. If such a template does not
                # exist, the requirement must be dangling and we
                # hand-off to the relationship declaration. This will
                # raise a KeyError if the attribute or property is not
                # found.
                try:
                    sub_entity = path.sub_entity
                    path = ToscaPath(sub_entity)
                    relationship_name = path.entity
                    requirement = self.get_requirement(relationship_name)
                    if not requirement:
                        # No local relationship template for this
                        # requirement in this node template. Delegate
                        # to our declaration instead.
                        return self.declaration.get_attribute_or_property_declaration(
                            attr_or_prop, value_name)
                except TypeError:
                    logger.error("%s: invalid requirement path %s", self.name, sub_entity)
                    raise KeyError(str(sub_entity))

                # Determine whether the rest of this path
                # references a list of relationships or single
                # relationship.
                requirement_declaration = self.declaration.get_requirement_declaration(relationship_name)
                try:
                    sub_path = ToscaPath(path.sub_entity)
                    if isinstance(sub_path.entity, int):
                        # Index that references a single relationship. Take
                        # the declaration from THAT template: 'requirement'
                        # above is whichever template came first under this
                        # name, which answers for an index only where every
                        # template sharing the name agrees. The two sibling
                        # sites, 'is_property_template_present' and
                        # 'get_attribute_or_property_template', already
                        # re-select here.
                        use_list = False
                        path = sub_path
                        requirement = self.get_requirement_by_index(
                            relationship_name, sub_path.entity)
                        if not requirement:
                            logger.error("%s: requirement '%s' has no relationship at index %d",
                                         self.name, relationship_name, sub_path.entity)
                            raise KeyError("{0}: requirement '{1}' has no relationship at "
                                           "index {2}".format(self.name, relationship_name,
                                                              sub_path.entity))
                    elif sub_path.entity == 'ALL':
                        use_list = True
                        path = sub_path
                    else:
                        # No qualifying keyword.
                        use_list = requirement_declaration.supports_multiple()
                except TypeError as e:
                    # Not a TOSCA path. Use remainder of path as is
                    # and check count_range to decide whether to
                    # return a list or a single declaration.
                    use_list = requirement_declaration.supports_multiple()

                # Get declaration for the rest of the path.
                value_declaration = requirement.get_attribute_or_property_declaration(
                    attr_or_prop, path.sub_entity)
                # List of declarations or single declaration?
                if use_list:
                    return tosca_core.models.property_declaration.as_list_declaration(
                        value_declaration, requirement_declaration.name, attr_or_prop)
                else:
                    return value_declaration

            # Does the path reference a capability?
            if path.entity == 'CAPABILITY':
                # Hand-off the 'get_attribute' or 'get_property' call
                # to the capability declaration instead of looking at
                # local capability templates (since the node template
                # cannot add any capability information that is not
                # already in the capability declaration). This will
                # raise a KeyError if the capability declaration is
                # not found
                try:
                    sub_entity = path.sub_entity
                    path = ToscaPath(sub_entity)
                    capability_declaration = self.declaration.get_capability_declaration(path.entity)
                    return capability_declaration.get_attribute_or_property_declaration(
                        attr_or_prop, path.sub_entity)
                except TypeError:
                    logger.error("%s: invalid capability path %s", self.name, sub_entity)
                    raise KeyError(str(sub_entity))

        except TypeError as e:
            # Not a ToscaPath.
            pass

        # 'value_name' is not a TOSCA Path expression, or does not
        # reference a requirement or capability. Just delegate to our
        # base class.
        return super(ToscaNodeTemplate,
                     self).get_attribute_or_property_declaration(attr_or_prop, value_name)


    ################################################################################
    # Support for checking if property value templates are available
    # in this template and for retrieving attribute and property value
    # templates from this node template.
    ################################################################################

    def is_property_template_present(self, property_path: Any, property_declaration: Any) -> bool:
        """Check if a property value exists for the property identified using path.
        Args:
          property_path (string or ToscaPath): the property for which
            to check if it exists
          property_declaration(ToscaPropertyDeclaration): declaration
            for the expected property value
        Returns:
          boolean
        Raises:
          ??
        """
        # Is property_path a ToscaPath expression?
        try:
            path = ToscaPath(property_path)

            # Does the path reference a relationship?
            if path.entity == 'RELATIONSHIP':
                # Hand-off to the relationship template
                try:
                    sub_entity = path.sub_entity
                    path = ToscaPath(sub_entity)
                    requirement_declaration = self.declaration.get_requirement_declaration(path.entity)
                    if requirement_declaration.supports_multiple():
                        try:
                            sub_path = ToscaPath(path.sub_entity)
                            if isinstance(sub_path.entity, int):
                                relationship = self.get_requirement_by_index(
                                    path.entity, sub_path.entity)
                                path = sub_path
                            elif sub_path.entity == 'ALL':
                                relationship = self.get_requirement(path.entity)
                                path = sub_path
                            else:
                                relationship = self.get_requirement(path.entity)
                        except TypeError:
                            relationship = self.get_requirement(path.entity)
                    else:
                        relationship = self.get_requirement(path.entity)
                    if not relationship:
                        return False
                    try:
                        return relationship.is_property_template_present(path.sub_entity, property_declaration)
                    except Exception as e:
                        logger.error("%s: unable to get relationship '%s': %s", self.name, path.sub_entity, str(e))
                        return presence.Undecided(
                            f"cannot follow requirement '{path.entity}' of '{self.name}': {e}")
                except TypeError:
                    logger.error("%s: invalid requirement path %s", self.name, sub_entity)
                    raise KeyError(str(sub_entity))

            # Does the path reference a capability?
            if path.entity == 'CAPABILITY':
                # Hand-off to the capability.
                try:
                    sub_entity = path.sub_entity
                    path = ToscaPath(sub_entity)
                    capability = self.capabilities[path.entity]
                    return capability.is_property_template_present(path.sub_entity, property_declaration)
                except TypeError:
                    logger.error("%s: invalid capability path %s", self.name, sub_entity)
                    raise KeyError(str(sub_entity))

        except TypeError as e:
            # Not a ToscaPath.
            pass

        # 'property_path' is not a TOSCA Path expression, or does not
        # reference a requirement or capability. Just delegate to our
        # base class.
        return super(ToscaNodeTemplate, self).is_property_template_present(
            property_path, property_declaration)
    
    def get_attribute_or_property_template(self, attr_or_prop: str, attribute_name: Any) -> Any:
        """Return the attribute or property value defined in this node
        template for the attribute or property specified in
        'attr_or_prop_path' (where the 'attr_or_prop' flag specifies
        whether to look up an attribute template or a property
        template).

        Args:
          attr_or_prop (either 'properties' or 'attributes'): flag
            that specifies whether to look for a property value or an
            attribute value.
          attribute_name (string or ToscaPath): the property or attribute
            for which to return the value declaration.

        Returns:
          Python value

        Raises:
          KeyError: when named property or attribute not found
        """
        # Is attribute_name a ToscaPath expression?
        try:
            path = ToscaPath(attribute_name)

            # Does the path reference a relationship?
            if path.entity == 'RELATIONSHIP':
                # Hand-off the 'get_attribute' or 'get_property' call
                # to the relationship template
                try:
                    sub_entity = path.sub_entity
                    path = ToscaPath(sub_entity)
                    requirement_declaration = self.declaration.get_requirement_declaration(path.entity)
                    if requirement_declaration.supports_multiple():
                        try:
                            sub_path = ToscaPath(path.sub_entity)
                            if isinstance(sub_path.entity, int):
                                relationship = self.get_requirement_by_index(
                                    path.entity, sub_path.entity)
                                path = sub_path
                            elif sub_path.entity == 'ALL':
                                relationship = self.get_requirement(path.entity)
                                path = sub_path
                            else:
                                relationship = self.get_requirement(path.entity)
                        except TypeError:
                            relationship = self.get_requirement(path.entity)
                    else:
                        relationship = self.get_requirement(path.entity)
                    if not relationship:
                        return None
                    try:
                        return relationship.get_attribute_or_property_template(attr_or_prop, path.sub_entity)
                    except Exception as e:
                        logger.error("%s: unable to get relationship '%s': %s", self.name, path.sub_entity, str(e))
                        return None

                except TypeError:
                    logger.error("%s: invalid requirement path %s", self.name, sub_entity)
                    raise KeyError(str(sub_entity))

            # Does the path reference a capability?
            if path.entity == 'CAPABILITY':
                # Hand-off the 'get_attribute' or 'get_property' call
                # to the capability. 
                try:
                    sub_entity = path.sub_entity
                    path = ToscaPath(sub_entity)
                    capability = self.capabilities[path.entity]
                    return capability.get_attribute_or_property_template(attr_or_prop, path.sub_entity)
                except TypeError:
                    logger.error("%s: invalid capability path %s", self.name, sub_entity)
                    raise KeyError(str(sub_entity))

        except TypeError as e:
            # Not a ToscaPath.
            pass

        # 'attribute_name' is not a TOSCA Path expression, or does not
        # reference a requirement or capability. Just delegate to our
        # base class.
        return super(ToscaNodeTemplate, self).get_attribute_or_property_template(
            attr_or_prop, attribute_name)
