"""Genera src/baxy_mind/data/intent_bank.jsonl (banco congelado del router).

Fuentes:
- Anclas autoradas canónicas de tools/router_bank_sources.py.
- Corpus curado de los oráculos congelados (positivos con su operación,
  negativos duros como ABSTAIN__corpus), extraído mediante
  tools/extract_router_cases.py → tools/data/router_cases.jsonl.

Dedup por clave de identidad QUE CONSERVA TILDES (accent_polarity); un texto
con más de una etiqueta se excluye. Se ejecuta en desarrollo; el artefacto
generado queda versionado y los gates offline solo leen el artefacto.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import unicodedata
from collections.abc import Iterable, Mapping
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
DEFAULT_CASES = TOOLS / "data" / "router_cases.jsonl"
DEFAULT_OUTPUT = TOOLS.parent / "data" / "intent_bank.jsonl"

if __package__ in {None, ""}:
    sys.path.insert(0, str(TOOLS.parents[1]))

from baxy_mind.tools.atomic_output import replace_bytes_atomically  # noqa: E402
from baxy_mind.tools.router_bank_sources import ALL_POOLS  # noqa: E402


@dataclass(frozen=True, slots=True)
class BankBuildResult:
    rows: int
    labels: int
    ambiguous: int
    sha256: str
    output: Path


def identity_key(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text.casefold()).split())


def build_bank(
    *,
    cases_path: Path = DEFAULT_CASES,
    output_path: Path = DEFAULT_OUTPUT,
    pools: Mapping[str, Iterable[str]] = ALL_POOLS,
) -> BankBuildResult:
    cases = [
        json.loads(line)
        for line in cases_path.read_text(encoding="utf-8").splitlines()
    ]

    by_key: dict[str, set[str]] = defaultdict(set)
    text_of: dict[str, str] = {}

    def add(label: str, text: str) -> None:
        key = identity_key(text)
        by_key[key].add(label)
        text_of[key] = text

    for label, exemplars in pools.items():
        for exemplar in exemplars:
            add(label, exemplar)
    for case in cases:
        if case["label"] == "ABSTAIN_POLICY":
            continue
        label = "ABSTAIN__corpus" if case["label"] == "ABSTAIN" else case["label"]
        add(label, case["text"])

    rows = [
        {"label": next(iter(labels)), "text": text_of[key]}
        for key, labels in sorted(by_key.items())
        if len(labels) == 1
    ]
    ambiguous = sum(1 for labels in by_key.values() if len(labels) > 1)

    payload = "".join(
        json.dumps(row, ensure_ascii=False) + "\n"
        for row in rows
    ).encode("utf-8")
    replace_bytes_atomically(output_path, payload)

    labels = {row["label"] for row in rows}
    return BankBuildResult(
        rows=len(rows),
        labels=len(labels),
        ambiguous=ambiguous,
        sha256=hashlib.sha256(payload).hexdigest(),
        output=output_path,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = build_bank(cases_path=args.cases, output_path=args.output)
    print(
        f"banco: {result.rows} anclas, {result.labels} clases, "
        f"{result.ambiguous} ambiguos excluidos -> {result.output}"
    )


if __name__ == "__main__":
    main()
