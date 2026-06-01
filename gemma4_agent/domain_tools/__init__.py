"""Higher-level local domain tools for the Gemma4 agent."""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
import webbrowser
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from .._ps import (
    PSValidationError,
    RX_DAY_OF_WEEK,
    RX_HHMM,
    RX_ISO_DATETIME,
    RX_LOG_NAME,
    RX_SQL_IDENT,
    RX_TCP_STATE,
    is_ipv4,
    is_ipv6,
    parse_ps_json,
    ps_safe_literal,
)
from ..memory_pkg.state import AgentState


Executor = Callable[[str, dict[str, Any]], dict[str, Any]]


# CC-105 + CC-101: unified in Sprint 4 — bodies live in :mod:`._shared`
# (was duplicated against tools._redact_sensitive / ToolRegistry._hard_gate,
# see audit §2.2). _ok/_err added 2026-05-27 (audit R3 sprint): were also
# triplicated (domain_tools/ops_tools/tools, byte-identical bodies).
from .._shared import (  # noqa: E402
    _err,
    _ok,
    hard_gate as _hard_gate,
    redact_sensitive as _redact_credentials,
)

# R3 sprint 2026-05-28: helpers cross-cutting movidos a domain_tools_helpers.py
# (rompe los ~26 ciclos falsos-positivos del analizador estático que el patrón
# lazy-import del R2 generaba). Re-exportamos acá para que callers existentes
# (`from gemma4_agent import domain_tools as dt; dt._safe_name(...)` y
# `from gemma4_agent.domain_tools import _existing_path`) sigan funcionando.
from .helpers import (  # noqa: F401, E402
    _existing_path,
    _find_resource,
    _find_routine,
    _find_soundvolumeview,
    _json_or_none,
    _parse_due_iso,
    _pid_alive,
    _pid_owned_by,
    _powershell_json,
    _ps_quote,
    _resources_by_kind,
    _safe_name,
    _update_resource_metadata,
)



# Office (PPTX/DOCX/XLSX) - extraído a domain_tools_office.py
# (R2 sprint 2026-05-28). 7 símbolos.
from .office import (  # noqa: F401
    _create_document,
    _create_presentation,
    _create_spreadsheet,
    _inspect_office_file,
    _output_path,
    _slides_from_args,
    office_tool,
)


def audio_device_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    action = str(args.get("action") or "list").casefold()
    if action in {"status", "list"}:
        helper = _find_soundvolumeview()
        svv_devices = _svv_list_devices() if helper else []
        devices = svv_devices if svv_devices else _audio_endpoints()
        defaults = _svv_current_defaults(svv_devices) if svv_devices else {}
        return _ok(
            devices=devices,
            count=len(devices),
            defaults=defaults,
            soundvolumeview=str(helper) if helper else None,
            can_set_default=bool(helper),
            install_hint="Download SoundVolumeView.zip from NirSoft and set GEMMA4_SOUNDVOLUMEVIEW to the exe path.",
        )
    if action == "snapshot":
        helper = _find_soundvolumeview()
        svv_devices = _svv_list_devices() if helper else []
        defaults = _svv_current_defaults(svv_devices) if svv_devices else {}
        rollback = _audio_rollback_steps(defaults)
        checkpoint = state.checkpoint(
            "audio device snapshot",
            rollback=rollback,
            metadata={"devices": svv_devices or _audio_endpoints(), "defaults": defaults, "helper": str(helper) if helper else None},
        )
        return _ok(
            snapshot=checkpoint.get("checkpoint"),
            defaults=defaults,
            rollback_steps=len(rollback),
            note="Snapshot saves device list and per-role defaults. Restore replays /SetDefault using SoundVolumeView." if rollback else "Defaults not detected; install SoundVolumeView for restorable snapshots.",
        )
    if action == "restore":
        return _restore_audio_default(args, state)
    if action in {"set_default", "set_default_communications"}:
        return _set_default_audio_device(args, state, communications=action == "set_default_communications")
    if action == "set_app_route":
        return _audio_set_app_route(args, state)
    if action == "get_app_routes":
        return _audio_get_app_routes()
    return _err(
        "unknown audio_device action", action=action,
        valid_actions=[
            "status", "list", "snapshot", "set_default", "set_default_app",
            "set_app_route", "rollback",
        ],
        status="needs_user",
    )


def _audio_set_app_route(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    """Route a specific app to a specific audio device via SoundVolumeView /SetAppDefault.

    SoundVolumeView CLI syntax (NirSoft 2020):
        SoundVolumeView.exe /SetAppDefault "<device-or-render-path>" <role> "<process.exe>"
    Role: 0=Console, 1=Multimedia, 2=Communications.
    """
    helper = _find_soundvolumeview()
    if not helper:
        return _err(
            "set_app_route requires SoundVolumeView",
            status="needs_dependency",
            install_hint="Download SoundVolumeView.zip from NirSoft and set GEMMA4_SOUNDVOLUMEVIEW.",
        )
    device = str(args.get("device") or args.get("name") or "").strip()
    app = str(args.get("app") or args.get("process") or "").strip()
    if not device or not app:
        return _err("set_app_route requires device (or 'default') and app (process name or pid)")
    direction = str(args.get("direction") or "render").casefold()  # render|capture
    role = str(args.get("role") or "1")  # 1=Multimedia by default
    if role not in {"0", "1", "2", "all"}:
        return _err("role must be 0|1|2|all (Console|Multimedia|Communications|all)")

    # If the user just gave a friendly device name, the CLI expects either the
    # full "Device\Speakers\Render" path or the friendly name from /sjson.
    # We accept both: if device looks like "<vendor>\\<dev>\\<dir>" pass through,
    # else resolve via the device list.
    if device.casefold() in {"default", "system_default"}:
        # SoundVolumeView treats empty/Default specially: pass "Default" literal.
        target_arg = "DefaultRenderDevice" if direction == "render" else "DefaultCaptureDevice"
    else:
        target_arg = device

    before_routes = _audio_get_app_routes().get("routes", [])
    rollback_step = {"tool": "audio_device", "args": {"action": "set_app_route", "device": "DefaultRenderDevice", "app": app, "role": role, "direction": direction}}
    checkpoint = state.checkpoint(
        f"audio_device set_app_route {app}->{device}",
        rollback=[rollback_step],
        metadata={"app": app, "target": target_arg, "role": role, "direction": direction, "before": before_routes},
    )
    proc = subprocess.run(
        [str(helper), "/SetAppDefault", target_arg, role, app],
        capture_output=True, text=True, timeout=20,
    )
    after_routes = _audio_get_app_routes().get("routes", [])
    matched_after = [r for r in after_routes if str(r.get("process") or "").casefold() == app.casefold()]
    return _ok(
        app=app, target=target_arg, role=role, direction=direction,
        helper=str(helper),
        exit_code=proc.returncode, stdout=proc.stdout.strip()[:500], stderr=proc.stderr[-500:],
        before=before_routes[:30], after=after_routes[:30],
        matched=matched_after,
        checkpoint=checkpoint.get("checkpoint"),
        verified=proc.returncode == 0,
        status="done" if proc.returncode == 0 else "needs_verification",
        note="Per-app overrides survive across sessions but only apply to the named process; relaunching the app picks up the new default.",
    )


def _audio_get_app_routes() -> dict[str, Any]:
    """List per-app audio overrides via SoundVolumeView /sjson (Type=Application rows)."""
    helper = _find_soundvolumeview()
    if not helper:
        return _err(
            "get_app_routes requires SoundVolumeView",
            status="needs_dependency",
            install_hint="Download SoundVolumeView.zip from NirSoft and set GEMMA4_SOUNDVOLUMEVIEW.",
        )
    import tempfile
    fd, tmp_path = tempfile.mkstemp(suffix=".json", prefix="svv_apps_")
    os.close(fd)
    try:
        proc = subprocess.run([str(helper), "/sjson", tmp_path], capture_output=True, text=True, timeout=20)
        if proc.returncode != 0:
            return _err("SoundVolumeView /sjson failed", stderr=proc.stderr, exit_code=proc.returncode)
        raw = Path(tmp_path).read_text(encoding="utf-16", errors="replace").lstrip("﻿").strip()
        if not raw:
            raw = Path(tmp_path).read_text(encoding="utf-8", errors="replace").lstrip("﻿").strip()
        if not raw:
            return _ok(routes=[], count=0)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return _err("SoundVolumeView returned invalid JSON")
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
    if isinstance(data, dict):
        data = [data]
    routes: list[dict[str, Any]] = []
    for entry in data if isinstance(data, list) else []:
        if not isinstance(entry, dict):
            continue
        entry_type = str(entry.get("Type") or "").casefold()
        if entry_type not in {"application", "application volume"}:
            continue
        routes.append({
            "process": entry.get("Process Path") or entry.get("Name"),
            "name": entry.get("Name"),
            "device_name": entry.get("Device Name") or entry.get("Default Endpoint"),
            "default_endpoint": entry.get("Default Endpoint"),
            "default_communications_endpoint": entry.get("Default Communications Endpoint"),
            "muted": entry.get("Muted"),
            "volume_percent": entry.get("Volume Percent") or entry.get("Volume dB"),
        })
    return _ok(routes=routes, count=len(routes))


# Notification entry-point + helpers - extraídos a domain_tools_notifications.py
# (R2 sprint 2026-05-27). domain_tools.py: ~-300 LOC. Re-export AL TOP para que
# tools.py linea 52 () y los call-
# sites internos sigan funcionando sin cambio.
from .notifications import (  # noqa: F401  (re-export por compat)
    _NotificationDueError,
    _delete_notification,
    _enrich_notification_resource,
    _ensure_notification_runner,
    _kind_for_notification_action,
    _notification_due,
    _notification_history,
    _schedule_notification,
    _show_message_box,
    _update_notification,
    notification_tool,
)


# Routine entry-point + import_triggercmd + destructive command detection
# - extraído a domain_tools_routine.py (R2 sprint 2026-05-28). 13 símbolos.
# Re-export AL TOP para que tools.py linea 57 y agent.py linea 1019
# (_looks_destructive) sigan funcionando sin cambio. _find_routine y
# _register_routine_process_watcher quedan en domain_tools.py (los importa
# routine_tool lazy).
from .routine import (  # noqa: F401  (re-export por compat)
    _DESTRUCTIVE_COMMAND_TOKENS,
    _append_routine_run,
    _build_routine_trigger_ps,
    _detect_python_executable,
    _enrich_routine_resource,
    _looks_destructive,
    _register_routine_scheduled_task,
    _routine_history,
    _routine_task_name,
    _terminal_args_for,
    _unregister_routine_scheduled_task,
    import_triggercmd_entries,
    routine_tool,
)


# Smart Home (HomeAssistant + MQTT) - extraído a domain_tools_smart_home.py
# (R2 sprint 2026-05-28). 10 funciones. Re-export para compat (tools.py linea 58).
from .smart_home import (  # noqa: F401  (re-export por compat)
    _hass_alive,
    _hass_area_control,
    _hass_area_list,
    _hass_call_service,
    _hass_get_state,
    _hass_request,
    _hass_set_state,
    _hass_states,
    _smart_home_mqtt_publish,
    smart_home_tool,
)


# Study (flashcards + SM-2) - extraído a domain_tools_study.py
# (R2 sprint 2026-05-28). 12 funciones (entry + 11 helpers).
from .study import (  # noqa: F401  (re-export por compat)
    _study_card_add,
    _study_card_delete,
    _study_card_list,
    _study_connect,
    _study_deck_create,
    _study_deck_delete,
    _study_deck_list,
    _study_due,
    _study_review,
    _study_stats,
    _today_iso,
    study_tool,
)


# Accessibility (Magnifier/Narrator/settings) - extraído a
# domain_tools_accessibility.py (R2 sprint 2026-05-28). 4 funciones.
from .accessibility import (  # noqa: F401  (re-export por compat)
    _accessibility_kill,
    _accessibility_launch,
    _process_running,
    accessibility_tool,
)


# Peripheral (USB/HID/controllers/PnP) - extraído a domain_tools_peripheral.py
# (R2 sprint 2026-05-28). 7 funciones.
from .peripheral import (  # noqa: F401
    _peripheral_controller_status,
    _peripheral_device_problems,
    _peripheral_device_toggle,
    _peripheral_hid_list,
    _peripheral_run_json,
    _peripheral_usb_list,
    peripheral_tool,
)


# Form Filler - extraído a domain_tools_form_filler.py
# (R2 sprint 2026-05-28). 6 funciones.
from .form_filler import (  # noqa: F401
    _form_apply,
    _form_discover,
    _form_match_field,
    _form_plan,
    _form_submit,
    form_filler_tool,
)


# Creative Local (ComfyUI) - extraído a domain_tools_creative_local.py
# (R2 sprint 2026-05-28). 9 funciones.
from .creative_local import (  # noqa: F401
    _comfy_alive,
    _comfy_get_json,
    _comfy_interrupt,
    _comfy_models,
    _comfy_post_json,
    _comfy_queue,
    _comfy_result,
    _comfy_submit,
    _comfy_wait,
    creative_local_tool,
)


# Database (sqlite/postgres/mysql) - extraído a domain_tools_database.py
# (R2 sprint 2026-05-28). 10 funciones (entry + connect + list/schema/query/
# execute/export + read-only enforcement + helpers).
from .database import (  # noqa: F401
    _apply_readonly,
    _database_connect,
    _database_execute,
    _database_export_csv,
    _database_list_tables,
    _database_query,
    _database_schema,
    _is_read_only_sql,
    _release_readonly,
    _scalarize,
    database_tool,
)


# Container (Docker / docker-compose) - extraído a domain_tools_container.py
# (R2 sprint 2026-05-28). 8 funciones.
from .container import (  # noqa: F401
    _container_compose,
    _container_exec,
    _container_images,
    _container_inspect,
    _container_lifecycle,
    _container_logs,
    _container_ps,
    container_tool,
)


# Photo Library - extraído a domain_tools_photo_library.py
# (R2 sprint 2026-05-28). 8 funciones + _PHOTO_EXTS.
from .photo_library import (  # noqa: F401
    _PHOTO_EXTS,
    _photo_exif,
    _photo_extract_date,
    _photo_find_by_date,
    _photo_group_by_date,
    _photo_open_exif,
    _photo_scan,
    _photo_thumbnails,
    photo_library_tool,
)


# Fact Check (TF-IDF + cosine, pure-Python) - extraído a
# domain_tools_fact_check.py (R2 sprint 2026-05-28).
from .fact_check import (  # noqa: F401
    _NEGATION_CUES_EN,
    _NEGATION_CUES_ES,
    _fact_check_chunks,
    _fact_check_rank,
    fact_check_tool,
)


# Data Analysis (pandas + matplotlib Agg) - extraído a
# domain_tools_data_analysis.py (R2 sprint 2026-05-28). 8 funciones.
from .data_analysis import (  # noqa: F401
    _data_csv_describe,
    _data_csv_head,
    _data_csv_profile,
    _data_csv_query,
    _data_csv_to_xlsx,
    _data_load_df,
    _data_plot,
    data_analysis_tool,
)


# Network diagnostics - extraído a domain_tools_network.py
# (R2 sprint 2026-05-28). 9 funciones (entry + 8 helpers).
from .network import (  # noqa: F401
    _network_connections,
    _network_dns_get,
    _network_dns_resolve,
    _network_dns_set,
    _network_ping,
    _network_port_check,
    _network_public_ip,
    _network_traceroute,
    network_tool,
)


# Watcher (file/url/process) - extraído a domain_tools_watcher.py
# (R2 sprint 2026-05-28). 9 funciones. _register_routine_process_watcher se
# usa por routine_tool — éste lo importa lazy desde domain_tools que ahora
# re-exporta desde aquí.
from .watcher import (  # noqa: F401
    _file_snapshot,
    _process_snapshot,
    _register_routine_process_watcher,
    _register_watcher_scheduled_task,
    _url_snapshot,
    _watcher_check,
    _watcher_register_file,
    _watcher_register_url,
    watcher_tool,
)


# Job Manager (subprocess tracking) - extraído a domain_tools_job_manager.py
# (R2 sprint 2026-05-28). 4 funciones.
from .job_manager import (  # noqa: F401
    _job_manager_cancel,
    _job_manager_log,
    _job_manager_start,
    job_manager_tool,
)


# _pid_owned_by + _pid_alive — extraídos a domain_tools_helpers.py
# (R3 sprint 2026-05-28).


# Maintenance (Win Update / Defender / Firewall / Services / Event Logs /
# Restore Point) - extraído a domain_tools_maintenance.py (R2 sprint 2026-05-28).
from .maintenance import (  # noqa: F401
    _maintenance_defender_quick_scan,
    _maintenance_defender_status,
    _maintenance_event_logs,
    _maintenance_firewall_status,
    _maintenance_restore_point_create,
    _maintenance_service_control,
    _maintenance_service_status,
    _maintenance_services_list,
    _maintenance_windows_update_status,
    maintenance_tool,
)


# Media Edit (ffmpeg) - extraído a domain_tools_media_edit.py
# (R2 sprint 2026-05-28). 12 funciones.
from .media_edit import (  # noqa: F401
    _media_edit_concat,
    _media_edit_extract_audio,
    _media_edit_input,
    _media_edit_normalize,
    _media_edit_output,
    _media_edit_probe,
    _media_edit_subtitles_extract,
    _media_edit_thumbnail,
    _media_edit_transcode,
    _media_edit_trim,
    _run_ffmpeg,
    media_edit_tool,
)


# Game Launcher (Epic/GOG/Xbox/Riot) - extraído a domain_tools_game_launcher.py
# (R2 sprint 2026-05-28). 10 funciones.
from .game_launcher import (  # noqa: F401
    _discover_epic_games,
    _discover_gog_games,
    _discover_riot_games,
    _discover_xbox_games,
    _epic_manifests_dir,
    _game_launcher_discover,
    _game_launcher_launch,
    _gog_registry_has_games,
    _riot_install_db,
    game_launcher_tool,
)


# Device settings compound entry - extraído a domain_tools_device_settings.py
# (R2 sprint 2026-05-28). Despacha a domain_tools_wifi/bluetooth y a los
# display/power helpers que también viven en domain_tools_device_settings.
from .device_settings import device_settings_tool  # noqa: F401


# WiFi domain tools - extraídos a domain_tools_wifi.py (R2 sprint 2026-05-27).
# Las 9 funciones _device_wifi_* + _wifi_match_score + _resolve_wifi_target +
# _xml_escape + _WIFI_FILLER viven ahora en su propio módulo. Re-exportamos acá
# para que callers existentes (test_wifi_resolve.py:
# `from gemma4_agent import domain_tools as dt; dt._device_wifi_X`) sigan
# funcionando sin tocar nada. Cuando los callers migren a importar
# `gemma4_agent.domain_tools_wifi` directo, este re-export se puede borrar.
from .wifi import (  # noqa: F401  (re-export por compat)
    _WIFI_FILLER,
    _device_wifi_add_profile,
    _device_wifi_connect,
    _device_wifi_delete_profile,
    _device_wifi_disconnect,
    _device_wifi_profiles,
    _device_wifi_scan,
    _device_wifi_status,
    _resolve_wifi_target,
    _wifi_match_score,
    _xml_escape,
)


# Bluetooth domain tool - extraído a domain_tools_bluetooth.py (R2 sprint
# 2026-05-27). Un sólo método hoy; se aísla para que cuando aparezca más
# (pair/disconnect/audio-routing) tenga su casa.
from .bluetooth import _device_bluetooth_status  # noqa: F401


# Display + power-plan helpers - extraídos a domain_tools_device_settings.py
# (R2 sprint 2026-05-28). El compound device_settings_tool también vive ahí.
from .device_settings import (  # noqa: F401
    _device_display_list,
    _device_power_plan_get,
    _device_power_plan_list,
    _device_power_plan_set,
)


# Developer workflows (detect/test/lint/format/git/dev_server) - extraído a
# domain_tools_developer.py (R2 sprint 2026-05-28). 8 funciones.
from .developer import (  # noqa: F401
    _developer_command,
    _developer_git,
    _developer_project_detect,
    _developer_project_root,
    _developer_run,
    _developer_start_dev_server,
    _developer_stop_dev_server,
    developer_tool,
)


# Document parsing/extraction - extraído a domain_tools_document.py
# (R2 sprint 2026-05-28). 13 funciones (entry + 12 helpers PDF/DOCX/XLSX/PPTX/
# HTML/text + OCR Tesseract).
from .document import (  # noqa: F401
    _document_compare,
    _document_extract_docx,
    _document_extract_html,
    _document_extract_images,
    _document_extract_pdf,
    _document_extract_pptx,
    _document_extract_tables,
    _document_extract_text,
    _document_extract_xlsx,
    _document_ocr_pdf,
    _document_ocr_pdf_with_fitz,
    _document_ocr_pdf_with_pdf2image,
    document_tool,
)


# active_phrase_triggers — movido a domain_tools_routine.py (R3 sprint 2026-05-28).
# Re-export para compat (agent.py + server.py lo importan por este nombre).
from .routine import active_phrase_triggers  # noqa: F401, E402


# Routine helpers - extraídos a domain_tools_routine.py (R2 sprint 2026-05-28).
# El cluster de helpers de Scheduled Task vivía acá; el re-export está en el
# bloque del entry point routine_tool más arriba (~línea 285).


def _find_vlc_executable() -> str | None:
    """Localiza vlc.exe en PATH o en las rutas tipicas de instalacion Windows.

    winget install VideoLAN.VLC no agrega vlc al PATH por default, asi que
    shutil.which("vlc") falla aunque este instalado. Probamos las rutas
    estandar como fallback.
    """
    vlc = shutil.which("vlc") or shutil.which("vlc.exe")
    if vlc:
        return vlc
    # Rutas standard de VLC en Windows
    candidates = [
        r"C:\Program Files\VideoLAN\VLC\vlc.exe",
        r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe",
    ]
    for c in candidates:
        if Path(c).is_file():
            return c
    return None


def _find_spotify_executable() -> str | None:
    """Localiza Spotify.exe. Spotify desktop instala en %APPDATA%\\Spotify\\
    por default (Microsoft Store version usa shell:AppsFolder).
    """
    spotify = shutil.which("spotify") or shutil.which("spotify.exe")
    if spotify:
        return spotify
    candidates = [
        Path.home() / "AppData" / "Roaming" / "Spotify" / "Spotify.exe",
        Path("C:/Program Files/WindowsApps") / "Spotify.exe",  # raro pero posible
    ]
    for c in candidates:
        try:
            if c.is_file():
                return str(c)
        except OSError:
            continue
    return None


# Streaming platforms — registro centralizado de cada plataforma.
# Cada entry: (canonical_name, normalized_aliases, UWP package_family_name,
#              exe_path_candidates, deeplink_template, web_url_template,
#              install_hint, post_open_note)
#
# {q} en templates se reemplaza con la query URL-encoded.
#
# Notas:
#   - UWP package family names recolectados de docs publicas; pueden variar
#     levemente por region. Usamos shell:AppsFolder\<pfn>!App via `start`.
#     Si el pfn no matchea, Windows no abre nada y caemos a web.
#   - Deeplinks: solo Spotify y Disney+ tienen scheme propio confiable.
#     Netflix/HBO/Prime no exponen schemes documentados → siempre web.
#   - Web URLs verificadas en 2025-2026 (post-rebrand HBO Max -> Max).
# Streaming platform specs. Each entry:
#   aliases:           set of user-friendly names that map to this canonical key.
#   uwp_pfn / exe_paths: how to detect the app on Windows (UWP package or EXE).
#   deeplink:          URI scheme template if the platform has one (Spotify only).
#   web_url:           landing URL. If template has {q}, it's substituted with
#                      url-encoded query and the page loads search results
#                      directly. If no {q}, this is the search page where the
#                      query must be TYPED into the input (Disney+/HBO Max).
#   web_search_via_url: True if {q} substitution gives a functional URL.
#   playback:          dict with selectors for Playwright/CDP automation:
#                       - search_input:   CSS selector for the search <input>
#                       - result_card:    selector for the first result card
#                                          (usually an <a> with the title link)
#                       - play_button:    selector for the Play CTA on detail page
#                       - title_url_pattern: regex describing detail URLs that
#                                            qualify as "watch deep links" — used
#                                            for the title→URL cache.
#   install_hint:      ms-windows-store URI for the user to install if they want.
#   post_open_note:    short note returned in the tool result.
#
# Sources for selectors and URLs: see docs/research/streaming/streaming_playback_field_guide_2026.md (research
# 2026-05-16) — Netflix data-uia family, Disney+/HBO Max data-testid/aria,
# Prime Video data-automation-id. All marked "needs live test" by the research
# are CANDIDATES that the agent tries in order; the first that matches wins.
#
# IMPORTANT: the search_shortcut field was REMOVED (2026-05-16) — no platform
# has a reliable global hotkey to open search ("/" and "s" do NOT work on
# Netflix/Disney+/HBO Max despite earlier code assuming so). For Disney+/HBO
# Max we MUST land on the search page URL and type into the input via DOM
# or via gui.type after focusing the input.
_STREAMING_PLATFORMS: dict[str, dict[str, Any]] = {
    "spotify": {
        "aliases": {"spotify"},
        "uwp_pfn": "SpotifyAB.SpotifyMusic_zpdnekdrzrea0",
        "exe_paths": [
            Path.home() / "AppData" / "Roaming" / "Spotify" / "Spotify.exe",
        ],
        "deeplink": "spotify:search:{q}",
        "web_url": "https://open.spotify.com/search/{q}",
        "web_search_via_url": True,
        "playback": {},  # Spotify uses deeplink + Enter; no web selectors needed
        "install_hint": "winget install Spotify.Spotify",
        "post_open_note": (
            "Spotify opened with search results. App does NOT auto-play. "
            "User must press Enter / click a track."
        ),
    },
    "netflix": {
        "aliases": {"netflix"},
        "uwp_pfn": "4DF9E0F8.Netflix_mcm4njqhnhss8",
        "exe_paths": [],
        "deeplink": None,
        # Verified via CDP probe 2026-05-16:
        # - `?q=` works post-login.
        # - search results: a[data-uia='search-gallery-video-card'] with href
        #   `/search?q=X&jbv=<title_id>`. Click opens DP (mini-modal).
        # - In the DP modal, [data-uia='play-button'] navigates to /watch/<id>
        #   and starts playback.
        # - profile-gate may appear first time per session.
        "web_url": "https://www.netflix.com/search?q={q}",
        "web_search_via_url": True,
        "playback": {
            "profile_picker_check": "[data-uia='profile-gate'], [data-uia='action-select-profile+secondary']",
            "profile_item_anchor": "a[data-uia='action-select-profile+secondary']",
            "search_input": [
                "input[data-uia='search-box-input']",
                "input[placeholder*='buscar' i]",
            ],
            "result_card": [
                "a[data-uia='search-gallery-video-card']",
                "a[data-uia*='video-card']",
                "a[data-uia='search-suggestion-item-link']",
            ],
            # En Netflix, click card abre detalle. Despues hay que click el
            # play-button del modal/detail para iniciar playback (/watch/).
            "play_button": [
                "[data-uia='play-button']",
                "a[data-uia*='play']",
                "button[data-uia*='play']",
                "a[href*='/watch/']",
            ],
            "click_card_starts_playback": False,
            "title_url_pattern": r"netflix\.com/(?:[a-z-]+/)?(?:watch|title)/(\d+)",
        },
        "install_hint": "Install Netflix from Microsoft Store: ms-windows-store://pdp/?productid=9wzdncrfj3tj",
        "post_open_note": (
            "Netflix opened with search results. User clicks a title to play."
        ),
    },
    "disney": {
        "aliases": {"disney", "disney+", "disneyplus", "disney_plus", "disney plus"},
        "uwp_pfn": "Disney.37853FC22B2CE_6rarf9sa4v8jt",
        "exe_paths": [],
        "deeplink": None,
        # Verified via CDP probe 2026-05-16: /es-419/browse/search is the
        # ONLY URL that works (logged in). Other /search variants return 404.
        # F-009: template + default_locale para permitir override segun region
        # del user (es-es, en-us, etc). `web_url` se mantiene como fallback
        # cuando no se puede resolver locale dinamicamente.
        "web_url": "https://www.disneyplus.com/es-419/browse/search",
        "web_url_template": "https://www.disneyplus.com/{locale}/browse/search",
        "default_locale": "es-419",
        "web_search_via_url": False,
        "playback": {
            "search_input": [
                "input[type='search']",
                "input[name='search input']",
                "input[placeholder*='buscar' i]",
                "input[placeholder*='ulo' i]",  # placeholder contains 'Título...'
            ],
            "result_card": [
                "a[data-testid='set-item']",
                "a[href*='/browse/entity-']",
            ],
            "play_button": [
                "[data-testid='playback-action-button']",
                "button[aria-label*='Ver ahora' i]",
                "button[aria-label*='VER AHORA' i]",
                "button[aria-label*='Reproducir' i]",
            ],
            "click_card_starts_playback": False,
            "title_url_pattern": r"disneyplus\.com/[a-z-]+/browse/entity-([A-Za-z0-9_-]+)",
        },
        "install_hint": "Install Disney+ from Microsoft Store: ms-windows-store://pdp/?productid=9NXQXXLFST89",
        "post_open_note": (
            "Disney+ search page opened. Type the title in the search box."
        ),
    },
    "hbo_max": {
        # Rebrand back to HBO Max on 9 July 2025. Verified via CDP probe
        # 2026-05-16: play.hbomax.com/search?q= works; play.max.com redirects
        # to play.hbomax.com. Anchors use data-testid='<uuid>_tile'.
        "aliases": {"hbo_max", "hbo max", "hbomax", "max", "hbo"},
        "uwp_pfn": None,
        "exe_paths": [],
        "deeplink": None,
        "web_url": "https://play.hbomax.com/search?q={q}",
        "web_search_via_url": True,
        "playback": {
            "search_input": [
                "input[type='search']",
                "input[aria-label*='buscar' i]",
                "input[data-testid*='search' i]",
            ],
            "result_card": [
                "a[data-testid$='_tile'][href*='/movie/']",
                "a[data-testid$='_tile'][href*='/show/']",
                "a[data-testid$='_tile'][href*='/series/']",
                "a[data-testid$='_tile']",
                "a[href*='/movie/']",
                "a[href*='/show/']",
                "a[href*='/series/']",
                "a[href*='/feature/']",
            ],
            "play_button": [
                "button[data-testid='play_button']",
                "button[data-testid='playButton']",
                "button[aria-label*='Reproducir' i]",
                "button[aria-label*='Ver' i]",
                "button[aria-label*='Play' i]",
            ],
            "click_card_starts_playback": False,
            "title_url_pattern": r"hbomax\.com/(?:movie|show|series|feature)/([A-Za-z0-9-]+)",
        },
        "install_hint": "HBO Max is web-only on Windows; browser will open.",
        "post_open_note": (
            "HBO Max opened. Type the title in the search box."
        ),
    },
    "prime_video": {
        "aliases": {"prime_video", "prime video", "primevideo", "amazon prime",
                     "amazon_prime", "amazon", "prime"},
        "uwp_pfn": "AmazonVideo.PrimeVideo_pwbj9vvecjh7j",
        "exe_paths": [],
        "deeplink": None,
        # Verified via CDP probe 2026-05-16: ?phrase= works, cards via
        # 'article a[href*=/detail/]'. Detail page auto-opens an inline
        # player (data-testid='draper-player') — explicit play often
        # unnecessary because preview already runs.
        "web_url": "https://www.primevideo.com/search/ref=atv_nb_sr?phrase={q}",
        "web_search_via_url": True,
        "playback": {
            "search_input": [
                "input[name='phrase']",
                "input[type='search']",
                "input[placeholder*='buscar' i]",
            ],
            "result_card": [
                "article a[href*='/detail/']",
                "a[href*='/detail/']",
            ],
            # Prime Video tiene varios botones con aria 'Play' que NO son
            # de iniciar playback (Close Player, mute, etc). Probar primero
            # los explicitos. Si todos fallan, asumir que el detail page
            # ya esta auto-playing (es lo que hace Prime).
            "play_button": [
                "button[data-automation-id='playButton']",
                "button[aria-label*='Watch now' i]",
                "button[aria-label*='Ver ahora' i]",
                "button[aria-label*='Reproducir ahora' i]",
            ],
            # En Prime, el detail page abre un mini-player con auto-play.
            # Markamos card-click como playback-starter (best-effort).
            "click_card_starts_playback": True,
            "title_url_pattern": r"primevideo\.com/(?:region/[a-z]+/)?detail/([A-Z0-9]+)",
        },
        "install_hint": "Install Prime Video from Microsoft Store: ms-windows-store://pdp/?productid=9P6RC76MSMMJ",
        "post_open_note": (
            "Prime Video opened with search results. User clicks a title to play."
        ),
    },
}


def _resolve_streaming_web_url(
    spec: dict[str, Any],
    *,
    state: AgentState | None = None,
) -> str:
    """F-009: resuelve la URL web del provider contemplando locale.

    Si el spec define `web_url_template` (con `{locale}` placeholder) y un
    `default_locale`, formatea segun el locale del user. Si no hay state o
    no se puede resolver, usa el default_locale o cae al web_url estatico.

    Pendiente futuro: agregar `state.user_locale` para soportar override
    real por region. Actualmente siempre usa el default_locale del spec.
    """
    template = spec.get("web_url_template")
    default_locale = spec.get("default_locale")
    if template and default_locale and "{locale}" in template:
        # TODO: cuando exista state.user_locale, usarlo aca con fallback.
        locale = default_locale
        if state is not None:
            user_locale = getattr(state, "user_locale", None)
            if isinstance(user_locale, str) and user_locale.strip():
                locale = user_locale.strip()
        return template.format(locale=locale)
    return str(spec.get("web_url") or "")


def _resolve_streaming_provider(provider_raw: str) -> tuple[str, dict[str, Any]] | None:
    """Mapea un alias del LLM (e.g. 'disney+') al provider canonico + spec.

    Returns (canonical_name, spec_dict) o None si no matchea.
    """
    p = str(provider_raw or "").strip().lower().replace("-", "_")
    for canonical, spec in _STREAMING_PLATFORMS.items():
        if p == canonical or p in spec["aliases"]:
            return canonical, spec
    return None


def _find_streaming_app(spec: dict[str, Any]) -> dict[str, str | None]:
    """Detecta si la app de streaming esta instalada como UWP o como EXE.

    Returns dict con keys:
      - "kind": 'uwp' | 'exe' | None
      - "launch_target": el string que se pasara a `start` (shell:AppsFolder\\<pfn>!App o path al exe)
    """
    # 1. EXE paths (preferencia: spotify desktop, etc.)
    for exe_path in spec.get("exe_paths", []):
        try:
            if exe_path.is_file():
                return {"kind": "exe", "launch_target": str(exe_path)}
        except OSError:
            continue
    # 2. UWP package via Get-AppxPackage check
    pfn = spec.get("uwp_pfn")
    if pfn and os.name == "nt":
        try:
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                  f"if (Get-AppxPackage -Name '{pfn.split('_')[0]}') {{ Write-Output yes }}"],
                capture_output=True, text=True, timeout=3,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if proc.returncode == 0 and "yes" in (proc.stdout or "").lower():
                return {"kind": "uwp", "launch_target": f"shell:AppsFolder\\{pfn}!App"}
        except (OSError, subprocess.TimeoutExpired):
            pass
    return {"kind": None, "launch_target": None}


# ---------------------------------------------------------------------------
# Streaming preferences (profile per platform)
# ---------------------------------------------------------------------------
# El user tiene varios perfiles en Netflix/Disney+/HBO/Prime (el "¿Quién está
# viendo?" picker). Para que el auto-play funcione sin preguntar cada vez,
# guardamos el nombre del perfil preferido por plataforma en agent state.

def _get_streaming_preference(state: AgentState | None, provider: str) -> str | None:
    """Lee el perfil guardado para una plataforma. None si no existe."""
    if state is None:
        return None
    try:
        data = state._load()  # noqa: SLF001 — state interno
        resources = data.get("resources", {})
    except Exception:
        return None
    for res in resources.values():
        if not isinstance(res, dict):
            continue
        if res.get("kind") != "streaming_preference":
            continue
        meta = res.get("metadata") or {}
        if str(meta.get("provider", "")).lower() == provider.lower():
            return str(meta.get("profile_name") or "").strip() or None
    return None


# Blacklist de "perfiles" obviamente invalidos. Defense in depth: si el
# extractor de profile_name falla y pasa algo como "Hola" o "Quien eres",
# el writer al state lo rechaza igual. Evita corrupcion persistente del
# store de preferencias.
_INVALID_PROFILE_NAMES = frozenset({
    "hola", "holas", "hello", "hi", "hey",
    "buenos dias", "buenas tardes", "buenas noches",
    "adios", "bye", "chau", "chao",
    "gracias", "thanks",
    "ok", "okay", "vale", "si", "no",
    "ayuda", "help",
    "quien eres", "quien soy", "que eres", "que sos",
    "quién eres", "qué eres",
    "que tal", "que pasa", "como estas",
    "qué tal", "cómo estás",
    "x", "xx", "xxx", "test", "prueba", "default",
})


def _is_valid_profile_name(name: str) -> bool:
    """True si parece un nombre real de perfil de streaming.

    Rechaza:
      - Vacio / solo espacios.
      - Demasiado largo (>30 chars).
      - Greetings / preguntas conocidas (Hola, Quien eres, etc).
      - Solo caracteres no-alfanumericos.
      - Strings con caracteres de tool_call / system markers.
    """
    if not name or not name.strip():
        return False
    n = name.strip()
    if len(n) > 30:
        return False
    if n.lower() in _INVALID_PROFILE_NAMES:
        return False
    # Debe tener al menos UNA letra (cubre nombres en cualquier idioma).
    if not any(ch.isalpha() for ch in n):
        return False
    # Tokens de system / tool_call leak.
    for bad in ("<|", "|>", "tool_call", "system:", "user:", "assistant:"):
        if bad in n:
            return False
    return True


# Query "generica" = el user pidio musica/una cancion SIN nombrar un titulo.
# Detector de query "generica" (pidio musica SIN nombrar titulo/artista).
#
# DISEÑO (minimo hardcode, regla de uso universal): NO enumeramos frases. Un
# pedido generico es uno cuyas palabras-de-contenido son TODAS "tokens
# genericos" (palabra de musica, cuantificador vago, o verbo de play). Si
# queda alguna palabra que no es generica, es un titulo/artista -> NO generico.
# Asi "pon una cancion", "reproduce algo de musica", "play some music" y
# "metele cualquier cosa" matchean sin listarlas; "pon Bad Bunny" no (queda
# "bad"/"bunny"). Y aunque el detector FALLE, el fallback UIA igual reproduce
# el top result de buscar esa frase (validado 2026-05-22) — no es punto critico.
#
# RAICES de contenido (play-verb / music-noun / cuantificador-vago). Se
# matchean por PREFIJO (startswith) para cubrir conjugaciones — por eso aca van
# SOLO tokens >=3 letras y semanticamente fuertes (nunca preposiciones cortas
# como "de", que matchearian "Despacito").
_GENERIC_CONTENT_ROOTS = (
    # play verbs
    "pon", "reproduc", "toca", "play", "put", "metel", "echa", "dale",
    # music nouns
    "cancion", "canción", "music", "música", "rola", "tema", "song", "tune",
    "cancao", "canzon", "chanson", "musik", "lied",
    # vague quantifiers / "anything"
    "algo", "cualquier", "random", "aleatori", "something", "anything",
    "whatever", "some", "qualquer", "qualcosa", "quelque", "irgend",
)
# FILLER de funcion (articulos/preposiciones/pronombres). Se matchean EXACTO
# (no prefijo) para no pisar titulos. Multi-idioma, pero es funcion pura.
_GENERIC_FILLER_WORDS = frozenset({
    "una", "un", "uno", "unos", "unas", "de", "del", "la", "el", "lo", "las",
    "los", "que", "sea", "cosa", "a", "me", "le", "nos", "te", "asi",
    "any", "of", "the", "for", "uma", "um", "qualsiasi",
    "une", "des", "du", "di", "una", "uno",  # fr/it articles
})


def _is_generic_music_query(query: str) -> bool:
    """True si el query NO nombra un titulo/artista concreto.

    Heuristica estructural (sin lista de frases): generico sii TODAS las
    palabras son o bien una RAIZ de contenido generica (por prefijo) o FILLER
    de funcion (exacto). Una sola palabra "real" (titulo/artista) hace False.
    Query vacia = generico. Cap de longitud para frases largas (probable titulo).
    """
    if not query or not query.strip():
        return True
    norm = " ".join(query.strip().lower().split()).strip(" .!?¡¿,;:\"'")
    words = [w for w in norm.split() if w]
    if not words:
        return True
    if len(words) > 6:
        return False
    for w in words:
        if w in _GENERIC_FILLER_WORDS:
            continue
        if any(w.startswith(root) for root in _GENERIC_CONTENT_ROOTS):
            continue
        return False  # palabra real -> hay un titulo/artista
    return True


def _get_spotify_username(state: AgentState | None) -> str | None:
    """Lee el username de Spotify guardado (para deeplink de Liked Songs).
    Reusa el store de streaming_preference con provider='spotify_user'."""
    return _get_streaming_preference(state, "spotify_user")


def _set_streaming_preference(
    state: AgentState | None, provider: str, profile_name: str,
) -> dict[str, Any] | None:
    """Guarda el nombre del perfil preferido para una plataforma.

    Validacion: rechaza nombres que parecen saludos/preguntas (defense in
    depth contra extractor permisivo). Si name es invalido, devuelve dict
    con ok=False para que el caller pueda manejar.

    Si ya existe una preferencia para el mismo provider, la actualiza.
    Devuelve el resource creado/actualizado o None si state es None.
    """
    if state is None:
        return None
    if not _is_valid_profile_name(profile_name):
        return {
            "ok": False,
            "error": f"refused to save invalid profile_name {profile_name!r}",
            "reason": "looks like a greeting / question / unrelated text",
        }
    profile_name = profile_name.strip()
    # Buscar existente.
    try:
        data = state._load()  # noqa: SLF001
        resources = data.get("resources", {})
    except Exception:
        resources = {}
    existing_id = None
    for rid, res in resources.items():
        if (isinstance(res, dict)
                and res.get("kind") == "streaming_preference"
                and str((res.get("metadata") or {}).get("provider", "")).lower() == provider.lower()):
            existing_id = rid
            break
    if existing_id:
        return state.update_resource(
            existing_id,
            metadata_patch={"profile_name": profile_name, "updated_at": datetime.now().isoformat()},
        )
    return state.register_resource(
        "streaming_preference",
        f"{provider} profile",
        metadata={"provider": provider, "profile_name": profile_name,
                  "created_at": datetime.now().isoformat()},
    )


# ---------------------------------------------------------------------------
# Title -> Direct URL cache (the highest-leverage optimization per compass
# research 2026-05-16: bypasses search-page entirely on subsequent plays).
# ---------------------------------------------------------------------------
# On first play we land on the search/detail page. After the user (or the
# agent's selectors) navigates to the actual title detail page, we capture
# the canonical URL and store it as a `streaming_title_cache` resource so
# subsequent calls jump straight to it.

def _normalize_title_key(title: str) -> str:
    """Normaliza titulo para lookup case+accent-insensitive."""
    s = unicodedata.normalize("NFKD", (title or "").strip().lower())
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    # Colapsa espacios y signos triviales para que "Daredevil: Born Again"
    # matchee "daredevil born again".
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _get_cached_title_url(
    state: AgentState | None, provider: str, query: str,
) -> str | None:
    """Devuelve la URL deep-link cacheada para (provider, title) o None."""
    if state is None or not query:
        return None
    key = _normalize_title_key(query)
    if not key:
        return None
    try:
        data = state._load()  # noqa: SLF001
        resources = data.get("resources", {})
    except Exception:
        return None
    for res in resources.values():
        if not isinstance(res, dict):
            continue
        if res.get("kind") != "streaming_title_cache":
            continue
        meta = res.get("metadata") or {}
        if (str(meta.get("provider", "")).lower() == provider.lower()
                and str(meta.get("title_key", "")) == key):
            url = str(meta.get("url") or "").strip()
            if url:
                return url
    return None


def _set_cached_title_url(
    state: AgentState | None, provider: str, query: str, url: str,
) -> None:
    """Persist (provider, title) -> URL. Overwrites if exists. Best-effort."""
    if state is None or not query or not url:
        return
    key = _normalize_title_key(query)
    if not key:
        return
    try:
        data = state._load()  # noqa: SLF001
        resources = data.get("resources", {})
    except Exception:
        return
    # Look for existing entry.
    for rid, res in resources.items():
        if not isinstance(res, dict):
            continue
        if res.get("kind") != "streaming_title_cache":
            continue
        meta = res.get("metadata") or {}
        if (str(meta.get("provider", "")).lower() == provider.lower()
                and str(meta.get("title_key", "")) == key):
            try:
                state.update_resource(
                    rid,
                    metadata_patch={
                        "url": url,
                        "updated_at": datetime.now().isoformat(),
                    },
                )
            except Exception:
                pass
            return
    # Not found -> create.
    try:
        state.register_resource(
            "streaming_title_cache",
            f"{provider}: {query[:60]}",
            metadata={
                "provider": provider,
                "title_query": query,
                "title_key": key,
                "url": url,
                "created_at": datetime.now().isoformat(),
            },
        )
    except Exception:
        pass


# Chromium-based browsers we know how to launch with CDP. Each entry:
#   - process_name: as seen in Get-Process (without .exe)
#   - exe_candidates: filesystem paths to look up the executable
#   - profile_subpath: user_data_dir relative to a Windows env root
#   - profile_root: which env var holds the root (APPDATA / LOCALAPPDATA)
_CDP_BROWSER_CANDIDATES: list[dict[str, Any]] = [
    {
        "key": "opera_gx",
        "progid_match": ("opera gx", "operagx"),
        "process_name": "opera",
        "exe_candidates": [
            r"%LOCALAPPDATA%\Programs\Opera GX\opera.exe",
        ],
        "profile_root": "APPDATA",
        "profile_subpath": r"Opera Software\Opera GX Stable",
    },
    {
        "key": "opera",
        "progid_match": ("operastable", "opera"),
        "process_name": "opera",
        "exe_candidates": [
            r"%LOCALAPPDATA%\Programs\Opera\opera.exe",
        ],
        "profile_root": "APPDATA",
        "profile_subpath": r"Opera Software\Opera Stable",
    },
    {
        "key": "chrome",
        "progid_match": ("chrome",),
        "process_name": "chrome",
        "exe_candidates": [
            r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
            r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
            r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe",
        ],
        "profile_root": "LOCALAPPDATA",
        "profile_subpath": r"Google\Chrome\User Data",
    },
    {
        "key": "edge",
        "progid_match": ("edge", "msedge"),
        "process_name": "msedge",
        "exe_candidates": [
            r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe",
            r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe",
        ],
        "profile_root": "LOCALAPPDATA",
        "profile_subpath": r"Microsoft\Edge\User Data",
    },
    {
        "key": "brave",
        "progid_match": ("brave",),
        "process_name": "brave",
        "exe_candidates": [
            r"%ProgramFiles%\BraveSoftware\Brave-Browser\Application\brave.exe",
            r"%ProgramFiles(x86)%\BraveSoftware\Brave-Browser\Application\brave.exe",
            r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe",
        ],
        "profile_root": "LOCALAPPDATA",
        "profile_subpath": r"BraveSoftware\Brave-Browser\User Data",
    },
]


def _cdp_endpoint_alive(timeout: float = 1.5) -> bool:
    """Quick check: does http://127.0.0.1:9222/json/version respond?"""
    import urllib.request
    try:
        with urllib.request.urlopen(
            "http://127.0.0.1:9222/json/version", timeout=timeout,
        ) as resp:
            return resp.status == 200
    except Exception:
        return False


def _detect_default_browser_progid() -> str:
    """Read the user's default browser from the Windows registry. Returns
    lowercase ProgId or '' if unknown."""
    if os.name != "nt":
        return ""
    try:
        import winreg
        key_path = (
            r"SOFTWARE\Microsoft\Windows\Shell\Associations\UrlAssociations"
            r"\https\UserChoice"
        )
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as k:
            val, _ = winreg.QueryValueEx(k, "ProgId")
            return str(val or "").lower()
    except Exception:
        return ""


def _running_chromium_process_names() -> set[str]:
    """Set de process names (sin .exe, lowercase) de los Chromium vivos AHORA.

    User-reported 2026-05-22: el agente abria Opera GX (default del registro)
    aunque el user tenia Chrome abierto y logueado en Disney/Netflix. El
    navegador donde vive la sesion es el que esta CORRIENDO, no el default
    nominal del registro. Devolvemos los process names para que
    `_pick_cdp_browser` priorice relanzar ese mismo navegador (preservando su
    --user-data-dir, asi conserva login + tabs via session restore).
    """
    if os.name != "nt":
        return set()
    names = {c["process_name"] for c in _CDP_BROWSER_CANDIDATES}
    try:
        # Una sola pasada: lista todos los procesos cuyo nombre matchea un
        # candidato. -ErrorAction SilentlyContinue evita ruido si ninguno corre.
        name_args = ",".join(sorted(names))
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
              f"Get-Process {name_args} -ErrorAction SilentlyContinue | "
              "Select-Object -ExpandProperty ProcessName -Unique"],
            capture_output=True, text=True, timeout=4,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return {
            line.strip().lower()
            for line in (res.stdout or "").splitlines()
            if line.strip()
        }
    except Exception:
        return set()


def _pick_cdp_browser() -> dict[str, Any] | None:
    """Choose which Chromium browser to launch with CDP. Priority (user
    decision 2026-05-22 — respetar el navegador default del user):
       1. The user's DEFAULT browser if it's currently RUNNING — relaunch it with
          the same --user-data-dir to preserve the logged-in session + tabs.
       2. The user's default browser even if not running (launch fresh).
       3. Any other Chromium that IS running (fallback: the session likely lives
          in whatever browser is open).
       4. The first installed candidate (Opera GX > Opera > Chrome > Edge > Brave).
    Returns the candidate dict (with `exe` and `user_data_dir` resolved) or None."""
    running = _running_chromium_process_names()
    progid = _detect_default_browser_progid()

    default_cand: dict[str, Any] | None = None
    if progid:
        for cand in _CDP_BROWSER_CANDIDATES:
            if any(m in progid for m in cand["progid_match"]):
                default_cand = cand
                break

    ordered: list[dict[str, Any]] = []
    # 1+2. Default del user primero (corriendo o no — lo relanzamos igual).
    if default_cand is not None:
        ordered.append(default_cand)
    # 3. Otros Chromium vivos (donde puede estar la sesion si el default no corre).
    if running:
        for cand in _CDP_BROWSER_CANDIDATES:
            if cand["process_name"].lower() in running and cand not in ordered:
                ordered.append(cand)
    # 4. Resto de instalados.
    for cand in _CDP_BROWSER_CANDIDATES:
        if cand not in ordered:
            ordered.append(cand)

    for cand in ordered:
        for raw in cand["exe_candidates"]:
            exe = os.path.expandvars(raw)
            if Path(exe).is_file():
                root = os.environ.get(cand["profile_root"], "")
                user_data_dir = str(Path(root) / cand["profile_subpath"])
                return {**cand, "exe": exe, "user_data_dir": user_data_dir}
    return None


def _ensure_cdp_browser(timeout_total: float = 10.0) -> dict[str, Any]:
    """Garantiza que CDP este disponible en :9222. Si no, cierra el browser
    Chromium del user y lo relanza con --remote-debugging-port=9222 + su
    propio --user-data-dir (preserva tabs/login).

    Returns dict con keys:
      - cdp_ok: bool
      - action: 'already_running' | 'relaunched' | 'launched' | 'failed' | 'unsupported' | 'disabled'
      - browser_key: str | None
      - reason: str | None
    """
    if _cdp_endpoint_alive():
        return {"cdp_ok": True, "action": "already_running",
                "browser_key": None, "reason": None}

    # Test isolation: pytest mockea webbrowser.open al nivel del tool, pero
    # _ensure_cdp_browser opera FUERA del executor (urllib + subprocess
    # reales). Para no matar Opera del dev cada vez que corren tests,
    # respetar GEMMA4_DISABLE_AUTO_CDP_LAUNCH=1 o detectar una corrida de tests.
    #
    # BUG 2026-05-22 (trace #847): `"unittest" in sys.modules` y
    # `"pytest" in sys.modules` son FALSOS POSITIVOS en produccion — torch /
    # transformers / numpy.testing importan `unittest` al cargar, asi que el
    # runtime de voz SIEMPRE creia estar en tests y NUNCA lanzaba CDP -> Disney
    # caia a webbrowser.open (abria la pagina pero nunca tipeaba la query).
    # Verificado: importar torch/transformers mete unittest en sys.modules.
    # Señal confiable de "corriendo DENTRO de un test": la env var
    # PYTEST_CURRENT_TEST (pytest la setea por test) o flags explicitos. La
    # presencia del modulo importado NO sirve.
    in_test_env = (
        os.environ.get("GEMMA4_DISABLE_AUTO_CDP_LAUNCH") == "1"
        or "PYTEST_CURRENT_TEST" in os.environ
        or os.environ.get("CI") == "true"
    )
    if in_test_env:
        return {"cdp_ok": False, "action": "disabled",
                "browser_key": None,
                "reason": "auto-launch disabled (test env var or GEMMA4_DISABLE_AUTO_CDP_LAUNCH)"}

    if os.name != "nt":
        return {"cdp_ok": False, "action": "unsupported",
                "browser_key": None,
                "reason": "auto-launch only implemented on Windows"}

    cand = _pick_cdp_browser()
    if not cand:
        return {"cdp_ok": False, "action": "failed",
                "browser_key": None,
                "reason": "no Chromium browser found (Opera/Chrome/Edge/Brave)"}

    exe = cand["exe"]
    user_data_dir = cand["user_data_dir"]
    proc_name = cand["process_name"]
    relaunched = False

    # Cerrar instancias corriendo del mismo browser. Si tenia tabs abiertas,
    # Opera/Chrome las restauran al abrir de nuevo (session restore default).
    # F-003: cierre graceful primero (CloseMainWindow envia WM_CLOSE -> browser
    # guarda session/forms), 3s de espera, solo entonces Stop-Process -Force
    # como ultimo recurso. Reduce perdida de trabajo del user.
    import time as _time
    try:
        running = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
              f"Get-Process {proc_name} -ErrorAction SilentlyContinue | "
              "Select-Object -ExpandProperty Id"],
            capture_output=True, text=True, timeout=4,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        pids = [p.strip() for p in (running.stdout or "").splitlines() if p.strip()]
        if pids:
            # 1. Pedir cierre suave (WM_CLOSE) a cada proceso.
            subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                  f"$procs = Get-Process {proc_name} -ErrorAction SilentlyContinue; "
                  "foreach ($p in $procs) { try { $p.CloseMainWindow() | Out-Null } catch {} }"],
                capture_output=True, text=True, timeout=6,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            _time.sleep(3.0)  # dar tiempo al browser para flush session/forms
            # 2. Si quedan vivos, force-kill.
            still = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                  f"Get-Process {proc_name} -ErrorAction SilentlyContinue | "
                  "Select-Object -ExpandProperty Id"],
                capture_output=True, text=True, timeout=4,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            still_pids = [p.strip() for p in (still.stdout or "").splitlines() if p.strip()]
            if still_pids:
                subprocess.run(
                    ["powershell", "-NoProfile", "-Command",
                      f"Get-Process {proc_name} -ErrorAction SilentlyContinue | "
                      "Stop-Process -Force -ErrorAction SilentlyContinue"],
                    capture_output=True, text=True, timeout=6,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                _time.sleep(1.5)  # let OS clean up handles
            relaunched = True
    except Exception:
        pass

    # Lanzar el browser con CDP.
    try:
        subprocess.Popen(
            [exe, "--remote-debugging-port=9222",
              f"--user-data-dir={user_data_dir}"],
            creationflags=getattr(subprocess, "DETACHED_PROCESS", 0)
                          | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
            close_fds=True,
        )
    except Exception as exc:
        return {"cdp_ok": False, "action": "failed",
                "browser_key": cand["key"],
                "reason": f"launch failed: {exc}"}

    # Poll endpoint hasta ~8s.
    deadline = _time.time() + max(3.0, timeout_total - 2.0)
    while _time.time() < deadline:
        if _cdp_endpoint_alive(timeout=1.0):
            return {"cdp_ok": True,
                    "action": "relaunched" if relaunched else "launched",
                    "browser_key": cand["key"], "reason": None}
        _time.sleep(0.6)

    return {"cdp_ok": False, "action": "failed",
            "browser_key": cand["key"],
            "reason": "browser launched but CDP endpoint never came up"}


def _try_cdp_attach(executor: Executor) -> dict[str, Any]:
    """Intenta conectarse al Chrome del user via CDP (puerto 9222).
    Si no esta disponible, intenta lanzar el browser default con CDP
    automaticamente y reintenta.

    Returns dict con keys:
      - "available": bool — True si se conecto exitosamente.
      - "session_id": str — id de la sesion de browser_real.
      - "reason": str | None — por que no se conecto si available=False.
      - "launched_browser": str | None — clave del browser auto-lanzado, si aplica.
    """
    # 0. Garantizar que el browser CDP este corriendo (auto-launch si hace falta).
    ensure = _ensure_cdp_browser()
    if not ensure["cdp_ok"]:
        return {
            "available": False, "session_id": None,
            "reason": f"CDP unavailable: {ensure['reason']}",
            "launched_browser": None,
        }

    try:
        r = executor("browser_real", {
            "action": "connect_cdp",
            "endpoint": "http://127.0.0.1:9222",
            "session_id": "streaming",
        })
        if r.get("ok"):
            return {"available": True, "session_id": "streaming",
                    "reason": None,
                    "launched_browser": ensure.get("browser_key"),
                    "browser_action": ensure.get("action")}
        return {
            "available": False, "session_id": None,
            "reason": str(r.get("error") or "connect_cdp returned not-ok"),
            "launched_browser": ensure.get("browser_key"),
        }
    except Exception as exc:
        return {
            "available": False, "session_id": None,
            "reason": f"connect_cdp exception: {exc}",
        }


def _streaming_cdp_play(
    executor: Executor,
    canonical: str,
    spec: dict[str, Any],
    query: str,
    profile_name: str,
    web_url: str,
    web_search_via_url: bool,
    cached_url: str | None,
    state: AgentState | None = None,
) -> dict[str, Any]:
    """CDP-first playback via Playwright + selectores REALES (verificados
    via probe 2026-05-16 contra Opera GX logueado).

    Flow:
      0. Si cached_url -> goto directo. Si click_card_starts_playback=True
         (Netflix), la URL cacheada YA es /watch/<id> y ya reproduce. Sino
         try click play.
      1. Goto search URL.
      2. Si profile_picker_check selector existe -> click profile_name
         (Netflix presenta profile-gate por sesion).
      3. Si NOT web_search_via_url -> fill search input.
      4. Esperar render + click primer result_card.
      5. Capturar detail URL (cache si matchea title_url_pattern).
      6. Si click_card_starts_playback=True -> ya reproduce. Sino:
         click play_button.
    """
    import time as _time
    playback = spec.get("playback") or {}
    selectors_input = playback.get("search_input") or []
    selectors_card = playback.get("result_card") or []
    selectors_play = playback.get("play_button") or []
    profile_picker_check = playback.get("profile_picker_check")
    profile_item_anchor = playback.get("profile_item_anchor")
    click_starts_playback = bool(playback.get("click_card_starts_playback"))
    title_pattern = playback.get("title_url_pattern")

    steps: list[str] = []
    session_id = "streaming"

    def _try_selectors(action: str, sel_list: list[str], **extras) -> dict[str, Any]:
        last_err = None
        for sel in sel_list:
            try:
                r = executor("browser_real", {
                    "action": action,
                    "session_id": session_id,
                    "selector": sel,
                    "timeout_sec": extras.get("timeout_sec", 6),
                    **{k: v for k, v in extras.items() if k != "timeout_sec"},
                })
                if r.get("ok"):
                    return {"ok": True, "selector": sel, "result": r}
                last_err = r.get("error")
            except Exception as exc:
                last_err = str(exc)
        return {"ok": False, "error": last_err or "all selectors failed"}

    def _get_current_url() -> str:
        try:
            r = executor("browser_real", {
                "action": "active_tab", "session_id": session_id,
            })
            if r.get("ok") and isinstance(r.get("active_tab"), dict):
                return str(r["active_tab"].get("url") or "")
        except Exception:
            pass
        return ""

    def _bring_browser_to_front() -> None:
        """User-reported bug 2026-05-16 21:23: after media play, the browser
        window stays in background and the user can't see what's playing.
        Issue a `window focus` with the provider name as query — Opera's
        page title contains "Disney+" / "Netflix" / etc. for the active tab,
        so this matches and brings it forward (auto-maximizes if small).
        """
        try:
            provider_title = {
                "disney": "Disney+",
                "netflix": "Netflix",
                "hbo_max": "Max",
                "prime_video": "Prime Video",
            }.get(canonical, canonical)
            executor("window", {"action": "focus", "query": provider_title})
            steps.append(f"focused_window:{provider_title}")
        except Exception:
            pass

    # 1. Navegar. Usamos new_tab=True para NO sobreescribir lo que el user
    # tenia abierto. headless=False matches la sesion CDP (Opera GX).
    target_url = cached_url or web_url
    via_cache = bool(cached_url)
    try:
        goto = executor("browser_real", {
            "action": "goto",
            "session_id": session_id,
            "url": target_url,
            "wait_until": "domcontentloaded",
            "timeout_sec": 25,
            "headless": False,
            "new_tab": True,
        })
        if not goto.get("ok"):
            return {
                "player_started": False, "attempted_play": False,
                "steps": steps,
                "abort_reason": f"goto {target_url!r} failed: {goto.get('error')}",
                "via_cache": via_cache,
            }
        steps.append(f"goto:{target_url[:80]}{' (cached)' if via_cache else ''}")
    except Exception as exc:
        return {
            "player_started": False, "attempted_play": False,
            "steps": steps,
            "abort_reason": f"goto exception: {exc}",
            "via_cache": via_cache,
        }
    # F-012: reducido 5.5s -> 2.5s. _try_selectors con timeout_sec interno
    # actua como wait_for_selector con polling, asi que el sleep inicial
    # solo necesita cubrir el DOMContentLoaded -> JS-hydration gap minimo.
    _time.sleep(2.5)

    # FAST PATH: cached URL para Netflix etc.
    if via_cache:
        if click_starts_playback:
            # Cached URL es ya /watch/<id> — esta reproduciendo.
            steps.append("cache_url_loaded_autoplay_expected")
            _bring_browser_to_front()
            return {
                "player_started": True, "attempted_play": True,
                "steps": steps, "abort_reason": None, "via_cache": True,
            }
        # Para otros, intentar el play button.
        play_res = _try_selectors("click", selectors_play, timeout_sec=8)
        if play_res["ok"]:
            steps.append(f"clicked_play_cached:{play_res['selector']}")
            _bring_browser_to_front()
            return {
                "player_started": True, "attempted_play": True,
                "steps": steps, "abort_reason": None, "via_cache": True,
            }
        # Cache URL cargada — usualmente significa que el video ya esta en
        # detail page o auto-reproduciendo. Mark como exito best-effort.
        _bring_browser_to_front()
        return {
            "player_started": True, "attempted_play": True,
            "steps": steps + ["cache_url_loaded_no_play_button"],
            "abort_reason": None, "via_cache": True,
        }

    # 2. Profile picker (Netflix). Sin `evaluate` (que requiere
    # confirmation en CDP). Click directo con selector :has-text(profile)
    # con timeout corto. Si no hay picker, falla rapido y seguimos.
    if profile_picker_check and profile_item_anchor and profile_name:
        prof_selectors = [
            f"{profile_item_anchor}:has-text({profile_name!r})",
        ]
        prof_res = _try_selectors("click", prof_selectors, timeout_sec=3)
        if prof_res["ok"]:
            steps.append(f"clicked_profile:{profile_name}")
            # F-012: reducido 8s -> 4s. Selector polling del fill/click
            # subsiguiente cubre el resto de espera con timeout interno.
            _time.sleep(4.0)
        else:
            # No vimos profile picker (Netflix recuerda sesion) -> continue.
            steps.append("profile_pick_not_needed_or_failed")

    # 3. Si la URL NO tiene query (Disney+), rellenar input.
    if not web_search_via_url:
        fill_res = _try_selectors("fill", selectors_input, value=query,
                                    timeout_sec=10)
        if not fill_res["ok"]:
            return {
                "player_started": False, "attempted_play": False,
                "steps": steps,
                "abort_reason": f"could not find search input: {fill_res['error']}",
                "via_cache": False,
                "hint": "Search page may have changed structure. Selectors: "
                        + ", ".join(selectors_input),
            }
        steps.append(f"filled_search:{fill_res['selector']}")
        # F-012: reducido 4s -> 2s post-fill. El polling del click_card
        # subsiguiente (timeout_sec=12) absorbe el resto del wait.
        _time.sleep(2.0)

    # 4. Click primer result card.
    # F-012: removido 'extra render time' de 2s — _try_selectors timeout=12
    # ya hace polling activo del selector.
    card_res = _try_selectors("click", selectors_card, timeout_sec=12)
    if not card_res["ok"]:
        return {
            "player_started": False, "attempted_play": False,
            "steps": steps,
            "abort_reason": f"could not click first result card: {card_res['error']}",
            "via_cache": False,
            "hint": "Selectors: " + ", ".join(selectors_card),
        }
    steps.append(f"clicked_first_result:{card_res['selector']}")
    # F-012: reducido 5s -> 2.5s post-card-click. El click_play subsiguiente
    # (timeout_sec=10) cubre el resto con polling activo.
    _time.sleep(2.5)

    # 5. Cache URL post-click.
    detail_url = _get_current_url()
    if detail_url and title_pattern:
        try:
            import re as _re
            if _re.search(title_pattern, detail_url):
                _set_cached_title_url(state, canonical, query, detail_url)
                steps.append(f"cached_title_url:{detail_url[:80]}")
        except Exception:
            pass

    # 6. Para plataformas donde click card YA reproduce (Netflix) -> done.
    if click_starts_playback:
        steps.append("playback_started_via_card_click")
        _bring_browser_to_front()
        return {
            "player_started": True, "attempted_play": True,
            "steps": steps, "abort_reason": None, "via_cache": False,
            "detail_url": detail_url,
        }

    # 7. Click play button.
    play_res = _try_selectors("click", selectors_play, timeout_sec=10)
    if play_res["ok"]:
        steps.append(f"clicked_play:{play_res['selector']}")
        _bring_browser_to_front()
        return {
            "player_started": True, "attempted_play": True,
            "steps": steps, "abort_reason": None, "via_cache": False,
            "detail_url": detail_url,
        }
    # Llegamos al detail page pero no encontramos un Play button explicito.
    # Solo asumimos playback automatico cuando spec lo declara explicit
    # (Prime: click del card abre el player). Para Disney/Netflix/HBO ser
    # honestos: attempted_play=True pero player_started=False.
    # Igual traer el browser al frente: el user al menos ve el detail page.
    _bring_browser_to_front()
    return {
        "player_started": click_starts_playback,
        "attempted_play": True,
        "steps": steps + ["detail_page_reached_no_explicit_play_button"],
        "abort_reason": None, "via_cache": False,
        "detail_url": detail_url,
    }


def _streaming_web_auto_play(
    executor: Executor,
    canonical: str,
    query: str,
    profile_name: str,
    wait_seconds: float,
    *,
    spec: dict[str, Any] | None = None,
    web_url: str | None = None,
    web_search_via_url: bool = True,
    state: AgentState | None = None,
) -> dict[str, Any]:
    """Auto-play en web para Netflix/Disney+/HBO Max/Prime Video.

    Estrategia (compass research 2026-05-16):
      1. Intentar CDP attach al Chrome real del user (puerto 9222).
         Si funciona: DOM-level via Playwright + selectors estables.
         Si NO funciona: cae a webbrowser.open + report honesto al user.

    Returns dict con keys:
      - player_started: bool — True solo si confirmamos Play click.
      - attempted_play: bool — True si llegamos a hacer click(s) en el flow.
      - steps: list[str] — pasos completados (para debug).
      - abort_reason: str | None — por que paramos.
      - via_cdp: bool — True si usamos CDP, False si webbrowser fallback.
      - via_cache: bool — True si usamos title->URL cache.
    """
    # 0. Buscar cache title -> URL.
    cached_url = _get_cached_title_url(state, canonical, query)

    # 1. Intentar CDP attach.
    cdp = _try_cdp_attach(executor)
    if cdp["available"] and spec and web_url:
        result = _streaming_cdp_play(
            executor, canonical, spec, query, profile_name,
            web_url=web_url,
            web_search_via_url=web_search_via_url,
            cached_url=cached_url,
            state=state,
        )
        result["via_cdp"] = True
        return result

    # 2. Fallback: webbrowser.open. Honesto — solo abrimos la pagina y
    # le pedimos al user que de UN click. NO intentamos Tab nav ciega
    # (causaba clicks accidentales).
    import webbrowser as _wb
    url_to_open = cached_url or web_url
    if not url_to_open:
        return {
            "player_started": False, "attempted_play": False,
            "steps": [], "via_cdp": False, "via_cache": False,
            "abort_reason": "no URL to open",
        }
    try:
        opened = _wb.open(url_to_open)
    except Exception as exc:
        return {
            "player_started": False, "attempted_play": False,
            "steps": [], "via_cdp": False, "via_cache": bool(cached_url),
            "abort_reason": f"webbrowser.open failed: {exc}",
        }
    if not opened:
        return {
            "player_started": False, "attempted_play": False,
            "steps": [], "via_cdp": False, "via_cache": bool(cached_url),
            "abort_reason": "webbrowser.open returned False",
        }
    return {
        "player_started": False,
        "attempted_play": False,  # honesto: NO intentamos play, solo abrimos.
        "steps": [f"opened_in_default_browser:{url_to_open[:80]}"],
        "via_cdp": False,
        "via_cache": bool(cached_url),
        "abort_reason": None,
        "verification_note": (
            "Opened in default browser. For auto-play, start Chrome with "
            "--remote-debugging-port=9222 so the agent can attach via CDP."
        ),
        "cdp_unavailable_reason": cdp["reason"],
    }


def _detect_spotify_already_running(executor: Executor) -> bool:
    """Devuelve True si hay una ventana 'Spotify' visible antes de mandar
    el deeplink.

    Importa para el wait dinamico: cuando Spotify ya esta abierto mostrando
    el player view, el deeplink `spotify:search:<q>` tarda 2-4s en navegar
    a search results. Default `auto_play_wait=1.8s` alcanza para cold-launch
    (el splash + load tarda mas que la navegacion intra-app) pero NO para
    warm — Enter dispara mientras la UI todavia esta en player view y
    reproduce lo que esta en la cola.
    """
    try:
        windows = executor("window", {"action": "list"})
    except Exception:
        return False
    if not isinstance(windows, dict):
        return False
    items = windows.get("windows") or windows.get("items") or []
    if not isinstance(items, list):
        return False
    for w in items:
        title = ""
        if isinstance(w, dict):
            title = str(w.get("title") or "")
        else:
            title = str(w)
        if "spotify" in title.lower():
            return True
    return False


def _spotify_play_random(
    executor: Executor,
    state: AgentState | None,
    auto_play_wait: float,
) -> dict[str, Any]:
    """User pidio 'una cancion' / 'musica' sin nombrar titulo.

    Decision del user (2026-05-22):
      - Si tenemos el username de Spotify -> reproducir 'Me Gusta' (Liked Songs)
        en shuffle via deeplink spotify:user:<user>:collection.
      - Si NO -> mandar Play global (media key): reanuda lo que Spotify tenga
        cargado / la cola. Universal y sin login, pero si Spotify esta vacio no
        suena nada (lo reportamos honesto).

    Fuente del URI de Liked Songs:
      https://community.spotify.com/t5/Your-Library/What-is-the-Spotify-URI-for-my-Liked-Songs/td-p/5255192
      (spotify:user:<username>:collection — workaround no-oficial pero estable).
    """
    username = _get_spotify_username(state)
    if username:
        # 1. Lanzar app con deeplink a Liked Songs.
        deeplink = f"spotify:user:{username}:collection"
        try:
            subprocess.Popen(
                ["cmd", "/c", "start", "", deeplink],
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, FileNotFoundError) as exc:
            return {"played": False, "mode": "liked_songs",
                    "abort_reason": f"deeplink launch failed: {exc}"}
        # 2. Focus + Enter para reproducir (con shuffle el primer track suena).
        ap = _spotify_auto_play(executor, max(auto_play_wait, 2.5), query=None)
        ap["mode"] = "liked_songs"
        ap["deeplink"] = deeplink
        ap["username"] = username
        return ap
    # Sin username -> Play global.
    try:
        r = executor("audio", {"action": "media_play_pause"})
        ok = bool(isinstance(r, dict) and r.get("ok", True))
        return {
            "played": ok,
            "mode": "global_play_key",
            "abort_reason": None if ok else "media_play_pause returned not-ok",
            "needs_username_hint": (
                "Para reproducir tus 'Me Gusta' aleatorias directamente, decime "
                "tu usuario de Spotify una vez (ej. 'mi usuario de Spotify es "
                "ema123') y lo recuerdo."
            ),
        }
    except Exception as exc:
        return {"played": False, "mode": "global_play_key",
                "abort_reason": f"media_play_pause failed: {exc}"}


def _is_spotify_track_title(title: str) -> bool:
    """Spotify pone "Track • Artist" (o "Spotify - Track • Artist") en el window
    title cuando suena algo. Cuando NO suena nada el title es la marca pelada:
    "Spotify Premium" / "Spotify Free" / "Spotify". True si hay un track."""
    t = (title or "").strip().lower()
    if not t:
        return False
    return t not in {"spotify", "spotify premium", "spotify free",
                      "spotify - premium", "advertisement"}


# Script PowerShell que reproduce en Spotify Desktop via UI Automation.
# VALIDADO EN VIVO 2026-05-22 (track/artista/cancion). Spotify (Electron)
# expone su arbol de accesibilidad: cada item reproducible tiene un boton
# cuyo Name empieza con "Reproducir <X>" (o "Play <X>" en ingles). El TAB+ENTER
# a ciegas NO reproduce nada — el clic UIA via InvokePattern SI.
#
# Estrategia:
#   1. Tomar la ventana de Spotify, leer su title ANTES.
#   2. Enumerar botones cuyo Name empiece con el verbo de play (localizado).
#      Filtrar a los del AREA DE CONTENIDO (x > borde-izq + margen) para
#      descartar la sidebar/biblioteca del user.
#   3. Elegir el que MATCHEA palabras de la query (>=4 chars); si ninguno,
#      el de menor Y (top result). Invoke().
#   4. Leer el title DESPUES y devolver JSON con played/post_play_title.
# Los verbos se pasan como parametro (multi-idioma, sin hardcode en el .ps1).
_SPOTIFY_UIA_PLAY_PS = r"""
param([string]$Query, [string]$PlayVerbs)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
function Get-Title { (Get-Process Spotify -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -ne "" } | Select-Object -First 1).MainWindowTitle }
$verbs = @()
foreach ($v in ($PlayVerbs -split '\|')) { if ($v.Trim() -ne "") { $verbs += $v.Trim().ToLower() } }
$proc = Get-Process Spotify -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
if (-not $proc) { [Console]::Out.WriteLine('{"ok":false,"error":"no_spotify_window"}'); exit }
$titleBefore = Get-Title
$root = [System.Windows.Automation.AutomationElement]::FromHandle($proc.MainWindowHandle)
$winRect = $root.Current.BoundingRectangle
$sidebarEdge = $winRect.X + 100
$cond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty, [System.Windows.Automation.ControlType]::Button)
$buttons = $root.FindAll([System.Windows.Automation.TreeScope]::Descendants, $cond)
function Is-PlayName($name) { $n=$name.ToLower(); foreach ($v in $verbs) { if ($n.StartsWith($v + " ")) { return $true } }; return $false }
$content = @()
foreach ($b in $buttons) {
  $nm = $b.Current.Name
  if ((Is-PlayName $nm) -and ($b.Current.BoundingRectangle.X -gt $sidebarEdge)) { $content += $b }
}
$content = $content | Sort-Object { $_.Current.BoundingRectangle.Y }
if ($content.Count -eq 0) {
  [Console]::Out.WriteLine((ConvertTo-Json @{ok=$false;error="no_play_button";title_before=$titleBefore} -Compress)); exit
}
$qwords = @(); foreach ($w in ($Query.ToLower() -split '\s+')) { if ($w.Length -ge 4) { $qwords += $w } }
$match = $null
foreach ($b in $content) { $n=$b.Current.Name.ToLower(); foreach ($w in $qwords) { if ($n.Contains($w)) { $match=$b; break } }; if ($match) { break } }
$target = if ($match) { $match } else { $content[0] }
$chosen = $target.Current.Name
$target.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
Start-Sleep -Milliseconds 1500
$titleAfter = Get-Title
[Console]::Out.WriteLine((ConvertTo-Json @{ok=$true;chosen=$chosen;matched_query=($match -ne $null);title_before=$titleBefore;title_after=$titleAfter} -Compress))
"""


def _spotify_auto_play(
    executor: Executor,
    wait_seconds: float,
    query: str | None = None,
) -> dict[str, Any]:
    """Reproduce via UIA con REINTENTOS (fix 2026-05-29).

    La búsqueda de Spotify tarda 2-4s en renderizar (más en frío). El click UIA
    en el botón 'Reproducir' es FIABLE; lo que fallaba intermitentemente era llegar
    ANTES del render con un único intento de wait FIJO → el árbol UIA aún no tenía
    el botón → "no pude verificar"/"debes pulsar Enter" (medido en los logs del
    usuario: 4/5 intentos de Spotify fallaron así). Reintentamos con esperas
    crecientes hasta que el botón aparezca y reproduzca (played=True)."""
    import time as _time
    waits = [max(0.5, wait_seconds), 2.0, 2.5]
    last: dict[str, Any] = {
        "played": False, "focus_verified": False,
        "abort_reason": "no attempt", "wait_seconds": wait_seconds,
    }
    for _i, _w in enumerate(waits):
        res = _spotify_auto_play_once(executor, _w, query)
        if res.get("played"):
            res["attempts"] = _i + 1
            return res
        last = res
    last["attempts"] = len(waits)
    return last


def _spotify_auto_play_once(
    executor: Executor,
    wait_seconds: float,
    query: str | None = None,
) -> dict[str, Any]:
    """Un intento: tras enviar spotify:search:<q>, esperar render y reproducir via
    UI Automation (clic real en el boton "Reproducir <X>" del resultado).

    DESCUBRIMIENTO 2026-05-22 (validado en vivo): Tab+Enter / media-keys NO
    reproducen de forma fiable desde la busqueda de Spotify. Spotify Electron
    SI expone su arbol UIA: cada resultado tiene un boton "Reproducir <X>".
    Clickearlo via InvokePattern reproduce de verdad — y eligiendo el que
    matchea la query reproduce EXACTAMENTE lo pedido (track/artista/genero).

    Multi-idioma: los verbos de "play" se detectan por el idioma de la UI de
    Spotify (ES "Reproducir", EN "Play", PT "Reproduzir", etc.) — se pasan al
    script como lista, sin hardcode en el .ps1.

    Returns dict: played, focus_verified, abort_reason, wait_seconds,
    post_play_title, query_match, chosen.
    """
    import json as _json
    import time as _time
    _time.sleep(max(0.5, wait_seconds))

    # Verbos de "Reproducir" en los idiomas de UI de Spotify. La UI puede estar
    # en cualquier idioma — incluimos los principales. (No es la query del user;
    # es el label del boton de Spotify, acotado a idiomas de la app.)
    play_verbs = "|".join([
        "reproducir", "play", "reproduzir", "riproduci", "lire", "abspielen",
        "afspelen", "spela", "odtwórz", "воспроизвести", "再生", "재생", "播放",
    ])

    if os.name != "nt":
        return {"played": False, "focus_verified": False,
                "abort_reason": "UIA play only implemented on Windows",
                "wait_seconds": wait_seconds}

    # IMPORTANTE: pasar un script multilinea con params via `-Command` lo
    # mangla (PowerShell rompe el param binding). Escribir a un .ps1 temporal
    # y correr con `-File` es robusto. Validado en vivo 2026-05-22.
    import tempfile as _tempfile
    ps_path = None
    try:
        with _tempfile.NamedTemporaryFile(
            mode="w", suffix=".ps1", delete=False, encoding="utf-8",
        ) as fh:
            fh.write(_SPOTIFY_UIA_PLAY_PS)
            ps_path = fh.name
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
              "-File", ps_path,
              "-Query", str(query or ""), "-PlayVerbs", play_verbs],
            capture_output=True, text=True, timeout=30,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception as exc:
        return {"played": False, "focus_verified": False,
                "abort_reason": f"UIA play subprocess failed: {exc}",
                "wait_seconds": wait_seconds}
    finally:
        if ps_path:
            try:
                os.unlink(ps_path)
            except Exception:
                pass

    out = (proc.stdout or "").strip()
    data: dict[str, Any] = {}
    # El script imprime una linea JSON; tomar la ultima por si hay ruido.
    for line in reversed(out.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                data = _json.loads(line)
                break
            except Exception:
                continue

    if not data.get("ok"):
        reason = data.get("error") or (proc.stderr or "").strip() or "uia_no_output"
        return {
            "played": False, "focus_verified": bool(data),
            "abort_reason": f"UIA play: {reason}",
            "wait_seconds": wait_seconds,
            "title_before_play": data.get("title_before", ""),
        }

    title_after = str(data.get("title_after") or "")
    played = _is_spotify_track_title(title_after)
    chosen = str(data.get("chosen") or "")

    # query_match: ¿lo que suena se parece a lo pedido? Heuristica: palabra
    # >=4 chars de la query en el title o en el nombre del boton elegido.
    query_match: bool | None = None
    if query and played:
        qwords = [w for w in str(query).lower().split() if len(w) >= 4]
        hay = (title_after + " " + chosen).lower()
        if qwords:
            query_match = any(w in hay for w in qwords)
    return {
        "played": played,
        "focus_verified": True,
        "abort_reason": None if played else (
            "UIA clicked a play button but no track in window title — Spotify "
            "may still be loading, or the result was not playable."
        ),
        "wait_seconds": wait_seconds,
        "via_uia": True,
        "chosen": chosen,
        "matched_query": bool(data.get("matched_query")),
        "title_before_play": str(data.get("title_before") or ""),
        "post_play_title": title_after,
        "query_match": query_match,
    }


def _launch_streaming(
    canonical: str,
    spec: dict[str, Any],
    query: str,
    *,
    executor: Executor | None = None,
    auto_play: bool = False,
    auto_play_wait: float = 1.8,
    profile_name: str | None = None,
    state: AgentState | None = None,
) -> dict[str, Any]:
    """Abre la app o web del provider con la query de busqueda.

    Prioridad:
      1. App desktop instalada + deeplink propio -> usar deeplink.
         Si auto_play=True + executor disponible + provider tiene auto-play
         soportado (Spotify), focus + verify + Enter para reproducir.
      2. App desktop instalada sin deeplink -> abrir app (sin busqueda) + abrir web search en background?
         Decision: si NO hay deeplink, vamos directo a web. Abrir la app sin
         busqueda obliga al user a navegar manualmente.
      3. No app -> abrir web URL en browser default.
    """
    import urllib.parse
    if not query:
        return _err(
            f"{canonical} provider requires a query (movie/series/song)",
            provider=canonical,
        )
    encoded = urllib.parse.quote(query)
    # Solo formatear {q} si la plataforma soporta search via URL. Sino,
    # web_url es solo el home y la query se escribira via GUI search shortcut.
    web_search_via_url = bool(spec.get("web_search_via_url", True))
    # F-009: resolver URL contemplando locale dinamico (Disney+ tiene
    # /es-419/ hardcoded). Si el spec define web_url_template + default_locale,
    # formatear con el locale del user (futuro: state.user_locale), sino
    # fallback al default_locale del spec, sino al web_url estatico.
    web_url = _resolve_streaming_web_url(spec, state=state)
    if web_search_via_url and "{q}" in web_url:
        web_url = web_url.format(q=encoded)
    install_hint = spec.get("install_hint", "")
    note = spec.get("post_open_note", "")

    app_info = _find_streaming_app(spec)
    deeplink_tpl = spec.get("deeplink")

    # PATH 1: app instalada + deeplink confiable
    if app_info["kind"] and deeplink_tpl:
        deeplink = deeplink_tpl.format(q=encoded)
        try:
            subprocess.Popen(
                ["cmd", "/c", "start", "", deeplink],
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, FileNotFoundError):
            pass  # fall through to web
        else:
            # AUTO-PLAY: si tenemos executor y el caller lo pidio, esperar
            # carga + focus verify + Enter para que Spotify reproduzca la
            # primera cancion del resultado de busqueda.
            auto_play_info: dict[str, Any] | None = None
            if auto_play and executor is not None and canonical == "spotify":
                # El UIA play necesita que los RESULTADOS de busqueda esten
                # renderizados (los botones "Reproducir <X>" recien existen en
                # el arbol cuando el grid cargo). Validado en vivo 2026-05-22:
                # ~5s alcanza. Piso 4.5s cold, 5.5s si ya estaba abierto (el
                # deeplink navega de player-view a search, mas lento en warm).
                already_open = _detect_spotify_already_running(executor)
                effective_wait = (
                    max(auto_play_wait, 5.5) if already_open
                    else max(auto_play_wait, 4.5)
                )
                auto_play_info = _spotify_auto_play(executor, effective_wait, query=query)
                if auto_play_info is not None:
                    auto_play_info["was_already_open"] = already_open
                    auto_play_info["wait_seconds_used"] = effective_wait
            played = bool(auto_play_info and auto_play_info.get("played"))
            qmatch = auto_play_info.get("query_match") if auto_play_info else None
            # Si played=True pero query_match=False, no marcamos verified=True.
            # El LLM debe saber que el Enter funciono pero el track tocando
            # probablemente no es lo que el user pidio.
            verified = played and qmatch is not False
            if not played:
                completion_status = "opened_search_results_pending_play"
                final_note = note
            elif qmatch is True:
                completion_status = "media_playing_match"
                final_note = (
                    f"{canonical}: playing — Spotify focused, Enter pressed; "
                    f"now-playing title matches query."
                )
            elif qmatch is False:
                completion_status = "media_playing_wrong_track"
                final_note = (
                    f"{canonical}: played — WARN: now-playing title does not match "
                    f"query (possible warm-cache race; queued track may have played "
                    f"instead of search result)."
                )
            else:
                completion_status = "media_playing_unverified"
                final_note = (
                    f"{canonical}: playing — Spotify focused, Enter pressed on first result."
                )
            return _ok(
                action="play",
                provider=canonical,
                query=query,
                deeplink=deeplink,
                app_kind=app_info["kind"],
                launch_target=app_info["launch_target"],
                opened=True,
                played=played,
                auto_play_attempted=auto_play,
                auto_play_info=auto_play_info,
                verified=verified,
                query_match=qmatch,
                status="dispatched" if played else "attempted",
                completion_status=completion_status,
                note=final_note,
            )

    # PATH 2/3: sin deeplink -> usar web.
    #   - auto_play + profile -> _streaming_web_auto_play intenta CDP attach.
    #     Si CDP attached (via_cdp=True), el browser real ya esta navegado;
    #     `opened` es True incluso si el play button no se encontro.
    #   - sin CDP (o sin auto_play) -> webbrowser.open con la search URL.
    web_auto_play_info: dict[str, Any] | None = None
    played = False
    attempted_play = False
    opened = False
    if auto_play and executor is not None and profile_name:
        web_auto_play_info = _streaming_web_auto_play(
            executor, canonical, query, profile_name, auto_play_wait,
            spec=spec, web_url=web_url, web_search_via_url=web_search_via_url,
            state=state,
        )
        played = bool(web_auto_play_info.get("player_started"))
        attempted_play = bool(web_auto_play_info.get("attempted_play"))
        if web_auto_play_info.get("via_cdp"):
            # CDP attached: Opera GX ya esta navegado al search/detail.
            # `opened` es True aunque el play button no se encontrara.
            opened = True
        else:
            # CDP no disponible -> el fallback de _streaming_web_auto_play
            # ya intento webbrowser.open. Chequear si fue exitoso.
            if not web_auto_play_info.get("abort_reason"):
                opened = True
            else:
                # Fallback adicional: intentar webbrowser.open desde aqui.
                try:
                    opened = webbrowser.open(web_url)
                except Exception as exc:
                    return _err(
                        f"Could not open {canonical} "
                        f"(no app deeplink and webbrowser failed): {exc}",
                        provider=canonical, status="failed",
                    )
    else:
        try:
            opened = webbrowser.open(web_url)
        except Exception as exc:
            return _err(
                f"Could not open {canonical} "
                f"(no app deeplink and webbrowser failed): {exc}",
                provider=canonical, status="failed",
            )

    if not opened:
        return _err(
            f"{canonical}: no native deeplink and default browser refused to open.",
            provider=canonical, status="needs_user",
            install_hint=install_hint,
        )

    via_cdp = bool(web_auto_play_info and web_auto_play_info.get("via_cdp"))
    if played:
        note_msg = (
            f"{canonical}: playing — CDP click play executed (profile "
            f"'{profile_name}'). Confirmed via Playwright."
            if via_cdp else
            f"{canonical}: playing — title clicked, Play pressed "
            f"(profile '{profile_name}')."
        )
    elif attempted_play:
        # via_cdp=True + attempted_play=True (sin played): el flow llego al
        # detail page pero no encontro Play button (caso comun: el video ya
        # esta auto-playing en el detail page, o el button selector cambio).
        # Reportar como exito — el user lo ve en pantalla.
        note_msg = (
            f"{canonical}: opened — navigated to '{query}' detail page via "
            f"CDP (profile '{profile_name}'). The video is loading."
            if via_cdp else
            f"{canonical}: opened search results with profile '{profile_name}'. "
            "Click the title to play."
        )
    else:
        note_msg = note
    result = _ok(
        action="play",
        provider=f"{canonical}_web",
        query=query,
        url=web_url,
        opened=True,
        played=played,
        attempted_play=attempted_play,
        auto_play_attempted=bool(auto_play and profile_name),
        profile_name=profile_name,
        web_auto_play_info=web_auto_play_info,
        verified=played,
        status="dispatched" if (played or attempted_play) else "attempted",
        completion_status=(
            "media_playing" if played
            else "playback_attempted_unverified" if attempted_play
            else "opened_search_results_pending_play"
        ),
        note=note_msg,
        via_cdp=via_cdp,
    )
    if app_info["kind"]:
        # Avisamos que la app esta pero no la usamos por falta de deeplink.
        result["app_available_but_no_deeplink"] = True
        result["app_kind"] = app_info["kind"]
    return result


def _media_play_streaming(
    provider: str,
    query: str,
    args: dict[str, Any],
    executor: Executor | None = None,
    state: AgentState | None = None,
) -> dict[str, Any]:
    """Entry point unificado para Spotify/Netflix/Disney+/Max/Prime Video."""
    resolved = _resolve_streaming_provider(provider)
    if not resolved:
        return _err(
            f"unsupported streaming provider: {provider!r}",
            provider=provider, status="needs_dependency",
            install_hint=(
                "Supported providers: spotify, netflix, disney+ (disney), "
                "hbo_max (max), prime_video. Use one of these names."
            ),
        )
    canonical, spec = resolved

    # SPOTIFY USERNAME: si el user lo da (para Liked Songs aleatorias), el LLM
    # lo pasa como spotify_user / username. Persistir igual que los perfiles.
    if canonical == "spotify":
        uname = str(args.get("spotify_user") or args.get("username") or "").strip()
        if uname:
            try:
                _set_streaming_preference(state, "spotify_user", uname)
            except Exception:
                pass  # best-effort

    # auto_play default True para todos: Spotify usa app+Enter; web streaming
    # usa profile picker + click title + click play.
    auto_play_raw = args.get("auto_play", True)
    if isinstance(auto_play_raw, str):
        auto_play = auto_play_raw.strip().lower() not in {"", "false", "0", "no", "off"}
    else:
        auto_play = bool(auto_play_raw)
    wait_raw = args.get("auto_play_wait") or args.get("wait_seconds") or 1.8
    try:
        auto_play_wait = max(0.5, min(10.0, float(wait_raw)))
    except (TypeError, ValueError):
        auto_play_wait = 1.8

    # GENERICO: "pon una cancion" / "musica" SIN titulo. Buscar la palabra
    # literal ("cancion") nunca reproduce nada util. Para Spotify -> random:
    # Liked Songs shuffle si hay username, sino Play global. (decision user
    # 2026-05-22). Solo aplica a Spotify; para video pedir titulo es razonable.
    if (canonical == "spotify" and auto_play and executor is not None
            and _is_generic_music_query(query)):
        rnd = _spotify_play_random(executor, state, auto_play_wait)
        played = bool(rnd.get("played"))
        mode = rnd.get("mode")
        if played and mode == "liked_songs":
            note = (
                "spotify: reproduciendo tus 'Me Gusta' en aleatorio "
                f"(usuario '{rnd.get('username')}')."
            )
            completion = "media_playing"
        elif played and mode == "global_play_key":
            note = (
                "spotify: Play global enviado — reanudando lo que tenías "
                "cargado. " + str(rnd.get("needs_username_hint") or "")
            )
            completion = "media_playing_unverified"
        else:
            note = (
                "spotify: no pude iniciar reproducción aleatoria"
                + (f" ({rnd.get('abort_reason')})" if rnd.get("abort_reason") else "")
                + ". " + str(rnd.get("needs_username_hint") or "")
            )
            completion = "opened_search_results_pending_play"
        return _ok(
            action="play",
            provider="spotify",
            query=query,
            random_playback=True,
            random_mode=mode,
            opened=True,
            played=played,
            auto_play_attempted=True,
            auto_play_info=rnd,
            verified=played and mode == "liked_songs",
            status="dispatched" if played else "attempted",
            completion_status=completion,
            note=note.strip(),
        )

    # PERFIL: solo aplica a plataformas con profile picker (NOT spotify).
    # Si el user paso profile= explicitamente, guardarlo Y usarlo.
    # Si no, leer del state. Si tampoco, pedir al user.
    profile_name: str | None = None
    needs_profile = canonical in {"netflix", "disney", "hbo_max", "prime_video"}
    if needs_profile and auto_play:
        explicit_profile = str(
            args.get("profile") or args.get("profile_name") or "",
        ).strip()
        if explicit_profile:
            profile_name = explicit_profile
            # Guardarlo para proximas veces.
            try:
                _set_streaming_preference(state, canonical, profile_name)
            except Exception:
                pass  # best-effort, no abortar si falla
        else:
            profile_name = _get_streaming_preference(state, canonical)
            if not profile_name:
                # PRIMERA VEZ: pedir al user que diga su perfil. El LLM ve
                # este error en history + tool result, y en el proximo turn
                # cuando el user dice "mi perfil es Ema", llama media de
                # nuevo con profile='Ema'. Confiamos en el LLM para mantener
                # el contexto via su history — no persistimos pending state
                # (eso causaba bugs donde turns ajenos eran atrapados como
                # respuestas).
                return _err(
                    f"need {canonical} profile to auto-play",
                    status="needs_user",
                    provider=canonical,
                    query=query,
                    hint=(
                        f"What's your {canonical} profile name? Tell me once and "
                        f"I'll remember it. Example: \"mi perfil de "
                        f"{canonical} es Emmanuel\" — or call media again with "
                        f"profile='<your name>'. If you don't want auto-play, "
                        f"pass auto_play=false."
                    ),
                    asks_for="streaming_profile",
                )

    return _launch_streaming(
        canonical, spec, query,
        executor=executor, auto_play=auto_play, auto_play_wait=auto_play_wait,
        profile_name=profile_name, state=state,
    )


# Backwards-compat: el viejo _media_play_spotify se mantiene como alias.
def _media_play_spotify(query: str, args: dict[str, Any]) -> dict[str, Any]:
    return _media_play_streaming("spotify", query, args)


def media_tool(args: dict[str, Any], executor: Executor, state: AgentState | None = None) -> dict[str, Any]:
    action = str(args.get("action") or "play").casefold()
    if action == "status":
        streaming = {}
        for canonical, spec in _STREAMING_PLATFORMS.items():
            app_info = _find_streaming_app(spec)
            streaming[canonical] = {
                "app_installed": app_info["kind"] is not None,
                "app_kind": app_info["kind"],
                "has_deeplink": spec.get("deeplink") is not None,
                "web_url_template": spec.get("web_url"),
            }
        return _ok(
            backends=["browser_youtube", "windows_media_keys", "local_file",
                       "vlc_cli", "winrt_smtc",
                       "spotify", "netflix", "disney", "hbo_max", "prime_video"],
            now_playing_supported=True,
            vlc_available=bool(_find_vlc_executable()),
            streaming_platforms=streaming,
            note="now_playing uses Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager via PowerShell. Streaming platforms launch desktop app if installed (with deeplink) else open web search URL.",
        )
    if action == "play":
        query = str(args.get("query") or args.get("song") or args.get("title") or "").strip()
        path = str(args.get("path") or "").strip()
        provider = str(args.get("provider") or "youtube").casefold()
        if path:
            return _media_play_local(path, args)
        # Streaming providers con soporte nativo (Spotify, Netflix, Disney+,
        # HBO Max/Max, Prime Video). Prioriza la app desktop si esta instalada
        # con deeplink confiable, sino abre la web URL de busqueda.
        if _resolve_streaming_provider(provider):
            return _media_play_streaming(provider, query, args, executor=executor, state=state)
        if provider in {"youtube", "yt", "browser"}:
            return executor("browser", {"action": "youtube_play", "query": query or "musica"})
        if provider == "vlc":
            vlc = _find_vlc_executable()
            if not vlc:
                return _err(
                    "VLC is not installed",
                    status="needs_dependency", verified=False,
                    install_hint="winget install VideoLAN.VLC",
                )
            target = str(args.get("path") or args.get("url") or "").strip()
            if not target:
                return _err("vlc provider requires path or url")
            return _media_play_vlc(vlc, target)
        # Otros streaming providers sin soporte nativo: fallback honesto a
        # YouTube con nota explicita de que NO es el provider pedido.
        if provider in {"apple_music", "applemusic", "deezer",
                        "tidal", "amazon_music", "amazonmusic", "soundcloud"}:
            result = executor("browser", {"action": "youtube_play", "query": query or "musica"})
            if isinstance(result, dict):
                result = dict(result)
                result["fallback_from"] = provider
                result["fallback_note"] = (
                    f"{provider} requires native SDK/OAuth not configured; "
                    "played on YouTube instead."
                )
            return result
        return _err(
            f"unsupported media provider: {provider!r}",
            provider=provider, status="needs_dependency", verified=False,
            install_hint="Use provider=youtube (default), local_file with path=..., or vlc with path/url.",
        )
    if action == "open_local":
        path = str(args.get("path") or "").strip()
        if not path:
            return _err("missing path")
        return _media_play_local(path, args)
    if action in {"pause", "resume", "play_pause"}:
        return executor("audio", {"action": "media_play_pause"})
    if action == "stop":
        return executor("audio", {"action": "media_stop"})
    if action == "next":
        return executor("audio", {"action": "next"})
    if action == "previous":
        return executor("audio", {"action": "previous"})
    if action == "now_playing":
        return _media_now_playing()
    if action in {"queue_add", "queue_clear", "queue_list"}:
        if not state:
            return _err("queue actions require state", status="needs_implementation")
        return _media_queue(action, args, state)
    if action == "search_local_library":
        return _media_search_local_library(args)
    if action in {"volume_for_app", "cast_lan"}:
        return _err(
            f"media.{action} is not implemented yet",
            status="needs_implementation", verified=False,
            note=("volume_for_app needs SoundVolumeView /SetAppVolume" if action == "volume_for_app" else "cast_lan needs UPnP/DLNA backend (deferred)"),
        )
    return _err(
        "unknown media action", action=action,
        valid_actions=[
            "status", "play", "pause", "resume", "play_pause",
            "stop", "next", "previous", "now_playing",
        ],
        status="needs_user",
    )


def _media_play_local(path_raw: str, args: dict[str, Any]) -> dict[str, Any]:
    target = Path(path_raw).expanduser()
    if not target.exists():
        return _err("media file not found", path=path_raw)
    backend = str(args.get("backend") or "").casefold()
    if backend == "vlc":
        vlc = _find_vlc_executable()
        if vlc:
            return _media_play_vlc(vlc, str(target))
        return _err(
            "VLC backend requested but vlc not on PATH",
            status="needs_dependency", install_hint="winget install VideoLAN.VLC",
        )
    if os.name == "nt":
        os.startfile(target)
    else:
        webbrowser.open(target.as_uri())
    return _ok(action="play", provider="local_file", path=str(target.resolve()), opened=True, verified=True)


def _media_play_vlc(vlc: str, target: str) -> dict[str, Any]:
    proc = subprocess.Popen(
        [vlc, target, "--play-and-exit", "--no-video-title-show"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    return _ok(action="play", provider="vlc", target=target, pid=proc.pid, verified=False, status="attempted", note="VLC launched; verify via now_playing or window list.")


def _media_now_playing() -> dict[str, Any]:
    """Query Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager.

    Pattern from Fleex (2018) and Microsoft Q&A; uses System.WindowsRuntimeSystemExtensions.AsTask
    to convert IAsyncOperation<T> to a Task<T> so PowerShell can wait synchronously.
    """
    script = r"""
$ErrorActionPreference = 'Stop'
try {
  Add-Type -AssemblyName System.Runtime.WindowsRuntime
  [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager,Windows.Media.Control,ContentType=WindowsRuntime] > $null
  [Windows.Media.Control.GlobalSystemMediaTransportControlsSession,Windows.Media.Control,ContentType=WindowsRuntime] > $null
  [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionMediaProperties,Windows.Media.Control,ContentType=WindowsRuntime] > $null

  $asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() |
    Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
  function Await($op, $resultType) {
    $task = $asTaskGeneric.MakeGenericMethod($resultType).Invoke($null, @($op))
    $task.Wait(-1) | Out-Null
    return $task.Result
  }

  $mgr = Await ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager]::RequestAsync()) ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager])
  $session = $mgr.GetCurrentSession()
  if ($null -eq $session) {
    [PSCustomObject]@{ has_session=$false } | ConvertTo-Json
    exit 0
  }
  $props = Await ($session.TryGetMediaPropertiesAsync()) ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionMediaProperties])
  $info = $session.GetPlaybackInfo()
  $timeline = $session.GetTimelineProperties()
  [PSCustomObject]@{
    has_session = $true
    source_app_user_model_id = $session.SourceAppUserModelId
    title = $props.Title
    artist = $props.Artist
    album_title = $props.AlbumTitle
    track_number = $props.TrackNumber
    genres = @($props.Genres)
    playback_status = $info.PlaybackStatus.ToString()
    playback_type = $info.PlaybackType.ToString()
    is_play_enabled = $info.Controls.IsPlayEnabled
    is_pause_enabled = $info.Controls.IsPauseEnabled
    is_next_enabled = $info.Controls.IsNextEnabled
    is_previous_enabled = $info.Controls.IsPreviousEnabled
    position_seconds = $timeline.Position.TotalSeconds
    end_seconds = $timeline.EndTime.TotalSeconds
  } | ConvertTo-Json -Depth 4
} catch {
  [PSCustomObject]@{ error = $_.Exception.Message; has_session = $false } | ConvertTo-Json
}
"""
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=20)
    if proc.returncode != 0:
        return _err("now_playing query failed", stderr=proc.stderr, exit_code=proc.returncode)
    raw = proc.stdout.strip()
    if not raw:
        return _ok(has_session=False, note="no active media session")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return _err("now_playing returned invalid JSON", raw=raw[:1000])
    if not data.get("has_session"):
        return _ok(has_session=False, raw=data)
    return _ok(
        has_session=True,
        title=data.get("title"),
        artist=data.get("artist"),
        album=data.get("album_title"),
        source_app=data.get("source_app_user_model_id"),
        playback_status=data.get("playback_status"),
        playback_type=data.get("playback_type"),
        controls={
            "play": data.get("is_play_enabled"),
            "pause": data.get("is_pause_enabled"),
            "next": data.get("is_next_enabled"),
            "previous": data.get("is_previous_enabled"),
        },
        position_seconds=data.get("position_seconds"),
        end_seconds=data.get("end_seconds"),
        verified=True,
        evidence={"source": "Windows.Media.Control.GSMTCSM"},
    )


def _media_queue(action: str, args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    if action == "queue_clear":
        for item in _resources_by_kind(state, "media_queue", include_closed=False):
            state.mark_cleaned(str(item["id"]), {"deleted": True})
        return _ok(cleared=True)
    if action == "queue_list":
        items = _resources_by_kind(state, "media_queue", include_closed=False)
        items.sort(key=lambda r: str(r.get("metadata", {}).get("added_at", "")))
        return _ok(queue=items, count=len(items))
    if action == "queue_add":
        item_query = str(args.get("query") or args.get("title") or "").strip()
        item_path = str(args.get("path") or "").strip()
        if not item_query and not item_path:
            return _err("queue_add requires query or path")
        label = item_query or Path(item_path).name
        resource = state.register_resource(
            "media_queue",
            label,
            metadata={
                "query": item_query or None,
                "path": item_path or None,
                "provider": args.get("provider"),
                "added_at": datetime.now().isoformat(),
            },
        )
        return _ok(queue_item=resource.get("resource"))
    return _err(
        "unknown queue action", action=action,
        valid_actions=["enqueue", "dequeue", "list", "clear", "current"],
        status="needs_user",
    )


def _media_search_local_library(args: dict[str, Any]) -> dict[str, Any]:
    root_raw = str(args.get("root") or "").strip()
    if not root_raw:
        # default user music folder
        root = Path.home() / "Music"
    else:
        root = Path(root_raw).expanduser()
    if not root.exists():
        return _err("library root not found", root=str(root))
    query = str(args.get("query") or "").casefold()
    extensions = {".mp3", ".flac", ".wav", ".m4a", ".aac", ".ogg", ".opus", ".wma"}
    limit = int(args.get("limit", 50))
    results = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.casefold() not in extensions:
            continue
        if query and query not in path.name.casefold() and query not in str(path.parent.name).casefold():
            continue
        try:
            results.append({"path": str(path), "name": path.name, "size": path.stat().st_size})
        except OSError:
            continue
        if len(results) >= limit:
            break
    return _ok(results=results, count=len(results), root=str(root))


# Source Manager - extraído a domain_tools_source_manager.py
# (R2 sprint 2026-05-28).
from .source_manager import source_manager_tool  # noqa: F401


# Dependency catalog - extraído a domain_tools_dependency.py
# (R2 sprint 2026-05-28). 4 funciones.
from .dependency import (  # noqa: F401
    _binary_dep,
    _dependency_catalog,
    _module_dep,
    dependency_tool,
)


# Regex laxas; el objetivo no es validar email/phone "correctos" sino
# rechazar valores claramente invalidos (caracteres de control, ints crudos).
# Contacts domain tool - extraído a domain_tools_contacts.py (R2 sprint
# 2026-05-27). Las 10 funciones contacts_tool + helpers vCard + name_similarity
# + _contacts_resolve_recipient + las 3 regex constants + 2 thresholds viven
# ahora en domain_tools_contacts.py. Re-export acá para compat (dispatch lo
# importa vía la clase ToolRegistry, mantenemos nombres en namespace).
from .contacts import (  # noqa: F401  (re-export por compat)
    _CONTROL_CHARS_RE,
    _EMAIL_BASIC_RE,
    _PHONE_BASIC_RE,
    _RESOLVE_AMBIGUOUS_MARGIN,
    _RESOLVE_MIN_SCORE,
    _clean_contact_field,
    _contact_to_vcard,
    _contacts_export_vcard,
    _contacts_import_vcard,
    _contacts_resolve_recipient,
    _contacts_update,
    _name_similarity,
    _vcard_escape,
    _vcard_parse,
    _vcard_unescape,
    contacts_tool,
)


# _parse_due_iso — extraído a domain_tools_helpers.py (R3 sprint 2026-05-28).


# ---------------------------------------------------------------------------
# WhatsApp tool
# ---------------------------------------------------------------------------

# WhatsApp UWP package family name (instalacion estandar desde Microsoft Store).
_WHATSAPP_UWP_PFN = "5319275A.WhatsAppDesktop_cv1g1gvanyjgm"

# Numero E.164 (puede tener +, espacios, guiones, parentesis).
_WHATSAPP_PHONE_RE = re.compile(r"^[\+\d\s\-\(\)]{7,20}$")


def _normalize_phone_for_whatsapp(phone: str) -> str:
    """Normaliza un numero al formato que espera whatsapp:// y wa.me:
    solo digitos, sin el +, sin separadores. Ej. '+54 9 11 1234-5678' -> '54911123456 78'.
    """
    if not phone:
        return ""
    # Mantener solo digitos.
    digits = re.sub(r"\D", "", phone)
    return digits


def _find_whatsapp_app() -> dict[str, str | None]:
    """Detecta si WhatsApp esta instalado como UWP.

    Returns dict con kind ('uwp' | None) y launch_target.
    Reutiliza el patron de _find_streaming_app.
    """
    if os.name != "nt":
        return {"kind": None, "launch_target": None}
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
              f"if (Get-AppxPackage -Name '{_WHATSAPP_UWP_PFN.split('_')[0]}') {{ Write-Output yes }}"],
            capture_output=True, text=True, timeout=3,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if proc.returncode == 0 and "yes" in (proc.stdout or "").lower():
            return {"kind": "uwp", "launch_target": f"shell:AppsFolder\\{_WHATSAPP_UWP_PFN}!App"}
    except (OSError, subprocess.TimeoutExpired):
        pass
    return {"kind": None, "launch_target": None}


def _resolve_whatsapp_recipient(
    args: dict[str, Any], state: AgentState,
) -> tuple[str | None, str | None, str, str | None] | dict[str, Any]:
    """Resuelve el destinatario.

    Acepta en args:
      - phone="<numero>"  -> usado directamente (validado).
      - contact="<nombre>" o recipient="<nombre>"  -> busca en contacts.

    Returns:
      - tupla (raw_phone, normalized_digits, source, name_for_gui_search) si OK.
        Si phone resolvio -> (phone, normalized, source, None) — usar deeplink.
        Si solo hay nombre (contacto sin phone en store, o store vacio) ->
        (None, None, "gui_search", name_query) — usar GUI search en WhatsApp.
      - dict de error _err(...) si no se pudo resolver (sin phone ni nombre).
    """
    explicit_phone = str(args.get("phone") or args.get("number") or "").strip()
    if explicit_phone:
        if not _WHATSAPP_PHONE_RE.match(explicit_phone):
            return _err(
                f"invalid phone format: {explicit_phone!r}",
                hint=("Pass an international format like +54 9 11 1234-5678 or "
                      "just digits 5491112345678. WhatsApp requires country code."),
                status="needs_user",
            )
        normalized = _normalize_phone_for_whatsapp(explicit_phone)
        if len(normalized) < 7:
            return _err(
                f"phone too short after normalization: {normalized!r}",
                hint="Include country code (e.g. 54 for Argentina, 1 for USA).",
                status="needs_user",
            )
        return explicit_phone, normalized, "explicit", None

    # Resolver por nombre.
    name_query = str(
        args.get("contact") or args.get("recipient") or args.get("to")
        or args.get("name") or ""
    ).strip()
    if not name_query:
        return _err(
            "missing recipient: pass phone='+...' OR contact='<name>'",
            status="needs_user",
        )

    # 1. Intentar contacts store local (rapido si esta).
    # exclude_groups=True: un envío directo por NOMBRE nunca debe resolver a un
    # grupo (cura de raíz del bug "mandale a mamá -> grupo Música"). Si el
    # usuario quiere un grupo, el LLM debe pasar el phone/JID del grupo
    # explícito o el contacto marcado is_group debe nombrarse aparte.
    resolve_result = _contacts_resolve_recipient(
        {"query": name_query, "limit": 5, "exclude_groups": True}, state,
    )
    matches = resolve_result.get("matches") or []
    # Inv 2 (grounding): si la resolución es AMBIGUA (dos contactos casi
    # empatados), NO adivinar — pedir desempate. Mandar al chat equivocado es
    # daño irreversible (bug "mamá"->"Música"). Mejor preguntar.
    if resolve_result.get("ambiguous") and len(matches) >= 2:
        cand_names = [
            str((m["contact"].get("metadata") or {}).get("name")
                or m["contact"].get("label") or "?")
            for m in matches[:3]
        ]
        return _err(
            f"contacto ambiguo para {name_query!r}",
            status="needs_user",
            contact_name=name_query,
            candidates=cand_names,
            hint=f"¿A cuál querías: {', '.join(cand_names)}?",
        )
    if matches:
        best = matches[0]["contact"]
        meta = best.get("metadata") or {}
        phone = str(meta.get("phone") or "").strip()
        if phone:
            normalized = _normalize_phone_for_whatsapp(phone)
            if len(normalized) >= 7:
                return phone, normalized, f"contact:{best.get('id')}", None
        # Contacto encontrado pero sin phone util -> caer a GUI search.

    # 2. Fallback: GUI search dentro de WhatsApp Desktop.
    # WhatsApp ya tiene la lista de contactos del telefono — usa Ctrl+F /
    # campo de busqueda para encontrar al contacto por nombre. Esto cubre
    # el caso "el contacto existe en WhatsApp pero no en mi store local".
    return None, None, "gui_search", name_query


def _resolve_whatsapp_recipient_legacy3(
    args: dict[str, Any], state: AgentState,
) -> tuple[str, str, str] | dict[str, Any]:
    """Backwards-compat 3-tuple form. Solo para tests viejos que esperaban
    (raw, normalized, source). NO usar en codigo nuevo.
    """
    r = _resolve_whatsapp_recipient(args, state)
    if isinstance(r, dict):
        return r
    raw, normalized, source, name = r
    if normalized is None:
        # tests legacy no soportaban el path gui_search; devolver error util.
        return _err(
            f"contact {name!r} found but has no phone number (use new GUI search path)",
            status="needs_user", contact_name=name,
        )
    return raw, normalized, source


def _verify_chat_header_uia(executor: Executor, contact_name: str) -> bool | None:
    """Inv 8 (UIA primary): verifica el chat activo leyendo el ÁRBOL DE
    ACCESIBILIDAD de WhatsApp (no OCR, no mmproj, sub-segundo). WhatsApp Desktop
    moderno es WebView2/Chromium: el nombre del contacto aparece como el `Name`
    de un control (heading/text/listitem). Buscamos un token significativo del
    nombre entre los elementos UIA de la ventana de WhatsApp.

    Returns:
        True  -> encontrado en el árbol UIA (chat correcto).
        None  -> UIA no disponible / sin evidencia -> el caller cae a OCR.
        (no devuelve False: ausencia en UIA no PRUEBA chat equivocado; eso lo
         decide el verificador OCR, más sensible al header visible.)
    """
    import re as _re
    try:
        res = executor("uia", {"action": "find", "window": "WhatsApp",
                               "query": contact_name, "limit": 40})
    except Exception:
        return None
    if not isinstance(res, dict) or not res.get("ok"):
        return None
    matches = res.get("matches")
    if not isinstance(matches, list):
        return None
    names = " ".join(
        str(m.get("name", "")) for m in matches if isinstance(m, dict)).lower()
    if not names.strip():
        return None
    names = _re.sub(r"[^a-záéíóúüñ ]", " ", names)
    tokens = [t for t in _re.split(r"\s+", contact_name.lower()) if len(t) >= 3]
    if not tokens:
        return None
    return True if any(t in names for t in tokens) else None


def _verify_chat_header(executor: Executor, contact_name: str) -> bool:
    """Confirma que el chat abierto en WhatsApp es del contacto pedido.

    Bug #847b: el Enter a ciegas tras buscar abría el chat equivocado (mensaje a
    'mamá' cayó en el grupo 'Música'). Antes de escribir verificamos el chat
    activo. Inv 8: PRIMERO por UIA (árbol de accesibilidad, barato, sin mmproj);
    si UIA no da evidencia, FALLBACK a OCR de la franja superior. Conservador: si
    NINGUNO verifica, devolvemos False -> el caller NO escribe (mejor no mandar
    que mandar al chat equivocado).

    El match es laxo a propósito: el header puede tener emojis/apodos ("Mamá🍓");
    basta con que un token alfabético >=3 chars del contacto aparezca.
    """
    import re as _re
    # Inv 8: UIA primero (más rápido y fiable que OCR, no carga mmproj).
    uia_ok = _verify_chat_header_uia(executor, contact_name)
    if uia_ok is True:
        return True
    # Fallback: OCR de la franja superior.
    try:
        shot = executor("gui", {"action": "locate_text", "text": contact_name})
    except Exception:
        return False
    if not isinstance(shot, dict):
        return False
    # locate_text devuelve found=True y matches si lo encontró en pantalla.
    if shot.get("found"):
        return True
    # Fallback: el OCR completo puede traer el texto aunque el match exacto falle
    # (emojis, mayúsculas). Buscar un token significativo del nombre en el texto.
    ocr_text = ""
    for key in ("text", "ocr_text", "full_text"):
        v = shot.get(key)
        if isinstance(v, str) and v:
            ocr_text = v
            break
    if not ocr_text and isinstance(shot.get("matches"), list):
        ocr_text = " ".join(
            str(m.get("text", "")) for m in shot["matches"] if isinstance(m, dict))
    ocr_norm = _re.sub(r"[^a-záéíóúüñ ]", " ", ocr_text.lower())
    tokens = [t for t in _re.split(r"\s+", contact_name.lower()) if len(t) >= 3]
    if not tokens:
        # nombre muy corto (p.ej. "mi") -> no podemos verificar con seguridad
        return False
    return any(t in ocr_norm for t in tokens)


def _verify_chat_header_status(executor: Executor, contact_name: str) -> str:
    """Tri-state para el envio WhatsApp.

    Returns:
        "confirmed"   -> el header contiene el contacto pedido.
        "wrong_chat"  -> el OCR leyo un header corto y claramente distinto.
        "unknown"     -> UIA/OCR no dio evidencia suficiente.

    El bool historico _verify_chat_header mezclaba "wrong_chat" con "unknown" y eso
    rompio WhatsApp: cuando WebView2 no exponia el header, abortaba envios validos.
    """
    import re as _re

    def _fold(s: str) -> str:
        s = unicodedata.normalize("NFKD", s.casefold())
        s = "".join(ch for ch in s if not unicodedata.combining(ch))
        return _re.sub(r"[^a-z0-9 ]", " ", s)

    # BUG CRÍTICO MEDIDO (2026-05-31): la versión vieja hacía
    # locate_text(contact) sobre TODA la pantalla y devolvía "confirmed" si lo
    # encontraba EN CUALQUIER LADO — pero el nombre buscado SIGUE ESCRITO en la
    # caja de búsqueda → falso "confirmed" → tipeaba/enviaba al chat ABIERTO
    # (equivocado). Es el C1 "destinatario equivocado = daño irreversible".
    # FIX: confirmar SOLO si el nombre aparece en la REGIÓN DEL ENCABEZADO (banda
    # superior del área de chat, a la derecha del sidebar) — NO en el buscador
    # (izquierda) ni en un mensaje (abajo). El texto del header es chico y de baja
    # confianza OCR (~20-24) → min_conf=20 (medido: el header cae a ~0.33W/0.09H).
    try:
        import win32gui  # type: ignore
        hwnd = win32gui.GetForegroundWindow()
        if "whatsapp" not in (win32gui.GetWindowText(hwnd) or "").lower():
            return "unknown"
        L, T, Rr, Bb = win32gui.GetWindowRect(hwnd)
    except Exception:
        return "unknown"
    W, Hh = Rr - L, Bb - T
    if W <= 0 or Hh <= 0:
        return "unknown"
    try:
        shot = executor("gui", {"action": "locate_text", "text": contact_name, "min_conf": 20})
    except Exception:
        return "unknown"
    if not isinstance(shot, dict):
        return "unknown"
    matches = shot.get("matches")
    if not isinstance(matches, list):
        return "unknown"
    # Región del encabezado en coords de PANTALLA. Excluye sidebar (x<0.30W) y
    # mensajes (y>0.18H). locate_text añade screen_x/screen_y pre-traducidos.
    hx0, hx1 = L + W * 0.30, L + W * 0.88
    hy0, hy1 = T + Hh * 0.02, T + Hh * 0.18
    saw_anywhere = False
    for m in matches:
        if not isinstance(m, dict):
            continue
        sxv = m.get("screen_x"); syv = m.get("screen_y")
        if sxv is None or syv is None:
            continue
        saw_anywhere = True
        try:
            if hx0 <= float(sxv) <= hx1 and hy0 <= float(syv) <= hy1:
                return "confirmed"
        except (TypeError, ValueError):
            continue
    # Apareció en pantalla pero NO en el encabezado -> chat equivocado (no enviar).
    # No apareció en ningún lado -> unknown (WebView2 puede no exponer el header).
    return "wrong_chat" if saw_anywhere else "unknown"


def _verify_visible_whatsapp_text_status(executor: Executor, target_text: str) -> str:
    """Confirma por OCR que un texto reciente quedo visible en WhatsApp."""
    import re as _re

    def _fold(s: str) -> str:
        s = unicodedata.normalize("NFKD", s.casefold())
        s = "".join(ch for ch in s if not unicodedata.combining(ch))
        return _re.sub(r"[^a-z0-9 ]", " ", s)

    target = (target_text or "").strip()
    if not target:
        return "unknown"
    try:
        import win32gui  # type: ignore
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return "unknown"
        title = win32gui.GetWindowText(hwnd) or ""
        if "whatsapp" not in title.lower():
            return "unknown"
        rect = win32gui.GetWindowRect(hwnd)
    except Exception:
        return "unknown"

    try:
        shot = executor("gui", {"action": "screenshot", "monitor": "all"})
    except Exception:
        return "unknown"
    if not isinstance(shot, dict) or not shot.get("ok") or not shot.get("image_path"):
        return "unknown"

    try:
        from PIL import Image
        from ..tools_pkg.ops_tools import ocr_find_text
        image_path = Path(str(shot["image_path"]))
        img = Image.open(image_path)
        screen_left = int(shot.get("left", 0))
        screen_top = int(shot.get("top", 0))
        left, top, right, bottom = [int(v) for v in rect]
        box = (
            max(0, left - screen_left),
            max(0, top - screen_top),
            min(img.width, right - screen_left),
            min(img.height, bottom - screen_top),
        )
        if box[2] <= box[0] or box[3] <= box[1]:
            return "unknown"
        crop_path = image_path.with_name(image_path.stem + "_whatsapp_crop.png")
        img.crop(box).save(crop_path)
        found = ocr_find_text(crop_path, target[:80], lang="spa+eng", min_conf=25)
    except Exception:
        return "unknown"

    if not isinstance(found, dict):
        return "unknown"
    if found.get("found"):
        return "confirmed"
    ocr_text = str(found.get("ocr_text") or found.get("text") or "")
    if not ocr_text:
        return "unknown"
    ocr_norm = _fold(ocr_text)
    target_tokens = [t for t in _fold(target).split() if len(t) >= 4]
    if not target_tokens:
        return "unknown"
    needed = target_tokens[: min(4, len(target_tokens))]
    return "confirmed" if all(t in ocr_norm for t in needed) else "unknown"


def _capture_whatsapp_chat_area(executor: Executor) -> dict[str, Any] | None:
    """Captura la zona de mensajes del chat activo, excluyendo sidebar e input."""
    try:
        import win32gui  # type: ignore
        from PIL import Image

        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return None
        title = win32gui.GetWindowText(hwnd) or ""
        if "whatsapp" not in title.lower():
            return None
        left, top, right, bottom = [int(v) for v in win32gui.GetWindowRect(hwnd)]
        shot = executor("gui", {"action": "screenshot", "monitor": "all"})
        if not isinstance(shot, dict) or not shot.get("ok") or not shot.get("image_path"):
            return None
        img = Image.open(Path(str(shot["image_path"]))).convert("RGB")
        screen_left = int(shot.get("left", 0))
        screen_top = int(shot.get("top", 0))
        w = max(1, right - left)
        h = max(1, bottom - top)
        # WhatsApp desktop: sidebar a la izquierda, header arriba, composer abajo.
        box = (
            max(0, int(left + w * 0.35) - screen_left),
            max(0, int(top + h * 0.14) - screen_top),
            min(img.width, int(right - w * 0.02) - screen_left),
            min(img.height, int(bottom - h * 0.13) - screen_top),
        )
        if box[2] <= box[0] or box[3] <= box[1]:
            return None
        crop = img.crop(box)
        return {"image": crop, "box": box}
    except Exception:
        return None


def _whatsapp_chat_area_changed(
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
) -> bool:
    try:
        from PIL import ImageChops, ImageStat

        if not before or not after:
            return False
        a = before.get("image")
        b = after.get("image")
        if a is None or b is None:
            return False
        if a.size != b.size:
            b = b.resize(a.size)
        diff = ImageChops.difference(a.convert("RGB"), b.convert("RGB"))
        bbox = diff.getbbox()
        if bbox is None:
            return False
        area_ratio = ((bbox[2] - bbox[0]) * (bbox[3] - bbox[1])) / max(1, a.size[0] * a.size[1])
        mean_delta = sum(ImageStat.Stat(diff).mean) / 3.0
        return area_ratio >= 0.01 and mean_delta >= 0.35
    except Exception:
        return False


def _whatsapp_send_via_gui_search(
    executor: Executor,
    contact_name: str,
    text: str,
    wait_seconds: float,
    auto_send: bool,
) -> dict[str, Any]:
    """Abre WhatsApp generico, busca el contacto por nombre via Ctrl+N,
    selecciona el primer match, escribe el mensaje y opcionalmente envia.

    Flujo (todos los pasos requieren focus verification antes de teclear):
      1. Dispatch whatsapp:// (sin args -> abre la app generica).
      2. Wait wait_seconds para que cargue.
      3. Focus WhatsApp + verify active window title.
      4. Ctrl+N (abre nuevo chat / selector global de contacto).
      5. Type contact_name.
      6. Wait ~1s (deja que filtre los resultados).
      7. Enter (selecciona el primer chat).
      8. Wait ~0.5s (entra al chat).
      9. Type text del mensaje.
      10. Si auto_send: Enter (envia).

    Returns dict con keys:
      - sent: bool
      - chat_opened: bool
      - search_term: str
      - abort_reason: str | None
      - steps: list[str] — pasos completados (para debug)
    """
    import time as _time

    steps: list[str] = []
    action_results: list[dict[str, Any]] = []

    def _compact_result(result: Any) -> dict[str, Any]:
        if not isinstance(result, dict):
            return {"type": type(result).__name__}
        keep = (
            "ok", "error", "reason", "status", "completion_status", "verified",
            "state_changed", "state_verify", "method", "keys", "chars",
            "exit_code", "events", "found", "source", "action",
        )
        compact = {k: result.get(k) for k in keep if k in result}
        nested = result.get("result")
        if isinstance(nested, dict):
            compact["result"] = {
                k: nested.get(k)
                for k in ("ok", "error", "action", "title", "process", "pid", "hwnd")
                if k in nested
            }
        return compact

    def _result_failure(label: str, result: Any, *, require_effect: bool = False) -> str | None:
        if not isinstance(result, dict):
            return f"{label} returned non-dict result"
        if result.get("ok") is not True:
            return str(result.get("error") or result.get("reason") or "ok was not true")
        nested = result.get("result")
        if isinstance(nested, dict) and nested.get("ok") is False:
            return str(nested.get("error") or "nested result ok=false")
        if result.get("found") is False:
            return str(result.get("error") or "target window/control was not found")
        if require_effect and result.get("state_changed") is False:
            return str(result.get("state_verify") or "action caused no visible state change")
        events = result.get("events")
        if isinstance(events, (int, float)) and events <= 0:
            return "input injector reported zero events"
        exit_code = result.get("exit_code")
        if isinstance(exit_code, int) and exit_code != 0:
            return f"input command returned exit_code={exit_code}"
        return None

    def _abort(
        label: str,
        reason: str,
        *,
        chat_opened: bool = False,
        result: Any = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "sent": False,
            "chat_opened": chat_opened,
            "search_term": contact_name,
            "abort_reason": f"{label}: {reason}",
            "steps": steps,
            "physical_actions_ok": False,
            "gui_action_results": action_results,
        }
        if result is not None:
            payload["failed_step"] = label
            payload["failed_result"] = _compact_result(result)
        if extra:
            payload.update(extra)
        return payload

    def _checked_executor(
        tool: str,
        args: dict[str, Any],
        label: str,
        *,
        require_effect: bool = False,
    ) -> tuple[dict[str, Any] | None, str | None]:
        if tool == "gui" and str(args.get("action") or "") in {
            "click", "double_click", "right_click", "type", "type_into",
            "click_button", "keypress", "hotkey", "scroll", "drag",
        }:
            _wait_until_not_user_active()
        try:
            result = executor(tool, args)
        except Exception as exc:
            return None, f"{type(exc).__name__}: {exc}"
        failure = _result_failure(label, result, require_effect=require_effect)
        if failure:
            return result, failure
        action_results.append({"step": label, "tool": tool, **_compact_result(result)})
        return result, None

    def _focus_and_verify() -> tuple[bool, str | None, Any]:
        # window.focus ahora hace restore + maximize si la ventana es chica
        # (regla universal aplicada en tools.py:window_control). Damos grace
        # de 0.5s para que el maximize tome efecto antes de verificar.
        last_active: Any = None
        last_title = ""
        for attempt in range(3):
            focus, abort = _checked_executor(
                "window", {"action": "focus", "title": "WhatsApp"}, "focus WhatsApp")
            if abort is not None:
                return False, abort, focus
            _time.sleep(0.5 + 0.25 * attempt)
            active, abort = _checked_executor("window", {"action": "active"}, "read active window")
            if abort is not None:
                return False, abort, active
            last_active = active
            active_title = ""
            a = active.get("active") if isinstance(active, dict) else None
            if isinstance(a, dict):
                active_title = str(a.get("title") or "")
            elif isinstance(active, dict):
                active_title = str(active.get("title") or "")
            last_title = active_title
            if "whatsapp" in active_title.lower():
                return True, None, active
        return False, f"active window is not WhatsApp: {last_title!r}", last_active

    def _focus_compose_box() -> tuple[dict[str, Any] | None, str | None]:
        """Click en la caja de mensaje del chat activo sin depender del idioma UI."""
        try:
            import win32gui  # type: ignore
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd:
                return None, "no foreground window"
            title = win32gui.GetWindowText(hwnd) or ""
            if "whatsapp" not in title.lower():
                return None, f"active window is not WhatsApp: {title!r}"
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        except Exception as exc:
            return None, f"could not locate WhatsApp compose box: {exc}"
        width = max(1, right - left)
        height = max(1, bottom - top)
        x = int(left + width * 0.72)
        y = int(bottom - max(44, min(72, height * 0.05)))
        return _checked_executor(
            "gui", {"action": "click", "x": x, "y": y}, "focus compose box")

    def _wait_until_not_user_active(timeout_s: float = 3.0) -> None:
        try:
            from . import gui_safety
        except Exception:
            return
        deadline = _time.monotonic() + max(0.0, timeout_s)
        while _time.monotonic() < deadline:
            try:
                if not gui_safety.user_is_active():
                    return
            except Exception:
                return
            _time.sleep(0.2)

    # 1. Abrir WhatsApp (deeplink generico).
    try:
        subprocess.Popen(
            ["cmd", "/c", "start", "", "whatsapp://"],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, FileNotFoundError) as exc:
        return {
            "sent": False, "chat_opened": False, "search_term": contact_name,
            "abort_reason": f"failed to launch WhatsApp: {exc}", "steps": steps,
            "physical_actions_ok": False, "gui_action_results": action_results,
        }
    steps.append("dispatched_deeplink")
    _time.sleep(max(0.5, wait_seconds))

    # 2. Focus + verify (incluye restore+maximize implicito).
    focused, reason, result = _focus_and_verify()
    if not focused:
        return _abort(
            "focus WhatsApp after launch",
            reason or "could not focus WhatsApp window after launch",
            result=result,
        )
    steps.append("focused")
    # Extra grace tras maximize — el window manager necesita repaint.
    _time.sleep(0.4)

    # 3. BUSCADOR PRINCIPAL (NO Ctrl+N). MEDIDO 2026-05-31: Ctrl+N abre "Nuevo chat"
    # que busca solo CONTACTOS, no GRUPOS -> "Letras" daba "sin resultados" y el
    # texto terminaba en el chat ABIERTO (destinatario equivocado, daño irreversible).
    # El buscador principal (arriba-izq) SÍ encuentra grupos Y contactos. Lo enfocamos
    # por OCR del placeholder "Buscar" (fallback: coords sup-izq de la ventana).
    _search_pt = None
    try:
        import win32gui as _wg  # type: ignore
        _hwnd = _wg.GetForegroundWindow()
        _L, _T, _R, _B = _wg.GetWindowRect(_hwnd); _W, _H = _R - _L, _B - _T
        # Default: coords sup-izq de la ventana (donde vive el buscador principal).
        # OCR del placeholder "Buscar" lo refina si hay screenshot disponible.
        _search_pt = (int(_L + _W * 0.12), int(_T + _H * 0.095))
        _sshot = executor("gui", {"action": "screenshot", "monitor": "all"})
        if isinstance(_sshot, dict) and _sshot.get("image_path"):
            from ..tools_pkg.ops_tools import ocr_find_text as _oft
            _sx0 = int(_sshot.get("left", 0)); _sy0 = int(_sshot.get("top", 0))
            _f = _oft(Path(str(_sshot["image_path"])), "Buscar", min_conf=20)
            for _m in (_f.get("matches", []) if _f.get("found") else []):
                _cx = _m["center_x"] + _sx0; _cy = _m["center_y"] + _sy0
                if _cx < _L + _W * 0.32 and _cy < _T + _H * 0.20:
                    _search_pt = (int(_cx), int(_cy)); break
    except Exception:
        _search_pt = None
    if _search_pt is None:
        return _abort("focus main search", "could not locate WhatsApp search box")
    result, reason = _checked_executor(
        "gui", {"action": "click", "x": _search_pt[0], "y": _search_pt[1]},
        "focus main search box")
    if reason:
        return _abort("focus main search box", reason, result=result)
    steps.append("focused_main_search")
    _time.sleep(0.5)

    result, reason = _checked_executor(
        "gui",
        {
            "action": "keypress", "keys": "ctrl+a",
            "window": "WhatsApp", "method": "sendkeys",
        },
        "select contact search text",
    )
    if reason:
        return _abort("select contact search text", reason, result=result)
    steps.append("selected_contact_search_text")
    _time.sleep(0.1)

    # 4. Type del nombre del contacto.
    focused, reason, result = _focus_and_verify()
    if not focused:
        return _abort(
            "focus before typing contact name",
            reason or "lost WhatsApp focus before typing contact name",
            result=result,
        )
    result, reason = _checked_executor(
        "gui",
        {
            "action": "type", "text": contact_name,
            "window": "WhatsApp", "method": "sendkeys",
        },
        "type contact name",
    )
    if reason:
        return _abort("type contact name", reason, result=result)
    steps.append("typed_contact_name")
    _time.sleep(1.0)  # tiempo para que WhatsApp filtre

    # 5. Enter para seleccionar primer resultado y entrar al chat.
    focused, reason, result = _focus_and_verify()
    if not focused:
        return _abort(
            "focus before selecting contact",
            reason or "lost WhatsApp focus before selecting contact",
            result=result,
        )
    # En el buscador principal hay que BAJAR al primer resultado y abrirlo (Down+Enter).
    _checked_executor(
        "gui", {"action": "keypress", "keys": "down", "window": "WhatsApp", "method": "sendkeys"},
        "highlight first result")
    _time.sleep(0.3)
    result, reason = _checked_executor(
        "gui",
        {
            "action": "keypress", "keys": "enter",
            "window": "WhatsApp", "method": "sendkeys",
        },
        "select first contact match",
    )
    if reason:
        return _abort("select first contact match", reason, result=result)
    steps.append("selected_first_match")
    _time.sleep(0.8)  # entrar al chat

    # Enter normalmente cierra el selector de nuevo chat. No mandamos Escape aqui:
    # necesitamos conservar el presupuesto fisico para enfocar la caja de mensaje.

    # 5b. Verificacion hard gate. Nunca escribir/enviar si no vemos evidencia
    # del header del chat pedido. Antes "unknown" seguia adelante y podia marcar
    # sent=True aunque el texto hubiera quedado en un buscador o en otro chat.
    chat_status = _verify_chat_header_status(executor, contact_name)
    chat_verified = chat_status == "confirmed"
    steps.append(f"chat_header_verified:{chat_verified}")
    steps.append(f"chat_header_status:{chat_status}")
    # GATE de destinatario por nivel de RIESGO (2026-05-31):
    #  - ENVIAR (text presente, DESTRUCTIVO): exigir "confirmed". Nunca escribir a
    #    ciegas — evita C1 "destinatario equivocado = daño irreversible" (caso
    #    Letras/Vecinos). "unknown"/"wrong_chat" -> abort.
    #  - ABRIR (open_chat, sin text, NO destructivo): basta con NO detectar un chat
    #    EQUIVOCADO. "unknown" (WebView2 no expone el header por OCR/UIA) SIGUE: el chat
    #    casi seguro abrió con Down+Enter sobre el primer resultado y el usuario lo ve
    #    por screenshot. Solo "wrong_chat" (header corto y distinto) aborta.
    #    MEDIDO en vivo: "Abre el chat de Pedro y sacá una foto" abortaba en "unknown"
    #    (27s) aunque el chat ESTABA abierto — Pedro es contacto real (no en el store
    #    del agente -> gui_search) y el header no es OCR-legible.
    _is_send = bool(text)
    _gate_fail = (chat_status != "confirmed") if _is_send else (chat_status == "wrong_chat")
    if _gate_fail:
        return {
            "sent": False,
            "chat_opened": chat_status == "wrong_chat",
            "search_term": contact_name,
            "abort_reason": (
                f"no pude confirmar que el chat abierto es de '{contact_name}' "
                "despues de buscarlo — no escribo para no mandar al chat equivocado."
            ),
            "steps": steps, "chat_verified": False, "chat_header_status": chat_status,
            "physical_actions_ok": False, "gui_action_results": action_results,
        }
    chat_area_before_send = _capture_whatsapp_chat_area(executor)

    # 6. Type del mensaje (focus moved al input del chat).
    if not text:
        # open_chat: solo queriamos llegar al chat, no mandar.
        return {
            "sent": False, "chat_opened": True, "search_term": contact_name,
            "abort_reason": None, "steps": steps, "chat_verified": chat_verified,
            "chat_header_status": chat_status, "physical_actions_ok": True,
            "gui_action_results": action_results,
        }
    focused, reason, result = _focus_and_verify()
    if not focused:
        return _abort(
            "focus before typing message",
            reason or "lost WhatsApp focus before typing message",
            chat_opened=True,
            result=result,
        )
    result, reason = _focus_compose_box()
    if reason:
        return _abort("focus compose box", reason, chat_opened=True, result=result)
    steps.append("focused_compose_box")
    _time.sleep(0.2)
    result, reason = _checked_executor(
        "gui",
        {
            "action": "type", "text": text,
            "window": "WhatsApp", "method": "sendkeys",
        },
        "type message",
    )
    if reason:
        return _abort("type message", reason, chat_opened=True, result=result)
    steps.append("typed_message")
    _time.sleep(0.4)

    # 7. Enviar si auto_send.
    if not auto_send:
        return {
            "sent": False, "chat_opened": True, "search_term": contact_name,
            "abort_reason": None, "steps": steps, "chat_verified": chat_verified,
            "chat_header_status": chat_status, "physical_actions_ok": True,
            "gui_action_results": action_results,
        }
    focused, reason, result = _focus_and_verify()
    if not focused:
        return _abort(
            "focus before sending",
            reason or "lost WhatsApp focus before sending",
            chat_opened=True,
            result=result,
        )
    result, reason = _checked_executor(
        "gui",
        {
            "action": "keypress", "keys": "enter",
            "window": "WhatsApp", "method": "sendkeys",
        },
        "send message",
    )
    if reason:
        return _abort("send message", reason, chat_opened=True, result=result)
    steps.append("sent_enter")
    _time.sleep(0.8)
    chat_area_after_send = _capture_whatsapp_chat_area(executor)
    visual_changed = _whatsapp_chat_area_changed(chat_area_before_send, chat_area_after_send)
    steps.append(f"sent_message_area_changed:{visual_changed}")
    message_status = _verify_visible_whatsapp_text_status(executor, text)
    steps.append(f"sent_message_visible:{message_status}")
    if message_status != "confirmed" and not visual_changed:
        return {
            "sent": False, "chat_opened": True, "search_term": contact_name,
            "abort_reason": (
                "no pude verificar en pantalla que el mensaje enviado aparezca "
                "en el chat despues de presionar Enter."
            ),
            "steps": steps, "chat_verified": chat_verified,
            "chat_header_status": chat_status,
            "sent_message_visible_status": message_status,
            "sent_message_area_changed": visual_changed,
            "physical_actions_ok": False,
            "gui_action_results": action_results,
        }
    return {
        "sent": True, "chat_opened": True, "search_term": contact_name,
        "abort_reason": None, "steps": steps, "chat_verified": chat_verified,
        "chat_header_status": chat_status, "physical_actions_ok": True,
        "sent_message_visible_status": message_status,
        "sent_message_area_changed": visual_changed,
        "gui_action_results": action_results,
    }


def _whatsapp_auto_send(executor: Executor, wait_seconds: float) -> dict[str, Any]:
    """Tras abrir el chat con el deeplink, esperar carga, asegurar focus
    de la ventana WhatsApp, y mandar Enter.

    Devuelve dict con keys:
      - "sent": bool — True si llegamos a mandar Enter.
      - "focus_verified": bool — si confirmamos que la ventana activa era WhatsApp.
      - "abort_reason": str | None — por que NO mandamos Enter (si aplica).
      - "wait_seconds": float — cuanto esperamos antes del Enter.

    Seguridad: NUNCA mandar Enter si no podemos confirmar que la ventana
    activa contiene "WhatsApp" en el titulo. De lo contrario el Enter va a
    la app que el user tenia en focus (IDE, browser, terminal con comando
    peligroso, etc.).
    """
    import time as _time
    # 1. Esperar a que WhatsApp termine de cargar el chat + rellenar texto.
    _time.sleep(max(0.5, wait_seconds))

    # 2. Asegurar focus: pedir explicitamente que la ventana de WhatsApp
    #    venga al frente. Si no esta abierta, esto falla silenciosamente.
    try:
        focus_result = executor("window", {"action": "focus", "title": "WhatsApp"})
    except Exception as exc:
        return {
            "sent": False, "focus_verified": False,
            "abort_reason": f"focus call failed: {exc}",
            "wait_seconds": wait_seconds,
        }
    focus_ok = bool(focus_result.get("ok"))

    # 3. Verificar que la ventana activa es realmente WhatsApp antes del Enter.
    #    Damos un pequeño grace para que el focus tome efecto.
    _time.sleep(0.3)
    try:
        active = executor("window", {"action": "active"})
    except Exception as exc:
        return {
            "sent": False, "focus_verified": False,
            "abort_reason": f"active check failed: {exc}",
            "wait_seconds": wait_seconds,
        }
    active_title = str(
        (active.get("active") or {}).get("title")
        if isinstance(active.get("active"), dict)
        else (active.get("title") or "")
    ).lower()
    if "whatsapp" not in active_title:
        return {
            "sent": False, "focus_verified": False,
            "abort_reason": (
                f"active window is {active_title!r}, not WhatsApp. "
                "Refusing to send Enter to a different app."
            ),
            "wait_seconds": wait_seconds,
            "focus_call_ok": focus_ok,
        }

    # 4. Enter — la ventana correcta esta en foco, podemos enviar el mensaje.
    try:
        keypress_result = executor("gui", {"action": "keypress", "keys": "enter"})
    except Exception as exc:
        return {
            "sent": False, "focus_verified": True,
            "abort_reason": f"keypress failed: {exc}",
            "wait_seconds": wait_seconds,
        }
    if not keypress_result.get("ok"):
        return {
            "sent": False, "focus_verified": True,
            "abort_reason": f"keypress returned: {keypress_result.get('error', 'unknown')}",
            "wait_seconds": wait_seconds,
        }
    return {
        "sent": True, "focus_verified": True,
        "abort_reason": None,
        "wait_seconds": wait_seconds,
        "active_window_title": active_title,
    }


def whatsapp_tool(
    args: dict[str, Any],
    state: AgentState,
    executor: Executor | None = None,
) -> dict[str, Any]:
    """Compound WhatsApp tool.

    Actions:
      - status:        report whether WhatsApp Desktop (UWP) is installed.
      - send_message:  open WhatsApp chat with phone + pre-filled text.
                        With auto_send=True (default) the tool waits for the
                        chat to load, focuses the WhatsApp window, verifies
                        active window is WhatsApp, then sends Enter — message
                        is actually delivered. With auto_send=False the chat
                        opens but Enter is NOT pressed (legacy behavior).
      - open_chat:     same as send_message but without text (just opens chat,
                        auto_send is ignored here).

    Phone resolution priority:
      1. args.phone (explicit, validated and normalized)
      2. args.contact / args.recipient / args.to / args.name -> lookup in
         state contacts (using existing _contacts_resolve_recipient).

    Safety for auto_send:
      - NEVER sends Enter without confirming the active window title contains
        "WhatsApp". This prevents sending Enter to a wrong window (IDE,
        terminal with destructive command, browser form, etc.).
      - If focus or active-window check fails, returns sent=False with
        abort_reason — the user sees the chat opened and can press Enter
        themselves.

    Defaults:
      auto_send=True for send_message (Meta deeplink doesn't actually auto-send;
      we provide a safe wrapper that does it via a verified keypress sequence).
      Pass auto_send=False if you only want the chat opened for the user to
      review/edit before sending.
    """
    import urllib.parse

    action = str(args.get("action") or "send_message").casefold()

    if action == "status":
        app_info = _find_whatsapp_app()
        return _ok(
            installed=app_info["kind"] is not None,
            app_kind=app_info["kind"],
            launch_target=app_info["launch_target"],
            web_fallback="https://wa.me/<phone>?text=<msg>",
            auto_send_supported=executor is not None,
            note=(
                "send_message with auto_send=True (default) opens chat AND sends "
                "after verifying focus. Set auto_send=False to only open the chat."
            ),
        )

    if action not in {"send_message", "open_chat", "send"}:
        return _err(
            f"unknown action: {action!r}",
            hint="Use action='send_message', 'open_chat', or 'status'.",
        )

    # Resolver destinatario.
    resolved = _resolve_whatsapp_recipient(args, state)
    if isinstance(resolved, dict):  # error
        return resolved
    raw_phone, normalized, source, gui_search_name = resolved

    # Mensaje (opcional para open_chat).
    text = str(args.get("text") or args.get("message") or args.get("body") or "").strip()
    if action in {"send_message", "send"} and not text:
        return _err(
            "missing text for send_message",
            hint="Pass text='<your message>' or use action='open_chat' to just open the chat.",
            status="needs_user",
        )

    # auto_send default True para send_message; False para open_chat.
    # Acepta string truthy/falsy y bool. Si executor=None, no podemos auto_send.
    auto_send_raw = args.get("auto_send", action != "open_chat")
    if isinstance(auto_send_raw, str):
        auto_send = auto_send_raw.strip().lower() not in {"", "false", "0", "no", "off"}
    else:
        auto_send = bool(auto_send_raw)
    if executor is None:
        auto_send = False  # sin executor no podemos focus+keypress
    # open_chat nunca envia: solo abre.
    if action == "open_chat":
        auto_send = False

    # PATH GUI SEARCH: si el resolver indico que necesitamos buscar el
    # contacto via la UI de WhatsApp (porque no tenemos phone), usar el
    # flujo Ctrl+F + type contact_name + Enter + type message + Enter.
    # Esto cubre contactos que existen en WhatsApp pero no en nuestro
    # contacts store local.
    if source == "gui_search" and gui_search_name and executor is not None:
        app_info = _find_whatsapp_app()
        if not app_info["kind"]:
            return _err(
                f"WhatsApp Desktop not installed; cannot search for contact {gui_search_name!r}",
                status="needs_user", provider="whatsapp",
                hint=("Install WhatsApp Desktop from Microsoft Store, OR add "
                      f"the contact phone first: contacts(action='create', "
                      f"name='{gui_search_name}', phone='+...')."),
            )
        wait_seconds_raw = args.get("wait_seconds") or args.get("send_delay_s") or 2.0
        try:
            wait_seconds = max(0.5, min(10.0, float(wait_seconds_raw)))
        except (TypeError, ValueError):
            wait_seconds = 2.0
        gui_result = _whatsapp_send_via_gui_search(
            executor, gui_search_name, text, wait_seconds, auto_send,
        )
        sent = bool(gui_result.get("sent"))
        chat_opened = bool(gui_result.get("chat_opened"))
        return _ok(
            action=action,
            provider="whatsapp_desktop_gui_search",
            recipient_contact=gui_search_name,
            recipient_source="gui_search",
            text=text or None,
            opened=chat_opened or gui_result.get("steps", []) != [],
            sent=sent,
            chat_opened=chat_opened,
            auto_send_attempted=auto_send,
            physical_actions_ok=bool(gui_result.get("physical_actions_ok")),
            gui_search_info=gui_result,
            verified=sent,
            status="dispatched" if sent else "attempted",
            completion_search="message_sent_via_gui_search" if sent
                               else "chat_search_partial",
            completion_status="message_sent" if sent
                               else ("chat_opened_pending_message"
                                     if chat_opened else "search_aborted"),
            note=(
                f"Sent {text!r} to {gui_search_name!r} via WhatsApp Desktop GUI search."
                if sent else
                f"WhatsApp GUI search for {gui_search_name!r} did not complete. "
                f"Reason: {gui_result.get('abort_reason') or 'unknown'}. "
                f"Steps completed: {gui_result.get('steps')}."
            ),
        )
    if source == "gui_search" and executor is None:
        return _err(
            f"contact {gui_search_name!r} requires GUI search but no executor "
            "available (CLI mode)",
            status="needs_user",
            hint=(
                "From CLI, pass phone='+...' explicitly, or run inside the agent "
                "where executor is wired."
            ),
        )
    # Tiempo de espera tras el deeplink antes de mandar Enter. Configurable
    # via args.wait_seconds. Default 1.8s — suficiente para que WhatsApp
    # Desktop ya este corriendo cargue el chat y rellene el input. Primera
    # vez en frio puede tardar mas; el user puede subirlo.
    wait_seconds_raw = args.get("wait_seconds") or args.get("send_delay_s") or 1.8
    try:
        wait_seconds = float(wait_seconds_raw)
    except (TypeError, ValueError):
        wait_seconds = 1.8
    wait_seconds = max(0.3, min(10.0, wait_seconds))

    # Construir URLs. Deeplink desktop scheme y wa.me como fallback.
    encoded_text = urllib.parse.quote(text) if text else ""
    deeplink = f"whatsapp://send?phone={normalized}"
    if encoded_text:
        deeplink += f"&text={encoded_text}"
    web_url = f"https://wa.me/{normalized}"
    if encoded_text:
        web_url += f"?text={encoded_text}"

    app_info = _find_whatsapp_app()
    desktop_err: str | None = None

    # PATH 1: WhatsApp Desktop instalado -> deeplink whatsapp://
    if app_info["kind"] and os.name == "nt":
        try:
            subprocess.Popen(
                ["cmd", "/c", "start", "", deeplink],
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, FileNotFoundError) as exc:
            desktop_err = str(exc)
        else:
            # Auto-send si esta habilitado y tenemos executor.
            auto_send_info: dict[str, Any] | None = None
            if auto_send and executor is not None:
                auto_send_info = _whatsapp_auto_send(executor, wait_seconds)
            sent = bool(auto_send_info and auto_send_info.get("sent"))
            return _ok(
                action=action,
                provider="whatsapp_desktop",
                recipient_phone=raw_phone,
                recipient_normalized=normalized,
                recipient_source=source,
                text=text or None,
                deeplink=deeplink,
                app_kind=app_info["kind"],
                opened=True,
                sent=sent,
                auto_send_attempted=auto_send,
                auto_send_info=auto_send_info,
                verified=sent,
                status="dispatched" if sent else "attempted",
                completion_status="message_sent" if sent
                                   else "chat_opened_pending_enter",
                note=(
                    "Message sent: WhatsApp focused + verified active window + Enter pressed."
                    if sent
                    else (
                        f"WhatsApp Desktop opened with chat pre-filled. "
                        f"{'Auto-send aborted: ' + (auto_send_info or {}).get('abort_reason', '?') + '. ' if auto_send_info and not sent else ''}"
                        "User can press Enter manually."
                    )
                ),
            )

    # PATH 2: fallback a wa.me (web). Auto_send aqui es mas fragil porque
    # depende del estado del browser (loguead/no, "Continuar al chat" click,
    # etc). Mantenemos auto_send=False en este path por seguridad.
    try:
        import webbrowser
        opened = webbrowser.open(web_url)
        if opened:
            result = _ok(
                action=action,
                provider="whatsapp_web",
                recipient_phone=raw_phone,
                recipient_normalized=normalized,
                recipient_source=source,
                text=text or None,
                url=web_url,
                opened=True,
                sent=False,
                auto_send_attempted=auto_send,
                auto_send_info={"abort_reason": "web fallback does not support auto_send safely"}
                                if auto_send else None,
                verified=False,
                status="attempted",
                completion_status="chat_opened_pending_enter",
                note=(
                    "wa.me (WhatsApp Web) opened in default browser. Auto-send "
                    "is disabled on the web path because we cannot reliably "
                    "verify the chat input has focus. User must click "
                    "'Continuar al chat' and press Enter."
                ),
            )
            if desktop_err:
                result["fallback_from"] = "whatsapp_desktop"
                result["fallback_reason"] = desktop_err
            return result
    except Exception as exc:
        return _err(
            f"Could not open WhatsApp (desktop deeplink and web both failed): {exc}",
            status="failed", provider="whatsapp",
            desktop_error=desktop_err,
        )
    return _err(
        "WhatsApp: no desktop app and webbrowser refused to open wa.me",
        status="needs_user", provider="whatsapp",
        install_hint="winget install WhatsApp.WhatsApp",
    )


# Notes / Tasks domain tool - extraído a domain_tools_notes.py (R2 sprint
# 2026-05-27). Re-export para compat (tools.py linea 51 hace
# ).
from .notes import notes_tasks_tool  # noqa: F401


# Local Calendar (ICS) domain tool - extraído a domain_tools_calendar.py
# (R2 sprint 2026-05-27). 9 funciones (entry + 8 helpers ICS). domain_tools.py
# ~-260 LOC. Re-export para compat (tools.py linea 33).
from .calendar import (  # noqa: F401  (re-export por compat)
    _calendar_event_update,
    _calendar_export_path,
    _calendar_ics_import,
    _events_to_ics,
    _ics_escape,
    _ics_normalize_datetime,
    _ics_parse_events,
    _ics_time,
    _ics_unescape,
    local_calendar_tool,
)


# Habit Tracker - extraído a domain_tools_habit_tracker.py (R2 sprint 2026-05-28).
from .habit_tracker import (  # noqa: F401
    _VALID_HABIT_FREQUENCIES,
    habit_tracker_tool,
)


# Local Search - extraído a domain_tools_local_search.py (R2 sprint 2026-05-28).
from .local_search import local_search_tool  # noqa: F401


# Printer & Scanner - extraído a domain_tools_printer_scanner.py
# (R2 sprint 2026-05-28). 6 funciones (entry + 5 helpers).
from .printer_scanner import (  # noqa: F401
    _printer_cancel_job,
    _printer_print_file,
    _printer_set_default,
    _scanner_scan,
    _scanners_list,
    printer_scanner_tool,
)


# _json_or_none — extraído a domain_tools_helpers.py (R3 sprint 2026-05-28).


# Desktop Layout (Win32 EnumWindows + MoveWindow) - extraído a
# domain_tools_desktop_layout.py (R2 sprint 2026-05-28). 4 funciones.
from .desktop_layout import (  # noqa: F401
    _desktop_layout_restore,
    _enum_windows_with_rect,
    _move_window_by_title,
    desktop_layout_tool,
)


# Backup & Sync - extraído a domain_tools_backup_sync.py (R2 sprint 2026-05-28).
# Re-export incluye _next_available_path porque photo_library_tool lo usa
# desde línea ~1856.
from .backup_sync import (  # noqa: F401
    _backup_dedupe,
    _backup_resolve,
    _backup_restore,
    _backup_verify,
    _next_available_path,
    backup_sync_tool,
)


# Office helpers - extraídos a domain_tools_office.py (R2 sprint 2026-05-28).
# Re-export en el entry point office_tool más arriba.


# _safe_name — extraído a domain_tools_helpers.py (R3 sprint 2026-05-28).


def _audio_endpoints() -> list[dict[str, Any]]:
    script = "Get-PnpDevice -Class AudioEndpoint | Select-Object FriendlyName,Status,InstanceId | ConvertTo-Json -Depth 3"
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=20)
    if proc.returncode != 0 or not proc.stdout.strip():
        return []
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return []
    if isinstance(data, dict):
        data = [data]
    return data if isinstance(data, list) else []


# _find_soundvolumeview — extraído a domain_tools_helpers.py (R3 sprint 2026-05-28).


def _set_default_audio_device(args: dict[str, Any], state: AgentState, *, communications: bool) -> dict[str, Any]:
    name = str(args.get("name") or args.get("device") or "").strip()
    if not name:
        return _err("missing device name")
    helper = _find_soundvolumeview()
    if not helper:
        return _err(
            "setting default audio device needs SoundVolumeView or a custom WASAPI policy helper",
            requested=name,
            status="needs_dependency",
            verified=False,
            completion_status="needs_dependency",
            install_hint="Download SoundVolumeView.zip from NirSoft and set GEMMA4_SOUNDVOLUMEVIEW to its exe path.",
        )

    devices_before = _svv_list_devices()
    target = _svv_find_device(devices_before, name)
    if not target:
        return _err(
            "audio device not found",
            requested=name,
            available=[d.get("Name") or d.get("Device Name") for d in devices_before],
            status="needs_user",
            verified=False,
        )

    defaults_before = _svv_current_defaults(devices_before)
    rollback = _audio_rollback_steps(defaults_before)
    checkpoint = state.checkpoint(
        "audio default device change",
        rollback=rollback,
        metadata={
            "requested": name,
            "helper": str(helper),
            "communications": communications,
            "defaults_before": defaults_before,
            "device_before": target.get("Name") or target.get("Device Name"),
        },
    )

    # Role mapping (SoundVolumeView): 0=Console, 1=Multimedia, 2=Communications.
    roles = ["2"] if communications else ["0", "1"]
    role_names = {"0": "Console", "1": "Multimedia", "2": "Communications"}
    results = []
    for role in roles:
        proc = subprocess.run(
            [str(helper), "/SetDefault", name, role],
            capture_output=True, text=True, timeout=20,
        )
        results.append({
            "role": role,
            "role_name": role_names.get(role, role),
            "exit_code": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        })

    devices_after = _svv_list_devices()
    defaults_after = _svv_current_defaults(devices_after)
    expected_roles = ["Communications"] if communications else ["Console", "Multimedia"]
    verified = _audio_verify_default(defaults_after, name, expected_roles)
    return _ok(
        requested=name,
        helper=str(helper),
        roles=roles,
        results=results,
        defaults_before=defaults_before,
        defaults_after=defaults_after,
        checkpoint=checkpoint.get("checkpoint"),
        verified=verified,
        status="done" if verified else "needs_verification",
        evidence={"defaults_before": defaults_before, "defaults_after": defaults_after, "exit_codes": [r["exit_code"] for r in results]},
    )


def _restore_audio_default(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    checkpoint_id = str(args.get("checkpoint_id") or args.get("snapshot") or "").strip()
    data = state._load()
    checkpoints = data.get("checkpoints", {})
    checkpoint = None
    if checkpoint_id and checkpoint_id in checkpoints:
        checkpoint = checkpoints[checkpoint_id]
    else:
        # latest audio snapshot
        for cp in reversed(list(checkpoints.values())):
            if "audio" in str(cp.get("label", "")).casefold():
                checkpoint = cp
                break
    if not checkpoint:
        return _err("no audio checkpoint available; create one with audio_device(action=snapshot) first")

    helper = _find_soundvolumeview()
    if not helper:
        return _err(
            "audio_device.restore requires SoundVolumeView",
            status="needs_dependency",
            verified=False,
            install_hint="Download SoundVolumeView.zip from NirSoft and set GEMMA4_SOUNDVOLUMEVIEW.",
        )
    defaults = checkpoint.get("metadata", {}).get("defaults") or {}
    if not defaults:
        return _err("checkpoint has no defaults to restore", checkpoint_id=checkpoint.get("id"))

    role_to_int = {"Console": "0", "Multimedia": "1", "Communications": "2"}
    results = []
    for role_name, device_name in defaults.items():
        role_int = role_to_int.get(role_name)
        if not role_int or not device_name:
            continue
        proc = subprocess.run(
            [str(helper), "/SetDefault", device_name, role_int],
            capture_output=True, text=True, timeout=20,
        )
        results.append({
            "role": role_name,
            "device": device_name,
            "exit_code": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        })
    devices_after = _svv_list_devices()
    defaults_after = _svv_current_defaults(devices_after)
    verified = all(defaults_after.get(role) == device for role, device in defaults.items() if device)
    return _ok(
        restored_from=checkpoint.get("id"),
        defaults_requested=defaults,
        defaults_after=defaults_after,
        results=results,
        verified=verified,
        status="done" if verified else "needs_verification",
    )


def _svv_list_devices() -> list[dict[str, Any]]:
    """Use SoundVolumeView /sjson to dump full device table."""
    helper = _find_soundvolumeview()
    if not helper:
        return []
    import tempfile
    fd, tmp_path = tempfile.mkstemp(suffix=".json", prefix="svv_")
    os.close(fd)
    try:
        proc = subprocess.run(
            [str(helper), "/sjson", tmp_path],
            capture_output=True, text=True, timeout=20,
        )
        if proc.returncode != 0:
            return []
        raw = Path(tmp_path).read_text(encoding="utf-16", errors="replace").lstrip("﻿").strip()
        if not raw:
            # SoundVolumeView sometimes writes utf-8; retry.
            raw = Path(tmp_path).read_text(encoding="utf-8", errors="replace").lstrip("﻿").strip()
        if not raw:
            return []
        data = json.loads(raw)
        if isinstance(data, dict):
            data = [data]
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def _svv_current_defaults(devices: list[dict[str, Any]]) -> dict[str, str]:
    """Read per-role default from SoundVolumeView output.

    The /sjson dump has a 'Default' column with values like 'Render', 'Capture'
    or empty, plus a 'Default Multimedia', 'Default Communications' set in some
    versions. We prefer the columns 'Default' and 'Default Multimedia' /
    'Default Communications' when present, otherwise we fall back to the
    composite 'Default' string.
    """
    defaults: dict[str, str] = {}
    for dev in devices:
        if not isinstance(dev, dict):
            continue
        name = str(dev.get("Name") or dev.get("Device Name") or "").strip()
        if not name:
            continue
        direction = str(dev.get("Direction") or "").strip()
        if direction and direction.casefold() != "render":
            # Only render devices count for default playback roles here.
            # Recording defaults are mirrored under same columns; the role
            # name itself disambiguates downstream consumers.
            pass
        for role, column in (("Console", "Default"), ("Multimedia", "Default Multimedia"), ("Communications", "Default Communications")):
            value = str(dev.get(column) or "").strip().casefold()
            if value in {"render", "capture", "yes", "true", "1"}:
                # Only set if not already taken (first device wins for the role).
                defaults.setdefault(role, name)
    # Some SoundVolumeView builds collapse roles into a single "Default" column
    # carrying values like "Render;Multimedia". Handle that fallback.
    if not defaults:
        for dev in devices:
            if not isinstance(dev, dict):
                continue
            name = str(dev.get("Name") or dev.get("Device Name") or "").strip()
            raw = str(dev.get("Default") or "").strip().casefold()
            if not name or not raw:
                continue
            if "render" in raw or "capture" in raw:
                defaults.setdefault("Console", name)
                defaults.setdefault("Multimedia", name)
    return defaults


def _svv_find_device(devices: list[dict[str, Any]], query: str) -> dict[str, Any] | None:
    q = query.casefold().strip()
    if not q:
        return None
    # Exact match first
    for dev in devices:
        for key in ("Name", "Device Name", "Item ID"):
            if str(dev.get(key) or "").casefold() == q:
                return dev
    # Substring match second
    for dev in devices:
        for key in ("Name", "Device Name", "Item ID"):
            if q in str(dev.get(key) or "").casefold():
                return dev
    return None


def _audio_rollback_steps(defaults: dict[str, str]) -> list[dict[str, Any]]:
    """Build a list of {tool, args} rollback steps for the checkpoint."""
    steps: list[dict[str, Any]] = []
    if not defaults:
        return steps
    # Group Console+Multimedia under a single set_default (covers roles 0,1).
    normal_device = defaults.get("Multimedia") or defaults.get("Console")
    if normal_device:
        steps.append({"tool": "audio_device", "args": {"action": "set_default", "name": normal_device}})
    comm_device = defaults.get("Communications")
    if comm_device and comm_device != normal_device:
        steps.append({"tool": "audio_device", "args": {"action": "set_default_communications", "name": comm_device}})
    return steps


def _audio_verify_default(defaults_after: dict[str, str], requested_name: str, expected_roles: list[str]) -> bool:
    """Return True if the requested device matches all expected roles."""
    if not defaults_after:
        return False
    q = requested_name.casefold().strip()
    for role in expected_roles:
        current = str(defaults_after.get(role) or "").casefold()
        if not current:
            return False
        if q not in current and current not in q:
            return False
    return True


# Notification helpers - extraídos a domain_tools_notifications.py (R2 sprint
# 2026-05-27). Los 9 helpers + _NotificationDueError + _notification_due
# (parsing NL) viven ahora afuera; el re-export está en el bloque del entry
# point notification_tool más arriba (líneas ~263).


# Cross-cutting helpers (_find_routine, _update_resource_metadata,
# _resources_by_kind, _find_resource, _powershell_json, _ps_quote) — extraídos
# a domain_tools_helpers.py (R3 sprint 2026-05-28). El re-export más arriba
# del módulo (debajo del import de _ok/_err) deja `dt._X` accesible para los
# callers que hacen `from gemma4_agent import domain_tools as dt`. Estos
# bloques quedan como ancla histórica.


# Dependency catalog helpers - extraídos a domain_tools_dependency.py.


# Calendar helpers (ICS export utils) - extraídos a domain_tools_calendar.py
# (R2 sprint 2026-05-27). Los 4 helpers (_calendar_export_path, _events_to_ics,
# _ics_time, _ics_escape) viven junto al resto del calendar; el re-export está
# en el bloque del entry point más arriba.


def _run_detached_powershell(script: str) -> dict[str, Any]:
    proc = subprocess.Popen(
        ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", script],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    return {"pid": proc.pid}
