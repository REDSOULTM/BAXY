"""INS1 (PKG-1, PKG-2, PKG-3, LEG-02): what the package folder may not carry, what each store's folder has to, and the
commit the App in it was built at.

PKG-1: a run of the folder leaves the App's hash cache and Python's bytecode in it, with the build machine's paths inside;
Steam's upload leaves them out, GitHub's archives and itch.io's folder took them. PKG-2: the App is copied from a build made
before and the mind is taken from HEAD, and nothing compared them. PKG-3 and LEG-02: itch.io's manifest and the agreement
its buyer reads were copied by hand, and no check asked for them."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPOSITORY / "scripts"))

import check_package_licenses as check  # noqa: E402
import package_channel as channel  # noqa: E402

LOCK = REPOSITORY / "pylock.runtime-win-x64.toml"
BUILD = REPOSITORY / "scripts" / "build_steam.ps1"
ITCH = REPOSITORY / "documentacion" / "itchio"
COMMIT = "0123456789abcdef0123456789abcdef01234567"
OTHER = "fedcba9876543210fedcba9876543210fedcba98"


def _code_lines(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if not line.strip().startswith("#")]


def _depot(root: Path, published: str | None) -> Path:
    """A folder with the licenses of the repository, the App an action may start and the channel build_steam.ps1 writes."""
    (root / "licenses").mkdir(parents=True)
    for text in (REPOSITORY / "licenses").iterdir():
        (root / "licenses" / text.name).write_bytes(text.read_bytes())
    (root / "app").mkdir()
    (root / "app" / "Baxy.exe").write_bytes(b"app")
    if published is not None:
        (root / "distribution.json").write_text(
            json.dumps({"schema": "baxy.distribution.v1", "channel": published}), encoding="utf-8")
    return root


def _checked(depot: Path) -> list[str]:
    return check.findings(depot, LOCK) + check.missing_texts(depot) + check.run_leftovers(depot) + check.missing_channel_files(depot)


# PKG-1


@pytest.mark.parametrize(
    "left",
    [
        "mind-runtime-v1.hash-cache.json",
        "mind/baxy_mind/__pycache__/gpu.cpython-312.pyc",
        "python/Lib/site-packages/numpy/__pycache__/version.cpython-312.pyc",
    ],
)
def test_what_a_run_of_the_folder_leaves_is_seen(tmp_path: Path, left: str) -> None:
    depot = _depot(tmp_path, "steam")
    channel.write(depot, "steam")
    assert _checked(depot) == []
    (depot / left).parent.mkdir(parents=True, exist_ok=True)
    (depot / left).write_bytes(b"C:\\Users\\someone\\build")

    found = _checked(depot)

    assert len(found) == 1 and found[0].startswith(left + ": "), found


def test_the_registration_and_the_sources_are_no_leftovers(tmp_path: Path) -> None:
    for name in ("mind-runtime-v1.json", "mind/baxy_mind/gpu.py", "app/mind-runtime-v1.hash-cache.txt"):
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_bytes(b"x")

    assert check.run_leftovers(tmp_path) == []


def test_the_check_and_steams_upload_leave_out_the_same_files() -> None:
    upload = (REPOSITORY / "scripts" / "steam" / "app_build.vdf").read_text(encoding="utf-8")
    assert re.findall(r'^\s*"FileExclusion"\s+"([^"]+)"', upload, re.MULTILINE) == list(check.RUN_LEFTOVERS)


def test_the_check_fails_on_a_package_with_what_a_run_left(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    depot = _depot(tmp_path, None)
    (depot / "mind-runtime-v1.hash-cache.json").write_bytes(b"{}")
    monkeypatch.setattr(sys, "argv", ["check_package_licenses.py", "--depot", str(depot), "--lock", str(LOCK)])

    assert check.main() == 1
    assert "mind-runtime-v1.hash-cache.json: " in capsys.readouterr().err


# PKG-3 and LEG-02


def test_itchs_folder_gets_its_manifest_and_the_agreement_in_both_languages() -> None:
    files = channel.files("itch")

    assert sorted(files) == [".itch.toml", "licenses/BAXY-licencia-es.txt", "licenses/BAXY-license-en.txt"]
    assert files[".itch.toml"] == (ITCH / "itch.toml").read_bytes()


@pytest.mark.parametrize(
    ("name", "first", "heading"),
    [
        ("licenses/BAXY-licencia-es.txt", "BAXY: acuerdo de licencia", "## Español (`BAXY-licencia-es.txt`)"),
        ("licenses/BAXY-license-en.txt", "BAXY: End User License Agreement", "## English (`BAXY-license-en.txt`)"),
    ],
)
def test_the_agreement_is_its_section_of_the_legal_document_without_the_markdown(name: str, first: str, heading: str) -> None:
    text = channel.files("itch")[name].decode("utf-8")
    document = (ITCH / "LEGAL.md").read_text(encoding="utf-8")
    section = document.split(heading + "\n", 1)[1].split("\n---\n", 1)[0].split("\n## ", 1)[0]

    assert text.splitlines()[0] == first
    assert text == section.strip("\n") + "\n"
    assert not [line for line in text.splitlines() if line.startswith("#") or line == "---"]
    # Whole: its eight sections, and the thirteen restrictions on the voice a buyer there accepts nowhere else.
    assert [line for line in text.splitlines() if re.match(r"\d+\. ", line)][-1].startswith("8. ")
    assert "itch.io" in text


def test_a_legal_document_that_lost_a_section_stops_the_build(tmp_path: Path) -> None:
    document = (ITCH / "LEGAL.md").read_text(encoding="utf-8")
    broken = tmp_path / "LEGAL.md"
    broken.write_text(document.replace("## English (`BAXY-license-en.txt`)", "## English"), encoding="utf-8", newline="")

    with pytest.raises(SystemExit, match="BAXY-license-en.txt"):
        channel.itch_agreements(broken)


def test_steams_folder_gets_the_script_steam_runs_on_uninstall_and_no_file_of_itchs() -> None:
    assert channel.files("steam") == {
        "installscript.vdf": (REPOSITORY / "scripts" / "steam" / "installscript.vdf").read_bytes()}


def test_writing_never_replaces_a_file_the_folder_already_has(tmp_path: Path) -> None:
    depot = _depot(tmp_path, "itch")
    (depot / ".itch.toml").write_bytes(b"someone's")

    with pytest.raises(SystemExit, match=".itch.toml"):
        channel.write(depot, "itch")
    assert (depot / ".itch.toml").read_bytes() == b"someone's"


def test_an_itch_folder_as_the_build_writes_it_passes_the_check(tmp_path: Path) -> None:
    depot = _depot(tmp_path, "itch")

    assert channel.write(depot, "itch") == [".itch.toml", "licenses/BAXY-licencia-es.txt", "licenses/BAXY-license-en.txt"]
    assert _checked(depot) == []


@pytest.mark.parametrize("name", [".itch.toml", "licenses/BAXY-licencia-es.txt", "licenses/BAXY-license-en.txt"])
def test_an_itch_folder_without_one_of_its_files_or_with_another_text_is_refused(tmp_path: Path, name: str) -> None:
    depot = _depot(tmp_path, "itch")
    channel.write(depot, "itch")
    (depot / name).unlink()

    assert check.missing_channel_files(depot) == [f"{name}: not in the package (channel itch)"]

    (depot / name).write_bytes(b"an older agreement")

    assert check.missing_channel_files(depot) == [f"{name}: differs from the repository's (channel itch)"]


def test_a_manifest_that_starts_a_file_the_folder_lacks_is_refused(tmp_path: Path) -> None:
    depot = _depot(tmp_path, "itch")
    channel.write(depot, "itch")
    (depot / "app" / "Baxy.exe").unlink()

    assert check.missing_channel_files(depot) == [".itch.toml: its action «play» starts app/Baxy.exe, which the package lacks"]


def test_a_steam_folder_without_its_uninstall_script_is_refused_and_needs_no_agreement_file(tmp_path: Path) -> None:
    depot = _depot(tmp_path, "steam")

    assert check.missing_channel_files(depot) == ["installscript.vdf: not in the package (channel steam)"]

    channel.write(depot, "steam")

    assert check.missing_channel_files(depot) == []


def test_the_check_fails_on_an_itch_folder_without_the_agreement(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    depot = _depot(tmp_path, "itch")
    monkeypatch.setattr(sys, "argv", ["check_package_licenses.py", "--depot", str(depot), "--lock", str(LOCK)])

    assert check.main() == 1
    assert "licenses/BAXY-licencia-es.txt: not in the package (channel itch)" in capsys.readouterr().err


def test_the_build_writes_the_channels_files_with_the_packages_python_before_it_checks_them() -> None:
    lines = _code_lines(BUILD)
    write = next(index for index, line in enumerate(lines) if r"'scripts\package_channel.py'" in line and "'--channel', $Channel" in line)
    assert lines[write].startswith("'-B', '-X', 'utf8', ")
    assert write < next(index for index, line in enumerate(lines) if "check_package_licenses.py" in line)
    # One way in: no copy by hand of a file the check asks for.
    assert not [line for line in lines if line.startswith("Copy-Item") and ("installscript.vdf" in line or "itch.toml" in line)]


def test_the_package_python_finds_the_module_beside_the_check_although_it_is_isolated(tmp_path: Path) -> None:
    # The embedded interpreter reads its path from python312._pth alone: the script's folder is not in it. -I gives the same here.
    depot = _depot(tmp_path, "itch")
    done = subprocess.run(
        [sys.executable, "-I", "-B", "-X", "utf8", str(REPOSITORY / "scripts" / "check_package_licenses.py"),
         "--depot", str(depot), "--lock", str(LOCK)],
        capture_output=True, text=True, encoding="utf-8", timeout=120)

    assert done.returncode == 1
    assert "ModuleNotFoundError" not in done.stderr
    assert ".itch.toml: not in the package (channel itch)" in done.stderr


# PKG-2


def _commit_checks(cases: dict[str, tuple[str, str]]) -> dict[str, str]:
    """What Assert-BaxyAppCommit says of each (product version, commit): «ok» or its refusal."""
    script = "; ".join(
        f"try {{ Assert-BaxyAppCommit -ProductVersion '{version}' -Commit '{commit}'; $r['{name}'] = 'ok' }} "
        f"catch {{ $r['{name}'] = [string]$_.Exception.Message }}"
        for name, (version, commit) in cases.items())
    done = subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
         "[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false); . .\\scripts\\app_commit.ps1; $r = [ordered]@{}; "
         + script + "; $r | ConvertTo-Json -Compress"],
        cwd=REPOSITORY, capture_output=True, text=True, encoding="utf-8", check=True, timeout=120)
    return json.loads(done.stdout)


def test_the_app_of_another_commit_or_of_a_worktree_with_changes_is_not_packed() -> None:
    short = COMMIT[:12]
    said = _commit_checks({
        # As build_product.ps1 seals it and the .NET SDK completes it (measured on 1.1.1's Baxy.exe, 2026-11-09).
        "same": (f"1.3.2+{short}.{COMMIT}", COMMIT),
        "same_with_a_build_label": (f"1.3.2+rc1.sha.{short}.{COMMIT}", COMMIT),
        "other": (f"1.3.2+{OTHER[:12]}.{OTHER}", COMMIT),
        "dirty": (f"1.3.2+{short}.dirty.{COMMIT}", COMMIT),
        "unsealed": ("1.3.2", COMMIT),
        "empty": ("", COMMIT),
    })

    assert said["same"] == said["same_with_a_build_label"] == "ok"
    for refused in ("other", "dirty", "unsealed", "empty"):
        assert said[refused].startswith("steam_build_failed: "), said
    assert COMMIT in said["other"] and OTHER[:12] in said["other"]
    assert "changes" in said["dirty"]


def test_the_build_compares_the_apps_commit_with_the_minds_before_it_copies_anything() -> None:
    lines = _code_lines(BUILD)
    compare = lines.index(
        "Assert-BaxyAppCommit -ProductVersion ([Diagnostics.FileVersionInfo]::GetVersionInfo($app).ProductVersion) -Commit $head")
    assert lines.index(". (Join-Path $PSScriptRoot 'app_commit.ps1')") < compare
    assert compare < lines.index("New-Item -ItemType Directory -Path $Output | Out-Null")
    # The mind is archived at that same commit, by its name: a commit made while the build runs changes nothing.
    assert any('"${head}:src"' in line for line in lines)
    assert not any("'HEAD:src'" in line for line in lines)
