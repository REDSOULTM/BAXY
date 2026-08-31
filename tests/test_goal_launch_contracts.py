from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPRINTS = ROOT / "documentacion" / "sprints"
ORDER = SPRINTS / "00_ORDEN_DESDE_09_5.md"
REFERENCE_DOCS = {
    "09.5_HERENCIA_TOTAL.md",
    "09.5_PROTOCOLO_GROK46.md",
    "10_USO_DIARIO.md",
    "10_PROTOCOLO_GROK46.md",
    "11_VALIDACION.md",
    "11_PROTOCOLO_GROK46.md",
}
FORBIDDEN_RELAUNCHES = (
    "una vez por lote",
    "toma **sólo el primer lote",
    "toma sólo el primer lote",
    "repite **el mismo fichero",
    "repite el mismo goal",
    "vuelve a ese goal",
    "en una sesión nueva y repite",
    "incluidos slices nuevos",
)


def executable_prompts() -> list[str]:
    text = ORDER.read_text(encoding="utf-8")
    linked = re.findall(r"\(((?:09\.5|10|11)[^)]+\.md)\)", text)
    return [name for name in linked if name not in REFERENCE_DOCS]


def test_order_is_complete_unique_and_chained() -> None:
    prompts = executable_prompts()
    assert len(prompts) == 50
    assert len(set(prompts)) == len(prompts)

    for index, name in enumerate(prompts):
        path = SPRINTS / name
        assert path.is_file(), name
        text = path.read_text(encoding="utf-8")
        assert text.startswith("# Goal"), name
        assert "## Objetivo único" in text, name
        assert "## Criterios de cierre" in text, name
        if index + 1 < len(prompts):
            assert prompts[index + 1] in text, f"{name} -> {prompts[index + 1]}"


def test_no_prompt_requires_a_human_relaunch() -> None:
    paths = [
        path
        for path in SPRINTS.iterdir()
        if path.is_file() and re.match(r"^(09\.5|10|11)", path.name)
    ]
    for path in paths:
        folded = path.read_text(encoding="utf-8").casefold()
        for forbidden in FORBIDDEN_RELAUNCHES:
            assert forbidden.casefold() not in folded, f"{path.name}: {forbidden}"

    for name in (
        "09.5_PROTOCOLO_GROK46.md",
        "10_PROTOCOLO_GROK46.md",
        "11_PROTOCOLO_GROK46.md",
    ):
        text = (SPRINTS / name).read_text(encoding="utf-8")
        assert re.search(r"una\s+sola\s+vez", text, re.IGNORECASE), name


def test_migration_preserves_finished_goal095_work() -> None:
    code_campaign = (SPRINTS / "09.5.3_AUDITAR_CODIGO_LOTE.md").read_text(
        encoding="utf-8"
    )
    assert "09.5.1" in code_campaign
    assert "code_tests-001-carter" in code_campaign
    assert "code_tests-002-carter-carter_legacy_Carter_v2" in code_campaign
    assert "Las dos" in code_campaign and "cuentan como progreso" in code_campaign


def test_final_prompt_declares_product_ready() -> None:
    final_prompt = (SPRINTS / "11.16_FULL_Y_CIERRE.md").read_text(encoding="utf-8")
    assert re.search(r"BAXY está\s+listo para uso diario", final_prompt)
