"""Evaluate semantic-risk-aware ServiceNow STT fusion on development data."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys


SCHEMA = "baxy.servicenow-codeswitch-semantic-fusion-development.v4"


def _load_module(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise RuntimeError(f"semantic_fusion_v4_import_failed:{name}")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def evaluate(arguments: argparse.Namespace) -> dict[str, object]:
    repository_root = arguments.repository_root.resolve(strict=True)
    evaluator_path = Path(__file__).resolve(strict=True)
    v2 = _load_module(
        "baxy_servicenow_semantic_fusion_v2_for_v4",
        repository_root
        / "experiments/stt_quality/evaluate_servicenow_semantic_fusion_development_v2.py",
    )
    original_load_v1 = v2._load_v1

    def load_v1_with_semantic_risk_fusion(root: Path):
        base = original_load_v1(root)
        original_load_module = base._load_module

        def load_module(name: str, path: Path):
            if name == "baxy_semantic_stt_fusion_development":
                path = root / "experiments/stt_quality/semantic_stt_fusion_v4.py"
            return original_load_module(name, path)

        base._load_module = load_module
        return base

    v2._load_v1 = load_v1_with_semantic_risk_fusion
    v2.SCHEMA = SCHEMA
    v2.__file__ = str(evaluator_path)
    artifact = v2.evaluate(arguments)

    hash_module = original_load_v1(repository_root)
    fusion_path = (
        repository_root / "experiments/stt_quality/semantic_stt_fusion_v4.py"
    )
    predecessor_path = (
        repository_root
        / "artifacts/development/servicenow_codeswitch_semantic_fusion_development_v3.json"
    )
    artifact["evaluator"] = {
        "path": evaluator_path.relative_to(repository_root).as_posix(),
        "sha256": hash_module.sha256(evaluator_path),
    }
    artifact["fusion"] = {
        "path": fusion_path.relative_to(repository_root).as_posix(),
        "sha256": hash_module.sha256(fusion_path),
    }
    artifact["predecessor"] = {
        "path": predecessor_path.relative_to(repository_root).as_posix(),
        "sha256": hash_module.sha256(predecessor_path),
        "status": "passed_with_overbroad_clarification_flag",
        "reason": "orthographic_aliases_were_counted_as_semantic_ambiguities",
    }
    artifact["semanticRiskRevision"] = {
        "clarificationReasons": [
            "address_homophone",
            "bilingual_device_brand",
            "multi_asr_proper_name",
        ],
        "writtenAliasesPreservedWithoutClarification": True,
        "qualityThresholdsChanged": False,
        "latencyThresholdsChanged": False,
        "blindRowsOpened": False,
    }
    artifact_path = arguments.artifact.resolve()
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
    repository_root = arguments.repository_root.resolve(strict=True)
    base = _load_module(
        "baxy_servicenow_semantic_fusion_v1_hash_v4",
        repository_root
        / "experiments/stt_quality/evaluate_servicenow_semantic_fusion_development.py",
    )
    print(
        json.dumps(
            {
                "artifact": str(arguments.artifact),
                "status": artifact["status"],
                "sha256": base.sha256(arguments.artifact),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
