"""Post-game validation: prove every VRAM profile is correct on THIS GPU.

Run this when the GPU is FREE (no game). For each profile it:
  1. boots llama-server via the REAL production path (force_restart_for_profile),
  2. checks the model loaded 100% on GPU (no CPU_Mapped layer spill -> speed),
  3. fires a real prompt at ctx16K to confirm no exceed_context error,
  4. measures generation tok/s (must be fast enough for the latency budget),
  5. fires a tool-call to confirm action routing works,
  6. measures peak VRAM (text + vision child) and checks it fits with margin.

Prints a PASS/FAIL table. Does NOT modify profiles. Usage:
    python scripts/validate_profiles.py            # all profiles
    python scripts/validate_profiles.py vram12 vram16   # subset
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gemma4_agent.infra.config import AgentConfig          # noqa: E402
from gemma4_agent.infra.llama_server import (               # noqa: E402
    LlamaServerManager, _kill_server_on_port,
)
from gemma4_agent.infra.profiles import PROFILES            # noqa: E402

LOG = Path(__file__).resolve().parent.parent / "gemma4_agent" / "logs" / "llama-server.out.log"
GPU_TOTAL = 16380  # 4060 Ti; informational
WDDM_MARGIN = 800  # MB we want free under total for safety

TOOLS = [
    {"type": "function", "function": {
        "name": "open_app", "description": "Abre una aplicacion en la PC.",
        "parameters": {"type": "object", "properties": {
            "app": {"type": "string"}}, "required": ["app"]}}},
]


def gpu_used():
    out = subprocess.check_output(
        ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
        text=True)
    return int(out.strip().splitlines()[0])


def tail_log(n=400):
    try:
        data = LOG.read_bytes()[-200_000:]
        return data.decode("utf-8", errors="replace").splitlines()[-n:]
    except Exception:
        return []


def cpu_mapped_mb(lines):
    """Largest CPU_Mapped model buffer reported (MB). >~600 likely = layer spill
    (embeddings alone are ~400-500MB; layers spilling is the speed killer)."""
    vals = []
    for ln in lines:
        m = re.search(r"CPU_Mapped model buffer size\s*=\s*([\d.]+)\s*MiB", ln)
        if m:
            vals.append(float(m.group(1)))
    return max(vals) if vals else 0.0


def chat(model, content, max_tokens, thinking=False, tools=None, port=8080):
    body = {"model": model, "messages": [{"role": "user", "content": content}],
            "max_tokens": max_tokens, "temperature": 0,
            "chat_template_kwargs": {"enable_thinking": thinking}}
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=180) as r:
        out = json.load(r)
    return time.time() - t0, out


def validate(name, mgr):
    prof = PROFILES[name]
    print(f"\n{'='*60}\n{name}: {os.path.basename(prof.model_path or '(default)')} "
          f"ctx={prof.context_size} vision={prof.vision_enabled}\n{'='*60}")
    if not prof.server_running:
        print("  server_running=False (standby) -> skip")
        return (name, "SKIP", {})
    res = {"cpu_mapped": None, "gpu_text": None, "gpu_vision": None,
           "tok_s": None, "ctx_ok": None, "tool_ok": None, "hola_s": None}
    try:
        mgr.force_restart_for_profile(prof, wait_health=True, timeout_s=180)
    except Exception as e:
        print(f"  [FAIL] boot: {e}")
        return (name, "FAIL", res)
    text_model = f"{name}-text"
    # 1) 'hola' turn (fast_action: thinking off, 128 budget) -> forces load
    try:
        dt, out = chat(text_model, "Hola", 128, thinking=False)
        usage = out.get("usage", {})
        gen = usage.get("completion_tokens", 0)
        res["hola_s"] = round(dt, 1)
        res["tok_s"] = round(gen / dt, 1) if dt else 0
        print(f"  hola: {dt:.1f}s, {gen} tok, {res['tok_s']} tok/s "
              f"-> {out['choices'][0]['message'].get('content','')[:50]!r}")
    except Exception as e:
        print(f"  [FAIL] hola turn: {e}")
        return (name, "FAIL", res)
    time.sleep(3)
    res["gpu_text"] = gpu_used()
    lines = tail_log()
    res["cpu_mapped"] = round(cpu_mapped_mb(lines), 0)
    print(f"  gpu_text={res['gpu_text']}MB  CPU_Mapped={res['cpu_mapped']}MB")
    # 2) big prompt: confirm ctx16K accepts a realistic multi-tool-size prompt
    big = "Hola. " + ("Necesito que recuerdes este contexto largo. " * 600)
    try:
        dt, out = chat(text_model, big, 32, thinking=False)
        res["ctx_ok"] = True
        print(f"  big-prompt ({len(big)} chars): OK ({dt:.1f}s) — no exceed_context")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        res["ctx_ok"] = "exceed" not in body.lower()
        print(f"  big-prompt: HTTP {e.code} ctx_ok={res['ctx_ok']} ({body[:80]})")
    except Exception as e:
        print(f"  big-prompt: {e}")
    # 3) tool-call
    try:
        dt, out = chat(text_model, "abre steam", 256, thinking=True, tools=TOOLS)
        tcs = out["choices"][0]["message"].get("tool_calls") or []
        names = [t["function"]["name"] for t in tcs]
        res["tool_ok"] = "open_app" in names
        print(f"  tool-call 'abre steam' -> {names} ({dt:.1f}s) ok={res['tool_ok']}")
    except Exception as e:
        print(f"  tool-call: {e}")
    # 4) vision (if enabled) -> peak VRAM
    if prof.vision_enabled:
        img = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQ"
               "AAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAASsJTYQAAAAASUVORK5CYII=")
        try:
            chat(f"{name}-vision", [
                {"type": "text", "text": "color?"},
                {"type": "image_url", "image_url": {"url": img}}], 16, thinking=False)
            time.sleep(3)
            res["gpu_vision"] = gpu_used()
            print(f"  gpu_vision={res['gpu_vision']}MB "
                  f"(total {GPU_TOTAL}, want <{GPU_TOTAL-WDDM_MARGIN})")
        except Exception as e:
            print(f"  vision: {e}")
    # verdict
    ok = (res["ctx_ok"] and res["tool_ok"]
          and (res["cpu_mapped"] or 0) < 700           # 100% GPU (only embed CPU)
          and (res["gpu_vision"] or res["gpu_text"] or 0) < GPU_TOTAL - WDDM_MARGIN
          and (res["tok_s"] or 0) >= 25)               # latency-viable
    return (name, "PASS" if ok else "CHECK", res)


def main():
    names = sys.argv[1:] or ["vram3", "vram4", "vram6", "vram8", "vram12", "vram16"]
    mgr = LlamaServerManager(AgentConfig.from_env())
    rows = []
    try:
        for n in names:
            rows.append(validate(n, mgr))
    finally:
        _kill_server_on_port(8080)
        print("\n(stopped server)")
    print(f"\n{'='*72}\nSUMMARY\n{'='*72}")
    print(f"{'profile':<9}{'verdict':<8}{'tok/s':>6}{'cpuMap':>8}{'gpu_txt':>8}"
          f"{'gpu_vis':>8}{'ctx':>5}{'tool':>6}")
    for name, verdict, r in rows:
        print(f"{name:<9}{verdict:<8}{str(r.get('tok_s')):>6}"
              f"{str(r.get('cpu_mapped')):>8}{str(r.get('gpu_text')):>8}"
              f"{str(r.get('gpu_vision')):>8}{str(r.get('ctx_ok')):>5}"
              f"{str(r.get('tool_ok')):>6}")
    print("\nPASS = 100%GPU (cpuMap<700) + fits (<15580) + ctx16K ok + tool ok + tok/s>=25")


if __name__ == "__main__":
    main()
