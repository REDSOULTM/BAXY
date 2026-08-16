#!/usr/bin/env python3
"""Generate deterministic CycloneDX evidence for the two Round-B finalists."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import uuid
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "artifacts" / "technology_tournament"
RAW = ARTIFACTS / "raw"
SHELL_ROOT = ARTIFACTS / "build" / "round_b" / "wpf_sc_shell"
SHELL = SHELL_ROOT / "baxy-dotnet-wpf-slice.exe"
RUST_LOCK = ROOT / "experiments" / "technology_tournament" / "rust_core" / "Cargo.lock"
RUST_MANIFEST = ROOT / "experiments" / "technology_tournament" / "rust_core" / "Cargo.toml"
RUST_TOOLCHAIN = ROOT / "experiments" / "technology_tournament" / "rust_core" / "rust-toolchain.toml"
DOTNET_PROJECT = ROOT / "experiments" / "technology_tournament" / "dotnet_windows_core" / "BaxySlice.csproj"
DOTNET_PIN = ROOT / "global.json"
PROTOCOL_PATH = ARTIFACTS / "protocol.json"
PACKAGE_WORK = ARTIFACTS / "work" / "round_b_package"

RUNTIME_PACKS = (
    {
        "name": "Microsoft.NETCore.App.Runtime.win-x64",
        "version": "10.0.0",
        "purl": "pkg:nuget/Microsoft.NETCore.App.Runtime.win-x64@10.0.0",
        "relative": ".nuget/packages/microsoft.netcore.app.runtime.win-x64/10.0.0/microsoft.netcore.app.runtime.win-x64.10.0.0.nupkg",
        "sha256": "d94ce14ef10caa1adfbdeb0426493486685de9c4cc8debeff36d38d9b08318a1",
    },
    {
        "name": "Microsoft.WindowsDesktop.App.Runtime.win-x64",
        "version": "10.0.0",
        "purl": "pkg:nuget/Microsoft.WindowsDesktop.App.Runtime.win-x64@10.0.0",
        "relative": ".nuget/packages/microsoft.windowsdesktop.app.runtime.win-x64/10.0.0/microsoft.windowsdesktop.app.runtime.win-x64.10.0.0.nupkg",
        "sha256": "58da08d83e919c7205a282621783ee28df45b47e3fec8a83ad18c9fcc3077224",
    },
)

BUILD_COMPONENTS = (
    {
        "name": "Microsoft.DotNet.ILCompiler",
        "version": "10.0.0",
        "purl": "pkg:nuget/Microsoft.DotNet.ILCompiler@10.0.0",
        "relative": ".nuget/packages/microsoft.dotnet.ilcompiler/10.0.0/microsoft.dotnet.ilcompiler.10.0.0.nupkg",
        "sha256": "0df2eb213ee3196e122b35db63c68a164f5e36739306a0edc9e8c8526cf8ff36",
    },
    {
        "name": "runtime.win-x64.Microsoft.DotNet.ILCompiler",
        "version": "10.0.0",
        "purl": "pkg:nuget/runtime.win-x64.Microsoft.DotNet.ILCompiler@10.0.0",
        "relative": ".nuget/packages/runtime.win-x64.microsoft.dotnet.ilcompiler/10.0.0/runtime.win-x64.microsoft.dotnet.ilcompiler.10.0.0.nupkg",
        "sha256": "396341615f0b95e830c6a3287adf577f3fb32cc66bc1debee6f169ff9398d4af",
    },
)

ACTIVE_CRATES = {
    "serde_json": "MIT OR Apache-2.0",
    "itoa": "MIT OR Apache-2.0",
    "memchr": "Unlicense OR MIT",
    "serde_core": "MIT OR Apache-2.0",
    "zmij": "MIT",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def source_record(path: Path) -> dict[str, Any]:
    resolved = path.resolve()
    if not resolved.is_relative_to(ROOT.resolve()) or not resolved.is_file():
        raise SystemExit(f"Supply-chain provenance input is unsafe or missing: {path}")
    return {
        "path": resolved.relative_to(ROOT.resolve()).as_posix(),
        "bytes": resolved.stat().st_size,
        "sha256": sha256(resolved),
    }


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    """Publish evidence without exposing a partially written JSON document."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def tree_hash(root: Path, files: list[Path] | None = None) -> str:
    digest = hashlib.sha256()
    selected = files if files is not None else [path for path in root.rglob("*") if path.is_file()]
    for path in sorted(selected, key=lambda item: str(item).lower()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    return digest.hexdigest()


def validate_package_evidence(
    system_id: str,
    raw: dict[str, Any],
    manifest_path: Path,
    manifest: dict[str, Any],
) -> dict[str, Path]:
    if raw.get("system_id") != system_id:
        raise SystemExit(f"Package evidence system mismatch for {system_id}")
    if raw.get("overall_passed") is not True or raw.get("failed_gates"):
        raise SystemExit(f"Package lifecycle did not pass for {system_id}")
    gates = raw.get("gates")
    if not isinstance(gates, dict) or not gates or any(value is not True for value in gates.values()):
        raise SystemExit(f"Package lifecycle has an unproved gate for {system_id}")
    expected_header = {
        "schema_version": 1,
        "product": "BAXY",
        "version": "1.0.0",
        "system": system_id,
        "authenticity": "not_provided",
    }
    for key, value in expected_header.items():
        if manifest.get(key) != value:
            raise SystemExit(f"Manifest field {key} drifted for {system_id}")

    package_root = manifest_path.parent
    entries = manifest.get("files")
    if not isinstance(entries, list) or len(entries) != 10:
        raise SystemExit(f"Unexpected package payload count for {system_id}")
    verified: dict[str, Path] = {}
    for entry in entries:
        relative = entry.get("path") if isinstance(entry, dict) else None
        if not isinstance(relative, str):
            raise SystemExit(f"Manifest contains an invalid path for {system_id}")
        parsed = PurePosixPath(relative)
        if parsed.is_absolute() or ".." in parsed.parts or ":" in relative or relative in verified:
            raise SystemExit(f"Manifest contains an unsafe or duplicate path for {system_id}: {relative}")
        path = package_root.joinpath(*parsed.parts)
        if not path.is_file():
            raise SystemExit(f"Manifest payload is missing for {system_id}: {relative}")
        if path.stat().st_size != entry.get("bytes") or sha256(path) != entry.get("sha256"):
            raise SystemExit(f"Manifest payload drift for {system_id}: {relative}")
        verified[relative] = path

    actual = {
        path.relative_to(package_root).as_posix()
        for path in package_root.rglob("*")
        if path.is_file() and path != manifest_path
    }
    if actual != set(verified):
        raise SystemExit(f"Manifest file set drift for {system_id}")
    package_bytes = sum(path.stat().st_size for path in package_root.rglob("*") if path.is_file())
    if package_bytes != raw.get("package_bytes"):
        raise SystemExit(f"Package byte count drift for {system_id}")
    if verified["baxy-dotnet-wpf-slice.exe"] != SHELL:
        if sha256(verified["baxy-dotnet-wpf-slice.exe"]) != sha256(SHELL):
            raise SystemExit(f"Packaged shell differs from the measured shell for {system_id}")
    if sha256(SHELL) != raw.get("hashes", {}).get("shell_entrypoint_sha256"):
        raise SystemExit(f"Shell entrypoint hash drift for {system_id}")
    shell_files = [path for relative, path in verified.items() if "/" not in relative and relative.endswith((".exe", ".dll"))]
    if tree_hash(package_root, shell_files) != raw.get("hashes", {}).get("shell_bundle_sha256"):
        raise SystemExit(f"Shell bundle hash drift for {system_id}")
    return verified


def license_id(identifier: str) -> list[dict[str, Any]]:
    return [{"license": {"id": identifier}}]


def license_expression(expression: str) -> list[dict[str, Any]]:
    return [{"expression": expression}]


def component_hash(value: str) -> list[dict[str, str]]:
    return [{"alg": "SHA-256", "content": value.lower()}]


def verify_cached_packages(records: tuple[dict[str, str], ...]) -> None:
    home = Path.home()
    configured_root = os.environ.get("NUGET_PACKAGES")
    for record in records:
        relative = PurePosixPath(record["relative"])
        if configured_root:
            if relative.parts[:2] != (".nuget", "packages"):
                raise SystemExit(f"Unexpected cached package path: {relative}")
            path = Path(configured_root).joinpath(*relative.parts[2:])
        else:
            path = home / relative
        if not path.is_file():
            raise SystemExit(f"Required cached package is missing: {path}")
        observed = sha256(path)
        if observed != record["sha256"]:
            raise SystemExit(f"Package hash drift for {record['name']}: {observed}")


def lock_packages() -> dict[str, dict[str, str]]:
    packages: dict[str, dict[str, str]] = {}
    for block in RUST_LOCK.read_text(encoding="utf-8").split("[[package]]")[1:]:
        name = re.search(r'^name = "([^"]+)"', block, re.MULTILINE)
        version = re.search(r'^version = "([^"]+)"', block, re.MULTILINE)
        checksum = re.search(r'^checksum = "([0-9a-f]{64})"', block, re.MULTILINE)
        if name and version:
            packages[name.group(1)] = {
                "version": version.group(1),
                "checksum": checksum.group(1) if checksum else "",
            }
    return packages


def dumpbin_imports(binary: Path) -> list[str]:
    roots = [
        Path(r"C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Tools\MSVC"),
        Path(r"C:\Program Files\Microsoft Visual Studio\2022"),
    ]
    candidates: list[Path] = []
    for root in roots:
        if root.exists():
            candidates.extend(root.glob("**/bin/Hostx64/x64/dumpbin.exe"))
    if not candidates:
        return []
    output = subprocess.run(
        [str(sorted(candidates)[-1]), "/dependents", str(binary)],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    ).stdout
    return sorted({match.lower() for match in re.findall(r"^\s+([A-Za-z0-9_.-]+\.dll)\s*$", output, re.MULTILINE)})


def common_components(shell_signature: str) -> list[dict[str, Any]]:
    components: list[dict[str, Any]] = [
        {
            "type": "application",
            "bom-ref": "baxy:wpf-shell",
            "name": "BAXY WPF shell",
            "version": "1.0.0",
            "hashes": component_hash(sha256(SHELL)),
            "properties": [
                {"name": "baxy:first-party-license", "value": "not-declared"},
                {"name": "baxy:authenticode", "value": shell_signature},
            ],
        }
    ]
    for record in RUNTIME_PACKS:
        components.append(
            {
                "type": "framework",
                "bom-ref": record["purl"],
                "name": record["name"],
                "version": record["version"],
                "purl": record["purl"],
                "hashes": component_hash(record["sha256"]),
                "licenses": license_id("MIT"),
                "supplier": {"name": "Microsoft"},
                "externalReferences": [
                    {"type": "vcs", "url": "https://github.com/dotnet/dotnet"},
                    {"type": "license", "url": "https://github.com/dotnet/runtime/blob/main/LICENSE.TXT"},
                ],
            }
        )
    return components


def build_tools(include_rust: bool) -> list[dict[str, Any]]:
    tools: list[dict[str, Any]] = [
        {"type": "application", "name": ".NET SDK", "version": "10.0.100"},
    ]
    for record in BUILD_COMPONENTS:
        tools.append(
            {
                "type": "application",
                "name": record["name"],
                "version": record["version"],
                "purl": record["purl"],
                "hashes": component_hash(record["sha256"]),
                "licenses": license_id("MIT"),
                "supplier": {"name": "Microsoft"},
            }
        )
    if include_rust:
        tools.append(
            {
                "type": "application",
                "name": "rustc",
                "version": "1.97.0",
                "licenses": license_expression("MIT OR Apache-2.0"),
            }
        )
    return tools


def make_bom(system_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    rust = system_id == "dotnet-wpf-rust"
    raw = load_json(RAW / f"round_b_package_{system_id.replace('-', '_')}.json")
    signatures = raw.get("signatures", {})
    if signatures.get("shell") != "NotSigned" or signatures.get("core") != "NotSigned":
        raise SystemExit(f"Unexpected measured Authenticode state for {system_id}: {signatures}")
    manifest_path = PACKAGE_WORK / system_id / "packages" / "1.0.0" / "manifest.json"
    manifest = load_json(manifest_path)
    verified_files = validate_package_evidence(system_id, raw, manifest_path, manifest)
    core_path = (
        ARTIFACTS / "build" / "packaging" / "rust_native" / "baxy-rust-slice.exe"
        if rust
        else ARTIFACTS / "build" / "packaging" / "dotnet_native_aot" / "baxy-dotnet-slice.exe"
    )
    core_hash = sha256(core_path)
    if core_hash != raw["hashes"]["core_sha256"]:
        raise SystemExit(f"Core hash does not match package evidence for {system_id}")
    if core_hash != sha256(verified_files["core/baxy-core.exe"]):
        raise SystemExit(f"Packaged core differs from measured core for {system_id}")

    package_ref = f"baxy:round-b:{system_id}:1.0.0"
    core_ref = "baxy:rust-core" if rust else "baxy:dotnet-core"
    components = common_components(signatures["shell"])
    core_component: dict[str, Any] = {
            "type": "application",
            "bom-ref": core_ref,
            "name": "BAXY Rust core" if rust else "BAXY .NET NativeAOT core",
            "version": "0.1.0" if rust else "1.0.0",
            "hashes": component_hash(core_hash),
            "properties": [
                {"name": "baxy:first-party-license", "value": "not-declared"},
                {"name": "baxy:authenticode", "value": signatures["core"]},
                {"name": "baxy:static-msvc-crt", "value": str(rust).lower()},
            ],
        }
    if rust:
        core_component["licenses"] = license_id("MIT")
        core_component["properties"].append({"name": "baxy:crate-license-source", "value": "Cargo.toml"})
    components.append(core_component)

    dependency_refs = ["baxy:wpf-shell", core_ref]
    core_dependencies: list[str] = []
    locked = lock_packages()
    if rust:
        for name, expression in ACTIVE_CRATES.items():
            record = locked[name]
            ref = f"pkg:cargo/{name}@{record['version']}"
            core_dependencies.append(ref)
            components.append(
                {
                    "type": "library",
                    "bom-ref": ref,
                    "name": name,
                    "version": record["version"],
                    "purl": ref,
                    "hashes": component_hash(record["checksum"]),
                    "licenses": license_expression(expression),
                    "externalReferences": [
                        {"type": "distribution", "url": f"https://crates.io/crates/{name}/{record['version']}"}
                    ],
                }
            )
        components.extend(
            [
                {
                    "type": "framework",
                    "bom-ref": "baxy:rust-std:1.97.0",
                    "name": "Rust standard library",
                    "version": "1.97.0",
                    "licenses": license_expression("MIT OR Apache-2.0"),
                    "properties": [{"name": "baxy:linkage", "value": "static"}],
                },
                {
                    "type": "framework",
                    "bom-ref": "baxy:msvc-crt:14.44",
                    "name": "Microsoft Visual C++ / Universal CRT",
                    "version": "14.44",
                    "licenses": license_expression("LicenseRef-Microsoft-Visual-Cpp-Runtime AND LicenseRef-Microsoft-Windows-SDK"),
                    "properties": [
                        {"name": "baxy:linkage", "value": "static"},
                        {"name": "baxy:exact-linked-libraries", "value": "not-recorded"},
                    ],
                },
            ]
        )
        core_dependencies.extend(["baxy:rust-std:1.97.0", "baxy:msvc-crt:14.44"])
    else:
        core_dependencies.append(RUNTIME_PACKS[0]["purl"])

    package_component = {
        "type": "application",
        "bom-ref": package_ref,
        "name": "BAXY Round-B integrated package",
        "version": "1.0.0",
        "hashes": component_hash(sha256(manifest_path)),
        "properties": [
            {"name": "baxy:system-id", "value": system_id},
            {"name": "baxy:package-bytes", "value": str(raw["package_bytes"])},
            {"name": "baxy:manifest-authenticity", "value": "not-provided"},
            {"name": "baxy:hash-scope", "value": "manifest.json"},
        ],
    }

    serial_seed = f"{system_id}:{sha256(manifest_path)}:{core_hash}:{sha256(SHELL)}"
    bom = {
        "$schema": "https://cyclonedx.org/schema/bom-1.6.schema.json",
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "serialNumber": f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, serial_seed)}",
        "version": 1,
        "metadata": {
            "tools": {"components": build_tools(rust)},
            "component": package_component,
            "properties": [
                {"name": "baxy:generated-from", "value": "Round-B package manifest, Cargo.lock and pinned local package hashes"},
                {"name": "baxy:first-party-license-declared", "value": str((ROOT / "LICENSE").is_file()).lower()},
            ],
        },
        "components": sorted(components, key=lambda item: item["bom-ref"]),
        "dependencies": [
            {"ref": package_ref, "dependsOn": dependency_refs},
            {
                "ref": "baxy:wpf-shell",
                "dependsOn": [record["purl"] for record in RUNTIME_PACKS],
            },
            {"ref": core_ref, "dependsOn": core_dependencies},
        ],
    }
    report = {
        "system_id": system_id,
        "package_manifest_sha256": sha256(manifest_path),
        "package_bytes": raw["package_bytes"],
        "shell_sha256": sha256(SHELL),
        "core_sha256": core_hash,
        "core_imports": dumpbin_imports(core_path),
        "runtime_external_packages": 5 if rust else 0,
        "cargo_lock_external_packages": len([item for item in locked if item != "baxy-rust-slice"]) if rust else 0,
        "first_party_license_declared": (ROOT / "LICENSE").is_file(),
        "authenticode": {"shell": signatures["shell"], "core": signatures["core"]},
        "authenticode_source": "round_b_package_lifecycle.signatures",
        "manifest_authenticity": "not_provided",
        "package_gates_passed": len(raw["gates"]),
        "manifest_file_count": len(verified_files),
        "manifest_all_files_verified": True,
        "runtime_framework_packs": len(RUNTIME_PACKS),
        "external_application_packages": 5 if rust else 0,
        "sbom_component_count": len(components) + 1,
    }
    return bom, report


def main() -> int:
    verify_cached_packages(RUNTIME_PACKS + BUILD_COMPONENTS)
    reports: list[dict[str, Any]] = []
    for system_id in ("dotnet-wpf", "dotnet-wpf-rust"):
        bom, report = make_bom(system_id)
        output = ARTIFACTS / f"round_b_sbom_{system_id.replace('-', '_')}.cdx.json"
        atomic_write_json(output, bom)
        report["sbom_path"] = output.relative_to(ROOT).as_posix()
        report["sbom_sha256"] = sha256(output)
        reports.append(report)
    supply_chain = {
        "schema_version": 1,
        "protocol_id": "baxy-technology-tournament-v1",
        "round": "b_supply_chain",
        "provenance": {
            "generator": source_record(Path(__file__)),
            "protocol": source_record(PROTOCOL_PATH),
            "package_evidence": {
                system_id: source_record(RAW / f"round_b_package_{system_id.replace('-', '_')}.json")
                for system_id in ("dotnet-wpf", "dotnet-wpf-rust")
            },
            "build_inputs": {
                "dotnet_pin": source_record(DOTNET_PIN),
                "dotnet_project": source_record(DOTNET_PROJECT),
                "rust_toolchain": source_record(RUST_TOOLCHAIN),
                "rust_manifest": source_record(RUST_MANIFEST),
                "rust_lock": source_record(RUST_LOCK),
            },
        },
        "systems": reports,
        "known_gaps": [
            "First-party license is not declared.",
            "BAXY executables are not Authenticode signed.",
            "Package manifests are not signed and do not prove authenticity.",
            "The statically linked Rust core lacks an exact MSVC/UCRT link manifest.",
            "The embedded icon has no recorded author, license or provenance.",
        ],
    }
    output = ARTIFACTS / "raw" / "round_b_supply_chain.json"
    atomic_write_json(output, supply_chain)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
