"""What each request to Qwen's llama-server read again, from its own log (timings only: the log holds no text).

usage: py -3.12 -X utf8 scripts/renew/relecturas.py [llama-server.log] [--rows]
(default: %LOCALAPPDATA%\\BAXY\\renew\\llama-server.log, the last run of the product or of a bench through it)

Per request: the tokens it read (prompt eval), the ones it kept from the slot, and how many of the slot's tokens it had
to drop (its prompt differs from what the slot held there; a hybrid model goes back to its last checkpoint before that
point). Al máximo W5: a follow-up turn.decide used to drop the previous turn (its messages change form once a new
request comes, mind.PREFILL_MARK) and read it again; with the read ahead on (BAXY_RENEW_PREFILL, default) those tokens
are read by a request of its own that writes one token («one token» rows, with System One's one-token name
completions), while BAXY speaks, and the decision reads only its turn. Compare a run with BAXY_RENEW_PREFILL=0 and
one without it on the same bench: «model requests» prompt ms p50/p90 and «dropped from the slot» should fall (a
bench's new sessions drop the case before in both runs); «one token» shows where that work went. «gap» is release →
the next request taking the slot: the client's work plus the server's own before it reads (template, tokens, grammar).
"""
import os
import re
import statistics
import sys
from pathlib import Path

LINE = re.compile(r"(\d+)\.(\d+)\.(\d+)\.(\d+) . slot +(\w+): id +\d+ \| task (-?\d+) \| (.*)")


def _seconds(match: re.Match) -> float:
    minutes, seconds, millis, micros = (int(match.group(i)) for i in range(1, 5))
    return minutes * 60 + seconds + millis / 1000 + micros / 1e6


def read(path: Path) -> list[dict]:
    tasks: dict[str, dict] = {}
    order: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = LINE.match(line)
        if not match:
            continue
        at, kind, task, rest = _seconds(match), match.group(5), match.group(6), match.group(7)
        row = tasks.setdefault(task, {"task": task})
        if kind == "get_availabl":
            row = tasks[task] = {"task": task, "asked": at}  # task -1: the next request taking the slot
        elif kind == "launch_slot_":
            row["start"] = at
            row["asked"] = tasks.pop("-1", {}).get("asked", at)
            order.append(task)
        elif "prompt eval time" in rest or rest.lstrip().startswith("eval time"):
            ms, n = re.search(r"=\s+([\d.]+) ms /\s+(\d+) tokens", rest).groups()
            prefix = "prompt" if "prompt eval" in rest else "gen"
            row[f"{prefix}_ms"], row[f"{prefix}_n"] = float(ms), int(n)
        elif kind == "release":
            row["end"], row["n_tokens"] = at, int(re.search(r"n_tokens = (\d+)", rest).group(1))
    rows = [tasks[t] for t in order if "n_tokens" in tasks[t] and "prompt_n" in tasks[t]]
    held = None
    for row in rows:
        row["kept"] = row["n_tokens"] - row.get("gen_n", 1) + 1 - row["prompt_n"]
        row["dropped"] = max(0, held - row["kept"]) if held is not None else 0
        # «other»: a request that kept nothing after the start (the vision's question, on a slot set aside).
        row["kind"] = ("start" if held is None else "other" if row["kept"] == 0
                       else "one token" if row.get("gen_n", 1) <= 1 else "model")
        held = row["n_tokens"]
    for before, after in zip(rows, rows[1:]):
        before["gap_ms"] = (after["asked"] - before["end"]) * 1000
    return rows


def _spread(values: list[float]) -> str:
    if not values:
        return "-"
    ordered = sorted(values)
    pick = lambda q: ordered[int(q * (len(ordered) - 1))]  # noqa: E731
    return f"n={len(values)} p50={pick(.5):.0f} p90={pick(.9):.0f} sum={sum(values):.0f}"


def main() -> int:
    args = [a for a in sys.argv[1:] if a != "--rows"]
    path = Path(args[0]) if args else Path(os.environ.get("LOCALAPPDATA", ".")) / "BAXY" / "renew" / "llama-server.log"
    rows = read(path)
    if "--rows" in sys.argv:
        for r in rows:
            print(f"{r['task']:>6} {r['kind']:<11} read {r['prompt_n']:>6} ({r['prompt_ms']:7.0f} ms) "
                  f"wrote {r.get('gen_n', 0):>4} kept {r['kept']:>6} dropped {r['dropped']:>5} "
                  f"gap {r.get('gap_ms', 0):6.0f} ms")
    model = [r for r in rows if r["kind"] == "model"]
    print(path)
    print("model requests, prompt tokens:", _spread([r["prompt_n"] for r in model]))
    print("model requests, prompt ms:    ", _spread([r["prompt_ms"] for r in model]))
    dropped = [r for r in rows if r["kind"] == "model" and r["dropped"] > 0]
    print("dropped from the slot:        ", _spread([r["dropped"] for r in dropped]))
    prefill = [r for r in rows if r["kind"] == "one token"]
    print("one token written:           ", _spread([r["prompt_n"] for r in prefill]), "tokens;",
          _spread([r["prompt_ms"] for r in prefill]), "ms")
    print("gap release -> next request:  ", _spread([r["gap_ms"] for r in rows if "gap_ms" in r]), "ms")
    print("decode ms per token:          ",
          f"{statistics.median(r['gen_ms'] / r['gen_n'] for r in model if r.get('gen_n', 0) > 1):.1f}" if model else "-")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
