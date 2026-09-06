"""Sprint contracts: bounded context and installed acceptance after Goal 11."""

from __future__ import annotations

import re
from pathlib import Path

from scripts.goal095_09512_integrate import (
    EXECUTABLE_PROMPTS,
    GROK46_CONTRACT_MARK,
    RETIRED_PROMPTS,
    parse_orden_executable,
)

REPO = Path(__file__).resolve().parents[1]
SPRINTS = REPO / "documentacion" / "sprints"

CLOSED_GOAL10 = (
    "10.0_BASE_VERDE.md",
    "10.1_CORPUS_Y_COLA.md",
    "10.2_PRESENCIA_Y_RECURSOS.md",
    "10.2.5_RECURSOS_EN_REPOSO.md",
)
PENDING = tuple(name for name in EXECUTABLE_PROMPTS if name not in CLOSED_GOAL10)


def test_live_order_skips_human_batches_and_continues_at_10_7() -> None:
    order = parse_orden_executable(REPO)
    assert order == list(EXECUTABLE_PROMPTS)
    assert order[0:5] == [
        "10.0_BASE_VERDE.md",
        "10.1_CORPUS_Y_COLA.md",
        "10.2_PRESENCIA_Y_RECURSOS.md",
        "10.2.5_RECURSOS_EN_REPOSO.md",
        "10.7_CONVERSACION.md",
    ]
    assert not set(RETIRED_PROMPTS).intersection(order)
    handoff = (REPO / "artifacts" / "goal10" / "HANDOFF.md").read_text(
        encoding="utf-8"
    )
    assert "Siguiente prompt: `documentacion/sprints/10.7_CONVERSACION.md`" in handoff
    assert "`0/50` no es deuda" in handoff


def test_every_pending_goal_incorporates_the_shared_grok46_contract() -> None:
    assert len(PENDING) == 28
    required = (
        GROK46_CONTRACT_MARK,
        "## Contrato de goal",
        "[00_PROTOCOLO_EJECUCION.md](00_PROTOCOLO_EJECUCION.md)",
        "Identidad y AGENTS",
        "## Herencia 09.5",
        "## Contrato de sesión",
        "## Objetivo único",
        "## Criterios de cierre",
        "Grok 4.6",
        "## Tramos de ejecución",
    )
    for name in PENDING:
        text = (SPRINTS / name).read_text(encoding="utf-8")
        for item in required:
            assert item in text, f"{name} missing {item}"


def test_pending_prompts_preserve_goal_01_09_rules_and_prompt_shape() -> None:
    headings = (
        "## Contrato de goal",
        "## Herencia 09.5",
        "## Contrato de sesión",
        "## Tramos de ejecución",
        "## Objetivo único",
        "## Criterios de cierre",
    )
    laws = (
        "Hereda primero",
        "Nada de sobreingeniería",
        "lo que bloquea",
        "más ligero",
        "Arquitectura modular",
    )
    invariants = (
        "catálogo tipado",
        "Nada se afirma sin verificar",
        "Estados terminales honestos",
        "confirmación se liga a la invocación exacta",
        "Cero respuestas visibles fijas",
        "Local y privado",
    )
    forbidden_human_dependencies = (
        "pedidos espontáneos del dueño",
        "turnos reales del dueño",
        "esperando tus interacciones",
        "el dueño debe proporcionar",
        "pide al dueño que pruebe",
    )

    authority = (REPO / "AGENTS.md").read_text(encoding="utf-8").casefold()
    assert all(law.casefold() in authority for law in laws)
    assert all(item.casefold() in authority for item in invariants)
    protocol = (SPRINTS / "00_PROTOCOLO_EJECUCION.md").read_text(encoding="utf-8")
    assert "Lee AGENTS, Identidad" in protocol
    assert "60–100K" in protocol and "150K" in protocol
    assert "máximo 80 líneas" in protocol
    assert "Ningún rojo permite cierre" in protocol
    for name in PENDING:
        text = (SPRINTS / name).read_text(encoding="utf-8")
        assert text.count("grok46-goal-contract:begin") == 1, name
        assert text.count("grok46-goal-contract:end") == 1, name
        assert all(text.count(heading) == 1 for heading in headings), name
        assert [text.index(heading) for heading in headings] == sorted(
            text.index(heading) for heading in headings
        ), name
        assert "Identidad y AGENTS" in text, name
        assert "Grok 4.6 High" in text, name
        assert "500k" in text and "FALLO_DE_AMBIENTE" in text, name
        assert "aceptación reservada" in text, name
        assert not any(
            item.casefold() in text.casefold()
            for item in forbidden_human_dependencies
        ), name


def test_goal11_contract_uses_goal11_authority_and_cannot_redefer_debt() -> None:
    protocol = (SPRINTS / "00_PROTOCOLO_EJECUCION.md").read_text(encoding="utf-8")
    assert "Los aplazados de 11 se resuelven con evidencia" in protocol
    assert "diferidos tienen dueño en 12" in protocol
    for name in PENDING:
        if not name.startswith("11."):
            continue
        text = (SPRINTS / name).read_text(encoding="utf-8")
        common = text.split("grok46-goal-contract:begin", 1)[1].split(
            "grok46-goal-contract:end", 1
        )[0]
        assert "11_VALIDACION.md" in common, name
        assert "00_PROTOCOLO_EJECUCION.md" in common, name
        assert "10_PROTOCOLO_GROK46.md" not in common, name
        assert "ningún ítem in-scope vuelve a" in common, name


def test_pending_launcher_contains_exact_sequence_and_no_closed_goal() -> None:
    launcher = (SPRINTS / "00_LANZAR_DESDE_10_7.md").read_text(encoding="utf-8")
    links = tuple(
        target
        for target in re.findall(r"\]\(([^)#]+\.md)\)", launcher)
        if target.startswith(("10.", "11."))
    )
    assert links == PENDING
    assert not set(CLOSED_GOAL10).intersection(links)
    assert not set(RETIRED_PROMPTS).intersection(links)
    assert "C09 es prerrequisito" in launcher
    assert "07_REPLANTEAR_C03.md" in launcher
    assert tuple(re.findall(r"\]\((12\.\d[^)]+\.md)\)", launcher)) == (
        "12.1_INSTALACION.md", "12.2_HARDWARE.md", "12.3_ENTREGA.md"
    )


def test_pending_goal_chain_hands_off_to_installed_acceptance() -> None:
    for current, following in zip(PENDING[:-1], PENDING[1:], strict=True):
        text = (SPRINTS / current).read_text(encoding="utf-8")
        assert f"Siguiente: `{following}`" in text, current
    final = (SPRINTS / PENDING[-1]).read_text(encoding="utf-8")
    assert "Siguiente: [12.1 — Instalación](12.1_INSTALACION.md)" in final
    assert "El producto instalado cierra en 12.3" in final


def test_retired_prompts_cannot_be_mistaken_for_work() -> None:
    for name in RETIRED_PROMPTS:
        text = (SPRINTS / name).read_text(encoding="utf-8")
        assert "NO LANZAR" in text
        assert "Retirado por decisión del dueño" in text
        assert "10_REPLANIFICACION_AUTONOMA.md" in text


def test_10_18_owns_agent_driven_public_entry_certification() -> None:
    text = (SPRINTS / "10.18_INTEGRACION.md").read_text(encoding="utf-8")
    for required in (
        "cuatro checkpoints",
        "200 en total",
        "entrada pública",
        "A/B/C/D = 50/50",
        "sin participación del dueño",
        "adjudicador independiente",
        "Las invocaciones internas sirven para diagnóstico y nunca suman 200",
    ):
        assert required.casefold() in text.casefold(), required
    assert "25 pedidos espontáneos del dueño" not in text
