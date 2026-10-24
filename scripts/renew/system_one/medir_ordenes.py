"""Laya's two orders (SystemOne.choose) one after the other against both at once, on a running CPU server of its own.

usage: py -3.12 -X utf8 scripts/renew/system_one/medir_ordenes.py --url http://127.0.0.1:PORT --catalog FILE [--n 20]
       [--out FILE]
Three questions shaped as the trace's (the tools Qwen nearly chose, ask_user, answering in words), each asked in both
orders: «seq» as choose asks them, «par» both at once from two threads (it gains only on a server with -np 2). Prints
p50 and min ms per question; --out keeps each order's probabilities, to compare two servers. Writes nothing else.
Measured 2026-10-23 (layam-long-s1-Q8_0, b11609, -ngl 0 -dev none -b 2048 -ub 2048, the PC in use; n 20):
-t 4 -np 1 -c 4096 (the product): seq 637 / 520 / 398 ms; -t 4 -np 2 -c 8192: seq 662 / 496 / 401, par 650 / 497 / 401,
the same probabilities to the last digit, working set 458 → 474 MiB. Both at once gain nothing: the encoder's pass is
bound by the CPU, and two in one batch cost what two in a row do. Its prompt cannot be kept either: the encoder reads
every token against every other (no prefix to reuse), and the second order changes every token's place. -t 8 (-np 2):
seq 531 / 450 / 313 (−15 to −22 %), but the probabilities move (up to 0.0007): another thread count is not the same
answer. Laya is asked only in a turn.decide where Qwen doubted (BAXY_S1_VETO), never in turn.continue.
"""
import argparse
import json
import statistics
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
QUESTIONS = (
    ("guindous tiene parches esperando para instalarse", [],
     ["game_catalog_list", "system_application_crash_diagnose", "web_search"]),
    ("cierra el spotify", [{"role": "user", "content": "pon música"},
                           {"role": "assistant", "content": "Puse Queen en Spotify."}], ["app_close", "media_control"]),
    ("sube el briyo quince desde donde esta", [], ["system_settings_adjust", "audio_volume"]),
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--n", type=int, default=20)
    parser.add_argument("--out", default="")
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT / "src"))
    from baxy_mind.mind import Mind  # noqa: E402
    from baxy_mind.system_one import ANSWER, ASK, OPTION_TEXT, QUESTION, short, state_text  # noqa: E402

    class _NoServer:
        context = 53248

    with tempfile.TemporaryDirectory() as scratch:  # configure keeps the catalog beside the trace
        mind = Mind(_NoServer(), Path(scratch) / "trace.jsonl")  # type: ignore[arg-type]
        mind.configure(json.loads(Path(args.catalog).read_text(encoding="utf-8")))
    described = {t["function"]["name"]: short(t["function"]["description"]) for t in mind.tools}

    def ask(text: str, history: list, options: dict) -> dict:
        body = {"state": state_text(text, history),
                "questions": {"operacion": {"type": "choice", "instructions": QUESTION, "criteria": options}}}
        request = urllib.request.Request(args.url.rstrip("/") + "/v1/systemone", data=json.dumps(body).encode("utf-8"),
                                         headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=30) as reply:
            return json.loads(reply.read())["answers"]["operacion"]

    def both(text: str, history: list, options: dict, at_once: bool) -> list:
        orders = [list(options), list(reversed(options))]
        if not at_once:
            return [ask(text, history, {k: options[k] for k in order}) for order in orders]
        answers: list = [None, None]

        def one(index: int) -> None:
            answers[index] = ask(text, history, {k: options[k] for k in orders[index]})
        threads = [threading.Thread(target=one, args=(index,)) for index in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        return answers

    kept: dict = {}
    for mode in ("seq", "par"):
        for text, history, names in QUESTIONS:
            options = {**{k: described[k] for k in names if k in described}, ASK: OPTION_TEXT[ASK],
                       ANSWER: OPTION_TEXT[ANSWER]}
            both(text, history, options, mode == "par")  # warm
            times = []
            for _ in range(args.n):
                started = time.perf_counter()
                answers = both(text, history, options, mode == "par")
                times.append((time.perf_counter() - started) * 1000)
            kept[f"{mode} {text}"] = [answer.get("probabilities") for answer in answers]
            print(f"{mode} {text[:40]:<40} p50 {statistics.median(times):6.1f} ms  min {min(times):6.1f}")
    if args.out:
        Path(args.out).write_text(json.dumps(kept, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
