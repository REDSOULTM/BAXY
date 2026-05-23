"""Runner identico a run_bench.py pero con tool_schemas_consolidated y stubs_consolidated.

Mide el impacto de consolidacion: con 16 tools en vez de 60, mismo modelo,
mismo system_prompt, mismos 540 tests.
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

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "buffer"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from tests import load_cases  # noqa
from system_prompt import SYSTEM_PROMPT  # noqa
from auditor import audit_case  # noqa
from stubs_consolidated import execute_tool  # noqa: tool consolidated dispatcher

SERVER_URL = "http://127.0.0.1:8080/v1/chat/completions"
HEALTH_URL = "http://127.0.0.1:8080/health"
SCHEMAS_PATH = ROOT / "tool_schemas_consolidated.json"

SAMPLING = {
    "temperature": 1.0,
    "top_p": 0.95,
    "top_k": 64,
    "repeat_penalty": 1.0,
    "max_tokens": 1280,
}

MAX_TURNS = 4


# Mapping consolidated tool name -> equivalent legacy name for auditor
# Auditor was trained on legacy names; we translate before audit.
def _translate_tool_for_auditor(name, args):
    """Convert composite tool call to legacy equivalent for auditor compatibility."""
    if name == "system_info":
        return {"time": "system_time", "cpu": "system_cpu", "ram": "system_ram",
                "gpu": "system_gpu", "disk": "system_disk", "battery": "system_battery",
                "volume": "system_get_volume"}.get(args.get("metric"), name)
    if name == "system_control":
        return {"set_volume": "system_set_volume", "mute": "system_mute",
                "shutdown": "system_shutdown", "reboot": "system_reboot"}.get(args.get("action"), name)
    if name == "app":
        return {"open": "app_open", "close": "app_close", "uninstall": "app_uninstall"}.get(args.get("action"), name)
    if name == "gui":
        return {"screenshot": "gui_screenshot", "click": "gui_click", "type": "gui_type",
                "keypress": "gui_keypress", "check_blockers": "gui_check_blockers",
                "locate": "vision_locate_target", "describe_dialog": "vision_describe_dialog",
                "universal_action": "gui_universal_action"}.get(args.get("action"), name)
    if name == "window":
        return {"list": "list_windows", "manage": "window_manage", "arrange": "window_arrange"}.get(args.get("action"), name)
    if name == "process":
        return "list_processes"
    if name == "filesystem":
        return f"filesystem_{args.get('action', '')}"
    if name == "web":
        return f"web_{args.get('action', '')}".replace("web_open_url", "web_open_url")
    if name == "memory":
        return f"memory_{args.get('action', '')}".replace("memory_list_all", "memory_list_all")
    if name == "media":
        return f"media_{args.get('action', '')}"
    if name == "clipboard":
        return f"clipboard_{args.get('action', '')}"
    if name == "office":
        if args.get("action") == "create":
            return f"office_{args.get('format','docx')}_create"
        return "office_word_open"
    if name == "registry":
        return f"registry_{args.get('action', '')}"
    return name


def _server_alive(timeout=2.0):
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def _call_llm(messages, tools, timeout=180.0):
    body = {"model": "gemma-4", "stream": False, "messages": messages,
            "tools": tools, "tool_choice": "auto", **SAMPLING}
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(SERVER_URL, data=data,
                                  headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _normalize_tool_calls(raw):
    out = []
    for tc in raw or []:
        fn = tc.get("function") or {}
        name = fn.get("name", "")
        args = fn.get("arguments", {})
        if isinstance(args, str):
            try: args = json.loads(args)
            except json.JSONDecodeError: args = {"_raw": args}
        out.append({"name": name, "arguments": args, "id": tc.get("id", f"call_{name}")})
    return out


def run_one_case(case, schemas):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": case.prompt},
    ]
    all_tool_calls = []
    final_reply = ""
    t0 = time.monotonic()
    for turn_idx in range(MAX_TURNS):
        try:
            resp = _call_llm(messages, schemas)
        except Exception as exc:
            dt = int((time.monotonic() - t0) * 1000)
            return {"cid": case.cid, "category": case.category, "severity": case.severity,
                    "prompt": case.prompt, "expected_tools": case.expected_tools,
                    "reply": f"LLM_ERROR: {type(exc).__name__}: {exc}",
                    "tools": [], "latency_ms": dt, "status": "FAIL",
                    "reasons": [f"llm_error: {exc}"]}

        choice = resp.get("choices", [{}])[0]
        msg = choice.get("message", {}) or {}
        content = msg.get("content", "") or ""
        finish_reason = choice.get("finish_reason", "")
        tool_calls_raw = msg.get("tool_calls", []) or []
        tool_calls = _normalize_tool_calls(tool_calls_raw)

        if not tool_calls:
            if not content.strip() and finish_reason == "length" and turn_idx < MAX_TURNS - 1:
                messages.append({"role": "user",
                    "content": "Por favor respondé en una frase corta."})
                continue
            final_reply = content
            break

        all_tool_calls.extend(tool_calls)
        messages.append({
            "role": "assistant", "content": content,
            "tool_calls": [{"id": tc["id"], "type": "function",
                            "function": {"name": tc["name"],
                                         "arguments": json.dumps(tc["arguments"])}}
                           for tc in tool_calls],
        })
        for tc in tool_calls:
            result = execute_tool(tc["name"], tc.get("arguments", {}))
            messages.append({"role": "tool", "tool_call_id": tc["id"],
                            "content": json.dumps(result, ensure_ascii=False)})

        if turn_idx == MAX_TURNS - 1:
            final_reply = content or "(loop sin reply final)"
            break

    dt = int((time.monotonic() - t0) * 1000)

    # Translate composite tool names back to legacy for auditor
    legacy_tool_calls = [
        {"name": _translate_tool_for_auditor(tc["name"], tc.get("arguments", {})),
         "arguments": tc.get("arguments", {})}
        for tc in all_tool_calls
    ]
    audit = audit_case(case, final_reply, legacy_tool_calls, dt)
    return {
        "cid": case.cid, "category": case.category, "severity": case.severity,
        "prompt": case.prompt, "expected_tools": case.expected_tools,
        "reply": final_reply[:500],
        "tools": [tc["name"] for tc in all_tool_calls],
        "tools_legacy": [tc["name"] for tc in legacy_tool_calls],
        "latency_ms": dt, "status": audit["status"], "reasons": audit["reasons"],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="unknown")
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int, default=None)
    parser.add_argument("--per-cat", type=int, default=None)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    if not _server_alive():
        print(f"[runner] llama-server no responde en {HEALTH_URL}", file=sys.stderr)
        sys.exit(2)

    schemas = json.loads(SCHEMAS_PATH.read_text(encoding="utf-8"))
    print(f"[runner-CONSOLIDATED] {len(schemas)} composite tools (vs 60 legacy)", flush=True)

    cases = load_cases()
    if args.per_cat:
        bucket = {}
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

    try:
        print("[runner] warmup...", flush=True)
        _call_llm([{"role": "system", "content": SYSTEM_PROMPT},
                   {"role": "user", "content": "ping"}], schemas)
    except Exception as exc:
        print(f"[runner] warmup fallo: {exc}", flush=True)

    results = []
    by_cat = {}
    pass_count = partial_count = fail_count = 0
    for i, case in enumerate(cases, 1):
        cat_stats = by_cat.setdefault(case.category, {"pass": 0, "partial": 0, "fail": 0})
        print(f"\n[{i:03d}/{len(cases)}] {case.cid} [{case.severity}] > {case.prompt[:80]}", flush=True)
        try:
            r = run_one_case(case, schemas)
        except Exception as exc:
            r = {"cid": case.cid, "category": case.category, "severity": case.severity,
                 "prompt": case.prompt, "status": "FAIL", "reasons": [f"exception: {exc}"],
                 "latency_ms": -1, "tools": [], "reply": ""}
        results.append(r)
        st = r.get("status", "FAIL")
        icon = {"PASS": "OK", "PARTIAL": "~~", "FAIL": "XX"}.get(st, "??")
        reply_short = (r.get("reply") or "").replace("\n", " ")[:120]
        print(f"   {icon} [{st}] ({r.get('latency_ms')}ms) {reply_short}", flush=True)
        if r.get("tools"):
            print(f"   tools: {r['tools']}", flush=True)
        if r.get("reasons"):
            print(f"   reasons: {r['reasons']}", flush=True)
        if st == "PASS": pass_count += 1; cat_stats["pass"] += 1
        elif st == "PARTIAL": partial_count += 1; cat_stats["partial"] += 1
        else: fail_count += 1; cat_stats["fail"] += 1
        if i % 30 == 0:
            output.write_text(json.dumps({
                "summary": {"completed": i, "total": len(cases),
                            "pass": pass_count, "partial": partial_count, "fail": fail_count,
                            "pass_rate": round(pass_count / i * 100, 2),
                            "model": args.model, "by_category": by_cat,
                            "tool_set": "consolidated_16"},
                "results": results,
            }, ensure_ascii=False, indent=2), encoding="utf-8")

    total = len(cases)
    summary = {"completed": total, "total": total,
               "pass": pass_count, "partial": partial_count, "fail": fail_count,
               "pass_rate": round(pass_count / total * 100, 2) if total else 0,
               "model": args.model, "by_category": by_cat,
               "tool_set": "consolidated_16"}
    output.write_text(json.dumps({"summary": summary, "results": results},
                                  ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n" + "=" * 70, flush=True)
    print(f"MODELO: {args.model}  TOOLS: 16 consolidated", flush=True)
    print(f"TOTAL: {total}  PASS: {pass_count}  PARTIAL: {partial_count}  FAIL: {fail_count}", flush=True)
    print(f"Pass rate: {summary['pass_rate']}%", flush=True)
    print("Por categoria:", flush=True)
    for cat in sorted(by_cat.keys()):
        s = by_cat[cat]
        tot = sum(s.values())
        rate = round(s["pass"] / tot * 100, 1) if tot else 0
        print(f"  C{cat:02d} {s['pass']:>3}/{tot} ({rate}%)", flush=True)
    print("=" * 70, flush=True)


if __name__ == "__main__":
    main()
