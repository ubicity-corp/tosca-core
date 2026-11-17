"""
TOSCA 2.0-specific helpers for recognizing function expressions in
parsed YAML data. v1 has its own is_function() that matches a fixed
list of legacy names; do not consolidate the two.
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2026, Ubicity Corp."
__email__ = "info@ubicity.com"

from typing import Any


def is_function(data: Any) -> bool:
    """Return True when ``data`` is shaped like a TOSCA 2.0 function
    call: a single-entry mapping whose key is an unescaped '$' name
    (e.g. ``{'$concat': [...]}``). A literal ``$$name`` is treated as
    an escaped value, not a function.
    """
    try:
        [(name, args)] = list(data.items())
    except Exception:
        return False

    return (isinstance(name, str)
            and len(name) > 1
            and name[0] == '$'
            and name[1] != '$')


def reads_service_input(data: Any) -> bool:
    """Return True when ``data`` calls ``$get_input`` anywhere within it."""
    if isinstance(data, dict):
        return any(key == '$get_input' or reads_service_input(value)
                   for key, value in data.items())
    if isinstance(data, list):
        return any(reads_service_input(item) for item in data)
    return False


def refuse_service_input(data: Any) -> None:
    """Marshmallow validator for the values a template assigns outside an
    entity's properties: an operation's inputs and an artifact's
    properties. A service input reaches an entity only through its
    properties, so an update can tell when it changed and every other
    node can read it.
    """
    from marshmallow import ValidationError
    names = sorted(name for name, value in (data or {}).items() if reads_service_input(value))
    if names:
        raise ValidationError(
            {name: "a service input reaches an entity only through its properties: assign "
                   "it to a property and read that with $get_property" for name in names})
