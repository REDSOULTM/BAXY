"""Política de verificación escalonada por riesgo (investigación 3, punto 5).

Verificar TODA acción añade latencia y carga (SmartSnap arXiv:2512.22322, 2026:
la verificación pasiva "incurs prohibitively high verification costs"). La cura
es verificación SELECTIVA por riesgo: garantías duras en acciones irreversibles
o a terceros; latencia cero en acciones triviales reversibles.

Este módulo es la ÚNICA fuente de verdad del tier de riesgo por tool — pura,
sin dependencias, evaluada al planificar (no al ejecutar). NO ejecuta
verificación; sólo dice si HAY que hacerla y con qué presupuesto de latencia.
El gate de confirmación real vive en safety.classify_tool_call (que esta tabla
documenta y mantiene coherente). Nombres de tool = los reales del catálogo de 65
(whatsapp, email, filesystem, terminal, app, audio...), no inventados.

Riesgo por args, no sólo por tool (inv 3): `audio.set_volume` a +5% es trivial;
absoluto a 100% no. `filesystem.delete` en temp vs en Documentos difieren.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class Risk(str, Enum):
    TRIVIAL = "trivial"   # reversible, daño nulo -> NO verificar
    LOW = "low"           # reversible, daño bajo -> verificar si es barato
    MEDIUM = "medium"     # reversible con coste -> verificar
    HIGH = "high"         # irreversible o comunicación a terceros -> verificar SIEMPRE


@dataclass(frozen=True)
class VerifyPolicy:
    risk: Risk
    must_verify: bool
    # Confirmación previa del usuario. Reservada para lo irreversible SIN otro
    # backstop (inv 3 punto 5). whatsapp.send_message NO la lleva: ya verifica
    # el chat por OCR. email.send SÍ (no tiene backstop) — coherente con
    # safety.classify_tool_call.
    require_user_confirmation: bool
    verify_timeout_ms: int


# Acciones de comunicación a terceros / irreversibles (HIGH). El daño de un
# mensaje al destinatario equivocado es real (bug #847b del chat equivocado).
_HIGH_RISK = {
    ("whatsapp", "send_message"),
    ("email", "send"),
    ("filesystem", "delete"),
    ("filesystem", "move"),
    ("filesystem", "rename"),
    ("terminal", "*"),
}

# Acciones triviales reversibles (TRIVIAL): no verificar (latencia cero).
_TRIVIAL = {
    ("media", "play"), ("media", "pause"), ("media", "next"),
    ("media", "previous"), ("media", "resume"),
}


def policy_for(tool: str, args: dict[str, Any] | None) -> VerifyPolicy:
    """Devuelve la política de verificación para (tool, args). Pura, nunca lanza."""
    a = dict(args or {})
    action = str(a.get("action") or "").casefold()

    # --- HIGH: irreversible / comunicación externa ---
    if (tool, action) in _HIGH_RISK or (tool, "*") in _HIGH_RISK:
        # email.send es el único sin backstop -> confirmación previa.
        confirm = tool == "email" and action == "send"
        # filesystem.delete también es destructivo sin retorno fácil.
        if tool == "filesystem" and action == "delete":
            confirm = True
        timeout = 5000 if tool == "terminal" else 400
        return VerifyPolicy(Risk.HIGH, must_verify=True,
                            require_user_confirmation=confirm,
                            verify_timeout_ms=timeout)

    # --- TRIVIAL: reversible, daño nulo ---
    if (tool, action) in _TRIVIAL:
        return VerifyPolicy(Risk.TRIVIAL, must_verify=False,
                            require_user_confirmation=False, verify_timeout_ms=0)

    # audio.set_volume: trivial si el cambio es pequeño/relativo, low si absoluto.
    if tool == "audio" and action in {"set_volume", "volume"}:
        delta = a.get("delta") or a.get("delta_pct")
        if delta is not None:
            try:
                if abs(float(delta)) <= 10:
                    return VerifyPolicy(Risk.TRIVIAL, False, False, 0)
            except (TypeError, ValueError):
                pass
        return VerifyPolicy(Risk.LOW, must_verify=True,
                            require_user_confirmation=False, verify_timeout_ms=10)

    # app.open / window.focus: reversible, daño nulo, pero verificar que abrió
    # ayuda a no mentir ("abrí Word" cuando no apareció ventana).
    if tool == "app" and action == "open":
        return VerifyPolicy(Risk.LOW, must_verify=True,
                            require_user_confirmation=False, verify_timeout_ms=1500)

    # default conservador: medium, verificar barato.
    return VerifyPolicy(Risk.MEDIUM, must_verify=True,
                        require_user_confirmation=False, verify_timeout_ms=500)
