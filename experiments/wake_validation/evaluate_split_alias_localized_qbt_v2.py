"""Evaluate a localized CTC QbT margin for split lexical wake aliases.

V1 proved that an exact greedy teacher path is too strict.  This follow-up
uses the already-published target-vs-confusable CTC recurrence and 0.5 margin,
but scores only the leading two-word span that made Parakeet propose the split
alias.  No other wake route can change.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys
import time
from typing import Any, Iterable, Sequence


ROOT = Path(__file__).resolve().parents[2]
VOICE = ROOT / "experiments" / "voice_latency"
WAKE_VALIDATION = ROOT / "experiments" / "wake_validation"
for entry in (ROOT / "src", ROOT / "scripts", VOICE, WAKE_VALIDATION):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import evaluate_split_alias_ctc_guard_v1 as v1  # noqa: E402


SCHEMA = "baxy.split-alias-localized-qbt-development.v2"
BINDING_SCHEMA = "baxy.split-alias-localized-qbt-binding.v2"
FRAME_SECONDS = 0.02
CONTEXT_FRAMES = 10
DECISION_MARGIN = 0.5
SAMPLE_RATE = 16_000


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"json_object_required:{path}")
    return value


def leading_word_locator_seconds(
    tokens: Sequence[str],
    timestamps: Sequence[float],
    durations: Sequence[float],
    *,
    speed_factor: float,
    word_count: int = 2,
) -> tuple[float, float]:
    if (
        len(tokens) != len(timestamps)
        or len(tokens) != len(durations)
        or not tokens
        or word_count <= 0
        or not math.isfinite(speed_factor)
        or speed_factor <= 0.0
    ):
        raise ValueError("split_alias_locator_inputs_invalid")
    starts = [0]
    for index, token in enumerate(tokens[1:], start=1):
        if token.startswith((" ", "▁")):
            starts.append(index)
    if len(starts) < word_count:
        raise ValueError("split_alias_locator_words_missing")
    end_index = starts[word_count] if len(starts) > word_count else len(tokens)
    final_token = end_index - 1
    start = float(timestamps[starts[0]]) * speed_factor
    end = (
        float(timestamps[final_token]) + float(durations[final_token])
    ) * speed_factor
    if (
        not math.isfinite(start)
        or not math.isfinite(end)
        or start < 0.0
        or end <= start
    ):
        raise ValueError("split_alias_locator_time_invalid")
    return start, end


def locator_frames(start_seconds: float, end_seconds: float) -> tuple[int, int]:
    start = max(0, math.floor(start_seconds / FRAME_SECONDS))
    end = max(start + 1, math.ceil(end_seconds / FRAME_SECONDS))
    return start, end


def qbt_accepts(margin: float | None) -> bool:
    return bool(
        margin is not None and math.isfinite(margin) and margin >= DECISION_MARGIN
    )


def summarize(
    records: Iterable[dict[str, Any]],
    *,
    current_confusable_positive_hashes: frozenset[str],
    current_confusable_negative_hashes: frozenset[str],
) -> dict[str, Any]:
    return v1.summarize(
        records,
        current_confusable_positive_hashes=current_confusable_positive_hashes,
        current_confusable_negative_hashes=current_confusable_negative_hashes,
    )


def _validate_file(path: Path, expected: str, code: str) -> Path:
    resolved = path.resolve(strict=True)
    if sha256(resolved) != expected:
        raise ValueError(code)
    return resolved


def _validate_base(binding: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    base = binding.get("base")
    if not isinstance(base, dict):
        raise ValueError("split_alias_qbt_base_missing")
    base_binding_path = _validate_file(
        Path(str(base.get("bindingPath"))),
        str(base.get("bindingSha256")),
        "split_alias_qbt_base_binding_mismatch",
    )
    base_report_path = _validate_file(
        Path(str(base.get("reportPath"))),
        str(base.get("reportSha256")),
        "split_alias_qbt_base_report_mismatch",
    )
    base_binding = read_json(base_binding_path)
    base_report = read_json(base_report_path)
    if (
        base_binding.get("schema") != v1.BINDING_SCHEMA
        or base_report.get("schema") != v1.SCHEMA
        or base_report.get("bindingSha256") != sha256(base_binding_path)
        or base_report.get("physicalV17Read") is not False
        or base_report.get("runtimeModified") is not False
        or base_report.get("effectsExecuted") != 0
    ):
        raise ValueError("split_alias_qbt_base_contract_invalid")
    _validate_file(
        Path(str(base_binding["test"]["path"])),
        str(base_binding["test"]["sha256"]),
        "split_alias_qbt_base_test_mismatch",
    )
    teacher_root = Path(str(base_binding["teacher"]["root"])).resolve(strict=True)
    _validate_file(
        teacher_root / "pytorch_model.bin",
        str(base_binding["teacher"]["weightsSha256"]),
        "split_alias_qbt_teacher_mismatch",
    )
    _validate_file(
        teacher_root / "config.json",
        str(base_binding["teacher"]["configSha256"]),
        "split_alias_qbt_teacher_config_mismatch",
    )
    _validate_file(
        Path(str(base_binding["cascade"]["manifest"])),
        str(base_binding["cascade"]["manifestSha256"]),
        "split_alias_qbt_cascade_mismatch",
    )
    stt = base_binding["stt"]
    stt_root = Path(str(stt["root"])).resolve(strict=True)
    for name, expected in stt["filesSha256"].items():
        _validate_file(
            stt_root / name, expected, f"split_alias_qbt_stt_mismatch:{name}"
        )
    sherpa_root = Path(str(stt["sherpaSitePackages"])).resolve(strict=True)
    for name, expected in stt["sherpaFilesSha256"].items():
        _validate_file(
            sherpa_root / name,
            expected,
            f"split_alias_qbt_sherpa_mismatch:{name}",
        )
    for corpus in base_binding["corpora"]:
        root = Path(str(corpus["root"])).resolve(strict=True)
        if "v17" in root.as_posix().casefold():
            raise ValueError("split_alias_qbt_physical_v17_forbidden")
        _validate_file(
            root / "manifest.v1.json",
            str(corpus["manifestSha256"]),
            f"split_alias_qbt_corpus_mismatch:{corpus['name']}",
        )
        if "sourceReport" in corpus:
            _validate_file(
                Path(str(corpus["sourceReport"]["path"])),
                str(corpus["sourceReport"]["sha256"]),
                f"split_alias_qbt_source_report_mismatch:{corpus['name']}",
            )
    current = base_binding["currentEndpointConfusableCascade"]
    _validate_file(
        Path(str(current["path"])),
        str(current["sha256"]),
        "split_alias_qbt_current_cascade_mismatch",
    )
    return base_binding, base_report


def _resolve_binding(
    binding_path: Path, output_path: Path
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    binding_path = binding_path.resolve(strict=True)
    binding = read_json(binding_path)
    if binding.get("schema") != BINDING_SCHEMA:
        raise ValueError("split_alias_qbt_binding_schema_invalid")
    if sha256(Path(__file__).resolve()) != binding.get("programSha256"):
        raise ValueError("split_alias_qbt_program_mismatch")
    _validate_file(
        Path(str(binding["test"]["path"])),
        str(binding["test"]["sha256"]),
        "split_alias_qbt_test_mismatch",
    )
    planned = Path(str(binding.get("plannedOutput"))).resolve()
    if planned != output_path.resolve():
        raise ValueError("split_alias_qbt_output_mismatch")
    if planned.exists():
        raise FileExistsError(f"split_alias_qbt_output_exists:{planned}")
    expected_contract = {
        "route": v1.SPLIT_METHOD,
        "locator": "parakeet_leading_two_words_mapped_to_original_audio",
        "score": "ctc_target_vs_declared_confusable_qbt_margin",
        "contextFrames": CONTEXT_FRAMES,
        "decisionMarginGte": DECISION_MARGIN,
        "allOtherRoutesUnchanged": True,
        "positivePreservationRequired": True,
        "negativeFalseActivationsRequired": 0,
        "physicalV17Read": False,
        "runtimeModificationAllowed": False,
        "promotionEligible": False,
        "effectsExecuted": 0,
    }
    if binding.get("contract") != expected_contract:
        raise ValueError("split_alias_qbt_contract_invalid")
    base_binding, base_report = _validate_base(binding)
    return binding, base_binding, base_report


def _selected_paths(
    base_binding: dict[str, Any], base_report: dict[str, Any], room: Any
) -> list[dict[str, Any]]:
    wanted = {
        str(record["audioSha256"]): {
            "corpus": str(record["corpus"]),
            "label": str(record["label"]),
        }
        for record in base_report["records"]
    }
    if len(wanted) != len(base_report["records"]):
        raise ValueError("split_alias_qbt_base_record_duplicate")
    found: dict[str, Path] = {}
    for corpus in base_binding["corpora"]:
        corpus_wanted = {
            audio_hash: value
            for audio_hash, value in wanted.items()
            if value["corpus"] == corpus["name"]
        }
        for label in sorted({value["label"] for value in corpus_wanted.values()}):
            for path in room._wav_paths(Path(str(corpus["root"])) / label, None):
                audio_hash = room._sha256(path)
                if audio_hash in corpus_wanted:
                    found[audio_hash] = path
    if set(found) != set(wanted):
        raise ValueError("split_alias_qbt_audio_path_missing")
    return [
        {**wanted[audio_hash], "audioSha256": audio_hash, "path": found[audio_hash]}
        for audio_hash in wanted
    ]


def _decode_locator(
    audio: Any,
    *,
    recognizer: Any,
    hotwords: str,
    aliases: frozenset[str],
    retry_speed_factors: tuple[float, ...],
    phonetic_confusion_score_gte: float,
    endpoint: Any,
    wake_cascade: Any,
) -> tuple[int, int, float]:
    import numpy as np

    for factor in (1.0, *retry_speed_factors):
        view = (
            audio
            if factor == 1.0
            else wake_cascade.time_scaled_recognition_audio(audio, factor)
        )
        stream = recognizer.create_stream(hotwords=hotwords)
        stream.accept_waveform(SAMPLE_RATE, np.asarray(view, dtype=np.float32))
        recognizer.decode_stream(stream)
        result = stream.result
        match = endpoint.match_endpoint_policy(
            (result.text or "").strip(),
            aliases,
            policy="bounded_development",
            verifier_score=0.0,
            phonetic_confusion_score_gte=phonetic_confusion_score_gte,
            endpoint_direct_score_gte=0.0,
        )
        if getattr(match, "method", None) != v1.SPLIT_METHOD:
            if match is not None:
                raise ValueError("split_alias_qbt_route_changed")
            continue
        start, end = leading_word_locator_seconds(
            result.tokens,
            result.timestamps,
            result.durations,
            speed_factor=factor,
        )
        start_frame, end_frame = locator_frames(start, end)
        return start_frame, end_frame, factor
    raise ValueError("split_alias_qbt_route_not_reproduced")


def evaluate(
    binding_path: Path, output_path: Path, batch_size: int, device: str
) -> dict[str, Any]:
    if batch_size <= 0 or device not in {"cpu", "cuda"}:
        raise ValueError("split_alias_qbt_schedule_invalid")
    binding, base_binding, base_report = _resolve_binding(binding_path, output_path)
    sherpa_site = str(Path(str(base_binding["stt"]["sherpaSitePackages"])))
    if sherpa_site not in sys.path:
        sys.path.append(sherpa_site)

    import evaluate_baxy_endpoint_lexical_raw_v1 as endpoint
    import evaluate_phoneme_teacher_category_oracle_v2 as oracle
    import run_lexical_wake_physical_room_gate_v1 as lexical
    import run_wakeword_physical_room_gate as room
    from audit_voxcpm2_gguf_pilot import configure_espeak_backend
    from baxy_mind import wake_cascade
    from ctc_wake_verifier import score_verifier_span
    from phoneme_student_vocabulary_v2 import (
        BLANK_ID,
        CONFUSABLE_IDS,
        TARGET_IDS,
        resolve_category_ids,
    )

    config = wake_cascade.load_wake_cascade_candidate_config(
        Path(str(base_binding["cascade"]["manifest"]))
    )
    recognizer, hotwords = lexical._recognizer(
        Path(str(base_binding["stt"]["root"])),
        config.direct_lexical_hotwords_score,
    )
    aliases = endpoint.endpoint_aliases(config)
    items = _selected_paths(base_binding, base_report, room)
    for index, item in enumerate(items, start=1):
        audio, rate = room._read_pcm16(Path(item["path"]))
        audio = room._resample(audio, rate, SAMPLE_RATE)
        start_frame, end_frame, factor = _decode_locator(
            audio,
            recognizer=recognizer,
            hotwords=hotwords,
            aliases=aliases,
            retry_speed_factors=config.direct_lexical_retry_speed_factors,
            phonetic_confusion_score_gte=config.direct_lexical_phonetic_confusion_score_gte,
            endpoint=endpoint,
            wake_cascade=wake_cascade,
        )
        item["locatorStartFrame"] = start_frame
        item["locatorEndFrame"] = end_frame
        item["recognitionSpeedFactor"] = factor
        print(f"LOCATOR|{index}/{len(items)}", flush=True)

    configure_espeak_backend()
    import numpy as np
    import torch
    import transformers
    from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor

    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("cuda_requested_but_unavailable")
    teacher_root = Path(str(base_binding["teacher"]["root"]))
    loaded = time.perf_counter()
    processor = Wav2Vec2Processor.from_pretrained(teacher_root, local_files_only=True)
    model = (
        Wav2Vec2ForCTC.from_pretrained(teacher_root, local_files_only=True)
        .eval()
        .to(device)
    )
    category_ids = resolve_category_ids(
        processor.tokenizer.get_vocab(), int(processor.tokenizer.pad_token_id)
    )
    load_seconds = time.perf_counter() - loaded
    inference_seconds = 0.0
    retained: list[dict[str, Any]] = []
    for start in range(0, len(items), batch_size):
        batch = items[start : start + batch_size]
        audios = []
        for item in batch:
            audio, rate = room._read_pcm16(Path(item["path"]))
            audios.append(room._resample(audio, rate, SAMPLE_RATE))
        prepared = processor(
            audios, sampling_rate=SAMPLE_RATE, return_tensors="pt", padding=True
        )
        input_lengths = torch.tensor(
            [len(audio) for audio in audios], dtype=torch.long, device=device
        )
        started = time.perf_counter()
        with torch.inference_mode():
            logits = model(input_values=prepared.input_values.to(device)).logits.float()
            probabilities = (
                oracle.compress_category_logits(torch, logits, category_ids)
                .cpu()
                .numpy()
            )
        if device == "cuda":
            torch.cuda.synchronize()
        inference_seconds += time.perf_counter() - started
        lengths = model._get_feat_extract_output_lengths(input_lengths).tolist()
        for item, probability, length in zip(
            batch, probabilities, lengths, strict=True
        ):
            values = probability[: int(length)]
            log_probabilities = np.log(np.maximum(values, 1e-12))
            locator_start = min(int(item["locatorStartFrame"]), len(values) - 1)
            locator_end = min(
                max(locator_start + 1, int(item["locatorEndFrame"])), len(values)
            )
            scored = score_verifier_span(
                log_probabilities,
                start_frame=locator_start,
                end_frame=locator_end,
                target_sequences=TARGET_IDS,
                confusable_sequences=CONFUSABLE_IDS,
                blank_id=BLANK_ID,
                context_before_frames=CONTEXT_FRAMES,
                context_after_frames=CONTEXT_FRAMES,
            )
            margin = float(scored["margin"])
            retained.append(
                {
                    "corpus": item["corpus"],
                    "label": item["label"],
                    "audioSha256": item["audioSha256"],
                    "locatorStartFrame": locator_start,
                    "locatorEndFrame": locator_end,
                    "recognitionSpeedFactor": item["recognitionSpeedFactor"],
                    "margin": margin,
                    "guardAccepted": qbt_accepts(margin),
                }
            )
        print(f"TEACHER|{min(start + batch_size, len(items))}/{len(items)}", flush=True)

    current = base_binding["currentEndpointConfusableCascade"]
    metrics = summarize(
        retained,
        current_confusable_positive_hashes=frozenset(
            current["splitPositiveAudioSha256"]
        ),
        current_confusable_negative_hashes=frozenset(
            current["splitNegativeAudioSha256"]
        ),
    )
    report = {
        "schema": SCHEMA,
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "scope": "opened_development_localized_split_alias_qbt",
        "bindingSha256": sha256(binding_path.resolve(strict=True)),
        "programSha256": sha256(Path(__file__).resolve()),
        "contract": binding["contract"],
        "metrics": metrics,
        "records": retained,
        "runtime": {
            "device": device,
            "batchSize": batch_size,
            "modelLoadSeconds": load_seconds,
            "inferenceSeconds": inference_seconds,
            "torch": torch.__version__,
            "transformers": transformers.__version__,
        },
        "candidateFrozen": False,
        "productOperatingPoint": False,
        "freshPhysicalHoldoutRequiredAfterCompleteCandidatePass": True,
        "promotionEligible": False,
        "filenamesRetained": False,
        "transcriptTextRetained": False,
        "physicalV17Read": False,
        "runtimeModified": False,
        "effectsExecuted": 0,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binding", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = evaluate(args.binding, args.output, args.batch_size, args.device)
    print(json.dumps(report["metrics"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
