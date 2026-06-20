"""Configurable safety gate for risky local actions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SafetyDecision:
    requires_confirmation: bool
    risk: str = "low"
    reason: str = ""


def classify_tool_call(tool: str, args: dict[str, Any]) -> SafetyDecision:
    action = str(args.get("action") or "").casefold()
    if tool == "filesystem" and action in {"delete", "write", "move", "rename", "unarchive"}:
        return SafetyDecision(True, "filesystem_mutation", f"{tool}.{action} can alter or remove files")
    if tool == "terminal":
        command = str(args.get("command") or "")
        if _terminal_risky(command, args):
            return SafetyDecision(True, "terminal_command", f"terminal command can modify system state: {command}")
    if tool == "package" and action in {"install", "uninstall"}:
        return SafetyDecision(True, "package_change", f"package.{action} changes installed software")
    if tool == "app" and action in {"close", "uninstall"}:
        return SafetyDecision(True, "process_or_app_change", f"app.{action} can close or remove software")
    if tool == "system" and action in {"shutdown", "restart", "sleep", "brightness_set"}:
        return SafetyDecision(True, "system_power_or_setting", f"system.{action} changes system state")
    if tool == "audio" and action in {"set_default"}:
        return SafetyDecision(True, "system_audio_device", "changing default audio device affects system settings")
    if tool == "audio_device" and action in {"set_default", "set_default_communications", "set_app_route", "restore"}:
        return SafetyDecision(True, "system_audio_device", "changing audio devices/routing affects system settings")
    if tool == "office" and action in {"edit_presentation", "edit_document", "edit_spreadsheet", "export_pdf"}:
        return SafetyDecision(True, "document_mutation", f"office.{action} can modify user documents")
    # Inv 3 (verificación): enviar email es irreversible y a terceros, y NO tiene
    # backstop (a diferencia de whatsapp.send_message, que verifica el chat por
    # OCR antes de mandar). Un email al destinatario/contenido equivocado es daño
    # real. Confirmar antes de send (no antes de draft/status). Lit.: acciones
    # irreversibles de comunicación externa = verificación/confirmación obligatoria.
    # NB: el send sin Graph token cae al redactor web pre-rellenado (no envía; el
    # usuario manda a mano en el redactor) — ver email_tool. Igual mantenemos la
    # confirmación previa cuando safety está ON: confirmar "voy a actuar sobre tu
    # correo" es correcto para comunicación externa, y el redactor abre DESPUÉS.
    if tool == "email" and action == "send":
        return SafetyDecision(True, "external_message_send", "email.send delivers an irreversible message to third parties")
    # CREAR/disparar un recordatorio/timer/alarma/toast local es BENIGNO y REVERSIBLE
    # (se cancela con *_cancel) -> tier-Alexa: NO se confirma (la propia confirmation_policy
    # clasifica "recordatorios/alarmas" como bajo-impacto auto-aprobable). Confirmar
    # "recordame en 5 min" era fricción anti-Alexa y, al narrar mal ese needs_confirmation,
    # el E2B confabulaba un motivo falso ("no aceptó la duración"). CANCELAR/BORRAR/EDITAR
    # sí toca algo que el usuario fijó -> se mantiene la confirmación.
    _NOTIF_CONFIRM = {"timer_cancel", "alarm_cancel", "reminder_delete", "delete",
                      "timer_update", "alarm_update", "reminder_update", "notification_update"}
    if tool == "notification" and action in _NOTIF_CONFIRM:
        return SafetyDecision(True, "scheduled_notification", f"notification.{action} cancels/edits a scheduled task the user set")
    if tool == "routine" and action in {"create", "enable", "disable", "delete", "run_now"}:
        return SafetyDecision(True, "automation", f"routine.{action} can run or persist multi-step automation")
    if tool in {"contacts", "notes_tasks", "local_calendar", "habit_tracker", "source_manager"} and action not in {"status", "list", "search", "read", "get", "sources", "notes", "tasks", "event_list", "stats"}:
        return SafetyDecision(True, "local_state_change", f"{tool}.{action} changes local agent state")
    if tool == "backup_sync" and action in {"backup_create", "restore", "dedupe"}:
        return SafetyDecision(True, "backup_or_restore", f"backup_sync.{action} can create or restore file backups")
    if tool == "printer_scanner" and action in {"printer_default_set", "print_file", "cancel_job", "scan_document"}:
        return SafetyDecision(True, "printer_scanner_action", f"printer_scanner.{action} affects printers/scanners")
    if tool == "desktop_layout" and action in {"restore"}:
        return SafetyDecision(True, "desktop_layout_change", "desktop_layout.restore changes visible window layout")
    if tool == "registry" and action in {"add", "delete", "import"}:
        return SafetyDecision(True, "registry_mutation", f"registry.{action} changes Windows registry")
    if tool == "env" and action in {"set", "delete"} and str(args.get("scope") or "process").casefold() in {"user", "machine"}:
        return SafetyDecision(True, "persistent_env_change", "persistent environment variable change")
    if tool == "download" and action == "fetch":
        return SafetyDecision(True, "download", "downloaded files can be unsafe without hash/signature verification")
    if tool == "input" and action in {"set_language_list", "switch_keyboard"}:
        return SafetyDecision(True, "keyboard_language_change", "keyboard/language list change affects Windows input settings")
    return SafetyDecision(False)


# Verbos de MUTACIÓN en nombres de tool MCP. NO es una lista de keywords por idioma
# del usuario (eso sí está prohibido): los nombres de tools MCP son identificadores
# del PROTOCOLO, siempre en inglés por convención del spec (read_file/write_file/
# delete/create_issue/...). Es una guarda ESTRUCTURAL sobre la FORMA del nombre del
# tool externo, no sobre el contenido del mensaje de entrada. Fuente: spec MCP de
# tool naming + tool annotations (readOnlyHint/destructiveHint).
_MCP_MUTATION_VERBS = (
    "write", "delete", "remove", "create", "update", "edit", "modify", "move",
    "rename", "put", "post", "patch", "insert", "append", "set", "push", "send",
    "drop", "truncate", "exec", "run", "install", "uninstall", "kill", "destroy",
    "publish", "merge", "commit", "revert", "reset", "clear", "purge", "upload",
)
# Verbos de LECTURA (no mutan). Si el nombre del tool MCP empieza con / contiene uno
# de estos y NINGÚN verbo de mutación, lo tratamos como lectura -> sin confirmación
# (evita fricción en el caso común: read_file/list_directory/get_*/search/query).
# Igual que arriba: identificadores del PROTOCOLO (inglés), guarda estructural.
_MCP_READ_VERBS = (
    "read", "list", "get", "fetch", "search", "query", "find", "show", "view",
    "describe", "inspect", "status", "info", "stat", "head", "peek", "lookup",
    "count", "exists", "check", "browse", "tail",
)


def classify_mcp_call(tool_name: str, annotations: dict[str, Any] | None = None) -> SafetyDecision:
    """Clasifica una tool MCP (externa, semántica desconocida) para el gate de
    confirmación. Las tools MCP saltaban el classifier por completo (early-return en
    el dispatcher): una `mcp__fs__delete_file` se ejecutaba sin confirmar aunque
    safety estuviera ON. Esto lo cierra.

    PRIORIDAD de la decisión (de más a menos confiable):
      1. ANNOTATIONS del protocolo MCP (la señal honesta del propio servidor):
         readOnlyHint=True  -> nunca confirmar (es lectura declarada).
         destructiveHint=True -> confirmar (mutación destructiva declarada).
      2. Estructura del NOMBRE: si el identificador del tool (inglés del protocolo)
         contiene un verbo de mutación -> confirmar.
      3. Default para MCP desconocido -> CONFIRMAR (fail-safe: es código externo
         arbitrario y no podemos medir su efecto; la honestidad manda confirmar).

    `annotations` es el dict ToolAnnotations del MCP (si el discovery lo capturó);
    None si el servidor no las expone (la mayoría de los servers viejos)."""
    ann = annotations if isinstance(annotations, dict) else {}
    # 1. Annotations del protocolo (lo más honesto).
    if ann.get("readOnlyHint") is True:
        return SafetyDecision(False, "mcp_read_only", f"MCP tool {tool_name} declares readOnlyHint")
    if ann.get("destructiveHint") is True:
        return SafetyDecision(True, "mcp_destructive", f"MCP tool {tool_name} declares destructiveHint")
    # 2. Estructura del nombre del tool (último segmento del namespaced).
    leaf = tool_name
    # tomar el último segmento del nombre namespaced 'mcp__server__tool' -> 'tool'
    if "__" in leaf:
        leaf = leaf.rsplit("__", 1)[-1]
    low = leaf.casefold()
    tokens = set(low.replace("-", "_").split("_"))
    # mutación gana sobre lectura (ej. 'get_and_delete' es mutación).
    if tokens & set(_MCP_MUTATION_VERBS) or any(low.startswith(v) for v in _MCP_MUTATION_VERBS):
        return SafetyDecision(True, "mcp_mutation", f"MCP tool {tool_name} name suggests a mutating action")
    if tokens & set(_MCP_READ_VERBS) or any(low.startswith(v) for v in _MCP_READ_VERBS):
        return SafetyDecision(False, "mcp_read_only", f"MCP tool {tool_name} name suggests a read-only action")
    # 3. Default: MCP externo sin señal clara -> confirmar (fail-safe, no auto-aprobar
    #    código arbitrario de terceros). El usuario puede confirmar una vez.
    return SafetyDecision(True, "mcp_external_unknown", f"MCP tool {tool_name} is external; confirming before running")


def _terminal_risky(command: str, args: dict[str, Any]) -> bool:
    low = " ".join([command, " ".join(str(item) for item in args.get("args") or [])]).casefold()
    risky_tokens = (
        "del ", "erase ", "remove-item", "rm ", "rmdir", "rd ",
        "format", "diskpart", "reg add", "reg delete", "shutdown",
        "restart-computer", "stop-process", "taskkill", "winget install",
        "winget uninstall", "set-itemproperty", "new-itemproperty",
    )
    return any(token in low for token in risky_tokens)
