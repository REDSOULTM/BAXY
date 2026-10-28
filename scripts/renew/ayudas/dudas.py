"""Look-before-asking probe (w9-dudas, 2026-10-23): what the model decides, by arm of BAXY_AYUDAS, on practice turns where
it asked or refused without looking, or told a list as whole that its result said was not.

A case with no steps is a decision: the person's words (and the case's earlier plain exchanges) reach turn.decide with
layer 0 of System One at BAXY_S1_DOUBT (0.4 as the benches run it; no decision model, so layer 2 is not simulated) and
the row says what the model chose, its confidence and whether the doubt held it. A case with steps is replayed as
breve.py does (the calls as the model made them, the results the App gave); a step's «observation_aid» {aid,
observation} is the result the App gives when that aid is on (an aid of the App's own view). Every arm of a decision
reads its own tools (a description aid changes them), so the arms run one after the other, each warming its prefix once.
A llama-server of its own in a folder of its own, on the CPU or with --ngl on the GPU beside the others (never one
already running); with --families the catalog keeps only the tools whose names start with them.
usage: py -3.12 -X utf8 dudas.py LABEL --src MIND_SRC --catalog CATALOG --cases FILE --arms SETTING[;SETTING]
       [--seeds 0,1,2] [--families file.,game.] [--ngl 99]
"""
import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from breve import EVAL, RUNS, Replay  # noqa: E402

CLOCK = "[Ahora: jueves 23 de octubre de 2026, 21:00]"


def decide(mind, case: dict, seed: int) -> dict:
    mind.new_session(case.get("history") or [])
    mind.seed = seed
    before = len(mind.trace.read_text(encoding="utf-8").splitlines()) if mind.trace.exists() else 0
    result = mind.decide(case["id"], case["text"])
    rows = [json.loads(line) for line in mind.trace.read_text(encoding="utf-8").splitlines()[before:]]
    first = next((r for r in rows if r.get("stage") == "turn.decide"), {})
    mind._close_open_calls()
    return {"first": first.get("operation") or first.get("kind"),
            "held": first.get("kind") in ("doubt_ask", "doubt_reread"), "confidence": (first.get("doubt") or {}).get("confidence"),
            "rivals": (first.get("doubt") or {}).get("rivals"), "kind": result.get("kind"),
            "operation": result.get("operation"), "reply": result.get("reply") or result.get("question")}


def replay(mind, case: dict, seed: int, setting: str, replayer: Replay) -> dict:
    on = {part.strip() for part in setting.split(",")}
    steps = [{**s, "observation": s["observation_aid"]["observation"]}
             if s.get("observation_aid") and s["observation_aid"]["aid"] in on else s for s in case["steps"]]
    mind.seed = seed
    result = replayer.run({**case, "n": 1, "history": case.get("history") or [], "steps": steps}, "")
    return {"kind": result.get("kind"), "operation": result.get("operation"),
            "reply": result.get("reply") or result.get("question")}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("label")
    ap.add_argument("--src", required=True)
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--cases", required=True)
    ap.add_argument("--arms", required=True)
    ap.add_argument("--seeds", default="0,1,2")
    ap.add_argument("--families", default="")
    ap.add_argument("--ngl", default="0")
    ap.add_argument("--threads", default="8")
    ap.add_argument("--gguf", default=str(EVAL / "models" / "BAXY-Qwen3.5-4B-ft-c2e1-Q4_K_M.gguf"))
    ap.add_argument("--server", default=str(EVAL / "llama" / "llama-server.exe"))
    ap.add_argument("--work", default=str(Path(tempfile.gettempdir()) / "baxy-dudas"))
    a = ap.parse_args()
    catalog = json.loads(Path(a.catalog).read_text(encoding="utf-8"))
    families = tuple(f for f in a.families.split(",") if f)
    if families:
        catalog["capabilities"] = [c for c in catalog["capabilities"] if str(c.get("name", "")).startswith(families)]
    cases = json.loads(Path(a.cases).read_text(encoding="utf-8"))
    work = Path(a.work)
    work.mkdir(parents=True, exist_ok=True)
    os.environ.update(LOCALAPPDATA=str(work), BAXY_VISION_SLOT_DIR=str(work / "slots"), BAXY_DATA_DIR=str(work / "data"),
                      BAXY_S1_DOUBT=os.environ.get("BAXY_S1_DOUBT", "0.4"))
    gpu = a.ngl != "0"
    if not gpu:
        os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
    for name in ("BAXY_MIND_LLAMA_PORT", "BAXY_MIND_MMPROJ", "BAXY_S1_VETO"):
        os.environ.pop(name, None)
    sys.path.insert(0, a.src)
    from baxy_mind.llm_server import LlmServer
    from baxy_mind.mind import Mind
    server = LlmServer(a.gguf, a.server, gpu_layers=a.ngl, context=53248,
                       extra_args=[] if gpu else ["--device", "none", "-t", a.threads], log_name=f"dudas-{a.label}.log")
    plain = server.chat
    server.chat = lambda body, timeout=120.0, on_text=None: plain(body, timeout=max(timeout, 10800.0))
    server.start()
    out_path = RUNS / f"{a.label}.dudas.jsonl"
    try:
        server.wait_ready(10800)
        with open(out_path, "w", encoding="utf-8") as out:
            for arm in a.arms.split(";"):
                os.environ["BAXY_AYUDAS"] = arm
                mind = Mind(server, work / f"{a.label}.trace.jsonl")
                mind.configure(catalog)
                mind.warm()
                mind._clock = lambda: CLOCK  # one clock for every arm and seed
                print(f"arm {arm[:60]}: {len(mind.tools)} tools, prefix {mind.prefix_tokens} tokens", flush=True)
                replayer = Replay(mind)
                for case in cases:
                    for seed in (int(s) for s in a.seeds.split(",")):
                        try:
                            row = replay(mind, case, seed, arm, replayer) if case.get("steps") else decide(mind, case, seed)
                            error = None
                        except Exception as exc:  # noqa: BLE001
                            row, error = {}, repr(exc)[:300]
                        row = {"case": case["id"], "seed": seed, "arm": arm, **row, "error": error}
                        out.write(json.dumps(row, ensure_ascii=False) + "\n")
                        out.flush()
                        print(case["id"], seed, row.get("first"), row.get("confidence"), row.get("held"), row.get("kind"),
                              row.get("operation"), "|", row.get("reply") or error, flush=True)
    finally:
        server.close()


if __name__ == "__main__":
    main()
