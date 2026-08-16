"""Evaluate opened R16 SAPI speech with the optional Nemotron streaming ASR."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(HERE))
import evaluate_r16_sapi_voice_semantics_development_v1 as base  # noqa: E402


EXPECTED_ROWS = 337
REPORT_SCHEMA = "baxy.r16-sapi-nemotron-streaming-development.v1"
CORPUS_SCHEMA = "baxy.r16-sapi-nemotron-streaming-transcript-development.v1"


def read_jsonl(path: Path) -> list[dict[str, object]]:
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]
    if any(not isinstance(row, dict) for row in rows):
        raise ValueError("baxy_nemotron_jsonl_invalid")
    return rows


def sha256_tree(path: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(path.rglob("*")):
        if not item.is_file():
            continue
        digest.update(item.relative_to(path).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(bytes.fromhex(base.sha256(item)))
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def decode_streaming(recognizer: object, audio: np.ndarray, language: str) -> str:
    stream = recognizer.create_stream()
    stream.set_option("language", language)
    chunk_samples = int(base.SAMPLE_RATE * 0.16)
    for start in range(0, len(audio), chunk_samples):
        stream.accept_waveform(
            base.SAMPLE_RATE,
            np.asarray(audio[start : start + chunk_samples], dtype=np.float32),
        )
        while recognizer.is_ready(stream):
            recognizer.decode_stream(stream)
    stream.input_finished()
    while recognizer.is_ready(stream):
        recognizer.decode_stream(stream)
    try:
        result = recognizer.get_result_all(stream)
    except Exception:  # noqa: BLE001 - compatibility with older sherpa builds
        result = stream.result
    return str(getattr(result, "text", "") or "").strip()


def evaluate(
    *,
    source_corpus_path: Path,
    parakeet_corpus_path: Path,
    model_path: Path,
    output_path: Path,
    transcript_output_path: Path,
    language: str,
) -> dict[str, object]:
    for candidate in (output_path, transcript_output_path):
        if candidate.exists():
            raise ValueError(f"baxy_nemotron_output_exists:{candidate}")
    source_corpus_path = source_corpus_path.resolve(strict=True)
    parakeet_corpus_path = parakeet_corpus_path.resolve(strict=True)
    model_path = model_path.resolve(strict=True)
    output_path = output_path.resolve()
    transcript_output_path = transcript_output_path.resolve()
    source_rows = read_jsonl(source_corpus_path)
    parakeet_rows = read_jsonl(parakeet_corpus_path)
    source_by_id = {str(row.get("case_id")): row for row in source_rows}
    if (
        len(source_rows) != 700
        or len(source_by_id) != 700
        or len(parakeet_rows) != EXPECTED_ROWS
        or len({str(row.get("case_id")) for row in parakeet_rows}) != EXPECTED_ROWS
        or any(row.get("execution_authority") is not False for row in parakeet_rows)
    ):
        raise ValueError("baxy_nemotron_population_invalid")
    for name in ("encoder.int8.onnx", "decoder.int8.onnx", "joiner.int8.onnx", "tokens.txt"):
        (model_path / name).resolve(strict=True)
    identities = {
        "sourceCorpusSha256": base.sha256(source_corpus_path),
        "parakeetCorpusSha256": base.sha256(parakeet_corpus_path),
        "modelTreeSha256": sha256_tree(model_path),
        "language": language,
    }
    checkpoint_path = output_path.with_suffix(output_path.suffix + ".partial.json")
    if checkpoint_path.exists():
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        if (
            checkpoint.get("identities") != identities
            or checkpoint.get("completed") != len(checkpoint.get("records", []))
        ):
            raise ValueError("baxy_nemotron_checkpoint_invalid")
    else:
        checkpoint = {
            "identities": identities,
            "completed": 0,
            "records": [],
            "synthesisSeconds": 0.0,
            "decodeSeconds": 0.0,
            "audioSeconds": 0.0,
        }

    import sherpa_onnx
    from baxy_mind.effect_intent import resolve_explicit_effects
    from baxy_mind.voice import SileroVad

    available_operations = frozenset(
        operation
        for row in parakeet_rows
        for accepted in base.accepted_effect_sets(row)
        for operation in accepted
    )
    recognizer = sherpa_onnx.OnlineRecognizer.from_transducer(
        encoder=str(model_path / "encoder.int8.onnx"),
        decoder=str(model_path / "decoder.int8.onnx"),
        joiner=str(model_path / "joiner.int8.onnx"),
        tokens=str(model_path / "tokens.txt"),
        num_threads=max(2, min(6, (os.cpu_count() or 4) // 2)),
        model_type="nemo_transducer",
        decoding_method="greedy_search",
        enable_endpoint_detection=False,
        provider="cpu",
    )
    warmup = np.zeros(base.SAMPLE_RATE // 2, dtype=np.float32)
    decode_streaming(recognizer, warmup, language)
    vad = SileroVad()
    synthesizer = base.SapiSynthesizer()
    started = time.perf_counter()
    try:
        start_at = int(checkpoint["completed"])
        for index, transcript_row in enumerate(parakeet_rows[start_at:], start=start_at):
            case_id = str(transcript_row.get("case_id"))
            source = source_by_id.get(case_id)
            if (
                source is None
                or transcript_row.get("voice_reference_text_sha256")
                != hashlib.sha256(str(source.get("text", "")).encode("utf-8")).hexdigest()
            ):
                raise ValueError(f"baxy_nemotron_binding_invalid:{case_id}")
            began = time.perf_counter()
            speech_language = str(source.get("language"))
            audio = synthesizer.synthesize(
                "409" if speech_language == "en" else "80A",
                str(source.get("text")),
                rate=(-1, 0, 1)[index % 3],
            )
            checkpoint["synthesisSeconds"] += time.perf_counter() - began
            segmented = base.segment_with_product_vad(vad, audio)
            began = time.perf_counter()
            text = (
                decode_streaming(recognizer, segmented, language)
                if segmented is not None
                else ""
            )
            checkpoint["decodeSeconds"] += time.perf_counter() - began
            checkpoint["audioSeconds"] += len(audio) / base.SAMPLE_RATE
            intent = (
                resolve_explicit_effects(text, available_operations) if text else None
            )
            actual = tuple(intent.operations) if intent is not None else ()
            reference_words = base.normalized_words(str(source.get("text")))
            hypothesis_words = base.normalized_words(text)
            checkpoint["records"].append(
                {
                    "caseId": case_id,
                    "language": speech_language,
                    "rate": (-1, 0, 1)[index % 3],
                    "vadSegmented": segmented is not None,
                    "transcript": text,
                    "referenceWordCount": len(reference_words),
                    "wordEdits": base.edit_distance(reference_words, hypothesis_words),
                    "actualOperations": list(actual),
                    "deterministicSemanticCorrect": actual
                    in base.accepted_effect_sets(source),
                    "unsafeEffect": source.get("outcome") != "action" and bool(actual),
                }
            )
            checkpoint["completed"] = index + 1
            write_json(checkpoint_path, checkpoint)
            print(f"BAXY_R16_NEMOTRON|{index + 1}/{EXPECTED_ROWS}", flush=True)
    finally:
        synthesizer.close()

    records = checkpoint["records"]
    total_words = sum(int(row["referenceWordCount"]) for row in records)
    metrics = {
        "cases": len(records),
        "deterministicSemanticCorrect": sum(
            bool(row["deterministicSemanticCorrect"]) for row in records
        ),
        "semanticAccuracy": sum(
            bool(row["deterministicSemanticCorrect"]) for row in records
        ) / len(records),
        "wordErrorRate": sum(int(row["wordEdits"]) for row in records) / total_words,
        "unsafeEffects": sum(bool(row["unsafeEffect"]) for row in records),
        "allVadSegmented": all(bool(row["vadSegmented"]) for row in records),
        "audioSeconds": checkpoint["audioSeconds"],
        "synthesisSeconds": checkpoint["synthesisSeconds"],
        "decodeSeconds": checkpoint["decodeSeconds"],
        "audioRealtimeFactor": checkpoint["decodeSeconds"] / checkpoint["audioSeconds"],
    }
    report = {
        "schema": REPORT_SCHEMA,
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "scope": "opened_r16_local_sapi_post_wake_vad_nemotron_streaming_semantics",
        "sources": identities,
        "inference": {
            "model": "nemotron-3.5-asr-streaming-0.6b-560ms-int8",
            "provider": "cpu",
            "language": language,
            "chunkMilliseconds": 160,
        },
        "metrics": metrics,
        "runtimeSeconds": time.perf_counter() - started,
        "records": records,
        "developmentOnly": True,
        "humanMicrophoneClaimSupported": False,
        "blindHoldoutClaimSupported": False,
        "candidateFrozen": False,
        "productOperatingPoint": False,
        "effectsExecuted": 0,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(output_path, report)
    corpus_rows = []
    for source_row, record in zip(parakeet_rows, records, strict=True):
        row = dict(source_row)
        row.update(
            {
                "schema": CORPUS_SCHEMA,
                "text": record["transcript"],
                "transcript_authority": "nemotron_streaming_candidate",
            }
        )
        corpus_rows.append(row)
    temporary = transcript_output_path.with_suffix(transcript_output_path.suffix + ".tmp")
    temporary.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
            for row in corpus_rows
        ),
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, transcript_output_path)
    checkpoint_path.unlink(missing_ok=True)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-corpus", type=Path, required=True)
    parser.add_argument("--parakeet-corpus", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--transcript-output", type=Path, required=True)
    parser.add_argument("--language", default="auto")
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = evaluate(
        source_corpus_path=arguments.source_corpus,
        parakeet_corpus_path=arguments.parakeet_corpus,
        model_path=arguments.model,
        output_path=arguments.output,
        transcript_output_path=arguments.transcript_output,
        language=arguments.language,
    )
    print(json.dumps(report["metrics"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
