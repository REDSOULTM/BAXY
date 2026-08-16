"""Build a hash-bound, non-authoritative BAXY wake cascade bundle."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import shutil


ALIASES = ["baxy", "baxi", "basi", "bakse"]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def fusion_assets(path: Path) -> tuple[Path, Path, dict[str, object]]:
    manifest = path.resolve(strict=True)
    value = json.loads(manifest.read_text(encoding="utf-8"))
    if (
        not isinstance(value, dict)
        or value.get("schema") != "baxy-hyperspotter-fusion-v1"
        or value.get("aliases") != ALIASES
        or value.get("sampleRate") != 16_000
        or value.get("audioSamples") != 48_000
        or value.get("logmelFrames") != 300
        or value.get("logmelBins") != 80
    ):
        raise ValueError("baxy_wake_cascade_fusion_manifest_invalid")
    graph = (manifest.parent / str(value.get("graph") or "")).resolve(strict=True)
    mel = (manifest.parent / str(value.get("melFilters") or "")).resolve(strict=True)
    graph.relative_to(manifest.parent.resolve(strict=True))
    mel.relative_to(manifest.parent.resolve(strict=True))
    if (
        graph.suffix.casefold() != ".onnx"
        or mel.suffix.casefold() != ".npy"
        or sha256(graph) != value.get("graphSha256")
        or sha256(mel) != value.get("melFiltersSha256")
    ):
        raise ValueError("baxy_wake_cascade_fusion_asset_invalid")
    return graph, mel, value


def build(
    *,
    original_fusion: Path,
    adapted_fusion: Path,
    logmel_verifier: Path,
    output_directory: Path,
    logmel_score_threshold: float = 3.0,
    rescue_alias: str | None = None,
    rescue_logit_threshold: float | None = None,
    lexical_rescue_enabled: bool = True,
) -> dict[str, object]:
    original_graph, original_mel, original = fusion_assets(original_fusion)
    adapted_graph, adapted_mel, adapted = fusion_assets(adapted_fusion)
    verifier = logmel_verifier.resolve(strict=True)
    output = output_directory.resolve()
    partial = output.with_name(output.name + ".partial")
    if output.exists() or partial.exists():
        raise FileExistsError("baxy_wake_cascade_output_exists")
    if (
        verifier.suffix.casefold() != ".onnx"
        or not math.isfinite(logmel_score_threshold)
        or (rescue_alias is None) != (rescue_logit_threshold is None)
        or rescue_alias is not None and rescue_alias not in ALIASES
        or rescue_logit_threshold is not None
        and not math.isfinite(rescue_logit_threshold)
        or original.get("melFiltersSha256") != adapted.get("melFiltersSha256")
        or sha256(original_mel) != sha256(adapted_mel)
    ):
        raise ValueError("baxy_wake_cascade_component_mismatch")
    partial.mkdir(parents=True)
    files = {
        "hyperspotter-original.onnx": original_graph,
        "hyperspotter-adapted.onnx": adapted_graph,
        "mel_80.npy": original_mel,
        "logmel-verifier.onnx": verifier,
    }
    for name, source in files.items():
        shutil.copyfile(source, partial / name)
    manifest: dict[str, object] = {
        "schema": "baxy-wake-cascade-v1",
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
        "acousticAliases": ALIASES,
        "lexicalAliases": ["baxy", "baxi", "boxy"],
        "lexicalRescueEnabled": lexical_rescue_enabled,
        "upstreamModels": [
            {
                "graph": "hyperspotter-original.onnx",
                "graphSha256": sha256(partial / "hyperspotter-original.onnx"),
            },
            {
                "graph": "hyperspotter-adapted.onnx",
                "graphSha256": sha256(partial / "hyperspotter-adapted.onnx"),
            },
        ],
        "melFilters": "mel_80.npy",
        "melFiltersSha256": sha256(partial / "mel_80.npy"),
        "logmelVerifier": {
            "graph": "logmel-verifier.onnx",
            "graphSha256": sha256(partial / "logmel-verifier.onnx"),
            "scoreGte": logmel_score_threshold,
        },
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
            "originalFusionManifestSha256": sha256(original_fusion.resolve()),
            "adaptedFusionManifestSha256": sha256(adapted_fusion.resolve()),
        },
        "approved": False,
        "developmentOnly": True,
        "effectsExecuted": 0,
    }
    manifest_path = partial / "baxy-wake-cascade-v1.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    bundle = {
        "schema": "baxy.wake-cascade-candidate-bundle.v1",
        "manifest": manifest_path.name,
        "manifestSha256": sha256(manifest_path),
        "files": sorted([*files, manifest_path.name]),
        "approved": False,
        "effectsExecuted": 0,
    }
    (partial / "candidate.bundle.v1.json").write_text(
        json.dumps(bundle, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    partial.rename(output)
    return bundle


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original-fusion", type=Path, required=True)
    parser.add_argument("--adapted-fusion", type=Path, required=True)
    parser.add_argument("--logmel-verifier", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--logmel-score-threshold", type=float, default=3.0)
    parser.add_argument("--rescue-alias", choices=ALIASES)
    parser.add_argument("--rescue-logit-threshold", type=float)
    parser.add_argument("--disable-lexical-rescue", action="store_true")
    args = parser.parse_args()
    result = build(
        original_fusion=args.original_fusion,
        adapted_fusion=args.adapted_fusion,
        logmel_verifier=args.logmel_verifier,
        output_directory=args.output_directory,
        logmel_score_threshold=args.logmel_score_threshold,
        rescue_alias=args.rescue_alias,
        rescue_logit_threshold=args.rescue_logit_threshold,
        lexical_rescue_enabled=not args.disable_lexical_rescue,
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
