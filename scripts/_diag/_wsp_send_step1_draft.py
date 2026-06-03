"""ENVÍO REAL a WhatsApp — PASO 1: DRAFT (auto_send=False, NO envía). Abre el chat
'Letras', escribe el mensaje de prueba pero NO lo manda. Guarda screenshot para LEER
y confirmar que es el GRUPO Letras antes de enviar (paso 2). Autorizado por el user:
envíos reales SOLO a Letras/Música."""
from __future__ import annotations
import os, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")
from gemma4_agent.infra.profiles import get_active_profile, apply_profile_to_env
from gemma4_agent.infra.llama_server import get_shared_manager
prof = get_active_profile(); apply_profile_to_env(prof)
get_shared_manager().start(prof, wait_health=True, timeout_s=120); print("[boot] OK", flush=True)
from PIL import ImageGrab
from gemma4_agent.agent_core.agent import Gemma4Agent

OUT = Path("scripts/_diag/_wsp"); OUT.mkdir(parents=True, exist_ok=True)
GROUP = "Letras"
MSG = "Prueba automatica de Gemma 4 (asistente de voz). Ignoren este mensaje, gracias."

a = Gemma4Agent()
a.tools._current_user_text = f"mandale a {GROUP} {MSG}"
print(f"[draft] contact={GROUP!r} auto_send=False", flush=True)
res = a.tools.execute("whatsapp", {"action": "send_message", "contact": GROUP,
                                   "text": MSG, "auto_send": False})
time.sleep(1.2)
ImageGrab.grab().convert("RGB").save(str((OUT / "step1_draft.png").resolve()))
print(f"[result] ok={res.get('ok')} status={res.get('status')} "
      f"sent={res.get('sent')} chat_opened={res.get('chat_opened')} "
      f"abort={res.get('abort_reason')}", flush=True)
print(f"[screenshot] scripts/_diag/_wsp/step1_draft.png (LEER: ¿es el grupo {GROUP}? ¿msg en la caja?)", flush=True)
print("[done-step1] NO se envió nada todavía.", flush=True)
