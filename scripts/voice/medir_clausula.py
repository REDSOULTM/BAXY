"""What the first clause as the first take (BAXY_RENEW_TTS_CLAUSE, src/baxy_mind/voice_output.py) would change on a set
of replies, offline: nothing is played and the product does not run.

    <mind-runtime python> -X utf8 scripts/voice/medir_clausula.py REPLIES [--campo text] [--sintetizar] [--max N]

REPLIES: one reply per line, or JSON lines whose --campo field is the reply (rows without it are skipped). Per reply,
voice_output's own takes with the switch off and on. The summary: how many replies have their first take cut at a
clause; the first take's characters off and on (p50); and what the model still writes after the clause closes before
its sentence closes, in characters (p50, p90): the voice no longer waits for that part.

--sintetizar (BAXY_RENEW_TTS_DIR: the voice; CPU, as the product synthesizes): for the replies that are cut, the first
take's synthesis (ms) off and on, the clause's voice (s) and the rest's synthesis (ms); «seca» counts the replies whose
rest takes longer to synthesize than the clause sounds, where the pause at the clause grows past GAP_CLAUSE_S.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from baxy_mind import voice_output  # noqa: E402
from baxy_mind.voice_output import Speech  # noqa: E402


def replies(path: Path, field: str) -> list[str]:
    found = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("{"):
            text = json.loads(line).get(field)
            if isinstance(text, str) and text.strip():
                found.append(" ".join(text.split()))
        else:
            found.append(line)
    return found


def takes(text: str, clause: bool) -> list[str]:
    before = os.environ.get("BAXY_RENEW_TTS_CLAUSE")
    os.environ["BAXY_RENEW_TTS_CLAUSE"] = "1" if clause else "0"
    try:
        return Speech._takes(Speech._units(text), text)
    finally:
        if before is None:
            os.environ.pop("BAXY_RENEW_TTS_CLAUSE")
        else:
            os.environ["BAXY_RENEW_TTS_CLAUSE"] = before


def pct(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(q * len(ordered)))]


def voice() -> Speech:
    speech = Speech(lambda speaking: None, lambda *spoken: None)
    while not speech._ready.wait(1.0):
        pass
    if speech.failure:
        raise SystemExit(f"la voz no cargó: {speech.failure}")
    return speech


def timed(speech: Speech, text: str) -> tuple[int, float]:
    """(synthesis ms, voice s without the pause after it)."""
    started = time.perf_counter()
    audio = speech._synthesize(text, pause=False)
    return round((time.perf_counter() - started) * 1000), round(len(audio) / speech.rate, 2)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("replies", type=Path)
    parser.add_argument("--campo", default="text")
    parser.add_argument("--sintetizar", action="store_true")
    parser.add_argument("--max", type=int, default=0)
    args = parser.parse_args()
    texts = replies(args.replies, args.campo)[: args.max or None]
    speech = voice() if args.sintetizar else None
    rows, first_off, first_on, ahead, synth_off, synth_on, clause_s, rest_ms, dry = [], [], [], [], [], [], [], [], 0
    for text in texts:
        off, on = takes(text, False), takes(text, True)
        cut = len(on) > len(off)
        first_off.append(len(off[0]))
        first_on.append(len(on[0]))
        row = {"text": text, "cut": cut, "first_off": off[0], "first_on": on[0]}
        if cut:
            ahead.append(len(off[0]) - len(on[0]))
            if speech is not None:
                whole_ms, _ = timed(speech, off[0])
                head_ms, head_s = timed(speech, on[0])
                tail_ms, _ = timed(speech, on[1])
                synth_off.append(whole_ms)
                synth_on.append(head_ms)
                clause_s.append(head_s)
                rest_ms.append(tail_ms)
                dry += tail_ms / 1000 > head_s
                row.update(synth_off_ms=whole_ms, synth_on_ms=head_ms, clause_s=head_s, rest_ms=tail_ms)
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False))
    summary = {
        "replies": len(texts), "cut": sum(row["cut"] for row in rows),
        "first_chars_p50": {"off": pct(first_off, 0.5), "on": pct(first_on, 0.5)},
        "written_after_clause_chars": {"p50": pct(ahead, 0.5), "p90": pct(ahead, 0.9)},
    }
    if speech is not None:
        summary["synthesis"] = {
            "first_ms_p50": {"off": pct(synth_off, 0.5), "on": pct(synth_on, 0.5)},
            "clause_s_p50": pct(clause_s, 0.5), "rest_ms_p50": pct(rest_ms, 0.5), "seca": dry,
            "mean_saved_ms": round(statistics.fmean(a - b for a, b in zip(synth_off, synth_on))) if synth_on else None,
        }
        speech.close()
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print(f"GAP_CLAUSE_S={voice_output.GAP_CLAUSE_S} CLAUSE_MIN_CHARS={voice_output.CLAUSE_MIN_CHARS} "
          f"CLAUSE_MIN_WORDS={voice_output.CLAUSE_MIN_WORDS}", file=sys.stderr)


if __name__ == "__main__":
    main()
