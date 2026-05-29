"""PRUEBA DE ESCUCHA de B3a (streaming TTS) — la corrés VOS y juzgás el SONIDO.

Por cada pregunta oís la MISMA respuesta hablada de DOS formas, para comparar:
  [1] SIN streaming  -> el agente genera TODA la respuesta y RECIÉN AHÍ la voz
                        arranca a hablar (hay una pausa de generación al inicio,
                        después habla corrido y parejo).
  [2] CON streaming  -> la voz arranca a decir la PRIMERA oración mientras el
                        agente todavía genera el resto (empieza a oírse antes,
                        pero puede haber pausas entre oración y oración).

Vos escuchás y juzgás:
  - ¿El streaming (forma 2) suena NATURAL, o se nota cortado/robótico en el
    corte entre una oración y la siguiente?
  - ¿Realmente empieza a hablar ANTES que la forma 1 (se gana latencia)?
  - ¿Cuál preferís?

SEGURO: usa el TTS real (Piper) -> SOLO reproduce AUDIO (salida) por los
parlantes; NUNCA input sintético (no toca teclado/mouse, no cierra VS Code).
Las tools del agente están MOCKEADAS: no se ejecuta NINGUNA acción real (sin
red, sin tocar el SO). Solo corre el LLM real para generar la prosa que se habla.

Uso:  python scripts/_listen_b3a_streaming.py
      python scripts/_listen_b3a_streaming.py "tu propia pregunta acá"
"""
import ctypes
import os
import sys
import time
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")
os.environ["GEMMA4_ACCESSIBILITY_MODE"] = "normal"
os.environ["GEMMA4_VOICE_FILLER"] = "0"   # sin filler, para no confundirlo con el streaming

# --- Auto-corrección de intérprete (regla #5: el script garantiza sus precondiciones) ---
# El runtime del agente es Python 3.10 (con piper-tts). Si VS Code / el usuario lo lanzó
# con el venv equivocado (típicamente .venv_livekit 3.11, el de TRAINING, SIN piper), nos
# re-lanzamos solos con un python que SÍ tenga piper, en vez de fallar al cargar el TTS.
import importlib.util as _ilu
if _ilu.find_spec("piper") is None:
    import shutil as _sh
    import subprocess as _sp
    _this = str(Path(__file__).resolve())
    _cands = []
    _pyl = _sh.which("py")
    if _pyl:
        _cands.append([_pyl, "-3.10"])   # py launcher (universal en Windows)
    for _p in (os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python310\python.exe"),
               r"C:\Python310\python.exe"):
        if os.path.isfile(_p):
            _cands.append([_p])
    for _c in _cands:
        try:
            # probamos ANTES de lanzar: ¿este intérprete tiene piper?
            if _sp.run(_c + ["-c", "import piper"], capture_output=True, timeout=30).returncode == 0:
                print(f"[auto] este python no tiene piper-tts; re-lanzando con: {' '.join(_c)}", flush=True)
                sys.exit(_sp.run(_c + [_this] + sys.argv[1:]).returncode)
        except Exception:
            continue
    print("[ERROR] No encontré un python con piper-tts instalado. Corré con el runtime 3.10, "
          r"p.ej.:  py -3.10 scripts\_listen_b3a_streaming.py", flush=True)
    sys.exit(1)

# Red de seguridad: neutralizar input físico (no toca teclado/mouse). Igual que el
# script del earcon — doble seguro además del mock de tools.
try:
    _orig_windll = ctypes.WinDLL
    _BLOCKED = {"SendInput", "keybd_event", "mouse_event", "BlockInput", "SetCursorPos"}

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
print(f"[boot] perfil={prof.name}; arrancando llama-server (puede tardar ~10-60s)...", flush=True)
_t = time.time()
st = mgr.start(prof, wait_health=True, timeout_s=120)
print(f"[boot] status={st!r} en {time.time()-_t:.1f}s", flush=True)

# ---- TTS real (Piper) — vas a OÍR la voz por los parlantes ----
from gemma4_agent.voice.tts import StreamingTTS

tts = StreamingTTS()
if not tts.load():
    print(f"[ERROR] no pude cargar el TTS Piper: {tts.last_error}", flush=True)
    sys.exit(1)
tts.start()
print(f"[boot] TTS Piper cargado (voz={tts.voice}). Subí el volumen: vas a OÍR la voz.", flush=True)

from gemma4_agent.agent_core.agent import Gemma4Agent

agent = Gemma4Agent()
reg = agent.tools
# Mock de TODAS las tools: ninguna acción real se ejecuta (seguro).
for _name in list(reg._impls.keys()):
    reg._impls[_name] = (lambda n: (lambda args: {"ok": True, "tool": n, "mocked": True,
                                                   "verified": True, "action": (args or {}).get("action")}))(_name)


class TeeSink:
    """Reproduce por el TTS real Y registra cuándo llegó la 1a oración (mide el adelanto)."""

    def __init__(self, real):
        self._real = real
        self.first_t = None
        self._t0 = None

    def arm(self):
        self.first_t = None
        self._t0 = time.monotonic()

    def __call__(self, text):
        if self.first_t is None and (text or "").strip():
            self.first_t = time.monotonic() - (self._t0 or time.monotonic())
        return self._real(text)


sink = TeeSink(tts.feed_text)


def _wait_quiet(max_s=30.0):
    """Espera a que el TTS termine de hablar antes del próximo turno (no solapar)."""
    t = time.monotonic()
    while tts.is_busy() and time.monotonic() - t < max_s:
        time.sleep(0.1)


def run(prompt, stream_on):
    if stream_on:
        os.environ["GEMMA4_STREAM_TTS"] = "1"
    else:
        os.environ.pop("GEMMA4_STREAM_TTS", None)
    sink.arm()
    t0 = time.monotonic()
    try:
        reply = agent.run_content(prompt, tts_sink=sink)
    except Exception as e:  # noqa: BLE001
        print(f"            <EXC {type(e).__name__}: {e}>", flush=True)
        return
    dt = time.monotonic() - t0
    streamed = bool(getattr(reply, "tts_streamed", False))
    content = (getattr(reply, "content", "") or "").replace("\n", " ")
    used = [getattr(e, "name", "?") for e in (getattr(reply, "tool_events", []) or [])]
    if not streamed:
        # No se streameó durante la generación -> hablar la respuesta completa AHORA,
        # igual que hace el runner real (feed full reply + flush).
        sink._real(content)
    tts.flush()
    if stream_on:
        if streamed and sink.first_t is not None:
            print(f"            CON streaming: empezó a HABLAR a los {sink.first_t:.1f}s | "
                  f"generó todo en {dt:.1f}s | adelanto ~{max(0.0, dt - sink.first_t):.1f}s "
                  f"| tools={used}", flush=True)
        else:
            why = f"ruteó a tool {used}" if used else "respuesta vacía/abortada"
            print(f"            (flag ON pero NO streameó: {why} -> habló completo en {dt:.1f}s)", flush=True)
    else:
        print(f"            SIN streaming: generó en {dt:.1f}s y RECIÉN AHÍ habló | tools={used}", flush=True)
    print(f"            dijo: {content[:120]!r}", flush=True)
    _wait_quiet()


# ---- preguntas de CONOCIMIENTO (el 4B responde HABLANDO, sin tool) ----
ARGS = [a for a in sys.argv[1:] if a.strip()]
PROMPTS = ARGS or [
    "Explicá en pocas palabras qué es la fotosíntesis.",
    "Explicá brevemente por qué el cielo se ve azul.",
    "¿Qué diferencia hay entre un meteorito y un cometa?",
]

# Warm-up: la 1a request post-boot es fría (~30s) y el 4B mis-rutea en frío.
# Descartada y MUTEADA (sin audio) para no contaminar la prueba.
print("[warm] calentando el modelo (turno descartado, sin audio)...", flush=True)
tts.set_muted(True)
try:
    run("Explicá brevemente qué es el agua.", stream_on=False)
except Exception:
    pass
tts.set_muted(False)

print("\n" + "=" * 76, flush=True)
print("PRUEBA DE ESCUCHA B3a — por cada pregunta oís la MISMA respuesta 2 veces:", flush=True)
print("  [1] SIN streaming  -> pausa de generación, DESPUÉS habla corrido.", flush=True)
print("  [2] CON streaming  -> empieza a hablar ANTES, oración por oración.", flush=True)
print("Juzgá: ¿el streaming suena natural (no cortado)? ¿se gana tiempo? ¿cuál preferís?", flush=True)
print("=" * 76, flush=True)

for i, p in enumerate(PROMPTS, 1):
    print(f"\n[{i}/{len(PROMPTS)}] PREGUNTA: {p!r}", flush=True)
    print("   [1] 🔇 SIN streaming  (escuchá: pausa, y después habla)...", flush=True)
    run(p, stream_on=False)
    time.sleep(1.2)
    print("   [2] 🔊 CON streaming  (escuchá: empieza antes, oración por oración)...", flush=True)
    run(p, stream_on=True)
    time.sleep(1.5)

print("\n" + "=" * 76, flush=True)
print("FIN. Decime: ¿el streaming (forma 2) sonó NATURAL o CORTADO? ¿se notó más rápido?", flush=True)
print("     Si te gustó -> lo flipeo a default-ON. Si sonó cortado -> lo dejo opt-in.", flush=True)
print("=" * 76, flush=True)
tts.stop()
