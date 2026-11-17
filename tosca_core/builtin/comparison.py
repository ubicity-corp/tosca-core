"""Module defining comparison operators for built-in TOSCA data types.
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2018-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger = logging.getLogger(__name__)

# Data structures to implement built-in data types
from tosca_core.builtin.version import ToscaVersion
from tosca_core.builtin.range import ToscaRange
from tosca_core.builtin.scalar_unit import ToscaScalarUnit
import iso8601

# For unsupported operations
def operation_not_supported(tosca_type, args):
    raise Exception("operation not supported")
    
####################################################################
# Comparison Operators
####################################################################

def equal_scalar(scalar_type, args):
    if args[0] == None or args[1] == None: return None
    return args[0] == args[1]

def equal_nil(nil_type, args):
    if args[0] == None or args[1] == None: return None
    return True

def equal_timestamp(timestamp_type, args):
    if args[0] == None or args[1] == None: return None
    first = iso8601.parse_date(args[0])
    second = iso8601.parse_date(args[1])
    return first == second

def equal_version(version_type, args):
    if args[0] == None or args[1] == None: return None
    first = ToscaVersion(args[0])
    second = ToscaVersion(args[1])
    return first == second

def equal_range(range_type, args):
    raise NotImplementedError("equal_range")

def equal_scalar_unit(scalar_unit_type, args):
    if args[0] == None or args[1] == None: return None
    first = ToscaScalarUnit(args[0], scalar_unit_type)
    second = ToscaScalarUnit(args[1], scalar_unit_type)
    return first == second

def equal_list(list_type, args):
    if args[0] == None or args[1] == None: return None
    return args[0] == args[1]

def equal_map(map_type, args):
    if args[0] == None or args[1] == None: return None
    return args[0] == args[1]

def equal_template(template_type, args):
    if args[0] == None or args[1] == None: return None
    return False

"""Map defining 'equal' operators"""
equal_operators = {
    'string' :                equal_scalar,
    'bytes' :                 equal_scalar,
    'integer' :               equal_scalar,
    'float' :                 equal_scalar, 
    'boolean' :               equal_scalar,
    'timestamp' :             equal_timestamp,
    'nil' :                   equal_nil,
    'version' :               equal_version,
    'range' :                 equal_range,
    'scalar' :                equal_scalar_unit,
    'list' :                  equal_list,
    'map' :                   equal_map,
    '<T>' :                   equal_template,
}

def greater_than_scalar(scalar_type, args):
    if args[0] == None or args[1] == None: return None
    return args[0] > args[1]

def greater_than_timestamp(timestamp_type, args):
    if args[0] == None or args[1] == None: return None
    first = iso8601.parse_date(args[0])
    second = iso8601.parse_date(args[1])
    return first > second

def greater_than_version(version_type, args):
    if args[0] == None or args[1] == None: return None
    first = ToscaVersion(args[0])
    second = ToscaVersion(args[1])
    return first > second

def greater_than_scalar_unit(scalar_unit_type, args):
    if args[0] == None or args[1] == None: return None
    first = ToscaScalarUnit(args[0], scalar_unit_type)
    second = ToscaScalarUnit(args[1], scalar_unit_type)
    return first > second

"""Map defining 'greater_than' operators"""
greater_than_operators = {
    'string' :                greater_than_scalar,
    'bytes' :                 operation_not_supported,
    'integer' :               greater_than_scalar,
    'float' :                 greater_than_scalar, 
    'boolean' :               operation_not_supported,
    'timestamp' :             greater_than_timestamp,
    'nil' :                   operation_not_supported,
    'version' :               greater_than_version,
    'range' :                 operation_not_supported,
    'scalar' :                greater_than_scalar_unit,
    'list' :                  operation_not_supported,
    'map' :                   operation_not_supported,
    '<T>' :                   operation_not_supported,
}

def greater_or_equal_scalar(scalar_type, args):
    if args[0] == None or args[1] == None: return None
    return args[0] >= args[1]

def greater_or_equal_timestamp(timestamp_type, args):
    if args[0] == None or args[1] == None: return None
    first = iso8601.parse_date(args[0])
    second = iso8601.parse_date(args[1])
    return first >= second

def greater_or_equal_version(version_type, args):
    if args[0] == None or args[1] == None: return None
    first = ToscaVersion(args[0])
    second = ToscaVersion(args[1])
    return first >= second

def greater_or_equal_scalar_unit(scalar_unit_type, args):
    if args[0] == None or args[1] == None: return None
    first = ToscaScalarUnit(args[0], scalar_unit_type)
    second = ToscaScalarUnit(args[1], scalar_unit_type)
    return first >= second

"""Map defining 'greater_or_equal' operators"""
greater_or_equal_operators = {
    'string' :                greater_or_equal_scalar,
    'bytes' :                 operation_not_supported,
    'integer' :               greater_or_equal_scalar,
    'float' :                 greater_or_equal_scalar, 
    'boolean' :               operation_not_supported,
    'timestamp' :             greater_or_equal_timestamp,
    'nil' :                   operation_not_supported,
    'version' :               greater_or_equal_version,
    'range' :                 operation_not_supported,
    'scalar' :                greater_or_equal_scalar_unit,
    'list' :                  operation_not_supported,
    'map' :                   operation_not_supported,
    '<T>' :                   operation_not_supported,
}

def less_than_scalar(scalar_type, args):
    if args[0] == None or args[1] == None: return None
    return args[0] < args[1]

def less_than_timestamp(timestamp_type, args):
    if args[0] == None or args[1] == None: return None
    first = iso8601.parse_date(args[0])
    second = iso8601.parse_date(args[1])
    return first < second

def less_than_version(version_type, args):
    if args[0] == None or args[1] == None: return None
    first = ToscaVersion(args[0])
    second = ToscaVersion(args[1])
    return first < second

def less_than_scalar_unit(scalar_unit_type, args):
    if args[0] == None or args[1] == None: return None
    first = ToscaScalarUnit(args[0], scalar_unit_type)
    second = ToscaScalarUnit(args[1], scalar_unit_type)
    return first < second

"""Map defining 'less_than' operators"""
less_than_operators = {
    'string' :                less_than_scalar,
    'bytes' :                 operation_not_supported,
    'integer' :               less_than_scalar,
    'float' :                 less_than_scalar, 
    'boolean' :               operation_not_supported,
    'timestamp' :             less_than_timestamp,
    'nil' :                   operation_not_supported,
    'version' :               less_than_version,
    'range' :                 operation_not_supported,
    'scalar' :                less_than_scalar_unit,
    'list' :                  operation_not_supported,
    'map' :                   operation_not_supported,
    '<T>' :                   operation_not_supported,
}

def less_or_equal_scalar(scalar_type, args):
    if args[0] == None or args[1] == None: return None
    return args[0] <= args[1]

def less_or_equal_timestamp(timestamp_type, args):
    if args[0] == None or args[1] == None: return None
    first = iso8601.parse_date(args[0])
    second = iso8601.parse_date(args[1])
    return first <= second

def less_or_equal_version(version_type, args):
    if args[0] == None or args[1] == None: return None
    first = ToscaVersion(args[0])
    second = ToscaVersion(args[1])
    return first <= second

def less_or_equal_scalar_unit(scalar_unit_type, args):
    if args[0] == None or args[1] == None: return None
    first = ToscaScalarUnit(args[0], scalar_unit_type)
    second = ToscaScalarUnit(args[1], scalar_unit_type)
    return first <= second

"""Map defining 'less_or_equal' operators"""
less_or_equal_operators = {
    'string' :                less_or_equal_scalar,
    'bytes' :                 operation_not_supported,
    'integer' :               less_or_equal_scalar,
    'float' :                 less_or_equal_scalar, 
    'boolean' :               operation_not_supported,
    'timestamp' :             less_or_equal_timestamp,
    'nil' :                   operation_not_supported,
    'version' :               less_or_equal_version,
    'range' :                 operation_not_supported,
    'scalar' :                less_or_equal_scalar_unit,
    'list' :                  operation_not_supported,
    'map' :                   operation_not_supported,
    '<T>' :                   operation_not_supported,
}
