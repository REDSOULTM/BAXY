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
         D61 (owner, 2026-10-02), only when asked, after the gold's own figures: ``--accept FILE`` also counts the
         alternative decisions FILE accepts per id; ``--d35`` also counts a recipe or figure looked up first (the
         audit's ``reference_looked_up`` stage, joined through the shell trace for a window run) where the gold talks.

usage:
  comprension_eval.py run --set S.jsonl --out RUN.jsonl [--audit AUDIT.jsonl] [--src DIR] [--limit N]
                          [--gguf G.gguf] [--ctx 12288] [--decider-adapter A.gguf]
  comprension_eval.py score --set S.jsonl --run RUN.jsonl [--audit AUDIT.jsonl] [--base RUN0.jsonl] [--blind]
                            [--json SUMMARY.json] [--accept ACCEPT.jsonl] [--d35]
"""

from __future__ import annotations

import argparse
import json
import math
import os
import pathlib
import re
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from typing import Any

SCRIPTS = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

WEB_OPS = {"web.search", "weather.current", "web.news.headlines"}
LIMIT_KINDS = {"unsupported", "unsupported_language"}
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


def asked_only(record: dict[str, Any]) -> bool:
    """D73 (DEV-I v4u I-s057 «ponme un recordatorio para mañana, lo de pagar la cuenta de la luz» → «¿A qué hora…?»):
    an action whose missing value BAXY asked for, and nothing else, was published as a clarification — every BAXY
    route of the turn is one. The person saw a question, which is what a gold ``ask`` accepts (counted with D61)."""

    routes = record.get("routes") or []
    return bool(routes) and all(route == "clarification" for route in routes)


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


def args_hold(groups: list[list[str]], arguments: dict[str, Any] | None, *, equivalent: bool = False) -> bool:
    if not arguments:
        return False
    haystack = fold(json.dumps(arguments, ensure_ascii=False))
    if equivalent:
        haystack = equivalent_forms(haystack)
    return all(
        any(fold(alternative) in haystack for alternative in group) for group in groups
    )


# D71 (owner, 2026-10-03): a turn is complete when BAXY did what was asked, even when the datum is said another way. Form
# only, never another result: a hyphen between word parts is a space («25-minute» = «25 minute»), and a spoken length is
# also its number of minutes and seconds («media hora» = 30 min = 1800).
_SPOKEN_LENGTHS = (
    (r"\bhora y media\b|\ban hour and a half\b|\bone and a half hours?\b|\b1\.5 hours?\b", 90),
    (r"\btres cuartos de hora\b|\bthree quarters of an hour\b", 45),
    (r"\bmedia hora\b|\bhalf an hour\b|\bhalf hour\b", 30),
    (r"\bun cuarto de hora\b|\ba quarter of an hour\b|\bquarter hour\b", 15),
    (r"\buna hora\b|\ban hour\b|\bone hour\b", 60),
)


def equivalent_forms(haystack: str) -> str:
    """``haystack`` with the forms D71 counts as the same datum appended (see above)."""
    extra = [re.sub(r"(?<=\w)-(?=\w)", " ", haystack)]
    for pattern, minutes in _SPOKEN_LENGTHS:
        if re.search(pattern, haystack):
            extra.append(f"{minutes} min {minutes} minutos {minutes} minutes {minutes * 60}")
    return " | ".join([haystack, *extra])


def verdict_equivalent(row: dict[str, Any], record: dict[str, Any]) -> tuple[bool, bool]:
    """``verdict`` with D71's equivalent forms of the arguments (the decision is judged the same)."""
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
        if any(args_hold(groups, grounded.get(op), equivalent=True) for op in matched):
            return True, True
    return decided, False


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
    gguf: pathlib.Path | None = None,
    context: int | None = None,
    decider_adapter: pathlib.Path | None = None,
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
    if context:
        # The gate pins 4 096 per slot; a candidate profile measures its own.
        overrides["BAXY_MIND_CTX"] = str(context)
    base = gguf or pathlib.Path(manifest["gguf"])
    if decider_adapter:
        overrides.update(gate.decider_adapter_environment(decider_adapter, base))
    with gate.MindClient(
        configuration["capabilities"],
        application_catalog=configuration["applicationCatalog"],
        game_catalog=configuration["gameCatalog"],
        gguf=base,
        llama_server=pathlib.Path(manifest["llama_server"]),
        ngl=int(manifest.get("ngl") or 99),
        endpoint=None,
        environment_overrides=overrides,
        startup_timeout=300.0,
    ) as client:
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


def read_accepted(path: pathlib.Path) -> dict[str, dict[str, Any]]:
    """D61: ``{"id", "accept": [labels], "reason"}`` per line — decisions the owner accepts besides the set's gold."""
    accepted: dict[str, dict[str, Any]] = {}
    for row in read_jsonl(path):
        labels = row.get("accept")
        if not row.get("id") or not isinstance(labels, list) or not labels or not str(row.get("reason") or "").strip():
            raise ValueError(f"{path.name}: cada fila lleva id, accept (etiquetas) y reason: {row}")
        for label in labels:
            label_matches(label, {})  # an unknown label fails here, not while scoring
        accepted[row["id"]] = row
    return accepted


def reference_lookups(run_path: pathlib.Path, audit: pathlib.Path | None) -> set[str]:
    """D61 (D35): the ids whose final turn audit carries the ``reference_looked_up`` stage — a recipe, a work or a
    figure the mind looked up first (``__main__``: M53 on the decider's «talk» and on an explicit knowledge
    conversation); a company's analysis (D59.8, kind ``analysis``) is not D35.

    A ``run`` record is the audit's ``cn-<id>``; a window record (``comprension_window.py records``) is joined through
    the shell trace next to the run, as ``records`` does. Only the audit is read, never a text."""
    audit = audit or run_path.parent / "turn-audit.jsonl"
    if not audit.is_file():
        raise FileNotFoundError(f"--d35 necesita la auditoría de turnos: {audit}")
    import comprension_window as window  # noqa: PLC0415 — it imports this module

    finals = window.audit_finals(window.read_capture(audit))
    trace = run_path.parent / "shell-trace.jsonl"
    segments = window.trace_segments(window.read_capture(trace)) if trace.is_file() else {}
    found: set[str] = set()
    for record in read_jsonl(run_path):
        segment = segments.get(str(record.get("turn_id")))
        candidates = [f"cn-{record['id']}"] + list(reversed(segment["decides"] if segment else []))
        final = next((finals[request] for request in candidates if request in finals), None)
        if final is not None and any(
            isinstance(stage, dict)
            and stage.get("name") == "reference_looked_up"
            # A real company's analysis is looked up by D59.8, not by D35 (recipes, works, figures, dated facts).
            and stage.get("kind") != "analysis"
            for stage in final.get("stages") or []
        ):
            found.add(record["id"])
    return found


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


def _d61_lines(
    judged: list[dict[str, Any]],
    records: dict[str, dict[str, Any]],
    results: dict[str, tuple[bool, bool]],
    groups: dict[str, list[dict[str, Any]]],
    accept: pathlib.Path | None,
    d35: bool,
    run_path: pathlib.Path,
    audit: pathlib.Path | None,
    blind: bool,
    summary: dict[str, Any],
) -> list[str]:
    """D61 (owner, 2026-10-02): the same turns scored again with what the owner also accepts — the alternative
    decisions of ``--accept`` and, with ``--d35``, a recipe or a figure looked up first where the gold talks. The
    figures above stay the set's own gold; these follow them."""
    accepted = read_accepted(accept) if accept is not None else {}
    looked_up = reference_lookups(run_path, audit) if d35 else set()
    cause: dict[str, str] = {}
    alternative: dict[str, tuple[bool, bool]] = {}
    for row in judged:
        record = records[row["id"]]
        decided, right = results[row["id"]]
        if not right and row["id"] in accepted and verdict({"gold": accepted[row["id"]]["accept"]}, record)[1]:
            decided, right = True, True
            cause[row["id"]] = "aceptada"
        if not right and "ask" in row["gold"] and asked_only(record):
            # D73: the question the gold accepts, asked from an action short of a value.
            decided, right = True, True
            cause[row["id"]] = "D73"
        if not right and verdict_equivalent(row, record)[1]:
            # D71 (owner, 2026-10-03): the datum done, said another way.
            decided, right = True, True
            cause[row["id"]] = "D71"
        if (
            not right
            and "error" not in record
            and row["id"] in looked_up
            and "talk" in row["gold"]
            and "web.search" in operations(record)
            and record.get("kind") in {"action", "plan"}
        ):
            decided, right = True, True
            cause[row["id"]] = "D35"
        alternative[row["id"]] = (decided, right)
    sources = " + ".join(
        part for part in (f"aceptadas de {accept.name}" if accept is not None else "", "D35 buscar primero" if d35 else "")
        if part
    )
    counts = Counter(cause.values())
    lines = [
        f"  con D61 ({sources}): +{len(cause)} turnos (aceptadas {counts['aceptada']}, D35 {counts['D35']}; "
        f"D71 mismo dato dicho de otra forma {counts['D71']}; D73 preguntó lo que el oro acepta {counts['D73']}; "
        f"turnos con consulta D35 en la auditoría {len(looked_up & set(records))})"
    ]
    summary["d61"] = {"accepted": counts["aceptada"], "d35": counts["D35"], "d71": counts["D71"], "d73": counts["D73"],
                      "d35_lookups": len(looked_up & set(records))}
    for name, subset in groups.items():
        right = sum(alternative[row["id"]][1] for row in subset)
        decided = sum(alternative[row["id"]][0] for row in subset)
        summary["d61"][name] = {"right": right, "n": len(subset), "decision_only": decided}
        pct = 100 * right / len(subset) if subset else 0.0
        lines.append(f"    {name:13} {right}/{len(subset)} = {pct:.1f} %   (sólo decisión {decided}/{len(subset)})")
    if not blind:
        for row in judged:
            if row["id"] in cause:
                lines.append(
                    f"    D61 {row['id']} [{cause[row['id']]}] {row['gold']} -> {got(records[row['id']])} | {row['text'][:90]}"
                )
    return lines


def score(
    set_path: pathlib.Path,
    run_path: pathlib.Path,
    audit: pathlib.Path | None,
    base: pathlib.Path | None,
    blind: bool,
    summary_path: pathlib.Path | None,
    accept: pathlib.Path | None = None,
    d35: bool = False,
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
    if accept is not None or d35:
        lines.extend(_d61_lines(judged, records, results, groups, accept, d35, run_path, audit, blind, summary))
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
    runner.add_argument(
        "--gguf", type=pathlib.Path, help="another GGUF than the runtime manifest's"
    )
    runner.add_argument(
        "--ctx", type=int, help="context per server slot (BAXY_MIND_CTX)"
    )
    runner.add_argument(
        "--decider-adapter", type=pathlib.Path, help="the decider's LoRA GGUF over the base GGUF"
    )
    scorer = sub.add_parser("score")
    scorer.add_argument("--set", required=True, type=pathlib.Path)
    scorer.add_argument("--run", required=True, type=pathlib.Path)
    scorer.add_argument("--audit", type=pathlib.Path)
    scorer.add_argument("--base", type=pathlib.Path)
    scorer.add_argument("--blind", action="store_true")
    scorer.add_argument("--json", type=pathlib.Path)
    scorer.add_argument(
        "--accept", type=pathlib.Path,
        help="D61: JSONL {id, accept: [labels], reason} — decisions the owner also accepts; scored after the gold's figures",
    )
    scorer.add_argument(
        "--d35", action="store_true",
        help="D61: a recipe or figure looked up first (audit stage reference_looked_up) where the gold talks also counts",
    )
    sub.add_parser("selftest")
    args = parser.parse_args(argv)
    if args.command == "run":
        run(args.set, args.out, args.audit, args.src, args.limit, args.gguf, args.ctx, args.decider_adapter)
    elif args.command == "score":
        score(args.set, args.run, args.audit, args.base, args.blind, args.json, args.accept, args.d35)
    else:
        self_test()
        print("selftest ok")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
