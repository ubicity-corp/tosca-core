"""
Shared validation for activities used in workflow steps and policy
trigger actions. Both contexts accept the same five mutually exclusive
actions (update_, delegate, set_state, call_operation, inline) defined
by the ``ActivitySchema``.
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2017-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

import logging
from typing import Any, Callable, Optional

import tosca_core.models.exceptions as te

logger = logging.getLogger(__name__)

ACTIVITY_ACTIONS = ('update_', 'delegate', 'inline', 'set_state', 'call_operation')


def validate_activity(
    owner: Any,
    activity: dict,
    *,
    owner_label: str,
    changed_collection: Any,
    call_operation_resolver: Optional[Callable[[dict, str, str], Any]] = None,
) -> Any:
    """Validate a single activity.

    Args:
      owner: workflow or policy entity (must expose ``name`` and
        ``service``).
      activity: the activity dict (already tagged with a ``name`` key
        by the caller for log/error keying).
      owner_label: human-readable kind, e.g. 'Workflow' or 'Policy',
        used in log prefixes.
      changed_collection: the SQLAlchemy relationship collection to
        mark dirty after an ``update_`` activity rewrites its inputs
        in place (``workflow.steps`` or ``policy.triggers``).
      call_operation_resolver: optional callback that resolves and
        validates a ``call_operation`` activity beyond the syntactic
        check. Receives ``(call_operation, interface_name,
        operation_name)`` and returns either a falsy value on success
        or an error description (str or dict). When None, the
        ``call_operation`` branch only checks that an operation string
        is present and well-formed.

    Returns:
      Either a dict of per-action validation errors (possibly empty)
      or a single error string when the activity itself is malformed.
    """
    actions = [a for a in ACTIVITY_ACTIONS if a in activity]
    if len(actions) != 1:
        logger.error("Activity '%s': multiple actions %s",
                     activity['name'], activity)
        return "multiple actions specified"

    validation_errors: dict = {}

    if 'update_' in activity:
        update_inputs = activity['update_']
        logger.debug("%s '%s': validating 'update' inputs '%s'",
                     owner_label, owner.name, str(update_inputs))
        validated_inputs: dict = dict()
        errors: dict = dict()
        input_declarations = owner.service.inputs
        for input_name, input_value in update_inputs.items():
            input_declaration = input_declarations[input_name]
            try:
                validated_inputs[input_name] = input_declaration.validate_value(owner, input_value)
            except te.ValidationError as e:
                logger.error("'%s' input '%s': '%s' is invalid value for %s",
                             owner.name, input_name, input_value, input_declaration.type)
                validated_inputs[input_name] = input_value
                errors[input_name] = e.errors
        if errors:
            validation_errors['update'] = errors
        activity['update_'] = validated_inputs
        # The assignment is to a dict nested inside the tracked collection,
        # which MutableDict does not see.
        changed_collection.changed()
        return validation_errors

    if 'delegate' in activity:
        delegate = activity['delegate']
        logger.debug("%s '%s': validating 'delegate'", owner_label, owner.name)
        # `delegate` (§13.2.3.1) names a workflow provided by the
        # orchestrator -- plausibly one defined outside the TOSCA
        # template (an external runtime, vendor system). It is NOT a
        # reference into ``service.workflows`` the way ``inline`` is,
        # so do not resolve it here. Schema-level type checking
        # ensures it's a string; the runtime currently logs "not
        # implemented" when executing it.
        return validation_errors

    if 'set_state' in activity:
        set_state = activity['set_state']
        logger.debug("%s '%s': validating 'set_state'", owner_label, owner.name)
        # TOSCA 2.0 doesn't normatively define a state alphabet, so any
        # string passes static validation. An application that runs
        # workflows names its states (STATE_NAMES); warn (don't error)
        # when the value isn't one of them, since executing it would
        # fail there.
        from tosca_core.constants import constants
        state_names = constants.STATE_NAMES
        if state_names and set_state not in state_names:
            logger.warning(
                "%s '%s': 'set_state: %s' is not one of this application's "
                "states (%s); execution would fail at runtime.",
                owner_label, owner.name, set_state, ", ".join(state_names))
        return validation_errors

    if 'call_operation' in activity:
        call_operation = activity['call_operation']
        logger.debug("%s '%s': validating 'call_operation'", owner_label, owner.name)
        try:
            operation = call_operation['operation']
        except KeyError:
            validation_errors['call_operation'] = 'no operation specified'
            return validation_errors
        try:
            interface_name, operation_name = operation.rsplit('.', 1)
        except ValueError:
            validation_errors['call_operation'] = "incorrectly formatted operation '{0}'".format(operation)
            return validation_errors
        if call_operation_resolver is not None:
            error = call_operation_resolver(call_operation, interface_name, operation_name)
            if error:
                validation_errors['call_operation'] = error
        return validation_errors

    if 'inline' in activity:
        inline = activity['inline']
        logger.debug("%s '%s': validating 'inline'", owner_label, owner.name)
        if inline not in owner.service.workflows:
            validation_errors['inline'] = "{0} not found".format(inline)
        return validation_errors

    return "unrecognized activity '{0}'".format(activity)
