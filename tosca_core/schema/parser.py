"""
Tosca parser
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2014-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# logging support
import logging
logger = logging.getLogger(__name__)

# YAML support
from ruamel.yaml import YAML
from ruamel.yaml.reader import ReaderError
from ruamel.yaml.error import MarkedYAMLError
from ruamel.yaml.constructor import DuplicateKeyError, RoundTripConstructor


# Reuse v2's TOSCA function detector. v1 has its own is_function with
# different semantics (matches a fixed list of legacy names), so we
# don't share one definition across versions.
from tosca_core.schema.v2.functions import is_function


class _ToscaRoundTripConstructor(RoundTripConstructor):
    """Round-trip constructor that intercepts the 'unhashable map key'
    failure ruamel hits when a YAML mapping uses another mapping (with
    a non-scalar value somewhere inside it) as a key. The default
    behaviour is to raise a bare TypeError from deep inside ruamel,
    which loses both line numbers and any hint about what the user
    likely intended. We catch that case, sniff the key to recognise a
    TOSCA function-call shape, and raise a MarkedYAMLError instead.
    """

    def check_mapping_key(self, node, key_node, mapping, key, value):
        try:
            return super().check_mapping_key(node, key_node, mapping, key, value)
        except TypeError as e:
            if 'unhashable' not in str(e):
                raise

            if is_function(key):
                name = next(iter(key.keys()))
                problem = (
                    "map key is a TOSCA function call '{0}'; "
                    "function-call map keys are not supported"
                ).format(name)
            else:
                problem = "map key is not a scalar"
            raise MarkedYAMLError(
                "while constructing a mapping",
                node.start_mark,
                problem,
                key_node.start_mark,
            ) from e


# Schema support
from marshmallow import ValidationError

# Config
from tosca_core.constants import constants

# For ordered dict
import collections

# Module-level schema singletons to avoid repeated instantiation
_v1_schema = None
_v2_schema = None


def get_tosca_data(tosca_file_name: str) -> tuple:
    """Create TOSCA file data object from data contained in a TOSCA file.

    Args:
      tosca_file_name(str): name of the TOSCA file from which to
        create the TOSCA file data object

    Returns:
      ToscaData object representing parsed data in file
    """

    # Log info
    logger.debug("Processing TOSCA file: %s", tosca_file_name)

    # Parse YAML data from the TOSCA file
    tosca_yaml, yaml_errors = get_yaml_data(tosca_file_name)
    if not tosca_yaml: 
        return tosca_yaml, yaml_errors if yaml_errors else 'empty file'

    # First, make sure this is a valid and supported TOSCA file by
    # making sure we have a tosca_definitions_version as the first
    # key
    try:
        # Make sure we have a definitions version. If not, this
        # will raise a KeyError
        tosca_definitions_version = tosca_yaml['tosca_definitions_version']

        # Make sure the definitions version is the first key (we
        # can do this since ruamel yaml returns an ordered dict)
        if list(tosca_yaml.keys())[0] != 'tosca_definitions_version':
            error = "TOSCA definitions version is not the first line in the file"
            return None, {'tosca_error' : error }

        # Make sure the definitions version is supported
        if not tosca_definitions_version in constants.SUPPORTED_DEFINITIONS_VERSIONS:
            error = "Unsupported definitions version ({0})".format(tosca_definitions_version)
            return None, {'tosca_error' : error }

    except KeyError as e:
        # tosca definitions version not found
        return None, {'tosca_error' : "No TOSCA definitions version specified" }
    except TypeError as e:
        # tosca_yaml is not a dict
        return None, {'tosca_error' : "Not a TOSCA file" }

    # Parse TOSCA yaml data into TOSCA file data object
    global _v1_schema, _v2_schema
    try:
        if tosca_definitions_version == 'tosca_2_0':
            if _v2_schema is None:
                import tosca_core.schema.v2.tosca as tfs
                _v2_schema = tfs.ToscaSchema()
            tosca_schema = _v2_schema
        else:
            if _v1_schema is None:
                import tosca_core.schema.v1.tosca as tfs
                _v1_schema = tfs.ToscaSchema()
            tosca_schema = _v1_schema
        tosca_data = tosca_schema.load(tosca_yaml)
        return tosca_data, None
    except ValidationError as e:
        return None, e.messages
    except Exception as e:
        # Anything not modeled as a Marshmallow ValidationError (e.g. a
        # TypeError raised while iterating a YAML node with an
        # unhashable key) would otherwise bubble all the way out to the
        # CLI as a bare string. Log the stack trace and report it as a
        # parse error so the user sees a structured response.
        logger.exception("Unhandled error parsing TOSCA file '%s'", tosca_file_name)
        return None, {'parse_error': "{0}: {1}".format(type(e).__name__, e)}


def get_yaml_data(tosca_file_name: str) -> tuple:
    """Parse file content as YAML data 

    Args:
      tosca_file_name(str): name of the TOSCA file from which to get
        YAML data

    Returns:
      dict containing parsed YAML data
    """

    # Open file
    try:
        with open(tosca_file_name) as tosca_file:
            # Read data from the opened TOSCA file
            try:
                file_data = tosca_file.read()
            except UnicodeDecodeError as e:
                return None, {
                    'file error': str(e)
                }
    except IOError as e:
        return None, {
            'type': 'IO Error',
            'message' : str(e)
        }

    # Parse file data as YAML. We use the RoundTripLoader (the
    # default) since it stores line numbers in the comments section.
    yaml_errors = {}
    yaml = YAML()
    yaml.Constructor = _ToscaRoundTripConstructor
    try:
        yaml_data = yaml.load(file_data)
    except ReaderError as e:
        logger.error("%s", e)
        yaml_data = None
        error = {}
        error['message'] = str(e)
        if e.name:      error['name'] = e.name
        if e.character: error['character'] = e.character.decode(e.encoding, errors='ignore')
        if e.position:  error['position'] = e.position
        if e.encoding:  error['encoding'] = e.encoding
        if e.reason:    error['reason'] = e.reason
        yaml_errors['invalid YAML'] = error
    except MarkedYAMLError as e:
        _log_marked_yaml_error(e, tosca_file_name)
        yaml_data = None
        yaml_errors['invalid YAML'] = serialize_marked_yaml_error(e)
    except DuplicateKeyError as e:
        _log_marked_yaml_error(e, tosca_file_name)
        yaml_data = None
        yaml_errors['duplicate key'] = serialize_marked_yaml_error(e)
    except Exception as e:
        # ruamel can raise other exceptions during construction — most
        # notably TypeError when a YAML node uses an unhashable value
        # (mapping or sequence) as a mapping key. Log the stack trace
        # and surface a structured error rather than letting it bubble
        # out as a bare string from the CLI.
        logger.exception("Unhandled error parsing YAML from '%s'", tosca_file_name)
        yaml_data = None
        yaml_errors['invalid YAML'] = {
            'message': "{0}: {1}".format(type(e).__name__, e)
        }
    return yaml_data, yaml_errors


def _log_marked_yaml_error(e, tosca_file_name: str) -> None:
    """Emit a single-line error log for a ruamel MarkedYAMLError. The
    default str(e) is a multi-line dump that's awkward in a log."""
    line = (e.problem_mark.line + 1) if e.problem_mark is not None else None
    problem = e.problem or e.context or 'YAML parse error'
    if line is not None:
        logger.error("'%s' line %d: %s", tosca_file_name, line, problem)
    else:
        logger.error("'%s': %s", tosca_file_name, problem)


def serialize_marked_yaml_error(e) -> dict:
    """Serialize a MarkedYAMLError into a compact dict.

    ruamel's str(e) is a multi-line dump that repeats the problem
    string, embeds the source snippet, and uses zero-indexed line
    numbers in the dict fields but one-indexed in the rendered text.
    We surface just the problem (and the context that explains what
    ruamel was trying to do) along with one-indexed line / column
    numbers that match what editors show.
    """
    error = collections.OrderedDict()

    if e.problem:
        error['problem'] = e.problem
    if e.problem_mark is not None:
        error['line'] = e.problem_mark.line + 1
        error['column'] = e.problem_mark.column + 1

    if e.context:
        error['context'] = e.context
    if e.context_mark is not None:
        error['context_line'] = e.context_mark.line + 1
        error['context_column'] = e.context_mark.column + 1

    return error
