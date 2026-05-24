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


# Builtin OS executables whose colloquial name is LOCALIZED by the user's
# language but whose actual binary name is fixed and English. Windows discovery
# (PATH/StartApps/registry) only knows the binary ("notepad", "calc"), so a
# French "bloc-notes" or German "Editor" fuzzy-scores 0 against "notepad" and
# the app is never found. This is NOT intent routing (the semantic router has
# already chosen the `app` tool) and NOT a canned reply — it is a name-translation
# table for a SMALL, FIXED set of OS-shipped binaries, the same precedent as the
# streaming-app alias table in domain_tools.py. Keys are folded (lowercase, no
# accents/punctuation — must match tools._fold output). We translate the
# localized name to the canonical binary query, then let normal discovery rank it.
# Sources: Windows shell names per MS docs (notepad.exe, calc, mspaint, cmd);
# localized labels from the OS UI in es/en/pt/fr/de/it.
_BUILTIN_ALIASES: dict[str, str] = {
    # notepad.exe
    "bloc de notas": "notepad", "bloco de notas": "notepad",
    "bloc notes": "notepad", "bloc note": "notepad",   # fr "bloc-notes" -> fold
    "editor": "notepad",                                 # de "Editor"
    "blocco note": "notepad", "blocco di note": "notepad",
    # calc (CalculatorApp / calc.exe)
    "calculadora": "calc", "calculatrice": "calc", "rechner": "calc",
    "calcolatrice": "calc",
    # mspaint.exe
    "paint": "mspaint", "pintura": "mspaint", "dessin": "mspaint",
    # cmd
    "simbolo del sistema": "cmd", "terminal": "cmd",
}


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
        from .tools import _score, _fold
        # Translate a localized OS-builtin name ("bloc-notes", "Editor",
        # "calculatrice") to its canonical binary BEFORE discovery — discovery
        # only knows the English binary name, so the foreign label fuzzy-scores 0.
        # See _BUILTIN_ALIASES. Strip a leading article the LLM may keep ("el/le/
        # den/o/il/la/lo/the") so "ouvre LE bloc-notes" still matches.
        folded = _fold(query)
        for _art in ("el ", "la ", "lo ", "le ", "den ", "der ", "das ", "o ", "a ", "il ", "the "):
            if folded.startswith(_art):
                folded = folded[len(_art):]
                break
        canonical = _BUILTIN_ALIASES.get(folded)
        if canonical is not None:
            query = canonical
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
        q_folded = _fold(query)
        q_len = len(q_folded)
        ranked: list[tuple[int, int, int, AppCandidate]] = []
        seen: set[tuple[str, str]] = set()
        for app in candidates:
            name_score = _score(query, app.name)
            launch_score = _score(query, Path(app.launch).stem)
            score = max(name_score, launch_score)
            if score <= 0:
                continue
            key = (_fold(app.name), app.launch.casefold())
            if key in seen:
                continue
            seen.add(key)
            # 2026-05-20 tiebreaks (both observed live):
            #  1. NAME match beats LAUNCH-stem match. PWA shortcuts ("YouTube",
            #     "southpark") launch via Chrome.exe, so they score 100 on the
            #     launch stem for query "Chrome" — but the user asking for
            #     "Chrome" wants the app NAMED Chrome, not a web-app that opens
            #     through it. name_matched=0 sorts before name_matched=1.
            #  2. NAME closest in LENGTH to the query. "Edge" tied at 75 vs
            #     "Microsoft Edge" (browser) and "MicrosoftEdgeBCHost" (helper);
            #     length-distance favors the real app over the longer helper.
            # name_in: 0 if the query actually appears in the NAME (any score
            # > 0), else 1. This is the real Chrome fix: "Google Chrome" has
            # name_score 75 (query in name) while the "YouTube" PWA has
            # name_score 0 (only its Chrome.exe launch stem matched). Prefer
            # the candidate the user actually named.
            name_in = 0 if name_score > 0 else 1
            length_gap = abs(len(_fold(app.name)) - q_len)
            # 2026-05-24: DEMOTE shortcuts muertos. Un .lnk cuyo target ya no
            # existe (p.ej. vlc.lnk -> D:\...\vlc.exe borrado) rankea primero por
            # nombre pero al lanzarlo el SO devuelve error ("operación cancelada"
            # / no abre). Si hay otro candidato vivo (VLC en Program Files), debe
            # ganar. dead=1 ordena DESPUÉS de dead=0 a igual score. No lo
            # dropeamos (si TODOS están muertos igual devolvemos algo).
            dead = 1 if self._is_dead_launch(app) else 0
            ranked.append((score, dead, name_in, length_gap, app))
        # Si hay AL MENOS un candidato VIVO, descartar los muertos (un .lnk con
        # target inexistente lanza error, no la app). Si TODOS están muertos,
        # los conservamos (mejor intentar que no devolver nada). Un shortcut
        # muerto con score altísimo NO debe ganarle a la app real con score
        # menor — por eso filtramos ANTES de ordenar por score.
        live = [it for it in ranked if it[1] == 0]
        pool = live if live else ranked
        # -score desc, name-match first, menor length gap, luego source/name.
        pool.sort(key=lambda item: (-item[0], item[2], item[3],
                                    item[4].source, item[4].name.casefold()))
        return [app for _s, _d, _nm, _gap, app in pool[:limit]]

    def _is_dead_launch(self, app: "AppCandidate") -> bool:
        """True si el launch del candidato apunta a un target inexistente. Para
        .lnk resuelve el TargetPath; para exe directo chequea el archivo. Solo
        para shortcuts/file (Steam/Epic usan URIs, no se tocan). Cacheado por
        path para no resolver el mismo .lnk muchas veces."""
        launch = app.launch or ""
        if app.source in ("steam", "epic") or launch[:5].lower() in ("steam", "com.e"):
            return False
        cache = getattr(self, "_dead_cache", None)
        if cache is None:
            cache = {}
            self._dead_cache = cache
        if launch in cache:
            return cache[launch]
        dead = False
        try:
            low = launch.lower()
            if low.endswith(".lnk"):
                target = self._resolve_lnk_target(launch)
                # si no pudimos resolver el target, NO lo marcamos muerto (duda
                # a favor de intentarlo); solo si resolvió y no existe.
                if target and not os.path.exists(target):
                    dead = True
            elif low.endswith((".exe", ".bat", ".cmd", ".com")):
                if not os.path.exists(launch):
                    dead = True
        except Exception:
            dead = False
        cache[launch] = dead
        return dead

    @staticmethod
    def _resolve_lnk_target(lnk_path: str) -> str | None:
        """TargetPath de un .lnk vía COM (WScript.Shell). None si falla."""
        try:
            import win32com.client  # type: ignore
            sh = win32com.client.Dispatch("WScript.Shell")
            sc = sh.CreateShortcut(lnk_path)
            return sc.TargetPath or None
        except Exception:
            return None

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
