"""Aislamiento de tests — backstop contra mock-patches leakeados (2026-05-29).

PROBLEMA (flakies intermitentes order-dependent): algunos tests inician un patch con
`patcher.start()` y dependen de su propio tearDown/`with` para detenerlo. Si un test
LEAKEA un patch iniciado (no llama `.stop()`), corrompe a los tests siguientes —
notablemente los que hacen `inspect.getsource(Gemma4Agent.<método>)` para verificar
strings en el código fuente: si el método está parcheado (mock) leen la fuente
EQUIVOCADA y fallan con AssertionError, pero SOLO cuando el test leaker corrió antes
en ese orden (de ahí la intermitencia). Ejemplos vistos: test_inherit_tools_safety::
test_last_turn_ts_attribute_exists, test_phrase_trigger_guards::test_promise_guard,
test_session847_fixes::test_suppression (pasan AISLADOS; fallan a veces en suite full).

FIX: este autouse fixture detiene CUALQUIER patch aún activo después de cada test
(`mock.patch.stopall()` — registro `_active_patches` de los `.start()`). Los patches
bien-manejados (`with patch()` / `@patch` / start+stop en tearDown) YA están detenidos
cuando esto corre, así que es no-op para ellos: SOLO limpia leaks. Garantiza que
ningún patch leakeado cruce a otro test (incluida la corrupción de getsource).
"""
import pytest


@pytest.fixture(autouse=True)
def _stop_leaked_mock_patches():
    yield
    try:
        from unittest import mock
        mock.patch.stopall()
    except Exception:
        pass
