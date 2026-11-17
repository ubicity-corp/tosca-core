"""
A URL field links to an API endpoint when the application serves it, and is
left out when it does not: the engine run in process, as the CLI runs it,
registers no API routes. Where the endpoint is served but the object names
nothing to link to, the field is null.

DB-free: two minimal Flask applications, one serving the endpoint.
"""

from types import SimpleNamespace

import pytest
from flask import Flask
from marshmallow import Schema

from tosca_core.schema.url_field import URLField


class ServiceSchema(Schema):
    url = URLField('service', service_id='<id>')


def app(serving):
    application = Flask(__name__)
    if serving:
        application.add_url_rule('/services/<service_id>', endpoint='service',
                                 view_func=lambda service_id: '')
    return application


def dump(serving, obj):
    with app(serving).test_request_context():
        return ServiceSchema().dump(obj)


def test_the_field_is_left_out_where_the_endpoint_is_not_served():
    assert 'url' not in dump(False, SimpleNamespace(id=7))


def test_the_url_is_built_where_the_endpoint_is_served():
    assert dump(True, SimpleNamespace(id=7)) == {'url': '/services/7'}


def test_the_field_is_null_where_the_object_names_nothing():
    assert dump(True, SimpleNamespace(id=None)) == {'url': None}


def test_the_field_is_left_out_with_no_request_in_process():
    with app(False).app_context():
        assert 'url' not in ServiceSchema().dump(SimpleNamespace(id=7))
