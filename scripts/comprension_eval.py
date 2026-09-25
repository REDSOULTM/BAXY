"""Decision-only scorer for the comprensión sets (DEV-A, DEV-B, FINAL): Fase 3.5b, 2026-09-25.

A set is JSONL, one row per turn:
  {"id", "set", "kind": "single"|"conv", "conv", "turn", "source", "text", "history": [{"role", "content"}...],
   "pending": str|null, "dep": bool, "gold": [labels], "args": {label: [[alternatives]...]}}
Gold labels: ``op:<operation>`` (``*`` suffix = prefix), ``plan:<a>+<b>`` (all present), ``web`` (web.search,
weather.current or web.news.headlines), ``talk`` (conversation that is not a limit), ``limit`` (conversation that
states a limit), ``ask`` (clarification). ``args`` (optional): for a label, groups of accepted spellings; one of each
group must appear in the folded arguments the mind grounds for that operation.

  run    each turn through the product mind's ``turn.decide`` with its fixed history (nothing executes); for an
         action whose gold carries ``args``, the mind's ``arguments`` step too. Resumes by id.
  score  accuracy (all, singles, conversation turns, follow-ups that depend on the previous turn), by source and
         by decision path (``--audit``: the mind's turn audit); ``--blind`` prints aggregates only (DEV-B, FINAL).

usage:
  comprension_eval.py run --set S.jsonl --out RUN.jsonl [--audit AUDIT.jsonl] [--src DIR] [--limit N]
  comprension_eval.py score --set S.jsonl --run RUN.jsonl [--audit AUDIT.jsonl] [--base RUN0.jsonl] [--blind]
                            [--json SUMMARY.json]
"""

from __future__ import annotations

import argparse
import json
import math
import os
import pathlib
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from typing import Any

SCRIPTS = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

WEB_OPS = {"web.search", "weather.current", "web.news.headlines"}
LIMIT_KINDS = {"unsupported", "unsupported_language"}
EVIDENCE_TIMEOUT_S = 600.0
DECIDE_TIMEOUT_S = 120.0


def fold(text: object) -> str:
    text = unicodedata.normalize("NFKD", str(text).casefold())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def read_jsonl(path: pathlib.Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


# ------------------------------------------------------------------------------------------------ verdict


def operations(record: dict[str, Any]) -> set[str]:
    ops = set(record.get("effects") or [])
    if record.get("operation"):
        ops.add(record["operation"])
    return ops


def empty_fallback(record: dict[str, Any]) -> bool:
    return record.get("recovery") == "protocol_fallback" and not (
        record.get("reply") or record.get("question")
    )


def label_matches(label: str, record: dict[str, Any]) -> list[str]:
    """The operations that satisfy ``label`` (``[""]`` for a non-operation label); empty when it does not hold."""
    kind = record.get("kind")
    ops = operations(record) if kind in {"action", "plan"} else set()
    if label == "ask":
        return [""] if kind == "clarify" else []
    if label == "talk":
        ok = (
            kind == "conversation"
            and record.get("conversation_kind") not in LIMIT_KINDS
            and not empty_fallback(record)
        )
        return [""] if ok else []
    if label == "limit":
        return (
            [""]
            if kind == "conversation" and record.get("conversation_kind") in LIMIT_KINDS
            else []
        )
    if label == "web":
        return sorted(ops & WEB_OPS)
    if label.startswith("plan:"):
        wanted = set(label[5:].split("+"))
        return sorted(wanted) if wanted <= ops else []
    if label.startswith("op:"):
        name = label[3:]
        if name.endswith("*"):
            return sorted(op for op in ops if op.startswith(name[:-1]))
        return [name] if name in ops else []
    raise ValueError(f"etiqueta de oro desconocida: {label}")


def args_hold(groups: list[list[str]], arguments: dict[str, Any] | None) -> bool:
    if not arguments:
        return False
    haystack = fold(json.dumps(arguments, ensure_ascii=False))
    return all(
        any(fold(alternative) in haystack for alternative in group) for group in groups
    )


def verdict(row: dict[str, Any], record: dict[str, Any]) -> tuple[bool, bool]:
    """(decision right, decision and key arguments right)."""
    if not record or "error" in record:
        return False, False
    decided = False
    for label in row["gold"]:
        matched = label_matches(label, record)
        if not matched:
            continue
        decided = True
        groups = (row.get("args") or {}).get(label)
        if not groups:
            return True, True
        grounded = record.get("arguments") or {}
        if any(args_hold(groups, grounded.get(op)) for op in matched):
            return True, True
    return decided, False


def self_test() -> None:
    action = {
        "kind": "action",
        "operation": "weather.current",
        "effects": ["weather.current"],
        "arguments": {"weather.current": {"location": "Santiago"}},
    }
    assert verdict({"gold": ["op:weather.current"]}, action) == (True, True)
    assert verdict({"gold": ["web"], "args": {"web": [["santiago"]]}}, action) == (
        True,
        True,
    )
    assert verdict(
        {"gold": ["op:weather.current"], "args": {"op:weather.current": [["rosario"]]}},
        action,
    ) == (True, False)
    assert verdict(
        {"gold": ["op:media.play*"]},
        {"kind": "action", "effects": ["media.play.youtube"]},
    ) == (True, True)
    assert verdict(
        {"gold": ["plan:app.open+media.play.query"]},
        {"kind": "plan", "effects": ["app.open", "media.play.query"]},
    ) == (True, True)
    assert verdict(
        {"gold": ["talk"]}, {"kind": "conversation", "conversation_kind": "unsupported"}
    ) == (False, False)
    assert verdict(
        {"gold": ["limit"]},
        {"kind": "conversation", "conversation_kind": "unsupported"},
    ) == (True, True)
    assert verdict(
        {"gold": ["talk"]},
        {"kind": "conversation", "recovery": "protocol_fallback", "reply": ""},
    ) == (False, False)
    assert verdict({"gold": ["ask"]}, {"kind": "clarify"}) == (True, True)
    assert verdict({"gold": ["ask"]}, {"error": "timeout"}) == (False, False)


# ------------------------------------------------------------------------------------------------ run


def _await(
    client, message: dict[str, Any], expected: str, timeout: float
) -> dict[str, Any]:
    """Send one request; the early ``turn.signal`` the mind may emit is not the answer."""
    client._process.stdin.write(
        json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n"
    )
    client._process.stdin.flush()
    deadline = time.monotonic() + timeout
    while True:
        reply = client._next(max(0.1, deadline - time.monotonic()))
        if reply.get("id") != message["id"] or reply.get("type") == "turn.signal":
            continue
        if reply.get("type") != expected:
            raise RuntimeError(
                f"{reply.get('type')}: {reply.get('code') or ''} {reply.get('message') or ''}"
            )
        return reply


def run(
    set_path: pathlib.Path,
    out: pathlib.Path,
    audit: pathlib.Path | None,
    src: pathlib.Path | None,
    limit: int | None,
) -> None:
    import run_turn_policy_gate as gate

    if src is not None:
        gate.SRC = src.resolve()
    rows = read_jsonl(set_path)[: limit or None]
    done = {record["id"] for record in read_jsonl(out) if "error" not in record}
    manifest = gate.read_runtime_manifest(
        pathlib.Path(os.environ["LOCALAPPDATA"])
        / "BAXYRuntime"
        / "mind-runtime-v1.json"
    )
    configuration = gate.core_catalog_configuration(gate.DEFAULT_CORE)
    overrides = {"BAXY_MIND_TURN_AUDIT_PATH": str(audit)} if audit else {}
    with gate.MindClient(
        configuration["capabilities"],
        application_catalog=configuration["applicationCatalog"],
        game_catalog=configuration["gameCatalog"],
        gguf=pathlib.Path(manifest["gguf"]),
        llama_server=pathlib.Path(manifest["llama_server"]),
        ngl=int(manifest.get("ngl") or 99),
        endpoint=None,
        environment_overrides=overrides,
        startup_timeout=300.0,
    ) as client:
        deadline = time.monotonic() + EVIDENCE_TIMEOUT_S
        while time.monotonic() < deadline:
            status = _await(
                client,
                {
                    "type": "turn.evidence.status",
                    "id": f"cn-evidence-{time.monotonic_ns()}",
                },
                "turn.evidence.status.result",
                30.0,
            )
            if status.get("state") in {"ready", "unavailable", "failed", "stopped"}:
                break
            time.sleep(1.0)
        _await(
            client,
            {
                "type": "turn.decide",
                "id": "cn-warmup",
                "text": "Hola",
                "history": [],
                "pendingClarification": False,
                "uiLanguage": "es",
            },
            "turn.result",
            DECIDE_TIMEOUT_S,
        )
        for row in rows:
            if row["id"] in done:
                continue
            history = row.get("history") or []
            message = {
                "type": "turn.decide",
                "id": f"cn-{row['id']}",
                "text": row["text"],
                "history": [*history, {"role": "user", "content": row["text"]}]
                if history
                else [],
                "pendingClarification": False,
                "uiLanguage": "es",
            }
            if row.get("pending"):
                message["pendingObjective"] = row["pending"]
            record: dict[str, Any] = {"id": row["id"]}
            started = time.perf_counter()
            try:
                reply = _await(client, message, "turn.result", DECIDE_TIMEOUT_S)
                record.update(
                    {
                        "kind": reply.get("kind"),
                        "operation": reply.get("operation"),
                        "effects": sorted(reply.get("effectOperations") or []),
                        "intent": sorted(reply.get("intentOperations") or []),
                        "conversation_kind": reply.get("conversationKind"),
                        "objective": reply.get("objective"),
                        "recovery": reply.get("turn_recovery"),
                        "question": str(reply.get("question") or "")[:400],
                        "reply": str(reply.get("reply") or "")[:400],
                    }
                )
                record["latency_s"] = round(time.perf_counter() - started, 2)
                wanted = {label for label in (row.get("args") or {})}
                if wanted and record["kind"] in {"action", "plan"}:
                    record["arguments"] = {}
                    for op in sorted(operations(record)):
                        if not any(
                            label_matches(label, {"kind": "action", "effects": [op]})
                            for label in wanted
                        ):
                            continue
                        grounded = _await(
                            client,
                            {
                                "type": "arguments",
                                "id": f"cn-args-{row['id']}-{op}",
                                "operation": op,
                                "text": record["objective"] or row["text"],
                                "history": history,
                            },
                            "arguments.result",
                            60.0,
                        )
                        record["arguments"][op] = grounded.get("arguments") or {}
                        if grounded.get("question"):
                            record.setdefault("argument_questions", {})[op] = str(
                                grounded["question"]
                            )[:200]
            except Exception as error:  # noqa: BLE001 - a failed turn is a measured failure
                record["error"] = f"{type(error).__name__}: {error}"[:400]
                record["latency_s"] = round(time.perf_counter() - started, 2)
            with out.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            print(
                f"{row['id']} {record.get('kind')} {record.get('operation') or ''} {record['latency_s']}s",
                flush=True,
            )


# ------------------------------------------------------------------------------------------------ score


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(math.floor(q * len(ordered))))]


def mcnemar_exact(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, k) for k in range(0, min(b, c) + 1)) / 2**n
    return min(1.0, 2 * tail)


def decision_paths(audit: pathlib.Path | None) -> dict[str, str]:
    paths: dict[str, str] = {}
    for record in read_jsonl(audit) if audit else []:
        if record.get("phase") == "final" and str(
            record.get("request_id", "")
        ).startswith("cn-"):
            paths[record["request_id"][3:]] = str(record.get("decision_path"))
    return paths


def got(record: dict[str, Any]) -> str:
    if "error" in record:
        return "error"
    ops = sorted(operations(record))
    if ops:
        return f"{record.get('kind')}:" + "+".join(ops)
    if record.get("kind") == "conversation":
        return "conversation:" + str(
            record.get("conversation_kind")
            or ("EMPTY" if empty_fallback(record) else "-")
        )
    return str(record.get("kind"))


def score(
    set_path: pathlib.Path,
    run_path: pathlib.Path,
    audit: pathlib.Path | None,
    base: pathlib.Path | None,
    blind: bool,
    summary_path: pathlib.Path | None,
) -> None:
    rows = read_jsonl(set_path)
    records = {record["id"]: record for record in read_jsonl(run_path)}
    base_records = {record["id"]: record for record in read_jsonl(base)} if base else {}
    paths = decision_paths(audit)
    judged = [row for row in rows if row["id"] in records]
    results = {row["id"]: verdict(row, records[row["id"]]) for row in judged}

    def share(subset: list[dict[str, Any]], strict: bool = True) -> tuple[int, int]:
        return sum(results[row["id"]][1 if strict else 0] for row in subset), len(
            subset
        )

    groups = {
        "total": judged,
        "sueltos": [row for row in judged if row["kind"] == "single"],
        "conversación": [row for row in judged if row["kind"] == "conv"],
        "seguimientos": [
            row for row in judged if row["kind"] == "conv" and row.get("dep")
        ],
    }
    summary: dict[str, Any] = {
        "set": set_path.name,
        "rows": len(rows),
        "judged": len(judged),
        "errors": sum(1 for row in judged if "error" in records[row["id"]]),
    }
    lines = [
        f"{set_path.name}: {len(judged)}/{len(rows)} turnos puntuados, errores de réplica {summary['errors']}"
    ]
    for name, subset in groups.items():
        right, count = share(subset)
        decided, _ = share(subset, strict=False)
        summary[name] = {"right": right, "n": count, "decision_only": decided}
        pct = 100 * right / count if count else 0.0
        lines.append(
            f"  {name:13} {right}/{count} = {pct:.1f} %   (sólo decisión {decided}/{count})"
        )
    latencies = [records[row["id"]].get("latency_s", 0.0) for row in judged]
    summary["latency_p50"], summary["latency_p90"] = (
        percentile(latencies, 0.5),
        percentile(latencies, 0.9),
    )
    lines.append(
        f"  latencia de decisión p50 {summary['latency_p50']} s, p90 {summary['latency_p90']} s"
    )
    by_source: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for row in judged:
        by_source[row["source"]][0] += results[row["id"]][1]
        by_source[row["source"]][1] += 1
    summary["by_source"] = {k: v for k, v in sorted(by_source.items())}
    lines.append(
        "  por fuente: "
        + " · ".join(f"{k} {a}/{n}" for k, (a, n) in sorted(by_source.items()))
    )
    if paths:
        by_path: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        for row in judged:
            path = paths.get(row["id"], "?")
            by_path[path][0] += results[row["id"]][1]
            by_path[path][1] += 1
        summary["by_path"] = dict(by_path)
        lines.append(
            "  por camino: "
            + " · ".join(f"{k} {a}/{n}" for k, (a, n) in sorted(by_path.items()))
        )
    if base_records:
        fixed = broken = 0
        broken_rows = []
        for row in judged:
            if row["id"] not in base_records:
                continue
            before = verdict(row, base_records[row["id"]])[1]
            now = results[row["id"]][1]
            fixed += now and not before
            broken += before and not now
            if before and not now:
                broken_rows.append(row)
        summary["vs_base"] = {
            "fixed": fixed,
            "broken": broken,
            "mcnemar_p": round(mcnemar_exact(fixed, broken), 4),
        }
        lines.append(
            f"  contra la base: arreglados {fixed}, rotos {broken}, McNemar p = {summary['vs_base']['mcnemar_p']}"
        )
        if not blind:
            for row in broken_rows:
                lines.append(
                    f"    ROTO {row['id']} {row['gold']} -> {got(records[row['id']])} | {row['text'][:90]}"
                )
    if not blind:
        misses = Counter(
            (row["gold"][0], got(records[row["id"]]))
            for row in judged
            if not results[row["id"]][1]
        )
        lines.append(
            "  fallos (oro principal, obtenido): "
            + ", ".join(f"{k}×{v}" for k, v in misses.most_common(30))
        )
        for row in judged:
            if not results[row["id"]][1]:
                record = records[row["id"]]
                said = (
                    record.get("question")
                    or record.get("reply")
                    or record.get("error")
                    or ""
                )[:100]
                lines.append(
                    f"  NO {row['id']} [{paths.get(row['id'], '?')}] {row['gold']} -> {got(record)} "
                    f"| {row['text'][:100]} || {said}"
                )
    print("\n".join(lines))
    if summary_path:
        summary_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8"
        )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)
    runner = sub.add_parser("run")
    runner.add_argument("--set", required=True, type=pathlib.Path)
    runner.add_argument("--out", required=True, type=pathlib.Path)
    runner.add_argument("--audit", type=pathlib.Path)
    runner.add_argument(
        "--src",
        type=pathlib.Path,
        help="mind sources to run (a worktree of another commit)",
    )
    runner.add_argument("--limit", type=int)
    scorer = sub.add_parser("score")
    scorer.add_argument("--set", required=True, type=pathlib.Path)
    scorer.add_argument("--run", required=True, type=pathlib.Path)
    scorer.add_argument("--audit", type=pathlib.Path)
    scorer.add_argument("--base", type=pathlib.Path)
    scorer.add_argument("--blind", action="store_true")
    scorer.add_argument("--json", type=pathlib.Path)
    sub.add_parser("selftest")
    args = parser.parse_args(argv)
    if args.command == "run":
        run(args.set, args.out, args.audit, args.src, args.limit)
    elif args.command == "score":
        score(args.set, args.run, args.audit, args.base, args.blind, args.json)
    else:
        self_test()
        print("selftest ok")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
