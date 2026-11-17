"""
A requirement mapping keyed by a two-letter requirement name.

Mappings were grouped by first reading each key as a [name, count] pair,
unpacking it and falling back to a plain name when that failed. A string of
two characters unpacks into them without failing, so 'to' was read as name
't' with count 'o' and the mapping refused. Only a pair is unpacked now;
names of every length are names.
"""

import textwrap

import pytest

from tosca_core.csar import validate_csar

TEMPLATE = textwrap.dedent("""\
    tosca_definitions_version: tosca_2_0
    capability_types:
      Service: {{}}
    relationship_types:
      ServedBy: {{}}
    node_types:
      Client:
        requirements:
          - {name}:
              capability: Service
              relationship: ServedBy
              count_range: [ 1, 1 ]
      ClientSoftware:
        requirements:
          - {name}:
              capability: Service
              relationship: ServedBy
              count_range: [ 1, 1 ]
    service_template:
      substitution_mappings:
        node_type: Client
        requirements:
          - {name}: [ software, {name} ]
      node_templates:
        software:
          type: ClientSoftware
    """)


@pytest.mark.parametrize("name", ["a", "to", "dep", "service"])
def test_a_requirement_name_of_any_length_maps(catalog, name):
    (catalog / "client.yaml").write_text(TEMPLATE.format(name=name))
    assert validate_csar(str(catalog / "client.yaml")) == {}
