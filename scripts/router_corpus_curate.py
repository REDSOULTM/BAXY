"""Curate the router-eval corpus into a CLEAN, fully-labeled ground truth.

Operator's instruction (2026-05-20): NO automatic oracle — an embedding/
keyword classifier corrupted good labels. **Opus 4.7 is the oracle**; the
labels live in scripts/router_corpus_labels.py, hand-authored after reading
the actual prompts. This script just applies them:

  1. NORMALIZE existing curated labels (legacy/dotted names → the 65
     compound tools) and TRUST them — never overwrite a human-curated tool
     label with a guess.
  2. For prompts that arrived with NO usable label (organic logs, voice
     traces) or a non-tool meta marker ("según tarea", "confirmable",
     "policy"), apply MY label from router_corpus_labels.label_for().
  3. Anything still unmatched is reported so I can add it to OVERRIDES —
     the corpus is only "done" when every row has a coherent label.

Output: gemma4_agent/data/router_eval_corpus.curated.jsonl  (a SEPARATE
file — never overwrites the shared router_eval_corpus.jsonl another agent
owns). Each row:
  {"q", "expected": ["tool", ...], "source", "label_origin", "raw"?, "prev"?}
where "prev" is the previous user turn (conversational context) when known —
the runtime router has this, so the harness can route continuations
("ciérralo", "haz lo mismo") the way they're actually routed instead of
scoring them context-free.

Run:
    python scripts/router_corpus_curate.py            # write curated file
    python scripts/router_corpus_curate.py --audit    # report only
    python scripts/router_corpus_curate.py --unmatched # list prompts I still
                                                       # need to label by hand
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

IMPORT_DIR = ROOT / "gemma4_agent" / "data" / "carter_import"
OUT = ROOT / "gemma4_agent" / "data" / "router_eval_corpus.curated.jsonl"


def _valid_tools() -> set[str]:
    from gemma4_agent.tool_schemas import COMPOUND_TOOL_SCHEMAS as S
    return {sch.get("function", {}).get("name", "") for sch in S} - {""}


VALID = _valid_tools()

# legacy/dotted bench names → compound tools (normalization only; we never
# invent a label here, just translate one that already exists).
LEGACY_NORM: dict[str, set[str]] = {
    "apps": {"app"}, "apps.open": {"app"}, "apps.close": {"app"},
    "app_open": {"app"}, "app_close": {"app"}, "app_resolver": {"app"},
    "active_window": {"window"}, "window_close": {"window"},
    "window_manage": {"window"}, "window_list": {"window"},
    "window_focus": {"window"}, "window.focus": {"window"},
    "window.list": {"window"}, "window.close": {"window"},
    "window_check": {"window", "verify"}, "process": {"system", "window"},
    "process_list": {"system", "window"}, "process_check": {"system", "verify"},
    "system.processes": {"system"}, "system_get_time": {"system"},
    "web_search": {"web"}, "web.search": {"web"}, "web_open_url": {"web", "browser"},
    "web.open_url": {"web", "browser"}, "browser.open_url": {"browser", "web"},
    "search": {"web"}, "default_browser": {"browser"},
    "files": {"filesystem"}, "files.read": {"filesystem"}, "files.search": {"filesystem"},
    "files.open": {"filesystem"}, "files.list": {"filesystem"}, "files.copy": {"filesystem"},
    "files.write": {"filesystem"}, "files.create_dir": {"filesystem"},
    "filesystem_list": {"filesystem"}, "filesystem_read": {"filesystem"},
    "terminal_run": {"terminal"}, "terminal.safe": {"terminal"}, "read": {"filesystem"},
    "zip": {"backup_sync", "filesystem"},
    "memory_recall": {"memory"}, "memory_save": {"memory"}, "memory.write": {"memory"},
    "memory.read": {"memory"}, "memory.delete": {"memory"}, "memory_write": {"memory"},
    "memory_read": {"memory"}, "memory_delete": {"memory"},
    "clock": {"system"}, "system.time": {"system"}, "time": {"system"},
    "system.audio": {"audio"}, "audio.read": {"audio"}, "audio.set": {"audio"},
    "audio.mute": {"audio"}, "media_volume": {"audio"}, "media_mute": {"audio"},
    "settings": {"device_settings", "system"}, "system.display": {"device_settings"},
    "system.settings": {"device_settings"}, "system.network": {"device_settings"},
    "system.power": {"system"}, "display": {"device_settings"},
    "steam_search": {"steam"}, "steam_run": {"steam"}, "screenshot": {"gui", "vision"},
    "vision_ocr": {"vision"}, "input.key": {"input"}, "input.hotkey": {"input"},
}

NONE_MARKERS = ("ninguna", "ningun", "none", "-", "n/a", "na")
# non-tool annotations: the cell is NOT a tool → label is unknown, defer to
# the hand-authored rules.
META_MARKERS = (
    "segun", "según", "confirmable", "confirmacion", "confirmación", "critica",
    "crítica", "policy", "control", "seguridad", "opcional", "context",
    "contexto", "trace", "verifier", "config", "runtime", "log", "pendiente",
    "tarea", "aclaracion", "aclaración", "local", "minima", "mínima", "default",
    "calculator", "calculadora", "llm", "model", "preload", "telemetry",
    "rollback", "screen recording", "recording", "camera", "mic", "installer",
    "display tool", "keyboard language", "context guard", "context only",
    "context reset", "policy block", "policy/confirmable", "policy/context",
    "policy/config", "según error", "según contexto", "según prompt",
    "según pendiente",
)


def normalize_label(cell: str) -> tuple[set[str] | None, str]:
    """(toolset, kind). kind ∈ {'none','tools','meta'}."""
    if not cell:
        return None, "meta"
    low = cell.strip().lower()
    if any(low == m or low.startswith(m) for m in NONE_MARKERS):
        return set(), "none"
    tools: set[str] = set()
    for tok in re.split(r"[\s/,]+", low):
        tok = tok.strip()
        if not tok:
            continue
        if tok in LEGACY_NORM:
            tools |= LEGACY_NORM[tok]
        elif tok in VALID:
            tools.add(tok)
    if tools:
        return tools, "tools"
    return None, "meta"


def _load_corpus_rows() -> list[dict]:
    import scripts.router_corpus_build as b
    rows: dict[str, dict] = {}

    def put(q: str, src: str, raw_tools: str | None, prev: str | None = None) -> None:
        if b._NOISE.search(q) or len(q) < 2:
            return
        r = rows.get(q)
        if r is None:
            rows[q] = {"q": q, "source": src, "raw": raw_tools, "prev": prev}
        else:
            if not r.get("raw") and raw_tools:
                r["raw"] = raw_tools
                r["source"] = src
            # keep the first non-empty conversational context we see.
            if not r.get("prev") and prev:
                r["prev"] = prev

    for src in [ROOT / "gemma4_agent" / "data" / "traces.jsonl", *sorted(ROOT.glob("traces_*.txt"))]:
        if src.exists():
            for q, prev in b._user_turns_from_jsonl(src):
                put(q, src.name, None, prev)
    for prompt, tools, prev in b._carter540_cases(ROOT / "Testing Inicial" / "harness_carter540" / "tests_540.md"):
        put(prompt, "tests_540.md", tools or None, prev)
    guides = [
        ("Carter_v3_GUIA_OFICIAL_TESTING.md", 3, 5),
        ("Carter_v2_Matriz_Pruebas.md", 2, 4),
        ("Carter_v3_MINIMUM_TESTING.md", 2, None),
    ]
    for name, pcol, tcol in guides:
        for prompt, tools, prev in b._md_table_cases(IMPORT_DIR / name, prompt_col=pcol, tools_col=tcol):
            put(prompt, f"carter:{name}", tools or None, prev)
    for runp in sorted(IMPORT_DIR.glob("full_18x30_true_ready*.json")):
        for prompt, used in b._carter_run_json(runp):
            put(prompt, f"carter_run:{runp.name}", used or "ninguna")
    for q, prev in b._carter_session_log(IMPORT_DIR / "carter_session.log"):
        put(q, "carter:session.log", None, prev)
    for prompt, tools in b._carter_py_cases(IMPORT_DIR / "universal_benchmark_cases.py"):
        put(prompt, "carter:cases.py", tools or None)
    return list(rows.values())


def main() -> int:
    from scripts.router_corpus_labels import label_for, is_noise

    ap = argparse.ArgumentParser()
    ap.add_argument("--audit", action="store_true")
    ap.add_argument("--unmatched", action="store_true",
                    help="list prompts with no curated label AND no hand rule")
    args = ap.parse_args()

    rows = _load_corpus_rows()
    stats = {
        "total": len(rows),
        "dropped_noise": 0,        # ASR garbage, not a real command
        "curated_label_kept": 0,   # had a real tool label → normalized & trusted
        "curated_none_kept": 0,    # explicit 'ninguna' → trusted
        "hand_labeled_tool": 0,    # my rule assigned tool(s)
        "hand_labeled_none": 0,    # my rule said no tool
        "unmatched": 0,            # NO curated label and NO hand rule (need work)
    }
    unmatched: list[tuple[str, str | None, str]] = []
    out_rows: list[dict] = []

    for r in rows:
        q, raw, src = r["q"], r.get("raw"), r["source"]
        # Drop broken-audio / gibberish that isn't a real command. Only the
        # unlabeled voice traces can be noise (curated guides never are).
        if raw is None and is_noise(q):
            stats["dropped_noise"] += 1
            continue
        is_run = src.startswith("carter_run")
        norm, kind = normalize_label(raw or "")
        # conversational context (previous user turn), if known. The runtime
        # router HAS this; the harness can use it to route continuations
        # ("ciérralo", "haz lo mismo") the way they're actually routed. Drop
        # a prev that equals the query itself (dedup artifact — a repeated
        # command became its own predecessor; not real context).
        _prev = r.get("prev")
        if _prev and _prev.strip().lower() == q.strip().lower():
            _prev = None
        prev_kw = {"prev": _prev} if _prev else {}

        if kind == "tools" and norm and not is_run:
            # human-curated tool label → trust, just normalized.
            out_rows.append({"q": q, "expected": sorted(norm), "source": src,
                             "label_origin": "curated",
                             **({"raw": raw} if raw else {}), **prev_kw})
            stats["curated_label_kept"] += 1
            continue
        if kind == "none":
            # explicit 'ninguna' from a guide → trust (it's deliberate).
            out_rows.append({"q": q, "expected": [], "source": src,
                             "label_origin": "curated_none", "raw": raw, **prev_kw})
            stats["curated_none_kept"] += 1
            continue

        # No usable curated label (meta marker, run-JSON, or unlabeled) →
        # use MY hand-authored label.
        mine = label_for(q)
        if mine is None:
            stats["unmatched"] += 1
            unmatched.append((q, raw, src))
            # leave a placeholder so the row still exists; expected empty but
            # flagged so it's visible it needs a hand label.
            out_rows.append({"q": q, "expected": [], "source": src,
                             "label_origin": "UNMATCHED",
                             **({"raw": raw} if raw else {}), **prev_kw})
            continue
        if mine:
            stats["hand_labeled_tool"] += 1
            origin = "hand"
        else:
            stats["hand_labeled_none"] += 1
            origin = "hand_none"
        out_rows.append({"q": q, "expected": sorted(mine), "source": src,
                         "label_origin": origin,
                         **({"raw": raw} if raw else {}), **prev_kw})

    print("=" * 64)
    print("Corpus curation — Opus-authored ground truth (no auto oracle)")
    print("=" * 64)
    for k, v in stats.items():
        print(f"  {k:22s} {v}")
    kept = len(rows) - stats["dropped_noise"]
    labeled = kept - stats["unmatched"]
    print(f"\n  corpus rows kept (after dropping noise): {kept}")
    print(f"  rows with a coherent label: {labeled}/{kept} "
          f"({100*labeled/max(1,kept):.1f}%)")

    if args.unmatched and unmatched:
        print(f"\n--- {len(unmatched)} prompts still needing a hand label ---")
        for q, raw, src in unmatched[:120]:
            tag = f"[{raw}]" if raw else "[no-label]"
            print(f"  {tag:26s} {q[:64]}")

    if not args.audit and not args.unmatched:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        with OUT.open("w", encoding="utf-8") as f:
            for r in out_rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"\nWritten curated corpus: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
