#!/usr/bin/env python3
"""Build and measure comparable distribution variants for tournament round A."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import harness


ROOT = harness.ROOT
EXPERIMENT = harness.EXPERIMENT
ARTIFACTS = harness.ARTIFACTS
BUILD_ROOT = ARTIFACTS / "build" / "packaging"
RAW_PATH = ARTIFACTS / "raw" / "packaging_results.json"
PYTHON_DIR = EXPERIMENT / "python_core"
PYTHON_SOURCE = PYTHON_DIR / "baxy_slice.py"
PYTHON_PACKAGER = PYTHON_DIR / ".venv" / "Scripts" / "python.exe"
DOTNET_DIR = EXPERIMENT / "dotnet_windows_core"
DOTNET_PROJECT = DOTNET_DIR / "BaxySlice.csproj"
RUST_DIR = EXPERIMENT / "rust_core"
CARGO = Path.home() / ".cargo" / "bin" / "cargo.exe"
EMBED_URL = "https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip"
EMBED_OFFICIAL_MD5 = "fe8ef205f2e9c3ba44d0cf9954e1abd3"


@dataclass
class BuiltVariant:
    variant_id: str
    family: str
    command: tuple[str, ...]
    cwd: Path
    artifact_root: Path
    runtime_external: bool
    source_files: tuple[Path, ...]
    build: dict[str, Any]


def run_build(command: list[str], cwd: Path, environment: dict[str, str] | None = None) -> dict[str, Any]:
    started = time.perf_counter_ns()
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=300,
        check=False,
    )
    return {
        "command": command,
        "cwd": cwd.relative_to(ROOT).as_posix(),
        "elapsed_ns": time.perf_counter_ns() - started,
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def tree_manifest(root: Path) -> dict[str, Any]:
    paths = [root] if root.is_file() else sorted(path for path in root.rglob("*") if path.is_file())
    files = []
    for path in paths:
        files.append(
            {
                "path": path.name if root.is_file() else path.relative_to(root).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": harness.sha256_file(path),
            }
        )
    return {
        "root": root.relative_to(ROOT).as_posix(),
        "files": files,
        "file_count": len(files),
        "bytes": sum(item["bytes"] for item in files),
    }


def finalize_build(variant: BuiltVariant) -> BuiltVariant:
    variant.build["artifact"] = tree_manifest(variant.artifact_root)
    variant.build["runtime_external"] = variant.runtime_external
    variant.build["source_tree_sha256"] = harness.sha256_tree(variant.source_files)
    variant.build["source_lines"] = sum(
        len(path.read_text(encoding="utf-8").splitlines()) for path in variant.source_files
    )
    return variant


def build_pyinstaller(mode: str) -> BuiltVariant:
    variant_id = f"python_pyinstaller_{mode}"
    output = BUILD_ROOT / variant_id
    dist = output / "dist"
    work = output / "work"
    spec = output / "spec"
    output.mkdir(parents=True, exist_ok=True)
    name = f"baxy-python-{mode}"
    command = [
        str(PYTHON_PACKAGER),
        "-m",
        "PyInstaller",
        "--clean",
        "--noconfirm",
        "--log-level",
        "WARN",
        f"--{mode}",
        "--name",
        name,
        "--distpath",
        str(dist),
        "--workpath",
        str(work),
        "--specpath",
        str(spec),
        str(PYTHON_SOURCE),
    ]
    build = run_build(command, PYTHON_DIR)
    artifact = dist / (name if mode == "onedir" else f"{name}.exe")
    executable = artifact / f"{name}.exe" if mode == "onedir" else artifact
    return finalize_build(
        BuiltVariant(
            variant_id,
            "Python",
            (str(executable), "--server"),
            executable.parent,
            artifact,
            False,
            (PYTHON_SOURCE, PYTHON_DIR / "packaging-requirements.txt"),
            build,
        )
    )


def build_embedded_python() -> BuiltVariant:
    variant_id = "python_embedded_runtime"
    output = BUILD_ROOT / variant_id
    bundle = output / "bundle"
    bundle.mkdir(parents=True, exist_ok=True)
    archive = output / "python-3.12.10-embed-amd64.zip"
    started = time.perf_counter_ns()
    error = ""
    try:
        urllib.request.urlretrieve(EMBED_URL, archive)
        import hashlib

        md5 = hashlib.md5(archive.read_bytes(), usedforsecurity=False).hexdigest()
        if md5 != EMBED_OFFICIAL_MD5:
            raise RuntimeError(f"official MD5 mismatch: {md5}")
        with zipfile.ZipFile(archive) as package:
            package.extractall(bundle)
        shutil.copy2(PYTHON_SOURCE, bundle / "baxy_slice.py")
        exit_code = 0
    except Exception as exception:
        exit_code = 1
        error = f"{type(exception).__name__}: {exception}"
    build = {
        "command": ["download-and-extract", EMBED_URL],
        "cwd": ROOT.as_posix(),
        "elapsed_ns": time.perf_counter_ns() - started,
        "exit_code": exit_code,
        "stdout": "",
        "stderr": error,
        "download": {
            "url": EMBED_URL,
            "official_md5": EMBED_OFFICIAL_MD5,
            "observed_sha256": harness.sha256_file(archive) if archive.is_file() else None,
        },
    }
    return finalize_build(
        BuiltVariant(
            variant_id,
            "Python",
            (str(bundle / "python.exe"), str(bundle / "baxy_slice.py"), "--server"),
            bundle,
            bundle,
            False,
            (PYTHON_SOURCE,),
            build,
        )
    )


def build_dotnet(variant_id: str, publish_arguments: list[str], runtime_external: bool) -> BuiltVariant:
    output = BUILD_ROOT / variant_id
    output.mkdir(parents=True, exist_ok=True)
    command = [
        "dotnet",
        "publish",
        str(DOTNET_PROJECT),
        "-c",
        "Release",
        "-r",
        "win-x64",
        *publish_arguments,
        "-p:DebugType=None",
        "-p:DebugSymbols=false",
        "-o",
        str(output),
        "--nologo",
    ]
    build = run_build(command, ROOT)
    executable = output / "baxy-dotnet-slice.exe"
    return finalize_build(
        BuiltVariant(
            variant_id,
            ".NET/Windows",
            (str(executable), "--server"),
            output,
            output,
            runtime_external,
            (DOTNET_PROJECT, DOTNET_DIR / "Program.cs"),
            build,
        )
    )


def build_rust() -> BuiltVariant:
    variant_id = "rust_native"
    output = BUILD_ROOT / variant_id
    output.mkdir(parents=True, exist_ok=True)
    command = [str(CARGO), "build", "--release", "--locked"]
    build = run_build(command, RUST_DIR)
    source = RUST_DIR / "target" / "release" / "baxy-rust-slice.exe"
    executable = output / "baxy-rust-slice.exe"
    if build["exit_code"] == 0:
        shutil.copy2(source, executable)
    return finalize_build(
        BuiltVariant(
            variant_id,
            "Rust",
            (str(executable), "--server"),
            output,
            executable,
            False,
            (RUST_DIR / "Cargo.toml", RUST_DIR / "Cargo.lock", RUST_DIR / "src" / "main.rs"),
            build,
        )
    )


def make_contender(variant: BuiltVariant) -> harness.Contender:
    artifacts = (
        (variant.artifact_root,)
        if variant.artifact_root.is_file()
        else tuple(sorted(path for path in variant.artifact_root.rglob("*") if path.is_file()))
    )
    return harness.Contender(
        variant.variant_id,
        variant.cwd,
        variant.command,
        ("already-built",),
        variant.source_files,
        artifacts,
        variant.runtime_external,
    )


def main() -> int:
    if sys.version_info[:2] != (3, 12):
        raise SystemExit("The frozen packaging harness requires CPython 3.12")
    if not PYTHON_PACKAGER.is_file():
        raise SystemExit("Install python_core/packaging-requirements.txt into python_core/.venv first")
    (ARTIFACTS / "build").mkdir(parents=True, exist_ok=True)
    harness.safe_reset_directory(BUILD_ROOT, ARTIFACTS / "build")
    cases = json.loads(harness.CASES_PATH.read_text(encoding="utf-8"))["cases"]
    protocol = json.loads(harness.PROTOCOL_PATH.read_text(encoding="utf-8"))
    started = datetime.now(timezone.utc).isoformat()
    variants = [
        build_embedded_python(),
        build_pyinstaller("onedir"),
        build_pyinstaller("onefile"),
        build_dotnet(
            "dotnet_fdd_single",
            ["--no-self-contained", "-p:PublishSingleFile=true"],
            True,
        ),
        build_dotnet(
            "dotnet_sc_single",
            [
                "--self-contained",
                "-p:PublishSingleFile=true",
                "-p:IncludeNativeLibrariesForSelfExtract=true",
            ],
            False,
        ),
        build_dotnet(
            "dotnet_native_aot",
            ["--self-contained", "-p:PublishAot=true", "-p:StripSymbols=true"],
            False,
        ),
        build_rust(),
    ]
    result: dict[str, Any] = {
        "schema_version": 1,
        "protocol_id": protocol["protocol_id"],
        "started_utc": started,
        "git_commit": harness.command_version(["git", "rev-parse", "HEAD"]),
        "protocol_sha256": harness.sha256_file(harness.PROTOCOL_PATH),
        "cases_sha256": harness.sha256_file(harness.CASES_PATH),
        "core_harness_sha256": harness.sha256_file(Path(harness.__file__)),
        "package_harness_sha256": harness.sha256_file(Path(__file__)),
        "ambient_before": harness.ambient_snapshot(),
        "packager_environment": harness.command_version([str(PYTHON_PACKAGER), "-m", "pip", "freeze"]),
        "variants": {},
    }
    for variant in variants:
        entry: dict[str, Any] = {
            "family": variant.family,
            "command": list(variant.command),
            "cwd": variant.cwd.relative_to(ROOT).as_posix(),
            "build": variant.build,
        }
        if variant.build["exit_code"] != 0 or not variant.artifact_root.exists():
            entry["fatal"] = "build_failed"
            result["variants"][variant.variant_id] = entry
            continue
        contender = make_contender(variant)
        entry["functional"] = harness.functional_run(contender, cases, 1)
        entry["cold_start"] = harness.cold_start_run(contender, 21)
        entry["warm"] = harness.warm_run(contender, 101)
        result["variants"][variant.variant_id] = entry
    result["ambient_after"] = harness.ambient_snapshot()
    result["finished_utc"] = datetime.now(timezone.utc).isoformat()
    RAW_PATH.parent.mkdir(parents=True, exist_ok=True)
    RAW_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(RAW_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
