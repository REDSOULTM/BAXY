"""Evaluate a frozen phoneme-CTC guard only on split lexical wake aliases.

The guard is deliberately narrower than a new wake classifier.  Existing
routes remain unchanged.  Only a ``bounded_split_phonetic_alias`` proposal is
allowed to survive when the frozen teacher independently emits an exact BAXY
category path with the already-published 0.5 target-vs-confusable margin.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
VOICE = ROOT / "experiments" / "voice_latency"
for entry in (ROOT / "src", ROOT / "scripts", VOICE):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))


SCHEMA = "baxy.split-alias-ctc-guard-development.v1"
BINDING_SCHEMA = "baxy.split-alias-ctc-guard-binding.v1"
SPLIT_METHOD = "bounded_split_phonetic_alias"
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


def split_records(report: dict[str, Any]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for label in ("positive", "negative"):
        group = report.get(label)
        if not isinstance(group, dict) or not isinstance(group.get("records"), list):
            raise ValueError("split_alias_source_report_invalid")
        for record in group["records"]:
            if not isinstance(record, dict):
                raise ValueError("split_alias_source_record_invalid")
            if record.get("method") == SPLIT_METHOD:
                selected.append({"label": label, **record})
    return selected


def guard_accepts(decision: object) -> bool:
    return bool(
        getattr(decision, "accepted", False)
        and getattr(decision, "method", None) == "ctc_exact"
        and getattr(decision, "margin", None) is not None
        and float(getattr(decision, "margin")) >= DECISION_MARGIN
    )


def summarize(
    records: Iterable[dict[str, Any]],
    *,
    current_confusable_positive_hashes: frozenset[str],
    current_confusable_negative_hashes: frozenset[str],
) -> dict[str, Any]:
    values = list(records)
    positive = [item for item in values if item["label"] == "positive"]
    negative = [item for item in values if item["label"] == "negative"]
    positive_accepted = sum(bool(item["guardAccepted"]) for item in positive)
    negative_false = sum(bool(item["guardAccepted"]) for item in negative)
    by_corpus: dict[str, Any] = {}
    for corpus in sorted({str(item["corpus"]) for item in values}):
        corpus_values = [item for item in values if item["corpus"] == corpus]
        corpus_positive = [
            item for item in corpus_values if item["label"] == "positive"
        ]
        corpus_negative = [
            item for item in corpus_values if item["label"] == "negative"
        ]
        by_corpus[corpus] = {
            "splitPositiveAccepted": sum(
                bool(item["guardAccepted"]) for item in corpus_positive
            ),
            "splitPositiveTotal": len(corpus_positive),
            "splitNegativeFalseActivations": sum(
                bool(item["guardAccepted"]) for item in corpus_negative
            ),
            "splitNegativeTotal": len(corpus_negative),
        }
    indexed = {str(item["audioSha256"]): item for item in values}
    expected_hashes = (
        current_confusable_positive_hashes | current_confusable_negative_hashes
    )
    if not expected_hashes.issubset(indexed):
        raise ValueError("split_alias_current_cascade_record_missing")
    current_positive_preserved = all(
        bool(indexed[value]["guardAccepted"])
        for value in current_confusable_positive_hashes
    )
    current_negative_remaining = sum(
        bool(indexed[value]["guardAccepted"])
        for value in current_confusable_negative_hashes
    )
    gate = bool(
        positive
        and positive_accepted == len(positive)
        and negative_false == 0
        and current_positive_preserved
        and current_negative_remaining == 0
    )
    return {
        "splitPositiveAccepted": positive_accepted,
        "splitPositiveTotal": len(positive),
        "splitNegativeFalseActivations": negative_false,
        "splitNegativeTotal": len(negative),
        "currentCascadeSplitPositivePreserved": current_positive_preserved,
        "currentCascadeSplitNegativeRemaining": current_negative_remaining,
        "byCorpus": by_corpus,
        "developmentGatePassed": gate,
    }


def _validate_file(path: Path, expected_hash: str, code: str) -> Path:
    resolved = path.resolve(strict=True)
    if sha256(resolved) != expected_hash:
        raise ValueError(code)
    return resolved


def _resolve_binding(
    binding_path: Path, output_path: Path
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    binding_path = binding_path.resolve(strict=True)
    binding = read_json(binding_path)
    if binding.get("schema") != BINDING_SCHEMA:
        raise ValueError("split_alias_binding_schema_invalid")
    if sha256(Path(__file__).resolve()) != binding.get("programSha256"):
        raise ValueError("split_alias_program_hash_mismatch")
    test = binding.get("test")
    if not isinstance(test, dict):
        raise ValueError("split_alias_test_binding_invalid")
    _validate_file(
        Path(str(test.get("path"))),
        str(test.get("sha256")),
        "split_alias_test_hash_mismatch",
    )
    planned = Path(str(binding.get("plannedOutput"))).resolve()
    if output_path.resolve() != planned:
        raise ValueError("split_alias_output_path_mismatch")
    if planned.exists():
        raise FileExistsError(f"split_alias_output_exists:{planned}")

    teacher = binding.get("teacher")
    cascade = binding.get("cascade")
    stt = binding.get("stt")
    if not all(isinstance(item, dict) for item in (teacher, cascade, stt)):
        raise ValueError("split_alias_asset_binding_invalid")
    teacher_root = Path(str(teacher["root"])).resolve(strict=True)
    _validate_file(
        teacher_root / "pytorch_model.bin",
        str(teacher["weightsSha256"]),
        "split_alias_teacher_weights_mismatch",
    )
    _validate_file(
        teacher_root / "config.json",
        str(teacher["configSha256"]),
        "split_alias_teacher_config_mismatch",
    )
    _validate_file(
        Path(str(cascade["manifest"])),
        str(cascade["manifestSha256"]),
        "split_alias_cascade_manifest_mismatch",
    )
    stt_root = Path(str(stt["root"])).resolve(strict=True)
    stt_hashes = stt.get("filesSha256")
    if not isinstance(stt_hashes, dict) or not stt_hashes:
        raise ValueError("split_alias_stt_hashes_missing")
    for name, expected in stt_hashes.items():
        _validate_file(
            stt_root / str(name),
            str(expected),
            f"split_alias_stt_hash_mismatch:{name}",
        )
    sherpa_site = Path(str(stt.get("sherpaSitePackages"))).resolve(strict=True)
    sherpa_hashes = stt.get("sherpaFilesSha256")
    if not isinstance(sherpa_hashes, dict) or not sherpa_hashes:
        raise ValueError("split_alias_sherpa_hashes_missing")
    for name, expected in sherpa_hashes.items():
        _validate_file(
            sherpa_site / str(name),
            str(expected),
            f"split_alias_sherpa_hash_mismatch:{name}",
        )

    corpora = binding.get("corpora")
    if not isinstance(corpora, list) or not corpora:
        raise ValueError("split_alias_corpora_missing")
    resolved_corpora: list[dict[str, Any]] = []
    for corpus in corpora:
        if not isinstance(corpus, dict):
            raise ValueError("split_alias_corpus_invalid")
        root = Path(str(corpus.get("root"))).resolve(strict=True)
        if "v17" in root.as_posix().casefold():
            raise ValueError("split_alias_physical_v17_forbidden")
        manifest = _validate_file(
            root / "manifest.v1.json",
            str(corpus.get("manifestSha256")),
            f"split_alias_corpus_manifest_mismatch:{corpus.get('name')}",
        )
        resolved = {**corpus, "root": root, "manifest": manifest}
        source_report = corpus.get("sourceReport")
        if source_report is not None:
            if not isinstance(source_report, dict):
                raise ValueError("split_alias_source_report_binding_invalid")
            resolved["sourceReportPath"] = _validate_file(
                Path(str(source_report.get("path"))),
                str(source_report.get("sha256")),
                f"split_alias_source_report_hash_mismatch:{corpus.get('name')}",
            )
        resolved_corpora.append(resolved)

    current = binding.get("currentEndpointConfusableCascade")
    if not isinstance(current, dict):
        raise ValueError("split_alias_current_cascade_binding_invalid")
    _validate_file(
        Path(str(current.get("path"))),
        str(current.get("sha256")),
        "split_alias_current_cascade_hash_mismatch",
    )
    contract = binding.get("contract")
    if not isinstance(contract, dict) or contract != {
        "route": SPLIT_METHOD,
        "teacherDecision": "ctc_exact_without_lexical_anchor",
        "decisionMarginGte": DECISION_MARGIN,
        "allOtherRoutesUnchanged": True,
        "positivePreservationRequired": True,
        "negativeFalseActivationsRequired": 0,
        "physicalV17Read": False,
        "runtimeModificationAllowed": False,
        "promotionEligible": False,
        "effectsExecuted": 0,
    }:
        raise ValueError("split_alias_contract_invalid")
    return binding, resolved_corpora


def _report_items(corpus: dict[str, Any], room: Any) -> list[dict[str, Any]]:
    report = read_json(Path(corpus["sourceReportPath"]))
    if report.get("schema") != "baxy.endpoint-lexical-raw-development.v1":
        raise ValueError("split_alias_source_report_schema_invalid")
    if report.get("corpusManifestSha256") != corpus["manifestSha256"]:
        raise ValueError("split_alias_source_report_corpus_mismatch")
    items: list[dict[str, Any]] = []
    grouped = {
        label: room._wav_paths(Path(corpus["root"]) / label, None)
        for label in ("positive", "negative")
    }
    for record in split_records(report):
        path = grouped[str(record["label"])][int(record["record"])]
        if room._sha256(path) != record.get("audioSha256"):
            raise ValueError("split_alias_source_audio_hash_mismatch")
        items.append(
            {
                "corpus": corpus["name"],
                "label": record["label"],
                "audioSha256": record["audioSha256"],
                "path": path,
                "discovery": "bound_source_report",
            }
        )
    return items


def _discover_positive_items(
    corpus: dict[str, Any],
    *,
    endpoint: Any,
    lexical: Any,
    room: Any,
    recognizer: Any,
    hotwords: str,
    aliases: frozenset[str],
    retry_speed_factors: tuple[float, ...],
    phonetic_confusion_score_gte: float,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    paths = room._wav_paths(Path(corpus["root"]) / "positive", None)
    expected = int(corpus["counts"]["positive"])
    if len(paths) != expected:
        raise ValueError(f"split_alias_positive_count_mismatch:{corpus['name']}")
    for index, path in enumerate(paths, start=1):
        audio, rate = room._read_pcm16(path)
        audio = room._resample(audio, rate, SAMPLE_RATE)
        match, _, _ = endpoint._decode_endpoint(
            audio,
            recognizer=recognizer,
            hotwords=hotwords,
            aliases=aliases,
            retry_speed_factors=retry_speed_factors,
            policy="bounded_development",
            verifier_score=0.0,
            phonetic_confusion_score_gte=phonetic_confusion_score_gte,
            endpoint_direct_score_gte=0.0,
        )
        if getattr(match, "method", None) == SPLIT_METHOD:
            items.append(
                {
                    "corpus": corpus["name"],
                    "label": "positive",
                    "audioSha256": room._sha256(path),
                    "path": path,
                    "discovery": "fresh_bounded_decode_without_transcript_retention",
                }
            )
        print(f"DISCOVER|{corpus['name']}|{index}/{len(paths)}", flush=True)
    return items


def evaluate(
    binding_path: Path, output_path: Path, batch_size: int, device: str
) -> dict[str, Any]:
    if batch_size <= 0 or device not in {"cpu", "cuda"}:
        raise ValueError("split_alias_schedule_invalid")
    binding, corpora = _resolve_binding(binding_path, output_path)
    sherpa_site = str(Path(str(binding["stt"]["sherpaSitePackages"])))
    if sherpa_site not in sys.path:
        sys.path.append(sherpa_site)

    import evaluate_baxy_endpoint_lexical_raw_v1 as endpoint
    import evaluate_phoneme_teacher_category_oracle_v2 as oracle
    import run_lexical_wake_physical_room_gate_v1 as lexical
    import run_wakeword_physical_room_gate as room
    from audit_voxcpm2_gguf_pilot import configure_espeak_backend
    from baxy_mind.wake_cascade import load_wake_cascade_candidate_config
    from baxy_mind.wake_verifier import (
        CATEGORY_NAMES,
        decide_category_probabilities,
        resolve_category_ids,
    )

    cascade = binding["cascade"]
    config = load_wake_cascade_candidate_config(Path(str(cascade["manifest"])))
    recognizer, hotwords = lexical._recognizer(
        Path(str(binding["stt"]["root"])), config.direct_lexical_hotwords_score
    )
    aliases = endpoint.endpoint_aliases(config)
    items: list[dict[str, Any]] = []
    for corpus in corpora:
        if corpus.get("sourceReport") is not None:
            items.extend(_report_items(corpus, room))
        else:
            items.extend(
                _discover_positive_items(
                    corpus,
                    endpoint=endpoint,
                    lexical=lexical,
                    room=room,
                    recognizer=recognizer,
                    hotwords=hotwords,
                    aliases=aliases,
                    retry_speed_factors=config.direct_lexical_retry_speed_factors,
                    phonetic_confusion_score_gte=(
                        config.direct_lexical_phonetic_confusion_score_gte
                    ),
                )
            )
    hashes = [str(item["audioSha256"]) for item in items]
    if not items or len(hashes) != len(set(hashes)):
        raise ValueError("split_alias_selected_items_invalid")

    configure_espeak_backend()
    import torch
    import transformers
    from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor

    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("cuda_requested_but_unavailable")
    teacher_root = Path(str(binding["teacher"]["root"]))
    load_started = time.perf_counter()
    processor = Wav2Vec2Processor.from_pretrained(teacher_root, local_files_only=True)
    model = (
        Wav2Vec2ForCTC.from_pretrained(teacher_root, local_files_only=True)
        .eval()
        .to(device)
    )
    category_ids = resolve_category_ids(
        processor.tokenizer.get_vocab(), int(processor.tokenizer.pad_token_id)
    )
    if tuple(oracle.CATEGORY_NAMES) != tuple(CATEGORY_NAMES):
        raise ValueError("split_alias_category_order_mismatch")
    load_seconds = time.perf_counter() - load_started
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
            decision = decide_category_probabilities(
                probability[: int(length)],
                "",
                decision_margin=DECISION_MARGIN,
                anchor_margin=DECISION_MARGIN,
            )
            retained.append(
                {
                    "corpus": item["corpus"],
                    "label": item["label"],
                    "audioSha256": item["audioSha256"],
                    "discovery": item["discovery"],
                    "guardAccepted": guard_accepts(decision),
                    "verifierMethod": decision.method,
                    "margin": decision.margin,
                }
            )
        print(f"TEACHER|{min(start + batch_size, len(items))}/{len(items)}", flush=True)

    current = binding["currentEndpointConfusableCascade"]
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
        "scope": "opened_development_localized_split_alias_guard",
        "bindingSha256": sha256(binding_path.resolve(strict=True)),
        "programSha256": sha256(Path(__file__).resolve()),
        "contract": binding["contract"],
        "counts": {
            "selectedSplitAliasRecords": len(retained),
            "methodCounts": dict(Counter(item["verifierMethod"] for item in retained)),
        },
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
