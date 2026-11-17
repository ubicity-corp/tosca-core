"""
How the service templates an archive's Other-Definitions carry are named.

Nothing in such a template names it, and it has no CSAR of its own whose file
name could, so it is named after what heads its archive -- a profile's name,
or the catalog entry's -- followed by its path in the archive. The extension
is dropped, and so is a file name of 'main', the convention for a directory
holding one template. The entry itself keeps its own name, and a file in
Other-Definitions that holds no service template is left alone.

Archives and profiles are stand-ins; no database is used.
"""

from types import SimpleNamespace

from tosca_core.actions.ingest_csar import name_other_definitions


class Profile:
    """A profile with or without a service template, as the model raises."""

    def __init__(self, tosca_file_path, service=None):
        self.tosca_file_path = tosca_file_path
        self._service = service

    @property
    def service(self):
        if not self._service:
            raise AttributeError("no 'service'")
        return self._service


def template(name='default'):
    return SimpleNamespace(name=name)


def test_a_main_file_is_named_for_its_directory():
    dcn = template()
    archive = SimpleNamespace(profiles=[
        Profile('/profile.yaml'), Profile('/substitutions/dcn/main.yaml', dcn)])
    name_other_definitions(archive, 'com.example:1.0')
    assert dcn.name == 'com.example:1.0/substitutions/dcn'


def test_any_other_file_is_named_without_its_extension():
    figlet = template()
    archive = SimpleNamespace(profiles=[
        Profile('/profile.yaml'),
        Profile('/substitutions/application/figlet.yaml', figlet)])
    name_other_definitions(archive, 'com.example:1.0')
    assert figlet.name == 'com.example:1.0/substitutions/application/figlet'


def test_the_entry_keeps_its_own_name():
    entry = template('my_service')
    other = template()
    archive = SimpleNamespace(profiles=[
        Profile('/main.yaml', entry), Profile('/variants/small.yaml', other)])
    name_other_definitions(archive, entry.name)
    assert entry.name == 'my_service'
    assert other.name == 'my_service/variants/small'


def test_a_file_without_a_service_template_is_skipped():
    archive = SimpleNamespace(profiles=[
        Profile('/profile.yaml'), Profile('/types/extra.yaml')])
    name_other_definitions(archive, 'com.example:1.0')
