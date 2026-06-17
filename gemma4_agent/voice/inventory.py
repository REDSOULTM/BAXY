"""Domain inventory: known apps, songs, contacts, etc.

Used by:
  - corrector.py — fuzzy-match candidate replacements
  - stt.py initial_prompt — biases Whisper toward known entities

The inventory has FOUR sources, merged at load time:
  1. STATIC_INVENTORY (this file)  — core verbs + common app names
  2. ~/.gemma4/voice_inventory.json — operator-editable additions
  3. installed-apps discovery (best-effort, OS-specific stubs here)
  4. recently-played media (stubbed for now)

Design principle: be SMALL by default (<200 entries) so RapidFuzz
remains <10 ms. Large inventories degrade match quality (more
ambiguity, more false corrections).

Output is a dict[category, list[str]] consumed by corrector.py.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


STATIC_INVENTORY: dict[str, list[str]] = {
    # Verbs in Spanish and English. Used as 'verb anchors' so the
    # corrector knows 'abre' is more likely than 'Aure' at sentence start.
    "verbs": [
        "abre", "abrir", "cierra", "cerrar", "minimiza", "maximiza",
        "pausa", "reproduce", "reproducir", "para",
        "busca", "buscar", "buscame", "búscame",
        "manda", "mándale", "mandale", "envia", "envíame",
        "sube", "baja", "apaga", "enciende", "prende",
        "open", "close", "play", "pause", "stop", "search",
        "minimize", "maximize", "send", "turn", "set",
    ],
    # Common desktop apps. The dynamic discoverer augments this
    # with the operator's actually-installed apps.
    "apps": [
        "Chrome", "Firefox", "Edge", "Brave", "Safari", "Opera",
        "Spotify", "Discord", "Telegram", "WhatsApp", "Signal",
        "Slack", "Zoom", "Teams", "Skype", "Reddit",
        "Steam", "Epic Games", "Battle.net", "GOG", "EA App", "Ubisoft Connect",
        "Visual Studio Code", "VS Code", "Visual Studio", "PyCharm", "IntelliJ",
        "Notion", "Obsidian", "Notepad", "Sublime Text",
        "OBS", "OBS Studio", "DaVinci Resolve", "Audacity", "Ableton",
        "YouTube", "Netflix", "Twitch",
        "Disney Plus", "Disney+", "HBO Max", "Max", "Prime Video", "Apple Music",
        "Explorer", "Finder", "Files",
        # Apps de productividad/creación GLOBALMENTE comunes (universales, no
        # del operador). Sin ellas el STT las fusiona cuando no hay target:
        # gimp->equipe, vlc->blc, reddit->red. El gate de longitud evita que
        # esta ampliación corrompa habla declarativa.
        "GIMP", "VLC", "Blender", "Krita", "Photoshop", "Illustrator",
        "Premiere", "After Effects", "Lightroom",
        "Word", "Excel", "PowerPoint", "Outlook", "OneNote", "Access",
        "Thunderbird", "Audible", "Kindle", "Calibre", "qBittorrent",
        "Figma", "Canva", "Unity", "Unreal Engine",
        # Juegos populares globales (títulos que un usuario cualquiera diría).
        "Counter-Strike 2", "Counter-Strike", "GTA V", "Grand Theft Auto",
        "Among Us", "Minecraft", "Fortnite", "Valorant", "League of Legends",
        "Dota 2", "Apex Legends", "Overwatch", "Roblox",
        "Elden Ring", "Cyberpunk 2077", "Cyberpunk", "Hollow Knight",
        "Stardew Valley", "Baldur's Gate", "Red Dead Redemption",
        "Marvel Rivals", "ARC Raiders", "Age of Empires",
    ],
    # Common artists / songs the operator references. Operator-extended
    # via voice_inventory.json.
    "music_artists": [
        "Benson Boone", "Bad Bunny", "Bizarrap", "Taylor Swift",
        "Queen", "The Beatles", "Pink Floyd", "Coldplay",
        "Los Redonditos de Ricota", "Soda Stereo", "Charly García",
        "Arctic Monkeys", "Radiohead",
        # Artistas GLOBALMENTE top (Spotify/charts mundiales) — universales, no
        # del operador. Nombres de pila ingleses cortos que el STT fusiona
        # (billy->billie, dualipa->dua lipa). El gate de longitud los protege.
        "Billie Eilish", "Dua Lipa", "The Weeknd", "Karol G", "Sabrina Carpenter",
        "Hozier", "Michael Jackson", "Ariana Grande", "Drake", "Ed Sheeran",
        "Eminem", "Rihanna", "Beyoncé", "Adele", "Bruno Mars", "Travis Scott",
        "Shakira", "Daddy Yankee", "Rauw Alejandro", "Feid",
        "Peso Pluma", "Olivia Rodrigo", "Lady Gaga", "Kanye West", "SZA",
    ],
    "music_songs": [
        "Bohemian Rhapsody", "Stairway to Heaven", "Hotel California",
        "La Bamba", "Despacito", "Macarena",
    ],
    # Brand of the assistant. Used by the wake-word transcript suppressor
    # (the LLM downstream shouldn't see the wake phrase as part of the command).
    # Wake word ACTIVA = "Baxy" (modelo baxy.onnx, recall held-out 0.872). SOLO las
    # variantes de Baxy: gemma/jarvis se quitaron para evitar falsos positivos (no son
    # la wake word activa). "carter" también fuera (su modelo falló el gate).
    #
    # STT MIS-HEARINGS de "Baxy" (2026-06-07): "Baxy" es una palabra INVENTADA fuera
    # del vocabulario del STT, que la mapea a la palabra REAL más cercana. Bug medido:
    # al decir "Baxy", Whisper transcribe a veces "Maxi." -> el strip fonético NO lo
    # atrapa (score 67 < umbral 72, e igualar a 67 colisionaría con el comando "busca"
    # =67) -> el 4B tomó "Maxi" como el OBJETO del comando ("clic en el elemento
    # 'Maxi'"). Estas variantes (maxi/paxi/vaxi/naxi/faxi/max/bixby) son las
    # transcripciones fonéticamente cercanas a "baxy" VERIFICADAS que NO son verbos/
    # comandos en es/en -> seguras en el stage EXACTO (no por score). NO es una lista
    # arbitraria: es el conjunto medido de homófonos del wake que el STT confunde.
    "wake_words": [
        "baxy", "baxi", "backsy", "hey baxy",
        "maxi", "paxi", "vaxi", "naxi", "faxi", "max", "bixby",
    ],
}


def _load_user_overrides() -> dict[str, list[str]]:
    """Operator-editable JSON at ~/.gemma4/voice_inventory.json.

    Schema (flexible):
        {
          "apps":     [...],
          "music_artists": [...],
          "music_songs":   [...],
          "contacts": [...],
          ...
        }
    Missing keys are ignored. Unknown keys are accepted (forward-compat).
    """
    path = Path.home() / ".gemma4" / "voice_inventory.json"
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            return {}
        out: dict[str, list[str]] = {}
        for k, v in data.items():
            if isinstance(v, list):
                out[k] = [str(x) for x in v if isinstance(x, (str,))]
        return out
    except Exception as exc:
        logger.warning("voice_inventory.json malformed, ignored: %s", exc)
        return {}


_DISCOVERY_CACHE: list[str] | None = None
_DISCOVERY_CACHE_MAX = 80  # cap for prompt size sanity


def _discover_installed_apps() -> list[str]:
    """Run app discovery once per process and cache the result.

    Best-effort: failures return []. The voice pipeline still works
    on STATIC_INVENTORY alone.
    """
    global _DISCOVERY_CACHE
    if _DISCOVERY_CACHE is not None:
        return _DISCOVERY_CACHE
    try:
        from .app_discovery import discover_apps
        apps = discover_apps()
    except Exception as exc:
        logger.warning("app discovery failed: %s", exc)
        apps = []
    if len(apps) > _DISCOVERY_CACHE_MAX:
        logger.info(
            "app discovery returned %d apps; truncating to %d for prompt budget",
            len(apps), _DISCOVERY_CACHE_MAX,
        )
        apps = apps[:_DISCOVERY_CACHE_MAX]
    _DISCOVERY_CACHE = apps
    return apps


def get_inventory(include_discovery: bool = True) -> dict[str, list[str]]:
    """Merged inventory: STATIC + user overrides + (optional) discovery.

    User overrides EXTEND (don't replace) the static lists. Discovery
    is opt-in via the include_discovery flag (default True) so tests
    can request a deterministic inventory without OS calls.
    """
    merged: dict[str, list[str]] = {k: list(v) for k, v in STATIC_INVENTORY.items()}
    user = _load_user_overrides()
    for k, v in user.items():
        merged.setdefault(k, []).extend(v)
    if include_discovery:
        # Never let discovery crash the voice pipeline. Any exception
        # here = ship STATIC_INVENTORY + user overrides only.
        try:
            merged.setdefault("apps", []).extend(_discover_installed_apps())
        except Exception as exc:
            logger.warning("inventory discovery failed; using static: %s", exc)
    # Deduplicate preserving order, case-insensitive.
    for k, v in merged.items():
        seen = set()
        out = []
        for s in v:
            if s.lower() not in seen:
                seen.add(s.lower())
                out.append(s)
        merged[k] = out
    return merged


# NOTA (Parakeet-only 2026-06-17): build_hotwords() y build_initial_prompt() se
# eliminaron junto con Whisper. Eran artefactos del decoder de Whisper
# (initial_prompt = continuación de estilo + hotwords del budget de 224 tokens).
# Parakeet es multilingüe, auto-detecta el idioma y no recibe prompt; los nombres
# propios se rescatan con el corrector fonético downstream (corrector.py).
