"""Generate a small, hash-bound VoxCPM2 GGUF wake-word quality pilot.

This is research-only.  It starts the pinned local llama.cpp-omni TTS server,
keeps the model resident while crossing personas and seeds, validates every
returned WAV, writes an attested manifest, and stops only the process it owns.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
import math
import os
from pathlib import Path
import socket
import subprocess
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import wave


MODEL_REPOSITORY = "DennisHuang648/VoxCPM2-GGUF"
MODEL_REVISION = "169f64d8b98bbaab1761e4ca3a83e6af653456cc"
RUNTIME_REPOSITORY = "https://github.com/tc-mb/llama.cpp-omni"
RUNTIME_COMMIT = "6e9ae1a06be74e1e05ada646d106fe174b4498ef"
EXPECTED_SAMPLE_RATE = 48_000
PERSONAS = (
    (
        "neutral_adult",
        "A clear adult voice, neutral accent, careful pronunciation",
    ),
    (
        "young_woman",
        "A young adult woman, clear mid-pitch voice, calm and articulate",
    ),
    (
        "young_man",
        "A young adult man, warm baritone, steady and articulate",
    ),
    (
        "older_woman",
        "An older adult woman, soft gentle voice, slow and clear",
    ),
    (
        "older_man",
        "An older adult man, deep resonant voice, deliberate and clear",
    ),
    (
        "british_woman",
        "A British English woman, clear RP-like delivery, moderate pace",
    ),
    (
        "spanish_woman",
        "Una mujer adulta, voz clara, acento español neutro y dicción cuidadosa",
    ),
    (
        "spanish_man",
        "Un hombre adulto, voz clara, acento latino neutro y dicción cuidadosa",
    ),
)
SEEDS = (11, 29, 42, 73)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_sha256(path: Path, expected: str, label: str) -> str:
    actual = sha256(path)
    if actual.casefold() != expected.casefold():
        raise ValueError(f"sha256_mismatch:{label}:expected={expected}:actual={actual}")
    return actual


def validate_personas(raw: object) -> tuple[tuple[str, str], ...]:
    if not isinstance(raw, list) or not raw:
        raise ValueError("personas_missing")
    personas: list[tuple[str, str]] = []
    seen: set[str] = set()
    for record in raw:
        if not isinstance(record, dict):
            raise ValueError("persona_record_is_not_object")
        persona_id = str(record.get("id", "")).strip()
        prompt = str(record.get("prompt", "")).strip()
        if not persona_id or not prompt:
            raise ValueError("persona_id_or_prompt_empty")
        if persona_id in seen:
            raise ValueError(f"duplicate_persona_id:{persona_id}")
        seen.add(persona_id)
        personas.append((persona_id, prompt))
    return tuple(personas)


def load_personas(path: Path | None) -> tuple[tuple[str, str], ...]:
    if path is None:
        return PERSONAS
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict) or value.get("schema") != "baxy.voxcpm2-voice-personas.v1":
        raise ValueError("unsupported_persona_spec_schema")
    return validate_personas(value.get("personas"))


def parse_seeds(value: str) -> tuple[int, ...]:
    try:
        seeds = tuple(int(part.strip()) for part in value.split(",") if part.strip())
    except ValueError as error:
        raise ValueError("seed_list_invalid") from error
    if not seeds or len(set(seeds)) != len(seeds):
        raise ValueError("seed_list_empty_or_duplicate")
    if any(seed < 0 or seed > 2**32 - 1 for seed in seeds):
        raise ValueError("seed_out_of_range")
    return seeds


def validate_phrases(raw: object) -> tuple[tuple[str, str], ...]:
    if not isinstance(raw, list) or not raw:
        raise ValueError("phrases_missing")
    phrases: list[tuple[str, str]] = []
    seen: set[str] = set()
    for record in raw:
        if not isinstance(record, dict):
            raise ValueError("phrase_record_is_not_object")
        phrase_id = str(record.get("id", "")).strip()
        text = str(record.get("text", "")).strip()
        if not phrase_id or not text:
            raise ValueError("phrase_id_or_text_empty")
        if phrase_id in seen:
            raise ValueError(f"duplicate_phrase_id:{phrase_id}")
        seen.add(phrase_id)
        phrases.append((phrase_id, text))
    return tuple(phrases)


def load_phrase_spec(path: Path | None, target_text: str) -> tuple[str, tuple[tuple[str, str], ...]]:
    if path is None:
        return "positive", (("target", target_text),)
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict) or value.get("schema") != "baxy.voxcpm2-phrase-set.v1":
        raise ValueError("unsupported_phrase_spec_schema")
    class_label = str(value.get("class_label", "")).strip()
    if class_label not in {"positive", "adversarial_negative"}:
        raise ValueError("phrase_spec_class_label_invalid")
    return class_label, validate_phrases(value.get("phrases"))


def generation_fingerprint(identity: dict[str, object]) -> str:
    payload = json.dumps(
        identity, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load_generation_checkpoint(
    path: Path,
    *,
    fingerprint: str,
    output_dir: Path,
    cases: list[dict[str, object]],
) -> list[dict[str, object]]:
    if not path.exists():
        if any(output_dir.glob("clip_*.wav")):
            raise ValueError("generation_wavs_exist_without_checkpoint")
        return []
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict) or value.get("schema") != "baxy.voxcpm2-generation-checkpoint.v1":
        raise ValueError("unsupported_generation_checkpoint_schema")
    if value.get("generation_fingerprint") != fingerprint:
        raise ValueError("generation_checkpoint_fingerprint_mismatch")
    records = value.get("records")
    if not isinstance(records, list) or len(records) > len(cases):
        raise ValueError("generation_checkpoint_records_invalid")
    typed = [record for record in records if isinstance(record, dict)]
    if len(typed) != len(records):
        raise ValueError("generation_checkpoint_record_is_not_object")
    for index, (record, case) in enumerate(zip(typed, cases, strict=False)):
        if (
            record.get("index") != index
            or record.get("persona_id") != case.get("persona_id")
            or record.get("seed") != case.get("seed")
            or record.get("phrase_id") != case.get("phrase_id")
            or record.get("phrase_text") != case.get("phrase_text")
        ):
            raise ValueError(f"generation_checkpoint_record_mismatch:{index}")
        wav_path = output_dir / str(record.get("output_file", ""))
        if not wav_path.is_file() or sha256(wav_path) != record.get("wav", {}).get(
            "sha256"
        ):
            raise ValueError(f"generation_checkpoint_wav_mismatch:{index}")
    allowed_names = {f"clip_{index:06d}.wav" for index in range(len(cases))}
    unexpected = {
        wav_path.name
        for wav_path in output_dir.glob("clip_*.wav")
        if wav_path.name not in allowed_names
    }
    if unexpected:
        raise ValueError("generation_checkpoint_unexpected_wav_names")
    return typed


def write_generation_checkpoint(
    path: Path,
    *,
    fingerprint: str,
    records: list[dict[str, object]],
) -> None:
    value = {
        "schema": "baxy.voxcpm2-generation-checkpoint.v1",
        "generation_fingerprint": fingerprint,
        "records": records,
        "blind_human_partition_accessed": False,
    }
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def build_cases(
    target_text: str = "Baxy.",
    persona_suffix: str = "",
    personas: tuple[tuple[str, str], ...] = PERSONAS,
    seeds: tuple[int, ...] = SEEDS,
    phrases: tuple[tuple[str, str], ...] | None = None,
) -> list[dict[str, object]]:
    if not target_text.strip():
        raise ValueError("target_text_empty")
    if phrases is None:
        phrases = (("target", target_text),)
    cases: list[dict[str, object]] = []
    for persona_id, persona in personas:
        guided_persona = persona
        if persona_suffix.strip():
            guided_persona = f"{persona}; {persona_suffix.strip()}"
        for seed in seeds:
            for phrase_id, phrase_text in phrases:
                cases.append(
                    {
                        "persona_id": persona_id,
                        "persona": guided_persona,
                        "seed": seed,
                        "phrase_id": phrase_id,
                        "phrase_text": phrase_text,
                        "text": f"({guided_persona}){phrase_text}",
                    }
                )
    return cases


def inspect_wav_bytes(payload: bytes) -> dict[str, object]:
    with wave.open(io.BytesIO(payload), "rb") as source:
        channels = source.getnchannels()
        sample_width = source.getsampwidth()
        sample_rate = source.getframerate()
        frames = source.getnframes()
        pcm = source.readframes(frames)
    if (channels, sample_width, sample_rate) != (1, 2, EXPECTED_SAMPLE_RATE):
        raise ValueError(
            "wav_contract_mismatch:"
            f"channels={channels}:sample_width={sample_width}:sample_rate={sample_rate}"
        )
    if frames <= 0 or len(pcm) != frames * sample_width:
        raise ValueError("wav_payload_empty_or_truncated")
    sum_squares = 0
    peak = 0
    for index in range(0, len(pcm), 2):
        value = int.from_bytes(pcm[index : index + 2], "little", signed=True)
        peak = max(peak, abs(value))
        sum_squares += value * value
    return {
        "channels": channels,
        "sample_width_bytes": sample_width,
        "sample_rate": sample_rate,
        "frames": frames,
        "duration_seconds": frames / sample_rate,
        "peak": peak / 32768.0,
        "rms": math.sqrt(sum_squares / frames) / 32768.0,
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def assert_port_free(host: str, port: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.25)
        if probe.connect_ex((host, port)) == 0:
            raise RuntimeError(f"pilot_port_already_in_use:{host}:{port}")


def request_bytes(
    url: str,
    *,
    method: str = "GET",
    body: dict[str, object] | None = None,
    timeout_seconds: float = 120.0,
) -> tuple[bytes, str]:
    payload = None
    headers = {}
    if body is not None:
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url, data=payload, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            return response.read(), response.headers.get_content_type()
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"http_error:{error.code}:{detail}") from error


def wait_until_ready(base_url: str, process: subprocess.Popen[bytes], timeout: float) -> float:
    started = time.perf_counter()
    last_error = "not_attempted"
    while time.perf_counter() - started < timeout:
        if process.poll() is not None:
            raise RuntimeError(f"tts_server_exited_before_ready:{process.returncode}")
        try:
            payload, content_type = request_bytes(
                f"{base_url}/health", timeout_seconds=1.0
            )
            health = json.loads(payload)
            if content_type == "application/json" and health == {
                "engine": "voxcpm2",
                "status": "ok",
            }:
                return time.perf_counter() - started
            last_error = f"unexpected_health:{content_type}:{health}"
        except (OSError, URLError, RuntimeError, json.JSONDecodeError) as error:
            last_error = repr(error)
        time.sleep(0.1)
    raise TimeoutError(f"tts_server_ready_timeout:{last_error}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server-exe", type=Path, required=True)
    parser.add_argument("--server-sha256", required=True)
    parser.add_argument("--base-lm", type=Path, required=True)
    parser.add_argument("--base-lm-sha256", required=True)
    parser.add_argument("--acoustic", type=Path, required=True)
    parser.add_argument("--acoustic-sha256", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18082)
    parser.add_argument("--cfg-value", type=float, default=2.0)
    parser.add_argument("--timesteps", type=int, default=8)
    parser.add_argument("--temperature", type=float, default=1.0)
    parser.add_argument("--target-text", default="Baxy.")
    parser.add_argument("--persona-suffix", default="")
    parser.add_argument("--persona-spec", type=Path)
    parser.add_argument("--seeds", default=",".join(str(seed) for seed in SEEDS))
    parser.add_argument("--phrase-spec", type=Path)
    parser.add_argument("--ready-timeout", type=float, default=60.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    server_exe = args.server_exe.resolve()
    base_lm = args.base_lm.resolve()
    acoustic = args.acoustic.resolve()
    for path in (server_exe, base_lm, acoustic):
        if not path.is_file():
            raise FileNotFoundError(path)
    hashes = {
        "server": validate_sha256(server_exe, args.server_sha256, "server"),
        "base_lm": validate_sha256(base_lm, args.base_lm_sha256, "base_lm"),
        "acoustic": validate_sha256(acoustic, args.acoustic_sha256, "acoustic"),
    }
    if not 0 < args.port < 65536:
        raise ValueError("port_out_of_range")
    if args.timesteps <= 0 or not 0.0 < args.cfg_value <= 10.0:
        raise ValueError("generation_parameters_out_of_range")

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    assert_port_free(args.host, args.port)
    stdout_path = output_dir / "server.stdout.log"
    stderr_path = output_dir / "server.stderr.log"
    creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    command = [
        str(server_exe),
        "--voxcpm2-base-lm",
        str(base_lm),
        "--voxcpm2-acoustic",
        str(acoustic),
        "--voxcpm2-n-gpu-layers",
        "-1",
        "--host",
        args.host,
        "--port",
        str(args.port),
    ]
    persona_spec = args.persona_spec.resolve() if args.persona_spec else None
    phrase_spec = args.phrase_spec.resolve() if args.phrase_spec else None
    personas = load_personas(persona_spec)
    seeds = parse_seeds(args.seeds)
    class_label, phrases = load_phrase_spec(phrase_spec, args.target_text)
    cases = build_cases(
        args.target_text, args.persona_suffix, personas, seeds, phrases
    )
    identity = {
        "runtime_commit": RUNTIME_COMMIT,
        "model_revision": MODEL_REVISION,
        "hashes": hashes,
        "cfg_value": args.cfg_value,
        "timesteps": args.timesteps,
        "temperature": args.temperature,
        "target_text": args.target_text,
        "persona_suffix": args.persona_suffix,
        "class_label": class_label,
        "cases": cases,
    }
    fingerprint = generation_fingerprint(identity)
    checkpoint_path = output_dir / "generation_checkpoint.v1.json"
    records = load_generation_checkpoint(
        checkpoint_path,
        fingerprint=fingerprint,
        output_dir=output_dir,
        cases=cases,
    )
    resumed_record_count = len(records)
    server_started_at = datetime.now(timezone.utc).isoformat()
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        process = subprocess.Popen(
            command,
            cwd=server_exe.parent,
            stdout=stdout,
            stderr=stderr,
            creationflags=creation_flags,
        )
        try:
            base_url = f"http://{args.host}:{args.port}"
            ready_seconds = wait_until_ready(
                base_url, process, timeout=args.ready_timeout
            )
            for index, case in enumerate(cases):
                if index < resumed_record_count:
                    continue
                request = {
                    "model": "voxcpm2",
                    "input": case["text"],
                    "voice": "default",
                    "response_format": "wav",
                    "seed": case["seed"],
                    "cfg_value": args.cfg_value,
                    "inference_timesteps": args.timesteps,
                    "max_steps": 200,
                    "temperature": args.temperature,
                }
                started = time.perf_counter()
                payload, content_type = request_bytes(
                    f"{base_url}/v1/audio/speech",
                    method="POST",
                    body=request,
                    timeout_seconds=180.0,
                )
                elapsed = time.perf_counter() - started
                if content_type != "audio/wav":
                    raise ValueError(
                        f"unexpected_synthesis_content_type:{content_type}"
                    )
                wav = inspect_wav_bytes(payload)
                path = output_dir / f"clip_{index:06d}.wav"
                temporary = path.with_suffix(".wav.partial")
                temporary.write_bytes(payload)
                os.replace(temporary, path)
                records.append(
                    {
                        "index": index,
                        **case,
                        "output_file": path.name,
                        "request": request,
                        "elapsed_seconds": elapsed,
                        "wav": wav,
                    }
                )
                if len(records) % 16 == 0 or len(records) == len(cases):
                    write_generation_checkpoint(
                        checkpoint_path,
                        fingerprint=fingerprint,
                        records=records,
                    )
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10.0)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10.0)

    manifest = {
        "schema": "baxy.voxcpm2-gguf-wake-pilot-corpus.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": f"development_only_synthetic_{class_label}_pronunciation_pilot",
        "server_started_at_utc": server_started_at,
        "server_ready_seconds": ready_seconds,
        "generation_fingerprint": fingerprint,
        "checkpoint_resumed_record_count": resumed_record_count,
        "runtime": {
            "repository": RUNTIME_REPOSITORY,
            "commit": RUNTIME_COMMIT,
            "server_exe": server_exe.as_posix(),
            "server_sha256": hashes["server"],
        },
        "model": {
            "repository": MODEL_REPOSITORY,
            "revision": MODEL_REVISION,
            "base_lm": base_lm.as_posix(),
            "base_lm_sha256": hashes["base_lm"],
            "acoustic": acoustic.as_posix(),
            "acoustic_sha256": hashes["acoustic"],
        },
        "generation": {
            "target_display_text": args.target_text,
            "persona_suffix": args.persona_suffix,
            "class_label": class_label,
            "phrase_count": len(phrases),
            "phrase_spec": phrase_spec.as_posix() if phrase_spec else None,
            "phrase_spec_sha256": sha256(phrase_spec) if phrase_spec else None,
            "persona_count": len(personas),
            "persona_spec": persona_spec.as_posix() if persona_spec else None,
            "persona_spec_sha256": sha256(persona_spec) if persona_spec else None,
            "seeds": list(seeds),
            "cfg_value": args.cfg_value,
            "inference_timesteps": args.timesteps,
            "temperature": args.temperature,
        },
        "records": records,
        "blind_human_partition_accessed": False,
        "candidate_model_training_started": False,
        "effects_executed": 0,
    }
    manifest_path = output_dir / "manifest.v1.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    checkpoint_path.unlink(missing_ok=True)
    print(
        json.dumps(
            {
                "manifest": manifest_path.as_posix(),
                "class_label": class_label,
                "record_count": len(records),
                "checkpoint_resumed_record_count": resumed_record_count,
                "blind_human_partition_accessed": False,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
