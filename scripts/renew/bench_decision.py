"""Decision bench: Renew's own Mind on its own llama-server, one model decision per case (no tool runs).

usage: py -3.12 -X utf8 scripts/renew/bench_decision.py <label> --cases FILE [--temp 0.2]
       [--gguf PATH] [--server-args "..."] [--catalog FILE] [--ctx 40960]
Cases: list of {id, family, history?, text, expect{kind: call|call_any|ask|text|any, op?, ops?, args?, options?}} (see
README of the banks; «any» lists the expectations a case accepts). Writes <banks>/runs/<label>.jsonl: a summary line (accuracy, decision p50/p90, VRAM and RAM of llama-server and
of this process acting as the mind) and one row per case. The summary's «run» says what was measured (run_record): the
mind's source, the catalog, the judge, the GGUF and the server with their sha256, KV, context, seed, temperature, System
One and every BAXY_* switch; «errors» the cases the model server failed (a failure, but not the model's answer).
The kernel's confirmation mode the mind reads (System One's «corrige») is the bench's own, normal, unless BAXY_DATA_DIR
is given: it was the owner's file %LOCALAPPDATA%\\BAXY\\1\\confirmation-mode, different on each machine.
"""
import argparse
import json
import os
import re
import statistics
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

import psutil

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_meta  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
BANKS = Path(os.environ.get("BAXY_RENEW_BANKS", r"F:\BAXYeval\renew_v1"))
# The catalog changed after the banks were written (operations merged or replaced, 2026-10-15): an expectation that
# names a retired operation is met by the operation that replaced it, with its fixed arguments and its arguments
# renamed; an argument with no counterpart is not checked. A case whose operation was retired with nothing in its
# place (op null) is left out of the count: no answer can be checked honestly against an action BAXY no longer has. Public, versioned, and applied without opening the banks.
EQUIVALENCE_FILE = Path(__file__).with_name("catalog_equivalence.json")
EQUIVALENCE = json.loads(EQUIVALENCE_FILE.read_text(encoding="utf-8")) if EQUIVALENCE_FILE.is_file() else {}


def current(op, args=None):
    """The operation and arguments that meet an expectation written for «op» in today's catalog."""
    entry = EQUIVALENCE.get(op)
    if not entry:
        return op, dict(args or {}), {}
    renamed = {}
    for name, want in (args or {}).items():
        target = (entry.get("args") or {}).get(name, name)
        if target is not None:
            renamed[target] = want
    return entry["op"], renamed, dict(entry.get("fixed") or {})


def norm(value):
    text = unicodedata.normalize("NFKD", str(value).lower())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def enums_of(catalog: dict) -> dict[str, dict[str, set[str]]]:
    """Each operation's arguments that take one code of a list (their schema's enum), normalized: op → arg → codes."""
    found: dict[str, dict[str, set[str]]] = {}
    for cap in catalog.get("capabilities") or []:
        for name, schema in ((cap.get("argumentsSchema") or {}).get("properties") or {}).items():
            if isinstance(schema, dict) and isinstance(schema.get("enum"), list):
                found.setdefault(str(cap.get("name")), {})[name] = {norm(v).strip() for v in schema["enum"]}
    return found


def arg_ok(want, got, codes=None):
    if got is None:
        return False
    if isinstance(want, bool):
        return got is want or norm(got) == norm(want)
    if isinstance(want, (int, float)):
        try:
            return float(got) == float(want)
        except (TypeError, ValueError):
            return False
    if isinstance(want, str) and want.startswith("re:"):
        return re.search(want[3:], norm(got)) is not None
    if codes and norm(want).strip() in codes:
        # Audit w8-medir (2026-10-23): one code of the argument's list is that code, not any text that holds it. As a
        # part of the text, «close» passed browser.control close_all, «space» backspace, «tab» alt_tab, «escape»
        # ctrl_shift_escape (Task Manager), «memory» cpu_memory and os_memory, «game» gamemode (16 such pairs in
        # catalog-final.json).
        return norm(got).strip() == norm(want).strip()
    return norm(want) in norm(got)


def judge(expect, result, arguments, enums=None):
    """True, False, or None (not counted). With `enums` (enums_of the run's catalog), an argument of a code list is
    compared exactly; without it, as part of the text, as before the audit."""
    kind = result.get("kind")
    enums = enums or {}
    if expect["kind"] == "any":
        # decision3 (README of practica): a case with more than one defensible answer lists them as options of any kind;
        # it is met by any of them, and left out only when every option names a retired operation.
        verdicts = [judge(option, result, arguments, enums) for option in expect["options"]]
        return None if all(v is None for v in verdicts) else any(bool(v) for v in verdicts)
    if expect["kind"] == "call":
        op, args, fixed = current(expect["op"], expect.get("args"))
        if op is None:  # retired with no replacement: not counted
            return None
        codes = enums.get(op) or {}
        return (kind == "action" and result.get("operation") == op
                and all(arg_ok(v, (arguments or {}).get(k), codes.get(k)) for k, v in {**args, **fixed}.items()))
    if expect["kind"] == "call_any":
        live = [current(candidate) for candidate in expect["ops"]]
        if all(op is None for op, _, _ in live):
            return None
        for op, _, fixed in live:
            if op is None:
                continue
            codes = enums.get(op) or {}
            if kind == "action" and result.get("operation") == op and all(
                    arg_ok(v, (arguments or {}).get(k), codes.get(k)) for k, v in fixed.items()):
                return True
        return False
    if expect["kind"] == "ask":
        # A spoken answer that asks the person something is a question, wherever its «?» is («¿Qué juego quieres
        # abrir? Necesito el nombre.»).
        return kind == "clarify" or (kind == "conversation" and "?" in str(result.get("reply", "")))
    if expect["kind"] == "text":
        reply = str(result.get("reply", ""))
        if kind != "conversation" or not reply.strip():
            return False
        # Goal «ayudas» (SEALED_AYUDAS.md): a text case may say, as regexes over the normalized reply, what the answer
        # must say (a mode that is not there yet) and what it must not claim (closing or saving what failed).
        said = norm(reply)
        must = expect.get("reply_re") or []
        must_not = expect.get("reply_not_re") or []
        return (all(re.search(spec, said) for spec in ([must] if isinstance(must, str) else must))
                and not any(re.search(spec, said) for spec in ([must_not] if isinstance(must_not, str) else must_not)))
    raise ValueError(expect)


def decide(mind, case):
    """The model's decision for a case, with the confirmation the case says is waiting for the person's «sí» (a case of
    the family confirmacion_pendiente carries `pending` {operation, arguments}, as the App sends it with the words;
    holdout v5: without it confirm_pending read nothing_pending and those cases could never pass)."""
    return mind.decide(case["id"], case["text"], pending=case.get("pending"))


class CountedSystemOne:
    """System One as the mind calls it (choose), counting the times it was asked and the times no answer came back: its
    server down, an order slower than choose's timeout (2 s each), or an answer not of its shape. The mind then goes on
    as Qwen decided, so a run «with System One» silently measured part of its cases without it (audit w8-medir)."""

    def __init__(self, inner) -> None:
        self.inner = inner
        self.asked = self.unanswered = 0
        self.case: str | None = None  # this case's: None, «answered» or «unanswered»

    def choose(self, text, history, options, *more, **named):
        answer = self.inner.choose(text, history, options, *more, **named)
        if len(options) >= 2:
            self.asked += 1
            self.unanswered += answer is None
            self.case = "unanswered" if answer is None or self.case == "unanswered" else "answered"
        return answer

    def __getattr__(self, name):
        return getattr(self.inner, name)


def wait_system_one(system_one, timeout: float = 300.0, poll: float = 0.25) -> None:
    """Until System One's server answers its health check. A server that died or never came up stops the run: the
    first cases ran without it (nothing waited for it: the product's turns do not, by design) and a crash under the
    RAM of a busy PC left the whole run without it, still labelled «with System One»."""
    deadline = time.monotonic() + timeout
    while not system_one.ready:
        process = getattr(system_one, "_process", None)
        if process is not None and process.poll() is not None:
            raise SystemExit(f"System One's server exited ({process.returncode}): see system-one.log; nothing was measured")
        if time.monotonic() > deadline:
            raise SystemExit(f"System One's server was not up after {timeout:.0f} s; nothing was measured")
        time.sleep(poll)


def gpu_used_mib():
    out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                         capture_output=True, text=True, timeout=20).stdout.strip().splitlines()
    return int(out[0]) if out and out[0].strip().isdigit() else None


def resources(server_pid, gpu_before):
    """VRAM as the GPU's growth since before llama-server started (WDDM reports no per-process VRAM) and RAM (working
    set and private bytes) of llama-server and of this process acting as the mind."""
    def ram(pid):
        # USS is the RAM the process alone holds: llama-server's working set counts the mapped GGUF, and its private
        # bytes count the VRAM WDDM commits (measured on the notebook, 2026-10-15).
        info = psutil.Process(pid).memory_full_info()
        return {"uss_mib": round(info.uss / 2**20), "working_set_mib": round(info.rss / 2**20),
                "private_mib": round(getattr(info, "private", 0) / 2**20)}

    after = gpu_used_mib()
    return {"llama_server": {"vram_mib": after - gpu_before if after is not None and gpu_before is not None else None,
                             **ram(server_pid)},
            "mind": ram(os.getpid()), "gpu_before_mib": gpu_before, "gpu_after_mib": after}


def run_record(args, server, mind, environ=None) -> dict:
    """What this run measured with (run_meta): written into the summary, so a run says what it is without its script."""
    cache = run_meta._cache_path()
    src = Path(args.src)
    return {"machine": run_meta.machine(), "src": str(src), "src_git": run_meta.git_state(src),
            "mind_sha256": run_meta.tree_sha256(src / "baxy_mind"),
            "judge_sha256": run_meta.sha256_file(Path(__file__)),
            "equivalence_sha256": run_meta.sha256_file(EQUIVALENCE_FILE),
            "catalog": run_meta.fingerprint(args.catalog, cache), "gguf": run_meta.fingerprint(args.gguf, cache),
            "server": run_meta.fingerprint(args.server, cache), "server_args": args.server_args,
            "kv": list(getattr(server, "kv", []) or []), "ctx": int(args.ctx),
            "seed": getattr(mind, "seed", None), "temp": float(args.temp),
            "s1_gguf": run_meta.fingerprint(os.environ.get("BAXY_S1_GGUF", "").strip() or None, cache),
            "confirmation_mode": run_meta.confirmation_mode(environ), "env": run_meta.baxy_env(environ)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("label")
    parser.add_argument("--cases", required=True)
    parser.add_argument("--temp", default="0.2")
    parser.add_argument("--gguf", default=os.environ.get("BAXY_MIND_LLM_GGUF", r"F:\BAXYeval\models\Qwen3.5-4B-Q4_K_M.gguf"))
    parser.add_argument("--server", default=os.environ.get("BAXY_MIND_LLAMA_SERVER", r"F:\BAXYeval\llama\llama-server.exe"))
    parser.add_argument("--server-args", default="")
    parser.add_argument("--catalog", default=str(Path(os.environ["LOCALAPPDATA"]) / "BAXY" / "renew" / "catalog.configure.json"))
    parser.add_argument("--ctx", default="53248")
    parser.add_argument("--src", default=str(ROOT / "src"), help="the mind to measure (a copy for an A/B of the prompt)")
    args = parser.parse_args()
    os.environ["BAXY_RENEW_DECIDE_TEMPERATURE"] = args.temp
    sys.path.insert(0, args.src)
    from baxy_mind.llm_server import LlmServer  # noqa: E402
    from baxy_mind.mind import Mind  # noqa: E402

    runs = BANKS / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    # The confirmation mode «corrige» reads is the bench's (normal), never the owner's file on this machine.
    os.environ.setdefault("BAXY_DATA_DIR", str(runs / f"{args.label}.datos"))
    # The server's --slot-save-path is the run's own: in the product's folder two runs at once collided on its
    # baxy_prefix_*.slot (WinError 32, 2026-10-25) and save_prefix removed the product's kept prefix.
    os.environ.setdefault("BAXY_VISION_SLOT_DIR", str(runs / f"{args.label}.ranuras"))
    trace = runs / f"{args.label}.trace.jsonl"
    trace.unlink(missing_ok=True)  # the mind appends: a label run again kept the trace of the run before
    gpu_before = gpu_used_mib()
    server = LlmServer(args.gguf, args.server, context=int(args.ctx), extra_args=args.server_args.split(),
                       log_name=f"bench-{args.label}.log")
    system_one = None
    try:
        server.start()
        if os.environ.get("BAXY_S1_GGUF", "").strip():  # System One, layer 2, as the product starts it (__main__.py)
            from baxy_mind.system_one import SystemOne  # noqa: E402
            system_one = SystemOne(os.environ["BAXY_S1_GGUF"].strip(), args.server,
                                   int(os.environ.get("BAXY_S1_THREADS", "4") or 4))
            system_one.start()
            system_one = CountedSystemOne(system_one)
        mind = Mind(server, trace, system_one)
        catalog = json.loads(Path(args.catalog).read_text(encoding="utf-8"))
        enums = enums_of(catalog)
        mind.configure(catalog)
        server.wait_ready(600)
        t0 = time.monotonic()
        mind.warm()
        warm_s = time.monotonic() - t0
        if system_one is not None:
            wait_system_one(system_one)
        cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
        rows, by_family = [], {}
        for case in cases:
            started = time.monotonic()
            if system_one is not None:
                system_one.case = None
            try:
                mind.new_session(case.get("history") or [])
                result = decide(mind, case)
                error = None
            except Exception as exc:  # noqa: BLE001 - a failed case is a failed case
                result, error = {"kind": "error"}, repr(exc)[:200]
            latency = time.monotonic() - started
            arguments = result.get("arguments") if result.get("operation") else None
            verdict = judge(case["expect"], result, arguments, enums)
            excluded = verdict is None
            ok = error is None and bool(verdict)
            if not excluded:
                fam = by_family.setdefault(str(case.get("family", "-")), [0, 0])
                fam[0] += ok
                fam[1] += 1
            rows.append({"id": case["id"], "family": case.get("family"), "ok": ok, "excluded": excluded,
                         "latency_s": round(latency, 3),
                         "kind": result.get("kind"), "operation": result.get("operation"), "arguments": arguments,
                         "reply": result.get("reply") or result.get("question"), "error": error,
                         "system_one": system_one.case if system_one is not None else None})
            print(f"{case['id']} {'-- ' if excluded else 'ok ' if ok else 'BAD'} {latency:5.2f}s {result.get('kind')} {result.get('operation')}",
                  flush=True)
        measured = resources(server._process.pid, gpu_before)  # type: ignore[union-attr]
        s1 = None
        if system_one is not None:
            # Asked, and not answered (the cases go on as Qwen decided): a run with many unanswered is not «with S1».
            s1 = {"asked": system_one.asked, "unanswered": system_one.unanswered, "up_at_end": system_one.ready,
                  "unanswered_ids": [r["id"] for r in rows if r["system_one"] == "unanswered"],
                  "threads": int(os.environ.get("BAXY_S1_THREADS", "4") or 4)}
        latencies = [r["latency_s"] for r in rows]
        counted = [r for r in rows if not r["excluded"]]
        summary = {"label": args.label, "cases": str(args.cases), "temp": args.temp,
                   "gguf": Path(args.gguf).name, "server_args": args.server_args, "ok": sum(r["ok"] for r in counted),
                   "n": len(counted), "accuracy": round(sum(r["ok"] for r in counted) / max(1, len(counted)), 4),
                   "excluded_retired": [r["id"] for r in rows if r["excluded"]],
                   # A case the model server failed (HTTP error, timeout) counts as wrong; a run with any is not clean.
                   "errors": sum(1 for r in rows if r["error"]), "error_ids": [r["id"] for r in rows if r["error"]],
                   "p50": round(statistics.median(latencies), 3),
                   "p90": round(statistics.quantiles(latencies, n=10)[8], 3) if len(latencies) > 2 else None,
                   "warm_s": round(warm_s, 1), "families": by_family, "resources": measured, "system_one": s1,
                   "run": run_record(args, server, mind)}
        with open(runs / f"{args.label}.jsonl", "w", encoding="utf-8") as out:
            out.write(json.dumps({"summary": summary}, ensure_ascii=False) + "\n")
            for row in rows:
                out.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(json.dumps(summary, ensure_ascii=False))
    finally:
        # Whatever stopped the run (System One dead, a Ctrl+C, a catalog that does not read), no server outlives it.
        try:
            server.close()
        finally:  # a second Ctrl+C inside Qwen's close must not leave System One's running
            if system_one is not None:
                system_one.close()


if __name__ == "__main__":
    main()
