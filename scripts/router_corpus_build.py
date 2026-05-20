"""Build the MASTER router-eval corpus from EVERY log that has ever
existed in this repo + the runtime logs in ~/.gemma4 + every prior
project (Carter v1..v5, the direct ancestor of this one).

The operator's instruction: use every log from the very first one to the
last as the test set. So we sweep all known sources, extract the user's
request text from each, dedupe, and write one master corpus. The router
eval (scripts/router_eval.py) then scores against ALL of it.

Sources swept (this project):
  - gemma4_agent/data/traces.jsonl           (main trace ring)
  - traces_*.txt at repo root                (archived trace dumps)
  - ~/.gemma4/timeline/*.jsonl               (per-turn timeline)
  - ~/.gemma4/recordings/*/manifest.jsonl    (session recordings)
  - ~/.gemma4/logs/**/full.log               (pre-session full logs)
  - harness_carter540/tests_540.md           (curated 540-case matrix)

Sources swept (Carter, the prior project — see CARTER_ROOT):
  - Extras/Carter_v3_tests/*.md              (3 distinct curated bench
    guides: v2 Matriz 361, v3 GUIA_OFICIAL 540, v3 MINIMUM 36; the 4th,
    Maximo_Esplendor_18x30, is byte-identical to tests_540.md → skipped)
  - legacy/Carter_v3/audit/runs/full_18x30_true_ready*.json  (540 real
    runs: prompt + the tools the model ACTUALLY used)
  - legacy/Carter_v1/carter_session.log      (~115 unique organic queries)
  - legacy/Carter_v1/data/universal_benchmark_cases.py  (72 base cases)

User text is found in 'request_start' events (content.preview) and in
any event carrying a 'user_text' / 'query' field. Each corpus row keeps
an 'origin' tag so a failure can be traced back to its source log.
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOME_GEMMA = Path.home() / ".gemma4"
# The prior project. Its logs are the historical test set the operator
# asked to fold in. Override with GEMMA4_CARTER_ROOT if it ever moves.
import os
CARTER_ROOT = Path(
    os.environ.get(
        "GEMMA4_CARTER_ROOT",
        r"C:\Users\usuario\Desktop\ETC\Programacion\Carter OS AI",
    )
)
OUT = ROOT / "gemma4_agent" / "data" / "router_eval_corpus.jsonl"

# Noise filters: test fixtures and broken-audio fragments are not real
# user commands and shouldn't be scored as routing failures.
_NOISE = re.compile(
    r"(echo|phrase_hook_test|prueba|test_\d|__stop__|\bhook_test\b)",
    re.IGNORECASE,
)


def _user_turns_from_jsonl(path: Path) -> list[tuple[str, str | None]]:
    """Return (query, prev_user_text) in temporal order. prev_user_text is
    the user's previous request in the SAME session/turn stream, so the
    eval can route continuations ("ciérralo", "haz lo mismo") with the
    context the planner actually has at runtime."""
    out: list[tuple[str, str | None]] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return out
    # Group request_start queries by their session prefix in turn_id.
    # turn_id looks like "20260518_113503_272138e3"; the date+time orders
    # them and the stream is already chronological in the file.
    last_by_session: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip().lstrip("﻿")
        if not line:
            continue
        try:
            e = json.loads(line)
        except Exception:
            continue
        q = None
        if e.get("kind") == "request_start":
            c = e.get("content") or {}
            q = c.get("preview") or c.get("text")
        if not (isinstance(q, str) and q.strip()):
            for key in ("user_text", "query"):
                v = e.get(key)
                if isinstance(v, str) and v.strip():
                    q = v
                    break
        if not (isinstance(q, str) and q.strip()):
            continue
        q = q.strip()
        tid = str(e.get("turn_id") or "")
        # session = everything up to the last underscore (drop the per-turn
        # hash) → consecutive turns in one conversation share it.
        session = tid.rsplit("_", 1)[0] if "_" in tid else tid
        prev = last_by_session.get(session)
        out.append((q, prev))
        last_by_session[session] = q
    return out


def _carter540_cases(path: Path) -> list[tuple[str, str, str | None]]:
    """Parse the Carter bench matrix: rows are
    | ID | Sev | Prompt | Resultado | Tools esperadas | Prohibido | PASS |
    Returns (prompt, expected_tools, prev_prompt) — prev is the prior row
    in the SAME category (C01-01 → C01-02 ...), which is the conversational
    context the bench implies for continuation prompts ("ahora ciérralo")."""
    out: list[tuple[str, str, str | None]] = []
    if not path.exists():
        return out
    row_id = re.compile(r"^(C(\d\d)-\d\d)$")
    last_by_cat: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        cells = [c.strip() for c in line.split("|")]
        if len(cells) >= 8:
            m = row_id.match(cells[1])
            if m:
                cat = m.group(2)
                prompt, tools = cells[3], cells[5]
                if prompt and len(prompt) >= 2:
                    out.append((prompt, tools, last_by_cat.get(cat)))
                    last_by_cat[cat] = prompt
    return out


def _md_table_cases(
    path: Path, *, prompt_col: int, tools_col: int | None
) -> list[tuple[str, str, str | None]]:
    """Parse a Carter markdown bench guide. Rows look like
        | <ID> | ... | <prompt> | ... | <tools?> | ... |
    where the ID matches Cnn-nn or MIN-Cnn-nn (optionally backtick-wrapped).
    `prompt_col` / `tools_col` are 0-based indices into the pipe-split cells
    (cell 0 is the empty string before the first '|'). `tools_col` may be
    None for guides with no expected-tools column.

    Returns (prompt, expected_tools, prev_prompt) where prev is the prior
    row in the SAME category — the conversational context the bench implies
    for continuation prompts ("ahora ciérralo")."""
    out: list[tuple[str, str, str | None]] = []
    if not path.exists():
        return out
    row_id = re.compile(r"^`?(?:MIN-)?C(\d\d)-\d\d`?$")
    last_by_cat: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "|" not in line:
            continue
        cells = [c.strip().strip("`").strip() for c in line.split("|")]
        if len(cells) <= prompt_col:
            continue
        m = row_id.match(cells[1]) if len(cells) > 1 else None
        if not m:
            continue
        cat = m.group(1)
        prompt = cells[prompt_col]
        tools = cells[tools_col] if (tools_col is not None and len(cells) > tools_col) else ""
        if prompt and len(prompt) >= 2:
            out.append((prompt, tools, last_by_cat.get(cat)))
            last_by_cat[cat] = prompt
    return out


def _carter_run_json(path: Path) -> list[tuple[str, str]]:
    """Parse a Carter 18x30 run result JSON. Each case carries `prompt` and
    the tools the model ACTUALLY used (`tool_families`, else names inside
    `tool_calls`). Returns (prompt, used_tools_csv); used_tools is '' when
    the run made no tool call (which itself is ground truth: 'ninguna')."""
    out: list[tuple[str, str]] = []
    if not path.exists():
        return out
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return out
    cases = data.get("results") if isinstance(data, dict) else data
    if not isinstance(cases, list):
        return out
    for c in cases:
        if not isinstance(c, dict):
            continue
        prompt = c.get("prompt")
        if not (isinstance(prompt, str) and len(prompt.strip()) >= 2):
            continue
        fams = c.get("tool_families")
        used: list[str] = []
        if isinstance(fams, list):
            used = [str(x) for x in fams if x]
        if not used:
            calls = c.get("tool_calls")
            if isinstance(calls, list):
                for tc in calls:
                    if isinstance(tc, dict):
                        nm = tc.get("tool") or tc.get("name") or tc.get("family")
                        if nm:
                            used.append(str(nm))
        out.append((prompt.strip(), ",".join(dict.fromkeys(used))))
    return out


def _carter_session_log(path: Path) -> list[tuple[str, str | None]]:
    """Parse Carter v1 session log lines:
        [HH:MM:SS] INFO | ╔══ NUEVA TAREA: <user query>
    Returns (query, prev_query) — prev is the previous task in the file
    (a single rolling session), giving continuation context."""
    out: list[tuple[str, str | None]] = []
    if not path.exists():
        return out
    pat = re.compile(r"NUEVA\s+TAREA:\s*(.+)$")
    prev: str | None = None
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = pat.search(line.rstrip())
        if not m:
            continue
        q = m.group(1).strip()
        # Strip box-drawing / decoration that sometimes trails the line.
        q = q.strip("═╗╔║╚╝─ ").strip()
        if len(q) >= 2:
            out.append((q, prev))
            prev = q
    return out


def _carter_py_cases(path: Path) -> list[tuple[str, str]]:
    """Parse Carter v1 universal_benchmark_cases.py — a module with a list
    of dicts each having a 'task' (the prompt) and 'expected_mode'
    (CHAT/EXECUTIVE...). We map expected_mode CHAT → 'ninguna' (no tool
    expected) as a weak ground-truth; other modes leave tools unknown.
    Returns (prompt, expected_tools_or_empty). Uses ast (no import/exec)."""
    out: list[tuple[str, str]] = []
    if not path.exists():
        return out
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return out
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        d: dict[str, object] = {}
        for k, v in zip(node.keys, node.values):
            if isinstance(k, ast.Constant) and isinstance(k.value, str):
                if isinstance(v, ast.Constant):
                    d[k.value] = v.value
        task = d.get("task")
        if isinstance(task, str) and len(task.strip()) >= 2:
            mode = str(d.get("expected_mode") or "").upper()
            tools = "ninguna" if mode == "CHAT" else ""
            out.append((task.strip(), tools))
    return out


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute and report counts WITHOUT writing the corpus file "
        "(use while another agent owns the shared corpus).",
    )
    args = ap.parse_args()

    sources: list[Path] = []
    sources.append(ROOT / "gemma4_agent" / "data" / "traces.jsonl")
    sources.extend(sorted(ROOT.glob("traces_*.txt")))
    if HOME_GEMMA.exists():
        sources.extend(sorted(HOME_GEMMA.glob("timeline/*.jsonl")))
        sources.extend(sorted(HOME_GEMMA.glob("recordings/*/manifest.jsonl")))
        sources.extend(sorted(HOME_GEMMA.glob("logs/**/full.log")))

    counts: dict[str, int] = {}
    seen: dict[str, int] = {}
    # expected tools, when known (from a bench guide). key=query.
    expected: dict[str, str] = {}
    # previous user turn for each query (conversational context). key=query.
    prev_ctx: dict[str, str] = {}
    # where each query was first seen (provenance). key=query.
    origin: dict[str, str] = {}

    def add(q: str, *, src: str, tools: str | None = None, prev: str | None = None) -> bool:
        if _NOISE.search(q) or len(q) < 2:
            return False
        seen[q] = seen.get(q, 0) + 1
        if tools and q not in expected:
            expected[q] = tools
        if prev and q not in prev_ctx:
            prev_ctx[q] = prev
        if q not in origin:
            origin[q] = src
        return True

    for src in sources:
        if not src.exists():
            continue
        kept = 0
        for q, prev in _user_turns_from_jsonl(src):
            if add(q, src=src.name, prev=prev):
                kept += 1
        counts[str(src)] = kept

    # ---- This project's curated 540-case matrix --------------------------
    carter = ROOT / "harness_carter540" / "tests_540.md"
    kept = 0
    for prompt, tools, prev in _carter540_cases(carter):
        if add(prompt, src="tests_540.md", tools=tools or None, prev=prev):
            kept += 1
    counts[str(carter)] = kept

    # ---- Carter (the prior project): every historical test/log -----------
    if CARTER_ROOT.exists():
        guides = [
            # (relative path, prompt cell idx, tools cell idx or None)
            ("Extras/Carter_v3_tests/Carter_v3_GUIA_OFICIAL_TESTING (1).md", 3, 5),
            ("Extras/Carter_v3_tests/Carter_v2_Matriz_Pruebas_30_por_categoria (1).md", 2, 4),
            ("Extras/Carter_v3_tests/Carter_v3_MINIMUM_TESTING_OFICIAL.md", 2, None),
        ]
        for rel, pcol, tcol in guides:
            p = CARTER_ROOT / rel
            kept = 0
            for prompt, tools, prev in _md_table_cases(p, prompt_col=pcol, tools_col=tcol):
                if add(prompt, src=f"carter:{Path(rel).name}", tools=tools or None, prev=prev):
                    kept += 1
            counts[str(p)] = kept

        # Real 18x30 runs — prompt + tools the model actually used.
        for runp in sorted((CARTER_ROOT / "legacy" / "Carter_v3" / "audit" / "runs").glob("full_18x30_true_ready*.json")):
            kept = 0
            for prompt, used in _carter_run_json(runp):
                # 'used' is the model's real tool families; when empty it's
                # ground truth that no tool was needed ('ninguna').
                if add(prompt, src=f"carter_run:{runp.name}", tools=used or "ninguna"):
                    kept += 1
            counts[str(runp)] = kept

        # Organic v1 session log.
        sess = CARTER_ROOT / "legacy" / "Carter_v1" / "carter_session.log"
        kept = 0
        for q, prev in _carter_session_log(sess):
            if add(q, src="carter:carter_session.log", prev=prev):
                kept += 1
        counts[str(sess)] = kept

        # v1 programmatic cases.
        pyc = CARTER_ROOT / "legacy" / "Carter_v1" / "data" / "universal_benchmark_cases.py"
        kept = 0
        for prompt, tools in _carter_py_cases(pyc):
            if add(prompt, src="carter:universal_benchmark_cases.py", tools=tools or None):
                kept += 1
        counts[str(pyc)] = kept
    else:
        print(f"WARNING: Carter root not found: {CARTER_ROOT}")

    if not args.dry_run:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        with OUT.open("w", encoding="utf-8") as f:
            for q, n in sorted(seen.items(), key=lambda x: -x[1]):
                row: dict = {"q": q, "count": n}
                if q in expected:
                    row["expected_tools"] = expected[q]
                if q in prev_ctx:
                    row["prev"] = prev_ctx[q]
                if q in origin:
                    row["origin"] = origin[q]
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print("Sources swept:")
    for s, n in sorted(counts.items(), key=lambda x: -x[1]):
        if n:
            print(f"  {n:5d}  {s}")
    carter_new = sum(1 for q, o in origin.items() if o.startswith("carter"))
    print(f"\nUnique user queries (master corpus): {len(seen)}")
    print(f"  of which first-seen in a Carter source: {carter_new}")
    print(f"  with expected_tools ground truth:       {len(expected)}")
    if args.dry_run:
        print(f"\nDRY-RUN: corpus NOT written (would go to {OUT})")
    else:
        print(f"Written: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
