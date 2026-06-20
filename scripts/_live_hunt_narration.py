# -*- coding: utf-8 -*-
"""Caza amplia de la clase "narración pisada / no-answer en readouts". Para cada
query: tool(s), reply, nº de passes de LLM, y qué guard/nudge se disparó (spy de
trace.event). Marca filler (meta no-answer) y vuelca a JSON los casos malos con
sus passes+eventos para diagnóstico. QAT :8090 (no toca :8080).
"""
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gemma4_agent.infra.config import AgentConfig
from gemma4_agent.infra.llama_server import llama_command
from gemma4_agent.infra.profiles import PROFILES

QAT_PORT = "8090"
QAT_LOG = ROOT / "documentacion" / "_hunt_narration_qat.log"
OUT = ROOT / "documentacion" / "_hunt_narration_bad.json"


def health(port: str) -> bool:
    import urllib.request
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def boot_qat() -> subprocess.Popen:
    cmd = llama_command(AgentConfig(), PROFILES["vram4_lean"])
    cmd = [QAT_PORT if c == "8080" else c for c in cmd]
    QAT_LOG.parent.mkdir(exist_ok=True)
    logf = open(QAT_LOG, "w", encoding="utf-8", errors="replace")
    print(f"booteando QAT en :{QAT_PORT} ...")
    proc = subprocess.Popen(cmd, stdout=logf, stderr=subprocess.STDOUT)
    t0 = time.time()
    while time.time() - t0 < 90:
        if health(QAT_PORT):
            print(f"  QAT healthy en {time.time()-t0:.1f}s")
            return proc
        if proc.poll() is not None:
            raise RuntimeError(f"QAT murio; ver {QAT_LOG}")
        time.sleep(1.0)
    raise RuntimeError("QAT no healthy en 90s")


# Preguntas-READOUT puras (no piden acción física; la respuesta ES el dato).
QUERIES = [
    # window (NO está en mi exclusión -> sospechoso)
    "qué ventanas tengo abiertas",
    "what windows do i have open",
    # audio / volumen
    "qué volumen tengo puesto",
    "what volume am i at",
    # media now_playing
    "qué se está reproduciendo",
    "what's playing right now",
    # app (apps instaladas)
    "qué navegadores tengo instalados",
    # system battery / brightness (en mi exclusión -> deberían estar limpios)
    "cuánta batería tengo",
    "qué brillo tengo",
    "how much battery do i have",
    # device_settings wifi/bluetooth (en exclusión)
    "a qué wifi estoy conectado",
    "qué redes wifi hay cerca",
    # network (en exclusión)
    "tengo internet",
    # regresión (ya limpios)
    "cuántos procesos hay corriendo",
    "cuántos monitores tengo",
    "qué hora es",
]

FILLER = re.compile(
    r"\blisto, lo dejo\b|no se ha (proporcionado|especificado)|ninguna (tarea|solicitud)|"
    r"no hay una acci[oó]n|qu[eé] paso debo|next step|i (will|understand)|ready for|"
    r"lista para recibir|i need a question|how can i help|i am ready|system note|"
    r"no tengo (la|esa) (funci|informaci)|procesado las.*instruccion|instrucciones para el uso|"
    r"no necesito que revises|entendido[.,]?\s+(he|no|ya)|he procesado|"
    r"no hay (una )?acci[oó]n (inmediata|solicitada|espec)", re.I)
GUARD_EVENTS = {
    "a11y_continue_nudge", "forced_tool_retry", "forced_tool_retry_empty",
    "validator_rejected", "chaining_nudge_injected", "research_fallback_ack_reprompt",
    "unverified_intermediate_warning", "error_recovery_hint", "empty_reply",
    "leaked_call", "loop_detected", "pending_question_set"}


def main() -> int:
    qat = boot_qat()
    os.environ["GEMMA4_AGENT_SERVER"] = f"http://127.0.0.1:{QAT_PORT}"
    os.environ["GEMMA4_FG_ROUTER"] = "1"
    os.environ["GEMMA4_ENCODER_ONNX"] = "1"
    os.environ["GEMMA4_LEAN_TOOLS"] = "0"
    os.environ["GEMMA4_FG_AUTOBOOT"] = "1"
    os.environ["GEMMA4_FG_SERVER"] = "http://127.0.0.1:8082/v1/chat/completions"
    os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4_lean")

    try:
        from gemma4_agent.infra.llm_client import LLMClient
        n_chat = {"n": 0}
        _orig = LLMClient.chat

        def _spy(self, messages, *a, **k):
            n_chat["n"] += 1
            return _orig(self, messages, *a, **k)
        LLMClient.chat = _spy

        from gemma4_agent.agent_core.agent import Gemma4Agent
        a = Gemma4Agent()
        guards: list = []
        if getattr(a, "trace", None) is not None:
            _orig_te = a.trace.event

            def _te_spy(turn_id, kind, **kw):
                if kind in GUARD_EVENTS:
                    guards.append(kind)
                return _orig_te(turn_id, kind, **kw)
            a.trace.event = _te_spy

        def run(msg, reps=1):
            out = []
            for _ in range(reps):
                n_chat["n"] = 0
                guards.clear()
                a.clear()
                r = a.run_content(msg)
                rep = (getattr(r, "content", None) or str(r)).replace("\n", " ")
                te = getattr(r, "tool_events", None) or []
                tools = [getattr(x, "name", None) for x in te]
                out.append({"reply": rep, "tools": tools, "passes": n_chat["n"],
                            "guards": list(guards), "filler": bool(FILLER.search(rep))})
            return out

        print("\n========== CAZA readout (3x c/u) ==========")
        bad = []
        nbad = ntot = 0
        for q in QUERIES:
            for res in run(q, reps=3):
                ntot += 1
                mark = "FILLER" if res["filler"] else "ok"
                nbad += res["filler"]
                g = ",".join(res["guards"]) or "-"
                print(f"  [{mark:6}] {q!r} | tools={res['tools']} passes={res['passes']} guards={g}")
                print(f"           -> {res['reply'][:120]!r}")
                if res["filler"]:
                    bad.append({"query": q, **res})

        print("\n========================= RESUMEN =========================")
        print(f"  filler/no-answer: {nbad}/{ntot}  (objetivo 0)")
        # ¿algún readout disparó a11y_continue_nudge u otro guard re-prompt?
        nudged = [b for b in bad if "a11y_continue_nudge" in b["guards"]]
        print(f"  de esos, con a11y_continue_nudge: {len(nudged)}")
        if bad:
            OUT.write_text(json.dumps(bad, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  -> casos malos en {OUT}")
    finally:
        print("\nmatando QAT :8090 ...")
        qat.terminate()
        try:
            qat.wait(timeout=10)
        except subprocess.TimeoutExpired:
            qat.kill()
    return 0


if __name__ == "__main__":
    sys.exit(main())
