"""Per-profile smoke test (latencia + calidad) — sprint de latencia 2026-05-22.

Para CADA modelo distinto del lineup de perfiles (E2B-Q4=vram3, E4B-Q4=vram4/6/8,
E4B-Q6=vram12/16) levanta el server UNO A LA VEZ (sin contención de GPU — la
contención de 3-en-paralelo fue lo que dio el artefacto de 17s) y corre un
mini-corpus mixto con los PARÁMETROS REALES del modo (thinking flag + max_tokens
+ hint que produce choose_mode). Verifica gates de latencia y calidad por tipo.

Por qué API directa y no el agente completo: el agent-loop con monkeypatch de
resolve_turn_model fue la fuente del artefacto 17s. La API directa con los mismos
params del modo aísla latencia+calidad del modelo, que es lo que varía por perfil.
El loop completo (dispatch, summary, guards) ya está validado contra el server
real del usuario (1.65-4.09s, en el reporte).

NO corre en la suite normal (necesita GPU + modelos). Uso:
  PYTHONPATH=. python bench/_profile_smoke.py
Server del usuario en :8080 NO se toca; los temporales se cierran al final.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
import unicodedata
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXE = r"C:\llamacpp-cuda\bin\llama-server.exe"

# Los 3 modelos distintos del lineup (perfiles que los usan).
MODELS = [
    ("vram3", "E2B-Q4", ROOT / "models/E2B/gemma-4-E2B-it-Q4_K_M.gguf"),
    ("vram4/6/8", "E4B-Q4", ROOT / "models/E4B/gemma-4-E4B-it-Q4_K_M.gguf"),
    ("vram12/16", "E4B-Q6", ROOT / "models/E4B/gemma-4-E4B-it-Q6_K.gguf"),
]
PORT = 8097  # spare; one server at a time

# Los hints REALES de modes.py (copiados textualmente para fidelidad).
_INFO = ("Mode: fast_info. You are a VOICE assistant. Answer the question DIRECTLY "
         "in 1-3 short sentences of plain prose. NO markdown, NO bullets, NO **bold**, "
         "NO headers, NO numbered lists, NO emojis. If the user asks for a concrete "
         "fact, give it FIRST in one sentence.")
_FAST = ("Mode: fast_action. Eres un asistente de voz. Responde SIEMPRE en español, "
         "en 1-2 frases MÁX, texto plano. NO markdown, NO listas, NO emojis. "
         "(El system prompt real del agente fija el idioma; acá lo replicamos para "
         "que el smoke no marque falso-positivo de idioma con un hint corto.)")
_ACTION_HINT = ("Eres un asistente de voz. Si una tool aplica, LLAMALA; luego confirma "
                "en 1 frase corta ('Listo, ...').")
_TOOLS = [
    {"type": "function", "function": {"name": "app", "description": "Abre/cierra apps",
     "parameters": {"type": "object", "properties": {"action": {"type": "string"},
        "name": {"type": "string"}}, "required": ["action", "name"]}}},
    {"type": "function", "function": {"name": "window", "description": "Minimiza/cierra ventanas",
     "parameters": {"type": "object", "properties": {"action": {"type": "string"}},
        "required": ["action"]}}},
]

# (id, tipo, prompt, hint, thinking, max_tokens, tools?, expected_keywords, budget_s)
CORPUS = [
    ("st", "smalltalk", "hola", _FAST, False, 128, False, None, 3.0),
    ("fs1", "factual", "cual es la capital de Francia", _INFO, False, 320, False, ["paris"], 3.0),
    ("fs2", "factual", "cuando salio GTA 5", _INFO, False, 320, False, ["2013"], 3.0),
    ("cx1", "info", "explica que es la fotosintesis", _INFO, False, 320, False, ["plant", "luz", "energia"], 4.0),
    ("cx2", "info", "cual es la diferencia entre RAM y disco", _INFO, False, 320, False, ["ram", "memoria"], 4.0),
    ("ac1", "accion", "abre la calculadora", _ACTION_HINT, True, 512, True, None, 4.0),
    ("ac2", "accion", "minimiza la ventana", _ACTION_HINT, True, 512, True, None, 4.0),
]


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", (s or "").casefold())
    return "".join(c for c in s if not unicodedata.combining(c))


def _wait_health(port, timeout=40):
    for _ in range(timeout):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as r:
                if b'"ok"' in r.read():
                    return True
        except Exception:
            pass
        time.sleep(1)
    return False


def _call(port, model, prompt, hint, thinking, max_tokens, with_tools, budget_tokens=256):
    body = {
        "model": model, "max_tokens": max_tokens, "temperature": 0.0, "stream": False,
        "messages": [{"role": "system", "content": hint}, {"role": "user", "content": prompt}],
        "chat_template_kwargs": {"enable_thinking": thinking},
    }
    if thinking:
        body["chat_template_kwargs"]["thinking_budget"] = budget_tokens
    if with_tools:
        body["tools"] = _TOOLS
        body["tool_choice"] = "auto"
    req = urllib.request.Request(f"http://127.0.0.1:{port}/v1/chat/completions",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=60) as r:
        j = json.load(r)
    dt = time.time() - t0
    m = j["choices"][0]["message"]
    return dt, (m.get("content") or ""), len(m.get("tool_calls") or []), j["choices"][0]["finish_reason"]


def run_model(label, model_name, model_path):
    if not model_path.is_file():
        print(f"  SKIP {label}: model not found ({model_path.name})")
        return None
    proc = subprocess.Popen(
        [EXE, "-m", str(model_path), "--host", "127.0.0.1", "--port", str(PORT),
         "-ngl", "99", "-c", "8192", "--jinja", "--no-webui", "--swa-full",
         "--flash-attn", "on", "--alias", model_name],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        if not _wait_health(PORT):
            print(f"  FAIL {label}: server no levantó")
            return None
        # warm prefix cache
        _call(PORT, model_name, "hola", _FAST, False, 16, False)
        results = []
        for cid, typ, prompt, hint, think, mt, tools, exp, budget in CORPUS:
            samples = []
            last = ""
            tc = 0
            fr = ""
            for _ in range(3):
                dt, txt, ntc, finish = _call(PORT, model_name, prompt, hint, think, mt, tools)
                samples.append(dt)
                last, tc, fr = txt, ntc, finish
            import statistics
            med = statistics.median(samples)
            # quality
            if typ in ("factual", "info"):
                 q_ok = bool(last.strip()) and (exp is None or any(_fold(k) in _fold(last) for k in exp))
            elif typ == "accion":
                q_ok = (tc >= 1) or any(w in _fold(last) for w in ("listo", "abri", "minim"))
            else:
                q_ok = bool(last.strip())
            lat_ok = med < budget
            results.append((cid, typ, med, budget, lat_ok, q_ok, last, tc))
        return results
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
        time.sleep(2)  # release VRAM before next model


def main():
    print(f"=== Per-profile smoke (latencia + calidad), one model at a time on :{PORT} ===\n")
    all_pass = True
    for label, mname, mpath in MODELS:
        print(f"--- {label} ({mname}) ---")
        res = run_model(label, mname, mpath)
        if res is None:
            all_pass = False
            continue
        for cid, typ, med, budget, lat_ok, q_ok, txt, tc in res:
            flag = "OK  " if (lat_ok and q_ok) else ("LAT!" if not lat_ok else "QUAL")
            if not (lat_ok and q_ok):
                all_pass = False
            safe = txt.encode("ascii", "replace").decode()[:38]
            print(f"  [{flag}] {cid:4s} {typ:9s} {med:5.2f}s (<{budget:.0f}) tc={tc} | {safe!r}")
        print()
    print("=== VEREDICTO:", "TODOS LOS PERFILES OK ✅" if all_pass else "HAY GATES EN ROJO ❌", "===")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
