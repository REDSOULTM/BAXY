"""Valida el TOOL integrado (con los fixes): whatsapp_tool auto_send=False a 'Música'.
Debe: buscar el grupo por el buscador principal -> abrirlo -> verificar el encabezado
'Música' por región -> redactar (NO enviar). Screenshot para LEER antes de enviar."""
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
GROUP = "Música"
MSG = "Prueba de Gemma 4 (asistente de voz): el envio a grupos ya funciona. Ignoren, gracias."
a = Gemma4Agent()
a.tools._current_user_text = f"mandale a {GROUP} {MSG}"
res = a.tools.execute("whatsapp", {"action": "send_message", "contact": GROUP,
                                   "text": MSG, "auto_send": False})
time.sleep(1.2)
ImageGrab.grab().convert("RGB").save(str((OUT / "tool_musica_draft.png").resolve()))
info = res.get("gui_search_info", {}) if isinstance(res, dict) else {}
print(f"[result] ok={res.get('ok')} sent={res.get('sent')} chat_opened={res.get('chat_opened')}", flush=True)
print(f"[result] status={res.get('status')} abort={info.get('abort_reason')}", flush=True)
print(f"[steps] {info.get('steps')}", flush=True)
print("[screenshot] tool_musica_draft.png — LEER: ¿grupo Música? ¿msg redactado? NADA enviado.", flush=True)
