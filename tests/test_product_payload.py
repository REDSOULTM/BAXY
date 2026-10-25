"""The product build's reviewed payload (scripts/product_build_common.ps1) against what Baxy.App publishes: the App
takes every file of src/Baxy.FieldUi/dist (Baxy.App.csproj, Content Include="..\\Baxy.FieldUi\\dist\\**\\*"), so the
list the build checks the payload against must name each one, or build_product.ps1 refuses the product it just built
(calidad PC 2026-10-25: «Product payload must contain exactly 38 reviewed files.» once the interface shipped its icon,
backgrounds and clips beside index.html and assets/)."""
import subprocess
from pathlib import Path

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
