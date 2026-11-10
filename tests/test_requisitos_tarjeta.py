"""Los requisitos que se publican dicen lo que el instalador hace sin tarjeta gráfica (INS-12).

Sin una tarjeta NVIDIA, AMD o Intel el instalador no instala (`MainWindow.WarningScreen`, y 1633 con `--quiet`) y la
App no arranca y lo dice (`no_supported_gpu`): le pasa a una máquina virtual y a un PC con el adaptador básico de
Microsoft. En Steam e itch.io no hay instalador nuestro: allí sólo lo dice la App.
Quien lee los requisitos lo tiene que saber antes de bajar o comprar.
"""
from __future__ import annotations

from pathlib import Path

import pytest

DOCS = Path(__file__).resolve().parents[1] / "documentacion"


def _fila(tabla: str, nombre: str) -> str:
    filas = [linea for linea in tabla.splitlines() if linea.startswith(f"| {nombre} |")]
    assert len(filas) == 1, filas
    return filas[0]


def test_los_requisitos_de_steam_dicen_que_sin_tarjeta_no_se_instala_ni_arranca() -> None:
    texto = (DOCS / "STEAM_PUBLICACION.md").read_text(encoding="utf-8")
    requisitos = texto[texto.index("**Requisitos del sistema para la página**") :]

    assert "BAXY no arranca" in _fila(requisitos, "GPU")


@pytest.mark.parametrize("frase", ["Sin tarjeta dedicada no funciona.", "Without a dedicated card it doesn't run."])
def test_la_pagina_de_itch_dice_que_sin_tarjeta_no_funciona(frase: str) -> None:
    pagina = (DOCS / "itchio" / "PAGINA.md").read_text(encoding="utf-8")

    assert frase in " ".join(pagina.split())
