"""Module defining value validator functions for builtin TOSCA data
types
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
import re

# RFC 3339 §5.6 allows ":60" in the seconds slot to denote a leap second.
# Python's datetime (and therefore iso8601) can't represent leap seconds, so
# we retry the parse with ":59" substituted in. The lookahead anchors the
# match to seconds immediately followed by a timezone marker so we don't
# false-positive elsewhere in the string.
_LEAP_SECOND_RE = re.compile(r":60(\.\d+)?(?=[Zz+-])")

################################################################################
# For each built-in type, check whether a provided value is valid for
# the type.
################################################################################

def validate_value_for_string(string_type, value):
    """Check if value is compatible with the Tosca string type"""
    if not isinstance(value, str):
        return 'not a string'
    return None

def validate_value_for_bytes(bytes_type, value):
    """Check if value is compatible with the Tosca bytes type"""
    if not isinstance(value, str):
        return 'not bytes'

def validate_value_for_integer(integer_type, value):
    """Check if value is compatible with the Tosca integer type"""
    if not isinstance(value, int):
        if (value == "UNBOUNDED"):
            return None
        return 'not an integer'
    return None

def validate_value_for_float(float_type, value):
    """Check if value is compatible with the Tosca float type"""
    if not isinstance(value, (float, int)):
        return 'not a float'
    return None

def validate_value_for_boolean(boolean_type, value):
    """Check if value is compatible with boolean type"""
    if not isinstance(value, bool):
        return 'not a boolean'
    return None

def validate_value_for_timestamp(timestamp_type, value):
    """Check if value is compatible with the TOSCA timestamp type.

    TOSCA follows RFC 3339, which requires an explicit time offset
    (Z or +/-HH:MM). Date and time may be separated by 'T' or
    whitespace per RFC 3339 §5.6 NOTE.
    """
    if not isinstance(value, str):
        return 'not a valid timestamp'
    try:
        parsed = iso8601.parse_date(value, default_timezone=None)
    except iso8601.ParseError:
        if _LEAP_SECOND_RE.search(value):
            try:
                parsed = iso8601.parse_date(
                    _LEAP_SECOND_RE.sub(r":59\1", value),
                    default_timezone=None,
                )
            except iso8601.ParseError:
                return 'not a valid timestamp'
        else:
            return 'not a valid timestamp'
    if parsed.tzinfo is None:
        return "not a valid timestamp (missing time offset)"
    return None

def validate_value_for_nil(nil_type, value):
    """Check if value is compatible with the Tosca nil type"""
    if value==None: return None
    return 'not nil'

def validate_value_for_version(version_type, value):
    """Check if value is compatible with version type"""
    if not isinstance(value, ToscaVersion):
        # Not a ToscaVersion object. Is this a valid string
        # representation of a tosca version?
        try:
            version = ToscaVersion(value)
        except ValueError:
            # Not a valid version string either.
            return "'{0}' is not a valid version string".format(value)
        except Exception:
            # Value is not a string
            return 'not a valid version'
    return None

def validate_value_for_range(range_type, value):
    """Check if value is compatible with range type"""
    if not isinstance(value, ToscaRange):
        # Not a ToscaRange object. Is this a valid string
        # representation of a tosca range?
        try:
            range = ToscaRange(value)
        except ValueError:
            # Not a valid range string either.
            return 'not a valid range string'
        except Exception:
            # Value is not a string
            return 'not a valid range'
    return None

def validate_value_for_scalar_unit(scalar_unit_type, value):
    """Check if value is compatible with scalar unit type"""
    if not isinstance(value, ToscaScalarUnit):
        # Not a ToscaScalarUnit object. Is this a valid string
        # representation of a tosca scalar_unit?
        try:
            scalar_unit = ToscaScalarUnit(value, scalar_unit_type)
        except ValueError as e:
            # Not a valid scalar_unit string
            return str(e)
        except Exception:
            # Value is not a string
            return f"'{value}' is not a valid scalar"
    return None

def validate_value_for_list(list_type, value):
    """Check if value is compatible with list type"""
    # must be a list that's not a string
    if not isinstance(value, list):
        return 'not a list'
    return None

def validate_value_for_map(map_type, value):
    """Check if value is compatible with map type"""
    """Check if value is compatible with integer type"""
    if not isinstance(value, dict):
        return 'not a map'
    return None

def validate_value_for_template(map_type, value):
    """This should never happen"""
    raise ValueError("<T> types not allowed for validation")

""" Map defining validators for the built-in Tosca data types.  """

data_type_validators = {
    'string' :                validate_value_for_string,
    'bytes' :                 validate_value_for_bytes,
    'integer' :               validate_value_for_integer,
    'float' :                 validate_value_for_float, 
    'boolean' :               validate_value_for_boolean,
    'timestamp' :             validate_value_for_timestamp,
    'nil' :                   validate_value_for_nil,
    'version' :               validate_value_for_version,
    'range' :                 validate_value_for_range,
    'scalar' :                validate_value_for_scalar_unit,
    'list' :                  validate_value_for_list,
    'map' :                   validate_value_for_map,
    '<T>' :                   validate_value_for_template,
}

def valid_values_nil(nil_type, args):
    return True

def valid_values_scalar(scalar_type, args):
    return args[0] in args[1]

def valid_values_timestamp(timestamp_type, args):
    first = iso8601.parse_date(args[0])
    for valid_value in args[1]:
        second = iso8601.parse_date(valid_value)
        if first == second: return True
    return False

def valid_values_version(version_type, args):
    first = ToscaVersion(args[0])
    for valid_value in args[1]:
        second = ToscaVersion(valid_value)
        if first == second: return True
    return False

def valid_values_scalar_unit(scalar_unit_type, args):
    first = ToscaScalarUnit(args[0], scalar_unit_type)
    for valid_value in args[1]:
        second = ToscaScalarUnit(valid_value, scalar_unit_type)
        if first == second: return True
    return False

def valid_values_range(range_type, args):
    raise NotImplementedError("valid_values_range")

def valid_values_list(list_type, args):
    for valid_value in args[1]:
        if args[0] == valid_value: return True
    return False

def valid_values_map(map_type, args):
    for valid_value in args[1]:
        if args[0] == valid_value: return True
    return False

def valid_values_template(template_type, args):
    return False

"""Map defining 'valid_values' operators"""
valid_values_operators = {
    'string' :                valid_values_scalar,
    'bytes' :                 valid_values_scalar,
    'integer' :               valid_values_scalar,
    'float' :                 valid_values_scalar, 
    'boolean' :               valid_values_scalar,
    'timestamp' :             valid_values_timestamp,
    'nil' :                   valid_values_nil,
    'version' :               valid_values_version,
    'range' :                 valid_values_range,
    'scalar' :                valid_values_scalar_unit,
    'list' :                  valid_values_list,
    'map' :                   valid_values_map,
    '<T>' :                   valid_values_template,
}

def list_has_entry_nil(nil_type, args):
    return True

def list_has_entry_scalar(scalar_type, args):
    return args[1] in args[0]

def list_has_entry_timestamp(timestamp_type, args):
    first = iso8601.parse_date(args[1])
    for entry in args[0]:
        second = iso8601.parse_date(entry)
        if first == second: return True
    return False

def list_has_entry_version(version_type, args):
    first = ToscaVersion(args[1])
    for entry in args[0]:
        second = ToscaVersion(entry)
        if first == second: return True
    return False

def list_has_entry_scalar_unit(scalar_unit_type, args):
    first = ToscaScalarUnit(args[1], scalar_unit_type)
    for entry in args[0]:
        second = ToscaScalarUnit(entry, scalar_unit_type)
        if first == second: return True
    return False

def list_has_entry_list(list_type, args):
    for entry in args[0]:
        if args[1] == entry: return True
    return False

def list_has_entry_map(map_type, args):
    for entry in args[0]:
        if args[1] == entry: return True
    return False

def list_has_entry_range(range_type, args):
    raise NotImplementedError("has_entry_range")

def list_has_entry_template(template_type, args):
    return False

"""Map defining 'list_has_entry' operators"""
list_has_entry_operators = {
    'string' :                list_has_entry_scalar,
    'bytes' :                 list_has_entry_scalar,
    'integer' :               list_has_entry_scalar,
    'float' :                 list_has_entry_scalar, 
    'boolean' :               list_has_entry_scalar,
    'timestamp' :             list_has_entry_timestamp,
    'nil' :                   list_has_entry_nil,
    'version' :               list_has_entry_version,
    'range' :                 list_has_entry_range,
    'scalar' :                list_has_entry_scalar_unit,
    'list' :                  list_has_entry_list,
    'map' :                   list_has_entry_map,
    '<T>' :                   list_has_entry_template,
}

def map_has_entry_nil(nil_type, args):
    return True

def map_has_entry_scalar(scalar_type, args):
    return args[1] in args[0].values()

def map_has_entry_timestamp(timestamp_type, args):
    first = iso8601.parse_date(args[1])
    for entry_name, entry in args[0].items():
        second = iso8601.parse_date(entry)
        if first == second: return True
    return False

def map_has_entry_version(version_type, args):
    first = ToscaVersion(args[1])
    for entry_name, entry in args[0].items():
        second = ToscaVersion(entry)
        if first == second: return True
    return False

def map_has_entry_scalar_unit(scalar_unit_type, args):
    first = ToscaScalarUnit(args[1], scalar_unit_type)
    for entry_name, entry in args[0].items():
        second = ToscaScalarUnit(entry, scalar_unit_type)
        if first == second: return True
    return False

def map_has_entry_range(range_type, args):
    raise NotImplementedError("has_entry_range")

def map_has_entry_list(list_type, args):
    for entry_name, entry in args[0].items():
        if args[1] == entry: return True
    return False

def map_has_entry_map(map_type, args):
    for entry_name, entry in args[0].items():
        if args[1] == entry: return True
    return False

def map_has_entry_template(template_type, args):
    return False

"""Map defining 'map_has_entry' operators"""
map_has_entry_operators = {
    'string' :                map_has_entry_scalar,
    'bytes' :                 map_has_entry_scalar,
    'integer' :               map_has_entry_scalar,
    'float' :                 map_has_entry_scalar, 
    'boolean' :               map_has_entry_scalar,
    'timestamp' :             map_has_entry_timestamp,
    'nil' :                   map_has_entry_nil,
    'version' :               map_has_entry_version,
    'range' :                 map_has_entry_range,
    'scalar' :                map_has_entry_scalar_unit,
    'list' :                  map_has_entry_list,
    'map' :                   map_has_entry_map,
    '<T>' :                   map_has_entry_template,
}
