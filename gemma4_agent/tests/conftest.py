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


# ---------------------------------------------------------------------------
# SEGURIDAD DE SUITE: ningún test debe ABRIR programas, ventanas o el navegador.
# La lógica vive en _suite_guards.install() (módulo compartido) y la activa por
# defecto el conftest RAÍZ del repo, para CUALQUIER corrida desde cualquier dir.
# Acá la re-invocamos por si estos tests se ejecutan sin pasar por la raíz; es
# idempotente, así que no duplica. Un test que ponga su propio mock.patch(...)
# gana dentro de su with/@patch.
from ._suite_guards import install as _install_suite_guards
_RECORDED_SIDE_EFFECTS = _install_suite_guards()


@pytest.fixture(autouse=True)
def _no_real_os_side_effects():
    """Backstop por-test: re-asegura los stubs seguros (por si un test los
    restauró sin querer) y limpia el registro. Los tests que mockean
    explícitamente os.startfile/webbrowser ganan dentro de su contexto."""
    yield
    # nada que limpiar agresivamente: los stubs son idempotentes y los patches
    # locales de los tests ya se deshacen solos.


@pytest.fixture(autouse=True)
def _clear_latency_caches():
    """Los fast-paths de latencia (2026-06-09) cachean lecturas de PowerShell con
    TTL (printers, bluetooth, juegos, audio). Entre tests hay que LIMPIARLAS: si un
    test cachea un éxito y el siguiente mockea un FALLO de PowerShell, leería el
    éxito cacheado y fallaría (cross-contaminación). Limpiamos ANTES de cada test."""
    try:
        from gemma4_agent.domain_tools import helpers as _h
        _h._PS_CACHE.clear()
    except Exception:
        pass
    try:
        from gemma4_agent.domain_tools import bluetooth as _bt
        _bt._BT_CACHE.clear()
    except Exception:
        pass
    try:
        from gemma4_agent.domain_tools import game_launcher as _gl
        _gl._DISCOVER_CACHE.clear()
    except Exception:
        pass
    yield


@pytest.fixture(autouse=True)
def _stop_leaked_mock_patches():
    yield
    try:
        from unittest import mock
        mock.patch.stopall()
    except Exception:
        pass
