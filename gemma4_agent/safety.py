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
    if tool == "email" and action == "send":
        return SafetyDecision(True, "external_message_send", "email.send delivers an irreversible message to third parties")
    if tool == "notification" and action not in {"status", "list", "timer_list", "alarm_list", "reminder_list"}:
        return SafetyDecision(True, "scheduled_notification", f"notification.{action} can create/cancel local scheduled tasks")
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


def _terminal_risky(command: str, args: dict[str, Any]) -> bool:
    low = " ".join([command, " ".join(str(item) for item in args.get("args") or [])]).casefold()
    risky_tokens = (
        "del ", "erase ", "remove-item", "rm ", "rmdir", "rd ",
        "format", "diskpart", "reg add", "reg delete", "shutdown",
        "restart-computer", "stop-process", "taskkill", "winget install",
        "winget uninstall", "set-itemproperty", "new-itemproperty",
    )
    return any(token in low for token in risky_tokens)
