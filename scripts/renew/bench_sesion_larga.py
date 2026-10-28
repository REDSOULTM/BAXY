"""Long-session bench (noche P0.1): the cases of the decision banks chained in ONE conversation of 40-60 turns, with
Renew's own Mind on its own llama-server, mounted as bench_decision.py mounts it (its judge, its System One, its run
record; bench_decision.py itself is not touched: its sha256 is the judge's identity).

usage:
  armar:   py -3.12 -X utf8 scripts/renew/bench_sesion_larga.py armar --out SESSION.json [--turnos 50] [--semilla 0]
           [--fuente NAME=FILE ...] [--catalog FILE] [--corpus GLOB]
  correr:  py -3.12 -X utf8 scripts/renew/bench_sesion_larga.py correr <label> --sesion SESSION.json --desde 1 --hasta 10
           [--catalog FILE] [--src DIR] [--temp 0.2] [--gguf PATH] [--server PATH] [--server-args "..."] [--ctx 53248]
  resumir: py -3.12 -X utf8 scripts/renew/bench_sesion_larga.py resumir <label> [--tramo 10] [--aislado RUN.jsonl ...]

armar picks cases with no history of their own and no confirmation waiting (a long session has its own history), mixed
by what they ask (an action, words, a search, a read, a question back) and by bank, and keeps with them the long texts
the session's reads return. correr runs turns desde..hasta of that session: every turn is the person's words to
Mind.decide, judged as bench_decision judges a case (the first decision of the turn); then the turn is closed as the App
would: each call gets its result (a read gets one of the session's long texts, an effect a completed and verified
result) until the model answers in words, at most MAX_CALLS calls. Per turn it writes the prompt's size and what it is
made of (system, catalog, history, tool results), the turns the mind cut, and the context_shrunk of the trace. A tanda
starts from the session the tanda before left (<label>.sesion-<N>.json, Mind.export_session/load_session, as the App
keeps a session), so the bench runs in tandas of a few minutes. resumir joins the tandas of a label and aggregates them by
stretches of turns (1-10, 11-20, ...) into <label>.resumen.json and .md; with --aislado (bench_decision runs of the same
cases) it says, per stretch, how the same cases did each on its own.
"""
import argparse
import glob
import json
import os
import random
import re
import statistics
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bench_decision
import bench_guardas

ROOT = Path(__file__).resolve().parents[2]
BANKS = Path(os.environ.get("BAXY_RENEW_BANKS", r"F:\BAXYeval\renew_v1"))
SOURCES = {"v11": r"F:\BAXYeval\renew_v11\holdout\abierto\decision.json",
           "v6": r"F:\BAXYeval\renew_v6\holdout\abierto\decision.json",
           "feria": r"F:\BAXYeval\fallos\bateria_feria.json",
           "heldout": r"F:\BAXYeval\fallos\bateria_heldout.json"}
READ_RISKS = ("read_only",)
# The order the categories come in, one cycle every 20 turns: as many actions as the rest, words between them, and a
# search or a long read every few turns, so the results pile up in the history as in a long working session.
PATTERN = ["accion", "charla", "busqueda", "accion", "lectura", "accion", "charla", "accion", "pregunta", "lectura",
           "accion", "busqueda", "charla", "accion", "lectura", "accion", "charla", "busqueda", "accion", "lectura"]
MAX_CALLS = 3
LONG_READ = (6000, 2500, 9000)  # characters of the reads' bodies, in turn: long, medium, very long
REPLY_CHARS = 300


def category(expect: dict, risk: dict[str, str]) -> str:
    """What a case asks, by its expectation: the first option of an «any»."""
    kind = expect.get("kind")
    if kind == "any":
        return category((expect.get("options") or [{}])[0], risk)
    if kind == "text":
        return "charla"
    if kind == "ask":
        return "pregunta"
    ops = [expect.get("op")] if kind == "call" else list(expect.get("ops") or [])
    ops = [bench_decision.current(op)[0] or op for op in ops if op]
    if any(op in {"web.search", "web.fetch"} for op in ops):
        return "busqueda"
    if ops and all(risk.get(op) in READ_RISKS for op in ops):
        return "lectura"
    return "accion"


def chunks(paths: list[str], size: int = 2000) -> list[str]:
    """The corpus' paragraphs, joined up to about `size` characters each: the long texts the session's reads return."""
    out: list[str] = []
    for path in paths:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
        piece = ""
        for paragraph in re.split(r"\n\s*\n", text):
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            piece = f"{piece}\n\n{paragraph}" if piece else paragraph
            if len(piece) >= size:
                out.append(piece)
                piece = ""
        if piece:
            out.append(piece)
    return out


def armar(banks: dict[str, list[dict]], turnos: int, semilla: int, risk: dict[str, str], lecturas: list[str]) -> dict:
    """One session of `turnos` turns from the banks' cases (no history, no confirmation waiting), in PATTERN's order of
    categories and taking each category's cases from the banks in turn; a category with no case left gives its place to
    the next one of the pattern. Deterministic for a seed."""
    rng = random.Random(semilla)
    pools: dict[str, dict[str, list[dict]]] = {}
    for name, cases in banks.items():
        eligible = [c for c in cases if not c.get("history") and not c.get("pending")]
        rng.shuffle(eligible)
        for case in eligible:
            pools.setdefault(category(case["expect"], risk), {}).setdefault(name, []).append(case)
    turns: list[dict] = []
    turn_of_bank: dict[str, int] = {}
    position = 0
    while len(turns) < turnos and any(any(b.values()) for b in pools.values()):
        wanted = PATTERN[position % len(PATTERN)]
        position += 1
        by_bank = pools.get(wanted) or {}
        names = [n for n in banks if by_bank.get(n)]
        if not names:
            continue
        name = names[turn_of_bank.get(wanted, 0) % len(names)]
        turn_of_bank[wanted] = turn_of_bank.get(wanted, 0) + 1
        case = by_bank[name].pop()
        n = len(turns) + 1
        turns.append({"n": n, "id": f"L{n:02d}-{name}-{case['id']}", "case": case["id"], "bank": name,
                      "category": wanted, "family": case.get("family"), "text": case["text"],
                      "expect": case["expect"]})
    return {"version": 1, "semilla": semilla, "turnos": turns, "lecturas": lecturas}


def observation(op: str, arguments: dict | None, risk: str, lecturas: list[str], index: int) -> str:
    """The result the bench's App gives a call: a read gets a long body (its size and text change with `index`), a
    search eight results with their snippets, an effect a completed and verified result."""
    if op == "web.search" or (risk in READ_RISKS and lecturas):
        size = LONG_READ[index % len(LONG_READ)]
        body, at = "", index
        while len(body) < size and lecturas:
            body += ("\n\n" if body else "") + lecturas[at % len(lecturas)]
            at += 1
        body = body[:size]
        if op == "web.search":
            query = str((arguments or {}).get("query") or "")
            parts = [body[i:i + 400] for i in range(0, min(len(body), 3200), 400)] or [""]
            observed = {"query": query, "results": [
                {"title": " ".join(p.split()[:8]), "url": f"https://ejemplo.org/articulo/{index}-{i}", "snippet": p}
                for i, p in enumerate(parts)]}
        else:
            observed = {"text": body, "chars": len(body)}
        return json.dumps({"status": "completed", "verification": "output_only", "observed": observed},
                          ensure_ascii=False)
    return json.dumps({"status": "completed", "verification": "readback", "observed": {}}, ensure_ascii=False)


class RecordingServer:
    """The mind's llama-server, keeping what each chat sent, by part (system, catalog's tools, history, tool results),
    and the prompt's tokens the server counted. The texts are copied when sent: the mind leaves out results' bodies in
    place afterwards."""

    def __init__(self, inner: Any) -> None:
        self.inner = inner
        self.sent: list[dict] = []

    def chat(self, body: dict, *more: Any, **named: Any) -> dict:
        messages = body.get("messages") or []
        parts = {"system": "", "history": "", "tool_results": ""}
        for message in messages:
            role = message.get("role")
            key = "system" if role == "system" else "tool_results" if role == "tool" else "history"
            parts[key] += str(message.get("content") or "")
            for call in message.get("tool_calls") or []:
                parts["history"] += json.dumps(call.get("function") or {}, ensure_ascii=False)
        record = {"parts": parts, "messages": len(messages), "prompt_tokens": None, "error": None}
        self.sent.append(record)
        try:
            reply = self.inner.chat(body, *more, **named)
        except Exception as exc:
            record["error"] = type(exc).__name__
            raise
        record["prompt_tokens"] = (reply.get("usage") or {}).get("prompt_tokens")
        return reply

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)


def sizes(server: Any, record: dict, prefix_tokens: int, system_tokens: int) -> dict:
    """A chat's prompt in tokens, by part: the catalog is the prefix (system and tools, measured at warm-up) less the
    system; «otros» is what the template adds (roles, call markup) and what the parts do not count."""
    history = len(server.tokenize(record["parts"]["history"])) if record["parts"]["history"] else 0
    results = len(server.tokenize(record["parts"]["tool_results"])) if record["parts"]["tool_results"] else 0
    catalog = max(0, prefix_tokens - system_tokens)
    total = record["prompt_tokens"]
    return {"total": total, "system": system_tokens, "catalog": catalog, "history": history, "tool_results": results,
            "otros": None if total is None else total - system_tokens - catalog - history - results,
            "messages": record["messages"]}


def trace_rows(trace: Path, start: int) -> tuple[list[dict], int]:
    """The trace's rows written since byte `start`, and where it ends now."""
    if not trace.is_file():
        return [], start
    with trace.open("rb") as handle:
        handle.seek(start)
        data = handle.read()
    rows = []
    for line in data.decode("utf-8", errors="replace").splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows, start + len(data)


def correr_turnos(mind: Any, server: RecordingServer, turns: list[dict], lecturas: list[str], enums: dict, trace: Path,
                  system_one: Any = None, guards: Any = None) -> list[dict]:
    """Each turn to the mind in order, judged on its first decision and then closed as the App would (module text).
    With `guards` (bench_guardas.Guards, the App's own) every call goes through them first, and the turn is also judged
    on the decision the person sees (ok_seen)."""
    system_tokens = len(server.tokenize(mind._system())) if mind.prefix_tokens else 0
    at = trace.stat().st_size if trace.is_file() else 0
    rows = []
    for turn in turns:
        started = time.monotonic()
        server.sent.clear()
        open_ask = bool((getattr(mind, "_turn", None) or {}).get("asked"))
        if system_one is not None:
            system_one.case = None
        calls, error, refused = [], None, []
        decision = result = shown = {"kind": "error"}
        try:
            if guards is not None:
                guards.heard(turn["text"])
            result = decision = mind.decide(turn["id"], turn["text"])
            if guards is not None:
                shown, calls, refused, result = bench_guardas.seen(
                    mind, turn["id"], decision, guards, MAX_CALLS,
                    lambda op, arguments, index: observation(op, arguments, mind.risk.get(op.replace(".", "_"), ""),
                                                             lecturas, turn["n"] * MAX_CALLS + index))
            while guards is None and result.get("kind") == "action" and len(calls) < MAX_CALLS:
                op = str(result.get("operation"))
                calls.append(op)
                result = mind.continue_turn(turn["id"], observation(
                    op, result.get("arguments"), mind.risk.get(mind.wires.name(op), ""), lecturas,
                    turn["n"] * MAX_CALLS + len(calls)), final=len(calls) == MAX_CALLS)
        except Exception as exc:
            # A decision that came is judged; a failure after it (a result's continuation) stays in «error».
            error = repr(exc)[:200]
        latency = time.monotonic() - started
        arguments = decision.get("arguments") if decision.get("operation") else None
        verdict = bench_decision.judge(turn["expect"], decision, arguments, enums)
        excluded = verdict is None
        ok = decision.get("kind") != "error" and bool(verdict)
        traced, at = trace_rows(trace, at)
        sent = [r for r in server.sent if r["error"] is None]
        first = sent[0] if sent else None
        rows.append({"n": turn["n"], "id": turn["id"], "case": turn.get("case"), "bank": turn.get("bank"),
                     "category": turn.get("category"), "family": turn.get("family"), "ok": ok, "excluded": excluded,
                     "latency_s": round(latency, 3), "open_ask_before": open_ask,
                     "kind": decision.get("kind"), "operation": decision.get("operation"), "arguments": arguments,
                     "reply": str(decision.get("reply") or decision.get("question") or "")[:REPLY_CHARS],
                     "calls": calls, "final_kind": result.get("kind") if error is None else "error", "error": error,
                     "chats": len(server.sent),
                     "context": sizes(server, first, mind.prefix_tokens, system_tokens) if first else None,
                     "context_max": max((r["prompt_tokens"] for r in sent if r["prompt_tokens"] is not None), default=None),
                     "n_ctx": getattr(server, "context", None),
                     "trimmed_turns": mind.trimmed_turns, "conversation_messages": len(mind.conversation),
                     "context_shrunk": sum(1 for r in traced if r.get("kind") == "context_shrunk"),
                     "system_one": system_one.case if system_one is not None else None})
        if guards is not None:
            seen_arguments = shown.get("arguments") if shown.get("operation") else None
            seen_verdict = bench_decision.judge(turn["expect"], shown, seen_arguments, enums)
            rows[-1].update(ok_seen=shown.get("kind") != "error" and bool(seen_verdict), refused=refused,
                            seen_kind=shown.get("kind"), seen_operation=shown.get("operation"),
                            seen_arguments=seen_arguments,
                            seen_reply=str(shown.get("reply") or shown.get("question") or "")[:REPLY_CHARS])
        print(f"{turn['n']:>2} {turn['id']} {'-- ' if excluded else 'ok ' if ok else 'BAD'} {latency:5.2f}s "
              f"{decision.get('kind')} {decision.get('operation')} ctx={rows[-1]['context_max']}", flush=True)
    return rows


def kept_trim_count(conversation: list[dict], mark: str) -> int:
    """How many turns the note of a cut at a kept session's start says are gone (0 without one), read as Mind._drop
    reads it (`mark`: the note's text up to its colon): load_session starts the mind's count at 0 again and only its
    next cut reads the note, so a tanda's first rows said 0."""
    first = str((conversation[:1] or [{}])[0].get("content") or "")
    told = re.match(r"\D*(\d+)", first) if first.startswith(mark) else None
    return int(told.group(1)) if told else 0


def snapshot_path(label: str, upto: int) -> Path:
    return BANKS / "runs" / f"{label}.sesion-{upto:02d}.json"


def correr(args: argparse.Namespace) -> None:
    os.environ["BAXY_RENEW_DECIDE_TEMPERATURE"] = args.temp
    sys.path.insert(0, args.src)
    from baxy_mind.llm_server import LlmServer
    from baxy_mind.mind import TRIMMED, Mind

    session = json.loads(Path(args.sesion).read_text(encoding="utf-8"))
    turns = [t for t in session["turnos"] if args.desde <= t["n"] <= args.hasta]
    if not turns:
        raise SystemExit(f"no turns {args.desde}..{args.hasta} in {args.sesion}")
    earlier = snapshot_path(args.label, args.desde - 1)
    if args.desde > 1 and not earlier.is_file():
        raise SystemExit(f"turn {args.desde} starts from the session turn {args.desde - 1} left: {earlier} is missing "
                         "(run the tanda before it first)")
    runs = BANKS / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    tanda = f"{args.label}-t{args.desde:02d}-{args.hasta:02d}"
    os.environ.setdefault("BAXY_DATA_DIR", str(runs / f"{args.label}.datos"))
    trace = runs / f"{tanda}.trace.jsonl"
    trace.unlink(missing_ok=True)
    gpu_before = bench_decision.gpu_used_mib()
    inner = LlmServer(args.gguf, args.server, context=int(args.ctx), extra_args=args.server_args.split(),
                      log_name=f"bench-{args.label}.log")
    inner.start()
    system_one = guards = None
    # What the bench starts it closes, whatever fails on the way (a server left up holds the GPU and its port).
    try:
        server = RecordingServer(inner)
        if os.environ.get("BAXY_S1_GGUF", "").strip():  # as bench_decision starts it
            from baxy_mind.system_one import SystemOne
            system_one = SystemOne(os.environ["BAXY_S1_GGUF"].strip(), args.server,
                                   int(os.environ.get("BAXY_S1_THREADS", "4") or 4))
            system_one.start()
            system_one = bench_decision.CountedSystemOne(system_one)
        mind = Mind(server, trace, system_one)  # type: ignore[arg-type]
        catalog = json.loads(Path(args.catalog).read_text(encoding="utf-8"))
        enums = bench_decision.enums_of(catalog)
        mind.configure(catalog)
        inner.wait_ready(600)
        t0 = time.monotonic()
        mind.warm()
        warm_s = time.monotonic() - t0
        if not mind.prefix_tokens:  # without it the system and the catalog would count 0 and the mind trim by characters
            raise SystemExit("the warm-up measured no prefix tokens; nothing was measured")
        if system_one is not None:
            bench_decision.wait_system_one(system_one)
        if args.desde > 1:
            mind.load_session(json.loads(earlier.read_text(encoding="utf-8")))
            mind.trimmed_turns = kept_trim_count(mind.conversation, TRIMMED[:TRIMMED.index(":")])
        else:
            mind.new_session([])
        if args.guardas:
            guards = bench_guardas.Guards(args.guardas)
            # The oracle starts empty: a later tanda's guards hear the turn before it, as the App's heard it.
            if args.desde > 1:
                guards.heard(next(t["text"] for t in session["turnos"] if t["n"] == args.desde - 1))
        rows = correr_turnos(mind, server, turns, session.get("lecturas") or [], enums, trace, system_one, guards)
        snapshot_path(args.label, args.hasta).write_text(json.dumps(mind.export_session(), ensure_ascii=False),
                                                         encoding="utf-8")
        # A question of the model's open at the end: the next tanda's load_session closes it as asked (the App's own
        # reload); in one run the next words would have answered it.
        open_at_end = bool((getattr(mind, "_turn", None) or {}).get("asked"))
        measured = bench_decision.resources(inner._process.pid, gpu_before)  # type: ignore[union-attr]
        s1 = None
        if system_one is not None:
            s1 = {"asked": system_one.asked, "unanswered": system_one.unanswered, "up_at_end": system_one.ready,
                  "unanswered_ids": [r["id"] for r in rows if r["system_one"] == "unanswered"]}
    finally:
        inner.close()
        if system_one is not None:
            system_one.close()
        if guards is not None:
            guards.close()
    counted = [r for r in rows if not r["excluded"]]
    summary = {"label": args.label, "tanda": [args.desde, args.hasta], "sesion": str(args.sesion),
               "from_snapshot": str(earlier) if args.desde > 1 else None, "open_ask_at_end": open_at_end,
               "ok": sum(r["ok"] for r in counted), "n": len(counted),
               "accuracy": round(sum(r["ok"] for r in counted) / max(1, len(counted)), 4),
               **bench_guardas.seen_summary(counted, args.guardas),
               "errors": sum(1 for r in rows if r["error"]), "warm_s": round(warm_s, 1),
               "prefix_tokens": mind.prefix_tokens, "resources": measured, "system_one": s1,
               "run": bench_decision.run_record(args, inner, mind)}
    with open(runs / f"{tanda}.jsonl", "w", encoding="utf-8") as out:
        out.write(json.dumps({"summary": summary}, ensure_ascii=False) + "\n")
        for row in rows:
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps({k: summary[k] for k in ("label", "tanda", "ok", "n", "accuracy", "ok_seen", "errors") if k in summary},
                     ensure_ascii=False))


def _mean(values: list) -> float | None:
    values = [v for v in values if v is not None]
    return round(statistics.mean(values)) if values else None


def resumir(rows: list[dict], tramo: int = 10, aislado: dict[tuple, bool] | None = None) -> dict:
    """The turns by stretches of `tramo`: accuracy, the prompt's mean and largest size with its parts, the turns cut
    and the context_shrunk; with `aislado` ((bank, case id) → ok each on its own), the same cases' accuracy alone."""
    by_n = {r["n"]: r for r in rows}  # a turn run again in a later tanda: the later one
    ordered = [by_n[n] for n in sorted(by_n)]
    stretches = []
    for begin in range(1, (max(by_n) if by_n else 0) + 1, tramo):
        part = [r for r in ordered if begin <= r["n"] < begin + tramo]
        if not part:
            continue
        counted = [r for r in part if not r["excluded"]]
        contexts = [r["context"] or {} for r in part]
        alone = [aislado[(r.get("bank"), r.get("case"))] for r in counted
                 if aislado and (r.get("bank"), r.get("case")) in aislado]
        stretches.append({
            "turnos": [begin, begin + tramo - 1], "ok": sum(r["ok"] for r in counted), "n": len(counted),
            "accuracy": round(sum(r["ok"] for r in counted) / len(counted), 4) if counted else None,
            "aislado": {"ok": sum(alone), "n": len(alone)} if aislado else None,
            "context_mean": {k: _mean([c.get(k) for c in contexts])
                             for k in ("total", "system", "catalog", "history", "tool_results", "otros")},
            "context_max": max((r["context_max"] for r in part if r["context_max"] is not None), default=None),
            "trimmed_turns_end": part[-1]["trimmed_turns"], "context_shrunk": sum(r["context_shrunk"] for r in part),
            "open_ask_before": sum(r["open_ask_before"] for r in part),
            "errors": sum(1 for r in part if r["error"]),
            "latency_p50": round(statistics.median(r["latency_s"] for r in part), 2)})
    categories: dict[str, list[int]] = {}
    for r in ordered:
        if not r["excluded"]:
            entry = categories.setdefault(str(r["category"]), [0, 0])
            entry[0] += r["ok"]
            entry[1] += 1
    counted = [r for r in ordered if not r["excluded"]]
    missing = sorted(set(range(1, max(by_n) + 1)) - set(by_n)) if by_n else []
    return {"turnos": len(ordered), "missing": missing, "ok": sum(r["ok"] for r in counted), "n": len(counted),
            "accuracy": round(sum(r["ok"] for r in counted) / max(1, len(counted)), 4),
            "n_ctx": next((r["n_ctx"] for r in ordered if r.get("n_ctx")), None),
            "categories": categories, "tramos": stretches}


def resumen_md(label: str, summary: dict) -> str:
    lines = [f"# Sesión larga {label}", "",
             f"{summary['turnos']} turnos; acierto {summary['ok']}/{summary['n']} ({summary['accuracy']:.0%}); "
             f"n_ctx {summary['n_ctx']}." + (f" Faltan los turnos {summary['missing']}." if summary["missing"] else ""),
             "", "| Turnos | Acierto | Aislado | Contexto medio | sistema | catálogo | historial | resultados | otros "
             "| Máximo | Turnos cortados | context_shrunk | Ask abierto | p50 s |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for s in summary["tramos"]:
        c = s["context_mean"]
        alone = f"{s['aislado']['ok']}/{s['aislado']['n']}" if s["aislado"] else "—"
        lines.append(f"| {s['turnos'][0]}-{s['turnos'][1]} | {s['ok']}/{s['n']} | {alone} | {c['total']} | "
                     f"{c['system']} | {c['catalog']} | {c['history']} | {c['tool_results']} | {c['otros']} | "
                     f"{s['context_max']} | {s['trimmed_turns_end']} | {s['context_shrunk']} | {s['open_ask_before']} "
                     f"| {s['latency_p50']} |")
    lines += ["", "| Categoría | Acierto |", "|---|---|"]
    lines += [f"| {name} | {ok}/{n} |" for name, (ok, n) in sorted(summary["categories"].items())]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="what", required=True)
    build = sub.add_parser("armar")
    build.add_argument("--out", required=True)
    build.add_argument("--turnos", type=int, default=50)
    build.add_argument("--semilla", type=int, default=0)
    build.add_argument("--fuente", action="append", help="NAME=FILE (default: v11, v6, feria, heldout)")
    build.add_argument("--catalog", default=r"F:\BAXYeval\renew_v6\catalog-final8c.json")
    build.add_argument("--corpus", default=str(ROOT / "documentacion" / "*.md"))
    run = sub.add_parser("correr")
    run.add_argument("label")
    run.add_argument("--sesion", required=True)
    run.add_argument("--desde", type=int, required=True)
    run.add_argument("--hasta", type=int, required=True)
    run.add_argument("--temp", default="0.2")
    run.add_argument("--gguf", default=os.environ.get("BAXY_MIND_LLM_GGUF", r"F:\BAXYeval\models\Qwen3.5-4B-Q4_K_M.gguf"))
    run.add_argument("--server", default=os.environ.get("BAXY_MIND_LLAMA_SERVER", r"F:\BAXYeval\llama\llama-server.exe"))
    run.add_argument("--server-args", default="")
    run.add_argument("--catalog", default=str(Path(os.environ.get("LOCALAPPDATA", "")) / "BAXY" / "renew"
                                              / "catalog.configure.json"))
    run.add_argument("--ctx", default="53248")
    run.add_argument("--src", default=str(ROOT / "src"))
    run.add_argument("--guardas", help="the App's guard oracle (bench_guardas): also judge the decision the person sees")
    report = sub.add_parser("resumir")
    report.add_argument("label")
    report.add_argument("--tramo", type=int, default=10)
    report.add_argument("--aislado", action="append", default=[], help="BANK=RUN: a bench_decision run (.jsonl) of that bank's cases")
    args = parser.parse_args()
    if args.what == "armar":
        pairs = dict(f.split("=", 1) for f in args.fuente) if args.fuente else SOURCES
        banks = {name: json.loads(Path(path).read_text(encoding="utf-8")) for name, path in pairs.items()}
        catalog = json.loads(Path(args.catalog).read_text(encoding="utf-8"))
        risk = {str(c.get("name")): str(c.get("risk") or "") for c in catalog.get("capabilities") or []}
        session = armar(banks, args.turnos, args.semilla, risk, chunks(sorted(glob.glob(args.corpus))))
        Path(args.out).write_text(json.dumps(session, ensure_ascii=False, indent=1), encoding="utf-8")
        counts: dict[str, int] = {}
        for turn in session["turnos"]:
            counts[turn["category"]] = counts.get(turn["category"], 0) + 1
        print(json.dumps({"turnos": len(session["turnos"]), "categorias": counts,
                          "lecturas": len(session["lecturas"])}, ensure_ascii=False))
    elif args.what == "correr":
        correr(args)
    else:
        runs = BANKS / "runs"
        rows, sessions = [], set()
        # Oldest first: a turn run again in a later tanda is the later one (resumir keeps the last row of a turn).
        for path in sorted(runs.glob(f"{args.label}-t[0-9][0-9]-[0-9][0-9].jsonl"), key=lambda p: p.stat().st_mtime):
            lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
            sessions.add(json.loads(lines[0])["summary"]["sesion"])
            rows += [json.loads(line) for line in lines[1:]]
        if len(sessions) > 1:
            raise SystemExit(f"the tandas of {args.label} ran different sessions: {sorted(sessions)}")
        aislado = {}
        for pair in args.aislado:
            bank, path = pair.split("=", 1)
            for line in Path(path).read_text(encoding="utf-8").splitlines()[1:]:
                row = json.loads(line)
                if not row.get("excluded"):
                    aislado[(bank, row["id"])] = bool(row["ok"])
        summary = {"label": args.label, **resumir(rows, args.tramo, aislado or None)}
        (runs / f"{args.label}.resumen.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1),
                                                         encoding="utf-8")
        (runs / f"{args.label}.resumen.md").write_text(resumen_md(args.label, summary), encoding="utf-8")
        print(resumen_md(args.label, summary))


if __name__ == "__main__":
    main()
