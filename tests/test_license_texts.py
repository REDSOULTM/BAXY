"""Los textos de licencia que el paquete debe entregar están en licenses/ y son los de cada licencia (encargo LIC1)."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

LICENSES = Path(__file__).resolve().parents[1] / "licenses"
# Una frase que sólo está en el texto completo: un fichero truncado o equivocado no pasa.
TEXTS = {
    "Apache-2.0.txt": "TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION",
    "Qwen3.5-4B-LICENSE.txt": "TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION",
    "CC-BY-4.0.txt": "Attribution 4.0 International Public License",
    "CC-BY-SA-4.0.txt": "Attribution-ShareAlike 4.0 International Public License",
    "OpenRAIL-M-Supertonic-3.txt": "Attachment A",
    "Inter-OFL.txt": "The Inter Project Authors",
    "JetBrainsMono-OFL.txt": "The JetBrains Mono Project Authors",
    "ChakraPetch-OFL.txt": "The Chakra Petch Project Authors",
    "dotnet-LICENSE.txt": ".NET Foundation",
    "WebView2-LICENSE.txt": "Microsoft Corporation",
    "WebView2-NOTICE.txt": "NOTICES",
    "Python-Licenses-and-Acknowledgements.txt": "Licenses and Acknowledgements for Incorporated Software",
}


@pytest.mark.parametrize(("name", "phrase"), TEXTS.items())
def test_the_full_text_is_there(name: str, phrase: str) -> None:
    text = (LICENSES / name).read_text(encoding="utf-8", errors="replace")
    assert phrase in text


def test_openrail_keeps_its_thirteen_use_restrictions() -> None:
    text = (LICENSES / "OpenRAIL-M-Supertonic-3.txt").read_text(encoding="utf-8")
    attachment = text[text.rindex("Attachment A") :]
    assert re.findall(r"^\(([a-z])\)", attachment, re.MULTILINE) == list("abcdefghijklm")


def test_every_listed_file_exists_and_every_text_has_its_source() -> None:
    readme = (LICENSES / "README.md").read_text(encoding="utf-8")
    rows = re.findall(r"^\| `([^`]+)` \| .+ \| <(https://[^>]+)> \| `([0-9a-f]{64})` \|$", readme, re.MULTILINE)
    listed = {name for name, _, _ in rows}
    on_disk = {path.name for path in LICENSES.iterdir()} - {"README.md", "ATRIBUCIONES_MODELOS.md", "FUENTES.md", "CRATES_RUST.md",
                                                          "FUENTES_GPL.md"}  # the public repository's offer for its history
    assert listed == on_disk
    assert set(TEXTS) <= listed


def test_the_source_notice_names_a_fixed_commit_and_eigens_source() -> None:
    sources = (LICENSES / "FUENTES.md").read_text(encoding="utf-8")
    assert "142807252687d81b40d6315f23470a1512a00de3" in sources
    assert "eigen-5.0.1.tar.gz" in sources
    assert "e9c326dc8c05cd1e044c71f30f1b2e34a6161a3b6ecf445d56b53ff1669e3dec" in sources


def test_the_package_gets_the_licenses_folder() -> None:
    build = (LICENSES.parent / "scripts" / "build_steam.ps1").read_text(encoding="utf-8")
    assert "Join-Path $repo 'licenses\\*'" in build


def test_the_notices_say_what_left_and_what_stays() -> None:
    notices = (LICENSES.parent / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    assert "el barrido de los binarios de 1.3.0 no halló código GPL ni LGPL" in notices
    assert "### 0. Lo que se quitó en 1.3.0, y Eigen (MPL-2.0), que queda" in notices
    assert "1.2.0 y 1.2.1, ya distribuidas, siguen llevando eSpeak NG" in notices
    assert "releases/tag/fuentes-terceros" in notices
    assert "**Eigen, MPL-2.0:**" in notices


def test_the_rust_crates_file_lists_what_the_wheels_declare() -> None:
    crates = (LICENSES / "CRATES_RUST.md").read_text(encoding="utf-8")
    assert "Unicode-3.0" in crates
    assert "Zlib" in crates
    assert "`pydantic_core`" in crates
    assert "`jiter`" in crates


def test_numpys_notices_the_wheel_does_not_carry_are_here() -> None:
    assert "Redistribution" in (LICENSES / "pocketfft-LICENSE.md").read_text(encoding="utf-8")
    msun = (LICENSES / "numpy-msun-NOTICE.txt").read_text(encoding="utf-8")
    assert "David Schultz" in msun
    assert "Sun Microsystems" in msun


def test_no_notice_keeps_a_file_the_package_no_longer_has() -> None:
    readme = (LICENSES / "README.md").read_text(encoding="utf-8")
    assert "sherpa-onnx-c-api" not in readme
    assert "FUENTES_GPL" not in readme
    assert "FUENTES_GPL" not in (LICENSES.parent / "scripts" / "build_steam.ps1").read_text(encoding="utf-8")
