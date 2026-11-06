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
    "GPL-3.0.txt": "GNU GENERAL PUBLIC LICENSE",
    "LGPL-2.1.txt": "GNU LESSER GENERAL PUBLIC LICENSE",
    "Inter-OFL.txt": "The Inter Project Authors",
    "JetBrainsMono-OFL.txt": "The JetBrains Mono Project Authors",
    "ChakraPetch-OFL.txt": "The Chakra Petch Project Authors",
    "dotnet-LICENSE.txt": ".NET Foundation",
    "WebView2-LICENSE.txt": "Microsoft Corporation",
    "WebView2-NOTICE.txt": "NOTICES",
    "Intel-Simplified-Software-License.txt": "Intel Simplified Software License",
    "Intel-EULA-Developer-Tools.txt": "Intel End User License Agreement for Developer Tools",
    "Intel-oneMKL-third-party-programs.txt": "Math Kernel Library (oneMKL) Third Party Programs File",
    "Intel-OpenMP-third-party-programs.txt": "OpenMP",
    "piper-phonemize-LICENSE.txt": "Michael Hansen",
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
    on_disk = {path.name for path in LICENSES.iterdir()} - {"README.md", "ATRIBUCIONES_MODELOS.md", "FUENTES_GPL.md"}
    assert listed == on_disk
    assert set(TEXTS) <= listed


def test_the_gpl_source_table_names_a_fixed_commit() -> None:
    sources = (LICENSES / "FUENTES_GPL.md").read_text(encoding="utf-8")
    assert "ed530aa113046142eb5115cf2fc9157854d0ffe1" in sources
    assert "142807252687d81b40d6315f23470a1512a00de3" in sources
    assert "libquadmath" in sources
    assert "autocommand" in sources


def test_the_package_gets_the_licenses_folder() -> None:
    build = (LICENSES.parent / "scripts" / "build_steam.ps1").read_text(encoding="utf-8")
    assert "Join-Path $repo 'licenses\\*'" in build


def test_the_notices_say_the_package_carries_gpl_code() -> None:
    notices = (LICENSES.parent / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    assert "No hay dependencias GPL/LGPL/AGPL enlazadas ni distribuidas" not in notices
    assert "### 0. eSpeak NG dentro de sherpa-onnx: GPL-3.0-or-later" in notices
    assert "libquadmath (LGPL-2.1-or-later)" in notices
    assert "autocommand (LGPLv3)" in notices
