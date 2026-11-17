"""
Module definining ToscaRange Entity
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2014-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger = logging.getLogger(__name__)


class ToscaRange(object):
    """The ToscaRange class implements the Tosca range type.

    Attributes:
      lower_bound(int): lower bound of the range
      upper_bound(int): upper bound of the range

    Note that the lower and upper bound attributes can hold a string
    containing the keyword 'UNBOUNDED' to represent ranges that have
    no lower or upper bounds.
    """


    def __init__ (self, range=None):
        """Instantiate a new ToscaRange instance

        Args: 
          range(list): list specifying lower and upper bound of range

        Raises:
          ValueError: in case of invalid range argument
          TypeError: if not a valid range
        """

        if range != None:
            self.parse(range)


    def parse (self, range):
        """Parse a Tosca range string

        Args: 
          range(list): list specifying lower and upper bound of range

        Raises:
          TypeError: if the range argument is not a valid range
          ValueError: in case of invalid range argument
        """

        # Is this a valid range list? Note that this will raise
        # TypeError if the "range" argument doesn't have a "len()"
        # method (e.g. when it's an integer)
        if not isinstance(range, list) \
           or isinstance(range, str) \
           or len(range) != 2:
            raise TypeError("Range has '{0}' elements".format(len(range)))

        # Make sure lower and upper bound values are either integers
        # or 'UNBOUNDED'
        """
        # Reflect the fact that lower bounds can not be unbounded
        if not isinstance(range[0], (int,long)) and not range[0] == 'UNBOUNDED':
            raise ValueError("Range lower bound ({0}) is not an integer".format(range[0]))
        """
        if not isinstance(range[0], int) and not isinstance(range[0], float): 
            raise ValueError("Range lower bound ({0}) is not a number".format(range[0]))
        if not isinstance(range[1], int) \
           and not isinstance(range[1], float) \
           and not range[1] == 'UNBOUNDED':
            raise ValueError("Range upper bound ({0}) is not a number".format(range[1]))
    
        # Is lower bound less than or equal to upper bound?
        if range[0] != 'UNBOUNDED' and range[1] != 'UNBOUNDED':
            if range[0] > range[1]:
                raise ValueError("Range lower bound ({0}) higher than upper bound ({1})".format(range[0], range[1]))

        # Everything OK
        self.lower_bound = range[0]
        self.upper_bound = range[1]


    def contains(self, value):
        """Check to see if a value is within the range. Value can either be a
        number or another range.

        Args: 
          value(int, float, or range): value to check

        Raise:
          None
        """

        # First, check if value is a range
        try:
            range = ToscaRange(value)
            lower_bound = range.lower_bound
            upper_bound = range.upper_bound
        except TypeError:
            # Not a range, must be a regular scalar value
            lower_bound = value
            upper_bound = value
        except Exception:
            # "value" is not a valid range
            logger.error("Error while checking if [%s, %s] contains <%s>: not valid for range",
                         self.lower_bound, self.upper_bound, value)
            return False

        # Check if upper and lower bounds are in range
        if self.lower_bound != 'UNBOUNDED' and lower_bound != 'UNBOUNDED' \
           and self.lower_bound > lower_bound:
            return False
        if self.upper_bound != 'UNBOUNDED' and upper_bound != 'UNBOUNDED' \
           and self.upper_bound < upper_bound:
            return False

        # number is in range
        return True
