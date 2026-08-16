"""Build a hash-bound two-route BAXY wake cascade candidate."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
import math
from pathlib import Path
import shutil


def load_component(filename: str, name: str) -> object:
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"baxy_wake_routed_builder_component_invalid:{filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_V1 = load_component(
    "build_baxy_wake_cascade_candidate_v1.py",
    "_baxy_wake_routed_builder_v1_assets",
)


def build(
    *,
    legacy_original_fusion: Path,
    legacy_adapted_fusion: Path,
    expanded_adapted_fusion: Path,
    legacy_logmel_verifier: Path,
    expanded_logmel_verifier: Path,
    direct_lexical_logmel_verifier: Path | None = None,
    output_directory: Path,
    legacy_logmel_score_threshold: float,
    expanded_logmel_score_threshold: float,
    direct_lexical_logmel_score_threshold: float | None = None,
    direct_lexical_retry_speed_factors: tuple[float, ...] = (),
    direct_lexical_hotwords_score: float = 5.0,
    direct_lexical_minimum_consecutive_hops: int = 4,
    direct_lexical_phonetic_confusion_score_gte: float | None = None,
    endpoint_lexical_score_threshold: float | None = None,
    endpoint_lexical_retry_speed_factors: tuple[float, ...] = (),
    rescue_alias: str | None = None,
    rescue_logit_threshold: float | None = None,
    lexical_rescue_enabled: bool = False,
    expanded_include_original: bool = False,
) -> dict[str, object]:
    fusion_paths = [
        legacy_original_fusion.resolve(strict=True),
        legacy_adapted_fusion.resolve(strict=True),
        expanded_adapted_fusion.resolve(strict=True),
    ]
    fusion_assets = [_V1.fusion_assets(path) for path in fusion_paths]
    verifier_paths = [
        legacy_logmel_verifier.resolve(strict=True),
        expanded_logmel_verifier.resolve(strict=True),
    ]
    if direct_lexical_logmel_verifier is not None:
        verifier_paths.append(direct_lexical_logmel_verifier.resolve(strict=True))
    output = output_directory.resolve()
    partial = output.with_name(output.name + ".partial")
    if output.exists() or partial.exists():
        raise FileExistsError("baxy_wake_routed_cascade_output_exists")
    if (
        any(path.suffix.casefold() != ".onnx" for path in verifier_paths)
        or not all(
            math.isfinite(value)
            for value in (
                legacy_logmel_score_threshold,
                expanded_logmel_score_threshold,
            )
        )
        or (rescue_alias is None) != (rescue_logit_threshold is None)
        or (direct_lexical_logmel_verifier is None)
        != (direct_lexical_logmel_score_threshold is None)
        or direct_lexical_logmel_score_threshold is not None
        and not math.isfinite(direct_lexical_logmel_score_threshold)
        or len(direct_lexical_retry_speed_factors) > 3
        or not math.isfinite(direct_lexical_hotwords_score)
        or not 1.0 <= direct_lexical_hotwords_score <= 20.0
        or isinstance(direct_lexical_minimum_consecutive_hops, bool)
        or not isinstance(direct_lexical_minimum_consecutive_hops, int)
        or not 1 <= direct_lexical_minimum_consecutive_hops <= 12
        or direct_lexical_phonetic_confusion_score_gte is not None
        and not math.isfinite(direct_lexical_phonetic_confusion_score_gte)
        or endpoint_lexical_score_threshold is not None
        and (
            direct_lexical_logmel_verifier is None
            or not math.isfinite(endpoint_lexical_score_threshold)
        )
        or endpoint_lexical_score_threshold is None
        and bool(endpoint_lexical_retry_speed_factors)
        or any(
            not math.isfinite(value) or not 0.75 <= value <= 1.25
            for value in direct_lexical_retry_speed_factors
        )
        or len(set(direct_lexical_retry_speed_factors))
        != len(direct_lexical_retry_speed_factors)
        or len(endpoint_lexical_retry_speed_factors) > 3
        or any(
            not math.isfinite(value) or not 0.75 <= value <= 1.25
            for value in endpoint_lexical_retry_speed_factors
        )
        or len(set(endpoint_lexical_retry_speed_factors))
        != len(endpoint_lexical_retry_speed_factors)
        or rescue_alias is not None
        and rescue_alias not in _V1.ALIASES
        or rescue_logit_threshold is not None
        and not math.isfinite(rescue_logit_threshold)
        or len({assets[2].get("melFiltersSha256") for assets in fusion_assets}) != 1
        or len({_V1.sha256(assets[1]) for assets in fusion_assets}) != 1
    ):
        raise ValueError("baxy_wake_routed_cascade_component_mismatch")

    partial.mkdir(parents=True)
    files = {
        "hyperspotter-original.onnx": fusion_assets[0][0],
        "hyperspotter-legacy-adapted.onnx": fusion_assets[1][0],
        "hyperspotter-expanded-adapted.onnx": fusion_assets[2][0],
        "mel_80.npy": fusion_assets[0][1],
        "logmel-verifier-legacy.onnx": verifier_paths[0],
        "logmel-verifier-expanded.onnx": verifier_paths[1],
        **(
            {}
            if len(verifier_paths) == 2
            else {"logmel-verifier-direct-lexical.onnx": verifier_paths[2]}
        ),
    }
    for name, source in files.items():
        shutil.copyfile(source, partial / name)
    upstream_names = [
        "hyperspotter-original.onnx",
        "hyperspotter-legacy-adapted.onnx",
        "hyperspotter-expanded-adapted.onnx",
    ]
    verifier_names = [
        "logmel-verifier-legacy.onnx",
        "logmel-verifier-expanded.onnx",
        *(("logmel-verifier-direct-lexical.onnx",) if len(verifier_paths) == 3 else ()),
    ]
    verifier_thresholds = [
        legacy_logmel_score_threshold,
        expanded_logmel_score_threshold,
        *(
            (float(direct_lexical_logmel_score_threshold),)
            if direct_lexical_logmel_score_threshold is not None
            else ()
        ),
    ]
    manifest: dict[str, object] = {
        "schema": "baxy-wake-cascade-v2",
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "backend": "onnxruntime-hyperspotter-logmel-cascade",
        "phrase": "Baxy",
        "sampleRate": 16_000,
        "windowSamples": 48_000,
        "hopSamples": 4_000,
        "historyWindows": 20,
        "debounceSeconds": 2.0,
        "primaryLogitGte": 0.5,
        "secondaryLogitGte": 0.3,
        "acousticAliases": list(_V1.ALIASES),
        "lexicalAliases": ["baxy", "baxi", "boxy"],
        "lexicalRescueEnabled": lexical_rescue_enabled,
        "upstreamModels": [
            {"graph": name, "graphSha256": _V1.sha256(partial / name)}
            for name in upstream_names
        ],
        "melFilters": "mel_80.npy",
        "melFiltersSha256": _V1.sha256(partial / "mel_80.npy"),
        "logmelVerifiers": [
            {
                "graph": name,
                "graphSha256": _V1.sha256(partial / name),
                "scoreGte": threshold,
            }
            for name, threshold in zip(
                verifier_names,
                verifier_thresholds,
                strict=True,
            )
        ],
        "routes": [
            {
                "name": "legacy",
                "upstreamModelIndexes": [0, 1],
                "verifierIndex": 0,
            },
            {
                "name": "expanded_physical",
                "upstreamModelIndexes": (
                    [0, 1, 2] if expanded_include_original else [1, 2]
                ),
                "verifierIndex": 1,
            },
        ],
        **(
            {}
            if direct_lexical_logmel_score_threshold is None
            else {
                "directLexicalProposal": {
                    "verifierIndex": 2,
                    "scoreGte": direct_lexical_logmel_score_threshold,
                    "retrySpeedFactors": list(direct_lexical_retry_speed_factors),
                    "hotwordsScore": direct_lexical_hotwords_score,
                    "minimumConsecutiveHops": (direct_lexical_minimum_consecutive_hops),
                    **(
                        {}
                        if direct_lexical_phonetic_confusion_score_gte is None
                        else {
                            "phoneticConfusionScoreGte": (
                                direct_lexical_phonetic_confusion_score_gte
                            )
                        }
                    ),
                }
            }
        ),
        **(
            {}
            if endpoint_lexical_score_threshold is None
            else {
                "endpointLexicalProposal": {
                    "verifierIndex": 2,
                    "scoreGte": endpoint_lexical_score_threshold,
                    "aliases": ["baxy", "baxi", "bakse", "backsy", "boxy"],
                    "retrySpeedFactors": list(endpoint_lexical_retry_speed_factors),
                }
            }
        ),
        **(
            {}
            if rescue_alias is None
            else {
                "singleAliasRescue": {
                    "alias": rescue_alias,
                    "logitGte": rescue_logit_threshold,
                }
            }
        ),
        "calibration": {"approved": False},
        "sources": {
            "fusionManifestSha256": [_V1.sha256(path) for path in fusion_paths],
        },
        "approved": False,
        "developmentOnly": True,
        "effectsExecuted": 0,
    }
    manifest_path = partial / "baxy-wake-cascade-v2.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    bundle = {
        "schema": "baxy.wake-routed-cascade-candidate-bundle.v2",
        "manifest": manifest_path.name,
        "manifestSha256": _V1.sha256(manifest_path),
        "files": sorted([*files, manifest_path.name]),
        "approved": False,
        "effectsExecuted": 0,
    }
    (partial / "candidate.bundle.v2.json").write_text(
        json.dumps(bundle, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    partial.rename(output)
    return bundle


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legacy-original-fusion", type=Path, required=True)
    parser.add_argument("--legacy-adapted-fusion", type=Path, required=True)
    parser.add_argument("--expanded-adapted-fusion", type=Path, required=True)
    parser.add_argument("--legacy-logmel-verifier", type=Path, required=True)
    parser.add_argument("--expanded-logmel-verifier", type=Path, required=True)
    parser.add_argument("--direct-lexical-logmel-verifier", type=Path)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--legacy-logmel-score-threshold", type=float, required=True)
    parser.add_argument("--expanded-logmel-score-threshold", type=float, required=True)
    parser.add_argument("--direct-lexical-logmel-score-threshold", type=float)
    parser.add_argument(
        "--direct-lexical-retry-speed-factor",
        type=float,
        action="append",
        default=[],
    )
    parser.add_argument("--direct-lexical-hotwords-score", type=float, default=5.0)
    parser.add_argument(
        "--direct-lexical-minimum-consecutive-hops", type=int, default=4
    )
    parser.add_argument("--direct-lexical-phonetic-confusion-score-gte", type=float)
    parser.add_argument("--endpoint-lexical-score-threshold", type=float)
    parser.add_argument(
        "--endpoint-lexical-retry-speed-factor",
        type=float,
        action="append",
        default=[],
    )
    parser.add_argument("--rescue-alias", choices=_V1.ALIASES)
    parser.add_argument("--rescue-logit-threshold", type=float)
    parser.add_argument("--enable-lexical-rescue", action="store_true")
    parser.add_argument("--expanded-include-original", action="store_true")
    arguments = parser.parse_args()
    result = build(
        legacy_original_fusion=arguments.legacy_original_fusion,
        legacy_adapted_fusion=arguments.legacy_adapted_fusion,
        expanded_adapted_fusion=arguments.expanded_adapted_fusion,
        legacy_logmel_verifier=arguments.legacy_logmel_verifier,
        expanded_logmel_verifier=arguments.expanded_logmel_verifier,
        direct_lexical_logmel_verifier=arguments.direct_lexical_logmel_verifier,
        output_directory=arguments.output_directory,
        legacy_logmel_score_threshold=arguments.legacy_logmel_score_threshold,
        expanded_logmel_score_threshold=arguments.expanded_logmel_score_threshold,
        direct_lexical_logmel_score_threshold=(
            arguments.direct_lexical_logmel_score_threshold
        ),
        direct_lexical_retry_speed_factors=tuple(
            arguments.direct_lexical_retry_speed_factor
        ),
        direct_lexical_hotwords_score=arguments.direct_lexical_hotwords_score,
        direct_lexical_minimum_consecutive_hops=(
            arguments.direct_lexical_minimum_consecutive_hops
        ),
        direct_lexical_phonetic_confusion_score_gte=(
            arguments.direct_lexical_phonetic_confusion_score_gte
        ),
        endpoint_lexical_score_threshold=(arguments.endpoint_lexical_score_threshold),
        endpoint_lexical_retry_speed_factors=tuple(
            arguments.endpoint_lexical_retry_speed_factor
        ),
        rescue_alias=arguments.rescue_alias,
        rescue_logit_threshold=arguments.rescue_logit_threshold,
        lexical_rescue_enabled=arguments.enable_lexical_rescue,
        expanded_include_original=arguments.expanded_include_original,
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
