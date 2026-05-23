"""Latency + structure harness for the latency sprint (eje: LATENCIA).

Runs each corpus prompt through Gemma4Agent.run_content against the REAL server,
measuring: wall-clock to COMPLETE reply, number of LLM calls, reasoning vs content
tokens (summed), and the mode chosen. Each prompt 3x, reports the MEDIAN.

SAFETY: tool DISPATCH is mocked to a no-op success so action prompts ("abre
Chrome") never touch the system — we measure the LLM/loop latency, not the side
effect. The model still emits the tool-call (so the loop structure is real); only
ToolRegistry.execute is stubbed. Uses a tmp memory/state so the user's data is
untouched.

Usage:
  PYTHONPATH=. python bench/_latency_harness.py            # full corpus
  PYTHONPATH=. python bench/_latency_harness.py st1 fs1    # specific ids
"""
from __future__ import annotations

import dataclasses
import json
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gemma4_agent.config import AgentConfig
from gemma4_agent.agent import Gemma4Agent
from gemma4_agent import llm_client


def _load_corpus(only_ids):
    rows = []
    with open(ROOT / "bench" / "latency_corpus.jsonl", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if only_ids and r["id"] not in only_ids:
                continue
            rows.append(r)
    return rows


def _make_agent():
    tmp = Path(tempfile.mkdtemp(prefix="gemma4_lat_"))
    cfg = dataclasses.replace(
        AgentConfig.from_env(),
        memory_path=tmp / "m.json", captures_dir=tmp / "cap",
        trace_path=tmp / "t.jsonl", state_path=tmp / "s.json",
        enable_tracing=False,
    )
    agent = Gemma4Agent(cfg)
    # SAFETY: stub tool dispatch so action prompts never touch the system.
    def _noop_execute(name, args=None):
        return {"ok": True, "status": "ok", "verified": True,
                "summary": f"(harness no-op) {name}", "tool": name}
    agent.tools.execute = _noop_execute
    agent.tools.execute_routine_step = lambda name, args=None, **k: _noop_execute(name, args)
    return agent


def _run_one(agent, prompt):
    """Returns (wall_s, n_calls, reasoning_chars, content_chars, mode_name, reply)."""
    calls = {"n": 0, "rc": 0, "cc": 0}
    orig = llm_client.LLMClient.chat

    def traced(self, messages, **kw):
        r = orig(self, messages, **kw)
        calls["n"] += 1
        try:
            m = (r or {}).get("choices", [{}])[0].get("message", {})
            calls["rc"] += len(m.get("reasoning_content") or "")
            calls["cc"] += len(m.get("content") or "")
        except Exception:
            pass
        return r

    llm_client.LLMClient.chat = traced
    try:
        t0 = time.time()
        reply = agent.run_content(prompt)
        wall = time.time() - t0
    finally:
        llm_client.LLMClient.chat = orig
    txt = reply.content if hasattr(reply, "content") else str(reply)
    return wall, calls["n"], calls["rc"], calls["cc"], txt


def main(argv):
    only = set(argv) if argv else None
    corpus = _load_corpus(only)
    agent = _make_agent()
    # Warm: pay router/encoder load + prefix cache once.
    agent.run_content("hola")

    results = []
    for row in corpus:
        samples = []
        last_reply = ""
        ncalls = rc = cc = 0
        for _ in range(3):
            wall, n, rcc, ccc, reply = _run_one(agent, row["prompt"])
            samples.append(wall)
            last_reply = reply
            ncalls, rc, cc = n, rcc, ccc
        med = statistics.median(samples)
        results.append({
            "id": row["id"], "type": row["type"], "prompt": row["prompt"],
            "median_s": round(med, 2), "samples": [round(s, 2) for s in samples],
            "n_calls": ncalls, "reasoning_chars": rc, "content_chars": cc,
            "reply": last_reply,
        })
        flag = "OK " if med < 5.0 else "SLOW"
        safe = last_reply.encode("ascii", "replace").decode()[:55]
        print(f"[{flag}] {row['id']:5s} {row['type']:18s} med={med:5.2f}s "
              f"calls={ncalls} reason={rc:4d} | {safe!r}", flush=True)

    # Dump JSON for the quality eval + report.
    out = ROOT / "bench" / "latency_results.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    slow = [r for r in results if r["median_s"] >= 5.0]
    print(f"\n=== {len(results)} prompts, {len(slow)} SLOW (>=5s): "
          f"{[r['id'] for r in slow]} ===")
    print(f"median over corpus: {statistics.median([r['median_s'] for r in results]):.2f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
