"""Tool2Vec synthetic query generation (Step 4 of the 2026-05-21 router rebuild).

All four research reports converged on the single most-replicated win in tool
retrieval: represent each tool by the MEAN EMBEDDING OF EXAMPLE USER QUERIES
that invoke it, not by its abstract description (Tool2Vec arXiv:2409.02141:
"+27.28 Recall@K on ToolBench"; Re-Invoke arXiv:2408.01875). Short voice
queries ("subelo", "qué notas tengo") share almost no surface form with a
terse English tool description, so cosine-to-description is weak — but cosine
to a cloud of real phrasings is strong.

This script generates ~N multilingual, voice-style example queries per tool
using the LOCAL Gemma-4 server that is ALREADY RUNNING (no new GPU job, no
disturbance to the user's session). Output is a versioned JSONL the centroid
builder consumes. Reproducible: fixed prompt skeleton + temperature, resumable
(skips tools already generated), and the generator model id is recorded.

Universality (project law): every tool gets queries across es/en/pt/fr/de/it
with voice-transcription noise, so the centroids don't overfit to Spanish.

Run:
    python scripts/router_tool2vec_generate.py            # resume/continue
    python scripts/router_tool2vec_generate.py --per-tool 30
    python scripts/router_tool2vec_generate.py --tool media   # one tool
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUT = ROOT / "gemma4_agent" / "data" / "tool2vec_queries.jsonl"
LANGS = ("es", "en", "pt", "fr", "de", "it")


def _server() -> tuple[str, str]:
    """Find the running llama-server's chat URL + model id. Probes the mgmt
    endpoint (8080) for the loaded model, then talks to its actual port."""
    import urllib.error
    # The model server port is dynamic; the loaded model is advertised at 8080.
    for base in ("http://127.0.0.1:10446", "http://127.0.0.1:8080"):
        try:
            r = urllib.request.urlopen(f"{base}/v1/models", timeout=3)
            data = json.load(r)
            loaded = [m for m in data.get("data", [])
                      if (m.get("status") or {}).get("value") == "loaded"]
            mid = (loaded[0]["id"] if loaded else data["data"][0]["id"])
            return base, mid
        except Exception:
            continue
    raise SystemExit("no running llama-server found on :10446 or :8080 — "
                     "start the agent (the server it launches is reused here)")


def _chat(base: str, model: str, prompt: str, *, temperature: float,
          max_tokens: int = 700) -> str:
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": temperature,
        "seed": 7,  # reproducibility
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{base}/v1/chat/completions", data=body,
        headers={"Content-Type": "application/json"})
    r = urllib.request.urlopen(req, timeout=180)
    d = json.load(r)
    return d["choices"][0]["message"]["content"]


_PROMPT = """You generate training data for a voice-assistant tool router.

Tool name: {name}
What it does: {desc}

Write {n} SHORT, realistic user utterances (3-10 words each) that a person
would say to a voice assistant to invoke THIS tool. Requirements:
- Spread evenly across these languages: Spanish, English, Portuguese, French,
  German, Italian. Roughly equal counts.
- Mix registers: imperative ("abre..."), question ("¿puedes...?"), elliptical,
  polite, and a few with realistic voice-transcription noise (missing accents,
  run-together words).
- Cover BOTH read and write/action phrasings if the tool supports both
  (e.g. "what notes do I have" AND "write down X").
- NO numbering, NO explanations, NO quotes. ONE utterance per line. Plain text.

Output {n} lines now:"""


def _parse_lines(raw: str) -> list[str]:
    out = []
    for ln in raw.splitlines():
        s = ln.strip().strip("-*0123456789.) \t").strip().strip('"').strip()
        # drop meta-lines the model sometimes emits
        if not s or len(s.split()) > 14:
            continue
        if s.lower().startswith(("here are", "tool name", "output", "sure",
                                 "claro", "voici", "ecco", "aqui estan")):
            continue
        out.append(s)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-tool", type=int, default=30)
    ap.add_argument("--tool", default="", help="only this tool (debug)")
    ap.add_argument("--temperature", type=float, default=0.8)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    from gemma4_agent.routing.semantic_router import TOOL_DESCRIPTIONS

    base, model = _server()
    print(f"server={base} model={model}")

    done: dict[str, int] = {}
    if OUT.exists() and not args.force:
        for ln in OUT.read_text(encoding="utf-8").splitlines():
            if ln.strip():
                t = json.loads(ln)["tool"]
                done[t] = done.get(t, 0) + 1

    tools = [args.tool] if args.tool else list(TOOL_DESCRIPTIONS.keys())
    mode = "w" if args.force else "a"
    with OUT.open(mode, encoding="utf-8") as f:
        for i, name in enumerate(tools):
            if not args.force and done.get(name, 0) >= args.per_tool:
                print(f"[{i+1}/{len(tools)}] {name}: have {done[name]}, skip")
                continue
            desc = TOOL_DESCRIPTIONS.get(name, name)
            prompt = _PROMPT.format(name=name, desc=desc, n=args.per_tool + 6)
            try:
                raw = _chat(base, model, prompt, temperature=args.temperature)
            except Exception as exc:
                print(f"[{i+1}/{len(tools)}] {name}: GEN FAILED {exc}")
                continue
            qs = _parse_lines(raw)[: args.per_tool]
            for q in qs:
                f.write(json.dumps({"tool": name, "q": q}, ensure_ascii=False) + "\n")
            f.flush()
            print(f"[{i+1}/{len(tools)}] {name}: wrote {len(qs)} queries")
    print(f"\ndone -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
