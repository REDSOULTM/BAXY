"""El contacto que BAXY declara a los servicios públicos es la dirección vigente de su repositorio (LEG-09).

MET Norway, Wikimedia y Photon piden un contacto válido en el User-Agent; BAXY da la dirección de su repositorio
(`ProductIdentity.Contact`). Esa dirección está escrita en más sitios (de dónde bajan las versiones, la privacidad, la
entrada de «Aplicaciones instaladas», el aviso de terceros): si el repositorio cambia de nombre, todos cambian a la vez.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_github_release  # noqa: E402

REPOSITORIO = "https://github.com/" + build_github_release.GITHUB_REPOSITORY


def _lee(*partes: str) -> str:
    return ROOT.joinpath(*partes).read_text(encoding="utf-8")


def _contacto() -> str:
    declarado = re.findall(r'internal const string Contact = "([^"]+)";',
                           _lee("src", "Baxy.Providers.Windows", "External", "ProductIdentity.cs"))
    assert len(declarado) == 1, declarado
    return declarado[0]


def test_el_contacto_es_el_repositorio_del_que_bajan_las_versiones() -> None:
    assert _contacto() == REPOSITORIO


def test_la_entrada_de_aplicaciones_instaladas_da_la_misma_direccion() -> None:
    assert f'key.SetValue("URLInfoAbout", "{_contacto()}");' in _lee("src", "Baxy.Installer", "WindowsIntegration.cs")


def test_la_privacidad_da_la_misma_direccion_en_los_dos_idiomas() -> None:
    assert _lee("licenses", "PRIVACIDAD.md").count(f"<{_contacto()}>") == 2


def test_el_aviso_de_terceros_dice_el_user_agent_que_se_envia() -> None:
    avisos = _lee("THIRD_PARTY_NOTICES.md")

    assert f"User-Agent `BAXY/<versión> ({_contacto()})`" in avisos
    assert len(re.findall(r"User-Agent `BAXY/<versión> \(", avisos)) == 1
