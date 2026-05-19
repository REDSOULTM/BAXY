"""App discovery dinamico para el biasing del INITIAL_PROMPT de Whisper.

Problema (informe sec. 2.2): un INITIAL_PROMPT estatico con "Steam, Spotify,
Discord, Chrome..." sesga al decoder a esas palabras, pero "Saints Row",
"Cyberpunk", "DBeaver" o "Hollow Knight" salen como hallucinations.

Solucion: descubrir las apps reales instaladas en el sistema del usuario
y construir el INITIAL_PROMPT a partir de esa lista. Resultado: "Abre Saints
Row" se transcribe bien porque "Saints Row" aparece en el prompt real.

Diseno:
- Fuentes (Windows): Start Menu shortcuts, registry Uninstall, Steam library,
  Epic Games manifests, Start apps (UWP). Todas via gemma4_agent.tools.AppResolver
  para no duplicar la logica que ya tiene el repo.
- Cache JSON en ~/.gemma4/cache/app_inventory.json con TTL 24h.
- Refresh en background al primer enable() del voice stack; primer arranque
  sin cache bloquea ~1-3s y rellena.
- Priority scoring (sec. 4 del prompt de fase): shortcut Desktop/Start +0.3,
  popular boost +0.1, blacklist suave -0.3, blacklist dura descarta.
- Hard cap 150 apps. Char cap 1500 (proxy de los ~224 tokens de Whisper).
- Si todo falla, callers reciben None y deben usar el fallback estatico.

CLI: python -m gemma4_agent.voice.app_inventory imprime estadisticas para
debug ("por que no entiende Saints Row?" -> ver si esta en la lista).
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
import threading
import time
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

logger = logging.getLogger(__name__)


CACHE_PATH = Path.home() / ".gemma4" / "cache" / "app_inventory.json"
DEFAULT_TTL_HOURS = 24.0
MAX_APPS = 60
PROMPT_CHAR_CAP = 900   # ~130 tokens (1900 chars / ~280 tokens anadia 200-400ms
# al primer step del decoder Whisper segun midiciones reales: pass1 con prompt
# de 1900 chars tardo 1625ms, sin prompt 1219ms = +400ms. Reducir a 900 chars
# preserva el biasing util (top apps OOV + Gemma anchor) pero recorta latencia.
# Lower bound: necesitamos espacio para >=15 menciones de "Gemma" y >=20 apps.
MIN_GEMMA_OCCURRENCES = 15

# ---------------------------------------------------------------------------
# Blacklists
# ---------------------------------------------------------------------------
# Blacklist dura: si el nombre matchea (substring case-insensitive), descartar
# entrada entera. Son non-apps que ensucian el prompt: runtimes, hotfixes,
# drivers, installers, helpers de crash, manifest-only entries del registry.
HARD_BLACKLIST: tuple[str, ...] = (
    "redistributable", "runtime", "driver pack", "kb2", "kb3", "kb4", "kb5",
    "hotfix", "service pack", "update for", "sdk", ".net framework",
    "vcredist", "directx", "java update", "helper", "crashreporter",
    "crash handler", "installer", "setup", "uninstall", "desinstalar",
    "elevation service", "feedback hub", "winrt", "appup-", "manifest",
    "websetup",
)

# Blacklist suave: penaliza priority sin descartar. Muchas apps legitimas
# llevan estas palabras en su nombre (Task Manager), por eso solo penalizamos.
SOFT_BLACKLIST: tuple[str, ...] = (
    "editor", "manager", "console", "diagnostic", "report", "tool",
)

# Boost para apps mainstream que la mayoria de usuarios usa. Sin este boost,
# una app de poco uso con shortcut en Desktop puede acabar por encima de Chrome.
POPULAR_BOOST: tuple[str, ...] = (
    "chrome", "firefox", "edge", "opera", "brave",
    "spotify", "discord", "whatsapp", "telegram", "signal",
    "obs", "vs code", "visual studio code", "vscode",
    "steam", "epic games", "epic", "battle.net", "ubisoft", "gog galaxy",
    "youtube", "netflix", "twitch", "vlc", "media player",
    "windows terminal", "notepad", "explorer", "calculator", "calculadora",
    "github desktop", "git", "docker desktop", "postman",
)


# ---------------------------------------------------------------------------
# AppEntry
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class AppEntry:
    """Una app descubierta. display_name es lo que entra al prompt de Whisper."""
    display_name: str
    aliases: tuple[str, ...] = field(default_factory=tuple)
    source: str = ""
    priority: float = 0.0


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.casefold())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text


def _is_hard_blacklisted(name: str) -> bool:
    folded = _fold(name)
    return any(b in folded for b in HARD_BLACKLIST)


def _soft_blacklist_hits(name: str) -> int:
    folded = _fold(name)
    return sum(1 for b in SOFT_BLACKLIST if b in folded)


def _has_popular_boost(name: str) -> bool:
    folded = _fold(name)
    return any(p in folded for p in POPULAR_BOOST)


# Sufijos de "version" / "arquitectura" que ensucian el display_name.
# Regex aplicado al final del nombre. Conservador: no cortar nombres legitimos.
_DISPLAY_CLEANUP_RES = (
    re.compile(r"\s*\(\s*x64\s*\)\s*$", re.IGNORECASE),
    re.compile(r"\s*\(\s*x86\s*\)\s*$", re.IGNORECASE),
    re.compile(r"\s*\(\s*64-bit\s*\)\s*$", re.IGNORECASE),
    re.compile(r"\s*\(\s*32-bit\s*\)\s*$", re.IGNORECASE),
    re.compile(r"\s*version\s+\d+(\.\d+)*\s*$", re.IGNORECASE),
    re.compile(r"\s+\d{4}(\.\d+)+\s*$"),  # "App 2024.10.1"
)


def _clean_display_name(name: str) -> str:
    """Limpia sufijos basura del nombre (arquitectura, version)."""
    out = name.strip()
    for _ in range(3):  # aplicar varias veces por si hay multiples sufijos
        before = out
        for pat in _DISPLAY_CLEANUP_RES:
            out = pat.sub("", out).strip()
        if out == before:
            break
    return out


def _gen_aliases(name: str) -> tuple[str, ...]:
    """Genera variantes utiles: acronimo si el nombre tiene >=3 words."""
    out: list[str] = []
    words = re.findall(r"[A-Za-z0-9]+", name)
    if len(words) >= 3:
        # Acronimo: solo iniciales en mayuscula (>=2 chars).
        acronym = "".join(w[0] for w in words if w[0].isalpha())
        if 2 <= len(acronym) <= 8:
            out.append(acronym.upper())
    return tuple(dict.fromkeys(out))  # dedupe preservando orden


# ---------------------------------------------------------------------------
# Recolectores que usan AppResolver (gemma4_agent.tools) como source of truth
# ---------------------------------------------------------------------------
def _safe_call(label: str, fn, timeout_s: float) -> list:
    """Llama fn() en un thread con timeout. Si crashea o no termina, [].

    Los recolectores _from_uninstall_registry y _from_start_apps lanzan
    PowerShell y pueden tardar varios segundos o colgarse en sistemas con
    AV/EDR. Mejor cortar y seguir con las fuentes que si respondieron.
    """
    result: list = []

    def _runner() -> None:
        nonlocal result
        try:
            result = list(fn() or [])
        except Exception as exc:
            logger.warning("source %s crashed: %s", label, exc)
            result = []

    t = threading.Thread(target=_runner, daemon=True, name=f"AppInvSource:{label}")
    t.start()
    t.join(timeout=timeout_s)
    if t.is_alive():
        logger.warning("source %s timed out after %.1fs", label, timeout_s)
        return []
    return result


def _collect_raw_candidates() -> list[tuple[str, str]]:
    """Reune (name, source) de todas las fuentes. Sin dedupe ni filtrado."""
    try:
        from gemma4_agent.tools import AppResolver
    except Exception as exc:
        logger.warning("AppResolver unavailable: %s", exc)
        return []
    resolver = AppResolver()
    # _from_path: indexa el PATH entero. Demasiada basura para el prompt
    # (where.exe, nslookup.exe, drivers, etc). Excluido a proposito.
    # _from_common_exe_roots: requiere query, no enumerable.
    sources: list[tuple[str, str, float]] = [
        ("shortcut", "_from_shortcuts", 2.0),
        ("registry", "_from_uninstall_registry", 10.0),
        ("steam", "_from_steam", 3.0),
        ("epic", "_from_epic", 3.0),
        ("start_app", "_from_start_apps", 8.0),
    ]
    out: list[tuple[str, str]] = []
    for label, method_name, timeout_s in sources:
        method = getattr(resolver, method_name, None)
        if method is None:
            continue
        t0 = time.monotonic()
        results = _safe_call(label, method, timeout_s)
        elapsed = time.monotonic() - t0
        logger.info("app source %s: %d entries (%.2fs)", label, len(results), elapsed)
        for cand in results:
            name = getattr(cand, "name", None) or ""
            if name:
                out.append((name, label))
    return out


# ---------------------------------------------------------------------------
# Priority scoring
# ---------------------------------------------------------------------------
def _desktop_shortcut_names() -> set[str]:
    """Devuelve nombres de .lnk en Desktop user + public (folded)."""
    out: set[str] = set()
    candidates = [
        Path.home() / "Desktop",
        Path(os.environ.get("PUBLIC", "C:/Users/Public")) / "Desktop",
    ]
    for root in candidates:
        if not root.is_dir():
            continue
        try:
            for shortcut in root.glob("*.lnk"):
                out.add(_fold(shortcut.stem))
        except OSError:
            continue
    return out


def _start_menu_user_names() -> set[str]:
    """Shortcuts del Start Menu del usuario (NO system-wide)."""
    out: set[str] = set()
    root = Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs"
    if root.is_dir():
        try:
            for shortcut in root.rglob("*.lnk"):
                out.add(_fold(shortcut.stem))
        except OSError:
            pass
    return out


def _score(
    display_name: str,
    source: str,
    desktop_names: set[str],
    start_user_names: set[str],
) -> float:
    """Priority en [0, 1]. Empates resueltos por orden alfabetico (en build)."""
    base = 0.5
    folded = _fold(display_name)

    boost = 0.0
    if folded in desktop_names:
        boost += 0.3
    if folded in start_user_names:
        boost += 0.2
    # Juegos de Steam/Epic: el usuario los instalo deliberadamente y los
    # nombres son MUY propensos a OOV ("Saints Row", "Cyberpunk 2077",
    # "Hollow Knight") - exactamente lo que el prompt debe sesgar. Boost
    # mas alto que apps mainstream (que Whisper ya conoce bien). El Start
    # Menu del usuario suele estar inundado de shortcuts de drivers/utility
    # software pre-instalado (Brother iPrint, Focusrite, HidHide...) y
    # necesitamos que los juegos los superen.
    if source in ("steam", "epic"):
        boost += 0.4
    if _has_popular_boost(display_name):
        boost += 0.1
    penalty = 0.0
    soft_hits = _soft_blacklist_hits(display_name)
    if soft_hits:
        penalty += 0.3 * min(1, soft_hits)
    score = base + boost - penalty
    return max(0.0, min(1.0, score))


# ---------------------------------------------------------------------------
# Discovery principal
# ---------------------------------------------------------------------------
def discover_apps(*, use_cache: bool = True, cache_ttl_h: float = DEFAULT_TTL_HOURS) -> list[AppEntry]:
    """Devuelve la lista de apps instaladas, ordenadas por priority desc.

    Si use_cache=True y el cache esta fresco (< cache_ttl_h horas), lo carga.
    Si no, escanea el sistema y reescribe el cache.
    """
    if use_cache:
        cached = _load_cache(cache_ttl_h)
        if cached is not None:
            logger.info("app_inventory: loaded %d apps from cache", len(cached))
            return cached
    apps = _discover_fresh()
    _save_cache(apps)
    return apps


def _discover_fresh() -> list[AppEntry]:
    if sys.platform != "win32":
        logger.info("app_inventory: non-Windows platform, returning empty")
        return []
    t0 = time.monotonic()
    desktop_names = _desktop_shortcut_names()
    start_user_names = _start_menu_user_names()
    raw = _collect_raw_candidates()
    if not raw:
        logger.warning("app_inventory: no candidates from any source")
        return []
    # Dedupe por display_name folded; preferir la entrada con mejor priority.
    by_key: dict[str, AppEntry] = {}
    skipped_hard = 0
    for raw_name, source in raw:
        display = _clean_display_name(raw_name)
        if not display or len(display) < 2:
            continue
        if _is_hard_blacklisted(display):
            skipped_hard += 1
            continue
        key = _fold(display)
        if not key:
            continue
        priority = _score(display, source, desktop_names, start_user_names)
        entry = AppEntry(
            display_name=display,
            aliases=_gen_aliases(display),
            source=source,
            priority=priority,
        )
        existing = by_key.get(key)
        if existing is None or entry.priority > existing.priority:
            by_key[key] = entry
    apps = sorted(
        by_key.values(),
        key=lambda e: (-e.priority, e.display_name.casefold()),
    )
    elapsed = time.monotonic() - t0
    # No loggear nombres (privacidad), solo el conteo.
    logger.info(
        "app_inventory: discovered %d apps in %.2fs (skipped %d by hard blacklist)",
        len(apps), elapsed, skipped_hard,
    )
    return apps


# ---------------------------------------------------------------------------
# Cache en disco
# ---------------------------------------------------------------------------
def _cache_fresh(cache_ttl_h: float) -> bool:
    if not CACHE_PATH.is_file():
        return False
    try:
        age_s = time.time() - CACHE_PATH.stat().st_mtime
    except OSError:
        return False
    return age_s < cache_ttl_h * 3600


def _load_cache(cache_ttl_h: float) -> list[AppEntry] | None:
    if not _cache_fresh(cache_ttl_h):
        return None
    try:
        data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.debug("cache unreadable (%s); ignoring", exc)
        return None
    apps: list[AppEntry] = []
    for item in data.get("apps") or []:
        try:
            apps.append(AppEntry(
                display_name=str(item["display_name"]),
                aliases=tuple(item.get("aliases") or ()),
                source=str(item.get("source") or ""),
                priority=float(item.get("priority") or 0.0),
            ))
        except (KeyError, TypeError, ValueError):
            continue
    return apps or None


def _save_cache(apps: list[AppEntry]) -> None:
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "saved_at": time.time(),
            "apps": [asdict(a) for a in apps],
        }
        # asdict deja tuples como tuples; json.dumps no las maneja en algunos
        # paths. Convertir a list explicitamente para aliases.
        for a in payload["apps"]:
            a["aliases"] = list(a.get("aliases") or [])
        CACHE_PATH.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    except OSError as exc:
        logger.warning("could not save app_inventory cache: %s", exc)


# ---------------------------------------------------------------------------
# Construccion del prompt
# ---------------------------------------------------------------------------
# Plantilla base con "Gemma" >= MIN_GEMMA_OCCURRENCES menciones. Las apps se
# interpolan en grupos. Cierra con frases generales para anclar estilo.
_PROMPT_PREFIX = (
    # Sprint R3.1 final (2026-05-19): operator confirmed that the
    # real usage pattern is Spanish-rioplatense embedded with English
    # app/song/person names. The decoder MUST keep these proper nouns
    # in their original English spelling. Seed the prompt with
    # bilingual command pairs ('abre X' / 'open X') so the decoder
    # doesn't phoneticize English nouns (e.g. Chrome -> Aurecrum,
    # Boone -> Mould, Spotify -> Esportifai).
    "Conversacion con el asistente Gemma en espanol rioplatense con nombres "
    "de aplicaciones y canciones en ingles. "
    "Hey Gemma, abre Chrome. Hey Gemma, open Chrome. "
    "Hey Gemma, abre Spotify. Hey Gemma, open Spotify. "
    "Hey Gemma, reproduce Bohemian Rhapsody de Queen. "
    "Hey Gemma, buscame info sobre Benson Boone en Google. "
)
_PROMPT_SUFFIX = (
    "Gemma, apaga la luz del salon. Gemma, enciende la luz de la cocina. "
    "Gemma, sube el volumen. Gemma, baja el volumen. Gemma, pausa la musica. "
    "Gemma, pon el temporizador a cinco minutos. Gemma, que hora es. "
    "Gemma, busca en Google. Gemma, cierra la ventana. "
    "Gemma, mandale un mensaje a Juan por WhatsApp. "
    "Comandos breves en espanol con nombres de apps en ingles."
)


def _groups_of(items: list[str], group_sizes: Iterable[int]) -> list[list[str]]:
    """Reparte items en grupos de los tamanos dados (ciclando si hace falta).

    Tamanos pequenos al principio (frases mas naturales), mas grandes despues.
    """
    sizes = list(group_sizes) or [3]
    out: list[list[str]] = []
    i = 0
    s = 0
    while i < len(items):
        size = sizes[s % len(sizes)]
        chunk = items[i:i + size]
        if chunk:
            out.append(chunk)
        i += size
        s += 1
    return out


def _phrase_for_group(group: list[str], idx: int) -> str:
    """Genera una frase natural en espanol con las apps del grupo."""
    if not group:
        return ""
    if len(group) == 1:
        # Variar el verbo segun idx para no repetir
        verbs = ["abre", "abre", "cierra", "pausa", "minimiza"]
        verb = verbs[idx % len(verbs)]
        return f"Gemma, {verb} {group[0]}."
    if len(group) == 2:
        return f"Hey Gemma, abre {group[0]} y {group[1]}."
    head = ", ".join(group[:-1])
    return f"Gemma, abre {head} y {group[-1]}."


def build_initial_prompt(apps: list[AppEntry], max_apps: int = MAX_APPS) -> str:
    """Construye el INITIAL_PROMPT con las top-N apps por priority.

    Si apps esta vacio, devuelve un prompt fallback (sin lista de apps).
    Garantiza:
      - "Gemma" aparece >= MIN_GEMMA_OCCURRENCES veces.
      - len(prompt) <= PROMPT_CHAR_CAP (truncando apps de menor priority).
    """
    names: list[str] = []
    for a in apps[:max_apps]:
        if a.display_name and a.display_name not in names:
            names.append(a.display_name)

    def _assemble(app_names: list[str]) -> str:
        if not app_names:
            apps_block = (
                "Hey Gemma, abre Chrome. Gemma, abre Spotify y Discord. "
                "Gemma, abre VS Code y YouTube. "
            )
        else:
            # Tamanos crecientes -> frase corta primero (mas natural), luego
            # listas mas largas para meter mas apps en menos caracteres.
            groups = _groups_of(app_names, group_sizes=[2, 3, 4, 5, 6])
            phrases: list[str] = []
            for i, g in enumerate(groups):
                phrases.append(_phrase_for_group(g, i))
            apps_block = " ".join(phrases) + " "
        return _PROMPT_PREFIX + apps_block + _PROMPT_SUFFIX

    prompt = _assemble(names)
    # Truncar progresivamente apps de menor priority hasta caber.
    while len(prompt) > PROMPT_CHAR_CAP and names:
        names.pop()
        prompt = _assemble(names)

    # Garantizar >= MIN_GEMMA_OCCURRENCES menciones de "Gemma".
    gemma_count = prompt.count("Gemma") + prompt.count("gemma")
    if gemma_count < MIN_GEMMA_OCCURRENCES:
        # Anadir frases de relleno con "Gemma" antes del suffix, sin romper
        # el char cap.
        filler = " Gemma, dime. Gemma, escucha. Gemma, ayudame. " * 3
        prompt = prompt.replace(_PROMPT_SUFFIX, filler + _PROMPT_SUFFIX, 1)
        if len(prompt) > PROMPT_CHAR_CAP:
            # Truncar mas apps si nos pasamos.
            while len(prompt) > PROMPT_CHAR_CAP and names:
                names.pop()
                prompt = _assemble(names)
                prompt = prompt.replace(_PROMPT_SUFFIX, filler + _PROMPT_SUFFIX, 1)
    return prompt


# ---------------------------------------------------------------------------
# API publica de cache + background refresh
# ---------------------------------------------------------------------------
_lock = threading.Lock()
_cached_prompt: str | None = None
_refresh_thread: threading.Thread | None = None


def get_cached_prompt() -> str | None:
    """Devuelve el prompt construido del inventario.

    Carga el cache si existe (fresco o stale). NO regenera por defecto:
    eso lo hace refresh_in_background(). Si no hay cache en absoluto,
    devuelve None para que el caller use el fallback estatico.
    """
    global _cached_prompt
    with _lock:
        if _cached_prompt is not None:
            return _cached_prompt
    # Sin cache en memoria: intentar leer disco (incluso si stale).
    apps = _load_cache(cache_ttl_h=float("inf"))
    if not apps:
        return None
    prompt = build_initial_prompt(apps)
    with _lock:
        _cached_prompt = prompt
    return prompt


def refresh_in_background(*, cache_ttl_h: float = DEFAULT_TTL_HOURS) -> None:
    """Lanza un thread que regenera el inventario si el cache esta stale.

    No-op si ya hay un refresh corriendo. No bloquea al caller.
    """
    global _refresh_thread
    with _lock:
        if _refresh_thread is not None and _refresh_thread.is_alive():
            return

        def _runner() -> None:
            global _cached_prompt
            try:
                fresh = _cache_fresh(cache_ttl_h)
                if fresh:
                    # Cache fresco: solo asegurarse de tener el prompt en memoria.
                    apps = _load_cache(cache_ttl_h)
                    if apps:
                        prompt = build_initial_prompt(apps)
                        with _lock:
                            _cached_prompt = prompt
                    return
                apps = _discover_fresh()
                _save_cache(apps)
                prompt = build_initial_prompt(apps)
                with _lock:
                    _cached_prompt = prompt
            except Exception as exc:
                logger.warning("app_inventory background refresh failed: %s", exc)

        t = threading.Thread(target=_runner, daemon=True, name="AppInventoryRefresh")
        _refresh_thread = t
        t.start()


def ensure_prompt_available(*, sync_timeout_s: float = 3.0) -> str | None:
    """Garantiza un prompt utilizable cuanto antes.

    - Si hay prompt cacheado en memoria o en disco, devuelve eso inmediatamente
      y dispara refresh en background.
    - Si NO hay cache en absoluto, ejecuta discovery sincrono limitado a
      sync_timeout_s y devuelve lo que se haya podido recolectar (puede ser
      vacio si todo fallo dentro del timeout).
    """
    prompt = get_cached_prompt()
    refresh_in_background()
    if prompt is not None:
        return prompt
    # Primer arranque: bloquear acotado.
    result_holder: dict = {"apps": []}

    def _runner() -> None:
        result_holder["apps"] = _discover_fresh()

    t = threading.Thread(target=_runner, daemon=True, name="AppInventoryFirstRun")
    t.start()
    t.join(timeout=sync_timeout_s)
    apps = result_holder["apps"]
    if not apps:
        return None
    _save_cache(apps)
    prompt = build_initial_prompt(apps)
    with _lock:
        global _cached_prompt
        _cached_prompt = prompt
    return prompt


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _cli() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    t0 = time.monotonic()
    apps = discover_apps(use_cache=False)  # CLI siempre re-escanea
    elapsed = time.monotonic() - t0
    if not apps:
        print(f"No apps discovered ({elapsed:.2f}s). Cache: {CACHE_PATH}")
        return 1
    by_source: dict[str, int] = {}
    for a in apps:
        by_source[a.source] = by_source.get(a.source, 0) + 1
    print(f"Discovered {len(apps)} apps in {elapsed:.2f}s")
    print("By source:")
    for src in sorted(by_source):
        print(f"  {src:<14} {by_source[src]}")
    print()
    print("Top 30 by priority:")
    for a in apps[:30]:
        aliases = f" (aka {','.join(a.aliases)})" if a.aliases else ""
        print(f"  {a.priority:.2f}  [{a.source:<10}]  {a.display_name}{aliases}")
    print()
    prompt = build_initial_prompt(apps)
    gemma_count = prompt.count("Gemma") + prompt.count("gemma")
    print(f"Prompt: {len(prompt)} chars, 'Gemma' x{gemma_count}")
    print(f"Cache: {CACHE_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
