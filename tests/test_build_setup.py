from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import textwrap
import unittest
import zlib


ROOT = Path(__file__).resolve().parents[1]
BUILD_SETUP = ROOT / "scripts" / "build_setup.ps1"
POWERSHELL = shutil.which("powershell.exe") or shutil.which("powershell")

PAYLOAD_PATHS = [
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
CHECKSUM_PATHS = [
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
    "build-manifest.json",
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
ZIP_PATHS = sorted({*CHECKSUM_PATHS, "SHA256SUMS"})


def package_contract_paths(name: str) -> list[str]:
    source = (ROOT / "src" / "Baxy.Setup" / "PackageContract.cs").read_text(
        encoding="utf-8"
    )
    match = re.search(
        rf"internal static readonly string\[\] {re.escape(name)}\s*=\s*\[(.*?)\];",
        source,
        re.DOTALL,
    )
    if match is None:
        raise AssertionError(f"PackageContract.{name} was not found")
    return re.findall(r'"([^"]+)"', match.group(1))


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fixed_dos_timestamp(epoch: int) -> tuple[int, int]:
    timestamp = dt.datetime.fromtimestamp(epoch, tz=dt.timezone.utc)
    minimum = dt.datetime(1980, 1, 1, tzinfo=dt.timezone.utc)
    maximum = dt.datetime(2107, 12, 31, 23, 59, 58, tzinfo=dt.timezone.utc)
    timestamp = min(max(timestamp, minimum), maximum).replace(microsecond=0)
    timestamp -= dt.timedelta(seconds=timestamp.second % 2)
    dos_time = (timestamp.hour << 11) | (timestamp.minute << 5) | (timestamp.second // 2)
    dos_date = ((timestamp.year - 1980) << 9) | (timestamp.month << 5) | timestamp.day
    return dos_time, dos_date


def write_canonical_stored_zip(path: Path, entries: dict[str, bytes], epoch: int) -> None:
    dos_time, dos_date = fixed_dos_timestamp(epoch)
    local = bytearray()
    central_records: list[bytes] = []
    for name in sorted(entries):
        name_bytes = name.encode("utf-8")
        content = entries[name]
        crc = zlib.crc32(content) & 0xFFFFFFFF
        local_offset = len(local)
        local.extend(
            struct.pack(
                "<IHHHHHIIIHH",
                0x04034B50,
                20,
                0x0808,
                0,
                dos_time,
                dos_date,
                0,
                0,
                0,
                len(name_bytes),
                0,
            )
        )
        local.extend(name_bytes)
        local.extend(content)
        local.extend(struct.pack("<IIII", 0x08074B50, crc, len(content), len(content)))
        central_records.append(
            struct.pack(
                "<IHHHHHHIIIHHHHHII",
                0x02014B50,
                20,
                20,
                0x0808,
                0,
                dos_time,
                dos_date,
                crc,
                len(content),
                len(content),
                len(name_bytes),
                0,
                0,
                0,
                0,
                0,
                local_offset,
            )
            + name_bytes
        )

    central_offset = len(local)
    central = b"".join(central_records)
    eocd = struct.pack(
        "<IHHHHIIH",
        0x06054B50,
        0,
        0,
        len(entries),
        len(entries),
        len(central),
        central_offset,
        0,
    )
    path.write_bytes(bytes(local) + central + eocd)


def create_product_package(
    root: Path,
    commit: str,
    source_date_epoch: int,
    *,
    version: str = "1.0.0",
    data_schema: int = 1,
) -> dict[str, object]:
    root.mkdir(parents=True, exist_ok=True)
    payload = {
        name: (f"synthetic setup fixture: {name}\0v1").encode("utf-8")
        for name in PAYLOAD_PATHS
    }
    file_records = [
        {"path": name, "bytes": len(payload[name]), "sha256": sha256(payload[name])}
        for name in PAYLOAD_PATHS
    ]
    manifest = {
        "schema": "baxy-product-build-v4",
        "product": "BAXY",
        "version": version,
        "data_schema": data_schema,
        "configuration": "Release",
        "runtime": "win-x64",
        "target_framework": "net10.0-windows10.0.19041.0",
        "authenticity": "not_provided",
        "source": {
            "commit": commit,
            "dirty": False,
            "provenance": "git_head_snapshot",
            "source_date_epoch": source_date_epoch,
        },
        "toolchain": {"dotnet_sdk": "10.0.100", "powershell": "5.1.26100.1"},
        "deployment": {
            "app": "self_contained_single_file",
            "native_libraries": "adjacent_no_self_extraction",
            "core": "native_aot_self_contained",
            "symbols": "excluded_from_user_payload",
        },
        "file_count": len(file_records),
        "total_bytes": sum(record["bytes"] for record in file_records),
        "files": file_records,
    }
    manifest_bytes = json.dumps(manifest, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    checksum_entries = dict(payload)
    checksum_entries["build-manifest.json"] = manifest_bytes
    checksum_bytes = "".join(
        f"{sha256(checksum_entries[name])}  {name}\n" for name in CHECKSUM_PATHS
    ).encode("utf-8")
    zip_entries = dict(checksum_entries)
    zip_entries["SHA256SUMS"] = checksum_bytes

    package_name = f"BAXY-{version}-{commit[:12]}-win-x64.zip"
    package = root / package_name
    write_canonical_stored_zip(package, zip_entries, source_date_epoch)
    package_bytes = package.read_bytes()
    package_sha256 = sha256(package_bytes)
    sidecar = package.with_name(package.name + ".sha256")
    sidecar.write_text(f"{package_sha256}  {package.name}\n", encoding="utf-8", newline="")

    content_material = bytearray()
    for name in sorted(zip_entries):
        content_material.extend(name.encode("utf-8"))
        content_material.append(0)
        content_material.extend(str(len(zip_entries[name])).encode("ascii"))
        content_material.append(0)
        content_material.extend(sha256(zip_entries[name]).encode("ascii"))
        content_material.append(0x0A)
    return {
        "path": package,
        "sidecar": sidecar,
        "name": package_name,
        "sha256": package_sha256,
        "bytes": len(package_bytes),
        "manifest_sha256": sha256(manifest_bytes),
        "content_id": sha256(bytes(content_material)),
        "version": version,
        "data_schema": data_schema,
        "commit": commit,
        "source_date_epoch": source_date_epoch,
    }


@unittest.skipUnless(POWERSHELL and shutil.which("git"), "PowerShell 5.1 and Git are required")
class BuildSetupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="baxy-build-setup-test-")
        self.base = Path(self.temporary.name)
        self.repo = self.base / "repo"
        self.repo.mkdir()
        (self.repo / "scripts").mkdir()
        (self.repo / "src" / "Baxy.Setup").mkdir(parents=True)
        for name in (
            "build_layout.ps1",
            "build_setup.ps1",
            "path_safety.ps1",
            "product_build_common.ps1",
        ):
            shutil.copy2(ROOT / "scripts" / name, self.repo / "scripts" / name)
        shutil.copy2(
            ROOT / "Directory.Build.props",
            self.repo / "Directory.Build.props",
        )
        (self.repo / "src" / "Baxy.Setup" / "Baxy.Setup.csproj").write_text(
            "<Project Sdk=\"Microsoft.NET.Sdk\"></Project>\n", encoding="utf-8", newline=""
        )
        (self.repo / ".gitignore").write_text(
            "/artifacts/product/build/\n/artifacts/setup/build/\n/artifacts/setup/runtime/\n",
            encoding="utf-8",
            newline="",
        )
        self.git("init", "-q")
        self.git("config", "user.email", "setup-tests@example.invalid")
        self.git("config", "user.name", "BAXY Setup Tests")
        self.git("config", "core.autocrlf", "false")
        self.git("add", ".")
        commit_env = os.environ.copy()
        commit_env["GIT_AUTHOR_DATE"] = "2023-11-14T22:13:20+00:00"
        commit_env["GIT_COMMITTER_DATE"] = commit_env["GIT_AUTHOR_DATE"]
        subprocess.run(
            ["git", "commit", "-q", "-m", "fixture"],
            cwd=self.repo,
            env=commit_env,
            check=True,
        )
        self.commit = self.git("rev-parse", "HEAD").strip()
        self.epoch = int(self.git("show", "-s", "--format=%ct", "HEAD").strip())
        self.package_root = self.repo / "artifacts" / "product" / "build" / "input"
        self.output_root = self.repo / "artifacts" / "setup" / "build" / "output"
        self.other_cwd = self.base / "caller-cwd"
        self.other_cwd.mkdir()
        self.fake_log = self.base / "fake-dotnet.jsonl"
        self.attestation_capture = self.base / "captured-attestation.json"
        self.fake_bin = self.base / "fake-bin"
        self.fake_bin.mkdir()
        helper = self.base / "fake_dotnet.py"
        helper.write_text(
            textwrap.dedent(
                """
                import json
                import os
                from pathlib import Path
                import shutil
                import sys

                arguments = sys.argv[1:]
                with Path(os.environ["BAXY_FAKE_DOTNET_LOG"]).open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(arguments) + "\\n")
                if arguments == ["--version"]:
                    print("10.0.100")
                if arguments and arguments[0] == "publish":
                    prefix = "-p:BaxyEmbeddedPackageAttestation="
                    match = next((item[len(prefix):] for item in arguments if item.startswith(prefix)), None)
                    if match:
                        shutil.copyfile(match, os.environ["BAXY_ATTESTATION_CAPTURE"])
                raise SystemExit(0)
                """
            ).lstrip(),
            encoding="utf-8",
            newline="",
        )
        wrapper = self.fake_bin / "dotnet.cmd"
        wrapper.write_text(
            f'@echo off\r\n"{sys.executable}" "{helper}" %*\r\nexit /b %ERRORLEVEL%\r\n',
            encoding="ascii",
            newline="",
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def git(self, *arguments: str) -> str:
        return subprocess.run(
            ["git", *arguments],
            cwd=self.repo,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=True,
        ).stdout

    def run_build(self, timeout: int = 60) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment["PATH"] = str(self.fake_bin) + os.pathsep + environment.get("PATH", "")
        environment["BAXY_FAKE_DOTNET_LOG"] = str(self.fake_log)
        environment["BAXY_ATTESTATION_CAPTURE"] = str(self.attestation_capture)
        return subprocess.run(
            [
                POWERSHELL,
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(self.repo / "scripts" / "build_setup.ps1"),
                "-PackageRoot",
                str(self.package_root),
                "-OutputRoot",
                str(self.output_root),
            ],
            cwd=self.other_cwd,
            env=environment,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout,
            check=False,
        )

    def rewrite_sidecar(self, package: Path) -> None:
        package_hash = sha256(package.read_bytes())
        package.with_name(package.name + ".sha256").write_text(
            f"{package_hash}  {package.name}\n", encoding="utf-8", newline=""
        )

    def test_dirty_worktree_is_rejected_before_package_or_dotnet(self) -> None:
        (self.repo / "dirty.txt").write_text("dirty", encoding="utf-8")
        result = self.run_build()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("worktree is dirty", result.stderr.lower())
        self.assertFalse(self.fake_log.exists())

    def test_package_root_must_be_exact_zip_and_sidecar(self) -> None:
        create_product_package(self.package_root, self.commit, self.epoch)
        (self.package_root / "unexpected.txt").write_text("no", encoding="utf-8")
        result = self.run_build()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("exactly one zip and its sidecar", result.stderr.lower())
        self.assertFalse(self.fake_log.exists())

    def test_sidecar_tamper_is_rejected_independently(self) -> None:
        fixture = create_product_package(self.package_root, self.commit, self.epoch)
        Path(fixture["sidecar"]).write_text(
            f"{'0' * 64}  {fixture['name']}\n", encoding="utf-8", newline=""
        )
        result = self.run_build()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("sidecar", result.stderr.lower())
        self.assertFalse(self.fake_log.exists())

    def test_oversized_sidecar_is_rejected_before_unbounded_read_or_dotnet(self) -> None:
        fixture = create_product_package(self.package_root, self.commit, self.epoch)
        Path(fixture["sidecar"]).write_bytes(b"x" * (1024 * 1024))
        result = self.run_build()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("sidecar byte length", result.stderr.lower())
        self.assertFalse(self.fake_log.exists())

    def test_hardlinked_product_input_is_rejected_before_dotnet(self) -> None:
        fixture = create_product_package(self.package_root, self.commit, self.epoch)
        external = self.base / "external-package-link.zip"
        try:
            os.link(Path(fixture["path"]), external)
        except OSError as error:
            self.skipTest(f"The test filesystem cannot create hardlinks: {error}")
        result = self.run_build()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("hard-linked", result.stderr.lower())
        self.assertIn("setup delivery file", result.stderr.lower())
        self.assertFalse(self.fake_log.exists())
        self.assertEqual(external.read_bytes(), Path(fixture["path"]).read_bytes())

    def test_semantic_version_length_is_bounded_before_dotnet(self) -> None:
        version = "1.0.0+" + ("a" * 123)
        create_product_package(self.package_root, self.commit, self.epoch, version=version)
        result = self.run_build()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid semantic version", result.stderr.lower())
        self.assertFalse(self.fake_log.exists())

    def test_unsupported_data_schema_is_rejected_before_dotnet(self) -> None:
        create_product_package(
            self.package_root,
            self.commit,
            self.epoch,
            data_schema=2,
        )
        result = self.run_build()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unsupported data schema", result.stderr.lower())
        self.assertFalse(self.fake_log.exists())

    def test_existing_output_root_is_preserved_and_rejected_before_dotnet(self) -> None:
        create_product_package(self.package_root, self.commit, self.epoch)
        self.output_root.mkdir(parents=True)
        sentinel = self.output_root / "keep.txt"
        sentinel.write_text("existing-valid-output", encoding="utf-8", newline="")
        result = self.run_build()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("outputroot must be new", result.stderr.lower())
        self.assertFalse(self.fake_log.exists())
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "existing-valid-output")

    def test_reparse_point_in_output_ancestor_is_rejected_before_dotnet(self) -> None:
        create_product_package(self.package_root, self.commit, self.epoch)
        external = self.base / "external-output"
        external.mkdir()
        sentinel = external / "keep.txt"
        sentinel.write_text("outside", encoding="utf-8", newline="")
        setup_build = self.repo / "artifacts" / "setup" / "build"
        setup_build.mkdir(parents=True)
        junction = setup_build / "redirect"
        created = subprocess.run(
            ["cmd.exe", "/d", "/c", "mklink", "/J", str(junction), str(external)],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
        )
        if created.returncode != 0:
            self.skipTest(f"The test environment cannot create a junction: {created.stderr}")
        self.output_root = junction / "output"
        result = self.run_build()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("reparse point", result.stderr.lower())
        self.assertFalse(self.fake_log.exists())
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "outside")

    def test_noncanonical_stored_zip_metadata_is_rejected(self) -> None:
        fixture = create_product_package(self.package_root, self.commit, self.epoch)
        package = Path(fixture["path"])
        archive = bytearray(package.read_bytes())
        central = archive.find(b"PK\x01\x02")
        self.assertGreaterEqual(central, 0)
        archive[central + 4] = 21
        package.write_bytes(archive)
        self.rewrite_sidecar(package)
        result = self.run_build()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("non-canonical", result.stderr.lower())
        self.assertFalse(self.fake_log.exists())

    def test_stored_zip_crc_must_match_entry_bytes(self) -> None:
        fixture = create_product_package(self.package_root, self.commit, self.epoch)
        package = Path(fixture["path"])
        archive = bytearray(package.read_bytes())
        central = archive.find(b"PK\x01\x02")
        self.assertGreaterEqual(central, 0)
        original_crc = struct.unpack_from("<I", archive, central + 16)[0]
        replacement_crc = original_crc ^ 0x01010101
        struct.pack_into("<I", archive, central + 16, replacement_crc)
        stored_size = struct.unpack_from("<I", archive, central + 20)[0]
        name_length = struct.unpack_from("<H", archive, 26)[0]
        extra_length = struct.unpack_from("<H", archive, 28)[0]
        descriptor = 30 + name_length + extra_length + stored_size
        self.assertEqual(archive[descriptor : descriptor + 4], b"PK\x07\x08")
        struct.pack_into("<I", archive, descriptor + 4, replacement_crc)
        package.write_bytes(archive)
        self.rewrite_sidecar(package)
        result = self.run_build()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("stored zip crc32", result.stderr.lower())
        self.assertIn("entry bytes", result.stderr.lower())
        self.assertFalse(self.fake_log.exists())

    def test_package_commit_must_equal_clean_head(self) -> None:
        create_product_package(self.package_root, "0" * 40, self.epoch)
        result = self.run_build()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("commit does not match", result.stderr.lower())
        self.assertFalse(self.fake_log.exists())

    def test_source_date_epoch_must_equal_head_commit_time(self) -> None:
        create_product_package(self.package_root, self.commit, self.epoch + 2)
        result = self.run_build()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("source_date_epoch does not match", result.stderr.lower())
        self.assertFalse(self.fake_log.exists())

    def test_valid_package_reaches_isolated_snapshot_publish_and_canonical_attestation(self) -> None:
        fixture = create_product_package(self.package_root, self.commit, self.epoch)
        result = self.run_build()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("publish output directory is missing", result.stderr.lower())

        invocations = [json.loads(line) for line in self.fake_log.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(invocations[0], ["--version"])
        restore = next(arguments for arguments in invocations if arguments and arguments[0] == "restore")
        publish = next(arguments for arguments in invocations if arguments and arguments[0] == "publish")
        self.assertIn("--artifacts-path", restore)
        self.assertIn("--artifacts-path", publish)
        self.assertIn("-c", publish)
        self.assertIn("Release", publish)
        self.assertIn("-r", publish)
        self.assertIn("win-x64", publish)
        self.assertIn("--self-contained", publish)
        self.assertIn("true", publish)
        self.assertIn("-p:PublishAot=true", publish)
        self.assertIn("-p:StripSymbols=true", publish)
        self.assertIn("-p:DebugType=none", publish)
        self.assertIn("-p:NativeDebugSymbols=false", publish)
        path_map = next(item for item in publish if item.startswith("-p:PathMap="))
        self.assertIn("=/_/baxy%2C", path_map)
        self.assertNotIn(",", path_map)
        self.assertIn("=/_/baxy-setup-work", path_map)
        self.assertIn(f"-p:SourceRevisionId={self.commit}", publish)
        package_argument = next(
            item for item in publish if item.startswith("-p:BaxyEmbeddedPackage=")
        )
        attestation_argument = next(
            item for item in publish if item.startswith("-p:BaxyEmbeddedPackageAttestation=")
        )
        embedded_package_path = Path(package_argument.split("=", 1)[1])
        attestation_path = Path(attestation_argument.split("=", 1)[1])
        self.assertEqual(embedded_package_path.parent.name, "input")
        self.assertEqual(attestation_path.parent, embedded_package_path.parent.parent)
        self.assertFalse(any("BaxyDevelopmentPayloadlessPublish" in item for item in publish))
        self.assertIn(".setup-source-snapshot-", publish[1].lower())
        self.assertNotIn(str(self.repo / "src"), publish[1])

        expected_attestation = {
            "schema": "baxy-setup-embedded-package-v2",
            "version": fixture["version"],
            "data_schema": fixture["data_schema"],
            "package_sha256": fixture["sha256"],
            "package_bytes": fixture["bytes"],
            "manifest_sha256": fixture["manifest_sha256"],
            "content_id": fixture["content_id"],
            "source_date_epoch": fixture["source_date_epoch"],
            "commit": fixture["commit"],
        }
        expected_bytes = (
            json.dumps(expected_attestation, separators=(",", ":"), ensure_ascii=False) + "\n"
        ).encode("utf-8")
        self.assertEqual(self.attestation_capture.read_bytes(), expected_bytes)

        worktrees = self.git("worktree", "list", "--porcelain")
        self.assertEqual(worktrees.count("worktree "), 1)
        setup_build = self.repo / "artifacts" / "setup" / "build"
        leftovers = [path.name for path in setup_build.iterdir()] if setup_build.exists() else []
        self.assertEqual(leftovers, [])

    def test_script_keeps_physical_delivery_and_exact_output_gates_explicit(self) -> None:
        script = BUILD_SETUP.read_text(encoding="utf-8")
        self.assertIn("New-BaxyHeadWorktreeSnapshot", script)
        self.assertIn("[BaxyZipStorageInspector]::AssertStored", script)
        self.assertIn("baxy-product-build-v4", script)
        self.assertIn("BaxyEmbeddedPackageAttestation", script)
        self.assertIn("--verify-embedded", script)
        self.assertIn("baxy-setup-embedded-verification-v2", script)
        self.assertIn("BaxySetupPeInspector", script)
        self.assertIn("MachineAmd64 = 0x8664", script)
        self.assertIn("WindowsGuiSubsystem = 2", script)
        self.assertIn("ClrDirectoryIndex = 14", script)
        self.assertIn("CodeView/PDB", script)
        self.assertIn("forbidden COFF symbol table", script)
        self.assertIn("Get-AuthenticodeSignature", script)
        self.assertIn("NotSigned", script)
        self.assertIn("Assert-BaxyTreeHasNoHardLinks", script)
        self.assertIn("Move-BaxyNewDirectoryAtomically", script)
        self.assertIn("OutputRoot must be new", script)
        self.assertIn("Baxy.Setup.exe", script)
        self.assertIn("setup-manifest.json", script)
        self.assertIn("SHA256SUMS", script)
        self.assertGreaterEqual(script.count("Assert-BaxySetupOutput -Root $OutputRoot"), 2)

    def test_setup_runtime_contract_matches_the_packaging_contract(self) -> None:
        self.assertEqual(package_contract_paths("PayloadPaths"), PAYLOAD_PATHS)
        self.assertEqual(package_contract_paths("ChecksumPaths"), CHECKSUM_PATHS)
        self.assertEqual(package_contract_paths("ZipPaths"), ZIP_PATHS)

    def test_setup_generated_roots_are_ignored(self) -> None:
        ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("/artifacts/setup/build/", ignore)
        self.assertIn("/artifacts/setup/runtime/", ignore)


if __name__ == "__main__":
    unittest.main()
