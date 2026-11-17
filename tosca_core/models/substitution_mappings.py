"""
Module defining the Tosca Substitution Mappings entity
"""
from __future__ import annotations

__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2017-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Typing support
from typing import Any, Optional

# Logging support
import logging
logger: logging.Logger = logging.getLogger(__name__)

# Database support
from tosca_core import db

# Mapping structures are mutable: validation rewrites them in place, and the
# code that does so calls '.changed()' on the value, as it does for policy
# triggers and workflow steps.
from sqlalchemy.ext.mutable import MutableDict, MutableList

# Exception support
import tosca_core.models.exceptions as te

# Support for TOSCA keywords that are shared between all entities
import tosca_core.models.entity


################################################################################
# What a requirement mapping TARGET is, and what it resolves to.
#
# Both the validator and the substitution path ask these questions, and they
# have to agree: the validator decides whether a template is accepted, and the
# substitution path acts on what was accepted. Asking them separately is how a
# three-element target once reached a dictionary lookup as a key and was
# reported as "unhashable type: 'CommentedSeq'" from inside the validator.
################################################################################

def is_requirement_pair(target: Any) -> bool:
    """Is this target '[node, requirement]' -- one requirement of one node?

    Args:
      target: one target of a requirement mapping entry
    """
    return (isinstance(target, list) and len(target) == 2
            and all(isinstance(element, str) for element in target))


def is_indexed_target(target: Any) -> bool:
    """Is this target '[node, index, requirement]' -- one requirement of ONE
    REPRESENTATION of a counted node template?

    The index selects the representation, so that the assignments of a single
    requirement are distributed across the instances rather than accumulating
    on one node. Its value is not inspected here: it is validated as an integer
    where the template is accepted, and evaluated against the relationship
    being mapped at substitution.

    Args:
      target: one target of a requirement mapping entry
    """
    return (isinstance(target, list) and len(target) == 3
            and isinstance(target[0], str) and isinstance(target[2], str))


def target_requirement(target: Any) -> Optional[tuple]:
    """Return '(node name, requirement name)' for a target that names a
    requirement, or None for one that does not.

    A selectable-node target names a node rather than a requirement and answers
    None, as does anything malformed. An indexed target answers with its node
    and requirement; the index says WHICH representation, not which
    requirement, so it is dropped here.

    Args:
      target: one target of a requirement mapping entry
    """
    if is_requirement_pair(target):
        return (target[0], target[1])
    if is_indexed_target(target):
        return (target[0], target[2])
    return None


def mandatory_mapping_targets(node_templates: Any, mappings: list) -> list:
    """Return the targets of one requirement mapping entry that name MANDATORY
    requirements, as 'node.requirement' strings.

    An entry with such a target cannot be left unfilled: the only thing that
    can satisfy it is an assignment handed down from the substituted node. This
    is the quantity §15.5.4 rule 2 is about, and both sites that ask it -- the
    design-time approximation against the substituted type's lower bound, and
    the substitution-time comparison against the node's actual assignments --
    count the same targets.

    A selectable-node target is not counted. Such an entry names a node rather
    than a requirement, and expands to however many requirements in the
    template happen to target that node; whether rule 2 applies to it, and over
    what, is undefined -- oasis-tcs/tosca-specs#368.

    Args:
      node_templates: the substituting template's node templates, by name
      mappings([]): the targets of one mapping entry
    Returns:
      A list of 'node.requirement' names, empty when none is mandatory
    """
    targets = list()
    for target in mappings:
        names = target_requirement(target)
        if not names:
            continue
        (node_name, requirement_name) = names
        try:
            node_template = node_templates[node_name]
            declaration = node_template.declaration.get_requirement_declaration(
                requirement_name)
            mandatory = declaration.count_range[0] >= 1
        except Exception:
            # A target that does not resolve is reported by the per-mapping
            # validation; nothing to add here.
            continue
        if mandatory:
            targets.append("{0}.{1}".format(node_name, requirement_name))
    return targets


class ToscaSubstitutionMappings(tosca_core.models.entity.ToscaEntityMixin, db.Model):
    """The substitution mappings of a service template.

    This is an entity rather than a dict on ``ToscaServiceTemplate``
    because it is the **owner of the expressions it contains** -- the
    substitution filter above all -- and an expression context has to
    answer for both the document an expression is written in and the
    entity it refers to. The substitution mappings is the only thing
    that knows both: its containing service template supplies
    ``profile`` / ``tosca_version`` / ``service``, and the node type it
    substitutes for supplies ``SELF`` (``tosca_core.models.context``).
    """

    ################################################################################
    # Keys
    ################################################################################

    # Primary key
    id =                    db.Column(db.Integer, primary_key=True)

    # Foreign keys
    _service_id =           db.Column(db.Integer,
                                      db.ForeignKey('tosca_service_template.id'),
                                      nullable=True)

    ################################################################################
    # Fields
    ################################################################################

    # Optional fields start with '_' and have corresponding getters and
    # setters to ensure that retrieving fields consistently raises an
    # AttributeError when not set. Note that 'nullable' defaults to
    # True, but we explicitly set the 'nullable' flag for clarity.

    # The name of the node type this service substitutes for.
    _node_type =            db.Column(db.String,     nullable=True)

    # The boolean expression that decides whether this template may
    # substitute for a given node. Rewritten to canonical form during
    # validation, hence mutable.
    _substitution_filter =  db.Column(MutableDict.as_mutable(db.PickleType), nullable=True)

    # The mapping sections. Each is optional.
    _properties =           db.Column(MutableDict.as_mutable(db.PickleType), nullable=True)
    _attributes =           db.Column(MutableDict.as_mutable(db.PickleType), nullable=True)
    _capabilities =         db.Column(MutableDict.as_mutable(db.PickleType), nullable=True)
    _interfaces =           db.Column(MutableDict.as_mutable(db.PickleType), nullable=True)

    # Requirement mappings are a list, not a map: TOSCA allows the same
    # requirement name to appear more than once.
    _requirements =         db.Column(MutableList.as_mutable(db.PickleType), nullable=True)

    # Source line, for diagnostics.
    _line =                 db.Column(db.Integer,    nullable=True)

    ################################################################################
    # Field accessors
    ################################################################################


    @property
    def node_type(self) -> str:
        if not self._node_type:
            raise AttributeError("substitution mappings do not have 'node_type'")
        return self._node_type

    @node_type.setter
    def node_type(self, value: Optional[str]) -> None:
        if value: self._node_type = value

    @property
    def substitution_filter(self) -> Any:
        if not self._substitution_filter:
            raise AttributeError("substitution mappings do not have 'substitution_filter'")
        return self._substitution_filter

    @substitution_filter.setter
    def substitution_filter(self, value: Optional[Any]) -> None:
        if value: self._substitution_filter = value

    @property
    def properties(self) -> dict[str, Any]:
        if not self._properties:
            raise AttributeError("substitution mappings do not have 'properties'")
        return self._properties

    @properties.setter
    def properties(self, value: Optional[dict[str, Any]]) -> None:
        if value: self._properties = value

    @property
    def attributes(self) -> dict[str, Any]:
        if not self._attributes:
            raise AttributeError("substitution mappings do not have 'attributes'")
        return self._attributes

    @attributes.setter
    def attributes(self, value: Optional[dict[str, Any]]) -> None:
        if value: self._attributes = value

    @property
    def capabilities(self) -> dict[str, Any]:
        if not self._capabilities:
            raise AttributeError("substitution mappings do not have 'capabilities'")
        return self._capabilities

    @capabilities.setter
    def capabilities(self, value: Optional[dict[str, Any]]) -> None:
        if value: self._capabilities = value

    @property
    def interfaces(self) -> dict[str, Any]:
        if not self._interfaces:
            raise AttributeError("substitution mappings do not have 'interfaces'")
        return self._interfaces

    @interfaces.setter
    def interfaces(self, value: Optional[dict[str, Any]]) -> None:
        if value: self._interfaces = value

    @property
    def requirements(self) -> list[Any]:
        if not self._requirements:
            raise AttributeError("substitution mappings do not have 'requirements'")
        return self._requirements

    @requirements.setter
    def requirements(self, value: Optional[list[Any]]) -> None:
        if value: self._requirements = value

    @property
    def line(self) -> Any:
        return self._line

    @line.setter
    def line(self, value: Optional[Any]) -> None:
        if value: self._line = value

    @property
    def substitutes_id(self) -> int:
        """The DB id of the node type these mappings substitute for.

        Held by the containing service template, and delegated here so a
        schema dumping these mappings can reach it the way it did when
        they were a dict.
        """
        return self.service.substitutes_id

    ################################################################################
    # Model Navigation
    ################################################################################

    # The containing service template. Set by that template when it
    # takes ownership of these mappings.
    _service =              db.relationship('ToscaServiceTemplate',
                                            foreign_keys='ToscaSubstitutionMappings._service_id',
                                            back_populates='_substitution_mappings')

    ################################################################################
    # Expression context
    #
    # An expression written in the substitution mappings -- the
    # substitution filter, and any function in a mapping value -- is
    # evaluated against these. The document half comes from the
    # containing service template; the referenced entity is the node
    # type this template substitutes for.
    ################################################################################

    @property
    def service(self) -> Any:
        """The service template these mappings belong to.

        At design time this is what ``$get_input`` and a named-node
        reference resolve against, which is correct: the inputs an
        expression here may read are the ones this template declares.
        """
        if not self._service:
            raise te.ModelCorruptionError(
                "substitution mappings do not have a containing service template")
        return self._service

    @property
    def profile(self) -> Any:
        """Get profile from the containing service template. This is the
        document the expressions here are written in, so it is the
        document whose namespaces are in scope.
        """
        return self.service.profile

    @property
    def tosca_version(self) -> str:
        """Get the TOSCA version from the containing service template, which
        is the grammar these expressions are written in.
        """
        return self.service.tosca_version

    def SELF(self) -> Any:
        """SELF in a substitution mappings expression is the node being
        substituted for, which at this layer is the node type.

        Taken from the containing service template, which resolves it
        before any expression here is validated: the validator checks
        the node type first and only then the mappings that refer to it.
        """
        try:
            return self.service.substitutes
        except AttributeError:
            raise te.ModelCorruptionError(
                "substitution mappings have no resolved node type for SELF")

    def SOURCE(self) -> Any:
        """SOURCE has no meaning here: substitution mappings are not a
        relationship.
        """
        raise te.ModelCorruptionError(
            "SOURCE is not available in substitution mappings: it refers to relationships only")

    def TARGET(self) -> Any:
        """TARGET has no meaning here: substitution mappings are not a
        relationship.
        """
        raise te.ModelCorruptionError(
            "TARGET is not available in substitution mappings: it refers to relationships only")

    ################################################################################
    # Constructor
    ################################################################################

    def __init__(self,
                 node_type: Optional[str] = None,
                 substitution_filter: Optional[Any] = None,
                 properties: Optional[dict[str, Any]] = None,
                 attributes: Optional[dict[str, Any]] = None,
                 capabilities: Optional[dict[str, Any]] = None,
                 requirements: Optional[list[Any]] = None,
                 interfaces: Optional[dict[str, Any]] = None,
                 line: Optional[Any] = None,
                 **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.node_type = node_type
        self.substitution_filter = substitution_filter
        self.properties = properties
        self.attributes = attributes
        self.capabilities = capabilities
        self.requirements = requirements
        self.interfaces = interfaces
        self.line = line
