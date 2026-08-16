"""Rebind an unchanged fusion graph to a new development CTC bundle."""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def _load_component() -> object:
    path = Path(__file__).with_name(
        "audit_baxy_hyperspotter_fusion_product_candidate_v1.py"
    )
    spec = importlib.util.spec_from_file_location(
        "_baxy_fusion_rebind_audit_v1", path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("baxy_fusion_rebind_component_invalid")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_PRODUCT = _load_component()
load_fusion_candidate = _PRODUCT.load_fusion_candidate
read_object = _PRODUCT.read_object
sha256 = _PRODUCT.sha256


def _adjacent(manifest: Path, value: object, suffix: str) -> Path:
    if not isinstance(value, str) or Path(value).name != value or not value.endswith(suffix):
        raise ValueError("baxy_fusion_rebind_asset_name_invalid")
    path = (manifest.parent / value).resolve(strict=True)
    if path.parent != manifest.parent:
        raise ValueError("baxy_fusion_rebind_asset_path_invalid")
    return path


def _hardlink(source: Path, destination: Path) -> None:
    if destination.exists():
        raise FileExistsError(f"baxy_fusion_rebind_destination_exists:{destination}")
    os.link(source.resolve(strict=True), destination)


def rebind(
    *,
    source_manifest_path: Path,
    ctc_manifest_path: Path,
    output_directory: Path,
) -> dict[str, object]:
    source_manifest_path = source_manifest_path.resolve(strict=True)
    ctc_manifest_path = ctc_manifest_path.resolve(strict=True)
    output_directory = output_directory.resolve()
    if output_directory.exists():
        raise FileExistsError(f"baxy_fusion_rebind_output_exists:{output_directory}")

    source = read_object(source_manifest_path)
    ctc = read_object(ctc_manifest_path)
    if (
        source.get("schema") != "baxy-hyperspotter-fusion-v1"
        or source.get("approved") is not False
        or source.get("developmentOnly") is not True
        or source.get("blindHumanAudioAccessed") is not False
        or source.get("effectsExecuted") != 0
        or ctc.get("schema") != "baxy-wake-verifier-v1"
    ):
        raise ValueError("baxy_fusion_rebind_manifest_invalid")

    graph = _adjacent(source_manifest_path, source.get("graph"), ".onnx")
    mel = _adjacent(source_manifest_path, source.get("melFilters"), ".npy")
    if (
        sha256(graph) != source.get("graphSha256")
        or graph.stat().st_size != source.get("graphBytes")
        or sha256(mel) != source.get("melFiltersSha256")
    ):
        raise ValueError("baxy_fusion_rebind_source_hash_mismatch")

    assets = [graph, mel]
    runtime_calibration = source.get("runtimeCalibration")
    if runtime_calibration is not None:
        if not isinstance(runtime_calibration, dict):
            raise ValueError("baxy_fusion_rebind_runtime_calibration_invalid")
        calibration = _adjacent(
            source_manifest_path,
            runtime_calibration.get("report"),
            ".json",
        )
        if sha256(calibration) != runtime_calibration.get("reportSha256"):
            raise ValueError("baxy_fusion_rebind_runtime_calibration_hash_mismatch")
        assets.append(calibration)

    output_directory.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(
            prefix=f".{output_directory.name}.",
            dir=output_directory.parent,
        )
    )
    try:
        for asset in assets:
            _hardlink(asset, temporary / asset.name)
        manifest = copy.deepcopy(source)
        manifest["measuredAtUtc"] = datetime.now(timezone.utc).isoformat()
        manifest["ctcVerifierManifestSha256"] = sha256(ctc_manifest_path)
        manifest["approved"] = False
        manifest["developmentOnly"] = True
        manifest["blindHumanAudioAccessed"] = False
        manifest["effectsExecuted"] = 0
        manifest["developmentRebind"] = {
            "schema": "baxy.hyperspotter-fusion-development-rebind.v1",
            "sourceManifestSha256": sha256(source_manifest_path),
            "ctcVerifierManifestSha256": sha256(ctc_manifest_path),
            "graphChanged": False,
            "policyChanged": False,
        }
        manifest_path = temporary / "baxy-hyperspotter-fusion-v1.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        load_fusion_candidate(manifest_path, ctc_manifest_path)
        bundle = {
            "schema": "baxy.hyperspotter-fusion-development-rebind-bundle.v1",
            "manifest": manifest_path.name,
            "manifestSha256": sha256(manifest_path),
            "sourceManifestSha256": sha256(source_manifest_path),
            "ctcVerifierManifestSha256": sha256(ctc_manifest_path),
            "assets": [asset.name for asset in assets],
            "candidateFrozen": False,
            "blindHumanAudioAccessed": False,
            "effectsExecuted": 0,
        }
        (temporary / "candidate.bundle.v1.json").write_text(
            json.dumps(bundle, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        temporary.rename(output_directory)
        return bundle
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--ctc-verifier-manifest", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = rebind(
        source_manifest_path=arguments.source_manifest,
        ctc_manifest_path=arguments.ctc_verifier_manifest,
        output_directory=arguments.output_directory,
    )
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
