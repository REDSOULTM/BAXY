"""B5 — Política de confirmación estructurada (adopción de OpenHands `ConfirmationPolicy`
+ openclaw `before_tool_call`).

Formaliza el guard ad-hoc de acciones riesgosas (que hoy vive disperso en
`classify_tool_call`) en una POLÍTICA configurable por sesión, manteniendo la
garantía dura del backlog B5: **NUNCA auto-aprobar una acción IRREVERSIBLE sin
confirmación**, sea cual sea la política.

Es una GUARDA ESTRUCTURAL (mide la FORMA de la acción —¿es riesgosa? ¿irreversible?—
vía `SafetyDecision`, no el contenido ni el idioma), del tipo explícitamente
permitido por CLAUDE.md §3. Determinista, sin LLM, sin listas de keywords.

Políticas (env `GEMMA4_CONFIRMATION_POLICY`):
  - `confirm_risky` (DEFAULT): confirmar lo que `classify_tool_call` marca riesgoso.
    Idéntico a la conducta histórica → flipear no cambia nada por defecto.
  - `never`: auto-aprobar lo REVERSIBLE (notas, calendario, layout, audio…) para
    reducir fricción del power-user, PERO seguir confirmando lo IRREVERSIBLE.
  - `always`: confirmar TODA acción (incluso lecturas) — modo auditoría/paranoico.
"""

from __future__ import annotations

import os
from typing import Any

CONFIRM_RISKY = "confirm_risky"
ALWAYS_CONFIRM = "always"
NEVER_CONFIRM = "never"
# `all` (permisivo TOTAL): auto-aprueba TODO, incluso lo IRREVERSIBLE (borrar
# archivos, taskkill, apagar, desinstalar, email a terceros). Cero fricción, máximo
# riesgo. Toggle OFF por default. NO confundir con `never`, que sigue confirmando
# lo destructivo.
ALL_PERMISSIVE = "all"
_VALID = (CONFIRM_RISKY, ALWAYS_CONFIRM, NEVER_CONFIRM, ALL_PERMISSIVE)

# Categorías de `SafetyDecision.risk` (ver safety_pkg/safety.py) consideradas
# IRREVERSIBLES o de alto daño: aunque la política sea `never`, estas SIEMPRE se
# confirman. Conservador a propósito (la seguridad pesa sobre la fricción): se
# incluyen los borderline (apagar/cerrar app, editar documento, automatización).
# Quedan FUERA (auto-aprobables bajo `never`) solo las claramente reversibles y de
# bajo impacto: audio device, recordatorios/alarmas, estado local (notas/calendario/
# contactos), impresión, layout de ventanas, idioma de teclado.
_IRREVERSIBLE_RISKS = frozenset({
    "external_message_send",    # email.send — a terceros, sin vuelta atrás
    "filesystem_mutation",      # delete/move/rename/write/unarchive — pérdida de datos
    "terminal_command",         # rm/format/shutdown/taskkill/…
    "package_change",           # install/uninstall
    "process_or_app_change",    # app.close/uninstall
    "system_power_or_setting",  # shutdown/restart/sleep
    "document_mutation",        # office edit/export — puede sobrescribir
    "automation",               # routine create/run — puede hacer cualquier cosa
    "backup_or_restore",        # restore sobrescribe
    "registry_mutation",        # registry add/delete/import
    "persistent_env_change",    # env user/machine
    "download",                 # archivos sin verificar hash/firma
    # Tools MCP externas (semántica desconocida): una mcp__fs__delete_file o un
    # create_issue son irreversibles/efecto-real. Bajo CUALQUIER política se confirman
    # (no auto-aprobar código de terceros). El readOnly declarado NO entra acá (no
    # marca requires_confirmation), así las lecturas MCP siguen sin fricción.
    "mcp_destructive",          # MCP annotation destructiveHint=True
    "mcp_mutation",             # nombre del tool MCP sugiere mutación
    "mcp_external_unknown",     # MCP externo sin señal -> fail-safe
})


def get_policy() -> str:
    """Lee `GEMMA4_CONFIRMATION_POLICY`. Default `confirm_risky` (= conducta actual).
    Un valor inválido cae a `confirm_risky` (fallback seguro)."""
    raw = (os.environ.get("GEMMA4_CONFIRMATION_POLICY") or CONFIRM_RISKY).strip().lower()
    return raw if raw in _VALID else CONFIRM_RISKY


def is_irreversible(decision: Any) -> bool:
    """¿La acción riesgosa es IRREVERSIBLE/alto-daño? (garantía dura B5)."""
    return bool(
        getattr(decision, "requires_confirmation", False)
        and getattr(decision, "risk", "") in _IRREVERSIBLE_RISKS
    )


def should_confirm(decision: Any, policy: str | None = None) -> bool:
    """¿Pedir confirmación para esta acción, dada la política?

    - `all`          → NUNCA confirma (permisivo total, incl. irreversible). Opt-in.
    - `never`        → solo si es IRREVERSIBLE (garantía dura); lo reversible se auto-aprueba.
    - `always`       → SIEMPRE (incluso lecturas; modo auditoría).
    - `confirm_risky`→ si `classify_tool_call` la marcó riesgosa (= conducta actual). DEFAULT.

    Invariante (salvo `all`): una acción IRREVERSIBLE se confirma bajo CUALQUIER
    política (never→is_irreversible; confirm_risky→requires_confirmation⊇irreversible;
    always→True). El modo `all` ROMPE el invariante a propósito: nada confirma.
    """
    if policy is None:
        policy = get_policy()
    if policy == ALL_PERMISSIVE:
        return False   # permisivo total: nada confirma, ni lo irreversible
    if policy == NEVER_CONFIRM:
        return is_irreversible(decision)
    if policy == ALWAYS_CONFIRM:
        return True
    # CONFIRM_RISKY (default / fallback)
    return bool(getattr(decision, "requires_confirmation", False))
