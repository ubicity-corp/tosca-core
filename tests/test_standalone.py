"""
tosca-core works on its own.

It must import, build a catalog, and validate TOSCA without the
orchestrator it was extracted from and without Flask. Nothing else
keeps it that way: one import of an orchestrator module, or one
module-level Flask import, works as long as both are installed, which
they are wherever the two are developed together.

The checks run in a separate interpreter with 'ubicity' and Flask made
unimportable, because this one may have imported them already.
"""

import json
import subprocess
import sys
import textwrap

import pytest


VALID = textwrap.dedent("""\
    tosca_definitions_version: tosca_2_0
    capability_types:
      Service: {}
    relationship_types:
      ServedBy: {}
    node_types:
      Server:
        capabilities:
          service:
            type: Service
      Client:
        requirements:
          - server:
              capability: Service
              relationship: ServedBy
    service_template:
      node_templates:
        server:
          type: Server
        client:
          type: Client
          requirements:
            - server: server
    """)

# Implementation artifacts of a type nothing could run: valid TOSCA, and
# validated with no embedding application to say what it can run
WITH_ARTIFACTS = textwrap.dedent("""\
    tosca_definitions_version: tosca_2_0
    artifact_types:
      Recipe:
        file_ext: [recipe]
    interface_types:
      Lifecycle:
        operations:
          create: {}
    node_types:
      Cake:
        interfaces:
          lifecycle:
            type: Lifecycle
    service_template:
      node_templates:
        cake:
          type: Cake
          interfaces:
            lifecycle:
              operations:
                create:
                  implementation:
                    primary:
                      type: Recipe
                      file: bake.recipe
    """)

# A node template of a type nothing defines
INVALID = textwrap.dedent("""\
    tosca_definitions_version: tosca_2_0
    service_template:
      node_templates:
        server:
          type: NoSuchType
    """)

_PROBE = """
import importlib, json, os, pkgutil, sys

BLOCKED = {"ubicity", "flask", "werkzeug", "flask_sqlalchemy", "flask_jwt_extended"}

class Blocker:
    # find_spec, not find_module: Python 3.12 ignores the latter, and a
    # blocker that never fires makes every check here pass
    def find_spec(self, name, path=None, target=None):
        if name.split(".")[0] in BLOCKED:
            raise ImportError(f"[blocked] {name}")

sys.meta_path.insert(0, Blocker())
report = {"blocker_fired": False, "unimportable": {}}
try:
    import ubicity
except ImportError:
    report["blocker_fired"] = True

os.environ["TOSCA_CORE_DIR"] = sys.argv[1]
import tosca_core
for module in pkgutil.walk_packages(tosca_core.__path__, "tosca_core."):
    try:
        importlib.import_module(module.name)
    except ImportError as e:
        report["unimportable"][module.name] = str(e)

from tosca_core.bootstrap import bootstrap
from tosca_core.catalog import create_tables, load_normative_profiles
from tosca_core.core import session_scope
from tosca_core.csar import validate_csar
from tosca_core import extensions
from tosca_core.models.profile import ToscaProfile
from tosca_core.models.service_template import ToscaServiceTemplate
from tosca_core.models.node_template import ToscaNodeTemplate
from tosca_core.models.relationship_template import ToscaRelationshipTemplate
from tosca_core.models.capability_template import ToscaCapabilityTemplate
from tosca_core.models.interface_template import ToscaInterfaceTemplate
from tosca_core.models.workflow_template import ToscaWorkflowTemplate
import importlib.util

bootstrap()
with session_scope():
    create_tables()
with session_scope():
    load_normative_profiles()
with session_scope():
    report["profiles"] = ToscaProfile.query.count()

report["valid_errors"] = validate_csar(sys.argv[2])
report["invalid_errors"] = validate_csar(sys.argv[3])
report["with_artifacts_errors"] = validate_csar(sys.argv[4])
with session_scope():
    report["service_templates_after_validation"] = ToscaServiceTemplate.query.count()

report["implementation_checks"] = len(extensions.implementation_checks())
report["function_evaluator"] = extensions.function_evaluator() is not None
report["instantiate_methods"] = sorted(
    cls.__name__ for cls in (ToscaServiceTemplate, ToscaNodeTemplate, ToscaRelationshipTemplate,
                             ToscaCapabilityTemplate, ToscaInterfaceTemplate, ToscaWorkflowTemplate)
    if hasattr(cls, "instantiate"))
report["instance_factory_module"] = importlib.util.find_spec("tosca_core.models.instance_factory") is not None
report["blocked_loaded"] = sorted(m for m in sys.modules if m.split(".")[0] in BLOCKED)
print(json.dumps(report))
"""


@pytest.fixture(scope="module")
def standalone(tmp_path_factory):
    """What running tosca-core with neither the orchestrator nor Flask
    produces"""
    work = tmp_path_factory.mktemp("tosca-core")
    valid = work / "valid.yaml"
    valid.write_text(VALID)
    invalid = work / "invalid.yaml"
    invalid.write_text(INVALID)
    artifacts = work / "artifacts"
    artifacts.mkdir()
    (artifacts / "TOSCA.meta").write_text(
        "CSAR-Version: 2.0\nCreated-By: tests\nEntry-Definitions: service.yaml\n")
    (artifacts / "service.yaml").write_text(WITH_ARTIFACTS)
    (artifacts / "bake.recipe").write_text("mix, then bake\n")
    result = subprocess.run(
        [sys.executable, "-c", _PROBE, str(work / "work"), str(valid), str(invalid),
         str(artifacts)],
        capture_output=True, text=True, timeout=300)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_blocker_fires(standalone):
    assert standalone["blocker_fired"]


def test_every_module_imports(standalone):
    assert standalone["unimportable"] == {}


def test_nothing_blocked_is_loaded(standalone):
    assert standalone["blocked_loaded"] == []


def test_catalog_holds_the_normative_profiles(standalone):
    assert standalone["profiles"] > 0


def test_a_valid_template_validates(standalone):
    assert standalone["valid_errors"] == {}


def test_implementation_artifacts_validate_with_nothing_to_run_them(standalone):
    """The open validator accepts any artifact type, as TOSCA does"""
    assert standalone["with_artifacts_errors"] == {}


def test_an_invalid_template_is_refused(standalone):
    assert standalone["invalid_errors"] != {}


def test_validation_persists_nothing(standalone):
    assert standalone["service_templates_after_validation"] == 0


def test_standalone_extends_nothing_and_creates_no_instances(standalone):
    """Checking what can run, running any artifact, Python functions
    included, and creating instances belong to an embedding application"""
    assert standalone["implementation_checks"] == 0
    assert standalone["function_evaluator"] is False
    assert standalone["instantiate_methods"] == []
    assert standalone["instance_factory_module"] is False
