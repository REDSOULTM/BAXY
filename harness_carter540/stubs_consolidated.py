"""Stubs consolidados: dispatchers que rutean al stub original por (name, action).

Mantiene determinismo total. Los outputs son los mismos que stubs.py para
que el bench mida solo el efecto de consolidacion en el modelo.
"""
from __future__ import annotations
from typing import Any

from stubs import execute_tool as _legacy_execute


# Map composite (name, action) -> legacy tool name
_LEGACY_MAP = {
    ("system_info", "time"): "system_time",
    ("system_info", "cpu"): "system_cpu",
    ("system_info", "ram"): "system_ram",
    ("system_info", "gpu"): "system_gpu",
    ("system_info", "disk"): "system_disk",
    ("system_info", "battery"): "system_battery",
    ("system_info", "volume"): "system_get_volume",

    ("system_control", "set_volume"): "system_set_volume",
    ("system_control", "mute"): "system_mute",
    ("system_control", "shutdown"): "system_shutdown",
    ("system_control", "reboot"): "system_reboot",

    ("app", "open"): "app_open",
    ("app", "close"): "app_close",
    ("app", "uninstall"): "app_uninstall",

    ("gui", "screenshot"): "gui_screenshot",
    ("gui", "click"): "gui_click",
    ("gui", "type"): "gui_type",
    ("gui", "keypress"): "gui_keypress",
    ("gui", "check_blockers"): "gui_check_blockers",
    ("gui", "locate"): "vision_locate_target",
    ("gui", "describe_dialog"): "vision_describe_dialog",
    ("gui", "universal_action"): "gui_universal_action",

    ("window", "list"): "list_windows",
    ("window", "manage"): "window_manage",
    ("window", "arrange"): "window_arrange",

    ("filesystem", "list"): "filesystem_list",
    ("filesystem", "read"): "filesystem_read",
    ("filesystem", "write"): "filesystem_write",
    ("filesystem", "delete"): "filesystem_delete",
    ("filesystem", "rename"): "filesystem_rename",
    ("filesystem", "copy"): "filesystem_copy",
    ("filesystem", "move"): "filesystem_move",
    ("filesystem", "create_dir"): "filesystem_create_dir",
    ("filesystem", "search"): "filesystem_search",
    ("filesystem", "diff"): "filesystem_diff",
    ("filesystem", "archive"): "filesystem_archive",
    ("filesystem", "unarchive"): "filesystem_unarchive",
    ("filesystem", "open"): "filesystem_open",

    ("web", "open_url"): "web_open_url",
    ("web", "search"): "web_search",
    ("web", "fetch"): "web_fetch",

    ("memory", "save"): "memory_save",
    ("memory", "recall"): "memory_recall",
    ("memory", "delete"): "memory_delete",
    ("memory", "list_all"): "memory_list_all",

    ("media", "play_pause"): "media_play_pause",
    ("media", "next"): "media_next",
    ("media", "prev"): "media_prev",
    ("media", "volume_up"): "media_volume_up",
    ("media", "volume_down"): "media_volume_down",

    ("clipboard", "read"): "clipboard_read",
    ("clipboard", "write"): "clipboard_write",

    ("office", "word_open"): "office_word_open",

    ("registry", "read"): "registry_read",
    ("registry", "list_keys"): "registry_list_keys",
}


def execute_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Despacha tool consolidada → legacy stub."""
    # Tools que pasan directo (1:1 con legacy)
    if name == "process":
        return _legacy_execute("list_processes", args)
    if name == "terminal_run":
        return _legacy_execute("terminal_run", args)
    if name == "gui_deeplink":
        return _legacy_execute("gui_deeplink", args)
    if name == "skill_load":
        return _legacy_execute("skill_load", args)

    # Composite: enrutar por action
    action = args.get("action")
    if not action:
        return {"ok": False, "error": f"composite_tool_missing_action: {name}"}

    legacy_name = _LEGACY_MAP.get((name, action))
    if not legacy_name:
        return {"ok": False, "error": f"unknown_composite_action: {name}.{action}"}

    # office.create necesita ruteo extra por format
    if name == "office" and action == "create":
        fmt = args.get("format", "docx")
        legacy_name = f"office_{fmt}_create"

    # Limpiar args: sacar 'action' que no espera el legacy
    clean = {k: v for k, v in args.items() if k != "action"}

    # gui.universal_action: el legacy espera 'action' como sub-action
    if name == "gui" and action == "universal_action":
        clean["action"] = clean.pop("sub_action", "click")

    return _legacy_execute(legacy_name, clean)


def coverage():
    import json
    from pathlib import Path
    schemas_path = Path(__file__).parent / "tool_schemas_consolidated.json"
    schemas = json.loads(schemas_path.read_text(encoding="utf-8"))
    return len(schemas), 60  # vs 60 originales


if __name__ == "__main__":
    cov, original = coverage()
    print(f"[stubs_consolidated] {cov} composite tools (vs {original} individuales)")
    print(f"[stubs_consolidated] Reduccion: {round((1 - cov/original)*100, 1)}%")

    # Test cada combo
    print("\nValidando ruteo:")
    for (name, action), legacy in _LEGACY_MAP.items():
        result = execute_tool(name, {"action": action, "level": 50, "name": "test", "path": "x.txt", "content": "y", "src": "a", "dst": "b", "key": "k", "value": "v", "url": "https://x", "query": "q", "title": "t", "action_type": "focus", "layout": "side", "x": 1, "y": 2, "text": "hi", "keys": "ctrl+a", "target_description": "btn", "target": "btn"})
        ok = result.get("ok", False)
        flag = "OK" if ok else "FAIL"
        print(f"  [{flag}] {name}.{action} -> {legacy}")
