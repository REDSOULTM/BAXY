"""Build BAXY's sealed, execution-inert memory-status holdout R2."""

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

from scripts import build_memory_status_holdout_r1 as r1  # noqa: E402
from scripts.build_generalization_product_holdout_r3 import normalize_text  # noqa: E402
from scripts.build_generalization_surface_holdout import write_jsonl_atomic  # noqa: E402
from scripts.measure_mind_budget import write_json_atomic  # noqa: E402


OUTPUT = REPO / "artifacts/holdout/memory_status_generalization_v2.jsonl"
PREREGISTRATION = (
    REPO / "artifacts/holdout/memory_status_generalization_v2.preregistration.json"
)
TRX = REPO / "artifacts/holdout/memory_status_generalization_r2.trx"
RESULT = REPO / "artifacts/holdout/memory_status_generalization_r2.json"
PARSER = REPO / "src/Baxy.App/NaturalMemoryRequestParser.cs"
TEST_SOURCE = REPO / "tests/Baxy.Integration.Tests/NaturalMemoryRequestParserTests.cs"
ANALYZER = REPO / "experiments/mind_router_spike/analyze_memory_status_holdout_r2.py"
PRIOR_CORPORA = (*r1.PRIOR_CORPORA, r1.OUTPUT)
EXPECTED_CASES = 360
REFERENCES = r1.REFERENCES


HEADS = {
    "es": ("Verifica", "Aclárame", "Quiero saber", "Necesito conocer", "Puedes decirme"),
    "en": ("Verify", "Let me know", "I want to know", "I need to learn", "Could you tell me"),
    "spanglish": ("Verifica", "Let me know", "Quiero saber", "Could you tell me", "Aclárame"),
}
BODIES = {
    "es": (
        "si tus memorias privadas locales están activas",
        "qué condición presentan los recuerdos personales guardados localmente",
        "el estado operativo de la memoria personal que Baxy conserva en local",
        "si funciona la memoria privada almacenada localmente",
    ),
    "en": (
        "whether your private local memories are active",
        "what condition the personal recollections stored locally are in",
        "the operational state of the personal memory Baxy keeps locally",
        "whether the privately stored local memory is working",
    ),
    "spanglish": (
        "si your private local memories están active",
        "qué condition tienen tus personal recollections stored locally",
        "the operational state de la memoria personal que Baxy keeps locally",
        "whether la private memory guardada locally está working",
    ),
}
CONTEXTS = {
    "es": ("ahora mismo", "en este equipo"),
    "en": ("right now", "on this computer"),
    "spanglish": ("ahora mismo", "on este computer"),
}
STACKED_PREFIX = {
    "es": "Por favor, Baxy, ",
    "en": "Please, Baxy, ",
    "spanglish": "Please, Baxy, por favor, ",
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
                        ("addressed", f"Baxy — {lower}?"),
                        ("stacked", f"{STACKED_PREFIX[language]}{lower}."),
                    )
                    for surface, text in surfaces:
                        rows.append(
                            {
                                "schema": "baxy.memory-status-holdout.v2",
                                "case_id": f"memory-r2-{language}-{base_index:02d}-{surface}",
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
        raise RuntimeError("memory R2 must contain 360 unique surfaces")
    if overlap:
        raise RuntimeError(f"memory R2 overlaps prior corpora: {sorted(overlap)}")
    return rows


def build() -> dict[str, object]:
    for path in (OUTPUT, PREREGISTRATION, TRX, RESULT):
        if path.exists():
            raise RuntimeError(f"refusing to overwrite memory R2 state: {path}")
    for path in (PARSER, TEST_SOURCE, ANALYZER, *PRIOR_CORPORA):
        if not path.is_file():
            raise RuntimeError(f"missing memory R2 source: {path}")
    rows = build_rows()
    write_jsonl_atomic(OUTPUT, rows)
    manifest: dict[str, object] = {
        "schema": "baxy.memory-status-preregistration.v2",
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
