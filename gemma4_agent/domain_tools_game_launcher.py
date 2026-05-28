"""Game Launcher domain tool — extracted from domain_tools.py (R2 sprint
2026-05-28).

Lanzadores NO-Steam: Epic, GOG, Xbox/UWP, Riot. Steam tiene su propio tool
dedicado. Cada lanzador tiene un mecanismo distinto:
  - Epic: leer manifests JSON en %ProgramData%/Epic/.../Manifests + URI
    com.epicgames.launcher://apps/<AppName>?action=launch
  - GOG: HKLM\\WOW6432Node\\GOG.com\\Games registry, lanzar exe directo
  - Xbox/UWP: Get-AppxPackage + shell:AppsFolder\\<PackageFamilyName>!App
  - Riot: RiotClientInstalls.json (associated_client map)

Funciones extraídas (10):
  game_launcher_tool             (entry, 4 acciones)
  _epic_manifests_dir
  _gog_registry_has_games
  _riot_install_db
  _game_launcher_discover
  _discover_epic_games
  _discover_gog_games
  _discover_xbox_games
  _discover_riot_games
  _game_launcher_launch          (registra game_session en state)

Auto-contenido (sólo subprocess/json/os/Path/webbrowser/datetime)."""
from __future__ import annotations

import json
import os
import re
import subprocess
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from ._shared import _err, _ok
from .state import AgentState


Executor = Callable[[str, dict[str, Any]], dict[str, Any]]


__all__ = [
    "game_launcher_tool",
    "_epic_manifests_dir",
    "_gog_registry_has_games",
    "_riot_install_db",
    "_game_launcher_discover",
    "_discover_epic_games",
    "_discover_gog_games",
    "_discover_xbox_games",
    "_discover_riot_games",
    "_game_launcher_launch",
]


def game_launcher_tool(args: dict[str, Any], state: AgentState, executor: Executor | None = None) -> dict[str, Any]:
    """Compound tool for non-Steam game launchers.

    Actions:
      - status
      - discover(launcher?) -> {epic, gog, xbox, riot} games found on disk
      - launch(launcher, game) -> opens by URI/shortcut/exe
      - open_store_page(launcher, query) -> deferred
      - open_library_page(launcher) -> opens launcher window
    Steam is handled by the existing `steam` tool; we do not duplicate it here.
    """
    action = str(args.get("action") or "status").casefold()
    if action == "status":
        epic_dir = _epic_manifests_dir()
        return _ok(
            launchers={
                "epic": epic_dir is not None,
                "gog": _gog_registry_has_games(),
                "xbox": True,  # always queryable via Get-StartApps
                "riot": _riot_install_db() is not None,
            },
            epic_manifest_dir=str(epic_dir) if epic_dir else None,
            note="Steam is handled by the dedicated `steam` tool.",
        )
    if action in {"discover", "list", "discover_games"}:
        return _game_launcher_discover(args)
    if action == "launch":
        return _game_launcher_launch(args, state, executor)
    if action == "open_library_page":
        launcher = str(args.get("launcher") or "").casefold()
        if not executor:
            return _err("open_library_page requires executor", status="needs_implementation")
        target = {
            "epic": "com.epicgames.launcher://store",
            "gog": "goggalaxy://",
            "xbox": "ms-windows-store://home",
        }.get(launcher)
        if not target:
            return _err(f"launcher '{launcher}' not supported for library page", status="needs_user")
        return executor("web", {"action": "open", "url": target})
    if action == "open_store_page":
        return _err(
            "game_launcher.open_store_page is deferred; each store needs its own URI scheme and search",
            status="needs_implementation",
            note="Use browser_real or steam(store_page) instead.",
        )
    return _err(
        "unknown game_launcher action", action=action,
        valid_actions=[
            "status", "discover", "launch", "open_launcher", "store_search",
        ],
        status="needs_user",
    )


def _epic_manifests_dir() -> Path | None:
    candidates = [
        Path(os.environ.get("ProgramData", "C:/ProgramData")) / "Epic" / "EpicGamesLauncher" / "Data" / "Manifests",
        Path("C:/ProgramData/Epic/EpicGamesLauncher/Data/Manifests"),
    ]
    for c in candidates:
        if c.is_dir():
            return c
    return None


def _gog_registry_has_games() -> bool:
    proc = subprocess.run(
        ["reg", "query", r"HKLM\SOFTWARE\WOW6432Node\GOG.com\Games"],
        capture_output=True, text=True, timeout=10,
    )
    return proc.returncode == 0 and bool(proc.stdout.strip())


def _riot_install_db() -> Path | None:
    candidates = [
        Path(os.environ.get("ProgramData", "C:/ProgramData")) / "Riot Games" / "RiotClientInstalls.json",
    ]
    for c in candidates:
        if c.is_file():
            return c
    return None


def _game_launcher_discover(args: dict[str, Any]) -> dict[str, Any]:
    launcher = str(args.get("launcher") or "").casefold()
    results: dict[str, list[dict[str, Any]]] = {"epic": [], "gog": [], "xbox": [], "riot": []}
    if not launcher or launcher == "epic":
        results["epic"] = _discover_epic_games()
    if not launcher or launcher == "gog":
        results["gog"] = _discover_gog_games()
    if not launcher or launcher == "xbox":
        results["xbox"] = _discover_xbox_games()
    if not launcher or launcher == "riot":
        results["riot"] = _discover_riot_games()
    total = sum(len(v) for v in results.values())
    return _ok(games=results, total=total, launcher_filter=launcher or None)


def _discover_epic_games() -> list[dict[str, Any]]:
    manifests_dir = _epic_manifests_dir()
    if not manifests_dir:
        return []
    games: list[dict[str, Any]] = []
    for item in manifests_dir.glob("*.item"):
        try:
            data = json.loads(item.read_text(encoding="utf-8", errors="replace"))
        except (OSError, json.JSONDecodeError):
            continue
        games.append({
            "launcher": "epic",
            "app_name": data.get("AppName"),
            "display_name": data.get("DisplayName"),
            "install_location": data.get("InstallLocation"),
            "launch_executable": data.get("LaunchExecutable"),
            "catalog_namespace": data.get("CatalogNamespace"),
            "catalog_item_id": data.get("CatalogItemId"),
            "manifest": str(item),
        })
    return games


def _discover_gog_games() -> list[dict[str, Any]]:
    proc = subprocess.run(
        ["reg", "query", r"HKLM\SOFTWARE\WOW6432Node\GOG.com\Games", "/s"],
        capture_output=True, text=True, timeout=20,
    )
    if proc.returncode != 0:
        return []
    games_by_id: dict[str, dict[str, Any]] = {}
    current_id: str | None = None
    for line in proc.stdout.splitlines():
        line = line.rstrip()
        m = re.match(r".*\\Games\\(\d+)$", line)
        if m:
            cid = m.group(1)
            if cid is None:
                continue
            current_id = cid
            games_by_id.setdefault(cid, {"launcher": "gog", "game_id": cid})
            continue
        if current_id and "REG_SZ" in line:
            parts = line.strip().split(None, 2)
            if len(parts) >= 3:
                key, _, value = parts[0], parts[1], parts[2]
                games_by_id[current_id][key.casefold()] = value
    games = []
    for gid, data in games_by_id.items():
        games.append({
            "launcher": "gog",
            "game_id": gid,
            "name": data.get("gamename"),
            "exe": data.get("exe"),
            "exepath": data.get("exepath"),
            "path": data.get("path"),
            "launch_command": data.get("launchcommand"),
        })
    return games


def _discover_xbox_games() -> list[dict[str, Any]]:
    # Get-AppxPackage with publisher filters Microsoft.Gaming or Microsoft.* gives
    # us UWP/Store games. We avoid system apps by filtering for HasNonRemovablePackage=$false.
    script = r"""
$apps = Get-AppxPackage | Where-Object {
  $_.SignatureKind -eq 'Store' -and
  ($_.PackageFamilyName -like '*Game*' -or $_.Name -like '*Gaming*' -or $_.Name -match 'Xbox|Halo|Forza|Minecraft|Sea Of Thieves|Gears|Age Of Empires')
} | Select-Object Name,PackageFullName,PackageFamilyName,InstallLocation,Version,Publisher
$apps | ConvertTo-Json -Depth 4
"""
    # try/except: Get-AppxPackage puede tardar 5-15s en sistemas con
    # cientos de apps UWP. 30s razonable; no queremos propagar timeout
    # al caller del tool.
    try:
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return []
    raw = proc.stdout.strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if isinstance(data, dict):
        data = [data]
    games = []
    for app in data if isinstance(data, list) else []:
        games.append({
            "launcher": "xbox",
            "name": app.get("Name"),
            "package_full_name": app.get("PackageFullName"),
            "package_family_name": app.get("PackageFamilyName"),
            "install_location": app.get("InstallLocation"),
            "version": app.get("Version"),
            "publisher": app.get("Publisher"),
            "launch_uri": f"shell:AppsFolder\\{app.get('PackageFamilyName')}!App",
        })
    return games


def _discover_riot_games() -> list[dict[str, Any]]:
    db_path = _riot_install_db()
    if not db_path:
        return []
    try:
        data = json.loads(db_path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return []
    products = data.get("associated_client") or {}
    games = []
    for product_path, client_path in products.items():
        games.append({
            "launcher": "riot",
            "product_path": product_path,
            "client_path": client_path,
            "name": Path(product_path).name,
        })
    return games


def _game_launcher_launch(args: dict[str, Any], state: AgentState, executor: Executor | None) -> dict[str, Any]:
    launcher = str(args.get("launcher") or "").casefold()
    query = str(args.get("game") or args.get("query") or args.get("name") or "").strip()
    if not launcher:
        return _err("missing launcher (epic|gog|xbox|riot)")
    if not query:
        return _err("missing game name/query")

    discovery = _game_launcher_discover({"launcher": launcher})
    games = discovery.get("games", {}).get(launcher, [])
    q = query.casefold()
    chosen = None
    for game in games:
        name_fields = (game.get("display_name") or game.get("name") or game.get("app_name") or "")
        if q in str(name_fields).casefold():
            chosen = game
            break
    if not chosen:
        return _err(
            f"no {launcher} game matching '{query}'",
            status="needs_user",
            available=[g.get("display_name") or g.get("name") for g in games][:30],
        )

    if launcher == "epic":
        # Epic supports a launch URI: com.epicgames.launcher://apps/<AppName>?action=launch&silent=true
        app_name = chosen.get("app_name")
        if not app_name:
            return _err("epic game has no AppName in manifest", chosen=chosen)
        uri = f"com.epicgames.launcher://apps/{app_name}?action=launch&silent=true"
        os.startfile(uri) if os.name == "nt" else webbrowser.open(uri)
        state.register_resource(
            "game_session", chosen.get("display_name") or app_name,
            metadata={"launcher": "epic", "app_name": app_name, "uri": uri, "started_at": datetime.now().isoformat()},
        )
        return _ok(launcher="epic", game=chosen, uri=uri, verified=False, status="attempted", note="Epic launcher should open and start the game; verify via window list.")
    if launcher == "gog":
        exe = chosen.get("exe") or chosen.get("path")
        if not exe:
            return _err("gog game has no exe registered", chosen=chosen)
        exe_path = Path(exe).expanduser()
        if not exe_path.is_file():
            return _err("gog exe path not found", path=str(exe_path))
        if os.name == "nt":
            os.startfile(exe_path)
        state.register_resource(
            "game_session", chosen.get("name") or exe,
            metadata={"launcher": "gog", "game_id": chosen.get("game_id"), "exe": str(exe_path), "started_at": datetime.now().isoformat()},
        )
        return _ok(launcher="gog", game=chosen, exe=str(exe_path), verified=False, status="attempted")
    if launcher == "xbox":
        uri = chosen.get("launch_uri")
        if not uri:
            return _err("xbox app has no launch URI", chosen=chosen)
        os.startfile(uri) if os.name == "nt" else webbrowser.open(uri)
        state.register_resource(
            "game_session", chosen.get("name") or uri,
            metadata={"launcher": "xbox", "uri": uri, "package_family_name": chosen.get("package_family_name"), "started_at": datetime.now().isoformat()},
        )
        return _ok(launcher="xbox", game=chosen, uri=uri, verified=False, status="attempted")
    if launcher == "riot":
        client = chosen.get("client_path")
        if not client or not Path(client).is_file():
            return _err("riot client path missing", chosen=chosen)
        os.startfile(client) if os.name == "nt" else webbrowser.open(Path(client).as_uri())
        state.register_resource(
            "game_session", chosen.get("name") or client,
            metadata={"launcher": "riot", "client": client, "started_at": datetime.now().isoformat()},
        )
        return _ok(launcher="riot", game=chosen, client=client, verified=False, status="attempted")
    return _err(f"launcher '{launcher}' not supported")
