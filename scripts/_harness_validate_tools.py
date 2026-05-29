"""Harness de validación de ROUTING masivo (item 4): para cada tool, varios fraseos
via run_content; reporta qué tool ELIGE el 4B (el valor central: ¿rutea bien?).

SEGURIDAD ABSOLUTA: TODAS las _impls se mockean a no-op (cero ejecución física/real)
+ el syscall user32 (SendInput/keybd/mouse) se neutraliza como red. NADA toca el SO,
el teclado, ni envía mensajes. Sólo se mide el ROUTING. La EJECUCIÓN real de cada tool
ya se validó en items previos (B7 web, B1 recovery, B2 memory, B8 reminder, skills,
MCP) + la suite de tests. run_content sin input físico es seguro (no cierra VS Code).

Reporte -> scripts/_out_tools_report.txt
"""
import ctypes
import os
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")
os.environ["GEMMA4_ACCESSIBILITY_MODE"] = "normal"
os.environ.pop("GEMMA4_STREAM_TTS", None)

# --- RED DE SEGURIDAD: neutralizar el syscall de input físico (cualquier path) ---
try:
    _orig_windll = ctypes.WinDLL
    _BLOCKED = {"SendInput", "keybd_event", "mouse_event", "BlockInput", "SetCursorPos", "mouse_event"}

    class _SafeDLL:
        def __init__(self, dll):
            object.__setattr__(self, "_dll", dll)

        def __getattr__(self, name):
            if name in _BLOCKED:
                return lambda *a, **k: 0
            return getattr(object.__getattribute__(self, "_dll"), name)

    def _safe_windll(name, *a, **k):
        dll = _orig_windll(name, *a, **k)
        if isinstance(name, str) and "user32" in name.lower():
            return _SafeDLL(dll)
        return dll

    ctypes.WinDLL = _safe_windll
except Exception:
    pass

from gemma4_agent.infra.profiles import get_active_profile, apply_profile_to_env
from gemma4_agent.infra.llama_server import get_shared_manager

prof = get_active_profile()
apply_profile_to_env(prof)
mgr = get_shared_manager()
mgr.start(prof, wait_health=True, timeout_s=120)

from gemma4_agent.agent_core.agent import Gemma4Agent

agent = Gemma4Agent()
# --- mock TODAS las _impls a no-op (cero ejecución; sólo medimos qué tool elige) ---
reg = agent.tools
for _name in list(reg._impls.keys()):
    reg._impls[_name] = (lambda n: (lambda args: {"ok": True, "tool": n, "mocked": True,
                                                  "verified": True, "action": (args or {}).get("action")}))(_name)

TABLE = [
    ("app", ["abrí el bloc de notas", "abrí la calculadora", "cerrá spotify", "abrí el explorador de archivos"], {"app", "window"}),
    ("audio", ["subí el volumen", "bajá el volumen", "silenciá el sonido", "poné el volumen al 30 por ciento"], {"audio"}),
    ("system", ["qué hora es", "subí el brillo", "cuánta batería tengo", "qué día es hoy"], {"system", "device_settings"}),
    ("window", ["maximizá la ventana", "minimizá esto", "poné la ventana a la izquierda", "cerrá la ventana"], {"window", "gui"}),
    ("web", ["buscá noticias de hoy", "qué es la fotosíntesis", "buscá recetas de pizza", "cuál es la capital de Japón"], {"web", "browser"}),
    ("media", ["poné música", "pausá la canción", "siguiente tema", "poné rock en spotify"], {"media", "audio"}),
    ("browser", ["abrí youtube", "andá a wikipedia", "abrí github", "navegá a gmail"], {"browser", "app", "web"}),
    ("filesystem", ["buscá un word en documentos", "listá mis descargas", "buscá el archivo presupuesto", "mostrame el escritorio"], {"filesystem", "local_search"}),
    ("reminder", ["recordame comprar pan a las 5", "recordame la reunión mañana 9am", "recordame llamar a mamá", "recordatorio de tomar agua en 1 hora"], {"reminder", "notification"}),
    ("notification", ["alarma a las 7am", "timer de 10 minutos", "avisame en 5 minutos", "alarma para mañana 8am"], {"notification", "reminder"}),
    ("network", ["conectate al wifi de casa", "qué redes wifi hay", "estado de la conexión", "cuál es mi ip"], {"network", "device_settings"}),
    ("vision", ["qué hay en mi pantalla", "leé la pantalla", "describí lo que ves", "qué ventana está abierta"], {"vision", "gui", "uia"}),
    ("gui", ["escribí hola mundo", "apretá enter", "escribí mi nombre", "clickeá aceptar"], {"gui", "computer_use", "uia"}),
    ("whatsapp", ["mandale un whatsapp a Juan", "escribile a mamá por whatsapp", "enviá un mensaje a Pedro", "whatsapp a mi hermano"], {"whatsapp"}),
    ("email", ["mandá un correo a juan@x.com", "escribile un email a mi jefe", "enviá un mail", "redactá un correo"], {"email"}),
]

report, hits, total = [], 0, 0
t0 = time.monotonic()
for ti, (tool, prompts, accepted) in enumerate(TABLE):
    if ti == len(TABLE) // 2:
        try:
            mgr.start(prof, wait_health=True, timeout_s=120)  # frescura anti-degradación
            report.append(f"  [server refresh @ {tool}]")
        except Exception:
            pass
    report.append(f"\n### {tool} (acepta {sorted(accepted)})")
    for p in prompts:
        total += 1
        try:
            agent.history.clear()
        except Exception:
            pass
        try:
            r = agent.run_content(p)
            used = [getattr(e, "name", "?") for e in (getattr(r, "tool_events", []) or [])]
            reply = (getattr(r, "content", "") or "").replace("\n", " ")
        except Exception as exc:
            used, reply = ["<EXC>"], f"{type(exc).__name__}: {exc}"
        ok = bool(set(used) & accepted)
        if ok:
            hits += 1
        report.append(f"  [{'OK  ' if ok else 'MISS'}] {p[:44]!r} -> {used} | {reply[:60]!r}")

dt = time.monotonic() - t0
head = f"{'='*64}\nROUTING: {hits}/{total} pedidos rutearon a una tool aceptable ({dt:.0f}s)\n{'='*64}"
Path("scripts/_out_tools_report.txt").write_text(head + "\n" + "\n".join(report), encoding="utf-8")
print(head)
