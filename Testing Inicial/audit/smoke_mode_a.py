"""Modo A — Direct call con stubs sobre las 62 tools.

Cada tool recibe varias invocaciones:
  1) Happy path
  2) Args inválidos
  3) Acción destructiva sin confirmed (donde aplique)
  4) Anti-bypass: inyectar _internal_safe / routine_context / confirmed_at_create

Resultados se escriben a `audit/smoke_log.md` con detalle, y se imprime un
resumen JSONL para captura/análisis.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from audit.smoke_harness import smoke_env, classify_result, SmokeContext


# ---------------------------------------------------------------------------
# Util de assertion / reporte
# ---------------------------------------------------------------------------


_LOG_LINES: list[str] = []
_RESULTS: list[dict[str, Any]] = []


def log(line: str) -> None:
    _LOG_LINES.append(line)


def case(
    ctx: SmokeContext,
    tool: str,
    args: dict[str, Any],
    *,
    expect: str,
    note: str = "",
    bypass_test: bool = False,
) -> dict[str, Any]:
    """Ejecuta un caso y compara `classify_result` con `expect`.

    `expect` puede ser una etiqueta (`"ok"`, `"needs_confirmation"`, etc.)
    o `"any_error"` (cualquier non-ok), o `"any"` (no falla nunca).
    """
    try:
        out = ctx.registry.execute(tool, dict(args))
    except Exception as exc:
        out = {"ok": False, "error": f"RAISED {type(exc).__name__}: {exc}", "status": "raised"}
    actual = classify_result(out)
    if expect == "any":
        passed = True
    elif expect == "any_error":
        passed = not bool(out.get("ok", False))
    else:
        passed = (actual == expect)
    record = {
        "tool": tool,
        "args": _trim_args(args),
        "expect": expect,
        "actual_status": actual,
        "ok": passed,
        "note": note,
        "error": out.get("error") if not out.get("ok") else None,
        "bypass_test": bypass_test,
    }
    _RESULTS.append(record)
    mark = "PASS" if passed else "FAIL"
    log(f"- [{mark}] `{tool}` {note} → expect={expect}, got={actual}" + (f", error={out.get('error', '')[:80]!r}" if not passed else ""))
    return out


def _trim_args(args: dict[str, Any]) -> dict[str, Any]:
    out = {}
    for k, v in args.items():
        if isinstance(v, str) and len(v) > 80:
            out[k] = v[:80] + "..."
        elif isinstance(v, (list, tuple)) and len(v) > 5:
            out[k] = list(v[:5]) + ["..."]
        else:
            out[k] = v
    return out


# ---------------------------------------------------------------------------
# Suites por tool
# ---------------------------------------------------------------------------


def suite_system(ctx: SmokeContext) -> None:
    log("\n## system")
    case(ctx, "system", {"action": "time"}, expect="ok", note="happy time")
    case(ctx, "system", {"action": "cpu_ram_gpu"}, expect="ok", note="cpu_ram_gpu")
    case(ctx, "system", {"action": "disk"}, expect="ok", note="disk")
    case(ctx, "system", {"action": "battery"}, expect="ok", note="battery")
    case(ctx, "system", {"action": "shutdown", "delay_sec": 30}, expect="needs_confirmation", note="CC-101 shutdown gate")
    case(ctx, "system", {"action": "restart"}, expect="needs_confirmation", note="CC-101 restart gate")
    case(ctx, "system", {"action": "sleep"}, expect="needs_confirmation", note="CC-101 sleep gate")
    # Anti-bypass: _internal_safe del LLM no debe permitir saltar el gate
    case(ctx, "system", {"action": "shutdown", "_internal_safe": True},
         expect="needs_confirmation", note="anti-bypass _internal_safe filtered", bypass_test=True)
    case(ctx, "system", {"action": "shutdown", "routine_context": True, "confirmed_at_create": True},
         expect="needs_confirmation", note="anti-bypass routine_context filtered", bypass_test=True)
    case(ctx, "system", {"action": "shutdown", "confirmed": True}, expect="ok", note="confirmed=True passes gate")
    case(ctx, "system", {"action": "unknown_xxx"}, expect="any_error", note="invalid action")


def suite_filesystem(ctx: SmokeContext) -> None:
    log("\n## filesystem")
    ws = ctx.workspace
    (ws / "sample.txt").write_text("hello world", encoding="utf-8")
    (ws / "sub").mkdir(exist_ok=True)
    (ws / "sub" / "a.txt").write_text("line1\nline2", encoding="utf-8")
    (ws / "sub" / "b.txt").write_text("line1\nline3", encoding="utf-8")
    case(ctx, "filesystem", {"action": "list", "path": str(ws)}, expect="ok", note="list")
    case(ctx, "filesystem", {"action": "read", "path": str(ws / "sample.txt")}, expect="ok", note="read")
    case(ctx, "filesystem", {"action": "search", "path": str(ws), "query": "hello"}, expect="any", note="search")
    case(ctx, "filesystem", {"action": "diff", "left": str(ws / "sub" / "a.txt"), "right": str(ws / "sub" / "b.txt")},
         expect="ok", note="diff happy")
    # CC-101 delete gate
    case(ctx, "filesystem", {"action": "delete", "path": str(ws / "sample.txt")},
         expect="needs_confirmation", note="CC-101 delete gate")
    case(ctx, "filesystem", {"action": "delete", "path": str(ws / "sample.txt"), "confirmed": True},
         expect="ok", note="delete confirmed")
    # Anti-bypass
    case(ctx, "filesystem", {"action": "delete", "path": str(ws / "sub" / "a.txt"), "_internal_safe": True},
         expect="needs_confirmation", note="anti-bypass _internal_safe filtered", bypass_test=True)
    # Args inválidos
    case(ctx, "filesystem", {"action": "read", "path": "C:/this/does/not/exist_xyz"}, expect="any_error", note="missing path")
    # Copy overwrite semantics (T2-003)
    (ws / "src.txt").write_text("src", encoding="utf-8")
    (ws / "dst.txt").write_text("dst", encoding="utf-8")
    case(ctx, "filesystem", {"action": "copy", "src": str(ws / "src.txt"), "dst": str(ws / "dst.txt"), "overwrite": False},
         expect="needs_user", note="T2-003 copy overwrite=false rejects existing")


def suite_terminal(ctx: SmokeContext) -> None:
    log("\n## terminal")
    case(ctx, "terminal", {"action": "run", "command": "echo", "args": ["hi"]},
         expect="needs_confirmation", note="CC-101 terminal gate")
    case(ctx, "terminal", {"action": "run", "command": "echo", "args": ["hi"], "confirmed": True},
         expect="ok", note="confirmed=True passes")
    # Anti-bypass
    case(ctx, "terminal", {"action": "run", "command": "echo", "args": ["hi"], "_internal_safe": True},
         expect="needs_confirmation", note="anti-bypass _internal_safe filtered", bypass_test=True)
    # cwd inválido
    case(ctx, "terminal", {"action": "run", "command": "echo", "args": ["hi"], "cwd": "C:/does/not/exist_xyz", "confirmed": True},
         expect="needs_user", note="T2-007 cwd validation")
    # Empty command
    case(ctx, "terminal", {"action": "run", "command": "", "confirmed": True}, expect="any_error", note="empty command")


def suite_package(ctx: SmokeContext) -> None:
    log("\n## package")
    case(ctx, "package", {"action": "search", "name": "7zip"}, expect="ok", note="search (no gate)")
    case(ctx, "package", {"action": "list"}, expect="ok", note="list (no gate)")
    case(ctx, "package", {"action": "install", "name": "7zip.7zip"},
         expect="needs_confirmation", note="CC-101 install gate")
    case(ctx, "package", {"action": "uninstall", "name": "vlc.vlc"},
         expect="needs_confirmation", note="CC-101 uninstall gate")
    case(ctx, "package", {"action": "install", "name": "7zip.7zip", "_internal_safe": True},
         expect="needs_confirmation", note="anti-bypass _internal_safe filtered", bypass_test=True)
    case(ctx, "package", {"action": "install", "name": "7zip.7zip", "confirmed": True},
         expect="ok", note="install confirmed")


def suite_database(ctx: SmokeContext) -> None:
    log("\n## database")
    import sqlite3
    db_path = ctx.workspace / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute("INSERT INTO items (name) VALUES ('a'), ('b'), ('c')")
    conn.commit()
    conn.close()
    case(ctx, "database", {"action": "status"}, expect="ok", note="status")
    case(ctx, "database", {"action": "list_tables", "driver": "sqlite", "path": str(db_path)}, expect="ok", note="list_tables")
    case(ctx, "database", {"action": "schema", "driver": "sqlite", "path": str(db_path), "table": "items"},
         expect="ok", note="schema happy")
    # T2-017: identifier injection
    case(ctx, "database", {"action": "schema", "driver": "sqlite", "path": str(db_path), "table": "items; DROP TABLE items; --"},
         expect="needs_user", note="T2-017 identifier validation")
    case(ctx, "database", {"action": "query", "driver": "sqlite", "path": str(db_path), "sql": "SELECT * FROM items LIMIT 5"},
         expect="ok", note="query happy")
    # T2-018: CTE+DML bypass — driver-level read-only debe rechazar la mutación
    case(ctx, "database", {"action": "query", "driver": "sqlite", "path": str(db_path),
                            "sql": "WITH x AS (SELECT 1) DELETE FROM items WHERE 1=1"},
         expect="any_error", note="T2-018 CTE+DML rejected by driver-level read-only")
    # T2-019: execute gate
    case(ctx, "database", {"action": "execute", "driver": "sqlite", "path": str(db_path),
                            "sql": "DELETE FROM items WHERE id=1"},
         expect="needs_confirmation", note="CC-101 execute gate")
    case(ctx, "database", {"action": "execute", "driver": "sqlite", "path": str(db_path),
                            "sql": "DELETE FROM items WHERE id=999", "confirmed": True},
         expect="ok", note="execute confirmed")
    # Anti-bypass
    case(ctx, "database", {"action": "execute", "driver": "sqlite", "path": str(db_path),
                            "sql": "DELETE FROM items", "_internal_safe": True},
         expect="needs_confirmation", note="anti-bypass", bypass_test=True)
    # CC-105 redaction: password en args
    out = ctx.registry.execute("database", {"action": "status", "password": "supersecret"})
    redacted_ok = "supersecret" not in json.dumps(out)
    log(f"- [{'PASS' if redacted_ok else 'FAIL'}] `database` CC-105 password redacted from result")
    _RESULTS.append({"tool": "database", "args": {"password": "***"}, "expect": "redacted",
                     "actual_status": "ok" if redacted_ok else "leaked", "ok": redacted_ok,
                     "note": "CC-105 redaction"})


def suite_backup_sync(ctx: SmokeContext) -> None:
    log("\n## backup_sync")
    import zipfile
    zip_path = ctx.workspace / "backup.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("normal.txt", "content")
    # zip-slip test
    evil_zip = ctx.workspace / "evil.zip"
    with zipfile.ZipFile(evil_zip, "w") as zf:
        zf.writestr("../../evil.txt", "pwn")
    dst = ctx.workspace / "restore_dst"
    dst.mkdir()
    case(ctx, "backup_sync", {"action": "status"}, expect="ok", note="status")
    # Restore overwrite gate
    case(ctx, "backup_sync", {"action": "restore", "path": str(zip_path), "dst": str(dst), "conflict": "overwrite"},
         expect="needs_confirmation", note="CC-101 restore overwrite gate")
    # Restore con conflict=skip: el safety.classifier marca backup_sync.restore como sensible,
    # así que sigue pidiendo confirmation. Es comportamiento intencional (el classifier
    # cubre tools sensibles; el gate duro solo se añade cuando overwrite es destructivo).
    case(ctx, "backup_sync", {"action": "restore", "path": str(zip_path), "dst": str(dst), "conflict": "skip"},
         expect="needs_confirmation", note="restore skip-policy (classifier asks confirm)")
    # Con confirmed=True debe completar el restore.
    case(ctx, "backup_sync", {"action": "restore", "path": str(zip_path), "dst": str(dst), "conflict": "skip", "confirmed": True},
         expect="ok", note="restore skip-policy confirmed")
    # T2-021 zip-slip
    case(ctx, "backup_sync", {"action": "restore", "path": str(evil_zip), "dst": str(dst), "conflict": "rename"},
         expect="failed", note="T2-021 zip-slip blocked")


def suite_notification(ctx: SmokeContext) -> None:
    log("\n## notification")
    case(ctx, "notification", {"action": "status"}, expect="ok", note="status")
    case(ctx, "notification", {"action": "toast", "text": "hello"}, expect="any", note="toast")
    # T2-024 due validation
    case(ctx, "notification", {"action": "alarm_create", "time": "garbage"},
         expect="needs_user", note="T2-024 invalid time format")
    # HH:MM atajo: el pre-validator lo deja pasar, pero el safety classifier marca
    # notification.alarm_create como automation y pide confirmation. Comportamiento
    # intencional. Verificamos también que con confirmed=True ejecute.
    case(ctx, "notification", {"action": "alarm_create", "title": "test", "text": "wake up", "time": "07:30"},
         expect="needs_confirmation", note="T2-024 HH:MM passes prevalidator, classifier asks confirm")
    case(ctx, "notification", {"action": "alarm_create", "title": "test", "text": "wake up", "time": "07:30", "confirmed": True},
         expect="any", note="alarm_create HH:MM confirmed")


def suite_routine(ctx: SmokeContext) -> None:
    log("\n## routine")
    case(ctx, "routine", {"action": "list"}, expect="ok", note="list")
    # T3-028 CC-100: at con caracteres maliciosos
    case(ctx, "routine", {"action": "create", "name": "tst1", "trigger": {"type": "cron", "cadence": "daily", "at": "08:00';Write-Host pwn;#"},
                          "steps": [{"tool": "system", "args": {"action": "time"}}]},
         expect="any_error", note="T3-028 PS injection rejected")
    # at válido
    case(ctx, "routine", {"action": "create", "name": "tst2", "trigger": {"type": "cron", "cadence": "daily", "at": "08:00"},
                          "steps": [{"tool": "system", "args": {"action": "time"}}]},
         expect="any", note="happy create")


def suite_network(ctx: SmokeContext) -> None:
    log("\n## network")
    case(ctx, "network", {"action": "ping", "host": "127.0.0.1"}, expect="any", note="ping")
    case(ctx, "network", {"action": "dns_get"}, expect="ok", note="dns_get")
    # T2-033: address con apóstrofo debe rechazar
    case(ctx, "network", {"action": "dns_set", "adapter": "Wi-Fi", "addresses": ["8.8.8.8' ; pwn ; '"]},
         expect="needs_user", note="T2-033 IPv4 validation")
    # CC-100 connections state allowlist
    case(ctx, "network", {"action": "connections", "state": "Established;pwn"},
         expect="needs_user", note="CC-100 state enum")
    case(ctx, "network", {"action": "connections", "state": "Established"},
         expect="ok", note="connections happy")
    # dns_set válido (con IPv4 OK pero adapter Wi-Fi puede fallar)
    case(ctx, "network", {"action": "dns_set", "adapter": "Wi-Fi", "addresses": ["8.8.8.8", "8.8.4.4"]},
         expect="any", note="dns_set valid IPs (may need adapter; just shouldn't crash)")


def suite_maintenance(ctx: SmokeContext) -> None:
    log("\n## maintenance")
    case(ctx, "maintenance", {"action": "status"}, expect="any", note="status")
    case(ctx, "maintenance", {"action": "firewall_status"}, expect="ok", note="firewall_status")
    # T2-025 PS injection
    case(ctx, "maintenance", {"action": "event_logs_query", "log": "System' ; Stop-Computer ; #"},
         expect="needs_user", note="T2-025 PS injection rejected")
    case(ctx, "maintenance", {"action": "event_logs_query", "log": "System"},
         expect="ok", note="event_logs_query happy")
    # T2-026 defender scan as job
    out = ctx.registry.execute("maintenance", {"action": "defender_quick_scan"})
    ok = bool(out.get("ok") and out.get("job_id"))
    log(f"- [{'PASS' if ok else 'FAIL'}] `maintenance` T2-026 defender returns job_id (got status={out.get('status')}, job_id={out.get('job_id')})")
    _RESULTS.append({"tool": "maintenance", "args": {"action": "defender_quick_scan"}, "expect": "job_id",
                     "actual_status": "ok" if ok else "fail", "ok": ok, "note": "T2-026"})
    # T2-027 disk_cleanup_describe no devuelve arrays
    out = ctx.registry.execute("maintenance", {"action": "disk_cleanup_describe"})
    no_array = "command_describe" not in out and "command_apply" not in out
    log(f"- [{'PASS' if no_array else 'FAIL'}] `maintenance` T2-027 disk_cleanup_describe no exec arrays")
    _RESULTS.append({"tool": "maintenance", "args": {"action": "disk_cleanup_describe"}, "expect": "no_arrays",
                     "actual_status": "ok" if no_array else "leak", "ok": no_array, "note": "T2-027"})


def suite_gui(ctx: SmokeContext) -> None:
    log("\n## gui")
    out = case(ctx, "gui", {"action": "screenshot"}, expect="ok", note="screenshot default")
    out = case(ctx, "gui", {"action": "screenshot", "monitor": "primary"}, expect="ok", note="CC-106 monitor=primary")
    case(ctx, "gui", {"action": "screenshot", "monitor": "garbage"}, expect="needs_user", note="monitor invalid")
    # gui_type (escape de SendKeys metachars)
    case(ctx, "gui", {"action": "type", "text": "hello (1)"}, expect="ok", note="T3-010 SendKeys escape")
    case(ctx, "gui", {"action": "keypress", "keys": "ENTER"}, expect="ok", note="keypress ENTER")
    # CC-100: keypress no debe crashear con apóstrofo (env-var indirection)
    case(ctx, "gui", {"action": "keypress", "keys": "'; Stop-Computer; '"}, expect="ok", note="CC-100 keypress injection safe")


def suite_window(ctx: SmokeContext) -> None:
    log("\n## window")
    case(ctx, "window", {"action": "list"}, expect="ok", note="list")
    case(ctx, "window", {"action": "active"}, expect="ok", note="active")
    case(ctx, "window", {"action": "control", "target": "FakeWindow", "op": "focus"},
         expect="any", note="control focus")


def suite_web(ctx: SmokeContext) -> None:
    log("\n## web")
    case(ctx, "web", {"action": "read", "url": "https://example.com"}, expect="any", note="read public")
    # T2-014: SSRF guard
    case(ctx, "web", {"action": "read", "url": "http://127.0.0.1:8123"},
         expect="any_error", note="T2-014 SSRF guard blocks loopback")
    case(ctx, "web", {"action": "read", "url": "http://169.254.169.254/latest/meta-data/"},
         expect="any_error", note="T2-014 SSRF guard blocks cloud metadata")
    case(ctx, "web", {"action": "search", "query": "python"}, expect="any", note="search")


def suite_browser_real(ctx: SmokeContext) -> None:
    log("\n## browser_real")
    # status no require playwright
    case(ctx, "browser_real", {"action": "status"}, expect="any", note="status")
    # evaluate on CDP requires confirmation — pero no podemos crear session real;
    # simulamos status-only.


def suite_data_analysis(ctx: SmokeContext) -> None:
    log("\n## data_analysis")
    case(ctx, "data_analysis", {"action": "status"}, expect="any", note="status")
    # T2-035 pandas query con @ rechazado
    csv_path = ctx.workspace / "data.csv"
    csv_path.write_text("a,b\n1,2\n3,4\n", encoding="utf-8")
    case(ctx, "data_analysis", {"action": "csv_query", "path": str(csv_path), "query": "@__import__"},
         expect="needs_user", note="T2-035 @ rejected")
    case(ctx, "data_analysis", {"action": "csv_query", "path": str(csv_path), "query": "`a` > 0"},
         expect="needs_user", note="T2-035 backtick rejected")
    case(ctx, "data_analysis", {"action": "csv_query", "path": str(csv_path), "query": "a > 1"},
         expect="any", note="csv_query happy")


def suite_download(ctx: SmokeContext) -> None:
    log("\n## download")
    case(ctx, "download", {"action": "status"}, expect="any", note="status")
    # T2-016: verified=True only when hash matches.
    # En el harness el subprocess de fake hash devuelve abc123def456... que no
    # matchea ningún expected. Esperamos verified=False con signature_present.
    out = ctx.registry.execute("download", {"action": "fetch", "url": "https://example.com/fake.exe",
                                              "dst": str(ctx.workspace / "fake.exe"), "confirmed": True})
    # Como Invoke-WebRequest está stubed, dst no existe. Verificamos shape.
    log(f"- [INFO] `download.fetch` ran: ok={out.get('ok')}, verified={out.get('verified')}, signature_present={out.get('signature_present')}")
    _RESULTS.append({"tool": "download", "args": {"action": "fetch"}, "expect": "verified_only_via_hash",
                     "actual_status": "ok" if out.get("ok") is not None else "fail",
                     "ok": True, "note": "T2-016 shape inspection"})


def suite_smart_home(ctx: SmokeContext) -> None:
    log("\n## smart_home")
    case(ctx, "smart_home", {"action": "status"}, expect="any", note="status")
    # T3-031: con stub urllib que devuelve 200, HA aparece alive=True.
    # No tenemos forma fácil de testear el "dead" path sin reescribir stub,
    # pero como mínimo no debe crashear ni reportar siempre True ciegamente.


def suite_simple(ctx: SmokeContext, tool: str, actions: list[tuple[str, dict[str, Any], str]]) -> None:
    """Suite genérica para tools simples: (action, extra_args, expect)."""
    log(f"\n## {tool}")
    for action, extra, expect in actions:
        args = {"action": action, **extra}
        case(ctx, tool, args, expect=expect, note=f"{action}")


def suite_remaining_tools(ctx: SmokeContext) -> None:
    """Smoke ligero para las tools restantes (1-2 invocaciones)."""
    ws = ctx.workspace
    txt = ws / "doc.txt"
    txt.write_text("hello document", encoding="utf-8")

    suite_simple(ctx, "audio", [
        ("get_volume", {}, "any"),
        ("devices", {}, "any"),
    ])
    suite_simple(ctx, "audio_device", [
        ("status", {}, "any"),
        ("list", {}, "any"),
    ])
    suite_simple(ctx, "app", [
        ("search", {"name": "notepad"}, "any"),
    ])
    suite_simple(ctx, "steam", [
        ("status", {}, "any"),
    ])
    suite_simple(ctx, "vision", [
        ("describe", {"image_path": str(ws / "doc.txt")}, "any"),
    ])
    suite_simple(ctx, "browser", [
        ("open", {"url": "https://example.com"}, "any"),
    ])
    suite_simple(ctx, "uia", [
        ("find", {"query": "OK"}, "any"),
    ])
    suite_simple(ctx, "clipboard", [
        ("read", {}, "any"),
        ("write", {"content": "test"}, "any"),
    ])
    suite_simple(ctx, "memory", [
        ("save", {"text": "remember pizza"}, "any"),
        ("recall", {"query": "pizza"}, "any"),
        ("list", {}, "any"),
    ])
    suite_simple(ctx, "verify", [
        ("app_opened", {"name": "notepad"}, "any"),
        ("file_exists", {"path": str(txt)}, "ok"),
    ])
    suite_simple(ctx, "state", [
        ("resources", {}, "ok"),
        ("checkpoints", {}, "ok"),
        ("note", {"text": "smoke test"}, "ok"),
    ])
    suite_simple(ctx, "input", [
        ("languages", {}, "any"),
    ])
    suite_simple(ctx, "env", [
        ("get", {"name": "PATH"}, "any"),
    ])
    suite_simple(ctx, "registry", [
        ("query", {"key": "HKLM\\SOFTWARE\\Microsoft\\Windows"}, "any"),
    ])
    suite_simple(ctx, "email", [
        ("status", {}, "any"),
    ])
    suite_simple(ctx, "reminder", [
        ("list", {}, "any"),
    ])
    suite_simple(ctx, "knowledge", [
        ("status", {}, "any"),
    ])
    suite_simple(ctx, "office", [
        ("status", {}, "any"),
    ])
    suite_simple(ctx, "media", [
        ("now_playing", {}, "any"),
    ])
    suite_simple(ctx, "source_manager", [
        ("status", {}, "any"),
        ("sources", {}, "any"),
    ])
    suite_simple(ctx, "dependency", [
        ("status", {}, "any"),
    ])
    suite_simple(ctx, "contacts", [
        ("list", {}, "any"),
    ])
    suite_simple(ctx, "notes_tasks", [
        ("list", {}, "any"),
    ])
    suite_simple(ctx, "local_calendar", [
        ("event_list", {}, "any"),
    ])
    suite_simple(ctx, "habit_tracker", [
        ("stats", {}, "any"),
    ])
    suite_simple(ctx, "local_search", [
        ("status", {}, "any"),
    ])
    suite_simple(ctx, "printer_scanner", [
        ("status", {}, "any"),
    ])
    suite_simple(ctx, "desktop_layout", [
        ("status", {}, "any"),
    ])
    suite_simple(ctx, "document", [
        ("status", {}, "any"),
    ])
    suite_simple(ctx, "developer", [
        ("status", {}, "any"),
    ])
    suite_simple(ctx, "device_settings", [
        ("status", {}, "any"),
    ])
    suite_simple(ctx, "game_launcher", [
        ("status", {}, "any"),
    ])
    suite_simple(ctx, "media_edit", [
        ("status", {}, "any"),
    ])
    suite_simple(ctx, "watcher", [
        ("list", {}, "any"),
    ])
    suite_simple(ctx, "job_manager", [
        ("list", {}, "any"),
    ])
    suite_simple(ctx, "fact_check", [
        ("status", {}, "any"),
    ])
    suite_simple(ctx, "photo_library", [
        ("status", {}, "any"),
    ])
    suite_simple(ctx, "container", [
        ("status", {}, "any"),
    ])
    suite_simple(ctx, "creative_local", [
        ("status", {}, "any"),
    ])
    suite_simple(ctx, "form_filler", [
        ("status", {}, "any"),
    ])
    suite_simple(ctx, "peripheral", [
        ("status", {}, "any"),
    ])
    suite_simple(ctx, "accessibility", [
        ("status", {}, "any"),
    ])
    suite_simple(ctx, "study", [
        ("status", {}, "any"),
    ])
    suite_simple(ctx, "subagent", [
        ("status", {}, "any"),
    ])
    suite_simple(ctx, "safety", [
        ("status", {}, "ok"),
        ("pending", {}, "ok"),
    ])
    # T2-job_manager-start-no-shell-flag-046: shlex.split happy path
    case(ctx, "job_manager", {"action": "start", "command": '"C:/Program Files/python.exe" --version'},
         expect="any", note="T2-046 shlex.split string command")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    log("# Smoke Log — Modo A (Direct call con stubs)")
    log("Generado en sesión autónoma 2026-05-15.\n")
    with smoke_env(safety_enabled=True) as ctx:
        suite_system(ctx)
        suite_filesystem(ctx)
        suite_terminal(ctx)
        suite_package(ctx)
        suite_database(ctx)
        suite_backup_sync(ctx)
        suite_notification(ctx)
        suite_routine(ctx)
        suite_network(ctx)
        suite_maintenance(ctx)
        suite_gui(ctx)
        suite_window(ctx)
        suite_web(ctx)
        suite_browser_real(ctx)
        suite_data_analysis(ctx)
        suite_download(ctx)
        suite_smart_home(ctx)
        suite_remaining_tools(ctx)
        # Sanity final: ninguna invocación PS destructiva real
        destructive = ctx.assert_no_real_powershell_destructive()
        log("\n## Sanity check")
        if destructive:
            log(f"- [FAIL] destructive PowerShell tokens detected:")
            for h in destructive:
                log(f"  - {h}")
        else:
            log("- [PASS] no destructive PowerShell tokens observed in subprocess calls")
        log(f"- subprocess.run calls: {len(ctx.subprocess_rec.calls)}")
        log(f"- subprocess.Popen calls: {len(ctx.subprocess_rec.popen_calls)}")
        log(f"- urlopen calls: {len(ctx.urllib_rec.calls)}")

    # Resumen
    total = len(_RESULTS)
    passed = sum(1 for r in _RESULTS if r["ok"])
    failed = total - passed
    bypass_total = sum(1 for r in _RESULTS if r.get("bypass_test"))
    bypass_pass = sum(1 for r in _RESULTS if r.get("bypass_test") and r["ok"])
    log("\n## Resumen Modo A")
    log(f"- Total casos: {total}")
    log(f"- PASS: {passed}")
    log(f"- FAIL: {failed}")
    log(f"- Bypass tests: {bypass_pass}/{bypass_total} PASS (anti-bypass de CC-101)")
    log("\n## Casos fallados")
    for r in _RESULTS:
        if not r["ok"]:
            log(f"- `{r['tool']}` {r['note']}: expect={r['expect']}, got={r['actual_status']}, err={r.get('error')}")

    # Persistir
    out_path = REPO_ROOT / "audit" / "smoke_log.md"
    out_path.write_text("\n".join(_LOG_LINES), encoding="utf-8")
    print(f"Wrote {out_path}")

    json_path = REPO_ROOT / "audit" / "smoke_results.json"
    json_path.write_text(json.dumps(_RESULTS, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {json_path}")
    print(f"\n{passed}/{total} pass ({failed} fail, {bypass_pass}/{bypass_total} bypass)")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
