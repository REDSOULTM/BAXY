"""Freeze the semantic STT candidate before opening ServiceNow blind rows."""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any


SCHEMA = "baxy.servicenow-semantic-fusion-blind-preregistration.v1"
SOURCE_PREREG_SCHEMA = "baxy.servicenow-codeswitch-stt-preregistration.v1"
DEVELOPMENT_SCHEMA = "baxy.servicenow-codeswitch-semantic-fusion-development.v4"
SOURCE_BYTES = 134_596_508
SOURCE_SHA256 = "808e373099ae16c80f2bf5434fbb70afd06487ffd3a9c2f88495638dc7e035d8"
PARAKEET_FILES = {
    "encoder.int8.onnx": {
        "bytes": 652_184_281,
        "sha256": "acfc2b4456377e15d04f0243af540b7fe7c992f8d898d751cf134c3a55fd2247",
    },
    "decoder.int8.onnx": {
        "bytes": 11_845_275,
        "sha256": "179e50c43d1a9de79c8a24149a2f9bac6eb5981823f2a2ed88d655b24248db4e",
    },
    "joiner.int8.onnx": {
        "bytes": 6_355_277,
        "sha256": "3164c13fc2821009440d20fcb5fdc78bff28b4db2f8d0f0b329101719c0948b3",
    },
    "tokens.txt": {
        "bytes": 93_939,
        "sha256": "d58544679ea4bc6ac563d1f545eb7d474bd6cfa467f0a6e2c1dc1c7d37e3c35d",
    },
}
NEMOTRON_FILES = {
    "encoder.int8.onnx": {
        "bytes": 657_601_403,
        "sha256": "012e9321373af99021415e0b0eb3ec827b4be3153be6f30d9b448fe65e896e68",
    },
    "decoder.int8.onnx": {
        "bytes": 14_978_075,
        "sha256": "19f9c98fc6d0a2c33a65a43b36fdb2e914c26c0aa9764be3aebc502a1e982fb0",
    },
    "joiner.int8.onnx": {
        "bytes": 9_504_438,
        "sha256": "4101c7c679a0bc30483794b27a059e34e79232aa2068d78d51231a22c8b0d7ce",
    },
    "tokens.txt": {
        "bytes": 131_440,
        "sha256": "729cc103155bafa785f9cd45746cd41cabe97eab7182fc04d594129587958f8a",
    },
}
WHEELS = {
    "ftfy-6.3.1-py3-none-any.whl": "7c70eb532015cd2f9adb53f101fb6c7945988d023a085d127d1573dc49dd0083",
    "langcodes-3.5.1-py3-none-any.whl": "b6a9c25c603804e2d169165091d0cdb23934610524a21d226e4f463e8e958a72",
    "locate-1.1.1-py3-none-any.whl": "9e5e2f3516639240f4d975c08e95ae6a24ff4dd63d228f927541cdec30105755",
    "msgpack-1.2.1-cp312-cp312-win_amd64.whl": "5c24aa15d5963051e1a5c62b12c50cd705992502b5ec1f3bece6046f33c9fc24",
    "regex-2026.7.19-cp312-cp312-win_amd64.whl": "e30d40268a28d54ce0437031750497004c22602b8e3ab891f759b795a003b312",
    "wcwidth-0.8.2-py3-none-any.whl": "d63947694a0539a1d51e01eda7caf800c291020e6cdd7e28ad7b14dd33ad4f85",
    "wordfreq-3.1.1-py3-none-any.whl": "4b1c6ecffc6198be3396d5cf871c4423ca71c907c231348d352dd54d62b97473",
}
THRESHOLDS = {
    "expectedCases": 200,
    "minimumNonemptyRate": 1.0,
    "maximumCorpusWer": 0.20,
    "maximumEnglishReferenceErrorRate": 0.20,
    "maximumSpanishReferenceErrorRate": 0.20,
    "minimumCriticalAnchorRecall": 0.99,
    "minimumClarificationUtilityRate": 1.0,
    "maximumInitialSignalLatencyP95Seconds": 2.0,
    "maximumSemanticFinalizationLatencyP95Seconds": 2.0,
    "maximumSemanticRealTimeFactorP95": 0.5,
    "maximumPeakRssBytes": 4_294_967_296,
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _created_at(value: str) -> None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("semantic_fusion_preregistration_created_at_invalid") from error
    if parsed.tzinfo is None:
        raise ValueError("semantic_fusion_preregistration_timezone_required")


def _load_module(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise RuntimeError(f"semantic_fusion_preregistration_import_failed:{name}")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def _validate_model(root: Path, expected: dict[str, dict[str, object]], label: str) -> None:
    for name, commitment in expected.items():
        path = root / name
        if (
            not path.is_file()
            or path.stat().st_size != commitment["bytes"]
            or sha256(path) != commitment["sha256"]
        ):
            raise RuntimeError(f"semantic_fusion_preregistration_{label}_changed:{name}")


def preregister(arguments: argparse.Namespace) -> dict[str, object]:
    _created_at(arguments.created_at_utc)
    repository_root = arguments.repository_root.resolve(strict=True)
    artifact_path = arguments.artifact.resolve()
    if artifact_path.exists():
        raise RuntimeError("semantic_fusion_preregistration_output_exists")
    source_parquet = arguments.source_parquet.resolve(strict=True)
    source_prereg_path = arguments.source_preregistration.resolve(strict=True)
    development_path = arguments.development_artifact.resolve(strict=True)
    runtime_path = arguments.runtime_manifest.resolve(strict=True)
    nemotron_root = arguments.nemotron_directory.resolve(strict=True)
    wordfreq_root = arguments.wordfreq_root.resolve(strict=True)
    wheel_root = arguments.wheel_directory.resolve(strict=True)
    pyarrow_root = arguments.pyarrow_root.resolve(strict=True)
    pyarrow_wheel = arguments.pyarrow_wheel.resolve(strict=True)
    if (
        source_parquet.stat().st_size != SOURCE_BYTES
        or sha256(source_parquet) != SOURCE_SHA256
    ):
        raise RuntimeError("semantic_fusion_preregistration_source_changed")
    source_prereg = json.loads(source_prereg_path.read_text(encoding="utf-8-sig"))
    if (
        source_prereg.get("schema") != SOURCE_PREREG_SCHEMA
        or source_prereg.get("selection", {}).get("blind", {}).get("rowGroups") != [0, 1]
        or source_prereg.get("selection", {}).get("blind", {}).get("rows") != 200
        or source_prereg.get("partitionContract", {}).get("blindRowsOpened") is not False
    ):
        raise RuntimeError("semantic_fusion_preregistration_source_contract_invalid")
    development = json.loads(development_path.read_text(encoding="utf-8-sig"))
    if (
        development.get("schema") != DEVELOPMENT_SCHEMA
        or development.get("status") != "passed"
        or development.get("partition") != "development"
        or development.get("blindRowGroupsOpened") != []
        or development.get("candidatePromoted") is not False
        or development.get("effectsExecuted") != 0
        or not all(development.get("checks", {}).values())
    ):
        raise RuntimeError("semantic_fusion_preregistration_development_invalid")
    runtime = json.loads(runtime_path.read_text(encoding="utf-8-sig"))
    python_path = Path(str(runtime["python"])).resolve(strict=True)
    parakeet_root = Path(str(runtime["stt_dir"])).resolve(strict=True)
    if (
        runtime.get("schema") != "baxy-mind-runtime-v1"
        or sha256(python_path) != runtime.get("python_sha256")
        or runtime.get("stt_sha256")
        != "5a70e0862ca0ed713a2bb1bfd50bf4886ae027815c8634a3800da7bdec6ab28f"
    ):
        raise RuntimeError("semantic_fusion_preregistration_runtime_invalid")
    _validate_model(parakeet_root, PARAKEET_FILES, "parakeet")
    _validate_model(nemotron_root, NEMOTRON_FILES, "nemotron")

    blind_evaluator_path = (
        repository_root
        / "experiments/stt_quality/evaluate_servicenow_semantic_fusion_blind.py"
    )
    extractor_path = (
        repository_root / "experiments/stt_quality/extract_servicenow_codeswitch_blind.py"
    )
    extractor_module = _load_module(
        "baxy_semantic_fusion_blind_extractor_prereg_helper", extractor_path
    )
    pyarrow_tree = extractor_module.semantic_tree_commitment(pyarrow_root)
    if pyarrow_tree != {
        "files": 760,
        "bytes": 86_422_337,
        "sha256": "653012f1ce8d89dc343776c7e852a7e3efdef874eb0300fe0a96bbd53701b976",
    }:
        raise RuntimeError("semantic_fusion_preregistration_pyarrow_changed")
    if (
        pyarrow_wheel.name != "pyarrow-25.0.0-cp312-cp312-win_amd64.whl"
        or pyarrow_wheel.stat().st_size != 27_945_954
        or sha256(pyarrow_wheel)
        != "3f356afe61186395c861d5cd63dc21ff7d5fa335012a4668d979257df7fea0f5"
    ):
        raise RuntimeError("semantic_fusion_preregistration_pyarrow_wheel_changed")
    evaluator_module = _load_module(
        "baxy_semantic_fusion_blind_prereg_helper", blind_evaluator_path
    )
    semantic_tree = evaluator_module.semantic_tree_commitment(wordfreq_root)
    if semantic_tree != {
        "files": 190,
        "bytes": 64_558_794,
        "sha256": "4965b7d926c6a17c70094274668b6e813f46907df17cbbf2ba6a69da7e73579f",
    }:
        raise RuntimeError("semantic_fusion_preregistration_lexicon_changed")
    wheel_commitments: list[dict[str, object]] = []
    for name, expected_hash in sorted(WHEELS.items()):
        path = wheel_root / name
        if not path.is_file() or sha256(path) != expected_hash:
            raise RuntimeError(f"semantic_fusion_preregistration_wheel_changed:{name}")
        wheel_commitments.append(
            {"name": name, "bytes": path.stat().st_size, "sha256": expected_hash}
        )

    candidate_files = {
        "scorer": repository_root / "experiments/stt_quality/evaluate_reserved_stt.py",
        "sourceEvaluator": repository_root
        / "experiments/stt_quality/evaluate_servicenow_codeswitch_development.py",
        "developmentEvaluator": repository_root
        / "experiments/stt_quality/evaluate_servicenow_semantic_fusion_development.py",
        "fusion": repository_root / "experiments/stt_quality/semantic_stt_fusion_v4.py",
        "blindEvaluator": blind_evaluator_path,
        "blindExtractor": extractor_path,
        "lexiconPreparer": repository_root
        / "experiments/stt_quality/prepare_wordfreq_semantic_fusion.py",
        "lexiconRequirements": repository_root
        / "experiments/stt_quality/wordfreq_semantic_fusion_requirements.txt",
    }
    candidate = {
        key: {
            "path": path.relative_to(repository_root).as_posix(),
            "sha256": sha256(path),
        }
        for key, path in candidate_files.items()
    }
    generator = Path(__file__).resolve(strict=True)
    frozen_scorer = _load_module(
        "baxy_semantic_fusion_prereg_frozen_scorer", candidate_files["scorer"]
    )
    artifact: dict[str, object] = {
        "schema": SCHEMA,
        "createdAtUtc": arguments.created_at_utc,
        "partition": {"name": "blind", "rowGroups": [0, 1], "rows": 200},
        "source": {
            "path": source_parquet.as_posix(),
            "bytes": SOURCE_BYTES,
            "sha256": SOURCE_SHA256,
            "preregistration": {
                "path": source_prereg_path.relative_to(repository_root).as_posix(),
                "sha256": sha256(source_prereg_path),
            },
        },
        "developmentEvidence": {
            "path": development_path.relative_to(repository_root).as_posix(),
            "sha256": sha256(development_path),
            "metrics": development["metrics"],
        },
        "candidate": candidate,
        "runtime": {
            "manifest": runtime_path.as_posix(),
            "manifestSha256": sha256(runtime_path),
            "python": python_path.as_posix(),
            "pythonSha256": sha256(python_path),
        },
        "models": {
            "parakeet": {
                "path": parakeet_root.as_posix(),
                "mode": "offline_greedy_primary",
                "files": PARAKEET_FILES,
            },
            "nemotron": {
                "path": nemotron_root.as_posix(),
                "mode": "streaming_auto_secondary_for_structured_postal_addresses",
                "files": NEMOTRON_FILES,
            },
        },
        "lexicon": {
            "path": wordfreq_root.as_posix(),
            "semanticTree": semantic_tree,
            "wheels": wheel_commitments,
            "wheelDirectory": wheel_root.as_posix(),
            "languages": ["en", "es"],
            "wordLimitPerLanguage": 150_000,
            "benchmarkReferenceUsedToBuildLexicon": False,
        },
        "extractionRuntime": {
            "pyarrowVersion": "25.0.0",
            "pyarrowRoot": pyarrow_root.as_posix(),
            "semanticTree": pyarrow_tree,
            "wheel": {
                "path": pyarrow_wheel.as_posix(),
                "bytes": pyarrow_wheel.stat().st_size,
                "sha256": sha256(pyarrow_wheel),
            },
            "productRuntimeDependency": False,
        },
        "thresholds": THRESHOLDS,
        "latencyClock": {
            "primary": "offline_decode_after_end_of_speech",
            "secondary": "streaming_concurrent_with_capture_endpoint_finalization",
            "serialSecondaryTotalCpuTimeExcluded": True,
        },
        "contract": {
            "candidateFrozen": True,
            "blindRowsOpened": False,
            "developmentRowsOpened": 59,
            "syntheticAudio": True,
            "supplementalOnly": True,
            "finalPhysicalCertificationEligible": False,
            "candidatePromoted": False,
            "effectsExecuted": 0,
        },
        "wakeProgramTree": frozen_scorer._program_tree(repository_root),
        "generator": {
            "path": generator.relative_to(repository_root).as_posix(),
            "sha256": sha256(generator),
        },
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
    parser.add_argument("--source-parquet", type=Path, required=True)
    parser.add_argument("--source-preregistration", type=Path, required=True)
    parser.add_argument("--development-artifact", type=Path, required=True)
    parser.add_argument("--runtime-manifest", type=Path, required=True)
    parser.add_argument("--nemotron-directory", type=Path, required=True)
    parser.add_argument("--wordfreq-root", type=Path, required=True)
    parser.add_argument("--wheel-directory", type=Path, required=True)
    parser.add_argument("--pyarrow-root", type=Path, required=True)
    parser.add_argument("--pyarrow-wheel", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--created-at-utc", required=True)
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    artifact = preregister(arguments)
    print(
        json.dumps(
            {
                "artifact": str(arguments.artifact),
                "rows": artifact["partition"]["rows"],
                "sha256": sha256(arguments.artifact),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
