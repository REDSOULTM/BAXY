"""Domain inventory: known apps, songs, contacts, etc.

Used by:
  - corrector.py — fuzzy-match candidate replacements
  - stt.py initial_prompt — biases Whisper toward known entities

The inventory has FOUR sources, merged at load time:
  1. STATIC_INVENTORY (this file)  — core verbs + common app names
  2. ~/.gemma4/voice_inventory.json — operator-editable additions
  3. installed-apps discovery (best-effort, OS-specific stubs here)
  4. recently-played media (future Sprint, stubbed for now)

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
    # Common desktop apps. The dynamic discoverer (future) augments this
    # with the operator's actually-installed apps.
    "apps": [
        "Chrome", "Firefox", "Edge", "Brave", "Safari",
        "Spotify", "Discord", "Telegram", "WhatsApp", "Signal",
        "Slack", "Zoom", "Teams", "Skype",
        "Steam", "Epic Games", "Battle.net", "GOG",
        "Visual Studio Code", "VS Code", "Visual Studio", "PyCharm", "IntelliJ",
        "Notion", "Obsidian", "Notepad", "Sublime Text",
        "OBS", "OBS Studio", "DaVinci Resolve",
        "YouTube", "Netflix", "Twitch", "Disney Plus",
        "Counter-Strike 2", "GTA V", "Among Us", "Minecraft",
        "Explorer", "Finder", "Files",
    ],
    # Common artists / songs the operator references. Operator-extended
    # via voice_inventory.json.
    "music_artists": [
        "Benson Boone", "Bad Bunny", "Bizarrap", "Taylor Swift",
        "Queen", "The Beatles", "Pink Floyd", "Coldplay",
        "Los Redonditos de Ricota", "Soda Stereo", "Charly García",
        "Arctic Monkeys", "Radiohead",
    ],
    "music_songs": [
        "Bohemian Rhapsody", "Stairway to Heaven", "Hotel California",
        "La Bamba", "Despacito", "Macarena",
    ],
    # Brand of the assistant. Used by the wake-word transcript suppressor
    # (the LLM downstream shouldn't see 'hey gemma' as part of the command).
    "wake_words": ["hey gemma", "hey jarvis", "gemma", "jarvis"],
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


def get_inventory() -> dict[str, list[str]]:
    """Merged inventory: STATIC + user overrides.

    User overrides EXTEND (don't replace) the static lists.
    """
    merged: dict[str, list[str]] = {k: list(v) for k, v in STATIC_INVENTORY.items()}
    user = _load_user_overrides()
    for k, v in user.items():
        merged.setdefault(k, []).extend(v)
    # Deduplicate preserving order
    for k, v in merged.items():
        seen = set()
        out = []
        for s in v:
            if s.lower() not in seen:
                seen.add(s.lower())
                out.append(s)
        merged[k] = out
    return merged


def build_initial_prompt(inv: dict[str, list[str]] | None = None) -> str:
    """Build the Whisper initial_prompt from the inventory.

    Cap at ~220 tokens worth of text (~880 chars conservative) to stay
    under Whisper's 224-token initial_prompt limit.
    """
    if inv is None:
        inv = get_inventory()
    apps = inv.get("apps", [])[:25]
    artists = inv.get("music_artists", [])[:10]
    songs = inv.get("music_songs", [])[:6]
    # Bilingual command pairs to bias against anglicism phoneticization.
    head = (
        "Conversación con el asistente Gemma en español rioplatense con "
        "nombres de aplicaciones y canciones en inglés. "
        "Hey Gemma, abre Chrome. Hey Gemma, open Chrome. "
        "Hey Gemma, abre Spotify. Hey Gemma, open Spotify. "
    )
    apps_str = "Apps: " + ", ".join(apps) + ". " if apps else ""
    artists_str = "Artistas: " + ", ".join(artists) + ". " if artists else ""
    songs_str = "Canciones: " + ", ".join(songs) + ". " if songs else ""
    tail = (
        "Comandos breves en español con nombres de apps en inglés, "
        "dirigidos al asistente Gemma."
    )
    prompt = head + apps_str + artists_str + songs_str + tail
    # Conservative cap at 880 chars.
    if len(prompt) > 880:
        prompt = prompt[:877] + "..."
    return prompt
