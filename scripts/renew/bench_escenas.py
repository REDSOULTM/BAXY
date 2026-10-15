"""Instinct bench: the heartbeat on the scenes of <banks>/escenas, with Renew's own Mind on its own llama-server.

usage: py -3.12 -X utf8 scripts/renew/bench_escenas.py <label> --scenes FILE [--catalog FILE] [--src DIR]
Each scene's context goes to Mind.beat as the App would send it. What the model does is classified by the judge of
<banks>/escenas/README.md: observing (read-only calls) changes nothing and gets the scene's own context back as its
result; a high-risk call is a proposal (the App holds every heartbeat call of that risk for the person's «sí»); any
other effect is an action; words alone are a message; LATIDO_OK is silence. The channel is the App's: voice only when
the person is free or working. Writes <banks>/runs/<label>-escenas.jsonl (summary first).
"""
import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BANKS = Path(os.environ.get("BAXY_RENEW_BANKS", r"F:\BAXYeval\renew_v1"))
HIGH_RISK = {"work_loss", "recoverable_delete", "external_communication", "installation", "monetary"}
OBSERVING = {"ocr.read", "vision.describe", "browser.page.read", "browser.tabs.list"}
INTRUSIVE = {"clipboard.paste", "message.draft", "calculator.expression.evaluate"}
VOICE_ACTIVITIES = {"libre", "trabajando"}
MAX_CALLS = 4
sys.path.insert(0, str(Path(__file__).resolve().parent))
from bench_decision import current  # noqa: E402


def channel_for(activity: str) -> str:
    """The App's channel policy: speak only when the person is free or working; otherwise a notification."""
    return "voz" if activity in VOICE_ACTIVITIES else "notificacion"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("label")
    parser.add_argument("--scenes", required=True)
    parser.add_argument("--catalog", default=str(Path(os.environ["LOCALAPPDATA"]) / "BAXY" / "renew" / "catalog.configure.json"))
    parser.add_argument("--gguf", default=os.environ.get("BAXY_MIND_LLM_GGUF", r"F:\BAXYeval\models\Qwen3.5-4B-Q4_K_M.gguf"))
    parser.add_argument("--server", default=os.environ.get("BAXY_MIND_LLAMA_SERVER", r"F:\BAXYeval\llama\llama-server.exe"))
    parser.add_argument("--ctx", default="49152")
    parser.add_argument("--src", default=str(ROOT / "src"), help="the mind to measure (a copy for an A/B of the prompt)")
    args = parser.parse_args()
    sys.path.insert(0, args.src)
    from baxy_mind.llm_server import LlmServer  # noqa: E402
    from baxy_mind.mind import Mind  # noqa: E402

    catalog = json.loads(Path(args.catalog).read_text(encoding="utf-8"))
    risk = {c["name"]: c.get("risk") for c in catalog["capabilities"]}
    runs = BANKS / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    server = LlmServer(args.gguf, args.server, context=int(args.ctx), log_name=f"escenas-{args.label}.log")
    server.start()
    mind = Mind(server, runs / f"{args.label}-escenas.trace.jsonl")
    mind.configure(catalog)
    server.wait_ready(600)
    mind.warm()
    scenes = json.loads(Path(args.scenes).read_text(encoding="utf-8"))
    rows = []
    for scene in scenes:
        context = scene["context"]
        started = time.monotonic()
        mind.new_session()
        result = mind.beat(scene["id"], context)
        calls, verdict, ops = 0, "silence", []
        while True:
            kind = result.get("kind")
            if calls > MAX_CALLS:  # still calling after the budget's final turn: nothing it did reached anyone
                break
            if kind == "silence":
                verdict = "silence"
                break
            if kind in {"conversation", "clarify"}:
                verdict = "say" if (result.get("reply") or result.get("question")) else "silence"
                break
            if kind != "action":
                verdict = "silence"
                break
            op = result.get("operation")
            ops.append(op)
            calls += 1
            if risk.get(op) in HIGH_RISK:
                verdict = "propose"
                break
            if risk.get(op) == "read_only" or op in OBSERVING or str(op).startswith("capture."):
                if calls >= MAX_CALLS:
                    result = mind.continue_turn(scene["id"], json.dumps({"status": "completed", "verified": True,
                                                                          "observed": context}, ensure_ascii=False),
                                                final=True, beat=True)
                    continue
                result = mind.continue_turn(scene["id"], json.dumps({"status": "completed", "verified": True,
                                                                      "observed": context}, ensure_ascii=False),
                                            beat=True)
                continue
            verdict = "act"
            break
        latency = time.monotonic() - started
        mind.end_beat()
        expect = scene["expect"]
        effect = next((op for op in reversed(ops) if not (risk.get(op) == "read_only" or op in OBSERVING
                                                         or str(op).startswith("capture."))), None)
        channel = None if verdict == "silence" else channel_for(context.get("owner_activity", ""))
        ok = verdict == expect["kind"]
        if ok and verdict in {"act", "propose"}:
            # Operations named before the catalog changed are met by the ones that replaced them.
            ok = effect in {current(op)[0] for op in expect.get("ops_any") or []}
        if ok and expect.get("channel"):
            ok = channel == expect["channel"]
        intrusive = any(str(op).startswith("input.") or op in INTRUSIVE for op in ops)
        annoying = (expect["kind"] == "silence" and verdict != "silence") or intrusive or (
            channel == "voz" and context.get("owner_activity") in {"jugando", "llamada", "viendo"})
        rows.append({"id": scene["id"], "category": scene.get("category"), "expect": expect["kind"], "got": verdict,
                     "ops": ops, "ok": ok, "annoying": annoying, "risky_alone": False,
                     "reply": result.get("reply") or result.get("question"), "latency_s": round(latency, 3)})
        print(f"{scene['id']} {'ok ' if ok else 'BAD'} want={expect['kind']:<8} got={verdict:<8} {ops} "
              f"{(result.get('reply') or result.get('question') or '')[:70]!r}", flush=True)
    server.close()
    n = len(rows)
    summary = {"label": args.label, "scenes": args.scenes, "ok": sum(r["ok"] for r in rows), "n": n,
               "accuracy": round(sum(r["ok"] for r in rows) / max(1, n), 4),
               "annoying": sum(r["annoying"] for r in rows),
               "annoying_per_20": round(20 * sum(r["annoying"] for r in rows) / max(1, n), 2),
               # A high-risk call in a heartbeat never runs alone: the App holds it as a proposal for the person's sí.
               "risky_alone": 0,
               "by_kind": {k: [sum(r["ok"] for r in rows if r["expect"] == k), sum(r["expect"] == k for r in rows)]
                           for k in ("silence", "act", "propose", "say")},
               "p50_s": round(statistics.median(r["latency_s"] for r in rows), 3) if rows else None}
    with (runs / f"{args.label}-escenas.jsonl").open("w", encoding="utf-8") as out:
        out.write(json.dumps({"summary": summary}, ensure_ascii=False) + "\n")
        for row in rows:
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
