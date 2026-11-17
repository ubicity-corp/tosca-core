"""
Module definining ToscaScalarUnit
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2014-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger = logging.getLogger(__name__)

# regular expressions
import regex as re

################################################################################
# Base class for all scalar units
################################################################################

class ToscaScalarUnit(object):
    """ToscaScalarUnit objects represent Tosca scalar-unit types.
    """
    # Regular expression for parsing scalar units. This is based on
    # regex for parsing floats as described in
    # https://stackoverflow.com/questions/638565/parsing-scientific-notation-sensibly
    scalar_unit_re = re.compile(r'^(?:\s*) ([+\-]?(?=\.\d|\d)(?:0|[1-9]\d*)?(?:\.\d+)?(?:[eE](?:[+\-])?\d+)?) (?:\s*) ([\w/]+) (?:\s*)$',
                                re.VERBOSE)

    def __init__ (self, scalar_unit, scalar_unit_type):
        """Constructur

        Args: 
          scalar_unit(str): string containing the scalar value and the
            unit for that value
        """
        # Call base class constructor
        super(ToscaScalarUnit, self).__init__()

        # Initialize. This can raise a ValueError
        self.parse(scalar_unit)

        # Track units
        try:
            # Create units from prefixes
            prefixes = scalar_unit_type.prefixes
            unit = next(iter(scalar_unit_type.units.keys()))
            self.supported_units = {key + unit: value for key, value in prefixes.items()}
        except AttributeError:
            # No prefixes
            self.supported_units = scalar_unit_type.units

        # Check unit. Do case-insensitive compare for now
        if not self.unit in self.supported_units:
            # return f"'{self.unit}' is not a valid unit for '{scalar_unit_type.name}'"
            raise ValueError(f"'{self.unit}' is not a valid unit'")

        # Check scalar value
        scalar_declaration = scalar_unit_type.data_type
        try:
            value = scalar_declaration.validate_simple_value(scalar_unit_type, self.scalar)
        except Exception as e:
            raise ValueError(f"'{self.scalar}' is not a valid '{scalar_declaration.type}'")


    def parse(self, scalar_unit_string):
        """Parse a Tosca scalar unit string

        Args: 
          scalar_unit_string(str): string specifying scalar value and
            the unit for that value
        """

        # Perform regular expression matching
        match = self.scalar_unit_re.match(scalar_unit_string)
        if not match:
            raise ValueError("invalid scalar unit {0}".format(scalar_unit_string))

        # Extract values from match and try to convert to a number
        (self.scalar, self.unit) = match.group(1, 2)
        try:
            self.scalar = int(self.scalar)
        except ValueError:
            # Not an integer. Try float instead. This could also raise
            # ValueError.
            try:
                self.scalar = float(self.scalar)
            except ValueError:
                raise ValueError(f"invalid scalar value '{self.scalar}'")
        

    # Representation
    def __repr__(self):
        return f"{self.scalar} {self.unit}"


    # Rich comparison methods
    def __eq__(self, other):
        if other == None: return False
        if self.unit == other.unit:
            return self.scalar == other.scalar
        else:
            return (self.scalar * self.supported_units[self.unit]) == \
                (other.scalar * other.supported_units[other.unit])

    def __ne__(self, other):
        if other == None: return True
        if self.unit == other.unit:
            return self.scalar != other.scalar
        else:
            return (self.scalar * self.supported_units[self.unit]) != \
                (other.scalar * other.supported_units[other.unit])

    def __gt__(self, other):
        if other == None: return False
        if self.unit == other.unit:
            return self.scalar > other.scalar
        else:
            return (self.scalar * self.supported_units[self.unit]) > \
                (other.scalar * other.supported_units[other.unit])

    def __ge__(self, other):
        if other == None: return False
        if self.unit == other.unit:
            return self.scalar >= other.scalar
        else:
            return (self.scalar * self.supported_units[self.unit]) >= \
                (other.scalar * other.supported_units[other.unit])

    def __lt__(self, other):
        if other == None: return False
        if self.unit == other.unit:
            return self.scalar < other.scalar
        else:
            return (self.scalar * self.supported_units[self.unit]) < \
                (other.scalar * other.supported_units[other.unit])

    def __le__(self, other):
        if other == None: return False
        if self.unit == other.unit:
            return self.scalar <= other.scalar
        else:
            return (self.scalar * self.supported_units[self.unit]) <= \
                (other.scalar * other.supported_units[other.unit])


    # In-place arithmetic functions
    def __iadd__(self, other):
        if self.supported_units[self.unit] == self.supported_units[other.unit]:
            self.scalar = self.scalar + other.scalar
        elif self.supported_units[self.unit] < self.supported_units[other.unit]:
            multiplier = self.supported_units[other.unit] / self.supported_units[self.unit]
            self.scalar = self.scalar + other.scalar * multiplier
        else:
            multiplier = self.supported_units[self.unit] / self.supported_units[other.unit]
            self.unit = other.unit
            self.scalar = other.scalar + self.scalar * multiplier
        return self
        
    def __isub__(self, other):
        if self.supported_units[self.unit] == self.supported_units[other.unit]:
            self.scalar = self.scalar - other.scalar
        elif self.supported_units[self.unit] < self.supported_units[other.unit]:
            multiplier = self.supported_units[other.unit] / self.supported_units[self.unit]
            self.scalar = self.scalar - other.scalar * multiplier
        else:
            multiplier = self.supported_units[self.unit] / self.supported_units[other.unit]
            self.unit = other.unit
            self.scalar = self.scalar * multiplier - other.scalar
        return self

    def __imul__(self, factor ):
        self.scalar = self.scalar * factor
        return self
    
    def __itruediv__(self, factor ):
        self.scalar = self.scalar / factor
        return self
    
    def __imod__(self, factor):
        self.scalar = self.scalar % factor
        return self


    # Return value in given units
    def value(self, unit):
        if not unit in self.supported_units:
            raise ValueError(f"'{unit}' is not a valid unit")
        if self.unit == unit:
            return self.scalar
        else:
            return self.scalar * self.supported_units[self.unit] / self.supported_units[unit]
    
