"""Extrae los casos de los oráculos congelados hacia data/router_cases.jsonl.

Fuentes (solo lectura, árbol de Codex intacto):
- tests/Baxy.Integration.Tests/HistoricalNaturalNoteRoutingTests.cs
- tests/Baxy.Integration.Tests/HistoricalSystemStatusRoutingTests.cs
- tests/Baxy.Integration.Tests/HistoricalAudioRoutingTests.cs
- tests/data/gpu_status_corpus_oracle.json
- tests/data/memory_corpus_oracle.json
- tests/data/historical_messages.jsonl (text_literal por message_id)

Etiquetas:
- Positivos: nombre de operación canónica (+ ":scope" para system.status).
- Negativos duros y composiciones: "ABSTAIN" (fail-closed en el router).
- Memoria: positivos → memory.<op>; los negativos de memoria son contratos de
  política (confirmación, etc.), se etiquetan ABSTAIN_POLICY y se reportan
  aparte para no mezclar routing con política.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
TESTS = REPO / "tests"
OUT = Path(__file__).resolve().parent / "data" / "router_cases.jsonl"

if __package__ in {None, ""}:
    sys.path.insert(0, str(REPO / "src"))

from baxy_mind.tools.atomic_output import replace_bytes_atomically  # noqa: E402

MSG_ID = re.compile(r'"(msg_[0-9a-f]{20})"')


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def ids_in(block: str) -> list[str]:
    return MSG_ID.findall(block)


def block_between(text: str, start_marker: str, end_marker: str) -> str:
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    return text[start:end]


def extract_notes() -> list[dict]:
    src = read(TESTS / "Baxy.Integration.Tests" / "HistoricalNaturalNoteRoutingTests.cs")
    pure = block_between(src, "PureCreateMessageIds =", "RequiredNegativeMessageIds =")
    neg = block_between(src, "RequiredNegativeMessageIds =", "[Test]")
    cases = [
        {"set": "note_create", "message_id": mid, "label": "note.create"}
        for mid in ids_in(pure)
    ]
    cases += [
        {"set": "note_negative", "message_id": mid, "label": "ABSTAIN"}
        for mid in ids_in(neg)
    ]
    return cases


def extract_system_status() -> list[dict]:
    src = read(TESTS / "Baxy.Integration.Tests" / "HistoricalSystemStatusRoutingTests.cs")
    table = block_between(src, "FrozenOracle =", "[Test]")
    cases: list[dict] = []
    # Bloques ["scope"] = [ ids ]
    for match in re.finditer(r'\["([a-z_]+)"\]\s*=\s*\[(.*?)\]', table, re.DOTALL):
        scope, body = match.group(1), match.group(2)
        for mid in ids_in(body):
            cases.append(
                {
                    "set": "system_status",
                    "message_id": mid,
                    "label": f"system.status:{scope}",
                }
            )
    return cases


def extract_audio() -> list[dict]:
    src = read(TESTS / "Baxy.Integration.Tests" / "HistoricalAudioRoutingTests.cs")
    cases: list[dict] = []

    vol = block_between(src, "FrozenVolumeOracle =", "FrozenMuteOracle =")
    for match in re.finditer(r"\[(\d+)\]\s*=\s*\[(.*?)\]", vol, re.DOTALL):
        level, body = int(match.group(1)), match.group(2)
        for mid in ids_in(body):
            cases.append(
                {
                    "set": "audio_volume",
                    "message_id": mid,
                    "label": "audio.volume",
                    "expected_args": {"level": level},
                }
            )

    mute = block_between(src, "FrozenMuteOracle =", "FrozenNamedVolumeAliasOracle =")
    for match in re.finditer(r"\[(true|false)\]\s*=\s*\[(.*?)\]", mute, re.DOTALL):
        muted, body = match.group(1) == "true", match.group(2)
        for mid in ids_in(body):
            cases.append(
                {
                    "set": "audio_mute",
                    "message_id": mid,
                    "label": "audio.mute",
                    "expected_args": {"muted": muted},
                }
            )

    alias = block_between(src, "FrozenNamedVolumeAliasOracle =", "FrozenStatusOracle =")
    for match in re.finditer(r"\[(\d+)\]\s*=\s*\[(.*?)\]", alias, re.DOTALL):
        level, body = int(match.group(1)), match.group(2)
        for mid in ids_in(body):
            cases.append(
                {
                    "set": "audio_volume_alias",
                    "message_id": mid,
                    "label": "audio.volume",
                    "expected_args": {"level": level},
                }
            )

    status = block_between(src, "FrozenStatusOracle =", "FrozenHardNegatives =")
    for mid in ids_in(status):
        cases.append(
            {"set": "audio_status", "message_id": mid, "label": "audio.status"}
        )

    negatives = block_between(src, "FrozenHardNegatives =", "[Test]")
    for match in re.finditer(r'\["([a-z_]+)"\]\s*=\s*\[(.*?)\]', negatives, re.DOTALL):
        category, body = match.group(1), match.group(2)
        for mid in ids_in(body):
            cases.append(
                {
                    "set": "audio_negative",
                    "message_id": mid,
                    "label": "ABSTAIN",
                    "category": category,
                }
            )
    return cases


def extract_gpu() -> list[dict]:
    data = json.loads(read(TESTS / "data" / "gpu_status_corpus_oracle.json"))
    cases: list[dict] = []
    for group in data["canonical_cases"]:
        for mid in group["ids"]:
            cases.append(
                {
                    "set": "gpu_status",
                    "message_id": mid,
                    "label": f"system.status:{group['scope']}",
                }
            )
    for group in data["composition_cases"]:
        for mid in group["ids"]:
            cases.append(
                {
                    "set": "gpu_composition",
                    "message_id": mid,
                    "label": "ABSTAIN",
                    "category": group["category"],
                }
            )
    for group in data["hard_negative_cases"]:
        for mid in group["ids"]:
            cases.append(
                {
                    "set": "gpu_negative",
                    "message_id": mid,
                    "label": "ABSTAIN",
                    "category": group["category"],
                }
            )
    return cases


def extract_memory() -> list[dict]:
    data = json.loads(read(TESTS / "data" / "memory_corpus_oracle.json"))
    cases: list[dict] = []
    for group in data["canonical_cases"]:
        for mid in group["ids"]:
            cases.append(
                {
                    "set": "memory_positive",
                    "message_id": mid,
                    "label": group["operation"],
                    "expected_args": group.get("arguments"),
                }
            )
    for group in data["hard_negative_cases"]:
        for mid in group["ids"]:
            cases.append(
                {
                    "set": "memory_negative",
                    "message_id": mid,
                    "label": "ABSTAIN_POLICY",
                    "category": group["category"],
                    "expected": group.get("expected"),
                }
            )
    return cases


def build_cases() -> list[dict]:
    texts: dict[str, str] = {}
    with open(TESTS / "data" / "historical_messages.jsonl", encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            texts[row["message_id"]] = row.get("text_literal") or ""

    cases = (
        extract_notes()
        + extract_system_status()
        + extract_audio()
        + extract_gpu()
        + extract_memory()
    )

    missing = [case for case in cases if case["message_id"] not in texts]
    if missing:
        raise SystemExit(f"IDs sin texto en el corpus: {missing[:5]} ({len(missing)})")

    seen: dict[tuple[str, str], dict] = {}
    for case in cases:
        case["text"] = texts[case["message_id"]]
        key = (case["set"], case["message_id"])
        if key in seen:
            raise SystemExit(f"Duplicado dentro de un set: {key}")
        seen[key] = case

    return cases


def write_cases(cases: list[dict], output: Path) -> None:
    payload = "".join(
        json.dumps(case, ensure_ascii=False) + "\n"
        for case in cases
    ).encode("utf-8")
    replace_bytes_atomically(output, payload)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    cases = build_cases()
    write_cases(cases, args.output)

    by_set: dict[str, int] = {}
    for case in cases:
        by_set[case["set"]] = by_set.get(case["set"], 0) + 1
    print(json.dumps(by_set, indent=2, sort_keys=True))
    print(f"total={len(cases)} -> {args.output}")


if __name__ == "__main__":
    main()
