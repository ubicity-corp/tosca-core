"""
URLs to REST resources in dumped TOSCA entities.

Dump-only fields link an entity to related resources on the REST
server. Those links exist only when a Flask app is serving; parsing and
validation, and code that runs without the server, get None instead.
This module is the one place schema/ reaches Flask, and it does so only
when a URL is asked for.
"""
from __future__ import annotations

__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2015-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def serves(endpoint: str) -> bool:
    """Whether an active Flask app serves 'endpoint'. Not when Flask is not
    installed or no app is active -- the engine run in process, as the CLI
    runs it, registers no API routes -- so there is nothing to link to."""
    try:
        import flask
    except ImportError:
        return False
    try:
        return endpoint in flask.current_app.view_functions
    except RuntimeError:
        return False


def url_for(endpoint: str, **values: Any) -> Optional[str]:
    """Return the relative URL for 'endpoint', or None when there is none
    to give: Flask is not installed, no app or request is active, or the
    URL cannot be built from 'values'. A served endpoint whose URL cannot
    be built is a defect, and is logged.
    """
    try:
        import flask
        from werkzeug.routing.exceptions import BuildError
    except ImportError:
        return None
    try:
        return flask.url_for(endpoint, _external=False, **values)
    except BuildError as e:
        logger.warning("No URL for endpoint '%s' with %s: %s", endpoint, values, e)
        return None
    except RuntimeError:
        return None
