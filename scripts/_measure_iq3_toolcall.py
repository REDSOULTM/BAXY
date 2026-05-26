"""Mide tool-calling de E4B-UD-IQ3_XXS a través del AGENTE completo (no bench
aislado — el prompt grande + 16 tools DEGRADA modelos chicos, lección 20/05).
Levanta un llama-server propio en 8092 con el modelo a probar (router mode, presets
text/vision como en prod) y apunta el agente ahí. Cuenta si el modelo EMITE el
tool-call esperado (tool_start), NO si la acción GUI tiene éxito (eso es otra cosa).

Compara IQ3_XXS contra el modelo dado por --baseline (default Q4_K_M).
Uso: python scripts/_measure_iq3_toolcall.py --model <gguf> [--port 8092]
"""
import os, sys, time, json, subprocess, urllib.request, argparse
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
E4B = ROOT / "models" / "E4B"
LLAMA = ROOT / "tools" / "llama-cuda" / "llama-server.exe"

ap = argparse.ArgumentParser()
ap.add_argument("--model", default=str(E4B/"gemma-4-E4B-it-UD-IQ3_XXS.gguf"))
ap.add_argument("--port", type=int, default=8092)
ap.add_argument("--label", default="IQ3_XXS")
args = ap.parse_args()
HOST = "127.0.0.1"

# Comandos de ACCIÓN (deben emitir tool-call). Variados, como el bench real.
CMDS = [
    "abre steam", "saca un screenshot", "sube el volumen", "mutea el sonido",
    "abre la calculadora", "pausa la musica", "minimiza la ventana",
    "que procesos consumen mas", "baja el volumen a 20", "abre el bloc de notas",
    "pon el volumen al maximo", "cierra esta ventana",
]

def health(port):
    try:
        urllib.request.urlopen(f"http://{HOST}:{port}/health", timeout=2); return True
    except Exception: return False

def start_server(model, port):
    # server simple text-only (sin mmproj) — el tool-calling es texto puro.
    cmd = [str(LLAMA),"-m",model,"-c","16384","-ngl","99","--flash-attn","on",
           "--swa-full","--jinja","--host",HOST,"--port",str(port),"--no-webui"]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(120):
        time.sleep(1)
        if health(port): return proc
        if proc.poll() is not None: return None
    return None

def main():
    print(f"levantando server {args.label}: {Path(args.model).name} en :{args.port}", flush=True)
    proc = start_server(args.model, args.port)
    if proc is None:
        print("ERROR: server no levantó"); return 1
    print("server OK, configurando agente", flush=True)
    os.environ["GEMMA4_AGENT_SERVER"] = f"http://{HOST}:{args.port}"
    os.environ["GEMMA4_ROUTER_MODE"] = "off"   # server simple, no router presets
    os.environ["GEMMA4_AGENT_MODEL"] = "default"  # el server simple expone 1 modelo
    os.environ.setdefault("GEMMA4_AGENT_CONTEXT", "16384")
    try:
        from gemma4_agent.agent import Gemma4Agent
        from gemma4_agent.config import AgentConfig
        ag = Gemma4Agent(AgentConfig.from_env())
        # NO ejecutar acciones reales (no tocar volumen/apps del user mientras usa la
        # PC): stubear tools.execute -> devuelve ok sin efecto. Medimos si el MODELO
        # EMITE el tool-call (tool_start), que es lo que define el tool-calling; la
        # ejecución real es ortogonal. Las tools de control (gui/audio/app/window/
        # media/system) se neutralizan; session/safety/state pasan (no tienen efecto).
        _real_exec = ag.tools.execute
        _NEUTRAL = {"audio","gui","app","window","media","system","game_launcher",
                    "whatsapp","uia","input","audio_device","browser","web"}
        def _safe_exec(name, a=None):
            if name in _NEUTRAL:
                return {"ok": True, "stubbed": True, "status": "done", "verified": True}
            return _real_exec(name, a)
        ag.tools.execute = _safe_exec
        ag.run_text("hola")  # warm
        ok = 0; rows = []
        for cmd in CMDS:
            seen = []
            def prog(s, i=None): seen.append(s)
            t = time.time()
            try:
                r = ag.run_text(cmd, progress=prog)
                reply = (r.content or "")
            except Exception as exc:
                reply = f"EXC {exc}"
            dt = time.time() - t
            called = any("tool_start" in s for s in seen)
            ok += called
            rows.append({"cmd": cmd, "tool_called": called, "lat": round(dt,1),
                         "reply": reply.encode("ascii","replace").decode()[:45]})
            print(f"  {'TOOL' if called else 'NONE'} | {cmd[:28]:28s} | {reply[:40]}", flush=True)
        print(f"\n>> {args.label} tool-calling: {ok}/{len(CMDS)} = {100*ok//len(CMDS)}%", flush=True)
        out = ROOT/"scripts"/"gui_eval"/f"_toolcall_{args.label}.json"
        out.write_text(json.dumps(rows,indent=2,ensure_ascii=False),encoding="utf-8")
        print("WROTE", out, flush=True)
    finally:
        proc.terminate()
        try: proc.wait(timeout=10)
        except Exception: proc.kill()
    return 0

if __name__ == "__main__": sys.exit(main())
