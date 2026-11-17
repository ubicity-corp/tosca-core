"""
Resolved-function caching regression tests.

The engine stores a resolved function as ``{$(sig_id[:type_id]): args}``: ``sig_id``
is the DB id of the matched signature, and the optional ``type_id`` caches the per-call-site
resolved templated type ``<T>`` so evaluation need not re-resolve it. These tests pin the
mechanism that a full deploy exercises only indirectly:

- the key format round-trips (``parse_function_key``);
- ``ToscaSignature.function_expression`` preserves the ``:type_id`` suffix when it re-emits a
  deferred function -- the bug that silently dropped the suffix and forced a live re-resolution
  on every eval (hundreds of cache misses across the suite);
- the display helper rewrites resolved keys back to names, idempotently;
- a resolved ``$(sig:type)`` key rehydrates its cached type and threads it into
  ``signature.evaluate`` as ``resolved_type`` -- i.e. eval USES the cache rather than
  re-resolving. A bare ``$(sig)`` threads ``None`` (the pre-cache / uncacheable path).

These are unit-level and DB-free: the two module-level lookups (``get_signature``,
``get_data_type_by_id``) are monkeypatched, so no app context or onboarded profile is needed.
"""

from types import SimpleNamespace

import tosca_core.models.function as f
import tosca_core.models.function_declaration as fd


# ---------------------------------------------------------------------------
# Key format
# ---------------------------------------------------------------------------

def test_parse_function_key_roundtrip():
    # A bare signature id, and a signature id carrying the cached type id.
    assert fd.parse_function_key('$(114)') == (114, None)
    assert fd.parse_function_key('$(114:17)') == (114, 17)
    # Named (unresolved) functions and non-keys are not signature keys.
    assert fd.parse_function_key('$get_property') is None
    assert fd.parse_function_key('$(x)') is None
    assert fd.parse_function_key('$(114:x)') is None
    assert fd.parse_function_key('notakey') is None
    assert fd.is_function_key('$(114:17)') is True
    assert fd.is_function_key('$get_property') is False


# ---------------------------------------------------------------------------
# function_expression: the suffix-preservation fix
# ---------------------------------------------------------------------------

def _emit(sig_id, resolved_type):
    """Call ToscaSignature.function_expression with a duck-typed self (it only reads
    self.id) and return the single resolved key it produced."""
    sig = SimpleNamespace(id=sig_id)
    expr = fd.ToscaSignature.function_expression(sig, ['arg'], resolved_type=resolved_type)
    (key,) = list(expr.keys())
    return key


def test_function_expression_preserves_resolved_type_suffix():
    # A resolved <T> type with a DB id -> the key carries ':type_id' (this is the fix:
    # a deferred re-emit used to drop it, so the next eval re-resolved from scratch).
    assert fd.parse_function_key(_emit(114, SimpleNamespace(id=17))) == (114, 17)


def test_function_expression_omits_suffix_without_cacheable_type():
    # No resolved type (non-templated / uncacheable) -> a bare '$(sig_id)'.
    assert fd.parse_function_key(_emit(114, None)) == (114, None)
    # A resolved type with no DB id cannot be cached by id -> also bare.
    assert fd.parse_function_key(_emit(114, SimpleNamespace(id=None))) == (114, None)


# ---------------------------------------------------------------------------
# Display: resolve_function_names
# ---------------------------------------------------------------------------

def test_resolve_function_names_rewrites_and_is_idempotent(monkeypatch):
    fake = SimpleNamespace(function=SimpleNamespace(name='valid_values'))
    monkeypatch.setattr(fd, 'get_signature', lambda sid: fake)

    pretty = fd.resolve_function_names({'$(13:17)': [['a', 'b']]})
    assert pretty == {'$valid_values': [['a', 'b']]}
    # Idempotent: a second pass finds no '$(sig)' key to rewrite.
    assert fd.resolve_function_names(pretty) == {'$valid_values': [['a', 'b']]}
    # Non-function structures pass through untouched.
    assert fd.resolve_function_names({'x': 1, 'y': [1, 2]}) == {'x': 1, 'y': [1, 2]}


def test_resolve_function_names_never_raises_on_dangling_id(monkeypatch):
    def _boom(sid):
        raise RuntimeError("no such signature")
    monkeypatch.setattr(fd, 'get_signature', _boom)
    # A dangling id keeps the raw node rather than raising (display is best-effort).
    assert fd.resolve_function_names({'$(999)': [1]}) == {'$(999)': [1]}


# ---------------------------------------------------------------------------
# Usage: eval threads the cached type instead of re-resolving
# ---------------------------------------------------------------------------

class _RecordingSignature:
    """A stand-in signature whose evaluate() records the resolved_type it was handed."""
    id = 114

    def __init__(self):
        self.function = SimpleNamespace(name='is_defined')
        self.seen_resolved_type = '<<unset>>'

    def evaluate(self, context, args, resolved_type=None, **kwargs):
        self.seen_resolved_type = resolved_type
        return 'RESULT'


def _build_resolved_function(monkeypatch, key, cached_type):
    sig = _RecordingSignature()
    monkeypatch.setattr(fd, 'get_signature', lambda sid: sig)
    monkeypatch.setattr(fd, 'get_data_type_by_id', lambda tid: cached_type)
    func = f.ToscaFunction({key: ['x']})
    return func, sig


def test_eval_threads_cached_resolved_type(monkeypatch):
    # A '$(sig:type)' key rehydrates the cached type and hands it to signature.evaluate,
    # so the templated <T> is NOT re-resolved at eval.
    sentinel = object()
    func, sig = _build_resolved_function(monkeypatch, '$(114:17)', sentinel)
    assert func.resolved_type is sentinel
    assert func.evaluate(context=None) == 'RESULT'
    assert sig.seen_resolved_type is sentinel


def test_eval_without_cached_type_threads_none(monkeypatch):
    # A bare '$(sig)' key carries no cached type -> None is threaded (the real signature
    # would then re-resolve live; here we just assert nothing spurious is cached).
    func, sig = _build_resolved_function(monkeypatch, '$(114)', object())
    assert func.resolved_type is None
    assert func.evaluate(context=None) == 'RESULT'
    assert sig.seen_resolved_type is None
