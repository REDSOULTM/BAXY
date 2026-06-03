"""Small local smoke checks for the Carter agent tools.

This does not call the LLM. It validates the tool catalog and the normalized
result contract used by the agent prompt.
"""

from __future__ import annotations

import argparse
import json

from ..infra.config import AgentConfig
from ..memory_pkg.memory import MemoryStore
from .modes import choose_mode
from ..routing.planner import plan_mission, select_tool_names
from .reasoning import sanitize_text
from ..memory_pkg.state import AgentState
from ..tools_pkg.tools import ToolRegistry


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--web", action="store_true", help="Also run a live web search")
    args = parser.parse_args()

    config = AgentConfig.from_env()
    tools = ToolRegistry(MemoryStore(config.memory_path), config.captures_dir, AgentState(config.state_path), safety_enabled=config.enable_safety)
    names = [schema["function"]["name"] for schema in tools.schemas]
    expected = {
        "system", "audio", "app", "steam", "window", "gui", "vision", "browser", "web", "uia",
        "filesystem", "package", "clipboard", "terminal", "memory", "verify", "state", "input",
        "env", "registry", "download", "email", "reminder", "browser_real", "knowledge", "safety",
        "office", "audio_device", "notification", "routine", "media",
        "source_manager", "dependency", "contacts", "notes_tasks", "local_calendar",
        "habit_tracker", "local_search", "printer_scanner", "desktop_layout", "backup_sync",
    }
    missing = sorted(expected - set(names))
    duplicate_count = len(names) - len(set(names))
    steam_schema = next(schema for schema in tools.schemas if schema["function"]["name"] == "steam")
    steam_actions = steam_schema["function"]["parameters"]["properties"]["action"].get("enum", [])
    steam_plan = plan_mission("abre steam, ve a mi biblioteca y busca doom eternal ahi dentro")
    steam_subset = select_tool_names("abre steam, ve a mi biblioteca y busca doom eternal ahi dentro", steam_plan, safety_enabled=config.enable_safety)
    casual_plan = plan_mission("quien es batman")
    casual_subset = select_tool_names("quien es batman", casual_plan, safety_enabled=config.enable_safety)

    checks = {
        "schema_count": len(names),
        "missing": missing,
        "duplicate_count": duplicate_count,
        "schemas_have_additional_properties_false": all(
            (schema["function"]["parameters"].get("additionalProperties") is False)
            for schema in tools.schemas
        ),
        "steam_has_store_page": "store_page" in steam_actions,
        "dynamic_subset_steam": steam_subset,
        "dynamic_subset_steam_schema_count": len(tools.schemas_for_names(steam_subset)),
        "dynamic_subset_casual": casual_subset,
        "mode_fast": choose_mode("quien es batman", "auto", config.max_tokens).name,
        "mode_deep": choose_mode("abre steam, luego ve a mi biblioteca y despues busca doom", "auto", config.max_tokens).name,
        "mode_research": choose_mode("investiga el nuevo juego de Batman con fuentes", "auto", config.max_tokens).name,
        "reasoning_sanitize": sanitize_text("<think>privado</think>respuesta"),
        "invalid_arg_rejected": tools.execute("verify", {"action": "file_exists", "path": __file__, "extra": "x"}),
        "system_time": tools.execute("system", {"action": "time"}),
        "file_verify": tools.execute("verify", {"action": "file_exists", "path": __file__}),
        "state_resources": tools.execute("state", {"action": "resources"}),
        "env_process_get": tools.execute("env", {"action": "get", "scope": "process", "name": "PATH"}),
        "input_language_list": tools.execute("input", {"action": "language_list"}),
        "download_hash": tools.execute("download", {"action": "hash", "path": __file__}),
        "browser_real_status": tools.execute("browser_real", {"action": "status"}),
        "email_status": tools.execute("email", {"action": "status"}),
        "knowledge_status": tools.execute("knowledge", {"action": "status"}),
        "office_status": tools.execute("office", {"action": "status"}),
        "audio_device_status": tools.execute("audio_device", {"action": "status"}),
        "notification_status": tools.execute("notification", {"action": "status"}),
        "routine_status": tools.execute("routine", {"action": "status"}),
        "media_status": tools.execute("media", {"action": "status"}),
        "source_manager_status": tools.execute("source_manager", {"action": "status"}),
        "dependency_status": tools.execute("dependency", {"action": "status"}),
        "contacts_status": tools.execute("contacts", {"action": "status"}),
        "notes_tasks_status": tools.execute("notes_tasks", {"action": "status"}),
        "local_calendar_status": tools.execute("local_calendar", {"action": "status"}),
        "habit_tracker_status": tools.execute("habit_tracker", {"action": "status"}),
        "local_search_status": tools.execute("local_search", {"action": "status"}),
        "printer_scanner_status": tools.execute("printer_scanner", {"action": "status"}),
        "desktop_layout_status": tools.execute("desktop_layout", {"action": "status"}),
        "backup_sync_status": tools.execute("backup_sync", {"action": "status"}),
        "safety_status": tools.execute("safety", {"action": "status"}),
    }
    if args.web:
        checks["web_search"] = tools.execute("web", {"action": "search", "query": "Gemma 4 Google model card", "limit": 2})

    print(json.dumps(checks, ensure_ascii=False, indent=2))
    return 1 if missing or duplicate_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
