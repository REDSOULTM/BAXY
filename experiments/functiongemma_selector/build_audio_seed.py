"""Build a disjoint technical seed corpus for the audio-family LoRA smoke."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
from pathlib import Path
from typing import Any

from selector_common import (
    NO_ACTION_OPERATION,
    REPO,
    catalog_by_name,
    family_operations,
    normalize_text,
    read_jsonl,
    selection_tools,
    sha256,
    write_jsonl,
)

DEFAULT_SOURCE = REPO / "src" / "baxy_mind" / "data" / "intent_bank.jsonl"
DEFAULT_HELDOUT = (
    REPO
    / "experiments"
    / "mind_router_spike"
    / "data"
    / "exact_operation_development.v1.jsonl"
)
DEFAULT_OUTPUT = REPO / "artifacts" / "research" / "functiongemma_audio_seed.v1.jsonl"

DIRECT_LABELS = {
    "audio.volume",
    "audio.mute",
    "audio.status",
}
REMAPPED_LABELS = {
    "ABSTAIN__relative_volume": "audio.volume.adjust",
    "ABSTAIN__microphone": "audio.microphone.mute",
}
NO_ACTION_LABELS = {
    "ABSTAIN__app_specific_audio",
    "ABSTAIN__hardware_knowledge",
    "ABSTAIN__media_control",
    "ABSTAIN__negated_command",
    "ABSTAIN__statement_no_request",
}

# Disjoint additions cover the two new leaves more symmetrically. They are
# authored here, never copied from the exact-operation development oracle.
AUTHORED = [
    ("es", "Aumenta ocho puntos el sonido del equipo.", "audio.volume.adjust"),
    ("es", "Redúceme doce puntos el volumen general.", "audio.volume.adjust"),
    ("es", "Dale un poco más de volumen al computador.", "audio.volume.adjust"),
    ("en", "Turn the system sound up by eight points.", "audio.volume.adjust"),
    ("en", "Drop the master volume twelve points.", "audio.volume.adjust"),
    ("en", "Make the computer audio a little louder.", "audio.volume.adjust"),
    ("es", "Pon en mudo el micro del computador.", "audio.microphone.mute"),
    ("es", "Vuelve a activar el micrófono del sistema.", "audio.microphone.mute"),
    ("es", "Desmutea mi micro, por favor.", "audio.microphone.mute"),
    ("en", "Silence the computer microphone.", "audio.microphone.mute"),
    ("en", "Unmute the system microphone.", "audio.microphone.mute"),
    ("en", "Disable microphone mute on this PC.", "audio.microphone.mute"),
]


def _language(text: str) -> str:
    english = {
        "the",
        "sound",
        "volume",
        "mute",
        "computer",
        "current",
        "turn",
        "what",
        "please",
    }
    tokens = set(normalize_text(text).split())
    return "en" if len(tokens & english) >= 2 else "es"


def build(source: Path, heldout: Path) -> list[dict[str, Any]]:
    catalog = catalog_by_name()
    audio_operations = family_operations(catalog, "audio")
    required = {
        "audio.microphone.mute",
        "audio.mute",
        "audio.status",
        "audio.volume",
        "audio.volume.adjust",
    }
    if set(audio_operations) != required:
        raise ValueError(f"unexpected audio catalog: {audio_operations}")
    tools = selection_tools(
        catalog, [*audio_operations, NO_ACTION_OPERATION]
    )
    heldout_texts = {
        normalize_text(str(row["text"])) for row in read_jsonl(heldout)
    }
    candidates: list[tuple[str, str, str, str]] = []
    for row in read_jsonl(source):
        label = str(row.get("label") or "")
        text = str(row.get("text") or "").strip()
        operation = (
            label
            if label in DIRECT_LABELS
            else REMAPPED_LABELS.get(label)
            if label in REMAPPED_LABELS
            else NO_ACTION_OPERATION
            if label in NO_ACTION_LABELS
            else None
        )
        if operation and text:
            candidates.append((_language(text), text, operation, f"historical:{label}"))
    for language, text, operation in AUTHORED:
        candidates.append((language, text, operation, "authored:audio-seed-v1"))

    deduplicated: dict[str, tuple[str, str, str, str]] = {}
    for candidate in candidates:
        normalized = normalize_text(candidate[1])
        if normalized in heldout_texts:
            continue
        prior = deduplicated.get(normalized)
        if prior is not None and prior[2] != candidate[2]:
            raise ValueError(
                f"conflicting labels for normalized text {normalized!r}: "
                f"{prior[2]} vs {candidate[2]}"
            )
        deduplicated[normalized] = candidate

    rows: list[dict[str, Any]] = []
    for normalized, (language, text, operation, source_id) in sorted(
        deduplicated.items()
    ):
        case_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        rows.append(
            {
                "schema": "baxy.functiongemma-selection-row.v1",
                "case_id": f"audio-seed-{case_hash[:16]}",
                "language": language,
                "text": text,
                "operation": operation,
                "family": "audio",
                "source": source_id,
                "tools": tools,
            }
        )
    counts = collections.Counter(row["operation"] for row in rows)
    missing = required - counts.keys()
    if missing:
        raise ValueError(f"seed has no examples for: {sorted(missing)}")
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--heldout", type=Path, default=DEFAULT_HELDOUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    rows = build(args.source.resolve(strict=True), args.heldout.resolve(strict=True))
    write_jsonl(args.output, rows)
    report: dict[str, Any] = {
        "schema": "baxy.functiongemma-audio-seed-build.v1",
        "rows": len(rows),
        "counts": dict(collections.Counter(row["operation"] for row in rows)),
        "languages": dict(collections.Counter(row["language"] for row in rows)),
        "heldout_overlap": 0,
        "source_sha256": sha256(args.source),
        "heldout_sha256": sha256(args.heldout),
        "output": str(args.output.resolve()),
        "output_sha256": sha256(args.output),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

