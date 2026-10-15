"""Where this PC keeps the person's known folders (Documentos, Escritorio, Descargas…), redirected or not.

The computer-use reader writes a file dialog's absolute path (v3 punto 2): the common dialog takes it as it is, and the
shell's ``file:`` atom needs it rooted. Windows answers with SHGetKnownFolderPath (OneDrive or a moved folder
included); anywhere else, or if it fails, the folder under the profile by its English name.
"""

from __future__ import annotations

import os
import sys
import time
import unicodedata
import uuid
from pathlib import Path, PureWindowsPath

_FOLDER_IDS = {
    "documents": "FDD39AD0-238F-46AF-ADB4-6C85480369C7",
    "desktop": "B4BFCC3A-DB2C-424C-B029-7FE99A87C641",
    "downloads": "374DE290-123F-4565-9164-39C4925E467B",
    "pictures": "33E28130-4E1E-4676-835A-98395C3BC3BB",
    "music": "4BD8D571-6D19-48D3-BE97-422220080E43",
    "videos": "18989B1D-99B5-455B-841C-AB7C74E4DDFC",
}
_FALLBACK_NAMES = {
    "documents": "Documents", "desktop": "Desktop", "downloads": "Downloads", "pictures": "Pictures",
    "music": "Music", "videos": "Videos",
}


def _shell_path(folder_id: str) -> str | None:
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class _Guid(ctypes.Structure):
            _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD), ("Data3", wintypes.WORD),
                        ("Data4", ctypes.c_ubyte * 8)]

        raw = uuid.UUID(folder_id).bytes_le
        guid = _Guid.from_buffer_copy(raw)
        pointer = ctypes.c_wchar_p()
        shell32 = ctypes.windll.shell32  # type: ignore[attr-defined]
        result = shell32.SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(pointer))
        try:
            return pointer.value if result == 0 and pointer.value else None
        finally:
            ctypes.windll.ole32.CoTaskMemFree(pointer)  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001 - any failure falls back to the profile folder
        return None


def known_folder(folder: str) -> str | None:
    """The absolute path of a known folder («documents», «desktop», «downloads», «pictures», «music», «videos»), or
    None for any other name."""

    folder_id = _FOLDER_IDS.get(folder)
    if folder_id is None:
        return None
    found = _shell_path(folder_id)
    if found:
        return found
    home = os.environ.get("USERPROFILE") or str(Path.home())
    return str(Path(home) / _FALLBACK_NAMES[folder])


# v3 ronda 3 (lugar M6; v3-17 «abre la imagen prueba.png de la carpeta baxy-prueba-v3 en fotos», v3-18 «open
# paisaje.jpg in photos…»): a file the person names with no known folder, or in a folder of theirs that is no known one,
# is looked up by its exact name under the known folders, as the file.open provider does. Only one match is a path;
# two are not guessed.
_SEARCHED = ("desktop", "documents", "downloads", "pictures")
_SEARCH_DEPTH = 4
_SEARCH_ENTRIES = 20000
# Review of r15b2 (finding 5): located_folders runs inside a semantic reader, on every phrase said in a folder with a
# doing. Measured on the owner's PC (2026-10-09, 2 853 folders and 12 376 files in reach): 130 ms to find two
# baxy-prueba-v3, 240–480 ms to tell no folder has a name. The entry budget alone would let a larger profile walk for
# seconds, so the search also stops at this many seconds (then it «did not tell»: one folder found is gone to by its
# name, none found reads no folder mission).
_FOLDER_SEARCH_SECONDS = 0.4
_clock = time.monotonic


def locate_file(name: str, folder: str | None = None) -> str | None:
    """The one absolute path of a file named ``name`` (exactly, case aside) under the known folders, inside a folder
    named ``folder`` when given; None when there is none or more than one, or the name is no plain file name."""

    found = located_files(name, folder)
    return found[0] if found is not None and len(found) == 1 else None


def located_files(name: str, folder: str | None = None) -> list[str] | None:
    """The files named ``name`` under the known folders (at most two: two are already «more than one»); None when the
    search was cut short or the name is no plain file name (review of cu-v3-abrir-archivo, finding 6: two files of
    one name are said, never one of them taken)."""

    if not name or any(sign in name for sign in "\\/:*?\"<>|") or name in {".", ".."}:
        return None
    wanted, inside = name.casefold(), (folder or "").casefold()
    found: set[str] = set()
    seen: set[str] = set()
    budget = _SEARCH_ENTRIES
    for known in _SEARCHED:
        root = known_folder(known)
        if not root or root.casefold() in seen or not os.path.isdir(root):
            continue
        seen.add(root.casefold())
        base_depth = os.path.normpath(root).count(os.sep)
        for current, directories, files in os.walk(root):
            budget -= len(directories) + len(files)
            if budget <= 0:
                return None
            depth = os.path.normpath(current).count(os.sep) - base_depth
            directories[:] = [d for d in directories if not d.startswith(".")] if depth < _SEARCH_DEPTH else []
            if inside and os.path.basename(os.path.normpath(current)).casefold() != inside:
                continue
            found.update(os.path.join(current, file) for file in files if file.casefold() == wanted)
            if len(found) > 1:
                return sorted(found)
    return sorted(found)


def left_to_the_provider(name: str, folder: str) -> bool:
    """Whether a file.open of the plain file name ``name`` given the known ``folder`` is looked up by the provider
    itself: no file of that name lies directly in the folder (the provider opens one found there without looking
    further), so it searches the known folders by that exact name, opens none of two and says when its own search was
    cut short (``file_search_incomplete``). A walk of ``located_files`` cut short by its entry budget then proves
    nothing either way: the provider's search decides (redpc, 2026-10-09: a profile past 20 000 entries stopped every
    name said alone before any file.open was tried)."""

    if not name or any(sign in name for sign in "\\/:*?\"<>|") or name.strip() in {"", ".", ".."}:
        return False
    root = known_folder(folder)
    return bool(root) and os.path.isdir(root) and not os.path.lexists(os.path.join(root, name))


def located_folders(name: str, within: str | None = None) -> tuple[tuple[str, ...], bool]:
    """r15b t-menu-2 («en baxy-prueba-v3 ordená los archivos por tamaño»): the folders named ``name`` (exactly, case
    aside) under the known folders, or under the known folder ``within`` («documents») when given — the known folder
    itself when ``name`` is one's spoken name —, at most two (two are already «more than one»), and whether the
    search told: False when it was cut short before finding two (one found then may not be the only one): by the
    entry budget or after ``_FOLDER_SEARCH_SECONDS`` (a reader waits no longer than that on the disk)."""

    if not name or any(sign in name for sign in "\\/:*?\"<>|") or name in {".", ".."}:
        return (), True
    spoken = "".join(
        char for char in unicodedata.normalize("NFD", name.strip().casefold()) if unicodedata.category(char) != "Mn"
    )
    if within is None and spoken in _SPOKEN:
        root = known_folder(_SPOKEN[spoken])
        return ((root,) if root else ()), True
    wanted = name.casefold()
    found: dict[str, str] = {}
    budget = _SEARCH_ENTRIES
    deadline = _clock() + _FOLDER_SEARCH_SECONDS
    for known in (within,) if within else _SEARCHED:
        root = known_folder(known)
        if not root or not os.path.isdir(root):
            continue
        base_depth = os.path.normpath(root).count(os.sep)
        for current, directories, _ in os.walk(root):
            budget -= len(directories)
            found.update(
                (os.path.normcase(os.path.realpath(path)), path)
                for path in (os.path.join(current, d) for d in directories if d.casefold() == wanted)
            )
            if len(found) > 1 or budget <= 0 or _clock() > deadline:
                return tuple(found.values())[:2], len(found) > 1
            depth = os.path.normpath(current).count(os.sep) - base_depth
            directories[:] = [d for d in directories if not d.startswith(".")] if depth < _SEARCH_DEPTH else []
    return tuple(found.values()), True


# The words a person says for a known folder, folded (es/en), and the folder they name.
_SPOKEN = {
    "documentos": "documents", "documents": "documents", "mis documentos": "documents",
    "escritorio": "desktop", "desktop": "desktop",
    "descargas": "downloads", "downloads": "downloads",
    "imagenes": "pictures", "pictures": "pictures",
    "musica": "music", "music": "music",
    "videos": "videos",
}


def rooted(path: str) -> str:
    """cu-v3-scroll-pegar-direccion (v3-48 «Documentos\\baxy-prueba-v3»): a path said from a known folder, rooted at
    where this PC keeps it, so an address field takes it from anywhere; any other path unchanged."""

    text = path.strip()
    if not text or PureWindowsPath(text).is_absolute() or PureWindowsPath(text).drive:
        return text
    head, _, rest = text.replace("/", "\\").partition("\\")
    folded = "".join(
        char for char in unicodedata.normalize("NFD", head.strip().casefold()) if unicodedata.category(char) != "Mn"
    )
    root = known_folder(_SPOKEN[folded]) if folded in _SPOKEN else None
    return str(PureWindowsPath(root) / rest) if root and rest else (root or text)


def known_place(path: str) -> tuple[str, str] | None:
    """cu-v3-abrir-archivo: the known folder file.open takes («documents», …) holding an absolute path and the path
    relative to it («baxy-prueba-v3\\paisaje.jpg»); None for a path under none of them."""

    target = os.path.normcase(os.path.normpath(path))
    for known in _SEARCHED:
        root = known_folder(known)
        if not root:
            continue
        base = os.path.normpath(root)
        if target.startswith(os.path.normcase(base) + os.sep):
            return known, os.path.normpath(path)[len(base) + 1:]
    return None
