"""
Implementations of the functions defined in the built-in TOSCA
profile. Every callable in this module accepts ``(args,
resolved_type=None)`` so it can be dispatched uniformly from
``tosca_core.models.function_declaration._BUILTIN_IMPLEMENTATIONS``.

- ``args`` is the list of evaluated function arguments.
- ``resolved_type`` is the TOSCA data type into which the templated
  type ``<T>`` was resolved (or, for non-templated signatures, the
  type of the first argument). It is only consulted by functions
  whose semantics differ per type — most callables here ignore it.
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2022-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# logging support
import logging
logger = logging.getLogger(__name__)

# Data structures to implement built-in data types
from tosca_core.builtin.version import ToscaVersion
from tosca_core.builtin.range import ToscaRange
import iso8601


####################################################################
# Boolean logic functions
####################################################################

def and_(args, resolved_type=None):
    result = None
    for arg in args:
        if arg is None: continue
        if not arg:
            return False
        result = True
    return result

def or_(args, resolved_type=None):
    result = None
    for arg in args:
        if arg is None: continue
        if arg:
            return True
        result = False
    return result

def xor_(args, resolved_type=None):
    if args[0] is None or args[1] is None:
        return None
    return args[0] != args[1]

def not_(args, resolved_type=None):
    if args[0] is None: return None
    return not args[0]

####################################################################
# Comparison functions. These delegate to the resolved type since
# each TOSCA type knows how to compare its own values (integers,
# scalar-units, versions, timestamps, strings, ...).
####################################################################

def equal(args, resolved_type=None):
    return resolved_type.equal(args)

def greater_than(args, resolved_type=None):
    return resolved_type.greater_than(args)

def greater_or_equal(args, resolved_type=None):
    return resolved_type.greater_or_equal(args)

def less_than(args, resolved_type=None):
    return resolved_type.less_than(args)

def less_or_equal(args, resolved_type=None):
    return resolved_type.less_or_equal(args)

def valid_values(args, resolved_type=None):
    return resolved_type.valid_values(args)

def has_entry(args, resolved_type=None):
    return resolved_type.has_entry(args)

def matches(args, resolved_type=None):
    import regex as re
    pattern = re.compile(args[1])
    return bool(pattern.match(args[0]))

####################################################################
# Boolean list, map and string functions
####################################################################

def has_suffix_string(args, resolved_type=None):
    if args[0] == None or args[1] == None: return None
    return args[0].endswith(args[1])

def has_suffix_list(args, resolved_type=None):
    if args[0] == None or args[1] == None: return None
    if len(args[0]) < len(args[1]): return False
    n = len(args[1])
    return all(x == y for x, y in zip(args[0][-n:], args[1][-n:]))

def has_prefix_string(args, resolved_type=None):
    if args[0] == None or args[1] == None: return None
    return args[0].startswith(args[1])

def has_prefix_list(args, resolved_type=None):
    if args[0] == None or args[1] == None: return None
    if len(args[0]) < len(args[1]): return False
    return all(x == y for x, y in zip(args[0], args[1]))

def contains_string(args, resolved_type=None):
    if args[0] == None or args[1] == None: return None
    return args[1] in args[0]

def contains_list(args, resolved_type=None):
    if args[0] == None or args[1] == None: return None
    if len(args[0]) < len(args[1]): return False
    n = len(args[1])
    return any(args[1] == args[0][i:i + n] for i in range(len(args[0])-n + 1))

def has_key(args, resolved_type=None):
    if args[0] == None or args[1] == None: return None
    return (args[1] in args[0].keys())

def has_all_entries_list(args, resolved_type=None):
    if args[0] == None or args[1] == None: return None
    for value in args[1]:
        if not value in args[0]: return False
    return True

def has_all_entries_map(args, resolved_type=None):
    if args[0] == None or args[1] == None: return None
    values = args[0].values()
    for value in args[1]:
        if not value in values: return False
    return True

def has_all_keys(args, resolved_type=None):
    if args[0] == None or args[1] == None: return None
    keys = args[0].keys()
    for key in args[1]:
        if not key in keys: return False
    return True

def has_any_entry_list(args, resolved_type=None):
    if args[0] == None or args[1] == None: return None
    for value in args[1]:
        if value in args[0]: return True
    return False

def has_any_entry_map(args, resolved_type=None):
    if args[0] == None or args[1] == None: return None
    values = args[0].values()
    for value in args[1]:
        if value in values: return True
    return False

def has_any_key(args, resolved_type=None):
    if args[0] == None or args[1] == None: return None
    keys = args[0].keys()
    for key in args[1]:
        if key in keys: return True
    return False

####################################################################
# String, list, and map functions
####################################################################

def length(args, resolved_type=None):
    if args[0] == None: return None
    return len(args[0])

def concat_string(args, resolved_type=None):
    concatenated_string = str()
    for arg in args:
        if arg == None:
            return None
        concatenated_string += arg
    return concatenated_string

def concat_list(args, resolved_type=None):
    concatenated_list = list()
    for arg in args:
        if arg == None:
            return None
        concatenated_list += arg
    return concatenated_list

def token(args, resolved_type=None):
    if args[0] == None or args[1] == None or args[2] == None: return None
    tokenized = args[0].split(args[1])
    # Handle out-of-bound indices
    if args[2] >= len(tokenized):
        index = len(tokenized) - 1
    elif args[2] <= (len(tokenized)) * -1:
        index = (len(tokenized)) * -1
    else:
        index = args[2]
    return tokenized[index]

def join(args, resolved_type=None):
    if args[0] == None or None in args[0]: return None
    if len(args) > 1:
        if args[1] == None: return None
        return args[1].join(args[0])
    else:
        return "".join(args[0])

####################################################################
# Set functions
####################################################################

def union(args, resolved_type=None):
    if None in args: return None
    result = set(args[0])
    for arg in args[1:]:
        result = result.union(set(arg))
    return list(result)

def intersection(args, resolved_type=None):
    if None in args: return None
    result = set(args[0])
    for arg in args[1:]:
        result = result.intersection(set(arg))
    return list(result)

####################################################################
# Arithmetic functions. These delegate to the resolved type since
# each TOSCA numeric type knows how to do arithmetic on its own
# values (in particular, scalar-units normalize across units).
####################################################################

def sum_(args, resolved_type=None):
    return resolved_type.arithmetic_function('sum', args)

def difference(args, resolved_type=None):
    return resolved_type.arithmetic_function('difference', args)

def product(args, resolved_type=None):
    return resolved_type.arithmetic_function('product', args)

def quotient(args, resolved_type=None):
    return resolved_type.arithmetic_function('quotient', args)

def remainder(args, resolved_type=None):
    return resolved_type.arithmetic_function('remainder', args)

def round_(args, resolved_type=None):
    return resolved_type.arithmetic_function('round', args)

def floor(args, resolved_type=None):
    return resolved_type.arithmetic_function('floor', args)

def ceil(args, resolved_type=None):
    return resolved_type.arithmetic_function('ceil', args)

####################################################################
# Scalar conversions (from_scalar / to_scalar)
####################################################################

def from_scalar(args, resolved_type=None):
    from tosca_core.builtin.scalar_unit import ToscaScalarUnit
    scalar = ToscaScalarUnit(args[0], resolved_type)
    return scalar.value(args[1])

def to_scalar(args, resolved_type=None):
    """Inverse of from_scalar: render a scalar-unit literal of the given
    magnitude (args[0]) expressed in the given units (args[1]). The unit is
    validated when the result is assigned to a typed scalar-unit property, so
    here we only build the literal.
    """
    magnitude = args[0]
    # Render an integral float without a trailing ".0" for a clean literal.
    if isinstance(magnitude, float) and magnitude.is_integer():
        magnitude = int(magnitude)
    return f"{magnitude} {args[1]}"

####################################################################
# Range
####################################################################

def in_range(args, resolved_type=None):
    range = ToscaRange(args[1])
    return range.contains(args[0])
