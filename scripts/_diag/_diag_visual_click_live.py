"""EN VIVO (CLAUDE.md 3.5): bugs de las capturas 2026-06-08.

1. "apretá el icono de Mortal Kombat" (visible en Steam) -> antes steam(click) ->
   launch_game -> callejón. AHORA debe redirigir a gui(click_text).
2. La descripción de visión NO debe volcar el OCR crudo al reply.

Corre el LLM REAL y varios fraseos (el 4B rutea distinto por fraseo). NO mockea
`execute` (el fix vive dentro), solo stubea los EFECTOS físicos: el OCR/screenshot
y el click real. Captura la tool FINAL que se ejecutó tras la redirección.
"""
import sys, os
sys.path.insert(0, os.path.abspath("."))
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")
os.environ.setdefault("GEMMA4_DIAG", "1")
os.environ.setdefault("GEMMA4_AGENT_SAFETY", "0")

from gemma4_agent.infra.profiles import get_active_profile, apply_profile_to_env
from gemma4_agent.infra.llama_server import get_shared_manager
prof = get_active_profile(); apply_profile_to_env(prof)
get_shared_manager().start(prof, wait_health=True, timeout_s=120)
print("[boot] OK", flush=True)

import gemma4_agent.tools_pkg.tools as T

# Capturar el tool-call CRUDO que emite el 4B (antes de cualquier redirección)
_raw = []
_orig_execute = T.ToolRegistry.execute
def _spy_execute(self, name, args=None):
    _raw.append((name, dict(args or {})))
    return _orig_execute(self, name, args)
T.ToolRegistry.execute = _spy_execute

# Capturar la action FINAL que llega a cada impl (post-redirección) sin romper
# el fix: parcheamos los métodos de bajo nivel, NO execute().
_calls = []  # (tool_name, action) que REALMENTE se despacharon

# gui(click_text) cae en t_gui -> action click_text. Interceptamos t_gui para
# registrar y cortocircuitar el OCR/click real, pero SOLO para click_text.
_orig_t_gui = T.ToolRegistry.t_gui
def _t_gui(self, args):
    act = str((args or {}).get("action") or "").strip()
    if act in {"click_text", "locate_text"}:
        _calls.append(("gui." + act, str(args.get("text") or args.get("target"))))
        return {"ok": True, "found": True, "clicked": True,
                "matches": [{"text": args.get("text")}],
                "completion_status": "clicked_text", "_eval_mock": True}
    return _orig_t_gui(self, args)
T.ToolRegistry.t_gui = _t_gui

# steam/app/window reales harían os.startfile -> stub para no lanzar nada físico,
# pero queremos VER si el 4B vuelve a caer en steam tras la redirección.
_orig_t_steam = T.ToolRegistry.t_steam
def _t_steam(self, args):
    _calls.append(("steam", str((args or {}).get("action"))))
    return {"ok": False, "status": "needs_user", "note": "stubbed", "_eval_mock": True}
T.ToolRegistry.t_steam = _t_steam

from gemma4_agent.agent_core.agent import Gemma4Agent

PHRASES = [
    "apretá el icono de Mortal Kombat",
    "hacé click en Mortal Kombat",
    "clickeá Mortal Kombat",
    "presioná el botón de Mortal Kombat que está en pantalla",
]
print("\n=== BUG 1: click visual -> gui(click_text), NO steam dead-end ===", flush=True)
for ph in PHRASES:
    agent = Gemma4Agent()
    agent.run_content("hola"); agent.history.clear()
    # contexto: el user dijo que ve Steam (como en la captura)
    agent.run_content("en mi pantalla estoy viendo Steam")
    _calls.clear(); _raw.clear()
    r = agent.run_content(ph)
    print(f"\n  RAW tool-calls del 4B: {_raw}", flush=True)
    reply = (getattr(r, "content", "") or "")[:90]
    print(f"\n  FRASE: {ph!r}", flush=True)
    print(f"  TOOLS: {_calls}", flush=True)
    print(f"  reply: {reply!r}", flush=True)
    ok = any(t.startswith("gui.click") or t.startswith("gui.locate") for t, _ in _calls)
    print(f"  -> {'OK click_text' if ok else 'NO llegó a gui.click_text'}", flush=True)

print("\n=== BUG 2: descripción de visión SIN dump de OCR ===", flush=True)
from gemma4_agent.tools_pkg.vision_describe import _strip_ocr_echo
samples = [
    'Se ve la app ChatGPT. <<<0 a_ox @ chatgpt.com BI [aM Recibidos>>> con pestañas.',
    'La pantalla muestra Steam. El OCR leyó "Mortal Kombat, Terraria". Hay una barra abajo.',
]
for s in samples:
    out = _strip_ocr_echo(s)
    leak = "<<<" in out or ">>>" in out or "OCR" in out or "a_ox" in out
    print(f"  IN : {s!r}", flush=True)
    print(f"  OUT: {out!r}  -> {'LEAK!' if leak else 'limpio'}", flush=True)
