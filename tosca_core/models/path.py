"""
Module definining Tosca Path expressions
"""
from __future__ import annotations

__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2019-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Typing support
from typing import Any, Optional

# Logging support
import logging
logger: logging.Logger = logging.getLogger(__name__)

# Cached lookups for TOSCA built-in data types
from tosca_core.models import builtin_types

# Exceptions
import tosca_core.models.exceptions as te


def extract_path_value(context: Any, property_value: Any, sub_property_path: Any) -> Any:
    """Return a sub_property of the provided 'property_value' within the
    provided context as specified by 'sub_property_path'.
    """
    # First, make sure the property value has content from which
    # values can be extracted.
    if not property_value:
        return property_value
    while sub_property_path is not None:
        # If 'sub_property_path' is itself a TOSCA path, parse it
        # into a property name and another sub-property path..
        try:
            path = ToscaPath(sub_property_path)
            property_name = path.entity
            sub_property_path = path.sub_entity
        except TypeError:
            # Not a TOSCA path expression
            property_name = sub_property_path
            sub_property_path = None
        # Resolve property_name as a TOSCA integer-typed value. This
        # accepts a literal int, an int-shaped string, and (load-
        # bearing) a function expression like $node_index that
        # evaluates to an integer -- the round-trip through
        # validate/evaluate is what enables index-by-function. Falls
        # through unchanged on a non-integer property name.
        integer_type = builtin_types.get('integer')
        declaration = integer_type.create_declaration(name='path_index')
        try:
            index = declaration.validate_value(context, property_name)
            property_name = declaration.evaluate_value(context, index)
        except Exception:
            pass
        try:
            property_value = property_value[property_name]
        except KeyError:
            # A field that is not there is not an error. Required fields
            # are enforced when the model is built, so a key missing at
            # read time is an optional field that was not supplied --
            # `name` on a credential entry, say, where absent means the
            # file's own default. Returning None mirrors how the
            # containing property is already treated one level up
            # (Instance.get_attribute_or_property_value). A wrong-shaped
            # value still raises: only an absent key is tolerated here.
            return None
    # All done
    return property_value


def _is_index(segment: Any) -> bool:
    """Is this path segment an index rather than a name?

    Told apart by kind, never by position: a non-negative integer, the keyword
    ALL, or a function that computes one. A bool is excluded explicitly because
    Python makes it an int, and `[node, True, name]` is a malformed path rather
    than index 1.
    """
    if isinstance(segment, bool):
        return False
    if isinstance(segment, int):
        return True
    if segment == 'ALL':
        return True
    # Imported here rather than at module scope: function_declaration imports
    # ToscaPath from this module, so a top-level import would be circular.
    from tosca_core.models.function_declaration import is_function
    return is_function(segment)


def split_requirement_step(sub_entity: Any) -> tuple[str, Optional[int], Any]:
    """Split what follows RELATIONSHIP in a path to an artifact: the
    requirement's name, the index of one of its relationships if the path
    gives one, and the rest of the path, kept as ToscaPath keeps a
    sub-entity -- a bare name when one element is left, a list otherwise.

    No index and ALL are the same: every relationship of the requirement.
    That is one where the requirement's count range admits one, and the
    caller refuses it where it admits several, since an artifact path
    reaches one artifact. An index a function computes is not followed.

    Raises:
      TypeError: when nothing follows the requirement's name
      ValueError: when the index is a function
    """
    if not isinstance(sub_entity, (list, tuple)) or len(sub_entity) < 2:
        raise TypeError("'{}': a requirement path names nothing after the requirement"
                        .format(sub_entity))
    name, tail = sub_entity[0], list(sub_entity[1:])
    index = None
    if tail[0] == 'ALL':
        tail = tail[1:]
    elif _is_index(tail[0]):
        if isinstance(tail[0], bool) or not isinstance(tail[0], int):
            raise ValueError("'{}': an artifact path selects a relationship of '{}' by an "
                             "integer index or ALL".format(sub_entity, name))
        index, tail = tail[0], tail[1:]
    if not tail:
        raise TypeError("'{}': a requirement path names nothing after the index"
                        .format(sub_entity))
    return name, index, (tail[0] if len(tail) == 1 else tail)


class ToscaPath(object):
    """The Tosca path class parses, stores, and manages TOSCA path
    expressions.
    """

    @property
    def expression(self) -> list[Any]:
        """Return the full TOSCA Path expression as a flat list of segments"""
        path: list[Any] = list()
        path.append(self.entity)
        if self.index is not None:
            path.append(self.index)
        # The tail is a sequence for paths of three or more segments, and
        # is a tuple whenever the path was written as a YAML flow
        # sequence in a mapping key -- the form attribute mappings use.
        # Both sequence kinds flatten; a bare two-element tail does not.
        if isinstance(self.sub_entity, (list, tuple)):
            path.extend(self.sub_entity)
        else:
            path.append(self.sub_entity)
        return path


    def __init__(self, path: list[Any], head_index: bool = False) -> None:
        """Constructor

        The constructor parses a path expression into a target entity
        name and a sub entity

        The path expression must be a list of two or more elements
        where:

        1. the first element is the entity from which to get the
           attribute 
        2. the second can be the following:

           a. the name of a property or attribute of that entity (in
              which case there is no third argument). The path
              expression refers to that attribute or property.

           b. the name of a sub entity. The sub entity can either be a
              capability or a requirement

              - If the sub entity is a capability of the entity, the
                third argument contains the name of a property or
                attribute within that capability.  The path expression
                refers to that attribute or property of that
                capability.

              - (Only for node templates): if the sub entity is a
                requirement of the entity, the third argument contains
                the name of an attribute or property of the node that
                fulfills the requirement. The path expression refers
                to that attribute or property of the node type that
                fulfills that requirement of the entity.

        Args:
          path(list): path expression to parse into a ToscaPath object

        Raises:
          TypeError: if argument does not represent a valid path
        """

        # Call superclass constructor
        super(ToscaPath, self).__init__()

        # Validate the input shape: must be a list-or-tuple (TOSCA 1.3
        # YAML can produce tuples for flow-sequence keys like
        # ``[class, size]``, which are nested-attribute paths) of at
        # least two elements (head entity + one or more sub-entity
        # segments). Strings are special-cased because they're
        # iterable -- without the guard, len('ab') == 2 would parse
        # as a valid two-element path.
        if isinstance(path, str) or not isinstance(path, (list, tuple)) or len(path) < 2:
            raise TypeError("'{}': not a valid TOSCA path".format(path))

        self.entity = path[0]

        # TOSCA 2.0 §10.3 puts an optional index after a NAMED node, and only
        # there: the grammar is ``<node_symbolic_name>, <idx>, <node_context>``
        # against ``SELF, <node_context>``. Several representations can be
        # created from one node template, and the index selects among them.
        #
        # An index is told from an attribute name by kind, which is what the
        # spec's own note relies on when it requires the segment after a path
        # to be a non-number: an integer, the keyword ALL, or -- extending the
        # BNF, as the requirement branch in ``node.py`` already does -- a
        # function, so an index can be computed.
        # Off by default. This class doubles as the splitter for nested data
        # paths -- ``['credentials', 'kubeconfig', 'file']``, or ``['a', 0]``
        # indexing into a list VALUE -- where a leading integer means something
        # else entirely. Only the sites that go on to resolve a head entity
        # from a written TOSCA path ask for it.
        self.index = None
        tail = list(path[1:])
        if head_index and self.entity not in ('SELF', 'SOURCE', 'TARGET') \
           and _is_index(tail[0]):
            self.index = tail[0]
            tail = tail[1:]
            if not tail:
                raise TypeError(
                    "'{}': path indexes a node but selects nothing from it".format(path))

        # Two-element paths store sub_entity as a bare value;
        # longer paths keep the tail as a list (callers walk it).
        self.sub_entity = tail[0] if len(tail) == 1 else tail


    #######################################################################################
    # methods to find declarations for the entity specified by path
    #######################################################################################

    def _resolve_head(self, context: Any, select: bool = False) -> Any:
        """Dispatch the head of this path against ``context``.

        Shared by get_entity_declaration (design-time) and get_entity
        (runtime). ``context`` is duck-typed: it must expose
        SELF/SOURCE/TARGET methods for the reserved keywords, and for named
        references a service that is either a service of templates (a
        ``nodes`` mapping) or a service of instances, which answers
        ``resolve_node`` (see _resolve_node). The return value's layer
        (template/declaration vs. instance) follows the layer of the
        context passed in. ``select`` lets a service of instances answer
        for a selectable template with the node it was bound to.

        Raises:
          AttributeError: ``context`` has no ``service`` (e.g. inside
            a type definition before a service exists).
          KeyError: named entity not present in ``service.nodes``.
          TypeError: structural failure in dispatch (wrong context
            shape).
        """
        if self.entity == 'SELF':
            return context.SELF()
        if self.entity == 'SOURCE':
            return context.SOURCE()
        if self.entity == 'TARGET':
            return context.TARGET()
        # Not a reserved keyword. Must refer to a node in the
        # context's service (design-time templates or runtime
        # instances depending on what was passed in).
        return self._resolve_node(context, select)


    def _resolve_node(self, context: Any, select: bool = False) -> Any:
        """Resolve a named head, which may name several representations.

        Returns a single entity, or a **list** of them when the head is
        multi-valued. Callers apply themselves across whichever they get; see
        ``apply_to_head``.

        At design time there is one template however many representations it
        will yield, and a declaration lookup wants it: a service of templates
        answers from its ``nodes`` whatever the index. Which representations
        exist, and how they are named, is a runtime fact of the application
        that created them, so a service of instances answers
        ``resolve_node(name, index, select)``: index None follows the
        template's declaration (list-shaped when it may yield several), 'ALL'
        is every representation, an integer selects one. It raises KeyError
        for "no value yet" and InvalidPathError for an index that cannot
        exist (the Ubicity orchestrator's ToscaService.resolve_node).

        TOSCA's part stays here: a computed index ($node_index,
        $relationship_index) is evaluated, and a negative one refused.
        """
        service = context.service
        resolve = getattr(service, 'resolve_node', None)
        if resolve is None:
            return service.nodes[self.entity]

        index = self.index
        if index is not None and index != 'ALL':
            index = self._evaluate_index(context)
            if index < 0:
                raise te.InvalidPathError(
                    "'{}': node index {} is negative; TOSCA indexes count from 0"
                    .format(self.entity, index))
        return resolve(self.entity, index, select)


    def _evaluate_index(self, context: Any) -> int:
        """The index as an integer, evaluating it when it is a function.

        Validated through the builtin integer type, which is what makes a
        computed index -- ``$node_index``, ``$relationship_index`` -- usable
        where the BNF allows only a literal.
        """
        if isinstance(self.index, int):
            return self.index
        # Validate then evaluate, as the requirement branch of
        # ``node.get_attribute_or_property_value`` and ``extract_path_value``
        # both do. Validation is not a formality here: it is what turns the
        # declared value into the form ``evaluate_value`` expects, and skipping
        # it makes a computed index behave differently from the identical one
        # written after a requirement name.
        integer_type = builtin_types.get('integer')
        declaration = integer_type.create_declaration(name='node_index')
        validated = declaration.validate_value(context, self.index)
        return declaration.evaluate_value(context, validated)


    def get_entity_declaration(self, context: Any) -> Any:
        """Find the declaration for the entity at the head of this path.

        Returns the design-time entity (template or declaration);
        the caller walks the sub_entity portion themselves.

        Raises:
          AttributeError: no service context (e.g. inside a type
            definition before a service exists).
          KeyError: named entity not present in ``context.service.nodes``.
          TypeError: structural failure in dispatch (wrong context
            shape).
        """
        return self._resolve_head(context)


    #######################################################################################
    # methods to the entity specified by path
    #######################################################################################

    def get_entity(self, instance: Any) -> Any:
        """Find the runtime entity at the head of this path.

        ``instance`` must be a runtime entity: its ``service`` answers
        ``resolve_node`` (see _resolve_node). Unlike a declaration lookup, a
        name the service has no instance for may be answered by a selectable
        template with the node it was bound to (``select``).

        Returns the runtime instance; the caller walks the sub_entity
        portion themselves. Runtime callers may treat KeyError as a
        recoverable "not yet provisioned" signal rather than a structural
        error.

        Raises:
          AttributeError: no service context (e.g. inside a type
            definition before a service exists).
          KeyError: no instance of that name yet, nor a bound selectable
            template.
          InvalidPathError: an index that cannot exist.
          TypeError: structural failure in dispatch (wrong context
            shape).
        """
        return self._resolve_head(instance, select=True)


    def head_yields_list(self, entity_declaration: Any) -> bool:
        """Will this path's head resolve to several entities at runtime?

        The design-time counterpart of what ``_resolve_node`` decides at
        runtime, and it must agree with it or a value will be rejected by the
        very check that is supposed to describe it. An explicit integer or
        computed index selects one; ALL selects every one; and no index at all
        follows the template's own declaration, which is what makes a count of
        ``{$get_input: n}`` yielding 1 a one-element list rather than a scalar.
        """
        # Only a NAMED head has representations to resolve among. SELF, SOURCE
        # and TARGET each name exactly one entity, and ``_resolve_head``
        # dispatches them before ``_resolve_node`` is ever reached -- so the
        # rule below must not be applied to them, or design time disagrees with
        # runtime. It matters because a relationship declaration carries a
        # ``supports_multiple`` of its own, meaning "this requirement allows
        # several relationships", which is a different question from how many
        # entities this path's head resolves to.
        if self.entity in ('SELF', 'SOURCE', 'TARGET'):
            return False
        supports_multiple = getattr(entity_declaration, 'supports_multiple', None)
        multiple = bool(supports_multiple and supports_multiple())

        # A qualifier -- an index or ALL -- selects among representations, which
        # presupposes there may be more than one. A template that declares no
        # count declares exactly one, so qualifying it is a category error
        # rather than a one-element list or a redundant index 0. Saying so at
        # validation is worth more than quietly answering.
        if self.index is not None and not multiple:
            raise te.InvalidPathError(
                "'{}': {} requires a node template that may yield several "
                "representations; this one yields exactly one".format(
                    self.entity, 'ALL' if self.index == 'ALL' else 'an index'))
        if self.index == 'ALL':
            return True
        if self.index is not None:
            return False
        return multiple


    def apply_to_head(self, head: Any, read: Any) -> Any:
        """Apply ``read`` to the head entity, or to each of several.

        A path whose head names a counted node template resolves to a list, and
        every caller that walks ``sub_entity`` has to read across it. Mirrors
        what the requirement branch of ``node.get_attribute_or_property_value``
        already does across the relationships of one requirement.
        """
        if isinstance(head, list):
            return [read(entity) for entity in head]
        return read(head)


    #######################################################################################
    # methods to upgrade the TOSCA path
    #######################################################################################

    def upgrade(self, context: Any) -> list[Any]:
        """Upgrade this TOSCA path to Version 2.0 syntax within the provided
        context.
        """
        try:
            entity = self.get_entity_declaration(context)
            self.sub_entity = entity.upgrade_tosca_path(self.sub_entity)
        except Exception as e:
            # Soft failure: the validator runs after upgrade and will
            # surface the real diagnostic. Logged at debug so 1.3
            # ingestion doesn't emit spurious ERROR lines for paths
            # that couldn't be upgraded but will be reported properly
            # downstream.
            logger.debug("Unable to upgrade %s: %s", str(self.sub_entity), str(e))
        # All done
        return self.expression
