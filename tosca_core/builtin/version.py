"""The ToscaVersion class is adapted from the python distutils
StrictVersion class
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2014-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger = logging.getLogger(__name__)

# Regular expression support
import string, re


# Helper function to compare two integers
def cmp(a, b):
    return (a > b) - (a < b)

# Interface for Tosca version-number class
#
#    __init__ (string) - create and take same action as 'parse'
#                        (string parameter is optional)
#    parse (string)    - convert a string representation to whatever
#                        internal representation is appropriate for
#                        this style of version numbering
#    __str__ (self)    - convert back to a string; should be very similar
#                        (if not identical to) the string supplied to parse
#    __repr__ (self)   - generate Python code to recreate
#                        the instance
#    __cmp__ (self, other) - compare two version numbers ('other' may
#                        be an unparsed version string, or another
#                        instance of the Tosca version class)

# TOSCA version strings have the following grammar:
#
#        <major_version>.<minor_version>[.<fix_version>[.<qualifier>[-<build_version] ]  ]
#

class ToscaVersion(object):
    """The ToscaVersion parser understands the Tosca version format and
    parses it.

    """

    version_re = re.compile(r'^(\d+) \. (\d+) (\. (\d+) (\. (\w+) (- (\d+))?)?)?$',
                            re.VERBOSE)


    def __init__ (self, vstring=None):
        """Instantiate a new ToscaVersion instance

        Args: 
          vstring(str): version string in Tosca version format

        Raises:
          ValueError: for invalid version strings
        """

        if vstring:
            # Convert to string if necessary
            if not isinstance(vstring, str):
                vstring = str(vstring)
            self.parse(vstring)


    def __repr__ (self):
        """Generate Python code to recreate the instance"""

        return "%s ('%s')" % (self.__class__.__name__, str(self))


    def parse (self, vstring):
        """Parse a Tosca version string

        Args: 
          vstring(str): version string in Tosca version format

        Raises:
          ValueError: for invalid version strings
        """

        # match regular expressions
        match = self.version_re.match(vstring)
        if not match:
            raise ValueError("invalid version number '{0}'".format(vstring))

        # extract results
        (major_version, minor_version, fix_version, qualifier, build_version) = \
            match.group(1, 2, 4, 6, 8)

        # major and minor version are mandatory
        self.major_version = int(major_version)
        self.minor_version = int(minor_version)

        # the rest is optional
        if fix_version:
            self.fix_version = int(fix_version)
            if qualifier:
                self.qualifier = qualifier
                if build_version:
                    self.build_version = int(build_version)


    def __str__ (self):
        """Convert back to a string"""

        vstring = str(self.major_version) + '.' + str(self.minor_version)

        try:
            vstring = vstring + '.' + str(self.fix_version)
            vstring = vstring + '.' + self.qualifier
            vstring = vstring + '-' + str(self.build_version)
        except AttributeError:
            # optional fields not present, which is OK
            pass

        return vstring


    def __cmp__ (self, other):
        """Compare two version numbers 

        Args:
          other(ToscaVersion or str): version number to compare. Other
            may be an unparsed version string, or another instance of
            the Tosca version class

        Returns:
          0:  when versions are identical
          1:  when other is greater/newer
          -1: when self is greater/newer
        """

        if not other:
            # No version to compare
            return 0

        # convert other version to ToscaVersion if it's a string
        if isinstance(other, str):
            other = ToscaVersion(other)

        # First, compare major, minor, and fix version numbers
        compare = cmp(self.major_version, other.major_version)
        if compare == 0:
            compare = cmp(self.minor_version, other.minor_version)
        if compare == 0:
            try:
                fix_version = self.fix_version
                try:
                    other_fix_version = other.fix_version
                    compare = cmp(fix_version, other_fix_version)
                except AttributeError:
                    # We have a fix version, but other doesn't. self
                    # is greater.
                    return 1
            except AttributeError:
                # We don't have a fix version
                try:
                    # other has a fix version. other is greater
                    other_fix_version = other.fix_version
                    return -1
                except AttributeError:
                    # other doesn't have a fix version either
                    compare = 0

        if (compare == 0):              
            # have to compare qualifier
            # case 1: neither has qualifier; they're equal
            # case 2: self has qualifier, other doesn't; other is greater
            # case 3: self doesn't have qualifier, other does: self is greater
            # case 4: both have qualifier: must compare them! If they're the same, 
            #         compare build number
            try:
                self_qualifier = self.qualifier
            except AttributeError:
                self_qualifier = None
            try:
                other_qualifier = other.qualifier
            except AttributeError:
                other_qualifier = None
            try:
                self_build_version = self.build_version
            except AttributeError:
                self_build_version = 0
            try:
                other_build_version = other.build_version
            except AttributeError:
                other_build_version = 0

            if (not self_qualifier and not other_qualifier):
                return 0
            elif (self_qualifier and not other_qualifier):
                return -1
            elif (not self_qualifier and other_qualifier):
                return 1
            elif (self_qualifier and other_qualifier):
                compare = cmp(self_qualifier, other_qualifier)
                if compare == 0:
                    if (not self_build_version and not other_build_version):
                        return 0
                    elif (self_build_version and not other_build_version):
                        return -1
                    elif (not self_build_version and other_build_version):
                        return 1
                    elif (self_build_version and other_build_version):
                        return cmp(self_build_version, other_build_version)
                else:
                    # Qualifiers don't match. Build version doesn't matter
                    return compare
        else:                           
            # numeric versions don't match --
            # qualifier stuff doesn't matter
            return compare              


    # Rich comparison methods
    def __eq__(self, other):
        return self.__cmp__(other) == 0

    def __ne__(self, other):
        return self.__cmp__(other) != 0

    def __gt__(self, other):
        return self.__cmp__(other) > 0

    def __ge__(self, other):
        return self.__cmp__(other) >= 0

    def __lt__(self, other):
        return self.__cmp__(other) < 0

    def __le__(self, other):
        return self.__cmp__(other) <= 0

        
