from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import unittest
import uuid
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILD_AREA = ROOT / "artifacts" / "product" / "build"
BUILD_SCRIPT = ROOT / "scripts" / "build_product.ps1"
PACKAGE_SCRIPT = ROOT / "scripts" / "package_product.ps1"
SCHEMA = "baxy-product-build-v4"
PRODUCT_PATHS = [
    "Baxy.exe",
    "D3DCompiler_47_cor3.dll",
    "DesktopClickVisible.ps1",
    "DesktopKeyPress.ps1",
    "DesktopSelectAll.ps1",
    "FieldUi/assets/index-CjozYCnU.css",
    "FieldUi/assets/index-D3QuhrLm.js",
    "FieldUi/index.html",
    "FieldUiHost/field-native-bridge.js",
    "KnownFileOpen.ps1",
    "KnownFolderOpen.ps1",
    "Microsoft.Web.WebView2.Core.xml",
    "Microsoft.Web.WebView2.WinForms.xml",
    "Microsoft.Web.WebView2.Wpf.xml",
    "PenImc_cor3.dll",
    "PresentationNative_cor3.dll",
    "SpotifyDesktopAutomation.ps1",
    "SpotifyMediaControl.ps1",
    "WebView2Loader.dll",
    "WindowsScheduledNotification.ps1",
    "core/DesktopClickVisible.ps1",
    "core/DesktopKeyPress.ps1",
    "core/DesktopSelectAll.ps1",
    "core/KnownFileOpen.ps1",
    "core/KnownFolderOpen.ps1",
    "core/SpotifyDesktopAutomation.ps1",
    "core/SpotifyMediaControl.ps1",
    "core/WindowsScheduledNotification.ps1",
    "core/baxy-core.exe",
    "runtimes/win-x64/native/WebView2Loader.dll",
    "tools/mpv/mpv.exe",
    "tools/mpv/vulkan-1.dll",
    "tools/yt-dlp/yt-dlp.exe",
    "vcruntime140_cor3.dll",
    "wpfgfx_cor3.dll",
]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def run_powershell(
    script: Path, *arguments: str, timeout: int = 45, cwd: Path = ROOT
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            *arguments,
        ],
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def source_identity() -> tuple[str, int]:
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    epoch = int(
        subprocess.check_output(
            ["git", "show", "-s", "--format=%ct", "HEAD"], cwd=ROOT, text=True
        ).strip()
    )
    return commit, epoch


class ProductPackagingTests(unittest.TestCase):
    def setUp(self) -> None:
        BUILD_AREA.mkdir(parents=True, exist_ok=True)
        self.sandbox = BUILD_AREA / f"packaging-test-{uuid.uuid4().hex}"
        self.build_root = self.sandbox / "input"
        self.payload_root = self.build_root / "app"
        (self.payload_root / "core").mkdir(parents=True)
        self.commit, self.epoch = source_identity()
        for relative in PRODUCT_PATHS:
            destination = self.payload_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(f"synthetic-{relative}\0v1".encode())
        self.write_manifest(dirty=False)

    def tearDown(self) -> None:
        shutil.rmtree(self.sandbox, ignore_errors=True)

    def test_sendinput_script_uses_the_complete_native_input_union(self) -> None:
        script = (
            ROOT
            / "src"
            / "Baxy.Providers.Windows"
            / "External"
            / "DesktopKeyPress.ps1"
        ).read_text(encoding="utf-8")
        self.assertIn("[FieldOffset(0)] public MOUSEINPUT mouse;", script)
        self.assertIn("[FieldOffset(0)] public HARDWAREINPUT hardware;", script)
        self.assertIn("if([IntPtr]::Size -eq 8){40}else{28}", script)
        self.assertIn("sendinput_layout_invalid", script)
        self.assertIn("acceptedEvents=$accepted", script)

    def test_select_all_script_verifies_textpattern_and_native_edit_controls(
        self,
    ) -> None:
        script = (
            ROOT
            / "src"
            / "Baxy.Providers.Windows"
            / "External"
            / "DesktopSelectAll.ps1"
        ).read_text(encoding="utf-8")
        self.assertIn("Add-Type -AssemblyName UIAutomationTypes", script)
        self.assertIn(
            "Windows.Automation.Text.TextPatternRangeEndpoint",
            script,
        )
        self.assertIn("EmGetSel = 0x00B0", script)
        self.assertIn("EmSetSel = 0x00B1", script)
        self.assertIn("EmGetTextLength = 0x000E", script)
        self.assertIn("SendControlA", script)
        self.assertIn("SelectAll($nativeHandle)", script)
        self.assertIn("acceptedEvents=$accepted", script)
        self.assertIn("win32_edit_selection_postread", script)
        self.assertIn("select_all_postcondition_not_verified", script)

    def manifest_object(self, *, dirty: bool) -> dict:
        files = []
        for path in sorted(
            (candidate for candidate in self.payload_root.rglob("*") if candidate.is_file()),
            key=lambda candidate: candidate.relative_to(self.payload_root).as_posix(),
        ):
            relative = path.relative_to(self.payload_root).as_posix()
            files.append(
                {
                    "path": relative,
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
        return {
            "schema": SCHEMA,
            "product": "BAXY",
            "version": "1.2.3",
            "data_schema": 1,
            "configuration": "Release",
            "runtime": "win-x64",
            "target_framework": "net10.0-windows10.0.19041.0",
            "authenticity": "not_provided",
            "source": {
                "commit": self.commit,
                "dirty": dirty,
                "provenance": (
                    "working_tree_development" if dirty else "git_head_snapshot"
                ),
                "source_date_epoch": self.epoch,
            },
            "toolchain": {"dotnet_sdk": "10.0.100", "powershell": "5.1"},
            "deployment": {
                "app": "self_contained_single_file",
                "native_libraries": "adjacent_no_self_extraction",
                "core": "native_aot_self_contained",
                "symbols": "excluded_from_user_payload",
            },
            "file_count": len(files),
            "total_bytes": sum(record["bytes"] for record in files),
            "files": files,
        }

    def write_manifest(self, *, dirty: bool) -> dict:
        manifest = self.manifest_object(dirty=dirty)
        (self.build_root / "build-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
            newline="",
        )
        return manifest

    def package(
        self, output: Path, *, allow_development: bool = False
    ) -> subprocess.CompletedProcess[str]:
        arguments = ["-BuildRoot", str(self.build_root), "-OutputRoot", str(output)]
        if allow_development:
            arguments.append("-AllowDirtyDevelopmentBuild")
        return run_powershell(PACKAGE_SCRIPT, *arguments)

    def assert_failed_without_mutating_output(
        self, result: subprocess.CompletedProcess[str], sentinel: Path
    ) -> None:
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertTrue(sentinel.is_file(), result.stderr)
        self.assertEqual(sentinel.read_bytes(), b"preserve-me")

    def test_release_build_rejects_dirty_tree_before_mutating_output(self) -> None:
        dirty_marker = ROOT / "tests" / f".baxy-dirty-gate-{uuid.uuid4().hex}"
        guarded_output = self.sandbox / "guarded-build"
        guarded_output.mkdir()
        sentinel = guarded_output / "sentinel.bin"
        sentinel.write_bytes(b"preserve-me")
        dirty_marker.write_text("force dirty worktree", encoding="utf-8")
        try:
            result = run_powershell(
                BUILD_SCRIPT,
                "-Configuration",
                "Release",
                "-OutputRoot",
                str(guarded_output),
                timeout=20,
            )
        finally:
            dirty_marker.unlink(missing_ok=True)
        self.assert_failed_without_mutating_output(result, sentinel)
        self.assertIn("worktree is dirty", result.stderr.lower())

    def test_release_dirty_rejection_is_independent_of_callers_cwd(self) -> None:
        dirty_marker = ROOT / "tests" / f".baxy-dirty-cwd-{uuid.uuid4().hex}"
        guarded_output = self.sandbox / "guarded-cwd-build"
        guarded_output.mkdir()
        sentinel = guarded_output / "sentinel.bin"
        sentinel.write_bytes(b"preserve-me")
        dirty_marker.write_text("force dirty worktree", encoding="utf-8")
        try:
            result = run_powershell(
                BUILD_SCRIPT,
                "-Configuration",
                "Release",
                "-OutputRoot",
                str(guarded_output),
                timeout=20,
                cwd=self.sandbox,
            )
        finally:
            dirty_marker.unlink(missing_ok=True)
        self.assert_failed_without_mutating_output(result, sentinel)

    def test_detached_head_snapshot_is_exact_and_cleanup_removes_it(self) -> None:
        snapshot = self.sandbox / "head-snapshot"
        command = f"""
$ErrorActionPreference = 'Stop'
. '{ROOT / 'scripts' / 'path_safety.ps1'}'
. '{ROOT / 'scripts' / 'product_build_common.ps1'}'
$created = $false
try {{
    $path = New-BaxyHeadWorktreeSnapshot -RepositoryRoot '{ROOT}' -AllowedRoot '{BUILD_AREA}' -SnapshotRoot '{snapshot}' -Commit '{self.commit}'
    $created = $true
    $actual = ([string](& git -C $path rev-parse HEAD)).Trim()
    if ($actual -cne '{self.commit}') {{ throw 'snapshot commit mismatch' }}
    if (@(& git -C $path status --porcelain=v1 --untracked-files=all).Count -ne 0) {{ throw 'snapshot is dirty' }}
}} finally {{
    if ($created -or (Test-Path -LiteralPath '{snapshot}')) {{
        Remove-BaxyHeadWorktreeSnapshot -RepositoryRoot '{ROOT}' -AllowedRoot '{BUILD_AREA}' -SnapshotRoot '{snapshot}'
    }}
}}
"""
        result = subprocess.run(
            [
                "powershell.exe",
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                command,
            ],
            cwd=self.sandbox,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=45,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(snapshot.exists())

    def test_package_is_byte_reproducible_and_self_verifying(self) -> None:
        first_output = self.sandbox / "package-a"
        second_output = self.sandbox / "package-b"
        first = self.package(first_output)
        second = self.package(second_output)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)

        first_zip = next(first_output.glob("*.zip"))
        second_zip = next(second_output.glob("*.zip"))
        self.assertEqual(first_zip.name, second_zip.name)
        self.assertEqual(first_zip.read_bytes(), second_zip.read_bytes())

        package_hash = sha256_file(first_zip)
        digest = Path(str(first_zip) + ".sha256")
        self.assertEqual(
            digest.read_bytes(), f"{package_hash}  {first_zip.name}\n".encode("utf-8")
        )

        manifest_path = self.build_root / "build-manifest.json"
        expected_hashes = {
            path: sha256_file(self.payload_root / Path(path)) for path in PRODUCT_PATHS
        }
        expected_hashes["build-manifest.json"] = sha256_file(manifest_path)
        checksum_text = "".join(
            f"{digest_value}  {path}\n"
            for path, digest_value in sorted(expected_hashes.items())
        )
        expected_entries = sorted([*expected_hashes, "SHA256SUMS"])
        fixed_time = dt.datetime.fromtimestamp(self.epoch, tz=dt.timezone.utc).replace(
            microsecond=0
        )
        fixed_time = fixed_time.replace(second=fixed_time.second - fixed_time.second % 2)
        with zipfile.ZipFile(first_zip, "r") as archive:
            infos = archive.infolist()
            self.assertEqual([info.filename for info in infos], expected_entries)
            self.assertTrue(all(not info.is_dir() for info in infos))
            self.assertEqual(archive.read("SHA256SUMS"), checksum_text.encode("utf-8"))
            for info in infos:
                self.assertEqual(info.compress_type, zipfile.ZIP_STORED)
                self.assertEqual(info.date_time, fixed_time.timetuple()[:6])
                self.assertEqual(info.external_attr, 0)
            for path, digest_value in expected_hashes.items():
                self.assertEqual(sha256_bytes(archive.read(path)), digest_value)

    def test_external_digest_detects_package_tamper(self) -> None:
        output = self.sandbox / "tamper-package"
        result = self.package(output)
        self.assertEqual(result.returncode, 0, result.stderr)
        package = next(output.glob("*.zip"))
        digest_path = Path(str(package) + ".sha256")
        expected = digest_path.read_text(encoding="utf-8").split()[0]
        tampered = bytearray(package.read_bytes())
        tampered[len(tampered) // 2] ^= 1
        package.write_bytes(tampered)
        self.assertNotEqual(sha256_file(package), expected)

    def test_validated_manifest_bytes_remain_immutable_after_path_changes(self) -> None:
        common = ROOT / "scripts" / "product_build_common.ps1"
        command = f"""
$ErrorActionPreference = 'Stop'
. '{ROOT / 'scripts' / 'path_safety.ps1'}'
. '{common}'
$validated = Get-BaxyValidatedBuildManifest -BuildRoot '{self.build_root}'
$before = [Convert]::ToBase64String([byte[]]$validated.manifest_bytes)
Set-Content -LiteralPath '{self.build_root / 'build-manifest.json'}' -Value '{{"tampered":true}}'
$after = [Convert]::ToBase64String([byte[]]$validated.manifest_bytes)
if ($before -cne $after) {{ throw 'validated manifest bytes mutated' }}
if ((Get-BaxyBytesSha256 -Bytes ([byte[]]$validated.manifest_bytes)) -cne [string]$validated.manifest_sha256) {{
    throw 'validated manifest digest changed'
}}
"""
        result = subprocess.run(
            [
                "powershell.exe",
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                command,
            ],
            cwd=self.sandbox,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_dirty_build_needs_explicit_development_override(self) -> None:
        self.write_manifest(dirty=True)
        output = self.sandbox / "dirty-package"
        output.mkdir()
        sentinel = output / "sentinel.bin"
        sentinel.write_bytes(b"preserve-me")
        refused = self.package(output)
        self.assert_failed_without_mutating_output(refused, sentinel)
        self.assertIn("allowdirtydevelopmentbuild", refused.stderr.lower())

        accepted = self.package(output, allow_development=True)
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        package = next(output.glob("*.zip"))
        self.assertIn("-dirty-win-x64.zip", package.name)
        with zipfile.ZipFile(package, "r") as archive:
            manifest = json.loads(archive.read("build-manifest.json"))
        self.assertIs(manifest["source"]["dirty"], True)

    def test_unmanifested_debug_symbols_are_rejected_before_output_mutation(self) -> None:
        for extension in ("pdb", "dbg"):
            with self.subTest(extension=extension):
                leaked = self.payload_root / f"private-paths.{extension}"
                leaked.write_bytes(b"symbol bytes")
                output = self.sandbox / f"symbol-{extension}"
                output.mkdir()
                sentinel = output / "sentinel.bin"
                sentinel.write_bytes(b"preserve-me")
                result = self.package(output)
                self.assert_failed_without_mutating_output(result, sentinel)
                self.assertIn(f".{extension}", result.stderr.lower())
                leaked.unlink()

    def test_any_unmanifested_bytes_are_rejected_before_output_mutation(self) -> None:
        (self.payload_root / "rogue.bin").write_bytes(b"not in manifest")
        output = self.sandbox / "rogue-package"
        output.mkdir()
        sentinel = output / "sentinel.bin"
        sentinel.write_bytes(b"preserve-me")
        result = self.package(output)
        self.assert_failed_without_mutating_output(result, sentinel)
        self.assertIn(f"exactly {len(PRODUCT_PATHS)}", result.stderr.lower())

    def test_case_insensitive_duplicate_manifest_path_is_rejected(self) -> None:
        manifest = self.manifest_object(dirty=False)
        duplicate = dict(manifest["files"][0])
        duplicate["path"] = duplicate["path"].lower()
        manifest["files"].append(duplicate)
        manifest["file_count"] += 1
        manifest["total_bytes"] += duplicate["bytes"]
        (self.build_root / "build-manifest.json").write_text(
            json.dumps(manifest, separators=(",", ":")), encoding="utf-8", newline=""
        )
        output = self.sandbox / "duplicate-package"
        result = self.package(output)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("duplicate manifest path", result.stderr.lower())
        self.assertFalse(output.exists())

    def test_payload_missing_a_reviewed_native_companion_is_rejected(self) -> None:
        missing = self.payload_root / "PenImc_cor3.dll"
        missing.unlink()
        self.write_manifest(dirty=False)
        output = self.sandbox / "missing-companion"
        result = self.package(output)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(f"exactly {len(PRODUCT_PATHS)}", result.stderr.lower())
        self.assertFalse(output.exists())

    @unittest.skipUnless(os.name == "nt", "alternate data streams are Windows-specific")
    def test_alternate_data_stream_is_rejected(self) -> None:
        app = self.payload_root / "Baxy.exe"
        with open(f"{app}:forbidden", "wb") as stream:
            stream.write(b"hidden bytes")
        output = self.sandbox / "ads-package"
        output.mkdir()
        sentinel = output / "sentinel.bin"
        sentinel.write_bytes(b"preserve-me")
        result = self.package(output)
        self.assert_failed_without_mutating_output(result, sentinel)
        self.assertIn("alternate data stream", result.stderr.lower())

    @unittest.skipUnless(os.name == "nt", "directory streams are Windows-specific")
    def test_alternate_data_stream_on_directory_is_rejected(self) -> None:
        core_directory = self.payload_root / "core"
        with open(f"{core_directory}:forbidden", "wb") as stream:
            stream.write(b"hidden directory bytes")
        output = self.sandbox / "directory-ads-package"
        output.mkdir()
        sentinel = output / "sentinel.bin"
        sentinel.write_bytes(b"preserve-me")
        result = self.package(output)
        self.assert_failed_without_mutating_output(result, sentinel)
        self.assertIn("alternate data stream", result.stderr.lower())

    def test_unsafe_manifest_path_is_rejected(self) -> None:
        manifest = self.manifest_object(dirty=False)
        manifest["files"][0]["path"] = "../Baxy.exe"
        (self.build_root / "build-manifest.json").write_text(
            json.dumps(manifest, separators=(",", ":")), encoding="utf-8", newline=""
        )
        output = self.sandbox / "unsafe-package"
        result = self.package(output)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("traverses", result.stderr.lower())
        self.assertFalse(output.exists())

    def test_configuration_requires_canonical_casing(self) -> None:
        manifest = self.manifest_object(dirty=False)
        manifest["configuration"] = "release"
        (self.build_root / "build-manifest.json").write_text(
            json.dumps(manifest, separators=(",", ":")), encoding="utf-8", newline=""
        )
        result = self.package(self.sandbox / "lowercase-release")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid configuration", result.stderr.lower())

    def test_data_schema_is_exact_integer_one(self) -> None:
        for value in (2, True, "1"):
            with self.subTest(value=value):
                manifest = self.manifest_object(dirty=False)
                manifest["data_schema"] = value
                (self.build_root / "build-manifest.json").write_text(
                    json.dumps(manifest, separators=(",", ":")),
                    encoding="utf-8",
                    newline="",
                )
                result = self.package(self.sandbox / f"bad-data-schema-{type(value).__name__}")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("unsupported data schema", result.stderr.lower())

    def test_semver_rejects_numeric_prerelease_leading_zero(self) -> None:
        manifest = self.manifest_object(dirty=False)
        manifest["version"] = "1.2.3-alpha.01"
        (self.build_root / "build-manifest.json").write_text(
            json.dumps(manifest, separators=(",", ":")), encoding="utf-8", newline=""
        )
        result = self.package(self.sandbox / "bad-semver")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid semantic version", result.stderr.lower())

    def test_semver_rejects_trailing_newline(self) -> None:
        manifest = self.manifest_object(dirty=False)
        manifest["version"] = "1.2.3\n"
        (self.build_root / "build-manifest.json").write_text(
            json.dumps(manifest, separators=(",", ":")), encoding="utf-8", newline=""
        )
        result = self.package(self.sandbox / "newline-semver")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid semantic version", result.stderr.lower())

    def test_zip_inspector_rejects_noncanonical_central_metadata(self) -> None:
        output = self.sandbox / "zip-metadata-tamper"
        result = self.package(output)
        self.assertEqual(result.returncode, 0, result.stderr)
        package = next(output.glob("*.zip"))
        archive_bytes = bytearray(package.read_bytes())
        central_offset = archive_bytes.find(b"PK\x01\x02")
        self.assertGreaterEqual(central_offset, 0)
        self.assertEqual(archive_bytes[central_offset + 4], 20)
        archive_bytes[central_offset + 4] = 21
        package.write_bytes(archive_bytes)
        with zipfile.ZipFile(package, "r") as archive:
            self.assertIsNone(archive.testzip())

        command = f"""
$ErrorActionPreference = 'Stop'
. '{ROOT / 'scripts' / 'path_safety.ps1'}'
. '{ROOT / 'scripts' / 'product_build_common.ps1'}'
[BaxyZipStorageInspector]::AssertStored('{package}')
"""
        inspected = subprocess.run(
            [
                "powershell.exe",
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                command,
            ],
            cwd=self.sandbox,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=30,
            check=False,
        )
        self.assertNotEqual(inspected.returncode, 0)
        self.assertIn("version", inspected.stderr.lower())

    def test_scripts_keep_product_payload_policy_explicit(self) -> None:
        build_text = BUILD_SCRIPT.read_text(encoding="utf-8")
        common_text = (ROOT / "scripts" / "product_build_common.ps1").read_text(
            encoding="utf-8"
        )
        package_text = PACKAGE_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("-p:PublishSingleFile=true", build_text)
        self.assertIn("-p:StripSymbols=true", build_text)
        self.assertIn("-p:NativeDebugSymbols=false", build_text)
        self.assertIn("--self-contained', 'true'", build_text)
        self.assertNotIn("created_utc", build_text + common_text + package_text)
        self.assertIn("SHA256SUMS", package_text)
        self.assertIn("BaxyStoredZipWriter", package_text + common_text)
        self.assertIn("Cleanup also failed closed", build_text + package_text)
        self.assertIn("BaxyZipStorageInspector", package_text + common_text)
        self.assertIn("manifest_bytes", package_text)
        self.assertGreaterEqual(
            package_text.count("Assert-DeterministicProductZip -Path $packagePath"), 2
        )
        self.assertIn("Push-Location $sourceRoot", build_text)
        self.assertIn("New-BaxyHeadWorktreeSnapshot", build_text)
        self.assertIn("\\z", build_text)
        self.assertIn("\\z", common_text)

    def test_native_aot_linker_uses_reproducible_pe_metadata(self) -> None:
        project_text = (ROOT / "src" / "Baxy.Core" / "Baxy.Core.csproj").read_text(
            encoding="utf-8"
        )

        self.assertIn("Condition=\"'$(PublishAot)' == 'true'\"", project_text)
        self.assertIn('<LinkerArg Include="/Brepro" />', project_text)

    def test_product_capture_removes_its_private_runtime_tree(self) -> None:
        capture_text = (ROOT / "scripts" / "capture_product.ps1").read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "Remove-TreeFailClosed -AllowedRoot $allowedRuntimeRoot -Target $dataRoot",
            capture_text,
        )
        self.assertIn("runtime cleanup failed closed", capture_text)


if __name__ == "__main__":
    unittest.main()
