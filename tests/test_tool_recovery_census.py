import ast
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _canonical_operation_families() -> set[str]:
    module = ast.parse((ROOT / "scripts" / "build_historical_corpus.py").read_text(encoding="utf-8"))
    for node in module.body:
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "OP_SPECS"
            and isinstance(node.value, ast.Dict)
        ):
            return {ast.literal_eval(key) for key in node.value.keys}
    raise AssertionError("OP_SPECS was not found")


def _table_operations(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return re.findall(r"^\| `([a-z][a-z0-9]*(?:\.[a-z][a-z0-9]*)+)` \|", text, re.MULTILINE)


def test_archaeology_inventory_and_frozen_census_cover_each_family_once():
    expected = _canonical_operation_families()
    inventory = _table_operations(ROOT / "documentacion" / "22_INVENTARIO_ARQUEOLOGICO_CARTER_BAXY.md")
    census = _table_operations(ROOT / "documentacion" / "23_CENSO_FUNCIONAL_TOOLS_CONGELADO.md")

    assert len(expected) == 43
    assert len(inventory) == len(set(inventory)) == 43
    assert len(census) == len(set(census)) == 43
    assert set(inventory) == expected
    assert set(census) == expected


def test_fable_v2_boundary_forbids_planning_inside_tools():
    boundary = (ROOT / "contexto" / "04_arquitectura" / "FRONTERA_CODEX_FABLE_V2.md").read_text(
        encoding="utf-8"
    )
    for required in (
        "La mente selecciona",
        "El planner actual",
        "Ninguna tool interpreta la frase original",
        "solo hay éxito si el verifier",
        "resultados estructurados",
    ):
        assert required in boundary
