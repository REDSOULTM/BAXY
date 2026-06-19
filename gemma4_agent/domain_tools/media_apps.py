"""Localización de ejecutables de apps de media (VLC, Spotify), extraído de
domain_tools/__init__.py (split del archivo-dios, 2026-06-19). Puro: solo
shutil + pathlib, sin dependencias del paquete.
"""
from __future__ import annotations

import shutil
from pathlib import Path


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
