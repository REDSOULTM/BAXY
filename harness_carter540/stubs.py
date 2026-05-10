"""Stub implementations deterministas para las 60 tools de Carter v4.

Cada stub devuelve un valor fijo plausible. NO ejecuta el SO real.
Esto mide al modelo (tool selection + args), no al sistema operativo.
"""

from __future__ import annotations

from typing import Any


def execute_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Despacha tool stub. Nombre exacto del catalog Carter v4."""
    fn = _STUBS.get(name)
    if fn is None:
        return {"ok": False, "error": f"tool_not_found: {name!r}"}
    try:
        return fn(args)
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


# ----------------------------------------------------------------
# system_*
# ----------------------------------------------------------------

def _system_set_volume(a):
    return {"ok": True, "level": int(a.get("level", 50)), "muted": False}

def _system_mute(a):
    return {"ok": True, "muted": bool(a.get("state", True))}

def _system_get_volume(a):
    return {"ok": True, "level": 50, "muted": False}

def _system_battery(a):
    return {"ok": True, "percent": 87, "charging": True, "ac_powered": True}

def _system_cpu(a):
    return {"ok": True, "percent_used": 14.2, "cores": 12}

def _system_ram(a):
    return {"ok": True, "used_gb": 18.4, "total_gb": 32.0, "percent": 57.5}

def _system_gpu(a):
    return {"ok": True, "vram_used_mb": 5354, "vram_total_mb": 16379,
            "name": "NVIDIA GeForce RTX 4060 Ti"}

def _system_time(a):
    return {"ok": True, "iso": "2026-05-10T02:30:00", "human": "2:30 AM, 10 May 2026"}

def _system_disk(a):
    return {"ok": True, "free_gb": 412.5, "total_gb": 1000.0, "drive": "C:"}

def _system_shutdown(a):
    return {"ok": True, "scheduled": True, "delay_s": 60}

def _system_reboot(a):
    return {"ok": True, "scheduled": True, "delay_s": 60}


# ----------------------------------------------------------------
# app_*
# ----------------------------------------------------------------

def _app_open(a):
    return {"ok": True, "name": a.get("name", "unknown"),
            "pid": 12345, "method": "shell"}

def _app_close(a):
    return {"ok": True, "name": a.get("name", "unknown"), "closed": True}


# ----------------------------------------------------------------
# gui_*
# ----------------------------------------------------------------

def _gui_deeplink(a):
    return {"ok": True, "app": a.get("app", ""), "intent": a.get("intent", ""),
            "uri": f"{a.get('app','')}://{a.get('intent','')}"}

def _gui_universal_action(a):
    return {"ok": True, "tier": 1, "tier_name": "UIA + click_input",
            "action": a.get("action", "click"), "x": 500, "y": 400,
            "frame_diff_fraction": 0.082}

def _gui_screenshot(a):
    return {"ok": True, "path": "C:\\temp\\screenshot.png",
            "size_bytes": 1234567, "image_path": "C:\\temp\\screenshot.png"}

def _gui_type(a):
    return {"ok": True, "typed_chars": len(a.get("text", "")),
            "frame_diff_fraction": 0.025}

def _gui_keypress(a):
    return {"ok": True, "keys": a.get("keys", "")}

def _gui_click(a):
    return {"ok": True, "x": int(a.get("x", 0)), "y": int(a.get("y", 0))}

def _gui_check_blockers(a):
    return {"ok": True, "captcha": False, "login_wall": False,
            "error_modal": False, "type": "none", "any_blocker": False}

def _vision_describe_dialog(a):
    return {"ok": True,
            "description": "Una ventana de Notepad con texto 'hola' en el editor."}

def _vision_locate_target(a):
    return {"ok": True, "visible": True, "x": 320, "y": 240,
            "confidence": 0.85,
            "summary": f"vi '{a.get('target_description','')}'"}


# ----------------------------------------------------------------
# window_*
# ----------------------------------------------------------------

def _window_manage(a):
    return {"ok": True, "action": a.get("action", "focus"),
            "title": a.get("title", ""), "result": "applied"}

def _list_windows(a):
    return {"ok": True, "windows": [
        {"title": "Notepad - Untitled", "pid": 1234, "visible": True},
        {"title": "Carter v4 — REPL", "pid": 5678, "visible": True},
    ]}

def _window_arrange(a):
    return {"ok": True, "arranged": True, "layout": a.get("layout", "side-by-side")}


# ----------------------------------------------------------------
# filesystem_*
# ----------------------------------------------------------------

def _filesystem_list(a):
    return {"ok": True, "path": a.get("path", "."),
            "items": ["nota.txt", "carpeta1", "README.md"]}

def _filesystem_read(a):
    return {"ok": True, "path": a.get("path", ""),
            "content": "[stub content for benchmark]",
            "size_bytes": 42}

def _filesystem_write(a):
    if a.get("path", "").startswith(("C:\\Windows", "C:\\Program Files")):
        return {"ok": False, "error": "path fuera del sandbox"}
    return {"ok": True, "path": a.get("path", ""),
            "bytes_written": len(a.get("content", ""))}

def _filesystem_create_dir(a):
    return {"ok": True, "path": a.get("path", "")}

def _filesystem_delete(a):
    return {"ok": True, "path": a.get("path", ""), "deleted": True}

def _filesystem_rename(a):
    return {"ok": True, "src": a.get("src", ""), "dst": a.get("dst", "")}

def _filesystem_copy(a):
    return {"ok": True, "src": a.get("src", ""), "dst": a.get("dst", "")}

def _filesystem_move(a):
    return {"ok": True, "src": a.get("src", ""), "dst": a.get("dst", "")}

def _filesystem_search(a):
    return {"ok": True, "query": a.get("query", ""),
            "matches": ["carpeta/archivo1.md", "carpeta/sub/archivo2.md"]}

def _filesystem_diff(a):
    return {"ok": True, "diff": "+++ added\n--- removed\n@@ -1 +1 @@"}

def _filesystem_archive(a):
    return {"ok": True, "archive_path": a.get("dst", "out.zip"),
            "files_count": 3}

def _filesystem_unarchive(a):
    return {"ok": True, "extracted_to": a.get("dst", "."),
            "files_count": 3}

def _filesystem_open(a):
    return {"ok": True, "path": a.get("path", ""), "opened_with": "default_app"}


# ----------------------------------------------------------------
# web_*
# ----------------------------------------------------------------

def _web_open_url(a):
    return {"ok": True, "url": a.get("url", ""), "browser": "default"}

def _web_search(a):
    return {"ok": True, "query": a.get("query", ""),
            "results": [
                {"title": f"Result 1 for '{a.get('query','')}'", "url": "https://example.com/1"},
                {"title": f"Result 2 for '{a.get('query','')}'", "url": "https://example.com/2"},
            ]}

def _web_fetch(a):
    return {"ok": True, "url": a.get("url", ""),
            "content_preview": "[stub HTML content for benchmark]"}


# ----------------------------------------------------------------
# terminal_*
# ----------------------------------------------------------------

def _terminal_run(a):
    cmd = a.get("command", "")
    args = a.get("args", [])
    if cmd == "echo":
        return {"ok": True, "exit_code": 0,
                "stdout": " ".join(str(x) for x in args), "stderr": "",
                "command": cmd, "args": args}
    if cmd in ("python", "python3", "py"):
        return {"ok": True, "exit_code": 0,
                "stdout": "Python 3.13.0", "stderr": "",
                "command": cmd, "args": args}
    if cmd == "pip":
        return {"ok": True, "exit_code": 0,
                "stdout": "pip 25.0.1", "stderr": "",
                "command": cmd, "args": args}
    if cmd == "git":
        return {"ok": True, "exit_code": 0,
                "stdout": "On branch main\nnothing to commit", "stderr": "",
                "command": cmd, "args": args}
    if cmd == "pytest":
        return {"ok": True, "exit_code": 0,
                "stdout": "5 passed in 1.23s", "stderr": "",
                "command": cmd, "args": args}
    if cmd == "nvidia-smi":
        return {"ok": True, "exit_code": 0,
                "stdout": "RTX 4060 Ti 16GB | 14% util | 5354 MiB used",
                "stderr": "", "command": cmd, "args": args}
    return {"ok": True, "exit_code": 0,
            "stdout": f"[stub output for {cmd}]", "stderr": "",
            "command": cmd, "args": args}


# ----------------------------------------------------------------
# memory_*
# ----------------------------------------------------------------

_MEMORY: dict[str, str] = {}

def _memory_save(a):
    key = a.get("key", "default")
    _MEMORY[key] = str(a.get("value", ""))
    return {"ok": True, "key": key, "saved": True}

def _memory_recall(a):
    key = a.get("key", "default")
    return {"ok": True, "key": key, "value": _MEMORY.get(key, ""),
            "exists": key in _MEMORY}

def _memory_delete(a):
    key = a.get("key", "default")
    existed = key in _MEMORY
    _MEMORY.pop(key, None)
    return {"ok": True, "key": key, "deleted": existed}

def _memory_list_all(a):
    return {"ok": True, "memories": dict(_MEMORY)}


# ----------------------------------------------------------------
# media_*
# ----------------------------------------------------------------

def _media_play_pause(a):
    return {"ok": True, "action": "toggled"}

def _media_next(a):
    return {"ok": True, "action": "next_track"}

def _media_prev(a):
    return {"ok": True, "action": "prev_track"}


# ----------------------------------------------------------------
# clipboard_*
# ----------------------------------------------------------------

def _clipboard_read(a):
    return {"ok": True, "content": "[stub clipboard content]"}

def _clipboard_write(a):
    return {"ok": True, "wrote_chars": len(a.get("content", ""))}


# ----------------------------------------------------------------
# office_*
# ----------------------------------------------------------------

def _office_word_open(a):
    return {"ok": True, "doc_path": a.get("path", ""), "word_pid": 9999}

def _office_docx_create(a):
    return {"ok": True, "path": a.get("path", "doc.docx"), "created": True}

def _office_pptx_create(a):
    return {"ok": True, "path": a.get("path", "pres.pptx"), "created": True}

def _office_xlsx_create(a):
    return {"ok": True, "path": a.get("path", "sheet.xlsx"), "created": True}

def _app_uninstall(a):
    return {"ok": True, "app": a.get("name", ""), "uninstalled": True}

def _list_processes(a):
    return {"ok": True, "processes": [
        {"name": "python.exe", "pid": 1234, "cpu_pct": 0.5},
        {"name": "chrome.exe", "pid": 5678, "cpu_pct": 2.1},
        {"name": "explorer.exe", "pid": 999, "cpu_pct": 0.0},
    ]}

def _media_volume_up(a):
    return {"ok": True, "level": 60, "delta": 10}

def _media_volume_down(a):
    return {"ok": True, "level": 40, "delta": -10}


# ----------------------------------------------------------------
# registry_*
# ----------------------------------------------------------------

def _registry_read(a):
    return {"ok": True, "hive": a.get("hive", ""),
            "key_path": a.get("key_path", ""),
            "value_name": a.get("value_name", ""), "value": "[stub]"}

def _registry_list_keys(a):
    return {"ok": True, "hive": a.get("hive", ""),
            "key_path": a.get("key_path", ""),
            "subkeys": ["sub1", "sub2", "sub3"]}


# ----------------------------------------------------------------
# skill_*
# ----------------------------------------------------------------

def _skill_load(a):
    return {"ok": True, "skill": a.get("name", ""),
            "instructions": "[stub skill loaded]"}


# ----------------------------------------------------------------
# Mapping name -> impl
# ----------------------------------------------------------------

_STUBS = {
    "system_set_volume": _system_set_volume,
    "system_mute": _system_mute,
    "system_get_volume": _system_get_volume,
    "system_battery": _system_battery,
    "system_cpu": _system_cpu,
    "system_ram": _system_ram,
    "system_gpu": _system_gpu,
    "system_time": _system_time,
    "system_disk": _system_disk,
    "system_shutdown": _system_shutdown,
    "system_reboot": _system_reboot,
    "app_open": _app_open,
    "app_close": _app_close,
    "gui_deeplink": _gui_deeplink,
    "gui_universal_action": _gui_universal_action,
    "gui_screenshot": _gui_screenshot,
    "gui_type": _gui_type,
    "gui_keypress": _gui_keypress,
    "gui_click": _gui_click,
    "gui_check_blockers": _gui_check_blockers,
    "vision_describe_dialog": _vision_describe_dialog,
    "vision_locate_target": _vision_locate_target,
    "window_manage": _window_manage,
    "list_windows": _list_windows,
    "window_arrange": _window_arrange,
    "filesystem_list": _filesystem_list,
    "filesystem_read": _filesystem_read,
    "filesystem_write": _filesystem_write,
    "filesystem_create_dir": _filesystem_create_dir,
    "filesystem_delete": _filesystem_delete,
    "filesystem_rename": _filesystem_rename,
    "filesystem_copy": _filesystem_copy,
    "filesystem_move": _filesystem_move,
    "filesystem_search": _filesystem_search,
    "filesystem_diff": _filesystem_diff,
    "filesystem_archive": _filesystem_archive,
    "filesystem_unarchive": _filesystem_unarchive,
    "filesystem_open": _filesystem_open,
    "web_open_url": _web_open_url,
    "web_search": _web_search,
    "web_fetch": _web_fetch,
    "terminal_run": _terminal_run,
    "memory_save": _memory_save,
    "memory_recall": _memory_recall,
    "memory_delete": _memory_delete,
    "memory_list_all": _memory_list_all,
    "media_play_pause": _media_play_pause,
    "media_next": _media_next,
    "media_prev": _media_prev,
    "clipboard_read": _clipboard_read,
    "clipboard_write": _clipboard_write,
    "office_word_open": _office_word_open,
    "registry_read": _registry_read,
    "registry_list_keys": _registry_list_keys,
    "skill_load": _skill_load,
    "office_docx_create": _office_docx_create,
    "office_pptx_create": _office_pptx_create,
    "office_xlsx_create": _office_xlsx_create,
    "app_uninstall": _app_uninstall,
    "list_processes": _list_processes,
    "media_volume_up": _media_volume_up,
    "media_volume_down": _media_volume_down,
}


def coverage() -> tuple[int, int]:
    """Devuelve (tools_with_stub, total_in_schemas)."""
    import json
    from pathlib import Path
    schemas_path = Path(__file__).parent / "tool_schemas.json"
    if not schemas_path.exists():
        return len(_STUBS), -1
    schemas = json.loads(schemas_path.read_text(encoding="utf-8"))
    names = {s["function"]["name"] for s in schemas}
    covered = len(names & set(_STUBS.keys()))
    return covered, len(names)


if __name__ == "__main__":
    covered, total = coverage()
    print(f"[stubs] coverage: {covered}/{total} tools")
    if covered < total:
        import json
        from pathlib import Path
        schemas = json.loads((Path(__file__).parent / "tool_schemas.json").read_text(encoding="utf-8"))
        names = {s["function"]["name"] for s in schemas}
        missing = names - set(_STUBS.keys())
        print(f"[stubs] missing: {sorted(missing)}")
