"""Bench runner standalone — Gemma 4 puro vs 540 cases.

Uso:
    python run_bench.py --model E4B-Q4_K_M [--start 0] [--end 540]

Asume llama-server corriendo en :8080 con el modelo activo. Hace POST
/v1/chat/completions con tools=[60 stubs] y mide PASS/FAIL via auditor.

NO depende del repo Carter. NO importa nada de Carter. Standalone puro.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# UTF-8 stdout
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "buffer"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from tests import load_cases  # noqa: E402
from system_prompt import SYSTEM_PROMPT  # noqa: E402
from auditor import audit_case  # noqa: E402
from stubs import execute_tool  # noqa: E402

SERVER_URL = "http://127.0.0.1:8080/v1/chat/completions"
HEALTH_URL = "http://127.0.0.1:8080/health"
SCHEMAS_PATH = ROOT / "tool_schemas.json"

# Sampling oficial Gemma 4 (model card Google 2026-04-17)
SAMPLING = {
    "temperature": 1.0,
    "top_p": 0.95,
    "top_k": 64,
    "repeat_penalty": 1.0,
    "max_tokens": 1280,  # +500 para evitar finish_reason=length que produce empty replies
}

MAX_TURNS = 4  # one tool call + follow-up reply, max 4 cycles


def _server_alive(timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def _call_llm(messages: list[dict], tools: list[dict], timeout: float = 180.0) -> dict:
    body = {
        "model": "gemma-4",  # llama-server no chequea, usa el cargado
        "stream": False,
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto",
        **SAMPLING,
    }
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        SERVER_URL, data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _normalize_tool_calls(raw: list) -> list[dict]:
    out = []
    for tc in raw or []:
        fn = tc.get("function") or {}
        name = fn.get("name", "")
        args = fn.get("arguments", {})
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {"_raw": args}
        out.append({"name": name, "arguments": args, "id": tc.get("id", f"call_{name}")})
    return out


def run_one_case(case, schemas: list[dict]) -> dict:
    """Run un caso end-to-end. Devuelve dict con reply, tool_calls, latency_ms, status."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": case.prompt},
    ]
    all_tool_calls: list[dict] = []
    final_reply = ""
    t0 = time.monotonic()

    for turn_idx in range(MAX_TURNS):
        try:
            resp = _call_llm(messages, schemas)
        except Exception as exc:
            dt = int((time.monotonic() - t0) * 1000)
            return {
                "cid": case.cid, "category": case.category,
                "severity": case.severity, "prompt": case.prompt,
                "expected_tools": case.expected_tools,
                "reply": f"LLM_ERROR: {type(exc).__name__}: {exc}",
                "tools": [],
                "latency_ms": dt,
                "status": "FAIL",
                "reasons": [f"llm_error: {exc}"],
            }

        choice = resp.get("choices", [{}])[0]
        msg = choice.get("message", {}) or {}
        content = msg.get("content", "") or ""
        finish_reason = choice.get("finish_reason", "")
        tool_calls_raw = msg.get("tool_calls", []) or []
        tool_calls = _normalize_tool_calls(tool_calls_raw)

        if not tool_calls:
            # If empty content with finish_reason=length, the model ran out of tokens
            # mid-thinking. Retry with stricter "EMIT TEXT NOW" hint to force a reply.
            if not content.strip() and finish_reason == "length" and turn_idx < MAX_TURNS - 1:
                messages.append({
                    "role": "user",
                    "content": "Por favor respondé en una frase corta: si necesitás info, pedila; si no podés, decí 'no tengo herramienta para eso'. NO hagas thinking, respondé directo.",
                })
                continue
            final_reply = content
            break

        all_tool_calls.extend(tool_calls)
        # NOTE (post-research): llama.cpp b9090 includes PR #21418 (merged 2026-04-04)
        # that adds the specialized Gemma 4 parser + EOG token for <|tool_response>.
        # That parser already strips thinking artifacts from content when tool_calls
        # are present. So we PRESERVE content here -- stripping it (v13 attempt)
        # caused a -1.5pp regression vs v12, confirming the parser is doing its job.
        messages.append({
            "role": "assistant",
            "content": content,
            "tool_calls": [{
                "id": tc["id"], "type": "function",
                "function": {"name": tc["name"],
                             "arguments": json.dumps(tc["arguments"])},
            } for tc in tool_calls],
        })
        for tc in tool_calls:
            result = execute_tool(tc["name"], tc.get("arguments", {}))
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": json.dumps(result, ensure_ascii=False),
            })

        if turn_idx == MAX_TURNS - 1:
            final_reply = content or "(loop sin reply final)"
            break

    dt = int((time.monotonic() - t0) * 1000)

    audit = audit_case(case, final_reply, all_tool_calls, dt)
    return {
        "cid": case.cid, "category": case.category,
        "severity": case.severity, "prompt": case.prompt,
        "expected_tools": case.expected_tools,
        "reply": final_reply[:500],
        "tools": [tc["name"] for tc in all_tool_calls],
        "latency_ms": dt,
        "status": audit["status"],
        "reasons": audit["reasons"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="unknown",
                        help="Nombre del modelo (informativo, no afecta llama-server)")
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int, default=None)
    parser.add_argument("--per-cat", type=int, default=None,
                        help="Sampling balanceado: primeros N por categoria")
    parser.add_argument("--output", default=None)
    parser.add_argument("--dry-run", action="store_true",
                        help="No usar GPU/LLM. Mock minimo para testear harness.")
    args = parser.parse_args()

    # Dry-run: testea harness (loader, auditor, stubs) sin tocar GPU
    if args.dry_run:
        print("[runner] DRY-RUN mode: no LLM, no GPU. Mock responses.", flush=True)
        global _call_llm
        _call_llm = _mock_llm  # type: ignore
    elif not _server_alive():
        print(f"[runner] llama-server no responde en {HEALTH_URL}", file=sys.stderr)
        sys.exit(2)

    schemas = json.loads(SCHEMAS_PATH.read_text(encoding="utf-8"))
    print(f"[runner] {len(schemas)} tool schemas cargados", flush=True)

    cases = load_cases()
    if args.per_cat:
        bucket: dict[int, list] = {}
        for c in cases:
            bucket.setdefault(c.category, []).append(c)
        sampled = []
        for cat in sorted(bucket.keys()):
            sampled.extend(bucket[cat][:args.per_cat])
        cases = sampled
    if args.start or args.end is not None:
        cases = cases[args.start:args.end]
    print(f"[runner] cases a ejecutar: {len(cases)}", flush=True)

    output = Path(args.output) if args.output else (
        ROOT / "results" / f"{args.model}_run.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)

    # Warmup
    try:
        print("[runner] warmup...", flush=True)
        t0 = time.monotonic()
        _call_llm(
            [{"role": "system", "content": SYSTEM_PROMPT},
             {"role": "user", "content": "ping"}],
            schemas,
        )
        print(f"[runner] warmup: {int((time.monotonic()-t0)*1000)}ms", flush=True)
    except Exception as exc:
        print(f"[runner] warmup fallo: {exc}", flush=True)

    results: list[dict] = []
    by_cat: dict[int, dict[str, int]] = {}
    pass_count = partial_count = fail_count = 0

    for i, case in enumerate(cases, 1):
        cat_stats = by_cat.setdefault(case.category, {"pass": 0, "partial": 0, "fail": 0})
        print(f"\n[{i:03d}/{len(cases)}] {case.cid} [{case.severity}] > {case.prompt[:80]}",
              flush=True)
        try:
            r = run_one_case(case, schemas)
        except Exception as exc:
            print(f"   EXCEPTION: {type(exc).__name__}: {exc}", flush=True)
            r = {
                "cid": case.cid, "category": case.category,
                "severity": case.severity, "prompt": case.prompt,
                "status": "FAIL", "reasons": [f"exception: {exc}"],
                "latency_ms": -1, "tools": [], "reply": "",
            }

        results.append(r)
        st = r.get("status", "FAIL")
        icon = {"PASS": "OK", "PARTIAL": "~~", "FAIL": "XX"}.get(st, "??")
        reply_short = (r.get("reply") or "").replace("\n", " ")[:120]
        print(f"   {icon} [{st}] ({r.get('latency_ms')}ms) {reply_short}", flush=True)
        if r.get("tools"):
            print(f"   tools: {r['tools']}", flush=True)
        if r.get("reasons"):
            print(f"   reasons: {r['reasons']}", flush=True)

        if st == "PASS":
            pass_count += 1; cat_stats["pass"] += 1
        elif st == "PARTIAL":
            partial_count += 1; cat_stats["partial"] += 1
        else:
            fail_count += 1; cat_stats["fail"] += 1

        # Checkpoint cada 30 cases
        if i % 30 == 0:
            output.write_text(json.dumps({
                "summary": {
                    "completed": i, "total": len(cases),
                    "pass": pass_count, "partial": partial_count, "fail": fail_count,
                    "pass_rate": round(pass_count / i * 100, 2),
                    "model": args.model,
                    "by_category": by_cat,
                },
                "results": results,
            }, ensure_ascii=False, indent=2), encoding="utf-8")

    total = len(cases)
    summary = {
        "completed": total, "total": total,
        "pass": pass_count, "partial": partial_count, "fail": fail_count,
        "pass_rate": round(pass_count / total * 100, 2) if total else 0,
        "model": args.model,
        "by_category": by_cat,
    }
    output.write_text(json.dumps({"summary": summary, "results": results},
                                  ensure_ascii=False, indent=2),
                      encoding="utf-8")

    print("\n" + "=" * 70, flush=True)
    print(f"MODELO: {args.model}", flush=True)
    print(f"TOTAL: {total}  PASS: {pass_count}  PARTIAL: {partial_count}  FAIL: {fail_count}",
          flush=True)
    print(f"Pass rate: {summary['pass_rate']}%", flush=True)
    print("Por categoria:", flush=True)
    for cat in sorted(by_cat.keys()):
        s = by_cat[cat]
        tot = sum(s.values())
        rate = round(s["pass"] / tot * 100, 1) if tot else 0
        print(f"  C{cat:02d} {s['pass']:>3}/{tot} ({rate}%)", flush=True)
    print("=" * 70, flush=True)
    print(f"[runner] saved to {output}", flush=True)


if __name__ == "__main__":
    main()
