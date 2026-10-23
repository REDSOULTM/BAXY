"""Answer-length probe (w7-breve, 2026-10-23): how long the model's answer after its last call is, by arm of BAXY_AYUDAS.

Each e2e practice turn that ran tools is replayed through the mind's own continue_turn (facts line, notes, aids) with
the person's words, the calls as the model made them and the results the App gave (events.jsonl); only the last
continue reaches the model, which answers (or calls again). Own cases (--cases, a JSON list of {id, text, steps}) join
them. One clock per case for every arm, the same seeds, and an arm whose prompt is the same as another's reuses its
answer. A CPU-only llama-server in a folder of its own (nothing of a running BAXY is touched); --reduce keeps only the
tools the cases use, so the prefix is ~14k tokens instead of ~44k (a relative measure: the arms share it).
usage: py -3.12 -X utf8 breve.py LABEL --src MIND_SRC --runs RUN[,RUN] [--cases FILE] --arms SETTING[;SETTING]
       [--seeds 0,1,2] [--min-steps 2] [--max-steps 5] [--reduce]
An arm is a BAXY_AYUDAS setting, optionally «|noline» (diagnostic: the last result without its facts line).
"""
import argparse
import json
import os
import statistics
import sys
import tempfile
from pathlib import Path

EVAL = Path(os.environ.get("BAXYEVAL", r"F:/BAXYeval"))
RUNS = EVAL / "renew_v1" / "runs"
FACTS = "\n[En este turno: "


def turns(run: str) -> list[dict]:
    """The turns of an e2e run in the order they ran, each with its case id (by the replies results.jsonl keeps), the
    case's earlier turns as plain words, its steps and BAXY's replies."""
    results = [json.loads(line) for line in open(RUNS / run / "results.jsonl", encoding="utf-8")][1:]
    by_text = {}
    for case in results:
        for reply in case["replies"]:
            by_text.setdefault(reply["text"], (case["id"], reply["turn"]))
    out, current = [], None
    for line in open(RUNS / run / "events.jsonl", encoding="utf-8"):
        event = json.loads(line)
        if event["type"] == "turn.start":
            current = {"steps": [], "replies": [], "text": event["input"].get("text")}
            out.append(current)
        elif current is None:
            continue
        elif event["type"] == "step":
            current["steps"].append(event)
        elif event["type"] == "message" and event["speaker"] == "baxy":
            current["replies"].append((event.get("route"), event["body"]))
    history: dict[str, list] = {}
    for turn in out:
        turn["id"], turn["n"] = next((by_text[b] for _, b in turn["replies"] if b in by_text), ("?", 0))
        turn["history"] = list(history.get(turn["id"], []))
        history.setdefault(turn["id"], []).extend([
            {"role": "user", "content": turn["text"]},
            {"role": "assistant", "content": " ".join(b for _, b in turn["replies"])}])
    return out


def usable(turn: dict) -> bool:
    return (turn["id"] != "?" and bool(turn["steps"]) and all(r == "conversation" for r, _ in turn["replies"])
            and all(s.get("observation") for s in turn["steps"]))


def without_facts(content: str) -> str:
    at = content.find(FACTS)
    return content if at < 0 else content[:at] + content[content.find("]", at) + 1:]


class Replay:
    def __init__(self, mind) -> None:
        self.mind, self.clocks, self.cache, self.row = mind, {}, {}, {}

    def run(self, turn: dict, diag: str) -> dict:
        mind = self.mind
        mind.new_session(turn["history"])
        clock = self.clocks.setdefault(f"{turn['id']}.{turn['n']}.{turn['text']}", mind._clock())
        mind.conversation += [{"role": "user", "content": clock}, {"role": "user", "content": turn["text"]}]
        mind._turn = {"conv": mind.conversation, "queue": [], "awaiting": None, "text": turn["text"], "pending": False,
                      "ended": None, "answering": False}
        real, self.row = type(mind)._next, {}

        def answer(*args, **kwargs):
            if diag == "noline":
                mind.conversation[-1]["content"] = without_facts(mind.conversation[-1]["content"])
            key = json.dumps([mind.seed, mind.conversation], ensure_ascii=False)
            if key not in self.cache:
                got = real(mind, *args, **kwargs)
                self.cache[key] = (dict(got), json.loads(mind.trace.read_text(encoding="utf-8").splitlines()[-1]))
            self.row = self.cache[key][1]
            return dict(self.cache[key][0])

        result = None
        try:
            for index, step in enumerate(turn["steps"]):
                op = step["operation"]
                args = {k: v for k, v in (step["arguments"] or {}).items() if k not in mind.constants.get(op, {})}
                call = f"call_{index}"
                mind.conversation.append({"role": "assistant", "content": "", "tool_calls": [
                    {"id": call, "type": "function",
                     "function": {"name": op.replace(".", "_"), "arguments": json.dumps(args, ensure_ascii=False)}}]})
                mind._turn.update(awaiting=call, calling=op,
                                  calling_args=json.dumps(args, sort_keys=True, ensure_ascii=False))
                last = index == len(turn["steps"]) - 1
                mind._next = answer if last else (lambda *a, **k: {"kind": "earlier_call"})
                result = mind.continue_turn(turn["id"], step["observation"])
        finally:
            mind.__dict__.pop("_next", None)
        return result


def summary(rows: list[dict]) -> None:
    arms = list(dict.fromkeys(r["arm"] for r in rows))
    by: dict[tuple, dict] = {}
    for r in rows:
        by.setdefault((r["case"], r["seed"]), {})[r["arm"]] = r
    base = arms[0]
    for arm in arms:
        said = [r["predicted_n"] for r in rows if r["arm"] == arm and r["kind"] == "conversation" and r["predicted_n"]]
        pairs = [(v[base]["predicted_n"], v[arm]["predicted_n"]) for v in by.values() if base in v and arm in v
                 and v[base]["kind"] == v[arm]["kind"] == "conversation"]
        changed = [b - a for a, b in pairs if a != b]
        print(f"{arm[:40]:40} answers {len(said):3} p50 {statistics.median(said) if said else 0:5} mean "
              f"{statistics.mean(said) if said else 0:5.1f} | vs first: {len(pairs)} pairs, "
              f"{sum(d < 0 for d in changed)} shorter / {sum(d > 0 for d in changed)} longer, "
              f"Δ mean {statistics.mean([b - a for a, b in pairs]) if pairs else 0:+.2f}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("label")
    ap.add_argument("--src", required=True)
    ap.add_argument("--runs", default="")
    ap.add_argument("--cases", default="")
    ap.add_argument("--arms", required=True)
    ap.add_argument("--seeds", default="0")
    ap.add_argument("--min-steps", type=int, default=1)
    ap.add_argument("--max-steps", type=int, default=6)
    ap.add_argument("--threads", default="12")
    ap.add_argument("--reduce", action="store_true")
    ap.add_argument("--gguf", default=str(EVAL / "models" / "BAXY-Qwen3.5-4B-ft-c2e1-Q4_K_M.gguf"))
    ap.add_argument("--server", default=str(EVAL / "llama" / "llama-server.exe"))
    ap.add_argument("--catalog", default=str(Path(os.environ["LOCALAPPDATA"]) / "BAXY" / "renew" / "catalog.configure.json"))
    ap.add_argument("--work", default=str(Path(tempfile.gettempdir()) / "baxy-breve"))
    a = ap.parse_args()
    catalog = json.loads(Path(a.catalog).read_text(encoding="utf-8"))
    cases = [turn for run in a.runs.split(",") if run for turn in turns(run) if usable(turn)]
    if a.cases:
        cases += [{"id": c["id"], "n": 1, "text": c["text"], "history": [], "steps": c["steps"], "replies": []}
                  for c in json.loads(Path(a.cases).read_text(encoding="utf-8"))]
    unique: dict[str, dict] = {}
    for turn in cases:  # the same turn in two runs is one case
        key = json.dumps([turn["text"], turn["history"], [[s["operation"], s["arguments"], s["observation"]]
                                                          for s in turn["steps"]]], ensure_ascii=False)
        unique.setdefault(key, turn)
    cases = [t for t in unique.values() if a.min_steps <= len(t["steps"]) <= a.max_steps]
    if a.reduce:
        used = {s["operation"] for t in cases for s in t["steps"]}
        catalog["capabilities"] = [c for c in catalog["capabilities"] if c["name"] in used]
    work = Path(a.work)
    work.mkdir(parents=True, exist_ok=True)
    os.environ.update(LOCALAPPDATA=str(work), BAXY_VISION_SLOT_DIR=str(work / ("slots-reduced" if a.reduce else "slots")),
                      BAXY_DATA_DIR=str(work / "data"), CUDA_VISIBLE_DEVICES="-1")
    for name in ("BAXY_MIND_LLAMA_PORT", "BAXY_MIND_MMPROJ"):
        os.environ.pop(name, None)
    sys.path.insert(0, a.src)
    from baxy_mind.llm_server import LlmServer
    from baxy_mind.mind import Mind
    server = LlmServer(a.gguf, a.server, gpu_layers="0", context=49152,
                       extra_args=["--device", "none", "-t", a.threads], log_name=f"breve-{a.label}.log")
    plain = server.chat
    server.chat = lambda body, timeout=120.0, on_text=None: plain(body, timeout=max(timeout, 10800.0))
    server.start()
    out_path = RUNS / f"{a.label}.breve.jsonl"
    rows = []
    try:
        mind = Mind(server, work / f"{a.label}.trace.jsonl")
        mind.configure(catalog)
        server.wait_ready(10800)
        mind.warm()  # the first time a CPU reads the whole prefix (~6 min reduced, ~40 min whole); then it is restored
        print(f"{len(cases)} cases, prefix {mind.prefix_tokens} tokens", flush=True)
        replay = Replay(mind)
        with open(out_path, "w", encoding="utf-8") as out:
            for turn in cases:
                for seed in a.seeds.split(","):
                    for arm in a.arms.split(";"):
                        setting, _, diag = arm.partition("|")
                        os.environ["BAXY_AYUDAS"] = setting
                        mind.seed = int(seed)
                        try:
                            result, error = replay.run(turn, diag), None
                        except Exception as exc:  # noqa: BLE001
                            result, error = {}, repr(exc)[:300]
                        row = {"case": f"{turn['id']}.{turn['n']}", "seed": int(seed), "arm": arm,
                               "kind": result.get("kind"), "operation": result.get("operation"),
                               "reply": result.get("reply") or result.get("question"),
                               "predicted_n": replay.row.get("predicted_n"), "prompt_n": replay.row.get("prompt_n"),
                               "recorded": " ".join(b for _, b in turn["replies"]), "error": error}
                        rows.append(row)
                        out.write(json.dumps(row, ensure_ascii=False) + "\n")
                        out.flush()
                        print(row["case"], seed, arm[:24], row["kind"], row["predicted_n"], "|",
                              row["reply"] or row["operation"] or error, flush=True)
    finally:
        server.close()
    summary(rows)


if __name__ == "__main__":
    main()
