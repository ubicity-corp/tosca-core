"""
Module definining Tosca Function declaration entity
"""
from __future__ import annotations

__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2022-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Typing support
from typing import Any, Optional

# Logging support
import logging
logger: logging.Logger = logging.getLogger(__name__)

# Database support
from tosca_core import db

# Exception support
import tosca_core.models.exceptions as te

# The evaluator for functions that carry implementation artifacts: one an
# embedding application installs, or the core's for Python ones
from tosca_core import extensions

# SQL Alchemy support
from sqlalchemy.orm import backref
from sqlalchemy.orm.collections import attribute_mapped_collection
from sqlalchemy.ext.orderinglist import ordering_list

# Support for TOSCA keywords that are shared between all entities
import tosca_core.models.entity
import tosca_core.models.artifact

# Cached lookups for TOSCA built-in data types
from tosca_core.models import builtin_types

# Support for workflow inputs
from tosca_core.models.workflow_template import ToscaWorkflowTemplate

# Tosca Path support
from tosca_core.models.path import ToscaPath, extract_path_value

# For resolving templated types
from tosca_core.models.type import lowest_common_ancestor

# Python implementations of the TOSCA built-in profile functions
from tosca_core.builtin import functions as _builtin_functions

################################################################################
# Built-in function registry
################################################################################

# Maps (function name, signature position) -> Python callable in
# tosca_core.builtin.functions for every function defined in the TOSCA
# built-in profile that is not handled by the 'intrinsics' execute_*
# methods on ToscaSignature. The signature position is needed because
# several functions (has_suffix, has_prefix, contains, has_all_entries,
# has_any_entry, concat, length, in_range, and the arithmetic /
# comparison families) provide multiple signatures, some of which
# require distinct implementations.
_BUILTIN_IMPLEMENTATIONS = {
    # Boolean logic
    ('and', 0):               _builtin_functions.and_,
    ('or', 0):                _builtin_functions.or_,
    ('xor', 0):               _builtin_functions.xor_,
    ('not', 0):               _builtin_functions.not_,
    # Comparisons (equal/valid_values use <T>, so they have a single
    # signature; the ordered comparisons have one signature per
    # supported concrete type)
    ('equal', 0):             _builtin_functions.equal,
    ('valid_values', 0):      _builtin_functions.valid_values,
    ('has_entry', 0):         _builtin_functions.has_entry,
    ('has_entry', 1):         _builtin_functions.has_entry,
    ('greater_than', 0):      _builtin_functions.greater_than,
    ('greater_than', 1):      _builtin_functions.greater_than,
    ('greater_than', 2):      _builtin_functions.greater_than,
    ('greater_than', 3):      _builtin_functions.greater_than,
    ('greater_than', 4):      _builtin_functions.greater_than,
    ('greater_than', 5):      _builtin_functions.greater_than,
    ('greater_or_equal', 0):  _builtin_functions.greater_or_equal,
    ('greater_or_equal', 1):  _builtin_functions.greater_or_equal,
    ('greater_or_equal', 2):  _builtin_functions.greater_or_equal,
    ('greater_or_equal', 3):  _builtin_functions.greater_or_equal,
    ('greater_or_equal', 4):  _builtin_functions.greater_or_equal,
    ('greater_or_equal', 5):  _builtin_functions.greater_or_equal,
    ('less_than', 0):         _builtin_functions.less_than,
    ('less_than', 1):         _builtin_functions.less_than,
    ('less_than', 2):         _builtin_functions.less_than,
    ('less_than', 3):         _builtin_functions.less_than,
    ('less_than', 4):         _builtin_functions.less_than,
    ('less_than', 5):         _builtin_functions.less_than,
    ('less_or_equal', 0):     _builtin_functions.less_or_equal,
    ('less_or_equal', 1):     _builtin_functions.less_or_equal,
    ('less_or_equal', 2):     _builtin_functions.less_or_equal,
    ('less_or_equal', 3):     _builtin_functions.less_or_equal,
    ('less_or_equal', 4):     _builtin_functions.less_or_equal,
    ('less_or_equal', 5):     _builtin_functions.less_or_equal,
    ('matches', 0):           _builtin_functions.matches,
    # Boolean list/map/string predicates
    ('has_suffix', 0):        _builtin_functions.has_suffix_string,
    ('has_suffix', 1):        _builtin_functions.has_suffix_list,
    ('has_prefix', 0):        _builtin_functions.has_prefix_string,
    ('has_prefix', 1):        _builtin_functions.has_prefix_list,
    ('contains', 0):          _builtin_functions.contains_string,
    ('contains', 1):          _builtin_functions.contains_list,
    ('has_key', 0):           _builtin_functions.has_key,
    ('has_all_entries', 0):   _builtin_functions.has_all_entries_list,
    ('has_all_entries', 1):   _builtin_functions.has_all_entries_map,
    ('has_all_keys', 0):      _builtin_functions.has_all_keys,
    ('has_any_entry', 0):     _builtin_functions.has_any_entry_list,
    ('has_any_entry', 1):     _builtin_functions.has_any_entry_map,
    ('has_any_key', 0):       _builtin_functions.has_any_key,
    # String / list / map
    ('length', 0):            _builtin_functions.length,
    ('length', 1):            _builtin_functions.length,
    ('length', 2):            _builtin_functions.length,
    ('concat', 0):            _builtin_functions.concat_string,
    ('concat', 1):            _builtin_functions.concat_list,
    ('token', 0):             _builtin_functions.token,
    ('join', 0):              _builtin_functions.join,
    # Set
    ('union', 0):             _builtin_functions.union,
    ('intersection', 0):      _builtin_functions.intersection,
    # Arithmetic (one signature per supported numeric / scalar type)
    ('sum', 0):               _builtin_functions.sum_,
    ('sum', 1):               _builtin_functions.sum_,
    ('sum', 2):               _builtin_functions.sum_,
    ('difference', 0):        _builtin_functions.difference,
    ('difference', 1):        _builtin_functions.difference,
    ('difference', 2):        _builtin_functions.difference,
    ('product', 0):           _builtin_functions.product,
    ('product', 1):           _builtin_functions.product,
    ('product', 2):           _builtin_functions.product,
    ('product', 3):           _builtin_functions.product,
    ('quotient', 0):          _builtin_functions.quotient,
    ('quotient', 1):          _builtin_functions.quotient,
    ('quotient', 2):          _builtin_functions.quotient,
    ('quotient', 3):          _builtin_functions.quotient,
    ('quotient', 4):          _builtin_functions.quotient,
    ('quotient', 5):          _builtin_functions.quotient,
    ('remainder', 0):         _builtin_functions.remainder,
    ('remainder', 1):         _builtin_functions.remainder,
    ('remainder', 2):         _builtin_functions.remainder,
    ('round', 0):             _builtin_functions.round_,
    ('floor', 0):             _builtin_functions.floor,
    ('ceil', 0):              _builtin_functions.ceil,
    # Scalar
    ('from_scalar', 0):       _builtin_functions.from_scalar,
    ('to_scalar', 0):         _builtin_functions.to_scalar,
    # Range
    ('in_range', 0):          _builtin_functions.in_range,
    ('in_range', 1):          _builtin_functions.in_range,
    ('in_range', 2):          _builtin_functions.in_range,
}

# Set of function names that have at least one built-in implementation
# in the registry above. Derived from _BUILTIN_IMPLEMENTATIONS so the
# two stay in lockstep.
_INTERNAL_FUNCTION_NAMES = frozenset(name for (name, _) in _BUILTIN_IMPLEMENTATIONS)

################################################################################
# Helper functions
################################################################################

# Parse a resolved function key into (signature_id, type_id).
def parse_function_key(key: Any) -> Optional[tuple[int, Optional[int]]]:
    """Parse a resolved function key into (signature_id, type_id).

    A resolved function key is ``$(sig_id)`` or -- when the matched signature resolved a
    templated type <T> -- ``$(sig_id:type_id)``, both DB ids. ``type_id`` is None when
    absent. Returns None when ``key`` is not a resolved function key. Both forms are
    accepted so old (``$(sig_id)``) and new expressions coexist.
    """
    if not (isinstance(key, str) and len(key) >= 4 and
            key[0] == '$' and key[1] == '(' and key[-1] == ')'):
        return None
    parts = key[2:-1].split(':')
    if len(parts) == 1 and parts[0].isdigit():
        return (int(parts[0]), None)
    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
        return (int(parts[0]), int(parts[1]))
    return None

# Check if a key is a function signature
def is_function_key(key: str) -> bool:
    return parse_function_key(key) is not None

# Check if a value is a (resolved) function
def is_function(value: Any) -> bool:
    try:
        [(key, args)] = list(value.items())
        return is_function_key(key)
    except (AttributeError, ValueError):
        # Not formatted as a function
        return False

# Check if a list contains function values
def has_functions(args: list[Any]) -> bool:
    for arg in args:
        if is_function(arg): return True
    return False

# Look up a (resolved templated) data type by its DB id.
def get_data_type_by_id(type_id: int) -> Any:
    """Return the ToscaType with the given DB id, or None. Used to rehydrate the
    resolved <T> type cached in a ``$(sig_id:type_id)`` function key. Best-effort:
    None (e.g. a dangling id after a re-onboard) triggers a live re-resolution at eval.
    """
    from tosca_core.models.type import ToscaType
    return ToscaType.query.filter(ToscaType.id == type_id).one_or_none()

# Rewrite resolved function keys back to readable names, for DISPLAY ONLY.
def resolve_function_names(value: Any) -> Any:
    """Recursively rewrite resolved function expressions ``{$(sig_id[:type_id]): args}``
    to ``{$<function-name>: args}`` for human-facing output (CLI/REST, logs).

    Best-effort and non-mutating: unrecognized nodes and unresolvable ids are left as-is,
    and it NEVER raises. The result is for reading only -- it is not a valid resolved
    expression (a name needs re-resolution; the id is already resolved), so do not feed it
    back into the engine.
    """
    try:
        if isinstance(value, dict):
            if len(value) == 1:
                (k, v), = value.items()
                parsed = parse_function_key(k)
                if parsed is not None:
                    sig_id, _ = parsed
                    try:
                        name = get_signature(sig_id).function.name
                        return {'$' + name: resolve_function_names(v)}
                    except Exception:
                        pass  # dangling id -> keep the raw node
            return {k: resolve_function_names(v) for k, v in value.items()}
        if isinstance(value, list):
            return [resolve_function_names(v) for v in value]
        return value
    except Exception:
        return value


def refuse_tosca_1_3_path_head(function_name: str, args: list[Any], context: Any) -> None:
    """Refuse a path that starts at TARGET or SOURCE in a TOSCA 2.0 file.

    TOSCA 2.0 starts a path at SELF or a node's symbolic name (§10.3); the
    TOSCA 1.3 heads TARGET and SOURCE became SELF, TARGET and SELF, SOURCE.
    A 1.x file keeps them. So does an entity whose version is unknown, which
    is not refused on a guess.

    Raises:
      ValueError: naming the path and its TOSCA 2.0 spelling
    """
    if not args or args[0] not in ('TARGET', 'SOURCE'):
        return
    try:
        version = context.tosca_version
    except Exception:
        return
    if not version or version.startswith('tosca_simple_yaml'):
        return
    written = ', '.join(str(arg) for arg in args)
    raise ValueError(f"${function_name}: [{written}]: TOSCA 2.0 starts a path at SELF or a "
                     f"node's name; write [SELF, {written}]")


class _PrettyFunctions:
    """Lazy display wrapper: ``str()`` renders a value with resolved function keys
    rewritten to names (see resolve_function_names). Lazy on purpose -- Python logging
    only stringifies args of records it actually emits, so wrapping a value in this costs
    nothing when the log level is suppressed. Never raises."""
    __slots__ = ('_value',)

    def __init__(self, value: Any) -> None:
        self._value = value

    def __str__(self) -> str:
        try:
            return str(resolve_function_names(self._value))
        except Exception:
            return str(self._value)


def pretty(value: Any) -> _PrettyFunctions:
    """Wrap a value so its ``str()`` shows ``$<function-name>`` instead of ``$(sig_id)``.
    For log messages: ``logger.error("... '%s'", pretty(value))``."""
    return _PrettyFunctions(value)

################################################################################
# ToscaSignature class
################################################################################
    
class ToscaSignature(db.Model):
    """A ToscaSignature object defines a signature for a named function in
    a Tosca profile.
    """

    ################################################################################
    # Keys
    ################################################################################
    
    # Primary key
    id =             db.Column(db.Integer, primary_key=True)

    # Foreign keys
    _function_id =   db.Column(db.Integer,
                               db.ForeignKey('tosca_function_declaration.id'),
                               nullable=True)
    
    ################################################################################
    # Fields
    ################################################################################

    # Function signatures are kept in an ordered list. The 'position'
    # field tracks this signature's position in the list.
    position =       db.Column(db.Integer)

    _description =   db.Column(db.String, nullable=True)
    _meta_data =     db.Column(db.PickleType, nullable=True)
    _variadic =      db.Column(db.Boolean, nullable=True)
    @property
    def variadic(self) -> bool:
        if self._variadic == None:
            # Default is false
            return False
        else:
            return self._variadic

    ################################################################################
    # Relationships
    ################################################################################

    arguments =     db.relationship('ToscaPropertyDeclaration',
                                     primaryjoin="and_(ToscaSignature.id==ToscaPropertyDeclaration._signature_id,"
                                     "ToscaPropertyDeclaration.role=='INPUT')",
                                     collection_class=ordering_list('position'),
                                     order_by='ToscaPropertyDeclaration.position',
                                     back_populates='_containing_function',
                                     overlaps='result')

    result =         db.relationship('ToscaPropertyDeclaration',
                                     primaryjoin="and_(ToscaSignature.id==ToscaPropertyDeclaration._signature_id,"
                                     "ToscaPropertyDeclaration.role=='OUTPUT')",
                                     uselist=False,
                                     back_populates='_containing_function',
                                     overlaps='arguments')

    # Implementation artifacts (primary + dependencies). Same shape as
    # ToscaOperationTemplate.artifacts so user-defined function
    # implementations follow TOSCA v2.0 operation-implementation grammar.
    artifacts =     db.relationship('ToscaArtifact',
                                     foreign_keys='ToscaArtifact._signature_id',
                                     collection_class=ordering_list('position'),
                                     order_by='ToscaArtifact.position',
                                     backref=backref('_containing_signature', uselist=False),
                                     cascade='all')

    
    ################################################################################
    # Model navigation
    ################################################################################

    @property
    def profile(self) -> Any:
        """Get profile from our function.
        """
        if self.function:
            return self.function.profile
        else:
            error = "No profile found for function signature"
            raise te.ModelCorruptionError(error)
        
    ################################################################################
    # Function expression for the specified arguments
    ################################################################################

    def function_expression(self, args: list[Any], resolved_type: Optional[Any] = None) -> dict[str, list[Any]]:
        # Re-emit a (resolved) function as its stored '$(sig_id[:type_id])' expression.
        # Callers that defer evaluation (no inputs / no tosca path) re-emit the function
        # to be evaluated later, so the cached resolved <T> type MUST survive the round
        # trip -- otherwise the later eval re-resolves it (a cache miss). resolved_type is
        # the per-call-site type (the signature can't hold it); None / id-less -> no suffix.
        type_suffix = ''
        if resolved_type is not None and resolved_type.id is not None:
            type_suffix = ':' + str(resolved_type.id)
        key = '$(' + str(self.id) + type_suffix + ')'
        return {key: args }
        
    ################################################################################
    # ToscaSignature Constructor
    ################################################################################

    def __init__(self,
                 arguments: Optional[list[Any]] = None,
                 optional_arguments: Optional[list[Any]] = None,
                 result: Optional[Any] = None,
                 variadic: Optional[bool] = None,
                 implementation: Optional[dict[str, Any]] = None,
                 line: Optional[int] = None,
                 description: Optional[str] = None,
                 meta_data: Optional[dict[str, Any]] = None,
                 **kwargs: Any
    ) -> None:
        # First, call superclass constructor
        super(ToscaSignature, self).__init__(**kwargs)

        # Store line number as transient attribute
        if line != None: self.line = line
        if description: self._description = description
        if meta_data: self._meta_data = meta_data

        # ToscaSignature-specific initialization
        if arguments: self.arguments = arguments
        if optional_arguments:
            for parameter in optional_arguments:
                parameter._required = False
            self.arguments.extend(optional_arguments)
        if result: self.result = result
        self.implementation = implementation
        if variadic != None: self._variadic = variadic

    # Map TOSCA "operation implementation" grammar onto the artifacts
    # relationship (same pattern as ToscaOperationTemplate).
    @property
    def implementation(self) -> dict[str, Any]:
        if self.artifacts:
            implementation: dict[str, Any] = dict()
            implementation['primary'] = self.artifacts[-1]
            implementation['dependencies'] = self.artifacts[:-1]
        else:
            raise AttributeError(
                "Signature for '{0}' does not have 'implementation' attribute".format(
                    self.function.name if self.function else '<unknown>'))
        return implementation

    @implementation.setter
    def implementation(self, value: Optional[dict[str, Any]]) -> None:
        if value is None:
            return
        try:
            if value['dependencies']:
                self.artifacts = value['dependencies']
        except KeyError:
            pass
        try:
            if value['primary']:
                self.artifacts.append(value['primary'])
        except KeyError:
            pass


    ################################################################################
    # Result declaration methods
    ################################################################################

    def get_result_declaration(self, context: Any, args: list[Any], value_declaration: Optional[Any] = None) -> Optional[Any]:
        """Get the property declaration of the result returned by this
        signature within the provided context:
        - If the signature declares a result, return that result
          declaration.
        - If not, dynamically determine result declarations for the
          following 'intrinsic' functions:
          - value
          - get_input
          - get_attribute
          - get_property
          - get_artifact
        - In all other cases, return None
        Args:
          context(ToscaTemplate, ToscaDeclaration, or Toscatype):
            context within which to get the result declaration
          args(list of Python values): function arguments to use when
            finding the result declaration for this function signature
          value_declaration(ToscaPropertyDeclaration): the property
            declaration for the result of the $value function within
            the provided context. This property declaration is also
            used for resolving the templated type <T> in function
            signatures.
        Returns:
          ToscaPropertyDeclaration: declaration for the result
            returned by the function (or None if no result declaration
            is defined)
        Raises:
          ValueError: for invalid function arguments
        """
        # For the following functions, determine the result
        # declaration dynamically.
        if self.function.name == 'value':
            return self.get_result_for_value(context, args, value_declaration)
        if self.function.name == 'get_input':
            return self.get_result_for_get_input(context, args)
        if self.function.name == 'get_attribute':
            return self.get_result_for_get_attribute(context, args)
        if self.function.name == 'get_property':
            return self.get_result_for_get_property(context, args)
        if self.function.name == 'get_artifact':
            return self.get_result_for_get_artifact(context, args)
        
        # For all other functions, return the resolved result
        # declaration defined in this signature.  Note that the result
        # declaration can be None.
        if self.result:
            # Resolve abstract type based on function arguments
            try:
                resolved_type = self.resolve_templated_type(context, args)
                if resolved_type:
                    templated_declaration = resolved_type.create_declaration('<template>')
                else:
                    templated_declaration = None
                if templated_declaration:
                    list_type = builtin_types.get('list')
                    map_type = builtin_types.get('map')
                    if self.result.has_templated_type():
                        return templated_declaration
                    elif self.result.has_type(list_type):
                        try:
                            entry_schema = self.result.entry_schema
                            if entry_schema.has_templated_type():
                                result = list_type.create_declaration("result")
                                result._entry_schema = templated_declaration
                                return result
                        except Exception:
                            # No entry schema
                            logger.debug("No entry schema, but continuing operation.")
                            #pass
                    elif self.result.has_type(map_type):
                        try:
                            entry_schema = self.result.entry_schema
                            if entry_schema.has_templated_type():
                                result = map_type.create_declaration("result")
                                result._entry_schema = templated_declaration
                                return result
                        except Exception:
                            # No entry schema
                            logger.debug("No entry schema, but continuing operation.")
                            #pass
            except Exception as e:
                logger.error("Error resolving abstract type: %s", str(e))
                raise te.SignatureNotFound(f"'${self.function.name}': no matching signature")

        # No templated types found
        return self.result

        
    def get_result_for_value(self, context: Any, args: list[Any], value_declaration: Optional[Any] = None) -> Optional[Any]:
        """Get the result declaration for the given get_input function within
        the provided context. Note that $value should only ever be
        used for validation expressions in a property declaration or
        data type, and 'context' is expected to be the property type
        or property declaration that contains these validation
        expressions.

        Args:
          context(ToscaTemplate, ToscaDeclaration, or Toscatype):
            context within which to get the result declaration
          args(list of Python values): function arguments to use when
            finding the result declaration for the $value function
          value_declaration(ToscaPropertyDeclaration): the property
            declaration for the result of the $value function within
            the provided context.
        Returns:
          ToscaPropertyDeclaration: declaration for the result
            returned by the function.
        Raises:
          ValueError: for invalid function arguments
        """
        if not context and not value_declaration:
            # $value requires the value declaration for validation
            raise ValueError("$value: no value declaration provided")

        # Get the value declaration
        if not value_declaration:
            from tosca_core.models.property_declaration import ToscaPropertyDeclaration
            from tosca_core.models.data_type import ToscaDataType
            if isinstance(context, ToscaPropertyDeclaration):
                value_declaration = context
            elif isinstance(context, ToscaDataType):
                value_declaration = context.create_declaration('value_declaration')
            else:
                logger.error("Invalid $value context '%s'", context.name, stack_info=True)
                raise ValueError("$value: invalid context {}".format(str(context)))
        
        if not args:
            # No sub-property. Just return the value declaration
            return value_declaration

        # Return sub-property if it exists
        try:
            if len(args) == 1:
                return value_declaration.get_property_declaration(args[0])
            else:
                return value_declaration.get_property_declaration(args)
        except Exception as e:
            raise ValueError("$value: unable to find '{}'".format(str(args)))
            

    def get_result_for_get_input(self, context: Any, args: list[Any]) -> Any:
        """Get the result declaration for the given get_input function within
        the provided context:

        Args:
          context(ToscaTemplate, ToscaDeclaration, or Toscatype):
            context within which to get the result declaration
          args(list of Python values): function arguments to use when
            finding the result declaration for the $get_input function
        Returns:
          ToscaPropertyDeclaration: declaration for the result
            returned by the function.
        Raises:
          ValueError: for invalid function arguments
        """
        # Workflows can define their own inputs:
        if isinstance(context, ToscaWorkflowTemplate):
            try:
                return context.get_input_declaration(args)
            except KeyError:
                # not a workflow input
                logger.debug("Not a workflow input, but continuing operation.")
                #pass
            except Exception as e:
                logger.error(str(e))
                #pass
            
        # Get input declaration from the service template in this
        # context.
        try:
            input_declaration = context.service.get_input_declaration(args)
            return input_declaration
        except KeyError:
            # Input not found. Keep the message terse: callers surface
            # this under a JSON path that already names the function and
            # the input, so additional context here would be redundant.
            raise ValueError("not found")


    def get_result_for_get_property(self, context: Any, args: list[Any]) -> Any:
        """Get the result declaration for the given get_property function
        within the provided context:

        Args:
          context(ToscaTemplate, ToscaDeclaration, or Toscatype):
            context within which to get the result declaration
          args(list of Python values): function arguments to use when
            finding the result declaration for the $get_property
            function
        Returns:
          ToscaPropertyDeclaration: declaration for the result
            returned by the function.
        Raises:
          ValueError: for invalid function arguments
        """
        # Parse TOSCA Path. Note that we have already verified that
        # the function has valid arguments.
        refuse_tosca_1_3_path_head('get_property', args, context)
        path = ToscaPath(args, head_index=True)

        # Get the the declaration for the entity referenced by the
        # path in this function
        try:
            entity_declaration = path.get_entity_declaration(context)
            result = entity_declaration.get_property_declaration(path.sub_entity)
        except Exception:
            raise ValueError("$get_property: {} not found".format(args))
        # A head naming several representations returns one value each, so the
        # declared result is a list OF that declaration -- built the same way
        # the requirement traversal builds it, so one expression is not
        # accepted in one position and rejected in another. Deferred import:
        # property_declaration imports this module.
        if path.head_yields_list(entity_declaration):
            from tosca_core.models.property_declaration import as_list_declaration
            return as_list_declaration(result, path.entity, 'properties')
        return result


    def get_result_for_get_attribute(self, context: Any, args: list[Any]) -> Any:
        """Get the result declaration for the given get_attribute function
        within the provided context:

        Args:
          context(ToscaTemplate, ToscaDeclaration, or Toscatype):
            context within which to get the result declaration
          args(list of Python values): function arguments to use when
            finding the result declaration for the $get_attribute
            function
        Returns:
          ToscaPropertyDeclaration: declaration for the result
            returned by the function.
        Raises:
          ValueError: for invalid function arguments
        """
        # Parse TOSCA Path. Note that we have already verified that
        # the function has valid arguments.
        refuse_tosca_1_3_path_head('get_attribute', args, context)
        path = ToscaPath(args, head_index=True)

        # Get the declaration for the entity referenced by the path in
        # this function
        try:
            entity_declaration = path.get_entity_declaration(context)
            result = entity_declaration.get_attribute_declaration(path.sub_entity)
        except Exception:
            raise ValueError("$get_attribute: {} not found".format(args))
        # A head naming several representations returns one value each, so the
        # declared result is a list OF that declaration -- built the same way
        # the requirement traversal builds it, so one expression is not
        # accepted in one position and rejected in another. Deferred import:
        # property_declaration imports this module.
        if path.head_yields_list(entity_declaration):
            from tosca_core.models.property_declaration import as_list_declaration
            return as_list_declaration(result, path.entity, 'attributes')
        return result


    def get_result_for_get_artifact(self, context: Any, args: list[Any]) -> Optional[Any]:
        """Get the result declaration for the given get_artifact function
        within the provided context. The purpose of this function is
        to make sure the arguments point to a valid artifact. The
        result is always a string declaration.

        Args:
          context(ToscaTemplate, ToscaDeclaration, or Toscatype):
            context within which to get the result declaration
          args(list of Python values): function arguments to use when
            finding the result declaration for the $get_artifact
            function
        Returns:
          ToscaPropertyDeclaration: declaration for the result
            returned by the function.
        Raises:
          ValueError: for invalid function arguments
        """
        # Parse TOSCA Path. Note that we have already verified that
        # the function has valid arguments.
        refuse_tosca_1_3_path_head('get_artifact', args, context)
        path = ToscaPath(args, head_index=True)

        # Get the the declaration for the entity referenced by the
        # path in this function.
        try:
            # Does the artifact exist?
            entity_declaration = path.get_entity_declaration(context)
            artifact = entity_declaration.get_artifact(path.sub_entity)
        except ValueError as e:
            # The path reaches no single artifact, and says why
            raise ValueError("$get_artifact: {}: {}".format(args, e))
        except Exception:
            raise ValueError("$get_artifact: {} not found".format(args))
        # Valid artifact. Its signature is a path's, as $get_attribute's is,
        # and declares no result: the result is the artifact's location.
        return builtin_types.get('string').create_declaration()


    def get_result_for_arithmetic_function(self, context: Any, args: list[Any]) -> Any:
        """Get the result declaration for the given arithmetic function within
        the provided context. Arithmetic functions may return scalar
        which needs to be replaced with the actual type.

        Args:
          context(ToscaTemplate, ToscaDeclaration, or Toscatype):
            context within which to get the result declaration
          args(list of Python values): function arguments to use when
            finding the result declaration for the arithmetic
            function
        Returns:
          ToscaPropertyDeclaration: declaration for the result
            returned by the function.
        Raises:
          ValueError: for invalid function arguments

        """
        # Check if result uses scalar type
        if not self.result.type == 'scalar': return self.result

        # Resolve abstract scalar types.
        try:
            resolved_type = self.resolve_templated_type(context, args)
            return resolved_type.create_declaration('<scalar_result>')
        except Exception as e:
            logger.error("Error resolving abstract type: %s", str(e))
            raise te.SignatureNotFound(f"'${self.function.name}': no matching signature")

    ################################################################################
    # Function evaluation methods
    ################################################################################

    def evaluate_value(self, instance: Any, args: list[Any], value: Any = None, **kwargs: Any) -> Any:
        return value

    def evaluate_node_index(self, instance: Any, args: list[Any], **kwargs: Any) -> Any:
        return instance.NODE_INDEX()

    def evaluate_relationship_index(self, instance: Any, args: list[Any], **kwargs: Any) -> Any:
        return instance.RELATIONSHIP_INDEX()

    def evaluate_get_input(self, instance: Any, args: list[Any], no_inputs: bool = False, **kwargs: Any) -> Any:
        """Get the input value referenced by the function within the provided
        context. Note that the context is always an instance.

        Args:
          instance(ToscaInstance): instance for which to evaluate the
            function
        args(list of Python values): function arguments to use when
            evaluating this $get_input function
        Returns:
          value(Python value). This value can be None if the function
            references a non-required input
        Raises:
          None
        """
        # Are we supposed to evaluate inputs?
        if no_inputs: return self.function_expression(args)

        # Evaluate. No head_index: the head here is an INPUT name, and a
        # following integer indexes into that input's value --
        # `{$get_input: [names, $node_index]}` picks an element of a list
        # input, which is not a node index.
        try:
            path = ToscaPath(args)
            input_name = path.entity
            sub_entity = path.sub_entity
        except Exception as e:
            # Single argument 
            input_name = args[0]
            sub_entity = None
        
        # Workflows can define their own inputs
        input = None
        # A running workflow is the one context whose template is a
        # workflow template
        if isinstance(getattr(instance, 'template', None), ToscaWorkflowTemplate):
            try:
                # Get input declarations from the service template
                input_declaration = instance.template.get_input_declaration(input_name)
                # Get the evaluated input value (this is done to support
                # default values)
                input = input_declaration.get_evaluated_value(instance, instance.inputs)
            except (AttributeError, KeyError, TypeError) as e:
                # Must be a non-required input or not a workflow input
                logger.debug("Must be a non-required input or not a workflow input.")
                #pass
        if input == None:
            # Workflow input not provided
            try:
                # Get input declarations from the service template
                input_declaration = instance.service.template.get_input_declaration(input_name)
                # Get the evaluated input value (this is done to support
                # default values)
                input = input_declaration.get_evaluated_value(instance, instance.service.inputs)
            except (AttributeError, KeyError, TypeError) as e:
                # Must be a non-required input or not a workflow input
                logger.debug("Must be a non-required input or not a workflow input.")
                #pass

        # Return the sub_entity if necessary
        if sub_entity:
            try:
                return extract_path_value(instance, input, sub_entity)
            except KeyError:
                # Sub-entity not found. Must be an optional field.
                return None
        else:
            # no sub_entity
            return input

    def evaluate_get_attribute(self, instance: Any, args: list[Any], no_tosca_path: bool = False, **kwargs: Any) -> Any:
        """Evaluate a 'get_attribute' function with the specified instance as
        context.

        Args:
          instance(ToscaInstance): instance for which to evaluate the
            function
        args(list of Python values): function arguments to use when
            evaluating this $get_attribute function
        Returns:
          value(Python value). This value can be None if the function
            references a non-required attribute
        Raises:
          KeyError: if attribute not found
          ValueError: if entity referred to by path is not found
          TypeError: if some other error occurred
        """
        # Don't evaluate if we're not supposed to traverse TOSCA Path
        if no_tosca_path: return self.function_expression(args)
        
        # Parse TOSCA Path. Note that we have already verified that
        # the function has valid arguments.
        path = ToscaPath(args, head_index=True)

        # Get the entity referenced by this path
        entity = path.get_entity(instance)

        # Read across every representation when the head names several.
        return path.apply_to_head(
            entity, lambda e: e.get_attribute(path.sub_entity))

    def evaluate_get_property(self, instance: Any, args: list[Any], no_tosca_path: bool = False, **kwargs: Any) -> Any:
        """Evaluate a 'get_property' function with the specified instance as
        context.

        Args:
          instance(ToscaInstance): instance for which to evaluate the
            function
        args(list of Python values): function arguments to use when
            evaluating this $get_property function
        Returns:
          value(Python value). This value can be None if the function
            references a non-required property
        Raises:
          KeyError: if property not found
          ValueError: if entity referred to by path is not found
          TypeError: if some other error occurred
        """
        # Don't evaluate if we're not supposed to traverse TOSCA Path
        if no_tosca_path: return self.function_expression(args)
        
        # Parse TOSCA Path. Note that we have already verified that
        # the function has valid arguments.
        path = ToscaPath(args, head_index=True)
        # Get the entity referenced by this path
        entity = path.get_entity(instance)

        # Read across every representation when the head names several.
        return path.apply_to_head(
            entity, lambda e: e.get_property(path.sub_entity))

    def evaluate_get_artifact(self, instance: Any, args: list[Any], no_tosca_path: bool = False, **kwargs: Any) -> Any:
        """Evaluate a 'get_artifact' function with the specified instance as
        context.

        Args:
          instance(ToscaInstance): instance for which to evaluate the
            function
        args(list of Python values): function arguments to use when
            evaluating this $get_artifact function
        Returns:
          value(Python value). This value can be None if the function
            references a non-required property

        Raises:
          ValueError: if artifact referred to by path is not found
        """
        # Don't evaluate if we're not supposed to traverse TOSCA Path
        if no_tosca_path: return self.function_expression(args)
        
        # Parse TOSCA Path. Note that we have already verified that
        # the function has valid arguments.
        path = ToscaPath(args, head_index=True)

        # Get the entity referenced by this path
        entity = path.get_entity(instance)

        # Unlike a property or an attribute, an artifact is not read across
        # several representations: this function retrieves the artifact's
        # CONTENT and its result is declared a string, so returning one per
        # representation would contradict the type a template is checked
        # against. Say so rather than return a list nothing expects.
        if isinstance(entity, list):
            raise ValueError(
                "$get_artifact: '{0}' names several node representations; "
                "index one of them".format(path.entity))

        # Get the artifact
        try:
            artifact = entity.get_artifact(path.sub_entity)
        except ValueError as e:
            raise ValueError("Artifact '{0}': {1}".format(path.sub_entity, e))
        except Exception as e:
            raise ValueError("Artifact '{0}' not found".format(path.sub_entity))

        # Retrieve artifact, checked against its checksum where it gives one
        try:
            return artifact.retrieve()
        except Exception as e:
            raise ValueError("unable to retrieve '{0}': {1}".format(path.sub_entity, e))

    def evaluate_if(self, instance: Any, args: list[Any], no_tosca_path: bool = False, resolved_type: Optional[Any] = None, **kwargs: Any) -> Any:
        """Evaluate an '$if' function: return the second argument when the first
        (the condition) evaluates truthy, otherwise the third.

        '$if' is an INTRINSIC rather than a built-in or profile function
        precisely because it must SHORT-CIRCUIT: only the condition and the
        selected branch are evaluated, so the unselected branch may reference
        values that are absent in that case (e.g. an unbound attribute). Ordinary
        functions receive all their arguments already evaluated, which would
        evaluate both branches. As an intrinsic we receive the raw (resolved but
        unevaluated) arguments and evaluate only the ones we choose, using the
        SAME per-argument evaluator (ToscaPropertyDeclaration.evaluate_value) that
        evaluate_function_arguments uses in its loop.

        Args:
          instance(ToscaInstance): instance for which to evaluate the function
          args(list): [condition, then, else] as raw argument expressions
        """
        # Consistent with the other intrinsics: don't evaluate when we are not
        # supposed to traverse TOSCA Path.
        if no_tosca_path:
            return self.function_expression(args, resolved_type)

        # The condition (arg 0) is 'boolean' in every signature, so evaluate it directly.
        condition = self.arguments[0].evaluate_value(instance, args[0], **kwargs)

        # Evaluate ONLY the selected branch. When the matched signature is the templated
        # one its branch parameter is the abstract <T>, which is validation-only -- so we
        # substitute the RESOLVED concrete type before evaluating, exactly as
        # evaluate_function_arguments does; otherwise evaluate_value would try to validate
        # the value against <T> and fail. Concrete signatures need no substitution.
        index = 1 if condition else 2
        parameter = self.arguments[index]
        if parameter.has_templated_type():
            # Prefer the resolved type cached on the resolved expression (passed as a
            # kwarg); resolve live only as a fallback (old / re-serialized expressions).
            if resolved_type is None:
                try:
                    resolved_type = self.resolve_templated_type(instance, args)
                except Exception:
                    resolved_type = None
            if resolved_type is not None:
                parameter = resolved_type.create_declaration('<template>')
        return parameter.evaluate_value(instance, args[index], **kwargs)

    def execute_builtin(self, instance: Any, evaluated_args: list[Any], resolved_type: Optional[Any] = None) -> Any:
        """Execute a built-in TOSCA profile function whose Python
        implementation lives in ``tosca_core.builtin.functions``. The
        implementation is selected by ``(function name, signature
        position)`` since several built-in functions (e.g. has_suffix,
        concat, sum, greater_than) provide multiple signatures with
        distinct implementations.

        Type-aware functions (comparison, arithmetic, valid_values,
        has_entry, from_scalar) need a resolved data type to dispatch
        to the right type-class method. When the function's signature
        does not use the templated type ``<T>``,
        ``resolve_templated_type`` returns None — fall back to the
        declared type of the first argument so those functions still
        get a usable type.
        """
        if resolved_type is None and self.arguments:
            try:
                resolved_type = self.arguments[0].type_entity
            except (AttributeError, IndexError):
                pass
        key = (self.function.name, self.position)
        try:
            implementation = _BUILTIN_IMPLEMENTATIONS[key]
        except KeyError:
            raise NotImplementedError(
                f"no built-in implementation for '{self.function.name}' signature {self.position}"
            )
        return implementation(evaluated_args, resolved_type=resolved_type)

    ################################################################################
    # Maps that drive function evaluation
    ################################################################################

    # Each intrinsic function is evaluated using special-purpose code.
    intrinsics = {
        'value': evaluate_value,
        'get_input': evaluate_get_input,
        'get_attribute': evaluate_get_attribute,
        'get_property': evaluate_get_property,
        'get_artifact': evaluate_get_artifact,
        # '$if' is intrinsic because it must short-circuit (evaluate only the
        # selected branch); see evaluate_if.
        'if': evaluate_if,
        'node_index': evaluate_node_index,
        'relationship_index': evaluate_relationship_index,
    }
    
    def evaluate(self, context: Any, args: list[Any], no_tosca_path: bool = False, value_declaration: Optional[Any] = None, resolved_type: Optional[Any] = None, **kwargs: Any) -> Any:
        """Evaluate the given function for the provided arguments within the
        specified context using the implementation provided by this
        signature.
          
        Args:
          context(ToscaTemplate, ToscaDeclaration, or Toscatype):
            context within which to evaluate the function
          args(list of Python values): function arguments to use when
            evaluating this function signature
        Keyword Args:
          no_tosca_path(bool): if true, do not evaluate functions with
            TOSCA Path arguments.
          value_declaration(ToscaPropertyDeclaration): the property
            declaration for the result of the $value function within
            the provided context. This is used for resolving the
            templated type <T>
        Returns:
          (result): Python value compatible with 'result' declaration.
        Raises:
          SignatureNotFound: when the function signature uses
            templated types that cannot be resolved.
          NotImplementedError: when there is no implementation for the
            function.
        """
        # Each intrinsic function has its own evaluation method that is called
        # directly. Look it up with .get() rather than `[]` + `except KeyError`: a
        # KeyError raised INSIDE an intrinsic -- e.g. get_attribute on a missing
        # attribute, or a nested get in a $if branch -- must propagate as itself, not be
        # mistaken for "not an intrinsic" and retried down the non-intrinsic path (which
        # would surface a confusing NotImplementedError, and for $if would evaluate BOTH
        # branches, defeating the short-circuit).
        evaluator = self.intrinsics.get(self.function.name)
        if evaluator is not None:
            return evaluator(self, context, args, no_tosca_path=no_tosca_path,
                             resolved_type=resolved_type, **kwargs)

        # Other functions may use templated types in their signatures. Prefer the
        # resolved type cached on the resolved expression (passed in as a kwarg -- a
        # per-call-site fact); resolve it live only when we don't have it (an old
        # $(sig_id) expression, a re-serialized function, or a non-templated function,
        # which resolves to None cheaply).
        if resolved_type is None:
            try:
                resolved_type = self.resolve_templated_type(context, args, value_declaration)
            except Exception as e:
                logger.error("Error resolving abstract type: %s", str(e))
                raise te.SignatureNotFound(f"${self.function.name}: no matching signature")
        
        # Evaluate function arguments
        if resolved_type:
            template_declaration = resolved_type.create_declaration('<template>')
        else:
            template_declaration = None
        evaluated_args = self.evaluate_function_arguments(
            context, args, value_declaration=value_declaration,
            template_declaration=template_declaration,
            no_tosca_path=no_tosca_path, **kwargs)

        # We may not be able to evaluate if we're not supposed to
        # traverse TOSCA Path.
        if no_tosca_path and has_functions(evaluated_args):
            return self.function_expression(evaluated_args, resolved_type)

        # If this signature carries its own implementation artifacts
        # (e.g. a profile-defined function), prefer that over the
        # built-in Python implementation.
        if self.artifacts:
            # The core runs no implementation artifact; an embedding
            # application that runs them installs an evaluator
            # (tosca_core.extensions). With none, or one that cannot
            # evaluate this function, it is left unevaluated for a
            # deployment that can
            evaluator = extensions.function_evaluator()
            if evaluator is None:
                return self.function_expression(evaluated_args, resolved_type)
            try:
                result = evaluator(self, context, evaluated_args)
            except extensions.CannotEvaluate:
                return self.function_expression(evaluated_args, resolved_type)
            except Exception as e:
                raise NotImplementedError(f"{self.function.name} not implemented: {str(e)}")
            # A declared result is a contract: the implementation returns a
            # value of it, or the evaluation fails. The presence check relies
            # on this (ToscaFunction._presence).
            if result is None and self.result is not None:
                raise te.ProcessorError(
                    f"${self.function.name} returned no value, though its signature "
                    f"declares a result")
            return result

        # Built-in TOSCA profile functions without a user-supplied
        # implementation; dispatch through execute_builtin.
        if self.function.name in _INTERNAL_FUNCTION_NAMES:
            return self.execute_builtin(context, evaluated_args, resolved_type=resolved_type)

        raise NotImplementedError(f"{self.function.name} not implemented")


    def evaluate_function_arguments(self, context: Any, args: list[Any], template_declaration: Optional[Any] = None, **kwargs: Any) -> list[Any]:
        """Evaluate function arguments using the arguments defined in this
        signature.

        Args:
          context(ToscaInstance): instance for which to evaluate the
            function arguments.
          args(list of Python values): list of function arguments that
            need to be evaluated.
        Keyword Args:
          value(Python value): the value returned by the $value
            function. This is passed as an argument since it cannot be
            retrieved from the context.
          value_declaration(ToscaPropertyDeclaration): Has the
            declaration for the value returned by the $value
            function. This is used in to determine the type of
            templated function arguments. Defaults to None.
          template_declaration(ToscaPropertyDeclaration): declaration
            obtained by resolving the templated type <T>
        Returns:
          list of evaluated values
        Raises:
          None
        """
        list_type = builtin_types.get('list')
        map_type = builtin_types.get('map')
        
        # evaluate each parameter
        evaluated = list()
        count = 0
        for arg in args:
            try:
                parameter = self.arguments[count]
            except IndexError:
                # Must be variadic. Just keep using the last parameter
                parameter = self.arguments[len(self.arguments)-1]
            if template_declaration:
                if parameter.has_templated_type():
                    parameter = template_declaration
                elif parameter.has_type(list_type):
                    try:
                        if parameter.entry_schema.has_templated_type():
                            parameter = list_type.create_declaration("evaluate")
                            parameter._entry_schema = template_declaration
                    except AttributeError as ae:
                        logger.debug(f"{ae}")
                        #pass
                elif parameter.has_type(map_type):
                    try:
                        if parameter.entry_schema.has_templated_type():
                            parameter = map_type.create_declaration("evaluate")
                            parameter._entry_schema = template_declaration
                    except AttributeError as ae:
                        logger.debug(f"{ae}")
                        #pass
            # Evaluate
            evaluated.append(parameter.evaluate_value(context, arg, **kwargs))
            count = count + 1

        # All done
        return evaluated


    ################################################################################
    # Templated type <T> resolution methods
    ################################################################################

    def resolve_templated_type(self, context: Any, args: list[Any], value_declaration: Optional[Any] = None) -> Optional[Any]:
        """If a templated type is used in this signature, resolve the
        templated type into the actual type that should be used for
        the provided function. Note that at this point the list of
        arguments has already been validated, which means that all
        functions used in the list of arguments are valid.

        Args:
          context(ToscaTemplate, ToscaDeclaration, or ToscaType):
            context within which to get the result declaration
          args(list of Python values): list of argument values to use
            when resolving templated type
          value_declaration(ToscaPropertyDeclaration): the property
            declaration for the result of the $value function within
            the provided context.
        Returns:
          (ToscaDataType): data type obtained by resolving the
          templated type <T>. This can be None
        Raises:
          ValueError: if incompatible declarations are found
        """
        # Nothing to resolve if there are no arguments
        if not self.arguments: return None

        # Find base types
        import tosca_core.models.function
        list_type = builtin_types.get('list')
        map_type = builtin_types.get('map')

        # Iterate over arguments
        count = 0
        args_use_template = False
        values_use_functions = False
        resolved_type = None
        for arg in args:
            try:
                argument = self.arguments[count]
            except IndexError:
                # Must be variadic. Just keep using the last argument
                argument = self.arguments[len(self.arguments)-1]
            if argument.has_templated_type():
                args_use_template = True
                try:
                    resolved_type = self.resolve_templated_argument_type(
                        context, arg, resolved_type, value_declaration)
                    values_use_functions = True
                except TypeError as te:
                    logger.debug(f"{te}")
                    #pass
            elif argument.has_type(list_type):
                try:
                    if argument.entry_schema.has_templated_type():
                        args_use_template = True
                        # Is the entire list returned by a function?
                        try:
                            resolved_type = self.resolve_templated_entry_schema_type(
                                context, arg, resolved_type, value_declaration)
                            values_use_functions = True
                        except TypeError:
                            # Not a function argument. Check the list entries themselves.
                            for list_arg in arg:
                                try:
                                    resolved_type = self.resolve_templated_argument_type(
                                        context, list_arg, resolved_type, value_declaration)
                                    values_use_functions = True
                                except TypeError as te:
                                    logger.debug(f"{te}")
                                    #pass
                except AttributeError:
                    logger.debug("No entry schema defined in function argument")
            elif argument.has_type(map_type):
                try:
                    if argument.entry_schema.has_templated_type():
                        args_use_template = True
                        # Is the entire map returned by a function?
                        try:
                            resolved_type = self.resolve_templated_entry_schema_type(
                                context, arg, resolved_type, value_declaration)
                            values_use_functions = True
                        except TypeError:
                            # Not a function argument. Check the map entries themselves.
                            for arg_name, map_arg in arg.items():
                                try:
                                    resolved_type = self.resolve_templated_argument_type(
                                        context, map_arg, resolved_type, value_declaration)
                                    values_use_functions = True
                                except TypeError as te:
                                    logger.debug(f"{te}")
                                    #pass
                except AttributeError:
                    logger.debug("No entry schema defined in function argument")

            count = count + 1

        # Success?
        if not resolved_type and args_use_template and not values_use_functions:
            # Not really an error from the caller's perspective:
            # find_matching_signature walks signatures in order and catches
            # the ValueError so it can try the next one.
            logger.debug("'%s': unable to resolve <T>: no functions in %s",
                         self.function.name, str(args))
            raise ValueError("no functions used in values")

        # All done
        return resolved_type

    def resolve_templated_argument_type(self, context: Any, arg: Any, resolved_type: Optional[Any], value_declaration: Optional[Any]) -> Optional[Any]:
        """Resolve the type for specified argument value within the provided
        context. This assumes that the argument value is a function.

        Args:
          context(ToscaTemplate, ToscaDeclaration, or ToscaType):
            context within which to get the result declaration
          arg(Python value): argument for which to find the type. This
            assumes that this argument value is a function for which
            we retrieve the property declaration of its return value.
          resolved_type(ToscaDataType): the data type with which this
            argument's type has to be compatible. A ValueError will be
            raised if it isn't.
          value_declaration(ToscaPropertyDeclaration): the property
            declaration for the result of the $value function within
            the provided context.
        Returns:
          (ToscaDataType): data type obtained by resolving the
          templated type <T>. This can be None
        Raises:
          ValueError: if incompatible declarations are found
          TypeError: if arg does not define a function value
        """
        try:
            # Is this a function argument?
            function = tosca_core.models.function.ToscaFunction(arg, context, value_declaration)
            declaration = function.get_result_declaration(context, value_declaration)
            # Make sure resolved type is compatible with the type that
            # has been found so far.
            resolved_type = lowest_common_ancestor(resolved_type, declaration.type_entity)
            if not resolved_type:
                raise ValueError("incompatible abstract types")
        except TypeError:
            # Not a function argument. Re-raise the exception
            raise
        except Exception as e:
            logger.error("Error resolving <T> argument in value: %s", str(e), exc_info=False)
            raise ValueError("unable to resolve <T>")
        return resolved_type

    def resolve_templated_entry_schema_type(self, context: Any, arg: Any, resolved_type: Optional[Any], value_declaration: Optional[Any]) -> Optional[Any]:
        """Resolve the type for the entry schema of the list argument within
        the provided context. This assumes that the argument value is
        a function that returns a list or a map.

        Args:
          context(ToscaTemplate, ToscaDeclaration, or ToscaType):
            context within which to get the result declaration
          arg(Python value): argument for which to find the type. This
            assumes that this argument value is a function that
            returns a list or a map for which we retrieve entry schema
            type
          resolved_type(ToscaDataType): the data type with which this
            argument's entry schema type has to be compatible. A
            ValueError will be raised if it isn't.
          value_declaration(ToscaPropertyDeclaration): the property
            declaration for the result of the $value function within
            the provided context.
        Returns:
          (ToscaDataType): data type obtained by resolving the
          templated type <T>. This can be None
        Raises:
          ValueError: if incompatible declarations are found
          TypeError: if arg does not define a function value
        """
        try:
            # Is this a function argument?
            function = tosca_core.models.function.ToscaFunction(arg, context, value_declaration)
            declaration = function.get_result_declaration(context, value_declaration)
            # Make sure resolved type is compatible with the type that
            # has been found so far.
            resolved_type = lowest_common_ancestor(resolved_type, declaration.entry_schema.type_entity)
            if not resolved_type:
                raise ValueError("incompatible abstract types")
        except TypeError:
            # Not a function argument. Re-raise the exception
            raise
        except Exception as e:
            logger.error("Error resolving <T> argument in entry schema: %s", str(e))
            raise ValueError("unable to resolve <T>")
        return resolved_type


    ################################################################################
    # Argument matching methods
    ################################################################################

    def do_arguments_match(self, context: Any, args: list[Any], template_declaration: Optional[Any], value_declaration: Optional[Any], **kwargs: Any) -> bool:
        """Check if function arguments match the argument declarations of this
        signature.

        Args:
          context(ToscaTemplate, ToscaDeclaration, or Toscatype):
            context within which to validate the function expression.
          args(list of Python values): list of argument values for
            which to check if this signature matches.
          template_declaration(ToscaPropertyDeclaration): declaration
            obtained by resolving the templated type <T>
        Returns:
          Boolean
        Raises:
          None
        """
        # Does this signature define arguments?
        if not self.arguments:
            if self.variadic:
                # Arbitrary arguments are accepted and not validated.
                return True
            else:
                # No arguments are accepted.
                if args:
                    return False

        # Validate each parameter
        count = 0
        for parameter in self.arguments:
            try:
                # Check each argument individually
                arg = args[count]
                if not self.does_argument_match(context, parameter, arg, template_declaration, value_declaration, **kwargs):
                    return False
            except IndexError:
                # Argument not found. Is this argument optional?
                if parameter.is_required():
                    return False
                else:
                    # No more arguments to validate, since all
                    # arguments after this are optional as well.
                    return True
            except Exception as e:
                logger.error("%s: unable to match arg[%d] value (%s) of type '%s': %s",
                             self.function.name, count, str(args[count]), parameter.type, str(e))
                return False
            count = count + 1
            
        # Are there any variadic arguments to validate?
        while count < len(args):
            if not self.does_argument_match(context, parameter, args[count], template_declaration, value_declaration, **kwargs):
                return False
            count = count + 1

        # All done
        return True


    def does_argument_match(self, context: Any, parameter: Any, arg: Any, template_declaration: Optional[Any], value_declaration: Optional[Any], **kwargs: Any) -> bool:
        """Check if a function argument match the specified argument
        declaration. Note that this method mimics the 'validate_value'
        method in ToscaPropertyDeclaration. The main difference is
        that it allows exceptions to be propagated to the calling
        function.

        Args:
          context(ToscaTemplate, ToscaDeclaration, or Toscatype):
            context within which to validate the function expression.
          parameter(ToscaPropertyDeclaration): argument declaration
            against which to check the argument
          arg(Python value or ToscaFunction): argument value to
            check against the argument declaration.
          template_declaration(ToscaPropertyDeclaration): declaration
            obtained by resolving the templated type <T>
        Returns:
          Boolean

        Raises:
          FunctionNotFound: if one of the arguments specifies a
            function that cannot be found.
          ValueError: if one of the arguments specifies a function
            with an invalid ToscaPath argument
          TypeError: if the parameter uses abstract type <T> and no
            templated type is provided.
        """

        # If the parameter has a abstract type, validate against
        # resolved declaration instead
        list_type = builtin_types.get('list')
        map_type = builtin_types.get('map')

        if parameter.has_templated_type():
            if not template_declaration:
                raise TypeError("no templated type provided")
            parameter = template_declaration
        elif parameter.has_type(list_type):
            try:
                if parameter.entry_schema.has_templated_type():
                    parameter = list_type.create_declaration("validate")
                    parameter._entry_schema = template_declaration
            except AttributeError:
                # No entry schema
                logger.debug("No entry schema")
                #pass
        elif parameter.has_type(map_type):
            try:
                if parameter.entry_schema.has_templated_type():
                    parameter = map_type.create_declaration("validate")
                    parameter._entry_schema = template_declaration
            except AttributeError:
                # No entry schema
                logger.debug("No entry schema")
                #pass

        # Adapted from ToscaPropertyDeclaration.validate_value
        try:
            try:
                # Is the property value a function? For purposes of
                # signature matching, there is no need to validate whether
                # the return value is present.
                expression = parameter.validate_function_value(context, arg,
                                                               value_declaration=value_declaration,
                                                               **kwargs)
            except TypeError:
                # Not a function. Must be an actual (python) property
                # value.
                try:
                    # Does the property have a simple type?
                    expression = parameter.validate_simple_value(context, arg, **kwargs)
                except TypeError:
                    # Must have a complex type.
                    expression = parameter.validate_complex_value(context, arg)
        except Exception as e:
            # Validation failed. Not a match
            return False

        # All done
        return True


################################################################################
# ToscaFunctionDeclaration class
################################################################################
    
class ToscaFunctionDeclaration(tosca_core.models.entity.ToscaEntityMixin, db.Model):
    """A ToscaFunctionDeclaration object defines a named function in a
    Tosca profile.
    """

    ################################################################################
    # Keys
    ################################################################################
    
    # Primary key
    id =           db.Column(db.Integer, primary_key=True)

    # Foreign keys
    _profile_id =  db.Column(db.Integer,
                             db.ForeignKey('tosca_profile.id'),
                             nullable=True)
    
    ################################################################################
    # Relationships
    ################################################################################

    signatures =   db.relationship('ToscaSignature',
                                   foreign_keys='ToscaSignature._function_id',
                                   collection_class=ordering_list('position'),
                                   order_by='ToscaSignature.position',      
                                   backref='function')

    ################################################################################
    # Model Navigation
    ################################################################################

    profile =      db.relationship('ToscaProfile',
                                   foreign_keys='ToscaFunctionDeclaration._profile_id')


    ################################################################################
    # ToscaFunctionDeclarationConstructor
    ################################################################################

    def __init__(self,
                 signatures: Optional[list[ToscaSignature]] = None,
                 **kwargs: Any
    ) -> None:
        # First, call superclass constructor
        super(ToscaFunctionDeclaration, self).__init__(**kwargs)

        # ToscaFunctionDeclaration-specific initialization
        if signatures: self.signatures = signatures


    ################################################################################
    # Signature matching method
    ################################################################################

    def find_matching_signature(self, context: Any, args: list[Any], value_declaration: Optional[Any], **kwargs: Any) -> ToscaSignature:
        """Find the function declaration's signature that matches the
        arguments of this function within the provided
        context. Returns the first signature for which the function
        arguments are valid.

        Args:
          context(ToscaTemplate, ToscaDeclaration, or Toscatype):
            context within which to find the matching signature
          args(list of Python values): list of argument values to use
            when trying to find a matching signature
          value_declaration(ToscaPropertyDeclaration): the property
            declaration for the result of the $value function within
            the provided context. This property declaration is used
            for validation of the function arguments as well as for
            resolving the templated type <T> in function signatures.
        Returns:
          (ToscaSignature, resolved_type): the matched signature and the type its
            templated <T> resolved to (None for a non-templated signature). The caller
            caches the resolved type in the resolved expression so eval need not re-derive
            it -- it is a per-call-site fact and cannot live on the (shared) signature.
        Raises:
          SignatureNotFound: if no matching signature is found for the
            provided arguments
        """
        # Use the first signature that matches.
        for signature in self.signatures:
            # First, resolve templated type if the signature uses it.
            try:
                resolved_type = signature.resolve_templated_type(context, args, value_declaration)
                if resolved_type:
                    template_declaration = resolved_type.create_declaration('<template>')
                else:
                    template_declaration = None
            except Exception as e:
                # Templated type cannot be resolved. This must not be
                # a matching signature.
                logger.debug(f"Templated type cannot be resolved - unmatching signature")
                continue
            # Check to see if function arguments match.
            if signature.do_arguments_match(context, args, template_declaration, value_declaration, **kwargs):
                # We found a matching signature. Return it together with the resolved
                # type so the caller can cache it. Don't try any more signatures.
                return signature, resolved_type

        # No signature found
        raise te.SignatureNotFound(f"function '${self.name}': no matching signature found")


############################
# SIGNATURE LOOKUP FUNCTIONS
############################

def get_signature(signature_id: int) -> ToscaSignature:
    """Return function signature by id.

    Args:
      signature_id(int): id of the signature

    Raises:
      sqlalchemy.orm.exc.NoResultFound: when no signature found with
        the specified signature id
      sqlalchemy.orm.exc.MultipleResultsFound: when multiple
        signatures found with the specified signature id (should never
        happen)
    """
    signature = ToscaSignature.query.filter(
        ToscaSignature.id == signature_id
    ).one()
    return signature
