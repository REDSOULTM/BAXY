"""App / game discovery on Windows.

Pulled out of :mod:`gemma4_agent.tools` in Sprint 5b. Behaviour is
identical; the two classes are re-exported from ``tools`` so existing
``from .tools import AppResolver, AppCandidate`` callers keep working.

Implementation note: the small ranking / parsing helpers
(`_fold`, `_score`, `_acf_value`, `_nearest_steam_appid`,
`_pretty_exe_name`, `_looks_like_uninstaller`) still live in
``tools`` because they are also consumed by code outside this
module. We import them lazily *inside* methods to avoid a top-level
cycle with ``tools``.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class AppCandidate:
    name: str
    source: str
    launch: str
    launch_type: str
    process_name: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "source": self.source,
            "launch": self.launch,
            "launch_type": self.launch_type,
            "process_name": self.process_name,
        }


class AppResolver:
    """Discovers apps/games from Windows instead of relying on manual aliases."""

    def __init__(self) -> None:
        self._cache: list[AppCandidate] = []
        self._loaded_sources: set[str] = set()

    def find(self, query: str, limit: int = 8, refresh: bool = False, deep_fallback: bool = True) -> list[AppCandidate]:
        # Lazy import: avoids a top-level cycle with tools.py.
        from .tools import _score
        if refresh:
            self._cache = []
            self._loaded_sources = set()

        for source_name, loader in (
            ("path", self._from_path),
            ("shortcuts", self._from_shortcuts),
            ("start_apps", self._from_start_apps),
            ("registry", self._from_uninstall_registry),
            ("steam", self._from_steam),
            ("epic", self._from_epic),
        ):
            self._load_source(source_name, loader)
            matches = self._rank(query, self._cache, limit)
            if matches and max(_score(query, matches[0].name), _score(query, Path(matches[0].launch).stem)) >= 90:
                return matches

        matches = self._rank(query, self._cache, limit)
        if matches or not deep_fallback:
            return matches

        deep_matches = self._from_common_exe_roots(query=query, max_matches=max(limit * 3, 24))
        self._cache.extend(deep_matches)
        return self._rank(query, self._cache, limit)

    def find_steam_library(self, query: str, limit: int = 8) -> list[AppCandidate]:
        candidates = [*self._from_steam(), *self._from_steam_appinfo_cache(query, max(limit * 3, 12))]
        return self._rank(query, candidates, limit)

    def _load_source(self, source_name: str, loader: Callable[[], list[AppCandidate]]) -> None:
        if source_name in self._loaded_sources:
            return
        self._cache.extend(loader())
        self._loaded_sources.add(source_name)

    def _rank(self, query: str, candidates: list[AppCandidate], limit: int) -> list[AppCandidate]:
        from .tools import _fold, _score
        ranked: list[tuple[int, AppCandidate]] = []
        seen: set[tuple[str, str]] = set()
        for app in candidates:
            score = max(_score(query, app.name), _score(query, Path(app.launch).stem))
            if score <= 0:
                continue
            key = (_fold(app.name), app.launch.casefold())
            if key in seen:
                continue
            seen.add(key)
            ranked.append((score, app))
        ranked.sort(key=lambda item: (-item[0], item[1].source, item[1].name.casefold()))
        return [app for _score_value, app in ranked[:limit]]

    def _from_path(self) -> list[AppCandidate]:
        out = []
        pathext = os.environ.get("PATHEXT", ".COM;.EXE;.BAT;.CMD").split(";")
        for folder in os.environ.get("PATH", "").split(os.pathsep):
            root = Path(folder.strip('"'))
            if not root.is_dir():
                continue
            try:
                for child in root.iterdir():
                    if child.is_file() and child.suffix.upper() in pathext:
                        out.append(AppCandidate(child.stem, "PATH", str(child), "file", child.name))
            except OSError:
                continue
        return out

    def _from_shortcuts(self) -> list[AppCandidate]:
        recursive_roots = [
            Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
            Path(os.environ.get("PROGRAMDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
        ]
        flat_roots = [
            Path.home() / "Desktop",
            Path(os.environ.get("PUBLIC", "C:/Users/Public")) / "Desktop",
        ]
        out = []
        for root in recursive_roots:
            if not root.is_dir():
                continue
            try:
                for shortcut in root.rglob("*.lnk"):
                    out.append(AppCandidate(shortcut.stem, "shortcut", str(shortcut), "file"))
            except OSError:
                continue
        for root in flat_roots:
            if not root.is_dir():
                continue
            try:
                for shortcut in root.glob("*.lnk"):
                    out.append(AppCandidate(shortcut.stem, "shortcut", str(shortcut), "file"))
            except OSError:
                continue
        return out

    def _from_start_apps(self) -> list[AppCandidate]:
        script = "Get-StartApps | Select-Object Name,AppID | ConvertTo-Json -Depth 2"
        # timeout reducido de 20s -> 8s: Get-StartApps normalmente termina en
        # <2s; 8s da headroom 4x. Si el sistema esta tan saturado que tarda
        # mas, mejor abortar y seguir con los otros loaders que dar 20s a una
        # sola fuente.
        try:
            proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=8)
        except Exception:
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
        out = []
        for item in data:
            name = item.get("Name")
            appid = item.get("AppID")
            if name and appid:
                out.append(AppCandidate(name, "start_app", f"shell:appsFolder\\{appid}", "shell"))
        return out

    def _from_uninstall_registry(self) -> list[AppCandidate]:
        script = r"""
$paths = @(
  'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*',
  'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*',
  'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*'
)
$items = foreach ($p in $paths) {
  Get-ItemProperty $p -ErrorAction SilentlyContinue |
    Where-Object { $_.DisplayName } |
    Select-Object DisplayName,DisplayIcon,InstallLocation
}
$items | ConvertTo-Json -Depth 3
"""
        # timeout reducido de 25s -> 12s: HKLM Uninstall puede tener 500+ keys
        # pero Get-ItemProperty con -ErrorAction SilentlyContinue es paralelo
        # internamente. En la practica este loader corre en 2-6s; 12s da
        # headroom 2x. Si tarda mas, mejor seguir con steam/epic loaders.
        try:
            proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=12)
        except Exception:
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
        out = []
        for item in data:
            name = item.get("DisplayName")
            launch = self._launch_from_registry_item(item)
            if name and launch:
                process = Path(launch).name if Path(launch).suffix.lower() == ".exe" else None
                out.append(AppCandidate(name, "registry", launch, "file", process))
        return out

    def _launch_from_registry_item(self, item: dict[str, Any]) -> str | None:
        from .tools import _looks_like_uninstaller
        icon = str(item.get("DisplayIcon") or "").strip().strip('"')
        icon = re.sub(r",\s*-?\d+$", "", icon).strip('"')
        if (
            icon
            and Path(icon).is_file()
            and Path(icon).suffix.lower() == ".exe"
            and not _looks_like_uninstaller(Path(icon))
        ):
            return icon
        install = str(item.get("InstallLocation") or "").strip().strip('"')
        root = Path(install)
        if root.is_dir():
            exes = sorted(
                (p for p in root.glob("*.exe") if p.is_file() and not _looks_like_uninstaller(p)),
                key=lambda p: len(p.name),
            )
            if exes:
                return str(exes[0])
        return None

    def _from_common_exe_roots(self, query: str, max_matches: int = 80) -> list[AppCandidate]:
        from .tools import _fold, _looks_like_uninstaller, _pretty_exe_name, _score
        words = _fold(query).split()
        if not words:
            return []

        # Heuristica: si la query es muy corta (<=3 chars) o "generica"
        # (1 sola palabra de <5 chars), skipear esta fase. where.exe /R
        # sobre Program Files completo puede tardar 3-5s por root y si la
        # query es ruido (ej. "abc") vamos a desperdiciar 20s sin encontrar
        # nada util. Si la query es real (ej. "discord"), el match aparecio
        # en loaders anteriores.
        joined = " ".join(words)
        if len(joined) <= 3:
            return []

        pattern = "*" + "*".join(words) + "*.exe"
        roots = [
            Path(os.environ.get("ProgramFiles", "C:/Program Files")),
            Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")),
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs",
            Path(os.environ.get("APPDATA", "")),
            Path("C:/Games"),
            Path("D:/Games"),
            Path("D:/SteamLibrary"),
            Path("E:/Games"),
            Path("E:/SteamLibrary"),
        ]

        # Budget total para evitar que esta fase domine el wall-clock.
        # 9 roots x 5s = 45s en el peor caso anterior; con 8s total cubrimos
        # ~3-4 roots completos antes de aceptar la derrota. Esto convierte
        # "app not found" de 45s -> 8s en el peor caso.
        try:
            budget_s = float(os.environ.get("GEMMA4_APP_SCAN_BUDGET_S") or "8.0")
        except ValueError:
            budget_s = 8.0
        budget_s = max(1.0, min(budget_s, 30.0))
        deadline = time.monotonic() + budget_s
        per_root_s = max(1.0, budget_s / 3.0)

        out = []
        seen: set[Path] = set()
        for root in roots:
            if not root.is_dir() or root in seen:
                continue
            seen.add(root)
            remaining = deadline - time.monotonic()
            if remaining <= 0.2:
                break  # budget agotado
            try:
                proc = subprocess.run(
                    ["where.exe", "/R", str(root), pattern],
                    capture_output=True,
                    text=True,
                    timeout=min(per_root_s, remaining),
                )
                for line in proc.stdout.splitlines():
                    exe = Path(line.strip())
                    if not exe.is_file() or _looks_like_uninstaller(exe):
                        continue
                    pretty = _pretty_exe_name(exe)
                    score = max(_score(query, pretty), _score(query, exe.stem), _score(query, str(exe.parent)))
                    if score <= 0:
                        continue
                    out.append(AppCandidate(pretty, "exe_scan", str(exe), "file", exe.name))
                    if len(out) >= max_matches:
                        return out
            except (OSError, subprocess.TimeoutExpired):
                continue
        return out

    def _from_steam(self) -> list[AppCandidate]:
        from .tools import _acf_value
        steam_roots = self._steam_library_roots()
        out = []
        for root in steam_roots:
            apps = root / "steamapps"
            if not apps.is_dir():
                continue
            for manifest in apps.glob("appmanifest_*.acf"):
                text = manifest.read_text(encoding="utf-8", errors="ignore")
                appid = _acf_value(text, "appid")
                name = _acf_value(text, "name")
                if appid and name:
                    out.append(AppCandidate(name, "steam", f"steam://rungameid/{appid}", "uri"))
        return out

    def _from_steam_appinfo_cache(self, query: str, max_matches: int = 20) -> list[AppCandidate]:
        from .tools import _fold, _nearest_steam_appid, _score
        needle = query.strip().encode("utf-8", errors="ignore").lower()
        if len(needle) < 2:
            return []
        out: list[AppCandidate] = []
        seen: set[str] = set()
        for root in self._steam_library_roots():
            appinfo = root / "appcache" / "appinfo.vdf"
            cache = root / "appcache" / "librarycache"
            if not appinfo.is_file() or not cache.is_dir():
                continue
            try:
                data = appinfo.read_bytes()
                lower = data.lower()
                appid_markers = [
                    (int(child.name), int(child.name).to_bytes(4, "little"))
                    for child in cache.iterdir()
                    if child.is_dir() and child.name.isdigit()
                ]
            except OSError:
                continue

            start = 0
            while len(out) < max_matches:
                pos = lower.find(needle, start)
                if pos < 0:
                    break
                start = pos + 1
                end = data.find(b"\x00", pos)
                if end < 0 or end - pos > 180:
                    continue
                name = data[pos:end].decode("utf-8", errors="replace").strip()
                if not name or _score(query, name) <= 0:
                    continue
                appid = _nearest_steam_appid(data, appid_markers, pos)
                if not appid:
                    continue
                key = _fold(name)
                if key in seen:
                    continue
                seen.add(key)
                out.append(AppCandidate(name, "steam_appinfo", f"steam://nav/games/details/{appid}", "uri"))
        return out

    def _steam_library_roots(self) -> list[Path]:
        roots: list[Path] = []
        for base in [Path("C:/Program Files (x86)/Steam"), Path("C:/Program Files/Steam")]:
            if base.is_dir():
                roots.append(base)
        vdf = next((root / "steamapps" / "libraryfolders.vdf" for root in roots if (root / "steamapps" / "libraryfolders.vdf").is_file()), None)
        if vdf:
            text = vdf.read_text(encoding="utf-8", errors="ignore")
            for path in re.findall(r'"path"\s+"([^"]+)"', text):
                p = Path(path.replace("\\\\", "\\"))
                if p.is_dir() and p not in roots:
                    roots.append(p)
        return roots

    def _from_epic(self) -> list[AppCandidate]:
        manifest_root = Path("C:/ProgramData/Epic/EpicGamesLauncher/Data/Manifests")
        if not manifest_root.is_dir():
            return []
        out = []
        for manifest in manifest_root.glob("*.item"):
            try:
                data = json.loads(manifest.read_text(encoding="utf-8"))
            except Exception:
                continue
            name = data.get("DisplayName") or data.get("AppName")
            install = Path(str(data.get("InstallLocation") or ""))
            exe = None
            if install.is_dir():
                exes = sorted(install.rglob("*.exe"), key=lambda p: len(str(p)))
                exe = str(exes[0]) if exes else None
            if name and exe:
                out.append(AppCandidate(name, "epic", exe, "file", Path(exe).name))
        return out

    def open(self, candidate: AppCandidate) -> dict[str, Any]:
        # T2-app-startfile-no-error-042: capturamos OSError y devolvemos
        # un dict estructurado con detalle del candidate.
        try:
            os.startfile(candidate.launch)  # type: ignore[attr-defined]
        except OSError as exc:
            return {
                "ok": False,
                "error": f"os.startfile failed: {exc}",
                "candidate": {"name": candidate.name, "launch": str(candidate.launch), "launch_type": candidate.launch_type},
            }
        return {"ok": True, "candidate": {"name": candidate.name, "launch": str(candidate.launch), "launch_type": candidate.launch_type}}


__all__ = ["AppCandidate", "AppResolver"]
