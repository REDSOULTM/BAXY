"""Build the MASTER router-eval corpus from EVERY log that has ever
existed in this repo + the runtime logs in ~/.gemma4.

The operator's instruction: use every log from the very first one to the
last as the test set. So we sweep all known sources, extract the user's
request text from each, dedupe, and write one master corpus. The router
eval (scripts/router_eval.py) then scores against ALL of it.

Sources swept:
  - gemma4_agent/data/traces.jsonl           (main trace ring)
  - traces_*.txt at repo root                (archived trace dumps)
  - ~/.gemma4/timeline/*.jsonl               (per-turn timeline)
  - ~/.gemma4/recordings/*/manifest.jsonl    (session recordings)
  - ~/.gemma4/logs/**/full.log               (pre-session full logs)

User text is found in 'request_start' events (content.preview) and in
any event carrying a 'user_text' / 'query' field.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOME_GEMMA = Path.home() / ".gemma4"
OUT = ROOT / "gemma4_agent" / "data" / "router_eval_corpus.jsonl"

# Noise filters: test fixtures and broken-audio fragments are not real
# user commands and shouldn't be scored as routing failures.
_NOISE = re.compile(
    r"(echo|phrase_hook_test|prueba|test_\d|__stop__|\bhook_test\b)",
    re.IGNORECASE,
)


def _user_texts_from_jsonl(path: Path) -> list[str]:
    out: list[str] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return out
    for line in text.splitlines():
        line = line.strip().lstrip("﻿")
        if not line:
            continue
        try:
            e = json.loads(line)
        except Exception:
            continue
        # request_start: content.preview
        if e.get("kind") == "request_start":
            c = e.get("content") or {}
            q = c.get("preview") or c.get("text")
            if isinstance(q, str) and q.strip():
                out.append(q.strip())
        # any event with an explicit user text field
        for key in ("user_text", "query"):
            v = e.get(key)
            if isinstance(v, str) and v.strip():
                out.append(v.strip())
    return out


def _carter540_cases(path: Path) -> list[tuple[str, str]]:
    """Parse the Carter bench matrix: rows are
    | ID | Sev | Prompt | Resultado | Tools esperadas | Prohibido | PASS |
    Returns (prompt, expected_tools_text) pairs."""
    out: list[tuple[str, str]] = []
    if not path.exists():
        return out
    row_id = re.compile(r"^C\d\d-\d\d$")
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        cells = [c.strip() for c in line.split("|")]
        if len(cells) >= 8 and row_id.match(cells[1]):
            prompt, tools = cells[3], cells[5]
            if prompt and len(prompt) >= 2:
                out.append((prompt, tools))
    return out


def main() -> int:
    sources: list[Path] = []
    sources.append(ROOT / "gemma4_agent" / "data" / "traces.jsonl")
    sources.extend(sorted(ROOT.glob("traces_*.txt")))
    if HOME_GEMMA.exists():
        sources.extend(sorted(HOME_GEMMA.glob("timeline/*.jsonl")))
        sources.extend(sorted(HOME_GEMMA.glob("recordings/*/manifest.jsonl")))
        sources.extend(sorted(HOME_GEMMA.glob("logs/**/full.log")))

    counts: dict[str, int] = {}
    seen: dict[str, int] = {}
    # expected tools, when known (from the Carter bench). key=query.
    expected: dict[str, str] = {}
    for src in sources:
        if not src.exists():
            continue
        texts = _user_texts_from_jsonl(src)
        kept = 0
        for q in texts:
            if _NOISE.search(q):
                continue
            if len(q) < 2:
                continue
            seen[q] = seen.get(q, 0) + 1
            kept += 1
        counts[str(src)] = kept

    # Carter 540 bench matrix — curated prompts + their expected tools.
    carter = ROOT / "harness_carter540" / "tests_540.md"
    c_cases = _carter540_cases(carter)
    for prompt, tools in c_cases:
        if _NOISE.search(prompt):
            continue
        seen[prompt] = seen.get(prompt, 0) + 1
        if tools:
            expected[prompt] = tools
    counts[str(carter)] = len(c_cases)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        for q, n in sorted(seen.items(), key=lambda x: -x[1]):
            row = {"q": q, "count": n}
            if q in expected:
                row["expected_tools"] = expected[q]
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print("Sources swept:")
    for s, n in counts.items():
        print(f"  {n:5d}  {s}")
    print(f"\nUnique user queries (master corpus): {len(seen)}")
    print(f"Written: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
