# HOTFIX 2026-05-17 — GUI silent crash + Spotify deeplink race

> Continuá el mismo chat de Claude Code (Sprints 0-8b + voice fixes
> de hoy 795f7a6 / b38ec32). Hotfix corto, dos bugs reportados por el
> usuario en la sesión 15:27-15:49 del 2026-05-17.

---

## Contexto

Estado del repo: rama PortandoLoMejor, HEAD `b38ec32` (voice toast fix),
working tree limpio salvo dos untracked viejos (`compass_artifact_*.md`
y `gemma4_audit_for_external_review.zip`) que NO se tocan.

Dos fallos en la sesión de hoy, capturados en
`~/.gemma4/logs/_pre_session/chat.log` + `full.log`:

### Fallo 1 — GUI cerró sola sin escribir error

- 15:27:08 → arranque de sesión.
- 15:31:55 → último turn ("Dónde dejaste el Powerpoint?" → "No alcancé").
- **15 minutos de silencio absoluto** en logs.
- 15:46:51 → arranque de NUEVA sesión (proceso fresco).

No hay traceback en `full.log`. No hay error en `chat.log`. No hay crash
en `gemma4_agent/logs/llama-server.err.log` (llama-server siguió OK).
Ningún evento `turn error` ni `voice failed` cerca del cierre.

Diagnóstico provisorio: el proceso Qt murió por algo fuera del scope de
nuestros loggers — posibles candidatos:
- Excepción no capturada en un slot Qt (Qt mata la app sin propagar al
  stdout si no hay sys.excepthook seteado).
- Excepción en un worker thread no daemon que no se loggea.
- `QApplication.quit()` invocado por un código de path que no
  logueamos.
- OS kill (memoria, energy saver) — improbable pero posible.

NO sabemos cuál fue. Por eso el hotfix de este fallo es INSTRUMENTACIÓN,
no fix directo: queremos que la PRÓXIMA vez que pase, sepamos qué fue.

### Fallo 2 — Spotify reprodujo la cola en vez de Michael Jackson

- 15:47:30 user: "pon una canción de Michael Jackson en Spotify"
- 15:47:33 tool dispatched: `media({"action":"play","provider":"spotify","query":"Michael Jackson"})`
- 15:47:36 GEMMA: "Listo, Michael Jackson reproduciéndose en Spotify"
- En realidad: Spotify YA estaba abierto con una canción en la cola, y
  lo que se reprodujo fue esa canción, NO Michael Jackson.

Root cause: en `gemma4_agent/domain_tools.py:6781-6900` (`_spotify_auto_play`)
el `auto_play_wait=1.8s` es muy corto cuando Spotify ya está abierto en
una vista que NO es search. El deeplink `spotify:search:<q>` navega la
UI, pero si Spotify estaba mostrando el player, tarda 2-4s en cambiar
a search results. Cuando se manda Enter a 1.8s+0.3s≈2.1s, Spotify
todavía está en player view → Enter reproduce lo seleccionado en el
player (la cola), no el primer resultado de búsqueda.

El tool reporta `played=True, verified=True, status="dispatched"` porque
**el Enter SE PRESIONÓ con éxito** sobre la ventana Spotify. No hay
ningún check de que la canción tocando coincida con la query.

---

## OBJETIVO DEL HOTFIX

Dos cambios chicos, dos commits separados:

1. **`fix(spotify)`**: detectar si Spotify ya estaba abierto y subir el
   wait dinámicamente; agregar verificación post-keypress del título
   tocando.
2. **`fix(gui)`**: hookear `sys.excepthook` global + qInstallMessageHandler
   en la app principal para que cualquier excepción no capturada se
   loggee a `~/.gemma4/logs/_pre_session/full.log` antes de morir.

Ningún cambio en routing, voice, planner, ni nada fuera de los dos
archivos directos.

---

## REGLAS GENERALES

1. Trabajás en PortandoLoMejor. Commits chicos, prefijo
   `fix(spotify):` y `fix(gui):`.
2. NO toques planner.py, agent.py, router_v2.py, semantic_router.py.
3. NO toques las 65 compound tools NI sus schemas.
4. NO modifiques tool_descriptions.yaml.
5. NUNCA `git add -A`.
6. Verificación post-commit:
   - `python -m pytest gemma4_agent/ -q` — debe seguir en 809 passed +
     1 pre-existing failure (test_planner_continuation.py).
   - `python -m gemma4_agent.launcher status` debe imprimir sin
     crashear.
   - `python -c "import gemma4_agent"` OK.

---

## FIX 1 — Spotify race condition

### 1.1 — Detectar Spotify ya abierto + wait dinámico

En `gemma4_agent/domain_tools.py`, antes de invocar `_spotify_auto_play`
(línea ~6938), agregá una check rápida del estado de la ventana
Spotify. Pseudocódigo:

```python
def _detect_spotify_already_running(executor: Executor) -> bool:
    """Devuelve True si hay una ventana 'Spotify' activa antes de
    enviar el deeplink. Si lo hay, vamos a subir el wait porque
    Spotify tarda más en navegar entre vistas que en cold-launch.
    """
    try:
        windows = executor("window", {"action": "list"})
    except Exception:
        return False
    items = windows.get("windows") or windows.get("items") or []
    if not isinstance(items, list):
        return False
    for w in items:
        title = ""
        if isinstance(w, dict):
            title = str(w.get("title") or "")
        else:
            title = str(w)
        if "spotify" in title.lower():
            return True
    return False
```

Después, en el bloque donde se llama `_spotify_auto_play`:

```python
if auto_play and executor is not None and canonical == "spotify":
    already_open = _detect_spotify_already_running(executor)
    # Si Spotify ya estaba abierto, el deeplink demora más en navegar
    # de player view a search results. El default 1.8s alcanza para
    # cold-launch (donde el splash + load tarda más que la navegación)
    # pero NO alcanza warm. Subimos a 3.5s en ese caso.
    effective_wait = max(auto_play_wait, 3.5) if already_open else auto_play_wait
    auto_play_info = _spotify_auto_play(executor, effective_wait)
    if auto_play_info is not None:
        auto_play_info["was_already_open"] = already_open
        auto_play_info["wait_seconds_used"] = effective_wait
```

### 1.2 — Verificación post-keypress

En `_spotify_auto_play`, después del `gui.keypress(enter)` exitoso,
agregar UN check del Now Playing title de Spotify para validar que la
canción que toca coincide con la query:

```python
# Post-keypress: validar que el track tocando matchea la query.
# Spotify muestra el now-playing en la barra de tareas / window title.
# Si el query es "Michael Jackson", esperamos que el title contenga
# "Michael Jackson" o un nombre de track conocido.
import time as _time
_time.sleep(0.8)  # dar tiempo a Spotify a actualizar el title
try:
    now_active = executor("window", {"action": "active"})
except Exception:
    now_active = {}
now_title = ""
na = now_active.get("active")
if isinstance(na, dict):
    now_title = str(na.get("title") or "")
else:
    now_title = str(now_active.get("title") or "")

# Heurística: si el title contiene cualquier palabra de la query con
# ≥4 caracteres, consideramos match. Spotify title format típico:
# "Track Name • Artist Name". Conservador: NO penalizamos si el title
# no contiene la query — sólo flageamos como "query_match=False" en
# el return para que el LLM sepa que hay duda.
query_words = [w for w in str(query).lower().split() if len(w) >= 4]
title_lower = now_title.lower()
query_match = any(w in title_lower for w in query_words) if query_words else None
```

Y agregar al return:

```python
return {
    "played": True,
    "focus_verified": True,
    "abort_reason": None,
    "wait_seconds": wait_seconds,
    "post_play_title": now_title,
    "query_match": query_match,  # True / False / None
}
```

En el caller `_media_play_streaming` que arma el `_ok`, propagar
`query_match` y modificar `completion_status` y `note`:

```python
played = bool(auto_play_info and auto_play_info.get("played"))
qmatch = auto_play_info.get("query_match") if auto_play_info else None
# Si played=True pero query_match=False, NO marcamos verified=True.
# El LLM tiene que saber que el Enter funcionó pero el track tocando
# probablemente no es lo que el user pidió.
verified = played and qmatch is not False  # True or None counts as OK
status_suffix = "" if qmatch is not False else " · WARN: now-playing title does not match query"
return _ok(
    ...,
    played=played,
    verified=verified,
    completion_status=("media_playing_match" if qmatch is True
                       else "media_playing_unverified" if qmatch is None
                       else "media_playing_wrong_track"),
    note=(f"{canonical}: played{status_suffix}"),
    ...
)
```

### 1.3 — Tests

Crear `gemma4_agent/test_spotify_race.py` con dos test:

```python
"""Regression tests for the Spotify already-open race condition.

Discovered 2026-05-17: when Spotify was already open showing the
player, `auto_play_wait=1.8s` was too short — Enter fired before
search results rendered, playing whatever was in the queue.
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from gemma4_agent.domain_tools import _detect_spotify_already_running


class DetectSpotifyOpenTest(unittest.TestCase):
    def test_returns_true_when_window_list_contains_spotify(self) -> None:
        executor = MagicMock()
        executor.return_value = {"windows": [
            {"title": "Spotify - Free"},
            {"title": "Notepad"},
        ]}
        self.assertTrue(_detect_spotify_already_running(executor))

    def test_returns_false_when_no_spotify_window(self) -> None:
        executor = MagicMock()
        executor.return_value = {"windows": [{"title": "Notepad"}]}
        self.assertFalse(_detect_spotify_already_running(executor))

    def test_returns_false_when_executor_fails(self) -> None:
        executor = MagicMock(side_effect=Exception("test"))
        self.assertFalse(_detect_spotify_already_running(executor))

    def test_returns_false_when_windows_key_missing(self) -> None:
        executor = MagicMock()
        executor.return_value = {}
        self.assertFalse(_detect_spotify_already_running(executor))


class SpotifyAutoPlayWaitBumpTest(unittest.TestCase):
    """When Spotify is already open, the wait MUST be ≥ 3.5s."""

    @patch("gemma4_agent.domain_tools._spotify_auto_play")
    @patch("gemma4_agent.domain_tools._detect_spotify_already_running")
    def test_wait_bumped_when_spotify_already_open(self, mock_detect, mock_autoplay):
        mock_detect.return_value = True
        mock_autoplay.return_value = {"played": True, "wait_seconds": 3.5}
        # Trigger the path that calls _spotify_auto_play. Easiest is to
        # call _media_play_streaming directly with auto_play=True.
        # (Pseudocódigo; ajustar al firmado real de la función.)
        from gemma4_agent.domain_tools import _media_play_streaming
        executor = MagicMock()
        _media_play_streaming(
            "spotify", "Michael Jackson", {},
            executor=executor, auto_play=True, auto_play_wait=1.8,
        )
        # Verificar que _spotify_auto_play fue llamado con 3.5s y no 1.8s.
        args, kwargs = mock_autoplay.call_args
        # El segundo arg posicional o el kwarg wait_seconds debe ser 3.5.
        wait_arg = args[1] if len(args) >= 2 else kwargs.get("wait_seconds")
        self.assertGreaterEqual(wait_arg, 3.5)


if __name__ == "__main__":
    unittest.main()
```

Si el test "wait bumped" es muy difícil de cablear por la complejidad
de `_media_play_streaming`, dejá sólo el `DetectSpotifyOpenTest` y
agregá un comentario `# TODO: integration test for the wait-bump
path` en el archivo. NO inviertas más de 30 min en ese test.

### 1.4 — Commit

`fix(spotify): bump auto_play_wait when Spotify already open + verify post-play title`

---

## FIX 2 — Instrumentación de cierre silencioso de GUI

### 2.1 — Hookear sys.excepthook + qInstallMessageHandler

Localizar el entry-point de la GUI. Probablemente `gemma4_agent/ui/`
o `gemma4_agent/main.py` o donde se crea el `QApplication`. Listalo
con:

```bash
grep -rn "QApplication\|qInstallMessageHandler\|sys.excepthook" gemma4_agent/ | head
```

Donde se crea el `QApplication`, ANTES de `app.exec()`, agregar:

```python
import sys
import traceback
import logging
from pathlib import Path

# Log path: el mismo que ya usa el pre-session recorder, así no
# proliferamos lugares de log.
_CRASH_LOG = Path.home() / ".gemma4" / "logs" / "_pre_session" / "crash.log"
_CRASH_LOG.parent.mkdir(parents=True, exist_ok=True)

_crash_logger = logging.getLogger("gemma4.crash")
_crash_logger.setLevel(logging.ERROR)
_crash_handler = logging.FileHandler(_CRASH_LOG, encoding="utf-8")
_crash_handler.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
))
_crash_logger.addHandler(_crash_handler)
_crash_logger.propagate = False  # no spam stdout

def _excepthook(exc_type, exc_value, exc_tb):
    """Captura cualquier excepción no manejada antes de que Python o
    Qt maten el proceso silenciosamente.

    Por defecto en Qt+PyQt, una excepción dentro de un slot puede
    matar la app sin que aparezca en stdout (depende de la versión).
    Esto persiste el traceback a un archivo dedicado para que la
    próxima vez que la GUI muera "de la nada", tengamos evidencia.
    """
    tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    _crash_logger.error("UNHANDLED EXCEPTION:\n%s", tb_text)
    # Re-emite al stderr default por si el operador lo está viendo
    # en una terminal.
    sys.__excepthook__(exc_type, exc_value, exc_tb)

sys.excepthook = _excepthook

# Qt también tiene su propio canal de mensajes que normalmente no se
# loggea. Hookearlo para capturar "QObject::connect: No such slot",
# "Qt has caught an exception thrown from an event handler", etc.
try:
    from PyQt6.QtCore import qInstallMessageHandler, QtMsgType  # type: ignore
except Exception:
    qInstallMessageHandler = None  # type: ignore
    QtMsgType = None  # type: ignore

if qInstallMessageHandler is not None:
    def _qt_msg_handler(msg_type, context, message):
        # Sólo loggeamos warning y critical / fatal. Debug e info los
        # filtramos para no spamear.
        try:
            level_name = getattr(msg_type, "name", str(msg_type))
        except Exception:
            level_name = str(msg_type)
        try:
            sev = int(msg_type)
        except Exception:
            sev = 0
        # QtMsgType: Debug=0, Info=4, Warning=1, Critical=2, Fatal=3
        if sev in (1, 2, 3):
            _crash_logger.error("Qt[%s]: %s", level_name, message)

    qInstallMessageHandler(_qt_msg_handler)
```

Asegurate de instalarlo lo más temprano posible — antes de cualquier
import que pueda crashear, idealmente como segundo statement después
de los imports estándar de la entry function.

### 2.2 — Smoke test

NO escribas un test que crashee la GUI a propósito (es lento y complejo).
En su lugar, smoke test de que el handler está instalado:

```python
# gemma4_agent/test_crash_logging.py
def test_excepthook_is_installed():
    """Cuando la GUI arranca, sys.excepthook debe estar custom.
    Smoke check: importar el módulo y verificar que el hook está
    seteado a algo que no es el default.
    """
    import sys
    # Importar el módulo de GUI que instala el hook. Ajustar el
    # import a tu entry point real (gemma4_agent.ui.main o similar).
    from gemma4_agent.ui import main as ui_main  # adjust if needed
    # Trigger any side-effect-only init.
    ui_main._install_crash_hooks()  # the function name you used
    assert sys.excepthook is not sys.__excepthook__, (
        "sys.excepthook should be replaced by the GUI crash hook"
    )
```

Si la arquitectura de entry point no permite invocar `_install_crash_hooks()`
sin levantar QApplication, OMITÍ este test y comentá un TODO en el
módulo: `# TODO: add a test that doesn't require QApplication`. NO
levantes Qt en un test unitario.

### 2.3 — Commit

`fix(gui): persist unhandled exceptions + Qt warnings to crash.log`

---

## REPORTE FINAL

Al terminar devolveme:

1. Hash de los dos commits (`fix(spotify):` y `fix(gui):`).
2. Output completo de `python -m pytest gemma4_agent/ -q --tb=line`.
3. Sample del nuevo `crash.log` si lograste triggerar un excepthook
   de prueba (opcional — sólo si lo hiciste sin Qt).
4. Diff resumido (sólo nombres de archivos + líneas cambiadas) de
   cada commit.

## CRITERIO DE ÉXITO

- 2 commits aterrizados.
- 809 passed + 1 pre-existing failure mantenido. Tests nuevos verde.
- `python -m gemma4_agent.launcher status` corre OK.
- `import gemma4_agent` OK.
- Working tree limpio post-cierre (salvo los 2 untracked viejos que
  ya estaban).

## NO HACER (anti-scope)

- NO toques el router_v2, router viejo, planner, tool_descriptions.yaml.
- NO toques el código de voice (wake.py / stt.py / voice_runner.py)
  — ya hicimos fixes esta tarde.
- NO modifiques las 65 compound tools.
- NO uses UIA para detectar Spotify search-view vs player-view (es
  fragil y caro). El title check es suficiente.
- NO instales librerías nuevas.
- NO migrés a PyQt5 si encontrás algo raro con PyQt6. Loggear el
  síntoma y seguir.
- NO inviertas más de 30 min en el integration test de wait-bump.
  Si es complicado, dejalo como TODO.
