"""
Shared runtime execution for activities used in workflow steps and
policy trigger actions. The target-free actions (``update_``,
``delegate``, ``inline``) have identical semantics in both contexts.
The target-dependent actions (``set_state``, ``call_operation``) need
a managed_instance and stay with the caller -- workflows resolve one
from the step's target/requirement; policies have no equivalent
binding yet, so they log "not implemented".
"""
from __future__ import annotations

__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2017-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

import logging
from typing import Any

logger = logging.getLogger(__name__)


def execute_target_free_action(activity: dict[str, Any], context: Any) -> bool:
    """Execute an activity if it carries a target-free action
    (``update_``, ``inline``). Returns True when handled here, False
    when the activity carries an action the caller must handle
    itself: ``set_state`` and ``call_operation`` need a
    managed_instance, and ``delegate`` is not yet implemented (see
    note below).

    Args:
      activity: the activity dict (already validated to contain
        exactly one action key).
      context: anything exposing ``.service``; for ``update_``, also
        used as the evaluation context for input values.
    """
    if 'update_' in activity:
        execute_update_action(activity['update_'], context)
        return True
    # `inline` (§13.2.3.4) drops a user-defined workflow into the
    # calling activity sequence. Ubicity runs it synchronously against
    # the whole service.
    if 'inline' in activity:
        inline = activity['inline']
        logger.debug("Run inline workflow <%s>", inline)
        context.service.run_workflow(inline)
        return True
    # `delegate` (§13.2.3.1) is intentionally left to the caller. The
    # spec says it hands lifecycle for the step's target (a no-op
    # node) off to an orchestrator-provided workflow -- most plausibly
    # a workflow defined *outside* the TOSCA template (a vendor
    # runtime, an external system). It's NOT the same as `inline`:
    # `service.run_workflow('deploy')` would re-launch the whole
    # service-level deploy and is almost certainly wrong here. Until
    # the external-handoff semantics are designed, callers log
    # "not implemented" rather than silently doing something wrong.
    return False


def execute_update_action(inputs: dict[str, Any], context: Any) -> None:
    """Update a service with the provided inputs. Inputs commonly
    arrive as function expressions (e.g. ``$(N)`` references into a
    policy's targets, or ``$get_input`` style references inside a
    workflow); resolve them against ``context`` before handing them
    to the service so what gets stored in ``service.inputs`` is
    concrete.
    """
    evaluated_inputs: dict = dict()
    input_declarations = context.service.template.inputs
    for input_name, input_value in inputs.items():
        input_declaration = input_declarations[input_name]
        evaluated_inputs[input_name] = input_declaration.evaluate_value(context, input_value)

    # Input names only, as for an operator's update (actions/service.py).
    logger.info("Update '%s' with inputs '%s'", context.service.name, ', '.join(evaluated_inputs))
    context.service.update(evaluated_inputs)
