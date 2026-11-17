"""
Arithmetic Function implementations
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2022-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# logging support
import logging
logger = logging.getLogger(__name__)

# Data structures to implement built-in data types
from tosca_core.builtin.scalar_unit import ToscaScalarUnit

####################################################################
# Arithmetic functions
####################################################################

def sum_scalar(scalar_type, args):
    result = None
    for arg in args:
        if arg != None:
            result = arg if result == None else result + arg
    return result
            
def sum_scalar_unit(scalar_unit_type, args):
    result = None
    for arg in args:
        if arg != None:
            size_to_add = ToscaScalarUnit(arg, scalar_unit_type)
            if result == None:
                result = size_to_add
            else:
                result += size_to_add
    return str(result)

def difference_scalar(scalar_type, args):
    if args[0] == None: return None
    if args[1] == None: return args[0]
    return args[0] - args[1]

def difference_scalar_unit(scalar_unit_type, args):
    if args[0] == None: return None
    if args[1] == None: return args[0]
    first = ToscaScalarUnit(args[0], scalar_unit_type)
    second = ToscaScalarUnit(args[1], scalar_unit_type)
    first -= second
    return str(first)

def product_scalar(scalar_type, args):
    result = None
    for arg in args:
        if arg != None:
            result = arg if result == None else result * arg
    return result

def product_scalar_unit(scalar_unit_type, args):
    if args[0] == None: return None
    if args[1] == None: return args[0]
    result = ToscaScalarUnit(args[0], scalar_unit_type)
    result *= args[1]
    return str(result)

def quotient_scalar(scalar_type, args):
    if args[0] == None: return None
    if args[1] == None: return float(args[0])
    return float(args[0] / args[1])

def quotient_scalar_unit(scalar_unit_type, args):
    if args[0] == None: return None
    if args[1] == None: return args[0]
    result = ToscaScalarUnit(args[0], scalar_unit_type)
    result /= args[1]
    return str(result)

def remainder_scalar(scalar_type, args):
    if args[0] == None: return None
    if args[1] == None: return args[0]
    return args[0] % args[1]

def remainder_scalar_unit(scalar_unit_type, args):
    if args[0] == None: return None
    if args[1] == None: return args[0]
    result = ToscaScalarUnit(args[0], scalar_unit_type)
    result %= args[1]
    return str(result)

def round_float(float_type, args):
    if args[0] == None: return None
    return round(args[0])

def floor_float(float_type, args):
    if args[0] == None: return None
    import math
    return math.floor(args[0])

def ceil_float(float_type, args):
    if args[0] == None: return None
    import math
    return math.ceil(args[0])


arithmetic_operators = {
    'integer': {
        'sum': sum_scalar,
        'difference': difference_scalar,
        'product': product_scalar,
        'quotient': quotient_scalar,
        'remainder': remainder_scalar,
        'round': None,
        'floor': None,
        'ceil': None,
    },
    'float': {
        'sum': sum_scalar,
        'difference': difference_scalar,
        'product': product_scalar,
        'quotient': quotient_scalar,
        'remainder': remainder_scalar,
        'round': round_float,
        'floor': floor_float,
        'ceil': ceil_float,
    },
    'scalar': {
        'sum': sum_scalar_unit,
        'difference': difference_scalar_unit,
        'product': product_scalar_unit,
        'quotient': quotient_scalar_unit,
        'remainder': remainder_scalar_unit,
        'round': None,
        'floor': None,
        'ceil': None,
    }    
}


