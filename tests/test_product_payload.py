"""The product build's reviewed payload (scripts/product_build_common.ps1) against what Baxy.App publishes: the App
takes every file of src/Baxy.FieldUi/dist (Baxy.App.csproj, Content Include="..\\Baxy.FieldUi\\dist\\**\\*"), so the
list the build checks the payload against must name each one, or build_product.ps1 refuses the product it just built
(calidad PC 2026-10-25: «Product payload must contain exactly 38 reviewed files.» once the interface shipped its icon,
backgrounds and clips beside index.html and assets/)."""
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "src" / "Baxy.FieldUi" / "dist"


def _payload_paths() -> list[str]:
    done = subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
         "[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false); "
         ". .\\scripts\\product_build_common.ps1; $BaxyProductPayloadPaths -join \"`n\""],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=True, timeout=120,
    )
    return done.stdout.split()


def test_the_payload_names_every_file_the_app_publishes_from_the_field_ui_build() -> None:
    published = {"FieldUi/" + path.relative_to(DIST).as_posix() for path in DIST.rglob("*") if path.is_file()}
    assert published - set(_payload_paths()) == set()


def test_the_payload_stays_in_ordinal_order_without_repeats() -> None:
    paths = _payload_paths()
    assert paths == sorted(set(paths))  # code-point order: StringComparer.Ordinal for these ASCII names


INSTALLER = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Microsoft Visual Studio" / "Installer"


def _vswhere_after_setup(path: str) -> list[str]:
    done = subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
         ". .\\scripts\\product_build_common.ps1; Use-BaxyVisualStudioInstallerPath; "
         "(Get-Command vswhere.exe -ErrorAction SilentlyContinue).Source; ($env:PATH -split ';').Count"],
        cwd=ROOT, capture_output=True, text=True, check=True, timeout=120,
        env={**os.environ, "PATH": path})
    return done.stdout.splitlines()


@pytest.mark.skipif(not (INSTALLER / "vswhere.exe").is_file(), reason="no Visual Studio Installer on this machine")
def test_the_native_link_finds_vswhere_without_it_on_the_path() -> None:
    # Calidad PC 2026-10-25: the NativeAOT link of baxy-core (and Baxy.Setup) runs VS's vcvars, which calls vswhere.exe
    # by name; the VS Installer never puts its folder on PATH, and build_product.ps1 failed where run_renew.cmd did not.
    path = ";".join(p for p in os.environ["PATH"].split(";") if "Visual Studio\\Installer" not in p)
    found, count = _vswhere_after_setup(path)
    assert Path(found) == INSTALLER / "vswhere.exe"
    assert int(count) == len(path.split(";")) + 1
    assert _vswhere_after_setup(path + ";" + str(INSTALLER))[1] == count  # already there: not added again
