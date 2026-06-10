"""Guards de seguridad de la suite — cargados por el conftest RAÍZ del repo.

Vive como módulo (no inline en un conftest) para que UN solo conftest en la raíz
del proyecto lo active globalmente: así NINGÚN test —corra desde donde corra, en
gemma4_agent/tests/, voice/tests/, o un subconjunto— puede abrir programas,
ventanas o el navegador. No requiere ningún flag ni comando especial: es el
comportamiento por defecto de cualquier corrida de pytest sobre este repo.

Las LECTURAS (Get-Clipboard, queries WMI/registro, Get-Process…) PASAN reales, así
la suite sigue comprobando todo; SOLO se interceptan los efectos de APERTURA.
"""
from __future__ import annotations

import os

# Registro de efectos interceptados (para que un test pueda assert_called si quiere).
RECORDED: dict[str, list] = {"startfile": [], "webbrowser": [], "sendinput": [], "spawn": []}

_INSTALLED = False


def install() -> dict[str, list]:
    """Instala los stubs seguros UNA vez (idempotente). Devuelve el registro."""
    global _INSTALLED
    if _INSTALLED:
        return RECORDED
    _INSTALLED = True

    # El código del agente puede consultar GEMMA4_DIAG para no disparar efectos
    # pesados. La suite corre en modo diagnóstico por defecto.
    os.environ.setdefault("GEMMA4_DIAG", "1")

    # os.startfile (Steam URIs, abrir archivos/apps) — NO-OP que registra.
    if hasattr(os, "startfile"):
        def _safe_startfile(path, *a, **k):  # type: ignore[no-redef]
            RECORDED["startfile"].append(path)
            return None
        os.startfile = _safe_startfile  # type: ignore[attr-defined]

    # webbrowser.open / open_new / open_new_tab — NO abrir el navegador real.
    # webbrowser es stdlib (siempre presente), así que no necesita guarda de import.
    import webbrowser

    def _safe_wb(url, *a, **k):
        RECORDED["webbrowser"].append(url)
        return True
    webbrowser.open = _safe_wb          # type: ignore[assignment]
    webbrowser.open_new = _safe_wb      # type: ignore[assignment]
    webbrowser.open_new_tab = _safe_wb  # type: ignore[assignment]

    # subprocess.run / Popen — interceptar SOLO los comandos que ABREN apps/ventanas
    # (Start-Process, `cmd /c start`, deeplinks steam://, lanzar un .exe directo).
    # Las LECTURAS PASAN reales para que los tests sigan comprobando.
    import subprocess as _sp

    def _is_app_open_cmd(cmd) -> bool:
        if isinstance(cmd, (list, tuple)):
            flat = " ".join(str(c) for c in cmd)
        else:
            flat = str(cmd)
        low = flat.lower()
        if "start-process" in low:
            return True
        if "steam://" in low or ("://" in low and any(
                p in low for p in ("openurl", "store", "install", "/run/"))):
            return True
        # `cmd /c start ...` (deeplinks, abrir apps)
        if "start" in low and (" /c " in low or low.startswith("cmd")):
            return True
        # invocar un .exe/.lnk directo "de usuario". Se EXCLUYEN los intérpretes y
        # herramientas de dev (python/node/git/...): un test puede lanzar un
        # subprocess de Python legítimo (p.ej. correr un script de auditoría) y eso
        # NO es "abrir una app a la cara del usuario" — bloquearlo rompería el test
        # devolviéndole stdout vacío.
        _DEV_TOOLS = ("python", "pythonw", "\\py.exe", "/py.exe", "node", "npm",
                      "npx", "git", "pip", "powershell", "pwsh", "cmd", "conhost")
        if isinstance(cmd, (list, tuple)) and cmd:
            head = str(cmd[0]).lower()
            if (head.endswith(".exe") or head.endswith(".lnk")) and not any(
                    p in head for p in _DEV_TOOLS):
                return True
        return False

    class _FakeCompleted:
        def __init__(self, cmd):
            self.args = cmd
            self.returncode = 0
            self.stdout = ""
            self.stderr = ""

    class _FakePopen:
        def __init__(self, cmd):
            self.args = cmd
            self.returncode = 0
            self.pid = -1
        def communicate(self, *a, **k):
            return ("", "")
        def wait(self, *a, **k):
            return 0
        def poll(self):
            return 0
        def kill(self):
            return None
        def terminate(self):
            return None

    _real_run = _sp.run
    _real_popen = _sp.Popen

    def _safe_run(cmd, *a, **k):
        if _is_app_open_cmd(cmd):
            RECORDED["spawn"].append(cmd)
            return _FakeCompleted(cmd)
        return _real_run(cmd, *a, **k)

    class _SafePopen:
        def __new__(cls, cmd, *a, **k):
            if _is_app_open_cmd(cmd):
                RECORDED["spawn"].append(cmd)
                return _FakePopen(cmd)
            return _real_popen(cmd, *a, **k)

    _sp.run = _safe_run          # type: ignore[assignment]
    _sp.Popen = _SafePopen       # type: ignore[assignment]

    return RECORDED
