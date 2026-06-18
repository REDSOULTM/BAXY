# -*- coding: utf-8 -*-
"""Valida el completado de args incompletos de FG por el LLM de habla (QAT):
  1) _missing_value_field detecta el campo faltante desde el slim-schema (sin server).
  2) _fg_complete_arg (QAT) recupera el valor del texto del usuario, o devuelve None si no lo dijo.
  3) end-to-end: "abre" (ambiguo) -> no completa -> el tool pide aclaración (honesto, no inventa).
Boota QAT :8090 (no toca el Baxy en :8080) + FG autoboot :8082. Se mata solo."""
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ["GEMMA4_FG_ROUTER"] = "1"
os.environ["GEMMA4_ENCODER_ONNX"] = "1"
os.environ["GEMMA4_LEAN_TOOLS"] = "0"
os.environ["GEMMA4_FG_AUTOBOOT"] = "1"
os.environ["GEMMA4_AGENT_SERVER"] = "http://127.0.0.1:8090"
os.environ["GEMMA4_FG_SERVER"] = "http://127.0.0.1:8082/v1/chat/completions"
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4_lean")
os.environ.setdefault("GEMMA4_DIAG", "1")

from gemma4_agent.infra.config import AgentConfig
from gemma4_agent.infra.llama_server import llama_command
from gemma4_agent.infra.profiles import PROFILES


def health(port):
    import urllib.request
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def boot_qat():
    cmd = [("8090" if c == "8080" else c) for c in llama_command(AgentConfig(), PROFILES["vram4_lean"])]
    logf = open(ROOT / "documentacion" / "_fg_argcomplete.log", "w", encoding="utf-8", errors="replace")
    p = subprocess.Popen(cmd, stdout=logf, stderr=subprocess.STDOUT)
    t0 = time.time()
    while time.time() - t0 < 90:
        if health("8090"):
            return p
        if p.poll() is not None:
            raise RuntimeError("QAT murió")
        time.sleep(1.0)
    raise RuntimeError("QAT no healthy")


def main():
    qat = boot_qat()
    print("QAT :8090 healthy")
    try:
        from gemma4_agent.routing import fg_router as fg
        fg.fg_emit("warmup")  # construye _R + boota FG

        print("\n=== (1) _missing_value_field (desde slim-schema, sin LLM) ===")
        for tool, args, exp in [
            ("app_open", {}, "name"), ("app_open", {"name": "Steam"}, None),
            ("set_volume", {}, "level"), ("system_time", {}, None),
            ("web_search", {}, "query"),
        ]:
            got = fg._missing_value_field(tool, args)
            ok = "OK " if got == exp else "FAIL"
            print(f"  [{ok}] {tool}{args} -> falta={got!r} (esperado {exp!r})")

        from gemma4_agent.agent_core.agent import Gemma4Agent
        a = Gemma4Agent()

        print("\n=== (2) _fg_complete_arg (QAT extrae del texto, o None si no lo dijo) ===")
        for text, tool, action, field, exp in [
            ("abre Steam", "app", "open", "name", "valor~Steam"),
            ("open Steam please", "app", "open", "name", "valor~Steam"),
            ("abre", "app", "open", "name", "None (ambiguo)"),
            ("abre este.", "app", "open", "name", "None (ambiguo)"),
            ("subí el volumen a 40", "audio", "set_volume", "level", "valor~40"),
            ("mandale a Ana por whatsapp", "whatsapp", "send_message", "text", "None (no dijo texto)"),
        ]:
            val = a._fg_complete_arg(text, tool, action, field)
            print(f"  {text!r:35s} -> {field}={val!r}   (esperado: {exp})")

        print("\n=== (3) end-to-end: ambiguo NO inventa, pide aclaración ===")
        for msg in ["abre", "abre Steam"]:
            a.clear()
            r = a.run_content(msg)
            rep = (getattr(r, "content", None) or "").replace("\n", " ")
            te = getattr(r, "tool_events", None) or []
            ev = [(getattr(x, "name", None), getattr(x, "args", None)) for x in te]
            print(f"  {msg!r} -> tools={ev} | {rep[:90]!r}")
    finally:
        print("\nmatando QAT :8090 (FG lo mata el atexit) ...")
        qat.terminate()
        try:
            qat.wait(timeout=10)
        except subprocess.TimeoutExpired:
            qat.kill()
        print("listo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
