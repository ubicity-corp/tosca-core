"""
Interface names, operation names and metadata keys recognized by their
spelling.

Each has two accepted spellings: dash case, which TOSCA v2.0 section 1.2.2
prescribes for value names, and the spelling TOSCA v1.3 and profiles written
before that convention use. The two are treated as the same name, so a profile
may use either; an application that invokes operations uses the dash-case
spelling.
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2015-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

from typing import Any, Callable, Optional

# The lifecycle interface the declarative deploy and delete workflows invoke.
STANDARD_INTERFACE: tuple[str, ...] = ('standard', 'Standard')

# The interface of a relationship's lifecycle operations.
CONFIGURE_INTERFACE: tuple[str, ...] = ('configure', 'Configure')

# The relationship operations whose name has more than one word.
_OPERATIONS: tuple[tuple[str, ...], ...] = (
    ('pre-create-source', 'pre_create_source'),
    ('pre-configure-source', 'pre_configure_source'),
    ('post-configure-source', 'post_configure_source'),
    ('add-target', 'add_target'),
    ('add-source', 'add_source'),
    ('remove-target', 'remove_target'),
    ('remove-source', 'remove_source'),
)

# The metadata key in which a relationship type states its kind.
RELATIONSHIP_KIND_KEY: tuple[str, ...] = ('relationship_kind', 'relationship-kind')

# Every recognized name, mapped to all of its spellings, dash case first.
_INTERFACE_SPELLINGS: dict[str, tuple[str, ...]] = {
    spelling: spellings
    for spellings in (STANDARD_INTERFACE, CONFIGURE_INTERFACE)
    for spelling in spellings
}
_OPERATION_SPELLINGS: dict[str, tuple[str, ...]] = {
    spelling: spellings for spellings in _OPERATIONS for spelling in spellings
}


def is_standard_interface(name: Optional[str]) -> bool:
    """Return True if 'name' is a spelling of the standard lifecycle interface."""
    return name in STANDARD_INTERFACE


def is_configure_interface(name: Optional[str]) -> bool:
    """Return True if 'name' is a spelling of the configure interface."""
    return name in CONFIGURE_INTERFACE


def interface_name(name: str) -> str:
    """The dash-case spelling of interface 'name', or 'name' itself when it
    is not a recognized interface name."""
    return _INTERFACE_SPELLINGS.get(name, (name,))[0]


def operation_name(name: str) -> str:
    """The dash-case spelling of operation 'name', or 'name' itself when it
    is not a recognized operation name."""
    return _OPERATION_SPELLINGS.get(name, (name,))[0]


def _lookup(spellings: dict[str, tuple[str, ...]], get: Callable[[str], Any], name: str) -> Any:
    try:
        return get(name)
    except KeyError:
        for spelling in spellings.get(name, ()):
            if spelling != name:
                try:
                    return get(spelling)
                except KeyError:
                    pass
        raise


def lookup_interface(get: Callable[[str], Any], name: str) -> Any:
    """Look up interface 'name' with 'get', falling back to the other spellings
    of a recognized interface name. 'get' raises KeyError for a name it does
    not hold, as a dict's __getitem__ or get_interface_declaration does.

    Raises:
      KeyError: when no spelling of 'name' is found
    """
    return _lookup(_INTERFACE_SPELLINGS, get, name)


def lookup_operation(get: Callable[[str], Any], name: str) -> Any:
    """Look up operation 'name' with 'get', falling back to the other spellings
    of a recognized operation name, as lookup_interface does for interfaces.

    Raises:
      KeyError: when no spelling of 'name' is found
    """
    return _lookup(_OPERATION_SPELLINGS, get, name)


def declared_operation(interface_declaration: Any, name: str) -> str:
    """The spelling of operation 'name' that 'interface_declaration' declares,
    or 'name' itself when it declares no spelling of it."""
    for spelling in _OPERATION_SPELLINGS.get(name, (name,)):
        try:
            interface_declaration.get_operation_declaration(spelling)
            return spelling
        except (KeyError, AttributeError):
            pass
    return name


def relationship_kind(meta_data: Any) -> Any:
    """Return the relationship kind stated in 'meta_data', under either
    spelling of the key.

    Raises:
      KeyError: when 'meta_data' states no kind
    """
    for key in RELATIONSHIP_KIND_KEY:
        if key in meta_data:
            return meta_data[key]
    raise KeyError(RELATIONSHIP_KIND_KEY[0])
