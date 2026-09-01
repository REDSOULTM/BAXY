"""Owner decision 2026-09-01: certify Goal 10 before daily use."""

from __future__ import annotations

from pathlib import Path

from scripts.goal095_09512_integrate import (
    EXECUTABLE_PROMPTS,
    GROK46_CONTRACT_MARK,
    RETIRED_PROMPTS,
    parse_orden_executable,
)

REPO = Path(__file__).resolve().parents[1]
SPRINTS = REPO / "documentacion" / "sprints"


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
    pending = [
        name
        for name in EXECUTABLE_PROMPTS
        if name.startswith("11.")
        or (
            name.startswith("10.")
            and name
            not in {
                "10.0_BASE_VERDE.md",
                "10.1_CORPUS_Y_COLA.md",
                "10.2_PRESENCIA_Y_RECURSOS.md",
                "10.2.5_RECURSOS_EN_REPOSO.md",
            }
        )
    ]
    assert len(pending) == 28
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
    for name in pending:
        text = (SPRINTS / name).read_text(encoding="utf-8")
        for item in required:
            assert item in text, f"{name} missing {item}"


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

