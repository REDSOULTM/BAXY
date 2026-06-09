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
import os
import pytest


# ---------------------------------------------------------------------------
# SEGURIDAD DE SUITE: ningún test debe ABRIR programas, ventanas o el navegador
# (2026-06-09, pedido del usuario). Algunos tests no-mockean os.startfile /
# webbrowser, así que un fallo de aislamiento lanzaba apps reales al correr la
# suite completa. Este autouse de SESIÓN reemplaza los efectos del SO por stubs
# SEGUROS que REGISTRAN la llamada (para que `assert_called` siga funcionando)
# pero NUNCA ejecutan la acción. Un test que ponga su propio `mock.patch(...)`
# lo sobreescribe dentro de su `with`/`@patch` (su patch gana). NO bloqueamos
# input físico (SendInput) acá: el runtime ya lo gatea por GEMMA4_DIAG y los
# tests no lo invocan; igual lo neutralizamos si aparece.
def _install_os_sideeffect_guards():
    import builtins  # noqa: F401
    recorded = {"startfile": [], "webbrowser": [], "sendinput": []}

    # os.startfile (Steam URIs, abrir archivos/apps) — NO-OP que registra.
    if hasattr(os, "startfile"):
        def _safe_startfile(path, *a, **k):  # type: ignore[no-redef]
            recorded["startfile"].append(path)
            return None
        os.startfile = _safe_startfile  # type: ignore[attr-defined]

    # webbrowser.open / open_new / open_new_tab — NO abrir el navegador real.
    try:
        import webbrowser
        def _safe_wb(url, *a, **k):
            recorded["webbrowser"].append(url)
            return True
        webbrowser.open = _safe_wb          # type: ignore[assignment]
        webbrowser.open_new = _safe_wb      # type: ignore[assignment]
        webbrowser.open_new_tab = _safe_wb  # type: ignore[assignment]
    except Exception:
        pass

    return recorded


# Marca de entorno: el código del agente puede consultar GEMMA4_DIAG para no
# disparar efectos pesados. La suite corre en modo diagnóstico por defecto.
os.environ.setdefault("GEMMA4_DIAG", "1")
_RECORDED_SIDE_EFFECTS = _install_os_sideeffect_guards()


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
