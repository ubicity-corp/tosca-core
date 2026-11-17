"""
Module definining Tosca Functions
"""
from __future__ import annotations

__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2014-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Typing support
from typing import Any, Optional

# Logging support
import logging
logger: logging.Logger = logging.getLogger(__name__)

# Exception support
import tosca_core.models.exceptions as te
import tosca_core.models.recognized_names as rn

# Function signature support
import tosca_core.models.function_declaration as fd

# Tosca Path support
from tosca_core.models.path import ToscaPath
import tosca_core.models.presence as presence
from tosca_core import extensions

# Cached lookups for TOSCA built-in data types
from tosca_core.models import builtin_types

# Backward compatibility support
V1_INTRINSIC_FUNCTIONS: list[str] = [
    'get_input',
    'get_attribute',
    'get_property',
    'get_artifact',
    'concat',
    'token',
    'join'
]


# The built-in functions whose result has a value exactly when every
# argument has one.
_ALL_ARGUMENTS = frozenset(('concat', 'join', 'token', 'union', 'intersection', 'length'))


def _target_type(requirement: Any) -> Any:
    """The node type a requirement template or declaration names as its
    target: the template's own, else its declaration's. None when neither
    names one."""
    query = getattr(requirement, 'get_target_query_node_type', None)
    if query is not None:
        return query()
    try:
        return requirement.target_node_type
    except AttributeError:
        return None

def _navigation_length(tokens: list) -> int:
    """How many leading tokens of a path below its head navigate to the entity
    whose property or attribute it reads -- requirements with their index and
    TARGET or SOURCE, and capabilities -- before the first token that names
    the value. A capability is named, except right after a requirement, where
    CAPABILITY stands for the capability the relationship is bound to."""
    i = 0
    at_relationship = False
    while i < len(tokens):
        token = tokens[i]
        if token == 'RELATIONSHIP':
            i += 2
            if i < len(tokens) and (isinstance(tokens[i], int) or tokens[i] == 'ALL'):
                i += 1
            at_relationship = True
        elif token in ('TARGET', 'SOURCE'):
            i += 1
            at_relationship = False
        elif token == 'CAPABILITY':
            i += 1 if at_relationship else 2
            at_relationship = False
        else:
            break
    return i


def _relationship_kind(relationship: Any) -> Optional[str]:
    """The kind of a relationship type, or of the type a requirement
    declaration or template names. None when it cannot be found."""
    for get in (lambda: relationship.get_kind(),
                lambda: relationship.type_entity.get_kind(),
                lambda: relationship.declaration.type_entity.get_kind()):
        try:
            return get()
        except Exception:
            continue
    return None


def _written_before_read(node: Any, tokens: list, through: Optional[list]) -> bool:
    """Whether the attribute at 'tokens' of 'node' is written by an
    operation certain to have run before the operation reading it.

    Which operations those are depends on the order an application runs
    operations in, which TOSCA does not define, so the application answers
    through the attribute-written check it installs
    (tosca_core.extensions.set_attribute_written_check). With none, an
    attribute is never guaranteed this way.

    'through' is None when the path does not start from SELF, SOURCE or
    TARGET, and only a read by an operation is asked about: the operation is
    what orders the read.
    """
    if through is None or node is None or not tokens:
        return False
    check = extensions.attribute_written_check()
    if check is None:
        return False
    reader = presence.read_by()
    if reader is None:
        return False
    reader = (rn.interface_name(reader[0]) if reader[0] else reader[0],
              rn.operation_name(reader[1]) if reader[1] else reader[1])
    return bool(check(node, list(tokens), list(through), reader))


class ToscaFunction(object):
    """The Tosca function class parses an expression as a TOSCA
    function. It separates out the function name and an array of
    function arguments.
    """

    @property
    def expression(self) -> dict[str, list[Any]]:
        """Return the (possibly resolved) function expression"""
        return {self.key: self.args }

    def __str__(self) -> str:
        """Render as ``$<name>[<arg>, <arg>, ...]`` for diagnostics."""
        args = ', '.join(str(a) for a in self.args)
        return f"${self.name}[{args}]"

    ################################################################################
    # ToscaFunction initialization methods
    ################################################################################

    def __init__(self, function: Any, context: Optional[Any] = None, value_declaration: Optional[Any] = None,
                 **kwargs: Any) -> None:
        """The ToscaFunction constructor parses a function expression into a
        function key and a list of function arguments.

        - For fully resolved functions, the function key has the
          format '$(signature_id)'. The signature_id is used to
          retrieve the corresponding signature object for the
          function.
        - For unresolved functions, the function key has the format
          '$function_name' (where function_name could include a
          namespace prefix). The function name is used to lookup the
          corresponding function declaration within the provided
          context.
        - For v1.3 functions, the function key has the format
          'function_name' where function_name must be in the list of
          known V1_INTRINSIC_FUNCTIONS.
        - Function arguments are expected to be a list. The
          constructor creates a single entry list if necessary.

        Args:
          function(dict): function statement to parse into a
            ToscaFunction object
          context: context within which to resolve function name. The
            context is not used for fully resolved functions, but is
            required for unresolved functions to look up the function
            declaration for this function. This function declaration
            is then used to find the appropriate function signature by
            matching the provided function arguments.
          value_declaration: defines the property declaration for the
            result of the $value function within the provided
            context. This property declaration is used for validation
            of the function arguments as well as for resolving the
            templated type <T> in function signatures.
        Raises:
          TypeError: if the provided function string does not
            represent a valid TOSCA function.
          FunctionNotFound: when no function found with the provided
            function name within the provided context.
        """

        # First, call superclass constructor
        super(ToscaFunction, self).__init__()

        # Parse the function statement into a function key and a list
        # of function arguments.
        try:
            [(self.key, self.args)] = list(function.items())
        except (AttributeError, ValueError):
            # Not formatted as a function map. It is possible that we
            # have a function string without arguments.
            if isinstance(function, str):
                self.key = function
                self.args = list()
            else:
                raise TypeError("Not a function expression")

        # Function keys must be on-empty strings
        if not isinstance(self.key, str) or not self.key:
            raise TypeError("Function key is not a string")

        # Make sure we have an argument list
        if not isinstance(self.args, list):
            # Handle the short notation case where a function with a
            # single argument doesn't need to use a list.
            self.args = [self.args]

        # Initialize signature and the resolved <T> type (a per-call-site fact carried
        # on this function, threaded into signature.evaluate as a kwarg; None when the
        # signature is not templated or the type isn't cached in the key).
        self.signature = None
        self.resolved_type = None

        # Different initialization paths depending on whether this is
        # a fully resolved function or an unresolved (named) function.
        try:
            self.init_resolved_function()
        except ValueError:
            self.init_named_function(context, value_declaration, **kwargs)
            

    def init_resolved_function(self) -> None:
        """Finish function initialization by looking up its signature using
        the signature id in the function key. Resolved functions use
        '$(signature_id)' as their function key.

        Raises:
          ValueError: if the function key does not contain a
            signature id.
          FunctionNotFound: if no signature is found for the provided
            signature id.
        """
        # Does the function key represent a signature ID? Parse it into (sig_id, type_id):
        # a resolved key is '$(sig_id)' or '$(sig_id:type_id)', where type_id is the cached
        # resolved <T> type (may be None).
        parsed = fd.parse_function_key(self.key)
        if parsed is None:
            # Function key does not represent a function signature.
            raise ValueError(f"'{self.key}' is not a signature id")
        signature_id, type_id = parsed

        # Retrieve the signature
        try:
            self.signature = fd.get_signature(signature_id)
            self.name = self.signature.function.name
        except Exception as e:
            error = f"Function signature '{signature_id}' not found"
            logger.error("%s: %s", error, str(e))
            raise te.FunctionNotFound(error)

        # Rehydrate the cached resolved <T> type, if the key carried one. Best-effort:
        # a dangling id -> None -> a live re-resolution at eval.
        if type_id is not None:
            self.resolved_type = fd.get_data_type_by_id(type_id)


    def init_named_function(self, context: Any, value_declaration: Optional[Any], **kwargs: Any) -> None:
        """Finish function initialization as follows:

        1. Make sure the function exists by looking up its declaration
           by function name within the provided context.
        2. Make sure any functions used in function arguments are
           valid.
        3. Find the function signature that matches the provided
           arguments.
        4. Upgrade TOSCA Path arguments to v2 if necessary

        Args:
          context: context within which to resolve function name. The
            context is used to look up the function declaration for
            this function.
          value_declaration: defines the property declaration for the
            result of the $value function within the provided
            context. This property declaration is used for validation
            of the function arguments as well as for resolving the
            templated type <T> in function signatures.
        Raises:
          TypeError: if the function key does not represent a
            function.
          FunctionNotFound: when no function found with the provided
            function name within the provided context.
          SignatureNotFound: when the function declaration does not
            have a signature that matches the provided function
            arguments.
          ValidationError: for invalid function arguments
          ValueError: for invalid function arguments
          ModelCorruptionError: if no context provided within which to
            find the function declaration.
        """
        # First, find function declaration. This can raise a TypeError
        # or FunctionNotFound exception.
        function_declaration = self.find_declaration(context)

        # Make sure that functions used in the list of arguments are
        # valid. There is no point in finding a matching signature for
        # a function whose arguments are invalid. Note that this is
        # effectively recursive (depth-first) function validation.
        self.validate_function_arguments(context, value_declaration)
        
        # We have a valid arguments list. Find the signature that matches the provided
        # arguments; it also returns the resolved <T> type (None when non-templated).
        self.signature, self.resolved_type = function_declaration.find_matching_signature(
            context, self.args, value_declaration, **kwargs)
        # Use the resolved function key from now on, caching the resolved type's id when we
        # have one (a persistent DB id) so eval need not re-resolve it: '$(sig_id)' or
        # '$(sig_id:type_id)'.
        type_suffix = ''
        if self.resolved_type is not None and self.resolved_type.id is not None:
            type_suffix = ':' + str(self.resolved_type.id)
        self.key = '$(' + str(self.signature.id) + type_suffix + ')'

        # Finally, upgrade TOSCA path arguments if necessary. We can
        # do this last, since TOSCA Path arguments are only used to
        # retrieve the result declaration.
        self.upgrade_tosca_path(context)
        
        
    def find_declaration(self, context: Optional[Any]) -> Any:
        """Find the function declaration for this function within the provided
        context. We do this by parsing out the function name from the
        function key and then looking up the function declaration by
        name.

        Args:
          context(ToscaTemplate, ToscaDeclaration, or ToscaType):
            context within which to find the declaration for this
            function
        Returns:
          ToscaFunctionDeclaration: declaration for this function
        Raises:
          TypeError: if the function key does not represent a
            function.
          FunctionNotFound: if no function with that name declared in
            this context.
          ModelCorruptionError: if no context provided within which to
            find the function declaration.
        """
        # Version 2.0 function keys start with an unescaped dollar
        # sign.
        if not self.key[0] == '$':
            # Not a Version 2.0 function name. Is this a Version 1.3
            # function perhaps?
            if (context and
                context.tosca_version and
                context.tosca_version.startswith("tosca_simple_yaml") and
                self.key in V1_INTRINSIC_FUNCTIONS):
                self.name = self.key
                self.key = '$' + self.name
            else:
                # Not a function
                raise TypeError(f"'{self.key}' is not a function")

        # An empty string is not a valid function name.
        if len(self.key) == 1:
            raise te.FunctionNotFound(self.key)

        # Make sure the $ sign is not escaped
        if self.key[1] == '$':
            raise TypeError(f"'{self.key}' is not a function")

        # Parse out the function name
        self.name = self.key[1:]

        # Context is mandatory for resolving named functions. Only
        # resolved functions can be initialized without a context.
        if not context:
            logger.error("Function '%s': no context for finding declaration", self.key)
            raise te.ModelCorruptionError("{}: no context provided".format(self.key))

        # Look up function declaration. This can raise a
        # FunctionNotFound error.
        return context.profile.get_function(self.name)
    

    ################################################################################
    # Function argument validation methods
    ################################################################################

    def validate_function_arguments(self, context: Any, value_declaration: Optional[Any]) -> None:
        """Check if any functions used in the arguments are valid. This will
        effectively recursively initialize functions in arguments.

        Args:
          context(ToscaTemplate, ToscaDeclaration, or Toscatype):
            context within which to validate this function's list of
            arguments.
          value_declaration(ToscaPropertyDeclaration): the property
            declaration for the result of the $value function within
            the provided context. This is also used for resolving the
            templated type <T>
        Returns:
          (list of Python values)
        Raises:
          ValidationError: in case of invalid function arguments
        """
        if self.name == 'get_attribute' or self.name == 'get_property' or self.name == 'get_input':
            self.args = self.resolve_functions_in_tosca_path(context)
        else:
            errors = dict()
            try:
                self.args = self.resolve_functions_in_list(context, self.args, value_declaration)
            except te.ValidationError as e:
                errors[f"${self.name}"] = e.errors
            except Exception as e:
                errors[f"${self.name}"] = str(e)
            if errors: raise te.ValidationError('invalid arguments', errors)


    def resolve_functions_in_list(self, context: Any, arg_list: list[Any], value_declaration: Optional[Any]) -> list[Any]:
        """Validate and resolve any functions used in the provided list of
        values.

        Args:
          context(ToscaTemplate, ToscaDeclaration, or Toscatype):
            context within which to validate this function's list of
            arguments.
          arg_list(list of Python values): list of function arguments
            that may contain functions that need to be validated and
            resolved.
          value_declaration(ToscaPropertyDeclaration): the property
            declaration for the result of the $value function within
            the provided context. This is also used for resolving the
            templated type <T>
        Returns:
          (list of Python values): argument list that contains
            resolved functions
        Raises:
          ValidationError: in case of invalid functions in the list of
            values.
        """
        errors = dict()

        # Validate each individual argument value
        count = 0
        resolved_args = list()
        for arg in arg_list:
            try:
                resolved_arg = self.resolve_functions_in_value(context, arg, value_declaration)
                resolved_args.append(resolved_arg)
            except te.ValidationError as e:
                errors[count] = e.errors
            except Exception as e:
                errors[count] = str(e)
            count = count+1

        # Raise exception if errors
        if errors:
            msg = f"{self.name}: invalid arguments"
            raise te.ValidationError(msg, errors)

        # Return resolved argument list
        return resolved_args
    

    def resolve_functions_in_map(self, context: Any, arg_map: dict[str, Any], value_declaration: Optional[Any]) -> dict[str, Any]:
        """Validate and resolve any functions used in the provided map of
        values.

        Args:
          context(ToscaTemplate, ToscaDeclaration, or Toscatype):
            context within which to validate this function's list of
            arguments.
          arg_map(map of Python values): map of function arguments
            that may contain functions that need to be validated and
            resolved.
          value_declaration(ToscaPropertyDeclaration): the property
            declaration for the result of the $value function within
            the provided context. This is also used for resolving the
            templated type <T>
        Returns:
          (map of Python values): argument map that contains
            resolved functions
        Raises:
          ValidationError: in case of invalid functions in the map of
            values
        """
        errors = dict()

        # Validate each individual argument value
        resolved_args = dict()
        for arg_name, arg in arg_map.items():
            try:
                resolved_arg = self.resolve_functions_in_value(context, arg, value_declaration)
                resolved_args[arg_name] = resolved_arg
            except te.ValidationError as e:
                errors[arg_name] = e.errors
            except Exception as e:
                errors[arg_name] = str(e)

        # Raise exception if errors
        if errors:
            msg = f"{self.name}: invalid arguments"
            raise te.ValidationError(msg, errors)

        # Return resolved argument map
        return resolved_args
    

    def resolve_functions_in_value(self, context: Any, arg: Any, value_declaration: Optional[Any]) -> Any:
        """Resolve a function used in an argument value.

        Args:
          context(ToscaTemplate, ToscaDeclaration, or Toscatype):
            context within which to validate the function in the
            provided value.
          arg(Python value): value that may contain a function that
            need to be validated and resolved.
          value_declaration(ToscaPropertyDeclaration): the property
            declaration for the result of the $value function within
            the provided context. This is also used for resolving the
            templated type <T>
        Returns:
          (Python value): value that contains resolved function
        Raises:
          ValidationError: in case of invalid function in the value
        """
        # Check if argument is a function
        try:
            function = ToscaFunction(arg, context, value_declaration)
            # We have a function. Make sure its result declaration
            # is valid. Raise a ValidationError if it isn't.
            result = function.get_result_declaration(context, value_declaration)
            resolved_arg = function.expression
        except TypeError:
            # Not a function. If this is a list or a map, validate
            # any functions in the list or map entries.
            if isinstance(arg, list):
                resolved_arg = self.resolve_functions_in_list(context, arg, value_declaration)
            elif isinstance(arg, dict):
                resolved_arg = self.resolve_functions_in_map(context, arg, value_declaration)
            else:
                resolved_arg = arg
        # All done
        return resolved_arg
        

    def resolve_functions_in_tosca_path(self, context: Any) -> list[Any]:
        """Resolve functions in TOSCA Path arguments within the provided
        context
        """
        integer_type = builtin_types.get('integer')
        declaration = integer_type.create_declaration(name='tosca_path')
        args = list()
        for arg in self.args:
            try:
                evaluated_arg = declaration.resolve_function_value(context, arg)
            except Exception as e:
                evaluated_arg = arg
            args.append(evaluated_arg)
        return args
    

    def upgrade_tosca_path(self, context: Any) -> None:
        """Upgrade TOSCA Path function arguments within the provided context.

        Args:
          context(ToscaTemplate, ToscaDeclaration, or Toscatype):
        Returns:
          None
        Raises:
          None
        """
        # Only 'get_attribute' and 'get_property' functions take TOSCA
        # path arguments.
        if not self.name == 'get_attribute' and not self.name == 'get_property':
            return

        # Is this a v1.3 TOSCA path expression?
        if (not context.tosca_version or
            not context.tosca_version.startswith("tosca_simple_yaml")):
            return 

        # We need to upgrade the TOSCA Path
        try:
            path = ToscaPath(self.args)
            self.args = path.upgrade(context)
        except Exception as e:
            # Not a valid TOSCA path. The validator will deal with
            # this later when trying to retrieve the result
            # declaration for this function.
            logger.error("Error upgrading TOSCA Path: %s", str(e))
        

    ################################################################################
    # External interface
    ################################################################################

    def get_result_declaration(self, context: Any, value_declaration: Optional[Any] = None) -> Optional[Any]:
        """Get the property declaration for the result returned by this
        function within the provided context

        Args:
          context(ToscaTemplate, ToscaDeclaration, or Toscatype):
            context within which to retrieve the result declaration.
          value(Python value): the value returned by the $value
            function. This is passed as an argument since it cannot be
            retrieved from the context.
          value_declaration(ToscaPropertyDeclaration): the property
            declaration for the result of the $value function within
            the provided context. This is also used for resolving the
            templated type <T>
        Returns:
          ToscaPropertyDeclaration: declaration for the result
            returned by the function (or None if no result declaration
            is defined)
        Raises:
          ValueError: for invalid function arguments
        """
        return self.signature.get_result_declaration(context, self.args, value_declaration)

    def is_value_required(self, context: Any, result_declaration: Optional[Any] = None) -> bool:
        """Whether the value this function returns is required.

        For $get_property and $get_attribute, the value must be required at
        every step of the path to it: the property or attribute the path
        starts from -- an attribute declared only as an attribute is not --
        and every step below it (ToscaPropertyDeclaration.is_required_along).
        An optional property, or an entry of a list or map, anywhere on the
        path makes the value optional. Any other function answers from its
        result declaration.

        Args:
          context: context within which to resolve the path
          result_declaration: the declaration of the value returned, when
            the caller already has it
        Returns:
          bool
        Raises:
          ValueError, KeyError: when the path cannot be resolved
        """
        if result_declaration is None:
            result_declaration = self.get_result_declaration(context)
        if self.name not in ('get_property', 'get_attribute'):
            return result_declaration.is_required()
        path = ToscaPath(self.args, head_index=True)
        entity_declaration = path.get_entity_declaration(context)
        if path.head_yields_list(entity_declaration):
            return result_declaration.is_required()
        tokens = path.sub_entity if isinstance(path.sub_entity, list) else [path.sub_entity]
        start = _navigation_length(tokens)
        if start >= len(tokens):
            return result_declaration.is_required()
        root_path = tokens[:start + 1]
        if self.name == 'get_property':
            get = entity_declaration.get_property_declaration
        else:
            get = entity_declaration.get_attribute_declaration
        root = get(root_path[0] if len(root_path) == 1 else root_path)
        if getattr(root, 'role', None) == 'ATTRIBUTE' or not root.is_required():
            return False
        return root.is_required_along(tokens[start + 1:])

    def is_return_value_present(self, context: Any) -> Any:
        """Check whether this function is guaranteed to return a value.

        $get_input and $get_property are answered as found. For every
        other function, an answer other than "guaranteed" is logged as a
        warning and answered as guaranteed: some correct models hold values
        onboarding cannot show to be present, and a required operation input
        without a value is refused when its operation is called
        (ToscaManagedInstance.call_interface_operation).

        Args:
          context(ToscaTemplate, ToscaDeclaration, or Toscatype):
            context within which to determine if the function is
            guaranteed to return a value.
        Returns:
          True: if the function return value is guaranteed
          False: if it is not
          Undecided or Circular (both false): when the check could not
            decide, or found the value defined in terms of itself --
            see tosca_core.models.presence
        Raises:
          None
        """
        answer = self._presence(context)
        if answer is True or self.name in ('get_input', 'get_property'):
            return answer
        logger.warning("%s%s: not shown to be present: %s", self, presence.where(),
                       presence.explain(answer, 'its result', 'its result may be absent'))
        return True

    def _presence(self, context: Any) -> Any:
        """Whether this function is guaranteed to return a value, as found.

        - $get_input: when the input it reads is required.
        - $get_property and $get_attribute: by following the path to the
          value read (_path_presence). An attribute that reflects a
          property is judged as the property; an attribute declared only
          as an attribute has no required-ness, and is guaranteed only
          through a template's assignment or a default that is itself
          guaranteed.
        - $if: when the branch its condition selects is -- both branches,
          unless the condition is a literal.
        - The string, list and set functions: when every argument is,
          since an argument with no value leaves the result without one
          (and for $join, every entry of the list it joins).
        - A function a profile implements: guaranteed when its signature
          declares a result, since an implementation returning null then
          fails the evaluation (ToscaSignature.evaluate); undecided
          otherwise. Its arguments do not decide it: $is_defined returns a
          value exactly when its argument has none.
        - Any other function: guaranteed.
        """
        if self.name == 'if':
            return self._if_presence(context)
        if self.name in _ALL_ARGUMENTS:
            arguments = list(self.args)
            if self.name == 'join' and arguments and isinstance(arguments[0], list):
                arguments = list(arguments[0]) + arguments[1:]
            return self._arguments_presence(arguments, context)
        if self.name not in ('get_input', 'get_property', 'get_attribute'):
            if self.name not in fd.ToscaSignature.intrinsics and \
               getattr(self.signature, 'artifacts', None):
                if getattr(self.signature, 'result', None) is not None:
                    return True
                return presence.Undecided(
                    f"{self} is implemented by a profile, and its signature declares "
                    f"no result")
            return True

        # For $get_input, $get_property and $get_attribute, the answer
        # starts from the declaration of the value read.
        try:
            result_declaration = self.result_declaration
        except AttributeError:
            try:
                result_declaration = self.signature.get_result_declaration(context, self.args)
            except Exception as e:
                return presence.Undecided(f"cannot find what {self} returns: {e}")

        # A $get_input is guaranteed when the input it reads is required.
        if self.name == 'get_input':
            return True if result_declaration.is_required() else False

        # Get the entity the path starts from.
        try:
            path = ToscaPath(self.args)
            head = path.get_entity(context)
        except Exception as e:
            return presence.Undecided(f"cannot resolve the path of {self}: {e}")

        # An attribute declared only as an attribute, not one reflecting a
        # property.
        attribute_only = (self.name == 'get_attribute' and
                          getattr(result_declaration, 'role', None) == 'ATTRIBUTE')

        # Required at every step of the path, not only at its end
        # (is_value_required).
        try:
            required = not attribute_only and \
                self.is_value_required(context, result_declaration)
        except Exception as e:
            logger.debug("%s: required-ness along the path not found (%s); "
                         "the value read answers", self, e)
            required = not attribute_only and result_declaration.is_required()

        # The relationships the read follows to the node it reads, for an
        # attribute an earlier operation writes (_written_before_read): none
        # from SELF, and from TARGET the relationship whose operation reads.
        # In a relationship, SELF is the relationship, and [SELF, TARGET, ...]
        # and [SELF, SOURCE, ...] -- TOSCA 2.0's spelling of the 1.3 [TARGET,
        # ...] and [SOURCE, ...] -- read its target or source.
        tokens = list(self.args[1:])
        start = self.args[0] if self.args else None
        if start == 'SELF' and tokens and tokens[0] in ('TARGET', 'SOURCE') and \
                not (hasattr(head, 'get_requirement') or
                     hasattr(head, 'get_requirement_declaration')):
            start = tokens.pop(0)
            head = presence._safely(getattr(context, start))
        through = None
        if self.name == 'get_attribute' and start is not None:
            if start == 'SELF':
                through = []
            elif start == 'SOURCE':
                through = ['SOURCE']
            elif start == 'TARGET':
                through = [_relationship_kind(presence._safely(context.SELF))]
        try:
            return self._path_presence(head, tokens, result_declaration,
                                       attribute_only, through, required)
        except Exception as e:
            logger.error("PRESENCE CHECK: %s", str(e), stack_info=True)
            return presence.Undecided(f"{type(e).__name__} while resolving {self}: {e}")

    def _if_presence(self, context: Any) -> Any:
        """$if returns the branch its condition selects: a literal condition
        selects one, any other may select either."""
        if len(self.args) != 3:
            return presence.Undecided(f"{self} does not have a condition and two branches")
        condition, then, otherwise = self.args
        if isinstance(condition, bool):
            return self._arguments_presence([then if condition else otherwise], context)
        return self._arguments_presence([then, otherwise], context)

    def _arguments_presence(self, arguments: list, context: Any) -> Any:
        """Whether every one of 'arguments' is guaranteed: a literal is, a
        function is when it guarantees its result. The first answer other
        than True is the answer."""
        for argument in arguments:
            try:
                function = ToscaFunction(argument, context)
            except TypeError:
                # A literal.
                continue
            except Exception as e:
                return presence.Undecided(f"{argument} is not a function this check can read: {e}")
            answer = function._presence(context)
            if answer is not True:
                return answer
        return True

    def _path_presence(self, entity: Any, tokens: list, result_declaration: Any,
                       attribute_only: bool = False, through: Optional[list] = None,
                       required: Optional[bool] = None) -> Any:
        """Whether the value at the end of 'tokens', read from 'entity', is
        guaranteed.

        The path is followed one requirement at a time. While there is a
        template to ask, a requirement is guaranteed when the template has
        it -- assigned, or inserted because its minimum count is at least
        one; once there is none -- the context is a type, or the target is
        found in the inventory at deploy -- a requirement is guaranteed when
        its declared minimum count is at least one, and its declared target
        type stands in for the target.

        At the end of the path, a template answers for its own value, as it
        always has. Without a template the declaration of the value read
        answers: guaranteed when it is required, or when its default is
        itself guaranteed there.

        An attribute declared only as an attribute is never required: at
        the end of the path, a template answers from its assignment of the
        attribute, and without one the attribute's default answers.

        A $get_attribute the rules above leave unguaranteed is guaranteed
        when an application that orders operations says an earlier operation
        writes it (_written_before_read); 'through' collects the kinds of the
        relationships the path follows.

        A required value read through a requirement that may be unfulfilled
        is not guaranteed either. That is reported as a warning and answered
        as guaranteed, as is_return_value_present answers every function it
        cannot show present.
        """
        if required is None:
            required = not attribute_only and result_declaration.is_required()
        tokens = list(tokens)
        hop_reason = None
        while tokens and tokens[0] == 'RELATIONSHIP' and len(tokens) >= 2:
            requirement_name = tokens[1]
            tokens = tokens[2:]
            index = None
            if tokens and (isinstance(tokens[0], int) or tokens[0] == 'ALL'):
                index = tokens.pop(0)
            if entity is None:
                # The previous requirement names no target type: the rest
                # of the path cannot be followed.
                break
            if hasattr(entity, 'get_requirement'):
                # A template: guaranteed when it has the requirement.
                if isinstance(index, int) and hasattr(entity, 'get_requirement_by_index'):
                    relationship = entity.get_requirement_by_index(requirement_name, index)
                else:
                    relationship = entity.get_requirement(requirement_name)
                if relationship is None:
                    hop_reason = (f"requirement '{requirement_name}' of '{entity.name}', "
                                  f"which is not assigned")
                    break
                if tokens and tokens[0] == 'TARGET':
                    tokens = tokens[1:]
                    if through is not None:
                        through = through + [_relationship_kind(relationship)]
                    target = getattr(relationship, 'target_node', None)
                    if target is not None and hasattr(target, 'is_property_template_present'):
                        entity = target
                    else:
                        # Found in the inventory at deploy: the target
                        # type the template or the requirement names
                        # stands in for it.
                        entity = _target_type(relationship)
                else:
                    entity = relationship
                    through = None
                    break
            else:
                # A type or declaration: guaranteed when the declared
                # minimum count is at least one.
                declaration = entity.get_requirement_declaration(requirement_name)
                if not declaration.is_required():
                    hop_reason = (f"requirement '{requirement_name}', whose minimum count "
                                  f"is zero")
                    break
                if tokens and tokens[0] == 'TARGET':
                    tokens = tokens[1:]
                    if through is not None:
                        through = through + [_relationship_kind(declaration)]
                    entity = _target_type(declaration)
                else:
                    entity = declaration
                    through = None
                    break

        if hop_reason:
            if required:
                logger.warning("%s%s: not shown to be present: required, but read through "
                               "%s and may be absent",
                               self, presence.where(), hop_reason)
                return True
            return False

        answer = self._end_presence(entity, tokens, result_declaration, required,
                                    attribute_only)
        if answer is not True and self.name == 'get_attribute' and \
                _written_before_read(entity, tokens, through):
            return True
        return answer

    def _end_presence(self, entity: Any, tokens: list, result_declaration: Any,
                      required: bool, attribute_only: bool) -> Any:
        """Whether the value at the end of a guaranteed path is guaranteed
        (_path_presence)."""
        # A required value at the end of a guaranteed path is guaranteed.
        if required:
            return True

        # A requirement that names no target type leaves nothing to ask
        # for an optional value.
        if entity is None:
            return False

        # A template answers for its own value, which may be a function in
        # turn. A value reached again while it is being resolved is
        # defined in terms of itself.
        if attribute_only:
            return self._attribute_presence(entity, tokens, result_declaration)
        check = getattr(entity, 'is_property_template_present', None)
        if check is not None:
            rest = tokens[0] if len(tokens) == 1 else tokens
            label = f"{getattr(entity, 'name', entity)}.{rest}"
            token = presence.enter((id(entity), str(rest)), label)
            if isinstance(token, presence.Circular):
                return token
            try:
                return check(rest, result_declaration)
            finally:
                presence.leave(token)

        # No template: the declaration answers, through its default.
        try:
            default = result_declaration.default
        except AttributeError:
            return False
        label = f"{getattr(entity, 'name', entity)}.{tokens}"
        token = presence.enter((id(result_declaration), 'default'), label)
        if isinstance(token, presence.Circular):
            return token
        try:
            return result_declaration.is_value_present(default, entity)
        finally:
            presence.leave(token)


    def _attribute_presence(self, entity: Any, tokens: list, result_declaration: Any) -> Any:
        """Whether an attribute declared only as an attribute is guaranteed
        at the end of a guaranteed path: through the template's assignment
        of it, when the path names it directly on a template, or else
        through its default."""
        value = None
        if len(tokens) == 1 and hasattr(entity, 'get_attribute_or_property_template'):
            try:
                value = entity.get_attribute_or_property_template('attributes', tokens[0])
            except Exception:
                value = None
        if value is None:
            try:
                value = result_declaration.default
            except AttributeError:
                return False
            key = (id(result_declaration), 'default')
        else:
            key = (id(entity), str(tokens[0]))
        label = f"{getattr(entity, 'name', entity)}.{tokens[0] if len(tokens) == 1 else tokens}"
        token = presence.enter(key, label)
        if isinstance(token, presence.Circular):
            return token
        try:
            return result_declaration.is_value_present(value, entity)
        finally:
            presence.leave(token)


    def evaluate(self, context: Any, **kwargs: Any) -> Any:
        """Evaluate the function within the given context.

        Args:
          context(ToscaInstance): context within which to evaluate the
            function
        Keyword Args:
          value(Python value): the value returned by the $value
            function. This is passed as an argument since it cannot be
            retrieved from the context. Default value is None.
          value_declaration(ToscaPropertyDeclaration): the property
            declaration for the result of the $value function within
            the provided context. This is used for resolving the
            templated type <T>. Default value is None.
        Returns:
          (Python value): value returned by the function's
            implementation. This can be None
        Raises:
          None
        """
        # Thread this call-site's resolved <T> type into signature.evaluate as a kwarg
        # (the signature is shared, so it can't hold it). Our cached type is authoritative
        # for this call-site, so drop any stray one from kwargs to avoid a duplicate arg.
        kwargs.pop('resolved_type', None)
        return self.signature.evaluate(context, self.args,
                                       resolved_type=self.resolved_type, **kwargs)
    

