"""Session report tool for VoiceRecorder manifests.

Reads ~/.gemma4/recordings/<session>/manifest.jsonl (or a path,
or "most recent") and produces a per-session summary: wake
phrases, wake-confidence distribution, STT health, TTS metrics,
and end-to-end latency for the happy-path turns.

Output forms:
  - stdout summary (default)
  - --json OUT.json (structured, includes a bench_compat block)
  - --md OUT.md (human-readable markdown)
  - --quiet (suppress stdout but still write --json/--md)

Examples:
  python scripts/session_report.py
  python scripts/session_report.py 20260518_193600
  python scripts/session_report.py /full/path/to/manifest.jsonl
  python scripts/session_report.py --json out.json --quiet

Eligible-for-E2E definition (matches docs/PRODUCTION_READY.md):
  whisper_transcription non-empty AND tts_samples > 0.
  Rejected or silent turns are NOT counted in the latency budget
  -- the 5s target is for wake-to-reply, not wake-to-silent.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# audio_io.SAMPLE_RATE is the authoritative constant; resolve
# without forcing the whole gemma4_agent package to import.
SAMPLE_RATE = 16000

RECORDINGS_DIR = Path.home() / ".gemma4" / "recordings"
LOW_CONFIDENCE_THRESHOLD = 0.85


@dataclass
class TurnRecord:
    turn_id: str
    duration_s: float
    wake_phrase: str
    wake_confidence: float
    tts_samples: int
    tts_duration_s: float
    whisper_transcription: str | None
    whisper_raw_text: str | None
    was_rejected: bool
    stt_reject_reason: str | None
    had_tts_reply: bool
    manual_correction: str


@dataclass
class SessionReport:
    session_id: str
    manifest_path: str
    turn_count: int
    turns: list[TurnRecord]

    # Wake
    wake_phrases_seen: dict[str, int]
    wake_confidence_p50: float | None
    wake_confidence_p95: float | None
    wake_low_confidence_count: int

    # STT
    transcribed_count: int
    rejected_count: int
    reject_reasons: dict[str, int]
    silent_count: int

    # TTS
    replied_count: int
    tts_duration_p50: float | None
    tts_duration_p95: float | None

    # E2E (happy-path only)
    e2e_durations_s: list[float]
    e2e_p50: float | None
    e2e_p95: float | None
    e2e_max: float | None

    # Where it came from, for the bench compat block.
    happy_path_eligible: int = 0


def _percentile(values: list[float], q: float) -> float | None:
    """Return the q-th percentile (q in [0, 100]) or None if empty.

    Uses linear interpolation between closest ranks. Matches numpy
    default behavior closely enough for our purposes — we don't pull
    numpy in just for this.
    """
    if not values:
        return None
    s = sorted(values)
    if len(s) == 1:
        return float(s[0])
    k = (len(s) - 1) * (q / 100.0)
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    frac = k - lo
    return float(s[lo] + (s[hi] - s[lo]) * frac)


def _resolve_manifest(arg: str | None) -> Path:
    """Resolve a session id, a path, or None (most recent) to a
    manifest.jsonl path. Raises FileNotFoundError with a clear
    message if nothing matches."""
    if arg is not None:
        p = Path(arg)
        if p.is_file():
            return p
        # Treat as session id under recordings dir.
        candidate = RECORDINGS_DIR / arg / "manifest.jsonl"
        if candidate.is_file():
            return candidate
        raise FileNotFoundError(
            f"Could not resolve '{arg}' as a manifest path or session id. "
            f"Looked for: {p}, {candidate}"
        )
    # No arg: pick the most recent session in RECORDINGS_DIR.
    if not RECORDINGS_DIR.is_dir():
        raise FileNotFoundError(
            f"No recordings dir at {RECORDINGS_DIR}. "
            f"Run a voice session first, or pass an explicit path."
        )
    manifests = list(RECORDINGS_DIR.glob("*/manifest.jsonl"))
    if not manifests:
        raise FileNotFoundError(
            f"No manifest.jsonl found under {RECORDINGS_DIR}. "
            f"Run a voice session first."
        )
    return max(manifests, key=lambda p: p.stat().st_mtime)


def _read_turns(manifest_path: Path) -> list[TurnRecord]:
    turns: list[TurnRecord] = []
    with open(manifest_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                # Be tolerant of partial/broken lines; the manifest
                # is append-only and the recorder can be killed mid-write.
                continue
            tts_samples = int(e.get("tts_samples") or 0)
            transcription = e.get("whisper_transcription")
            reject_reason = e.get("stt_reject_reason")
            turns.append(TurnRecord(
                turn_id=str(e.get("turn_id", "")),
                duration_s=float(e.get("duration_s") or 0.0),
                wake_phrase=str(e.get("wake_phrase") or ""),
                wake_confidence=float(e.get("wake_confidence") or 0.0),
                tts_samples=tts_samples,
                tts_duration_s=tts_samples / SAMPLE_RATE,
                whisper_transcription=transcription if transcription else None,
                whisper_raw_text=e.get("whisper_raw_text"),
                was_rejected=reject_reason is not None,
                stt_reject_reason=reject_reason,
                had_tts_reply=tts_samples > 0,
                manual_correction=str(e.get("manual_correction") or ""),
            ))
    return turns


def build_report(manifest_path: Path) -> SessionReport:
    turns = _read_turns(manifest_path)
    session_id = manifest_path.parent.name

    # Wake aggregates.
    wake_phrases_seen: dict[str, int] = dict(
        Counter(t.wake_phrase for t in turns if t.wake_phrase)
    )
    confidences = [t.wake_confidence for t in turns if t.wake_confidence > 0]
    wake_low = sum(
        1 for t in turns if 0 < t.wake_confidence < LOW_CONFIDENCE_THRESHOLD
    )

    # STT health.
    transcribed = sum(1 for t in turns if t.whisper_transcription)
    rejected = sum(1 for t in turns if t.was_rejected)
    reject_reasons: dict[str, int] = dict(
        Counter(t.stt_reject_reason for t in turns
                if t.stt_reject_reason is not None)
    )
    silent = sum(
        1 for t in turns
        if not t.whisper_raw_text and not t.was_rejected
    )

    # TTS.
    replied = sum(1 for t in turns if t.had_tts_reply)
    tts_durations = [t.tts_duration_s for t in turns if t.had_tts_reply]

    # E2E happy-path: transcription non-empty AND TTS reply present.
    happy = [
        t for t in turns
        if t.whisper_transcription and t.had_tts_reply
    ]
    e2e = [t.duration_s for t in happy]

    return SessionReport(
        session_id=session_id,
        manifest_path=str(manifest_path),
        turn_count=len(turns),
        turns=turns,
        wake_phrases_seen=wake_phrases_seen,
        wake_confidence_p50=_percentile(confidences, 50),
        wake_confidence_p95=_percentile(confidences, 95),
        wake_low_confidence_count=wake_low,
        transcribed_count=transcribed,
        rejected_count=rejected,
        reject_reasons=reject_reasons,
        silent_count=silent,
        replied_count=replied,
        tts_duration_p50=_percentile(tts_durations, 50),
        tts_duration_p95=_percentile(tts_durations, 95),
        e2e_durations_s=e2e,
        e2e_p50=_percentile(e2e, 50),
        e2e_p95=_percentile(e2e, 95),
        e2e_max=max(e2e) if e2e else None,
        happy_path_eligible=len(happy),
    )


# --- Formatting ----------------------------------------------------

def _fmt_pct(num: int, denom: int) -> str:
    if denom <= 0:
        return "0%"
    return f"{round(100 * num / denom)}%"


def _fmt_optional(v: float | None, suffix: str = "") -> str:
    if v is None:
        return "--"
    return f"{v:.2f}{suffix}"


def render_stdout(rep: SessionReport) -> str:
    lines: list[str] = []
    lines.append(f"Session report: {rep.session_id}")
    lines.append(f"  Manifest: {rep.manifest_path}")
    lines.append(f"  Turns:    {rep.turn_count}")
    lines.append("")

    lines.append("Wake")
    if rep.wake_phrases_seen:
        phrases_str = ", ".join(
            f"{k} ({v})"
            for k, v in sorted(
                rep.wake_phrases_seen.items(), key=lambda kv: -kv[1]
            )
        )
    else:
        phrases_str = "(none)"
    lines.append(f"  Phrases:        {phrases_str}")
    lines.append(
        f"  Confidence:     p50={_fmt_optional(rep.wake_confidence_p50)} "
        f"p95={_fmt_optional(rep.wake_confidence_p95)} "
        f"low={rep.wake_low_confidence_count}"
    )
    lines.append("")

    lines.append("STT")
    lines.append(
        f"  Transcribed:    {rep.transcribed_count} / {rep.turn_count} "
        f"({_fmt_pct(rep.transcribed_count, rep.turn_count)})"
    )
    if rep.reject_reasons:
        reasons_str = ", ".join(
            f"{k} ({v})"
            for k, v in sorted(
                rep.reject_reasons.items(), key=lambda kv: -kv[1]
            )
        )
        lines.append(
            f"  Rejected:       {rep.rejected_count}        "
            f"[reasons: {reasons_str}]"
        )
    else:
        lines.append(f"  Rejected:       {rep.rejected_count}")
    lines.append(f"  Silent:         {rep.silent_count}")
    lines.append("")

    lines.append("TTS")
    lines.append(
        f"  Replied:        {rep.replied_count} / {rep.turn_count} "
        f"({_fmt_pct(rep.replied_count, rep.turn_count)})"
    )
    lines.append(
        f"  TTS duration:   p50={_fmt_optional(rep.tts_duration_p50, 's')}  "
        f"p95={_fmt_optional(rep.tts_duration_p95, 's')}"
    )
    lines.append("")

    if rep.happy_path_eligible > 0:
        lines.append(
            f"E2E latency (happy path only, n={rep.happy_path_eligible})"
        )
        lines.append(
            f"  p50={_fmt_optional(rep.e2e_p50, 's')}  "
            f"p95={_fmt_optional(rep.e2e_p95, 's')}  "
            f"max={_fmt_optional(rep.e2e_max, 's')}"
        )
    else:
        lines.append(
            f"E2E latency: N/A (no happy-path turns: replied={rep.replied_count})"
        )
    lines.append("")

    lines.append("bench_compat (consumable by scripts/bench.py --session-jsonl):")
    lines.append(
        f"  n_e2e_eligible={rep.happy_path_eligible}  "
        f"voice_e2e_p95={_fmt_optional(rep.e2e_p95)}"
    )

    return "\n".join(lines)


def render_md(rep: SessionReport) -> str:
    # Markdown variant: same content with table-friendly formatting.
    lines: list[str] = []
    lines.append(f"# Session report — `{rep.session_id}`")
    lines.append("")
    lines.append(f"- Manifest: `{rep.manifest_path}`")
    lines.append(f"- Turns: **{rep.turn_count}**")
    lines.append("")
    lines.append("## Wake")
    lines.append("")
    if rep.wake_phrases_seen:
        lines.append("| Phrase | Count |")
        lines.append("|---|---|")
        for k, v in sorted(
            rep.wake_phrases_seen.items(), key=lambda kv: -kv[1]
        ):
            lines.append(f"| `{k}` | {v} |")
    else:
        lines.append("_(no wake phrases)_")
    lines.append("")
    lines.append(
        f"- Confidence p50: {_fmt_optional(rep.wake_confidence_p50)}"
    )
    lines.append(
        f"- Confidence p95: {_fmt_optional(rep.wake_confidence_p95)}"
    )
    lines.append(
        f"- Low-confidence (<{LOW_CONFIDENCE_THRESHOLD}): "
        f"{rep.wake_low_confidence_count}"
    )
    lines.append("")
    lines.append("## STT")
    lines.append("")
    lines.append(
        f"- Transcribed: {rep.transcribed_count} / {rep.turn_count} "
        f"({_fmt_pct(rep.transcribed_count, rep.turn_count)})"
    )
    lines.append(f"- Rejected: {rep.rejected_count}")
    if rep.reject_reasons:
        for k, v in sorted(
            rep.reject_reasons.items(), key=lambda kv: -kv[1]
        ):
            lines.append(f"  - `{k}`: {v}")
    lines.append(f"- Silent: {rep.silent_count}")
    lines.append("")
    lines.append("## TTS")
    lines.append("")
    lines.append(
        f"- Replied: {rep.replied_count} / {rep.turn_count}"
    )
    lines.append(
        f"- TTS duration p50/p95: "
        f"{_fmt_optional(rep.tts_duration_p50, 's')} / "
        f"{_fmt_optional(rep.tts_duration_p95, 's')}"
    )
    lines.append("")
    lines.append("## E2E latency (happy path only)")
    lines.append("")
    if rep.happy_path_eligible > 0:
        lines.append(f"- Eligible turns: {rep.happy_path_eligible}")
        lines.append(f"- p50: {_fmt_optional(rep.e2e_p50, 's')}")
        lines.append(f"- p95: {_fmt_optional(rep.e2e_p95, 's')}")
        lines.append(f"- max: {_fmt_optional(rep.e2e_max, 's')}")
    else:
        lines.append("_No happy-path turns._")
    return "\n".join(lines)


def report_to_json(rep: SessionReport) -> dict[str, Any]:
    payload = asdict(rep)
    # Top-level bench_compat block (mirrors what bench.py expects).
    payload["bench_compat"] = {
        "voice_e2e_p95_eligible_turns": rep.happy_path_eligible,
        "voice_e2e_p95": rep.e2e_p95,
        "voice_e2e_p50": rep.e2e_p50,
        "voice_e2e_max": rep.e2e_max,
        "manifest_used": rep.manifest_path,
    }
    return payload


# --- CLI -----------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read a VoiceRecorder manifest.jsonl and print/save a report."
    )
    parser.add_argument(
        "session", nargs="?", default=None,
        help="Session id (resolves under ~/.gemma4/recordings/) or full "
             "manifest path. Omit for most-recent session.",
    )
    parser.add_argument("--json", dest="json_out", type=Path, default=None,
                        help="Write structured JSON to this path.")
    parser.add_argument("--md", dest="md_out", type=Path, default=None,
                        help="Write markdown report to this path.")
    parser.add_argument("--quiet", action="store_true",
                        help="Suppress stdout (still writes --json/--md).")
    args = parser.parse_args(argv)

    try:
        manifest = _resolve_manifest(args.session)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    rep = build_report(manifest)

    if not args.quiet:
        print(render_stdout(rep))

    if args.json_out is not None:
        args.json_out.write_text(
            json.dumps(report_to_json(rep), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    if args.md_out is not None:
        args.md_out.write_text(render_md(rep), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
