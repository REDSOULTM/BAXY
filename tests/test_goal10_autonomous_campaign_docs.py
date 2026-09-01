"""Owner decision 2026-09-01: certify Goal 10 before daily use."""

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


def test_every_pending_goal_embeds_the_full_grok46_contract() -> None:
    assert len(PENDING) == 28
    required = (
        GROK46_CONTRACT_MARK,
        "## Contrato de goal",
        "## BAXY y fuentes de autoridad",
        "## Las cinco leyes",
        "## Los seis invariantes",
        "## Cómo trabajas aquí",
        "## Herencia 09.5",
        "## Contrato de sesión",
        "## Objetivo único",
        "## Criterios de cierre",
        "Grok 4.6",
        "HEAD == origin/main",
    )
    for name in PENDING:
        text = (SPRINTS / name).read_text(encoding="utf-8")
        for item in required:
            assert item in text, f"{name} missing {item}"


def test_pending_prompts_preserve_goal_01_09_rules_and_prompt_shape() -> None:
    headings = (
        "## Contrato de goal",
        "## BAXY y fuentes de autoridad",
        "## Las cinco leyes",
        "## Los seis invariantes",
        "## Cómo trabajas aquí",
        "## Herencia 09.5",
        "## Contrato de sesión",
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
        "Nada se afirma sin verificarlo independientemente",
        "estados terminales dicen la verdad",
        "confirmación pertenece a la invocación exacta",
        "Cero respuestas visibles fijas",
        "Modelo local y privado",
    )
    forbidden_human_dependencies = (
        "pedidos espontáneos del dueño",
        "turnos reales del dueño",
        "esperando tus interacciones",
        "el dueño debe proporcionar",
        "pide al dueño que pruebe",
    )

    for name in PENDING:
        text = (SPRINTS / name).read_text(encoding="utf-8")
        assert text.count("grok46-goal-contract:begin") == 1, name
        assert text.count("grok46-goal-contract:end") == 1, name
        assert all(text.count(heading) == 1 for heading in headings), name
        assert [text.index(heading) for heading in headings] == sorted(
            text.index(heading) for heading in headings
        ), name
        assert all(law.casefold() in text.casefold() for law in laws), name
        assert all(item.casefold() in text.casefold() for item in invariants), name
        assert "Grok 4.6" in text and "esfuerzo `high`" in text, name
        assert "500k" in text and "FALLO_DE_AMBIENTE" in text, name
        assert "HEAD == origin/main" in text, name
        assert not any(
            item.casefold() in text.casefold()
            for item in forbidden_human_dependencies
        ), name


def test_goal11_contract_uses_goal11_authority_and_cannot_redefer_debt() -> None:
    for name in PENDING:
        if not name.startswith("11."):
            continue
        text = (SPRINTS / name).read_text(encoding="utf-8")
        common = text.split("grok46-goal-contract:begin", 1)[1].split(
            "grok46-goal-contract:end", 1
        )[0]
        assert "11_VALIDACION.md" in common, name
        assert "11_PROTOCOLO_GROK46.md" in common, name
        assert "10_PROTOCOLO_GROK46.md" not in common, name
        assert "ningún ítem in-scope vuelve a" in common, name
        assert "si este prompt sólo inventaría o particiona" in common, name


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
    assert "SIGUIENTE:" in launcher
    assert "10.7_CONVERSACION.md" in launcher
    assert "No hay otra tanda humana ni un goal oculto después" in launcher


def test_pending_goal_chain_is_explicit_and_terminal_only_at_11_16() -> None:
    for current, following in zip(PENDING[:-1], PENDING[1:], strict=True):
        text = (SPRINTS / current).read_text(encoding="utf-8")
        assert f"Siguiente: `{following}`" in text, current
    final = (SPRINTS / PENDING[-1]).read_text(encoding="utf-8")
    assert "Siguiente: `ninguno — BAXY listo para uso diario`" in final


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
        "no acredita end-to-end",
    ):
        assert required.casefold() in text.casefold(), required
    assert "25 pedidos espontáneos del dueño" not in text
