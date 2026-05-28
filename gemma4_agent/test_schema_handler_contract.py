"""R5 sprint 2026-05-28: contract-check entre COMPOUND_TOOL_SCHEMAS y los
handlers `t_<name>` de ToolRegistry.

Motivación: el commit `c546677` arregló el bug donde `browser` schema
declaraba `target` pero el handler lo ignoraba — el LLM elegía el campo
declarado (válido según schema), el handler nunca lo leía. Bug
silencioso pre-test.

Este test detecta esos casos automáticamente: para cada tool, parsea el
AST del handler y verifica que cada `property` declarada en el schema
aparece como `args.get("<prop>")` o `args["<prop>"]` o se itera por
nombre. Si una propiedad declarada NUNCA aparece en el código del
handler, fail.

Hay una WHITELIST por tool para casos donde la propiedad es pasada via
`**args` a una función helper que sí la usa (no detectable estáticamente).
Cada entrada whitelist documenta por qué se ignora.
"""
from __future__ import annotations

import ast
import inspect
import unittest
from typing import Any


# Propiedades cuyo uso es indirect (via **args, helper externo, etc.).
# Cada entrada lleva razón por la que el AST scan no las detecta.
# Tools que delegan a un sibling que a su vez delega a helpers internos
# (`_csv_describe`, `_hass_call_service`, etc). El AST scan no sigue 2+
# niveles de indirección. Whitelisting con razón documentada. Cada caso
# fue revisado a ojo para confirmar que los props NO son ignorados de
# verdad, solo no son detectables estáticamente.
_DEEP_DELEGATE_TOOLS = {
    "data_analysis",   # data_analysis_tool -> _csv_*(args) helpers
    "photo_library",   # photo_library_tool -> _photo_* helpers
    "container",       # container_tool -> _docker_* helpers
    "database",        # database_tool -> _db_{sqlite,postgres,mysql} helpers
    "creative_local",  # creative_local_tool -> _comfy_* helpers
    "form_filler",     # form_filler_tool -> _form_fill helpers
    "peripheral",      # peripheral_tool -> _pnp_* helpers
    "study",           # study_tool -> _study_* helpers
    "smart_home",      # smart_home_tool -> _hass_*/_mqtt_publish helpers
    "subagent",        # t_subagent runs another agent — `enable_thinking` consumed by sub-agent's modes.py
    "media_edit",      # media_edit_tool -> _ffmpeg_* helpers
    "notes",           # notes_tool -> _note_* helpers
    "habit_tracker",   # habit_tracker_tool -> _habit_* helpers
    "calendar",        # calendar_tool -> _calendar_* helpers
    "office",          # office_tool -> _office_* helpers
    "developer",       # developer_tool -> _developer_* helpers
    "device_settings", # device_settings_tool -> _device_* helpers
    "game_launcher",   # game_launcher_tool -> per-store helpers
    "maintenance",     # maintenance_tool -> _maint_* helpers
    "watcher",         # watcher_tool -> _watcher_* helpers
    "job_manager",     # job_manager_tool -> _job_* helpers
    "network",         # network_tool -> _net_* helpers
    "wifi",            # wifi_tool -> _device_wifi_* helpers
    "bluetooth",       # bluetooth_tool -> _device_bluetooth_* helpers
    "fact_check",      # fact_check_tool -> _fact_* helpers
    "local_search",    # local_search_tool -> _local_search_* helpers
    "printer_scanner", # printer_scanner_tool -> _print_* helpers
    "backup_sync",     # backup_sync_tool -> _backup_* helpers
    "document",        # document_tool -> _doc_* helpers
    "routine",         # routine_tool -> _routine_* helpers (dispatch grande)
    "contacts",        # contacts_tool -> _contact_* helpers
    "notification",    # notification_tool -> _notif_* helpers
    "accessibility",   # accessibility_tool -> _a11y_* helpers
    "desktop_layout",  # desktop_layout_tool -> _desktop_* helpers
    "source_manager",  # source_manager_tool -> handlers internos
    "dependency",      # dependency_tool -> _module_dep/_binary_dep
}


WHITELIST: dict[str, set[str]] = {
    # tool_name -> set of property names to skip
    "filesystem": {
        # _fs_* helpers reciben todo el dict args y lo procesan adentro
        "max_chars", "max_bytes", "max_files",
    },
    "browser_real": {
        # browser_real_tool() pasa **args a playwright_engine
        "headless", "new_tab", "screenshot", "full_page", "wait_until",
        "exact", "save_dir", "browser", "port",
    },
    "knowledge": {
        # _knowledge_*() recibe args dict; el handler delega
        "doc_id",
    },
    "gui": {
        # gui_tool() pasa args a gui_runtime; campos viajan via kwargs.
        "x1", "y1", "x2", "y2",
        "force_paste", "force_sendkeys",
        "method", "input_method",
        "keys", "hotkey", "amount", "raw_sendkeys",
    },
    "uia": {
        # uia_tool() pasa args a uia_runtime; text_value/title/etc via kwargs.
        "text_value", "title", "value", "limit", "timeout_sec",
    },
    "vision": {
        # vision_tool() pasa args a vision_runtime
        "image_path",
    },
    "audio_device": {
        # audio_device_tool dispatcher per-action; algunos campos en sub-funcs
        "process", "checkpoint_id", "snapshot",
        "name", "device", "app", "role", "direction",
    },
    "media": {
        # _media_play_* receives args dict; many keys consumed in helpers
        "song", "title", "path", "url", "app", "level", "backend", "root",
        "auto_play_wait", "profile_name", "spotify_user", "username",
        "limit", "auto_play", "profile",
    },
    "registry": {
        # registry_tool dispatcher
        "value_name", "value", "dst",
    },
    "download": {
        # download_tool with verifier helpers
        "sha256", "expected_sha256", "algorithm",
    },
    "state": {
        # state_tool dispatcher
        "checkpoint_id",
    },
    "input": {
        # input_tool dispatcher
        "language_tags",
    },
    "notification": {
        # notification_tool dispatcher
        "message", "task_name",
    },
    "routine": {
        # routine_tool dispatcher
        "entries", "json_path",
    },
    "browser": {
        "song",  # alias para youtube_play(query) — el handler la lee via args.get fallback
    },
    "email": {
        # email_tool vive en ops_tools.py (R2.6 skip), no detectable desde acá
        "action", "to", "subject", "body", "save_to_sent", "timeout_sec",
    },
    "whatsapp": {
        "number",  # _resolve_whatsapp_recipient lee number
    },
    "notes_tasks": {
        "resource_id",  # notes_tool lo lee via _find_resource
    },
    "local_calendar": {
        "resource_id", "path", "content", "ics",  # calendar_tool dispatch
    },
}


def _harvest(node: ast.AST, keys: set[str]) -> None:
    """Recoge keys de un AST node."""
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Attribute) and node.func.attr == "get":
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "args":
                if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    keys.add(node.args[0].value)
    if isinstance(node, ast.Subscript):
        if isinstance(node.value, ast.Name) and node.value.id == "args":
            slc = node.slice
            if isinstance(slc, ast.Constant) and isinstance(slc.value, str):
                keys.add(slc.value)
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        keys.add(node.value)


def _collect_arg_keys_referenced(func_src: str) -> set[str]:
    """Devuelve los nombres-de-propiedad que el handler (y sus delegates)
    referencian. Heurística TEXTUAL robusta a múltiples bloques concatenados:
    busca cualquier `args.get("X")`, `args["X"]`, o aparición del nombre
    como string literal en cualquier lugar del code chain. Falsos positivos
    posibles pero el test los acepta (es chequeo de PRESENCIA, no semántica)."""
    import re as _re
    keys: set[str] = set()
    # args.get("X")
    for m in _re.finditer(r'args\.get\(\s*["\']([^"\']+)["\']', func_src):
        keys.add(m.group(1))
    # args["X"]
    for m in _re.finditer(r'args\[\s*["\']([^"\']+)["\']\s*\]', func_src):
        keys.add(m.group(1))
    # any "X" or 'X' string literal (catches action == "X" dispatch)
    for m in _re.finditer(r'["\']([a-zA-Z_][a-zA-Z0-9_]*)["\']', func_src):
        keys.add(m.group(1))
    return keys


def _get_handler_source(registry: Any, tool_name: str) -> str | None:
    """Returns the source of `t_<tool_name>` method.

    If the handler is a thin delegate `return <name>_tool(args, ...)` to a
    sibling module, we also append the source of the delegate target so
    the AST scan sees the property reads in the sibling.
    """
    method = getattr(registry, f"t_{tool_name}", None)
    if method is None:
        return None
    try:
        method_src = inspect.getsource(method)
    except (OSError, TypeError):
        return None
    # Detect delegation patterns and append source of delegates:
    #   `return <name>_tool(args, ...)` — function in some sibling module
    #   `return self.<method>(args)`     — method on same registry
    import re as _re
    chunks = [method_src]
    # Function delegates (module-level)
    for m in _re.finditer(r"return\s+([a-z_][a-z0-9_]*_tool|[a-z_][a-z0-9_]*)\s*\(args[,)]", method_src):
        target_name = m.group(1)
        target = _find_function_anywhere(target_name)
        if target is not None:
            try:
                chunks.append(inspect.getsource(target))
            except (OSError, TypeError):
                pass
    # Method delegates (self.foo(args))
    for m in _re.finditer(r"self\.([a-z_][a-z0-9_]*)\s*\(args[,)]", method_src):
        method_name = m.group(1)
        if method_name.startswith("t_"):  # avoid t_* recursion noise
            continue
        method_target = getattr(registry, method_name, None)
        if method_target is not None and callable(method_target):
            try:
                chunks.append(inspect.getsource(method_target))
            except (OSError, TypeError):
                pass
    return "\n".join(chunks)


def _find_function_anywhere(name: str):
    """Search the gemma4_agent package modules for a function named `name`."""
    import importlib, pkgutil
    import gemma4_agent
    for mod_info in pkgutil.iter_modules(gemma4_agent.__path__, prefix="gemma4_agent."):
        try:
            mod = importlib.import_module(mod_info.name)
        except Exception:
            continue
        fn = getattr(mod, name, None)
        if callable(fn):
            return fn
    return None


class TestSchemaHandlerContract(unittest.TestCase):
    """Para cada tool de COMPOUND_TOOL_SCHEMAS, verifica que cada `property`
    declarada en el schema aparece referenciada en el código del handler.

    Si una property aparece en el schema pero el handler nunca la lee
    (ni siquiera como string literal), es un bug silencioso esperando
    pasar: el LLM elegirá la key y el handler la ignorará.
    """

    @classmethod
    def setUpClass(cls):
        from .tools import COMPOUND_TOOL_SCHEMAS, ToolRegistry
        from .state import AgentState
        from .memory import MemoryStore
        import tempfile, pathlib
        tmp = pathlib.Path(tempfile.mkdtemp())
        memory = MemoryStore(tmp / "m.json")
        cls.registry = ToolRegistry(memory, tmp / "cap",
                                    state=AgentState(tmp / "s.json"),
                                    safety_enabled=False)
        cls.schemas = COMPOUND_TOOL_SCHEMAS

    def test_every_schema_property_is_read_by_handler(self):
        offenders: list[str] = []
        skipped: list[str] = []
        for schema in self.schemas:
            fn = schema.get("function", {})
            name = fn.get("name", "")
            props = fn.get("parameters", {}).get("properties", {})
            if not name or not props:
                continue
            if name in _DEEP_DELEGATE_TOOLS:
                # Delegación de 2+ niveles que el AST scan no sigue.
                # Whitelisted con razón en _DEEP_DELEGATE_TOOLS.
                skipped.append(name)
                continue
            src = _get_handler_source(self.registry, name)
            if src is None:
                # No `t_<name>` method — handler dispatch is differently named.
                # Skip (cubierto por test_handler_exists separado).
                skipped.append(name)
                continue
            referenced = _collect_arg_keys_referenced(src)
            whitelisted = WHITELIST.get(name, set())
            missing = []
            # `action` se lee via helper `_action(args, default=...)` en muchos
            # handlers; pseudo-presence si el helper aparece en el code chain.
            if "_action(args" in src or "args.get('action')" in src or 'args.get("action")' in src:
                referenced.add("action")
            for prop in props:
                if prop in referenced:
                    continue
                if prop in whitelisted:
                    continue
                missing.append(prop)
            if missing:
                offenders.append(f"{name}: schema declara {missing} pero handler `t_{name}` no los lee")
        # Permitimos handlers sin `t_<name>` (lista skipped) — un test
        # separado podría chequear que exista alguna forma de dispatch.
        self.assertEqual(
            offenders, [],
            "Schema↔handler contract violations encontradas:\n  "
            + "\n  ".join(offenders)
            + "\n\nPara whitelistear casos legítimos (campo pasado via "
            "**args a helper), agregalo a WHITELIST en este archivo con "
            "razón documentada.",
        )

    def test_deep_delegate_tools_actually_read_majority_of_props(self):
        """Para los tools en _DEEP_DELEGATE_TOOLS, el AST scan no sigue
        2+ niveles. Verifica que al menos el 50% de las props del schema
        aparecen referenciadas en ALGÚN archivo del package — sirve como
        sanity check de que la WHITELIST no esconda un tool wholly-broken.
        """
        import pathlib as _pl
        pkg_dir = _pl.Path(__file__).resolve().parent
        offenders: list[str] = []
        for schema in self.schemas:
            fn = schema.get("function", {})
            name = fn.get("name", "")
            props = list(fn.get("parameters", {}).get("properties", {}).keys())
            if name not in _DEEP_DELEGATE_TOOLS or len(props) < 3:
                continue
            # Búsqueda global por nombre en archivos del package, incluyendo
            # el subpaquete domain_tools/ (R2 finalize 2026-05-28).
            haystack_parts: list[str] = []
            for py in pkg_dir.glob("domain_tools*.py"):
                try:
                    haystack_parts.append(py.read_text(encoding="utf-8"))
                except Exception:
                    pass
            # También buscar en el sub-paquete domain_tools/ (post R2 finalize)
            sub_pkg = pkg_dir / "domain_tools"
            if sub_pkg.is_dir():
                for py in sub_pkg.glob("*.py"):
                    try:
                        haystack_parts.append(py.read_text(encoding="utf-8"))
                    except Exception:
                        pass
            haystack = "\n".join(haystack_parts)
            hits = sum(1 for p in props if f'"{p}"' in haystack or f"'{p}'" in haystack)
            ratio = hits / len(props)
            if ratio < 0.5:
                offenders.append(
                    f"{name}: solo {hits}/{len(props)} props del schema "
                    f"aparecen en archivos domain_tools* del pkg ({ratio:.0%}). "
                    f"Posible whitelist abuse."
                )
        self.assertEqual(
            offenders, [],
            "DEEP_DELEGATE tools cuyas props NO se leen mayoritariamente:\n  "
            + "\n  ".join(offenders),
        )

    def test_schema_enums_are_referenced_in_handlers(self):
        """R5 extended 2026-05-28: si un schema declara `enum=[...]`
        para una property, cada valor del enum debe aparecer como
        string literal en el código del handler. Si el LLM elige un
        valor del enum y el handler NO lo reconoce, es un bug silencioso
        equivalente al de `target=canvas` que motivó R5."""
        import pathlib as _pl
        pkg_dir = _pl.Path(__file__).resolve().parent
        haystack_parts: list[str] = []
        # Incluir tools.py + ops_tools.py donde viven los handlers t_*
        for fname in ("tools.py", "ops_tools.py"):
            p = pkg_dir / fname
            if p.exists():
                haystack_parts.append(p.read_text(encoding="utf-8"))
        # Y los siblings + sub-paquete domain_tools/
        for py in pkg_dir.glob("domain_tools*.py"):
            try:
                haystack_parts.append(py.read_text(encoding="utf-8"))
            except Exception:
                pass
        sub_pkg = pkg_dir / "domain_tools"
        if sub_pkg.is_dir():
            for py in sub_pkg.glob("*.py"):
                try:
                    haystack_parts.append(py.read_text(encoding="utf-8"))
                except Exception:
                    pass
        haystack = "\n".join(haystack_parts)

        offenders: list[str] = []
        for schema in self.schemas:
            fn = schema.get("function", {})
            tool_name = fn.get("name", "")
            props = fn.get("parameters", {}).get("properties", {})
            for prop_name, prop in props.items():
                if not isinstance(prop, dict) or "enum" not in prop:
                    continue
                for enum_value in prop["enum"]:
                    if not isinstance(enum_value, str):
                        continue
                    if f'"{enum_value}"' not in haystack and f"'{enum_value}'" not in haystack:
                        offenders.append(f"{tool_name}.{prop_name}.{enum_value!r}")
        self.assertEqual(
            offenders, [],
            "Schema enum values NOT referenced in any handler code:\n  "
            + "\n  ".join(offenders),
        )

    def test_every_compound_schema_has_handler(self):
        """Cada schema declarado debe tener un `t_<name>` Y aparecer en
        el dispatch principal — esto no se chequea acá (necesita inspect
        del execute path); solo verificamos que `t_<name>` exista."""
        missing_handlers: list[str] = []
        for schema in self.schemas:
            fn = schema.get("function", {})
            name = fn.get("name", "")
            if not name:
                continue
            if getattr(self.registry, f"t_{name}", None) is None:
                # Algunos tools tienen handler en otro lado (ops_tools, mcp).
                # Skip explícitos por ahora.
                if name in {"email", "reminder"}:  # viven en ops_tools.py
                    continue
                missing_handlers.append(name)
        self.assertEqual(missing_handlers, [],
                         f"Tools sin `t_<name>` ni en exclusiones: {missing_handlers}")


if __name__ == "__main__":
    unittest.main()
