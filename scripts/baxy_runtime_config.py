"""Shared fail-closed resolution of BAXY's externally registered mind runtime."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_RUNTIME_MANIFEST = (
    Path(os.environ.get("LOCALAPPDATA", Path.cwd()))
    / "BAXYRuntime"
    / "mind-runtime-v1.json"
)
RUNTIME_CONFIGURATION_ERROR_CODE = "baxy_runtime_configuration_invalid"
RUNTIME_PROPERTIES = {
    "schema",
    "python",
    "python_sha256",
    "python_path",
    "gguf",
    "gguf_sha256",
    "llama_server",
    "llama_server_sha256",
    "stt_dir",
    "stt_sha256",
    "wake_manifest",
    "wake_manifest_sha256",
    "ngl",
    "wake_on_start",
}
OPTIONAL_TTS_PROPERTIES = {"tts_model", "tts_sha256"}
OPTIONAL_WAKE_PROPERTIES = {"wake_manifest", "wake_manifest_sha256"}
STT_FILES = (
    "encoder.int8.onnx",
    "decoder.int8.onnx",
    "joiner.int8.onnx",
    "tokens.txt",
)


@dataclass(frozen=True)
class RuntimeConfig:
    python: Path
    python_path: Path
    gguf: Path
    llama_server: Path
    gpu_layers: int
    source: str
    manifest_sha256: str


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def stt_sha256(path: Path) -> str:
    fingerprint = "".join(f"{name}:{file_sha256(path / name)}\n" for name in STT_FILES)
    return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()


def stt_file_sha256s(path: Path) -> dict[str, str]:
    """Return the current manifest-v1 per-file STT identity."""

    return {name: file_sha256(path / name) for name in STT_FILES}


def _stt_identity_matches(path: Path, expected: object) -> bool:
    """Accept the original aggregate or the current closed per-file identity."""

    if _sha256_text(expected):
        return stt_sha256(path) == expected
    if not isinstance(expected, dict) or set(expected) != set(STT_FILES):
        return False
    observed = stt_file_sha256s(path)
    return all(
        _sha256_text(expected[name]) and observed[name] == expected[name]
        for name in STT_FILES
    )


def _sha256_text(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _read_json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("el manifiesto del runtime debe ser un objeto JSON")
    return value


def _required_file(path: Path, label: str) -> Path:
    try:
        resolved = path.resolve(strict=True)
    except (FileNotFoundError, OSError) as error:
        raise FileNotFoundError(f"falta el componente registrado: {label}") from error
    if not resolved.is_file():
        raise FileNotFoundError(f"el componente registrado no es archivo: {label}")
    return resolved


def _required_directory(path: Path, label: str) -> Path:
    try:
        resolved = path.resolve(strict=True)
    except (FileNotFoundError, OSError) as error:
        raise FileNotFoundError(f"falta el componente registrado: {label}") from error
    if not resolved.is_dir():
        raise FileNotFoundError(f"el componente registrado no es directorio: {label}")
    return resolved


def resolve_runtime(
    *,
    manifest_path: Path,
    python: Path | None = None,
    python_path: Path | None = None,
    gguf: Path | None = None,
    llama_server: Path | None = None,
    gpu_layers: int | None = None,
) -> RuntimeConfig:
    """Resolve a registered runtime, with an all-explicit portable fallback."""

    explicit = {
        "python": python,
        "python_path": python_path,
        "gguf": gguf,
        "llama_server": llama_server,
    }
    all_explicit = all(value is not None for value in explicit.values())
    manifest: dict[str, Any] = {}
    manifest_sha256 = ""
    if not all_explicit:
        if not manifest_path.is_file():
            raise FileNotFoundError(
                "no existe el runtime registrado; proporciona los cuatro componentes explícitos"
            )
        manifest = _read_json_object(manifest_path)
        manifest_properties = set(manifest)
        base_property_sets = (
            RUNTIME_PROPERTIES,
            RUNTIME_PROPERTIES - OPTIONAL_WAKE_PROPERTIES,
        )
        valid_properties = {
            frozenset(properties | optional)
            for properties in base_property_sets
            for optional in (set(), OPTIONAL_TTS_PROPERTIES)
        }
        if (
            manifest.get("schema") != "baxy-mind-runtime-v1"
            or manifest_properties not in valid_properties
        ):
            raise ValueError("schema de runtime registrado no compatible")
        manifest_sha256 = file_sha256(manifest_path)

    values: dict[str, Path] = {}
    for name, override in explicit.items():
        raw = override if override is not None else manifest.get(name)
        if raw is None or not str(raw).strip():
            raise ValueError(f"falta el componente de runtime: {name}")
        values[name] = Path(str(raw))

    python_full = _required_file(values["python"], "python")
    python_path_full = _required_directory(values["python_path"], "python_path")
    gguf_full = _required_file(values["gguf"], "gguf")
    server_full = _required_file(values["llama_server"], "llama_server")
    if python_full.name.casefold() != "python.exe":
        raise ValueError("el runtime Python debe terminar en python.exe")
    if not (python_path_full / "baxy_mind" / "__main__.py").is_file():
        raise ValueError("python_path no contiene baxy_mind")
    if gguf_full.suffix.casefold() != ".gguf":
        raise ValueError("el modelo registrado no es GGUF")
    if server_full.name.casefold() != "llama-server.exe":
        raise ValueError("el servidor registrado no es llama-server.exe")
    if not all_explicit:
        for name, path in (
            ("python", python_full),
            ("gguf", gguf_full),
            ("llama_server", server_full),
        ):
            expected = manifest.get(f"{name}_sha256")
            if not _sha256_text(expected) or file_sha256(path) != expected:
                raise ValueError(f"hash SHA-256 no coincide: {name}")
        if "tts_model" in manifest:
            tts = _required_file(Path(str(manifest["tts_model"])), "tts_model")
            expected_tts = manifest.get("tts_sha256")
            if not _sha256_text(expected_tts) or file_sha256(tts) != expected_tts:
                raise ValueError("hash SHA-256 no coincide: tts_model")
        stt = _required_directory(Path(str(manifest.get("stt_dir") or "")), "stt_dir")
        expected_stt = manifest.get("stt_sha256")
        if any(
            not (stt / name).is_file() for name in STT_FILES
        ) or not _stt_identity_matches(stt, expected_stt):
            raise ValueError("hash SHA-256 no coincide: stt_dir")
        wake_on_start = manifest.get("wake_on_start")
        if not isinstance(wake_on_start, bool):
            raise ValueError("wake_on_start inválido")
        if wake_on_start:
            wake = _required_file(
                Path(str(manifest.get("wake_manifest") or "")),
                "wake_manifest",
            )
            expected_wake = manifest.get("wake_manifest_sha256")
            if not _sha256_text(expected_wake) or file_sha256(wake) != expected_wake:
                raise ValueError("hash SHA-256 no coincide: wake_manifest")
        elif (
            manifest.get("wake_manifest") is not None
            or manifest.get("wake_manifest_sha256") is not None
        ):
            raise ValueError("wake desactivado conserva activos declarados")

    layers = gpu_layers
    if layers is None:
        layers = int(manifest.get("ngl") or 99)
    if not 0 <= layers <= 999:
        raise ValueError("gpu_layers debe estar entre 0 y 999")
    override_count = sum(value is not None for value in explicit.values())
    source = (
        "explicit_components"
        if all_explicit
        else "registered_manifest_with_overrides"
        if override_count
        else "registered_manifest"
    )
    return RuntimeConfig(
        python=python_full,
        python_path=python_path_full,
        gguf=gguf_full,
        llama_server=server_full,
        gpu_layers=layers,
        source=source,
        manifest_sha256=manifest_sha256,
    )


def add_runtime_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--runtime-manifest",
        type=Path,
        default=DEFAULT_RUNTIME_MANIFEST,
    )
    parser.add_argument("--python", type=Path)
    parser.add_argument("--python-path", type=Path)
    parser.add_argument("--gguf", type=Path)
    parser.add_argument("--llama-server", type=Path)
    parser.add_argument("--gpu-layers", type=int)


def resolve_runtime_from_args(args: argparse.Namespace) -> RuntimeConfig:
    return resolve_runtime(
        manifest_path=args.runtime_manifest,
        python=args.python,
        python_path=args.python_path,
        gguf=args.gguf,
        llama_server=args.llama_server,
        gpu_layers=args.gpu_layers,
    )


def resolve_runtime_from_args_or_error(
    parser: argparse.ArgumentParser,
    args: argparse.Namespace,
) -> RuntimeConfig:
    """Resolve a runtime or stop argparse with a stable, traceback-free code."""

    try:
        return resolve_runtime_from_args(args)
    except (OSError, TypeError, ValueError) as error:
        parser.error(f"{RUNTIME_CONFIGURATION_ERROR_CODE}: {error}")


def public_runtime_identity(runtime: RuntimeConfig) -> dict[str, Any]:
    """Attest selected components without disclosing their local directories."""

    return {
        "source": runtime.source,
        "manifest_sha256": runtime.manifest_sha256,
        "python": {
            "name": runtime.python.name,
            "bytes": runtime.python.stat().st_size,
        },
        "mind": {"module": "baxy_mind"},
        "gguf": {
            "name": runtime.gguf.name,
            "bytes": runtime.gguf.stat().st_size,
        },
        "llama_server": {
            "name": runtime.llama_server.name,
            "bytes": runtime.llama_server.stat().st_size,
        },
        "profiles": {
            "gpu_layers": runtime.gpu_layers,
            "cpu_fallback_layers": 0,
        },
    }
