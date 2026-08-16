"""Measure Parakeet modified-beam decoding on opened ServiceNow development."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
from typing import Any

import numpy as np


ENGINE = "parakeet_modified_beam"
SAMPLE_RATE = 16_000


def _load(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise RuntimeError(f"servicenow_modified_beam_import_failed:{name}")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


class ParakeetModifiedBeamStt:
    def __init__(self, model_directory: Path) -> None:
        import sherpa_onnx

        started = time.perf_counter()
        self._recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
            encoder=str(model_directory / "encoder.int8.onnx"),
            decoder=str(model_directory / "decoder.int8.onnx"),
            joiner=str(model_directory / "joiner.int8.onnx"),
            tokens=str(model_directory / "tokens.txt"),
            num_threads=max(2, min(6, (os.cpu_count() or 4) // 2)),
            model_type="nemo_transducer",
            decoding_method="modified_beam_search",
            max_active_paths=8,
        )
        self.load_seconds = time.perf_counter() - started
        self.status = {
            "loaded": True,
            "model": "parakeet-tdt-0.6b-v3-int8",
            "provider": "cpu",
            "decodingMethod": "modified_beam_search",
            "maxActivePaths": 8,
            "hotwords": False,
        }
        self.last_diagnostics: dict[str, float] = {}
        stream = self._recognizer.create_stream()
        stream.accept_waveform(
            SAMPLE_RATE, np.zeros(SAMPLE_RATE // 2, dtype=np.float32)
        )
        self._recognizer.decode_stream(stream)

    def transcribe(
        self, audio: np.ndarray, _language: str | None = None
    ) -> tuple[str, str, float]:
        stream = self._recognizer.create_stream()
        stream.accept_waveform(SAMPLE_RATE, audio)
        started = time.perf_counter()
        self._recognizer.decode_stream(stream)
        latency = time.perf_counter() - started
        text = str(stream.result.text or "").strip()
        self.last_diagnostics = {
            "finalizationLatencySeconds": latency,
            "maximumChunkDecodeSeconds": latency,
        }
        return text, text, latency


def evaluate(arguments: argparse.Namespace) -> dict[str, Any]:
    repository_root = arguments.repository_root.resolve(strict=True)
    base_path = (
        repository_root
        / "experiments/stt_quality/evaluate_servicenow_codeswitch_development.py"
    )
    base = _load("baxy_servicenow_modified_beam_base", base_path)

    def candidate(
        candidate_arguments: argparse.Namespace,
        _frozen: Any,
        contract: dict[str, Any],
    ) -> ParakeetModifiedBeamStt:
        runtime = json.loads(
            Path(str(contract["runtime"]["path"])).read_text(
                encoding="utf-8-sig"
            )
        )
        return ParakeetModifiedBeamStt(Path(str(runtime["stt_dir"])))

    base._candidate = candidate
    base_arguments = argparse.Namespace(
        repository_root=repository_root,
        extraction=arguments.extraction,
        base_contract=arguments.base_contract,
        engine=ENGINE,
        qwen_directory=None,
        qwen_archive=None,
        threads=6,
        detail_output=arguments.detail_output,
        artifact=arguments.artifact,
    )
    artifact = base.evaluate(base_arguments)
    wrapper_path = Path(__file__).resolve(strict=True)
    artifact["baseEvaluator"] = artifact["evaluator"]
    artifact["evaluator"] = {
        "path": wrapper_path.relative_to(repository_root).as_posix(),
        "sha256": base.sha256(wrapper_path),
    }
    artifact["candidateImplementation"] = artifact["evaluator"]
    arguments.artifact.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return artifact


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--extraction", type=Path, required=True)
    parser.add_argument("--base-contract", type=Path, required=True)
    parser.add_argument("--detail-output", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    artifact = evaluate(arguments)
    base = _load(
        "baxy_servicenow_modified_beam_hash",
        arguments.repository_root.resolve(strict=True)
        / "experiments/stt_quality/evaluate_servicenow_codeswitch_development.py",
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
