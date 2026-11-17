"""
Deleting a service template.

tosca-core creates no services, so it deletes a service template whenever
asked; refusing while services created from it exist is the job of an
application that creates them (ubicity's catalog actions, since 0.4.0).
Before, the delete read a 'services' attribute only the orchestrator's
models define, and failed without them.

The template is a stand-in borrowing ToscaServiceTemplate.delete; the
session is replaced, so no database is used.
"""

from tosca_core.models import service_template as st


class Template:
    delete = st.ToscaServiceTemplate.delete
    id = 7


def test_it_can_always_be_deleted():
    assert Template().delete(check_only=True) is True


def test_it_is_deleted_with_no_services_attribute(monkeypatch):
    deleted = []
    monkeypatch.setattr(st.db.session, "delete", deleted.append, raising=False)
    template = Template()
    template.delete()
    assert deleted == [template]
