"""Build BAXY's sealed, execution-inert memory-status holdout R1."""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from scripts import build_generalization_product_holdout_r10 as r10  # noqa: E402
from scripts.build_generalization_product_holdout_r3 import (  # noqa: E402
    normalize_text,
)
from scripts.build_generalization_surface_holdout import (  # noqa: E402
    write_jsonl_atomic,
)
from scripts.measure_mind_budget import write_json_atomic  # noqa: E402


OUTPUT = REPO / "artifacts/holdout/memory_status_generalization_v1.jsonl"
PREREGISTRATION = (
    REPO / "artifacts/holdout/memory_status_generalization_v1.preregistration.json"
)
TRX = REPO / "artifacts/holdout/memory_status_generalization_r1.trx"
RESULT = REPO / "artifacts/holdout/memory_status_generalization_r1.json"
PARSER = REPO / "src/Baxy.App/NaturalMemoryRequestParser.cs"
TEST_SOURCE = REPO / "tests/Baxy.Integration.Tests/NaturalMemoryRequestParserTests.cs"
ANALYZER = REPO / "experiments/mind_router_spike/analyze_memory_status_holdout_r1.py"
PRIOR_CORPORA = (*r10.PRIOR_CORPORA, r10.OUTPUT)
EXPECTED_CASES = 360
REFERENCES = r10.REFERENCES


HEADS = {
    "es": ("Dime", "Comprueba", "Revisa", "Confirma", "Indica"),
    "en": ("Tell me", "Check", "Review", "Confirm", "Report"),
    "spanglish": ("Dime", "Check", "Review", "Confirma", "Tell me"),
}
BODIES = {
    "es": (
        "si tu memoria personal local está operativa",
        "el estado actual de tus recuerdos privados guardados localmente",
        "si el almacenamiento privado de recuerdos está habilitado",
        "la condición de la memoria personal local de Baxy",
    ),
    "en": (
        "whether your personal local-memory store is operational",
        "the current state of your locally kept personal memory",
        "whether the private recollection store is enabled",
        "the condition of Baxy's local personal memory",
    ),
    "spanglish": (
        "whether tu personal local-memory store está operational",
        "el current state de tus private memories guardadas locally",
        "si the private recollection store está enabled",
        "la condition de Baxy's local personal memory",
    ),
}
CONTEXTS = {
    "es": ("en este dispositivo", "aquí"),
    "en": ("on this device", "here"),
    "spanglish": ("en este device", "here"),
}
STACKED_PREFIX = {
    "es": "Oye Baxy, por favor, ",
    "en": "Hey Baxy, please, ",
    "spanglish": "Hey Baxy, por favor, ",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _prior_texts() -> set[str]:
    texts: set[str] = set()
    for path in PRIOR_CORPORA:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if isinstance(row.get("text"), str):
                texts.add(normalize_text(row["text"]))
    return texts


def build_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for language in ("es", "en", "spanglish"):
        base_index = 0
        for head in HEADS[language]:
            for body in BODIES[language]:
                for context in CONTEXTS[language]:
                    base_index += 1
                    base = f"{head} {body} {context}"
                    lower = base[:1].lower() + base[1:]
                    surfaces = (
                        ("plain", base),
                        ("addressed", f"Baxy: {lower}."),
                        ("stacked", f"{STACKED_PREFIX[language]}{lower}."),
                    )
                    for surface, text in surfaces:
                        rows.append(
                            {
                                "schema": "baxy.memory-status-holdout.v1",
                                "case_id": (
                                    f"memory-r1-{language}-{base_index:02d}-{surface}"
                                ),
                                "owner": "app_private_memory_parser",
                                "language": language,
                                "surface": surface,
                                "text": text,
                                "expected_operation": "memory.status",
                                "execution_authority": False,
                                "blind_holdout": True,
                            }
                        )
    normalized = [normalize_text(str(row["text"])) for row in rows]
    overlap = set(normalized) & _prior_texts()
    if len(rows) != EXPECTED_CASES or len(set(normalized)) != EXPECTED_CASES:
        raise RuntimeError("memory R1 must contain 360 unique surfaces")
    if overlap:
        raise RuntimeError(f"memory R1 overlaps prior corpora: {sorted(overlap)}")
    return rows


def build() -> dict[str, object]:
    for path in (OUTPUT, PREREGISTRATION, TRX, RESULT):
        if path.exists():
            raise RuntimeError(f"refusing to overwrite memory R1 state: {path}")
    for path in (PARSER, TEST_SOURCE, ANALYZER, *PRIOR_CORPORA):
        if not path.is_file():
            raise RuntimeError(f"missing memory R1 source: {path}")
    rows = build_rows()
    write_jsonl_atomic(OUTPUT, rows)
    manifest: dict[str, object] = {
        "schema": "baxy.memory-status-preregistration.v1",
        "blind_holdout": True,
        "measurement_status": "unopened",
        "preregistered_before_measurement": True,
        "authority": "private_parser_decision_only_no_execution",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "population": {
            "cases": EXPECTED_CASES,
            "languages": dict(Counter(str(row["language"]) for row in rows)),
            "surfaces": dict(Counter(str(row["surface"]) for row in rows)),
            "normalized_prior_overlap": 0,
        },
        "thresholds": {
            "minimum_accuracy": 0.99,
            "minimum_one_sided_95_binomial_lower_if_zero_failures": 0.99,
            "maximum_unsafe_effects": 0,
        },
        "sources": {
            "corpus": str(OUTPUT.relative_to(REPO)),
            "corpus_sha256": sha256(OUTPUT),
            "builder": str(Path(__file__).resolve().relative_to(REPO)),
            "builder_sha256": sha256(Path(__file__).resolve()),
            "parser": str(PARSER.relative_to(REPO)),
            "parser_sha256": sha256(PARSER),
            "test": str(TEST_SOURCE.relative_to(REPO)),
            "test_sha256": sha256(TEST_SOURCE),
            "analyzer": str(ANALYZER.relative_to(REPO)),
            "analyzer_sha256": sha256(ANALYZER),
            "references": list(REFERENCES),
        },
        "expected_artifacts": {
            "trx": str(TRX.relative_to(REPO)),
            "result": str(RESULT.relative_to(REPO)),
        },
    }
    write_json_atomic(PREREGISTRATION, manifest)
    return manifest


def main() -> int:
    manifest = build()
    print(json.dumps(manifest["population"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
