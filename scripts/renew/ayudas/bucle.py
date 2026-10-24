"""Session replay (w9-bucle, 2026-10-23): a long session of the w8 bench replayed through the mind's own decide and
continue_turn, with the model's decisions forced to the recorded ones (the run's mente/turns.jsonl) up to a turn and its
first --force decisions; from there the real model decides, the recorded results (events.jsonl) come back by operation
and arguments, and the App's closing (TurnClosing: 15 moves, the same call and result 3 times in a row) applies. Each
seed and arm writes what the model called and how the turn ended.

int10's «abre la calculadora» (nb-i10-T-sesion), PC GPU, seeds 0-4, forced to the first look: int10's mind clicked
«Sistema» and looked in turn up to the App's cap (15 calls) in 3 seeds, pressed another control over and over in a
4th and answered in the 5th; with same_call_closes and look_click_cap the third same pair did not run and the model
answered at 10 calls in 4 seeds (the 5th answered at once).

usage: py -3.12 -X utf8 bucle.py LABEL --src MIND_SRC --run RUN_DIR --catalog CATALOG --upto TEXT [--force 1]
       [--arms SETTING[;SETTING]] [--seeds 0,1] [--live 16] [--ngl 0]
RUN_DIR holds turns.jsonl and events.jsonl; CATALOG is the run's catalog.configure.json; an arm is a BAXY_AYUDAS
setting. --ngl 0 runs llama-server on the CPU (slow: ~50 min for the prefix).
"""
import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path


def recorded(run: Path) -> tuple[list[dict], list[dict]]:
    """The model's decisions in the order the mind traced them, and each turn's person's words and steps."""
    rows = [json.loads(line) for line in open(run / "turns.jsonl", encoding="utf-8")]
    decisions = [r for r in rows if r["stage"] in ("turn.decide", "turn.continue")
                 and r.get("kind") in ("action", "conversation", "clarify")]
    turns, current = [], None
    for line in open(run / "events.jsonl", encoding="utf-8"):
        event = json.loads(line)
        if event["type"] == "turn.start":
            current = {"text": event["input"].get("text"), "steps": []}
            turns.append(current)
        elif event["type"] == "step" and current is not None:
            current["steps"].append(event)
    return decisions, turns


def forced_reply(decision: dict, n: int) -> dict:
    message = {"role": "assistant", "content": decision.get("content") or ""}
    if decision["kind"] == "action":
        message["tool_calls"] = [{"id": f"call_r{n}", "type": "function", "function": {
            "name": decision["operation"].replace(".", "_"),
            "arguments": json.dumps(decision.get("arguments") or {}, ensure_ascii=False)}}]
    return {"choices": [{"message": message}], "timings": {}, "usage": {}}


class Closing:
    """The App's TurnClosing without its time budget."""

    def __init__(self, key) -> None:
        self.last, self.same, self.key = None, 0, key

    def after(self, calls: int, operation: str, arguments: str, observation: str) -> bool:
        call = json.dumps([operation, arguments, self.key(observation)])
        self.same = self.same + 1 if call == self.last else 1
        self.last = call
        return calls >= 15 or self.same >= 3


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("label")
    ap.add_argument("--src", required=True)
    ap.add_argument("--run", required=True)
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--upto", required=True)
    ap.add_argument("--force", type=int, default=1)
    ap.add_argument("--arms", default="all")
    ap.add_argument("--seeds", default="0")
    ap.add_argument("--live", type=int, default=16)
    ap.add_argument("--threads", default="16")
    ap.add_argument("--ngl", default="0")
    ap.add_argument("--gguf", default="F:/BAXYeval/models/BAXY-Qwen3.5-4B-ft-c2e1-Q4_K_M.gguf")
    ap.add_argument("--server", default="F:/BAXYeval/llama/llama-server.exe")
    ap.add_argument("--work", default=str(Path(tempfile.gettempdir()) / "baxy-bucle"))
    a = ap.parse_args()
    decisions, turns = recorded(Path(a.run))
    work = Path(a.work)
    work.mkdir(parents=True, exist_ok=True)
    os.environ.update(LOCALAPPDATA=str(work), BAXY_VISION_SLOT_DIR=str(work / "slots"), BAXY_DATA_DIR=str(work / "data"))
    if a.ngl == "0":
        os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
    for name in ("BAXY_MIND_LLAMA_PORT", "BAXY_MIND_MMPROJ"):
        os.environ.pop(name, None)
    sys.path.insert(0, a.src)
    from baxy_mind import mind as M
    from baxy_mind.llm_server import LlmServer
    extra = ["--device", "none", "-t", a.threads] if a.ngl == "0" else []
    server = LlmServer(a.gguf, a.server, gpu_layers=a.ngl, context=53248, extra_args=extra,
                       log_name=f"bucle-{a.label}.log")
    plain = server.chat
    forced: list[dict] = []

    def chat(body, timeout=120.0, on_text=None):
        if body.get("max_tokens") == 512 and forced:  # a decision, not the warm-up
            return forced_reply(forced.pop(0), len(forced))
        return plain(body, timeout=max(timeout, 10800.0))

    server.chat = chat
    server.start()
    try:
        mind = M.Mind(server, work / f"{a.label}.trace.jsonl")
        mind.configure(json.loads(Path(a.catalog).read_text(encoding="utf-8")))
        server.wait_ready(10800)
        started = time.time()
        mind.warm()
        print(f"warm {time.time() - started:.0f}s prefix {mind.prefix_tokens}", flush=True)
        target = next(i for i, t in enumerate(turns) if t["text"] == a.upto)
        with open(work / f"{a.label}.jsonl", "a", encoding="utf-8") as out:
            for seed in a.seeds.split(","):
                for arm in a.arms.split(";"):
                    os.environ["BAXY_AYUDAS"] = arm
                    mind.seed = int(seed)
                    mind.new_session()
                    forced[:] = list(decisions)
                    live: list[dict] = []
                    for index, turn in enumerate(turns[:target + 1]):
                        if index == target:
                            forced[:] = forced[:a.force]
                        result, calls, closing, pool = mind.decide(index, turn["text"]), 0, Closing(M._result_key), \
                            list(turn["steps"])
                        while result.get("kind") == "action":
                            calls += 1
                            op, args = result["operation"], result.get("arguments") or {}
                            if index == target and calls > a.force:
                                live.append({"op": op, "args": {k: v for k, v in args.items()
                                                                if k not in mind.constants.get(op, {})}})
                            step = next((s for s in pool if s["operation"] == op and s["arguments"] == args), None) \
                                or next((s for s in pool if s["operation"] == op), None)
                            if step is None:
                                live.append({"stop": f"no recorded result for {op}"})
                                break
                            if len(pool) > 1:
                                pool.remove(step)
                            final = closing.after(calls, op, json.dumps(args, ensure_ascii=False), step["observation"])
                            if index == target and calls > a.live:
                                break
                            result = mind.continue_turn(index, step["observation"], final=final)
                        if index == target:
                            live.append({"end": result.get("kind"), "reply": result.get("reply")})
                    row = {"arm": arm, "seed": int(seed), "live": live, "calls": sum("op" in r for r in live)}
                    out.write(json.dumps(row, ensure_ascii=False) + "\n")
                    out.flush()
                    print(json.dumps(row, ensure_ascii=False)[:1500], flush=True)
    finally:
        server.close()


if __name__ == "__main__":
    main()
