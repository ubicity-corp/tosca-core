import re
from typing import Any, Optional

from marshmallow import fields
from marshmallow import missing

from tosca_core.schema.url import serves, url_for

_tpl_pattern = re.compile(r"\s*<\s*(\S*)\s*>\s*")


def _tpl(val: str) -> Optional[str]:
    """Return value within ``< >`` if possible, else return ``None``."""
    match = _tpl_pattern.match(val)
    if match:
        return match.groups()[0]
    return None


def _get_value(obj: Any, key: str, default: Any = missing) -> Any:
    """Slightly-modified version of marshmallow.utils.get_value.
    If a dot-delimited ``key`` is passed and any attribute in the
    path is `None`, return `None`.
    """
    if "." in key:
        return _get_value_for_keys(obj, key.split("."), default)
    else:
        return _get_value_for_key(obj, key, default)


def _get_value_for_keys(obj: Any, keys: list, default: Any) -> Any:
    if len(keys) == 1:
        return _get_value_for_key(obj, keys[0], default)
    else:
        value = _get_value_for_key(obj, keys[0], default)
        # XXX This differs from the marshmallow implementation
        if value is None:
            return None
        return _get_value_for_keys(value, keys[1:], default)


def _get_value_for_key(obj: Any, key: str, default: Any) -> Any:
    if not hasattr(obj, "__getitem__"):
        return getattr(obj, key, default)

    try:
        return obj[key]
    except (KeyError, IndexError, TypeError, AttributeError):
        return getattr(obj, key, default)


class URLField(fields.Field):
    """Field that outputs the URL for an endpoint. Acts identically to
    Flask's ``url_for`` function, except that arguments can be pulled from the
    object to be serialized.

    Usage: ::

        url = URLFor('author_get', id='<id>')
        https_url = URLFor('author_get', id='<id>', _scheme='https', _external=True)

    :param str endpoint: Flask endpoint name.
    :param kwargs: Same keyword arguments as Flask's url_for, except string
        arguments enclosed in `< >` will be interpreted as attributes to pull
        from the object.
    """

    _CHECK_ATTRIBUTE = False

    def __init__(self, endpoint: str, **kwargs: Any) -> None:
        self.endpoint = endpoint
        self.params = kwargs
        # breakpoint()
        fields.Field.__init__(self, metadata=kwargs)

    def _serialize(self, value: Any, key: Any, obj: Any) -> Any:
        """Output the URL for the endpoint, given the kwargs passed to
        ``__init__``.

        Omitted when no app serves such an endpoint: Flask is not
        installed, or the engine runs in process, as the CLI runs it, with
        no API routes registered, so there is nothing to link to. ``None``
        when the object has nothing for the link to name, such as a type
        with no parent.
        """
        if not serves(self.endpoint):
            return missing
        param_values = {}
        for name, attr_tpl in self.params.items():
            attr_name = _tpl(str(attr_tpl))
            if attr_name:
                attribute_value = _get_value(obj, attr_name, default=missing)
                if attribute_value is None:
                    return None
                if attribute_value is not missing:
                    param_values[name] = attribute_value
                else:
                    """
                    raise AttributeError(
                        "{attr_name!r} is not a valid "
                        "attribute of {obj!r}".format(attr_name=attr_name, obj=obj)
                    )
                    """
                    return missing
            else:
                param_values[name] = attr_tpl
        return url_for(self.endpoint, **param_values)
'''
class URLField(fields.Field):
    """Field that outputs the URL for an endpoint. Acts identically to
    Flask's ``url_for`` function, except that arguments can be pulled from the
    object to be serialized.

    Usage: ::

        url = URLField('author_get', id='<id>')
        https_url = URLField('author_get', id='<id>', _scheme='https', _external=True)

    :param str endpoint: Flask endpoint name.
    :param kwargs: Same keyword arguments as Flask's url_for, except string
        arguments enclosed in `< >` will be interpreted as attributes to pull
        from the object.
    """
    _CHECK_ATTRIBUTE = False

    def __init__(self, endpoint, **kwargs):
        self.endpoint = endpoint
        self.params = kwargs
        fields.Field.__init__(self, **kwargs)

    def _format(self, val):
        return val

    def _serialize(self, value, key, obj):
        """Output the URL for the endpoint, given the kwargs passed to
        ``__init__``.
        """

        param_values = {}
        for name, attr_tpl in iteritems(self.params):
            attr_name = _tpl(str(attr_tpl))
            if attr_name:
                attribute_value = utils.get_value(attr_name, obj, default=missing_)
                if attribute_value is not missing_:
                    param_values[name] = attribute_value
                else:
                    """
                    raise ValidationError(AttributeError(
                        '{attr_name!r} is not a valid '
                        'attribute of {obj!r}'.format(
                            attr_name=attr_name, obj=obj,
                        )))
                    """
                    return missing_
            else:
                param_values[name] = attr_tpl
        try:
            return url_for(self.endpoint, **param_values)
        except BuildError as err:  # Make sure BuildErrors are raised
            raise err
        except Exception:
            return "No URL"
'''
