"""Build provenance-preserving BAXY evidence from licensed public corpora.

This offline data adapter never assigns a capability from the wording of an
utterance. It only accepts an upstream semantic label from a reviewed source
map. The emitted records are advisory evidence for a turn-decider, never an
operation name or execution authority.
"""

from __future__ import annotations

import hashlib
import json
import tarfile
import unicodedata
import zipfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .turn_evidence_contracts import EVIDENCE_RECORD_SCHEMA_VERSION

PUBLIC_RECORD_SCHEMA_VERSION = EVIDENCE_RECORD_SCHEMA_VERSION
SOURCE_MAP_SCHEMA_VERSION = "baxy.turn-evidence-source-map.v1"
PRESTO_ARCHIVE_ENTRY_BY_SPLIT = {
    "train": "presto_train.jsonl",
    "validation": "presto_dev.jsonl",
    "test": "presto_test.jsonl",
}
MASSIVE_SPLIT_BY_PARTITION = {"train": "train", "dev": "validation", "test": "test"}
_ALLOWED_MODES = frozenset({"conversation", "clarify", "action", "plan"})


@dataclass(frozen=True, slots=True)
class PublicCorpusBuildReport:
    archive_sha256: str
    source_rows: int
    accepted_rows: int
    excluded_locale: int
    excluded_contextual: int
    excluded_unmapped: int
    excluded_invalid: int
    source_intents: dict[str, int]
    excluded_partition: int = 0
    excluded_quality: int = 0


@dataclass(frozen=True, slots=True)
class SourceMap:
    source: dict[str, str]
    locales: frozenset[str]
    require_empty_previous_turns: bool
    maximum_text_characters: int
    labels: dict[str, tuple[str, tuple[str, ...]]]
    minimum_localized_judgments: int = 0
    minimum_localized_grammar_score: int = 0


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normal_text(value: object, maximum_characters: int) -> str | None:
    if not isinstance(value, str):
        return None
    text = " ".join(unicodedata.normalize("NFC", value).split())
    if not text or len(text) > maximum_characters:
        return None
    if any(ord(character) < 32 for character in text):
        return None
    return text


def load_source_map(path: Path) -> SourceMap:
    """Validate the reviewed, declarative adapter for one public source."""

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("no se pudo leer el mapa de la fuente publica") from error
    if not isinstance(raw, dict) or raw.get("schema") != SOURCE_MAP_SCHEMA_VERSION:
        raise ValueError("el mapa de fuente tiene un schema desconocido")
    source_raw = raw.get("source")
    selection = raw.get("selection")
    labels_raw = raw.get("labels")
    if not isinstance(source_raw, dict) or not isinstance(selection, dict) or not isinstance(labels_raw, dict):
        raise ValueError("el mapa de fuente esta incompleto")
    source = {
        key: value
        for key, value in source_raw.items()
        if isinstance(key, str) and isinstance(value, str) and value.strip()
    }
    if source.get("license") != "CC-BY-4.0" or not source.get("download_url"):
        raise ValueError("la fuente publica no tiene licencia o procedencia aprobada")
    locales_raw = selection.get("locales")
    maximum_characters = selection.get("maximum_text_characters")
    minimum_judgments = selection.get("minimum_localized_judgments", 0)
    minimum_grammar = selection.get("minimum_localized_grammar_score", 0)
    if (
        not isinstance(locales_raw, list)
        or not all(isinstance(locale, str) and locale for locale in locales_raw)
        or not isinstance(maximum_characters, int)
        or maximum_characters < 1
        or maximum_characters > 4_096
        or not isinstance(minimum_judgments, int)
        or minimum_judgments < 0
        or minimum_judgments > 10
        or not isinstance(minimum_grammar, int)
        or minimum_grammar < 0
        or minimum_grammar > 4
    ):
        raise ValueError("la seleccion de la fuente no es valida")
    labels: dict[str, tuple[str, tuple[str, ...]]] = {}
    for source_intent, value in labels_raw.items():
        if not isinstance(source_intent, str) or not isinstance(value, dict):
            raise ValueError("una etiqueta de fuente no es valida")
        mode = value.get("mode")
        families = value.get("families")
        if (
            mode not in _ALLOWED_MODES
            or not isinstance(families, list)
            or not all(isinstance(family, str) and family.isidentifier() for family in families)
        ):
            raise ValueError("una proyeccion de etiqueta no es valida")
        labels[source_intent] = (mode, tuple(sorted(set(families))))
    if not labels:
        raise ValueError("el mapa de fuente no selecciona ninguna etiqueta")
    return SourceMap(
        source=source,
        locales=frozenset(locales_raw),
        require_empty_previous_turns=bool(selection.get("require_empty_previous_turns")),
        maximum_text_characters=maximum_characters,
        labels=labels,
        minimum_localized_judgments=minimum_judgments,
        minimum_localized_grammar_score=minimum_grammar,
    )


def _source_intent(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    intent = value.split(" (", 1)[0].strip()
    return intent or None


def build_presto_records(
    archive: Path,
    source_map: SourceMap,
    split: str,
) -> tuple[list[dict[str, Any]], PublicCorpusBuildReport]:
    """Stream one official split and retain only reviewed standalone examples.

    The original train/dev/test partitions stay independent. The output does
    not contain PRESTO contact/list/note metadata or preceding turns.
    """

    if split not in PRESTO_ARCHIVE_ENTRY_BY_SPLIT:
        raise ValueError("el split de PRESTO no es reconocido")
    archive = archive.resolve(strict=True)
    counts: Counter[str] = Counter()
    source_intents: Counter[str] = Counter()
    records: list[dict[str, Any]] = []
    try:
        with zipfile.ZipFile(archive) as bundle:
            with bundle.open(PRESTO_ARCHIVE_ENTRY_BY_SPLIT[split]) as handle:
                for raw_line in handle:
                    if not raw_line.strip():
                        continue
                    counts["source_rows"] += 1
                    try:
                        row = json.loads(raw_line.decode("utf-8"))
                    except (UnicodeDecodeError, json.JSONDecodeError) as error:
                        raise ValueError("PRESTO contiene JSONL invalido") from error
                    metadata = row.get("metadata") if isinstance(row, dict) else None
                    if not isinstance(metadata, dict):
                        counts["excluded_invalid"] += 1
                        continue
                    locale = metadata.get("locale")
                    if locale not in source_map.locales:
                        counts["excluded_locale"] += 1
                        continue
                    if source_map.require_empty_previous_turns and metadata.get("previous_turns") != []:
                        counts["excluded_contextual"] += 1
                        continue
                    intent = _source_intent(row.get("targets"))
                    mapping = source_map.labels.get(intent or "")
                    if mapping is None:
                        counts["excluded_unmapped"] += 1
                        continue
                    text = _normal_text(row.get("inputs"), source_map.maximum_text_characters)
                    example_id = metadata.get("example_id")
                    if text is None or not isinstance(example_id, str) or not example_id:
                        counts["excluded_invalid"] += 1
                        continue
                    mode, families = mapping
                    source_id = f"presto-v1:{locale}:{example_id}"
                    records.append(
                        {
                            "schema": PUBLIC_RECORD_SCHEMA_VERSION,
                            "text": text,
                            "mode": mode,
                            "families": list(families),
                            "mission_id": source_id,
                            "source_id": source_id,
                            "split": split,
                            "provenance": {
                                "dataset": source_map.source["name"],
                                "license": source_map.source["license"],
                                "source_intent": intent,
                            },
                        }
                    )
                    counts["accepted_rows"] += 1
                    source_intents[intent] += 1
    except (OSError, zipfile.BadZipFile, KeyError) as error:
        raise ValueError("no se pudo leer el archivo PRESTO esperado") from error
    return records, PublicCorpusBuildReport(
        archive_sha256=_sha256(archive),
        source_rows=counts["source_rows"],
        accepted_rows=counts["accepted_rows"],
        excluded_locale=counts["excluded_locale"],
        excluded_contextual=counts["excluded_contextual"],
        excluded_unmapped=counts["excluded_unmapped"],
        excluded_invalid=counts["excluded_invalid"],
        source_intents=dict(sorted(source_intents.items())),
    )


def _passes_massive_quality(row: dict[str, Any], source_map: SourceMap) -> bool:
    """Use MASSIVE's existing localized-quality judgments without copying them."""

    minimum = source_map.minimum_localized_judgments
    if minimum == 0:
        return True
    judgments = row.get("judgments")
    # en-US is the original collection and deliberately has no localization
    # judgment object. Its official partition is retained as published.
    if judgments is None:
        return True
    if not isinstance(judgments, list):
        return False
    qualified = 0
    for judgment in judgments:
        if not isinstance(judgment, dict):
            continue
        if (
            isinstance(judgment.get("intent_score"), int)
            and judgment["intent_score"] >= 1
            and isinstance(judgment.get("grammar_score"), int)
            and judgment["grammar_score"] >= source_map.minimum_localized_grammar_score
        ):
            qualified += 1
    return qualified >= minimum


def build_massive_records(
    archive: Path,
    source_map: SourceMap,
    split: str,
) -> tuple[list[dict[str, Any]], PublicCorpusBuildReport]:
    """Stream a MASSIVE split while preserving its official language partitions."""

    if split not in {"train", "validation", "test"}:
        raise ValueError("el split de MASSIVE no es reconocido")
    archive = archive.resolve(strict=True)
    counts: Counter[str] = Counter()
    source_intents: Counter[str] = Counter()
    records: list[dict[str, Any]] = []
    try:
        with tarfile.open(archive, mode="r:gz") as bundle:
            for locale in sorted(source_map.locales):
                member_name = f"1.1/data/{locale}.jsonl"
                member = bundle.getmember(member_name)
                handle = bundle.extractfile(member)
                if handle is None:
                    raise ValueError("MASSIVE no contiene el archivo de locale esperado")
                with handle:
                    for raw_line in handle:
                        if not raw_line.strip():
                            continue
                        counts["source_rows"] += 1
                        try:
                            row = json.loads(raw_line.decode("utf-8"))
                        except (UnicodeDecodeError, json.JSONDecodeError) as error:
                            raise ValueError("MASSIVE contiene JSONL invalido") from error
                        if not isinstance(row, dict):
                            counts["excluded_invalid"] += 1
                            continue
                        row_split = MASSIVE_SPLIT_BY_PARTITION.get(row.get("partition"))
                        if row_split != split:
                            counts["excluded_partition"] += 1
                            continue
                        intent = row.get("intent")
                        mapping = source_map.labels.get(intent) if isinstance(intent, str) else None
                        if mapping is None:
                            counts["excluded_unmapped"] += 1
                            continue
                        if not _passes_massive_quality(row, source_map):
                            counts["excluded_quality"] += 1
                            continue
                        text = _normal_text(row.get("utt"), source_map.maximum_text_characters)
                        example_id = row.get("id")
                        if text is None or not isinstance(example_id, (str, int)):
                            counts["excluded_invalid"] += 1
                            continue
                        mode, families = mapping
                        source_id = f"massive-v1.1:{locale}:{example_id}"
                        records.append(
                            {
                                "schema": PUBLIC_RECORD_SCHEMA_VERSION,
                                "text": text,
                                "mode": mode,
                                "families": list(families),
                                # Same source ID across locales is a translated
                                # task group, so a future fine-tune cannot leak it.
                                "mission_id": f"massive-v1.1:{example_id}",
                                "source_id": source_id,
                                "split": split,
                                "provenance": {
                                    "dataset": source_map.source["name"],
                                    "license": source_map.source["license"],
                                    "source_intent": intent,
                                },
                            }
                        )
                        counts["accepted_rows"] += 1
                        source_intents[intent] += 1
    except (OSError, tarfile.TarError, KeyError) as error:
        raise ValueError("no se pudo leer el archivo MASSIVE esperado") from error
    return records, PublicCorpusBuildReport(
        archive_sha256=_sha256(archive),
        source_rows=counts["source_rows"],
        accepted_rows=counts["accepted_rows"],
        excluded_locale=0,
        excluded_contextual=0,
        excluded_unmapped=counts["excluded_unmapped"],
        excluded_invalid=counts["excluded_invalid"],
        source_intents=dict(sorted(source_intents.items())),
        excluded_partition=counts["excluded_partition"],
        excluded_quality=counts["excluded_quality"],
    )


def deduplicate_public_records(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep one exact duplicate only when its semantic signature agrees."""

    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        text = record.get("text")
        if isinstance(text, str):
            grouped.setdefault(" ".join(text.casefold().split()), []).append(record)
    accepted: list[dict[str, Any]] = []
    for variants in grouped.values():
        signatures = {
            (item.get("mode"), tuple(item.get("families", [])), item.get("split"))
            for item in variants
        }
        if len(signatures) == 1:
            accepted.append(min(variants, key=lambda item: str(item.get("source_id"))))
    accepted.sort(key=lambda item: str(item.get("source_id")))
    return accepted
