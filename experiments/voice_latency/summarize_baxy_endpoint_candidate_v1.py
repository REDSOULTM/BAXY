"""Publish the opened-development verdict for a score-gated endpoint candidate."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any


EXPECTED_ENDPOINT_ALIASES = ["backsy", "bakse", "baxi", "baxy", "boxy"]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("endpoint_summary_json_invalid")
    return value


def _load_sapi_builder() -> Any:
    path = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "build_sapi_wake_physical_holdout_v1.py"
    )
    spec = importlib.util.spec_from_file_location("endpoint_summary_sapi_builder", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("endpoint_summary_builder_import_invalid")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _target_breakdown(
    report: dict[str, Any],
    source_manifest: dict[str, Any],
    physical_manifest: dict[str, Any],
    texts: tuple[str, ...],
) -> dict[str, dict[str, int]]:
    by_text_hash = {
        hashlib.sha256(text.encode("utf-8")).hexdigest(): text for text in texts
    }
    source_by_audio = {
        record["audioSha256"]: by_text_hash[record["textSha256"]]
        for record in source_manifest["records"]["positive"]
    }
    text_by_output = {
        record["outputSha256"]: source_by_audio[record["sourceSha256"]]
        for record in physical_manifest["records"]
        if record["recordId"].startswith("positive/")
    }
    groups: dict[str, list[bool]] = {}
    for record in report["positive"]["records"]:
        prefix = text_by_output[record["audioSha256"]].split()[0]
        groups.setdefault(prefix, []).append(bool(record["hit"]))
    return {
        prefix: {"hits": sum(values), "files": len(values)}
        for prefix, values in sorted(groups.items())
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-manifest", type=Path, required=True)
    parser.add_argument("--baseline-manifest", type=Path, required=True)
    parser.add_argument("--human-runtime-report", type=Path, required=True)
    parser.add_argument("--confusable-runtime-report", type=Path, required=True)
    parser.add_argument("--suffix-runtime-report", type=Path, required=True)
    parser.add_argument("--human-fusion-report", type=Path, required=True)
    parser.add_argument("--confusable-source-corpus", type=Path, required=True)
    parser.add_argument("--confusable-physical-corpus", type=Path, required=True)
    parser.add_argument("--suffix-source-corpus", type=Path, required=True)
    parser.add_argument("--suffix-physical-corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    output = args.output.resolve()
    if output.exists():
        raise SystemExit("Output already exists.")
    inputs = {
        name: value.resolve(strict=True)
        for name, value in vars(args).items()
        if name != "output"
    }
    candidate = _read(inputs["candidate_manifest"])
    baseline = _read(inputs["baseline_manifest"])
    human = _read(inputs["human_runtime_report"])
    confusable = _read(inputs["confusable_runtime_report"])
    suffix = _read(inputs["suffix_runtime_report"])
    fusion = _read(inputs["human_fusion_report"])
    endpoint = candidate.get("endpointLexicalProposal")
    if not isinstance(endpoint, dict):
        raise ValueError("endpoint_summary_candidate_contract_missing")
    acoustic_parity = {
        "upstreamGraphs": candidate.get("upstreamModels")
        == baseline.get("upstreamModels"),
        "acousticVerifiers": candidate.get("logmelVerifiers", [])[:2]
        == baseline.get("logmelVerifiers", [])[:2],
        "melFilters": candidate.get("melFiltersSha256")
        == baseline.get("melFiltersSha256"),
        "routes": candidate.get("routes") == baseline.get("routes"),
        "singleAliasRescue": candidate.get("singleAliasRescue")
        == baseline.get("singleAliasRescue"),
    }
    sapi = _load_sapi_builder()
    confusable_breakdown = _target_breakdown(
        confusable,
        _read(inputs["confusable_source_corpus"] / "manifest.v1.json"),
        _read(inputs["confusable_physical_corpus"] / "manifest.v1.json"),
        sum(sapi._ENDPOINT_CONFUSABLE_DEVELOPMENT_POSITIVE_TEXTS.values(), ()),
    )
    suffix_breakdown = _target_breakdown(
        suffix,
        _read(inputs["suffix_source_corpus"] / "manifest.v1.json"),
        _read(inputs["suffix_physical_corpus"] / "manifest.v1.json"),
        sum(sapi._ENDPOINT_SUFFIX_DEVELOPMENT_POSITIVE_TEXTS.values(), ()),
    )
    clear_confusable = sum(
        values["hits"]
        for name, values in confusable_breakdown.items()
        if name != "Basi"
    )
    clear_confusable_files = sum(
        values["files"]
        for name, values in confusable_breakdown.items()
        if name != "Basi"
    )
    clear_suffix = sum(
        values["hits"] for name, values in suffix_breakdown.items() if name != "Basi"
    )
    clear_suffix_files = sum(
        values["files"] for name, values in suffix_breakdown.items() if name != "Basi"
    )
    reports = (human, confusable, suffix)
    false_hits = sum(report["negative"]["hits"] for report in reports)
    negative_files = sum(report["negative"]["files"] for report in reports)
    maximum_p50 = max(
        report["positive"]["runtimeSeconds"]["wallP50"] for report in reports
    )
    maximum_p95 = max(
        report["positive"]["runtimeSeconds"]["wallP95"] for report in reports
    )
    opened_passed = bool(
        all(acoustic_parity.values())
        and endpoint.get("scoreGte") == -1.0
        and sorted(endpoint.get("aliases", [])) == EXPECTED_ENDPOINT_ALIASES
        and false_hits == 0
        and clear_confusable == clear_confusable_files == 17
        and clear_suffix == clear_suffix_files == 69
        and fusion["positive"]["policies"]["cascadeOrEndpoint"]["hits"] == 48
        and fusion["negative"]["policies"]["cascadeOrEndpoint"]["hits"] == 0
        and maximum_p50 <= 1.5
        and maximum_p95 <= 2.0
    )
    report = {
        "schema": "baxy.endpoint-candidate-opened-verdict.v1",
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "candidateManifestSha256": _sha256(inputs["candidate_manifest"]),
        "baselineManifestSha256": _sha256(inputs["baseline_manifest"]),
        "acousticBaselineByteParity": acoustic_parity,
        "contract": {
            "scoreGte": endpoint.get("scoreGte"),
            "aliases": sorted(endpoint.get("aliases", [])),
            "retrySpeedFactors": endpoint.get("retrySpeedFactors"),
        },
        "metrics": {
            "humanCombined": fusion["positive"]["policies"]["cascadeOrEndpoint"],
            "humanCombinedFalseActivations": fusion["negative"]["policies"][
                "cascadeOrEndpoint"
            ],
            "runtimeNegativeFiles": negative_files,
            "runtimeFalseActivations": false_hits,
            "clearConfusable": {
                "hits": clear_confusable,
                "files": clear_confusable_files,
            },
            "clearSuffixIndependent": {
                "hits": clear_suffix,
                "files": clear_suffix_files,
            },
            "confusableBreakdown": confusable_breakdown,
            "suffixBreakdown": suffix_breakdown,
            "maximumRuntimeP50Seconds": maximum_p50,
            "maximumRuntimeP95Seconds": maximum_p95,
        },
        "sources": {
            name: _sha256(path)
            if path.is_file()
            else _sha256(path / "manifest.v1.json")
            for name, path in inputs.items()
        },
        "openedDevelopmentPassed": opened_passed,
        "candidateFrozen": False,
        "freshBlindPhysicalRequired": True,
        "promotable": False,
        "developmentOnly": True,
        "effectsExecuted": 0,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "openedDevelopmentPassed": opened_passed,
                "humanCombined": report["metrics"]["humanCombined"],
                "falseActivations": f"{false_hits}/{negative_files}",
                "maximumP50Seconds": maximum_p50,
                "maximumP95Seconds": maximum_p95,
            },
            sort_keys=True,
        )
    )
    return 0 if opened_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
