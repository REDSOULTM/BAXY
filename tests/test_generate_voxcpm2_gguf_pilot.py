from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path
import re
import wave

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "generate_voxcpm2_gguf_pilot.py"
)
SPEC = importlib.util.spec_from_file_location("generate_voxcpm2_gguf_pilot", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
VOICE_LATENCY_DIR = SCRIPT.parent


def _wav_bytes(*, sample_rate: int = 48_000, frames: int = 480) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(sample_rate)
        target.writeframes((1000).to_bytes(2, "little", signed=True) * frames)
    return output.getvalue()


def test_case_matrix_is_deterministic_and_unique() -> None:
    cases = MODULE.build_cases()

    assert len(cases) == len(MODULE.PERSONAS) * len(MODULE.SEEDS) == 32
    assert len({(case["persona_id"], case["seed"]) for case in cases}) == 32
    assert all(str(case["text"]).endswith("Baxy.") for case in cases)
    assert cases == MODULE.build_cases()
    assert all(case["phrase_id"] == "target" for case in cases)


def test_case_matrix_accepts_phonetic_target_text() -> None:
    cases = MODULE.build_cases("Back-see.")

    assert all(str(case["text"]).endswith("Back-see.") for case in cases)


def test_case_matrix_places_pronunciation_guidance_inside_persona() -> None:
    cases = MODULE.build_cases("Baxy.", "pronounce Baxy as back-see")

    assert all(
        str(case["text"]).endswith("; pronounce Baxy as back-see)Baxy.")
        for case in cases
    )


def test_case_matrix_rejects_empty_target_text() -> None:
    with pytest.raises(ValueError, match="target_text_empty"):
        MODULE.build_cases("   ")


def test_parse_seeds_rejects_duplicate() -> None:
    with pytest.raises(ValueError, match="seed_list_empty_or_duplicate"):
        MODULE.parse_seeds("11,29,11")


def test_validate_personas_rejects_duplicate_id() -> None:
    with pytest.raises(ValueError, match="duplicate_persona_id:same"):
        MODULE.validate_personas(
            [{"id": "same", "prompt": "one"}, {"id": "same", "prompt": "two"}]
        )


def test_case_matrix_crosses_personas_seeds_and_phrases() -> None:
    cases = MODULE.build_cases(
        personas=(("speaker", "Clear voice"),),
        seeds=(1, 2),
        phrases=(("maxi", "Maxi."), ("taxi", "Taxi.")),
    )

    assert len(cases) == 4
    assert [case["phrase_id"] for case in cases] == ["maxi", "taxi", "maxi", "taxi"]


def test_validate_phrases_rejects_duplicate_id() -> None:
    with pytest.raises(ValueError, match="duplicate_phrase_id:same"):
        MODULE.validate_phrases(
            [{"id": "same", "text": "Maxi"}, {"id": "same", "text": "Taxi"}]
        )


def test_inspect_wav_bytes_enforces_contract_and_signal() -> None:
    result = MODULE.inspect_wav_bytes(_wav_bytes())

    assert result["sample_rate"] == 48_000
    assert result["duration_seconds"] == pytest.approx(0.01)
    assert result["peak"] == pytest.approx(1000 / 32768)
    assert result["rms"] == pytest.approx(1000 / 32768)


def test_inspect_wav_bytes_rejects_wrong_sample_rate() -> None:
    with pytest.raises(ValueError, match="wav_contract_mismatch"):
        MODULE.inspect_wav_bytes(_wav_bytes(sample_rate=16_000))


def test_validate_sha256_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "artifact.bin"
    path.write_bytes(b"payload")

    with pytest.raises(ValueError, match="sha256_mismatch:model"):
        MODULE.validate_sha256(path, "0" * 64, "model")


def test_voxcpm2_negative_spec_matches_canonical_livekit_inventory() -> None:
    config_lines = (
        VOICE_LATENCY_DIR / "livekit_baxy_piper_scale.yaml"
    ).read_text(encoding="utf-8").splitlines()
    start = config_lines.index("custom_negative_phrases:") + 1
    end = config_lines.index("noise_scales: [0.98]")
    pattern = re.compile(r'^\s+-\s+"(.*)"\s*$')
    canonical = [
        match.group(1)
        for line in config_lines[start:end]
        if (match := pattern.fullmatch(line))
    ]
    spec = json.loads(
        (VOICE_LATENCY_DIR / "voxcpm2_baxy_hard_negatives.v1.json").read_text(
            encoding="utf-8"
        )
    )
    candidate = [record["text"].removesuffix(".") for record in spec["phrases"]]
    normalize = lambda value: value.strip().casefold()  # noqa: E731

    assert len(canonical) == len(candidate) == 69
    assert [normalize(value) for value in candidate] == [
        normalize(value) for value in canonical
    ]
    assert len({normalize(value) for value in candidate}) == 69


def test_context_positive_spec_is_short_multilingual_and_unique() -> None:
    path = VOICE_LATENCY_DIR / "voxcpm2_baxy_context_positives.v1.json"
    class_label, phrases = MODULE.load_phrase_spec(path, "unused")

    assert class_label == "positive"
    assert len(phrases) == 16
    assert len({phrase_id for phrase_id, _ in phrases}) == 16
    assert any("Бакси" in text for _, text in phrases)
    assert any("Baxi" in text for _, text in phrases)
    assert all(len(text.split()) <= 3 for _, text in phrases)


def test_generation_checkpoint_is_fingerprint_and_audio_bound(tmp_path: Path) -> None:
    output = tmp_path / "output"
    output.mkdir()
    wav_path = output / "clip_000000.wav"
    payload = _wav_bytes()
    wav_path.write_bytes(payload)
    case = {
        "persona_id": "speaker",
        "seed": 42,
        "phrase_id": "target",
        "phrase_text": "Baxy.",
    }
    record = {
        "index": 0,
        **case,
        "output_file": wav_path.name,
        "wav": {"sha256": MODULE.sha256(wav_path)},
    }
    checkpoint = output / "generation_checkpoint.v1.json"
    MODULE.write_generation_checkpoint(
        checkpoint, fingerprint="a" * 64, records=[record]
    )

    assert MODULE.load_generation_checkpoint(
        checkpoint,
        fingerprint="a" * 64,
        output_dir=output,
        cases=[case],
    ) == [record]
    with pytest.raises(
        ValueError, match="generation_checkpoint_fingerprint_mismatch"
    ):
        MODULE.load_generation_checkpoint(
            checkpoint,
            fingerprint="b" * 64,
            output_dir=output,
            cases=[case],
        )


def test_generation_without_checkpoint_refuses_existing_audio(tmp_path: Path) -> None:
    (tmp_path / "clip_000000.wav").write_bytes(_wav_bytes())

    with pytest.raises(ValueError, match="generation_wavs_exist_without_checkpoint"):
        MODULE.load_generation_checkpoint(
            tmp_path / "missing.json",
            fingerprint="a" * 64,
            output_dir=tmp_path,
            cases=[],
        )
