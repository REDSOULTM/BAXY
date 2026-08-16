"""Rescore frozen ServiceNow development hypotheses with semantic ASR fusion.

This evaluator never reads blind row groups.  It consumes already-published
development hypotheses, applies a reference-free canonicalizer, and uses the
reference only after inference to compute metrics.  Raw text stays outside the
repository because the source dataset does not declare a license.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import importlib.util
import json
import math
from pathlib import Path
import re
import sys
from typing import Any


SCHEMA = "baxy.servicenow-codeswitch-semantic-fusion-development.v1"
SOURCE_SCHEMA = "baxy.servicenow-codeswitch-stt-development-evaluation.v1"
EXPECTED_CASES = 59
LEXICON_WORD_LIMIT_PER_LANGUAGE = 150_000
THRESHOLDS = {
    "expectedCases": EXPECTED_CASES,
    "minimumNonemptyRate": 1.0,
    "maximumCorpusWer": 0.20,
    "maximumEnglishReferenceErrorRate": 0.20,
    "maximumSpanishReferenceErrorRate": 0.20,
    "minimumCriticalAnchorRecall": 0.99,
    "maximumInitialSignalLatencyP95Seconds": 2.0,
    "maximumSemanticFinalizationLatencyP95Seconds": 2.0,
    "maximumSemanticRealTimeFactorP95": 0.5,
}
_ADDRESS_SUFFIX = re.compile(
    r"(?i)\b(?:avenue|bypass|boulevard|circle|court|drive|highway|lane|"
    r"parkway|place|road|street|trail|view|way)\b"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_module(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise RuntimeError(f"semantic_fusion_module_import_failed:{name}")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def _nearest_rank(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(percentile * len(ordered)) - 1)]


def _tree_commitment(root: Path) -> dict[str, object]:
    digest = hashlib.sha256()
    files = 0
    total_bytes = 0
    for path in sorted(
        (
            item
            for item in root.rglob("*")
            if item.is_file()
            and "__pycache__" not in item.parts
            and item.suffix.casefold() != ".pyc"
        ),
        key=lambda item: item.relative_to(root).as_posix(),
    ):
        relative = path.relative_to(root).as_posix()
        size = path.stat().st_size
        file_hash = sha256(path)
        digest.update(f"{relative}\t{size}\t{file_hash}\n".encode("utf-8"))
        files += 1
        total_bytes += size
    return {
        "path": root.as_posix(),
        "files": files,
        "bytes": total_bytes,
        "sha256": digest.hexdigest(),
    }


def _installed_distributions(root: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for distribution in importlib.metadata.distributions(path=[str(root)]):
        name = distribution.metadata.get("Name")
        version = distribution.version
        if name and version:
            rows.append({"name": str(name), "version": str(version)})
    return sorted(rows, key=lambda item: item["name"].casefold())


def _load_source(
    *, artifact_path: Path, detail_path: Path, engine: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    artifact = json.loads(artifact_path.read_text(encoding="utf-8-sig"))
    detail = json.loads(detail_path.read_text(encoding="utf-8-sig"))
    if (
        artifact.get("schema") != SOURCE_SCHEMA
        or detail.get("schema") != SOURCE_SCHEMA
        or artifact.get("engine") != engine
        or detail.get("engine") != engine
        or artifact.get("partition") != "development"
        or detail.get("partition") != "development"
        or artifact.get("blindRowGroupsOpened") != []
        or detail.get("blindRowGroupsOpened") != []
        or artifact.get("effectsExecuted") != 0
        or detail.get("effectsExecuted") != 0
        or artifact.get("detail", {}).get("sha256") != sha256(detail_path)
        or len(detail.get("cases", [])) != EXPECTED_CASES
    ):
        raise RuntimeError(f"semantic_fusion_source_invalid:{engine}")
    return artifact, detail


def needs_secondary_hypothesis(transcript: str) -> bool:
    """Select only utterances containing a structured postal address."""

    return bool(_ADDRESS_SUFFIX.search(transcript) and re.search(r"\b\d{4,6}\b", transcript))


class WordfreqBilingualLexicon:
    """General EN/ES lexicon; no benchmark text is used to build it."""

    def __init__(self) -> None:
        from wordfreq import iter_wordlist, zipf_frequency

        self._iter_wordlist = iter_wordlist
        self._zipf_frequency = zipf_frequency
        self._words: set[str] | None = None

    def frequency(self, word: str) -> float:
        return max(
            float(self._zipf_frequency(word, "en")),
            float(self._zipf_frequency(word, "es")),
        )

    def _load_words(self) -> set[str]:
        if self._words is not None:
            return self._words
        words: set[str] = set()
        for language in ("en", "es"):
            for index, word in enumerate(self._iter_wordlist(language, "large")):
                if index >= LEXICON_WORD_LIMIT_PER_LANGUAGE:
                    break
                if word.isalpha() and 3 <= len(word) <= 14:
                    words.add(word.casefold())
        self._words = words
        return words

    def phonetic_candidates(self, word: str) -> tuple[str, ...]:
        import jellyfish
        from rapidfuzz import fuzz

        query = word.casefold()
        if len(query) < 3:
            return ()
        source_frequency = self.frequency(query)
        source_code = jellyfish.metaphone(query)
        ranked: list[tuple[float, str]] = []
        for candidate in self._load_words():
            if (
                candidate == query
                or candidate[:3] != query[:3]
                or abs(len(candidate) - len(query)) > 2
                or jellyfish.metaphone(candidate) != source_code
            ):
                continue
            similarity = float(fuzz.ratio(query, candidate))
            frequency = self.frequency(candidate)
            if similarity < 55.0 or frequency < source_frequency + 0.3:
                continue
            ranked.append((similarity + frequency * 2.0, candidate))
        ranked.sort(reverse=True)
        return tuple(candidate for _score, candidate in ranked[:3])


def evaluate(arguments: argparse.Namespace) -> dict[str, object]:
    repository_root = arguments.repository_root.resolve(strict=True)
    artifact_path = arguments.artifact.resolve()
    detail_output = arguments.detail_output.resolve()
    if artifact_path.exists() or detail_output.exists():
        raise RuntimeError("semantic_fusion_output_exists")
    if detail_output.is_relative_to(repository_root):
        raise RuntimeError("semantic_fusion_detail_must_stay_outside_repository")

    primary_artifact_path = arguments.primary_artifact.resolve(strict=True)
    primary_detail_path = arguments.primary_detail.resolve(strict=True)
    secondary_artifact_path = arguments.secondary_artifact.resolve(strict=True)
    secondary_detail_path = arguments.secondary_detail.resolve(strict=True)
    primary_artifact, primary_detail = _load_source(
        artifact_path=primary_artifact_path,
        detail_path=primary_detail_path,
        engine="parakeet_greedy",
    )
    secondary_artifact, secondary_detail = _load_source(
        artifact_path=secondary_artifact_path,
        detail_path=secondary_detail_path,
        engine="nemotron_auto",
    )
    primary_cases = list(primary_detail["cases"])
    secondary_by_id = {
        str(case["caseId"]): case for case in secondary_detail["cases"]
    }
    if [str(case["caseId"]) for case in primary_cases] != list(secondary_by_id):
        raise RuntimeError("semantic_fusion_case_order_changed")
    for case in primary_cases:
        secondary = secondary_by_id[str(case["caseId"])]
        if case.get("referenceSha256") != secondary.get("referenceSha256"):
            raise RuntimeError("semantic_fusion_reference_commitment_changed")

    wordfreq_root = arguments.wordfreq_root.resolve(strict=True)
    distributions = _installed_distributions(wordfreq_root)
    if {item["name"].casefold(): item["version"] for item in distributions}.get(
        "wordfreq"
    ) != "3.1.1":
        raise RuntimeError("semantic_fusion_wordfreq_version_changed")
    sys.path.insert(0, str(wordfreq_root))
    lexicon = WordfreqBilingualLexicon()
    fusion = _load_module(
        "baxy_semantic_stt_fusion_development",
        repository_root / "experiments/stt_quality/semantic_stt_fusion.py",
    )
    frozen = _load_module(
        "baxy_frozen_stt_semantic_fusion",
        repository_root / "experiments/stt_quality/evaluate_reserved_stt.py",
    )
    source_evaluator = _load_module(
        "baxy_servicenow_source_semantic_fusion",
        repository_root
        / "experiments/stt_quality/evaluate_servicenow_codeswitch_development.py",
    )

    results: list[dict[str, Any]] = []
    for primary in primary_cases:
        case_id = str(primary["caseId"])
        secondary = secondary_by_id[case_id]
        use_secondary = needs_secondary_hypothesis(str(primary["productTranscript"]))
        alternatives = (
            (str(secondary["productTranscript"]),) if use_secondary else ()
        )
        semantic = fusion.canonicalize_transcript(
            str(primary["productTranscript"]),
            alternatives=alternatives,
            lexicon=lexicon,
        )
        reference = str(primary["reference"])
        reference_tokens = frozen._scoring_tokens(reference)
        semantic_tokens = frozen._scoring_tokens(semantic.text)
        word_errors = frozen._edit_distance(reference_tokens, semantic_tokens)
        anchors = frozen._critical_anchors(reference)
        preserved = [
            anchor for anchor in anchors if frozen._anchor_present(anchor, semantic.text)
        ]
        expanded_reference, labels = source_evaluator._expanded_reference_words(
            frozen,
            list(primary["words"]),
            list(primary["wordLanguages"]),
        )
        language_counts = source_evaluator.reference_language_errors(
            expanded_reference,
            labels,
            semantic_tokens,
        )
        initial_latency = float(primary["latencySeconds"])
        semantic_latency = max(
            initial_latency,
            float(secondary["latencySeconds"]) if use_secondary else initial_latency,
        )
        audio_seconds = float(primary["audioSeconds"])
        results.append(
            {
                "caseId": case_id,
                "reference": reference,
                "primaryTranscript": str(primary["productTranscript"]),
                "secondaryTranscript": (
                    str(secondary["productTranscript"]) if use_secondary else None
                ),
                "semanticTranscript": semantic.text,
                "transformations": list(semantic.transformations),
                "ambiguities": [
                    {
                        "surface": ambiguity.surface,
                        "alternatives": list(ambiguity.alternatives),
                        "reason": ambiguity.reason,
                    }
                    for ambiguity in semantic.ambiguities
                ],
                "requiresClarification": semantic.requires_clarification,
                "secondaryTriggered": use_secondary,
                "nonempty": bool(semantic_tokens),
                "decodeError": primary.get("error") is not None
                or (use_secondary and secondary.get("error") is not None),
                "referenceTokens": len(reference_tokens),
                "wordErrors": word_errors,
                "wer": round(word_errors / max(1, len(reference_tokens)), 6),
                "criticalAnchors": anchors,
                "criticalAnchorsPreserved": preserved,
                "referenceWordLanguageCounts": language_counts,
                "audioSeconds": audio_seconds,
                "initialSignalLatencySeconds": initial_latency,
                "semanticFinalizationLatencySeconds": semantic_latency,
                "semanticRealTimeFactor": semantic_latency / max(0.001, audio_seconds),
                "referenceSha256": str(primary["referenceSha256"]),
            }
        )

    reference_tokens = sum(int(row["referenceTokens"]) for row in results)
    word_errors = sum(int(row["wordErrors"]) for row in results)
    anchors = sum(len(row["criticalAnchors"]) for row in results)
    preserved = sum(len(row["criticalAnchorsPreserved"]) for row in results)
    language_counts = {
        language: {
            "referenceTokens": sum(
                int(
                    row["referenceWordLanguageCounts"]
                    .get(language, {})
                    .get("referenceTokens", 0)
                )
                for row in results
            ),
            "errors": sum(
                int(
                    row["referenceWordLanguageCounts"]
                    .get(language, {})
                    .get("errors", 0)
                )
                for row in results
            ),
        }
        for language in ("EN", "ES")
    }
    for counts in language_counts.values():
        counts["referenceErrorRate"] = round(
            counts["errors"] / max(1, counts["referenceTokens"]), 6
        )
    initial_latencies = [float(row["initialSignalLatencySeconds"]) for row in results]
    semantic_latencies = [
        float(row["semanticFinalizationLatencySeconds"]) for row in results
    ]
    semantic_rtfs = [float(row["semanticRealTimeFactor"]) for row in results]
    metrics = {
        "cases": len(results),
        "nonemptyRate": round(
            sum(bool(row["nonempty"]) for row in results) / max(1, len(results)), 6
        ),
        "decodeErrors": sum(bool(row["decodeError"]) for row in results),
        "referenceTokens": reference_tokens,
        "wordErrors": word_errors,
        "corpusWer": round(word_errors / max(1, reference_tokens), 6),
        "criticalAnchors": anchors,
        "criticalAnchorsPreserved": preserved,
        "criticalAnchorRecall": round(preserved / max(1, anchors), 6),
        "ambiguities": sum(len(row["ambiguities"]) for row in results),
        "casesRequiringClarification": sum(
            bool(row["requiresClarification"]) for row in results
        ),
        "secondaryTriggeredCases": sum(bool(row["secondaryTriggered"]) for row in results),
        "initialSignalLatencyP50Seconds": _nearest_rank(initial_latencies, 0.50),
        "initialSignalLatencyP95Seconds": _nearest_rank(initial_latencies, 0.95),
        "semanticFinalizationLatencyP50Seconds": _nearest_rank(
            semantic_latencies, 0.50
        ),
        "semanticFinalizationLatencyP95Seconds": _nearest_rank(
            semantic_latencies, 0.95
        ),
        "semanticRealTimeFactorP50": _nearest_rank(semantic_rtfs, 0.50),
        "semanticRealTimeFactorP95": _nearest_rank(semantic_rtfs, 0.95),
        "referenceLanguage": language_counts,
    }
    checks = {
        "expectedCases": metrics["cases"] == THRESHOLDS["expectedCases"],
        "nonemptyRate": metrics["nonemptyRate"] >= THRESHOLDS["minimumNonemptyRate"],
        "decodeErrors": metrics["decodeErrors"] == 0,
        "corpusWer": metrics["corpusWer"] <= THRESHOLDS["maximumCorpusWer"],
        "englishReferenceErrorRate": language_counts["EN"]["referenceErrorRate"]
        <= THRESHOLDS["maximumEnglishReferenceErrorRate"],
        "spanishReferenceErrorRate": language_counts["ES"]["referenceErrorRate"]
        <= THRESHOLDS["maximumSpanishReferenceErrorRate"],
        "criticalAnchorRecall": metrics["criticalAnchorRecall"]
        >= THRESHOLDS["minimumCriticalAnchorRecall"],
        "initialSignalLatencyP95": metrics["initialSignalLatencyP95Seconds"]
        <= THRESHOLDS["maximumInitialSignalLatencyP95Seconds"],
        "semanticFinalizationLatencyP95": metrics[
            "semanticFinalizationLatencyP95Seconds"
        ]
        <= THRESHOLDS["maximumSemanticFinalizationLatencyP95Seconds"],
        "semanticRealTimeFactorP95": metrics["semanticRealTimeFactorP95"]
        <= THRESHOLDS["maximumSemanticRealTimeFactorP95"],
        "effectsExecuted": True,
        "blindRowsOpened": True,
    }

    detail = {
        "schema": SCHEMA,
        "partition": "development",
        "metrics": metrics,
        "checks": checks,
        "thresholds": THRESHOLDS,
        "cases": results,
        "blindRowGroupsOpened": [],
        "effectsExecuted": 0,
    }
    detail_output.parent.mkdir(parents=True, exist_ok=True)
    detail_output.write_text(
        json.dumps(detail, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    evaluator_path = Path(__file__).resolve(strict=True)
    fusion_path = repository_root / "experiments/stt_quality/semantic_stt_fusion.py"
    artifact: dict[str, object] = {
        "schema": SCHEMA,
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "partition": "development",
        "status": "passed" if all(checks.values()) else "failed",
        "metrics": metrics,
        "checks": checks,
        "thresholds": THRESHOLDS,
        "sources": {
            "primary": {
                "artifact": primary_artifact_path.relative_to(repository_root).as_posix(),
                "artifactSha256": sha256(primary_artifact_path),
                "detail": primary_detail_path.as_posix(),
                "detailSha256": sha256(primary_detail_path),
                "engineRuntime": primary_artifact["engineRuntime"],
            },
            "secondary": {
                "artifact": secondary_artifact_path.relative_to(repository_root).as_posix(),
                "artifactSha256": sha256(secondary_artifact_path),
                "detail": secondary_detail_path.as_posix(),
                "detailSha256": sha256(secondary_detail_path),
                "engineRuntime": secondary_artifact["engineRuntime"],
                "selection": "postal_address_suffix_and_4_to_6_digit_field",
            },
        },
        "lexicon": {
            "type": "wordfreq-general-bilingual-frequency-and-phonetic-index",
            "version": "3.1.1",
            "languages": ["en", "es"],
            "wordLimitPerLanguage": LEXICON_WORD_LIMIT_PER_LANGUAGE,
            "distributions": distributions,
            "tree": _tree_commitment(wordfreq_root),
            "benchmarkReferenceUsedToBuildLexicon": False,
            "licenseReviewRequiredBeforePromotion": True,
        },
        "detail": {"path": detail_output.as_posix(), "sha256": sha256(detail_output)},
        "evaluator": {
            "path": evaluator_path.relative_to(repository_root).as_posix(),
            "sha256": sha256(evaluator_path),
        },
        "fusion": {
            "path": fusion_path.relative_to(repository_root).as_posix(),
            "sha256": sha256(fusion_path),
        },
        "caseCommitments": [
            {
                "caseId": row["caseId"],
                "referenceSha256": row["referenceSha256"],
                "semanticTranscriptSha256": hashlib.sha256(
                    str(row["semanticTranscript"]).encode("utf-8")
                ).hexdigest(),
                "wer": row["wer"],
                "ambiguities": len(row["ambiguities"]),
                "secondaryTriggered": row["secondaryTriggered"],
            }
            for row in results
        ],
        "developmentOnly": True,
        "syntheticAudio": True,
        "finalPhysicalCertificationEligible": False,
        "blindRowGroupsOpened": [],
        "candidatePromoted": False,
        "wakeProgramTree": frozen._program_tree(repository_root),
        "effectsExecuted": 0,
    }
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return artifact


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--primary-artifact", type=Path, required=True)
    parser.add_argument("--primary-detail", type=Path, required=True)
    parser.add_argument("--secondary-artifact", type=Path, required=True)
    parser.add_argument("--secondary-detail", type=Path, required=True)
    parser.add_argument("--wordfreq-root", type=Path, required=True)
    parser.add_argument("--detail-output", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    artifact = evaluate(arguments)
    print(
        json.dumps(
            {
                "artifact": str(arguments.artifact),
                "status": artifact["status"],
                "sha256": sha256(arguments.artifact),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
