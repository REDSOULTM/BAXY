"""Fase V — Perfiles dinamicos de VRAM (Performance / Balanced / Light / Standby).

Cuatro perfiles que cambian context_size, modelo, vision (mmproj), rerank,
parallel_tools y fact_extraction de forma atomica. STANDBY apaga llama-server
y deja la GUI viva en modo solo-lectura.

Modulo nuevo, no toca core. Reusa state.atomic_write_json y el patron de
env vars existentes. AgentConfig.from_env() y los modulos que leen env vars
directamente (knowledge.py reranker, agent.py parallel_tools/fact_extraction,
config.py mmproj_path/model_path/context_size) recogen los cambios en el
proximo restart_worker.

Decisiones:
- profile_size se persiste en ~/.gemma4/active_profile.txt (una linea).
- profiles.json (overrides editables por el usuario) en ~/.gemma4/profiles.json.
- Para apagar vision: GEMMA4_MMPROJ_PATH="" (cadena vacia). AgentConfig.from_env
  ya respeta esto via `Path(raw) if raw else default` -- pero cadena vacia es
  falsy en Python, asi que default se aplica. Para forzar "sin mmproj" hay que
  detectar el caso en launcher.py al construir el comando del server.
- Si profile.model_path es None: usar GEMMA4_MODEL_PATH actual del usuario
  (default de AgentConfig). Si el path apunta a un archivo inexistente
  (caso LIGHT con modelo chico no bajado), NO sobreescribimos
  GEMMA4_MODEL_PATH -- el caller debe detectar y caer al modelo principal.

VRAM estimada (est_vram_mb) en cada perfil es solo display en UI; no se
usa para decisiones. Numeros vienen del INFORME_ARQUITECTURA_6GB.md de
esta misma sesion de investigacion.
"""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .state import atomic_write_json


PROFILE_NAMES = ("performance", "balanced", "light", "standby")

ACTIVE_PROFILE_PATH = Path.home() / ".gemma4" / "active_profile.txt"
PROFILES_OVERRIDES_PATH = Path.home() / ".gemma4" / "profiles.json"


def atomic_write_text(path: Path, text: str) -> None:
    """Atomic text write (analogous to state.atomic_write_json)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


@dataclass(frozen=True)
class Profile:
    name: str
    display_name: str
    context_size: int
    model_path: str | None  # None = use user's default GEMMA4_MODEL_PATH
    vision_enabled: bool
    rerank_enabled: bool
    parallel_tools: bool  # J5 backend parallel tool execution
    fact_extraction: bool
    server_running: bool
    # Voice ON/OFF por perfil. Whisper + Piper corren en CPU (0 VRAM), asi
    # que la decision por defecto es "ON en todos los perfiles con server".
    # standby fuerza voice_enabled=False (no hay LLM al que entregar el texto).
    # El usuario sigue teniendo un master switch en Settings que prevalece.
    voice_enabled: bool
    description: str
    est_vram_mb: int  # display only; not used for decisions


# Defaults — copiados aqui para que sean editables sin tocar profiles.json.
# El usuario puede sobreescribir cualquier campo via Settings > Profiles.
# Paths default a los GGUF reales del repo. Numeros entre parentesis son
# VRAM cargada real medida en RTX 4060 Ti (idle ~1.2 GB incluido), CSV en
# documentacion/datos_crudos/vram_real_medida.csv. NO confundir con "delta
# del modelo" (peso del modelo vs idle Windows): el cargado es lo que el
# usuario ve en nvidia-smi y es el que cuenta para el budget.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_E2B_Q4_K_M = str(_PROJECT_ROOT / "models" / "E2B" / "gemma-4-E2B-it-Q4_K_M.gguf")  # 4.46 GB cargado
_E2B_Q5_K_M = str(_PROJECT_ROOT / "models" / "E2B" / "gemma-4-E2B-it-Q5_K_M.gguf")  # 4.70 GB cargado
_E4B_Q4_K_M = str(_PROJECT_ROOT / "models" / "E4B" / "gemma-4-E4B-it-Q4_K_M.gguf")  # 6.10 GB cargado


PROFILES: dict[str, Profile] = {
    "performance": Profile(
        name="performance",
        display_name="Performance",
        context_size=32768,
        model_path=None,  # usuario configura modelo principal (Q6_K u otro grande)
        vision_enabled=True,
        rerank_enabled=True,
        parallel_tools=True,
        fact_extraction=True,
        server_running=True,
        voice_enabled=True,
        description=(
            "Maximo rendimiento. Context 32K, vision ON, rerank ON, "
            "parallel tools ON, fact extraction ON, voice ON. Para 12+ GB VRAM. "
            "Usa el modelo principal del usuario (Q6_K o superior)."
        ),
        est_vram_mb=7500,
    ),
    "balanced": Profile(
        name="balanced",
        display_name="Balanced",
        context_size=8192,
        model_path=_E2B_Q5_K_M,  # 4.70 GB cargado real (NO E4B-Q4_K_M, que mide 6.10 GB y NO entra en 6 GB)
        vision_enabled=False,    # mmproj F16 (0.9 GB) rompe el budget de 6 GB
        rerank_enabled=True,
        parallel_tools=False,
        fact_extraction=False,
        server_running=True,
        voice_enabled=True,
        description=(
            "Perfil objetivo para 6 GB VRAM. E2B-Q5_K_M (mejor calidad que "
            "Q4_K_M y misma familia que light), context 8K, vision OFF, "
            "rerank ON, voice ON (CPU). Racional: 4.70 GB cargado + KV F16 8K "
            "(~0.40) = ~5.1 GB. Holgura ~0.9 GB sobre 6 GB nominales."
        ),
        # E2B-Q5_K_M (4.70) + KV F16 8K (~0.40) ~= 5.10 GB. Sin KV quant
        # porque la doc del repo (04_vram_y_hardware) advierte contra q8_0 KV
        # en Gemma 4 sin medir.
        est_vram_mb=5100,
    ),
    "light": Profile(
        name="light",
        display_name="Light",
        context_size=4096,
        model_path=_E2B_Q4_K_M,  # 4.46 GB cargado: cabe con holgura en 4-6 GB
        vision_enabled=False,
        rerank_enabled=False,
        parallel_tools=False,
        fact_extraction=False,
        server_running=True,
        voice_enabled=True,
        description=(
            "Modo gaming/4 GB VRAM. E2B-Q4_K_M, context 4K, vision OFF, "
            "rerank OFF, voice ON (CPU). 4.46 GB cargado + KV F16 4K "
            "(~0.20) = ~4.66 GB. Deja ~1.3 GB libres en 6 GB para juego."
        ),
        # E2B-Q4_K_M (4.46) + KV F16 4K (~0.20) ~= 4.66 GB.
        est_vram_mb=4700,
    ),
    "standby": Profile(
        name="standby",
        display_name="Standby",
        context_size=4096,  # irrelevante pero algo hay que poner
        model_path=None,
        vision_enabled=False,
        rerank_enabled=False,
        parallel_tools=False,
        fact_extraction=False,
        server_running=False,
        voice_enabled=False,  # sin LLM no hay a quien hablarle
        description=(
            "llama-server apagado. La GUI sigue viva (memory viewer, "
            "sessions, triggers, tool explorer non-LLM). El chat muestra "
            "'Server offline — switch profile to chat.' VRAM ~0. Voice OFF "
            "porque no hay LLM al que entregar el texto."
        ),
        est_vram_mb=0,
    ),
}


def detect_vram_mb() -> int | None:
    """Detecta VRAM total de la GPU principal en MB.

    Orden de intentos:
    1. nvidia-smi (NVIDIA)
    2. rocm-smi (AMD)
    3. None (sin GPU detectable o sin tools instaladas)

    subprocess timeout=3s en todos los casos. Errores silenciosos -> None.
    """
    # NVIDIA
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            # Toma la primera GPU si hay varias
            first_line = result.stdout.strip().splitlines()[0].strip()
            return int(first_line)
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError, OSError):
        pass

    # AMD
    try:
        result = subprocess.run(
            ["rocm-smi", "--showmeminfo", "vram", "--csv"],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            # rocm-smi devuelve bytes; parseamos burdamente
            for line in result.stdout.splitlines():
                parts = line.split(",")
                for part in parts:
                    part = part.strip()
                    if part.isdigit():
                        val_bytes = int(part)
                        if val_bytes > 1_000_000_000:  # >1GB plausible
                            return val_bytes // (1024 * 1024)
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError, OSError):
        pass

    # dxdiag fallback intencionalmente omitido: parseo poco fiable y el usuario
    # puede setear manualmente el perfil. Retornamos None.
    return None


# Reserva fija de VRAM para Windows/WDDM + driver buffers + headroom CUDA.
# El informe de auditoria externa (Bloque F1, item I1 #10) cita evidencia
# anecdotica de foros Microsoft / Tom's Hardware de 0.6-1.2 GB para dwm.exe
# mas 150-400 MB para buffers de driver. Reservamos 1.5 GB como cifra
# conservadora para que un usuario con 6 GB fisicos y Chrome abierto NO
# sufra OOM al arrancar el server.
WINDOWS_VRAM_RESERVE_MB = 1500


def recommend_profile(vram_mb: int | None) -> str:
    """Sugiere perfil segun VRAM detectada.

    Aplica una reserva fija de WINDOWS_VRAM_RESERVE_MB (1.5 GB) al valor
    reportado por nvidia-smi antes de mapear, porque Windows 11 + driver
    consumen esa cantidad antes de que el server arranque. Cortes en VRAM
    *efectiva* (post-reserva):

    >=10500 MB efectiva (>=12 GB fisicos) -> performance
    >= 4500 MB efectiva (>= 6 GB fisicos) -> balanced
    >= 2500 MB efectiva (>= 4 GB fisicos) -> light
    resto / None                          -> light (voice CPU sigue ON)
    """
    if vram_mb is None:
        # Sin GPU detectable: light es el mas conservador. Voice CPU
        # sigue andando aunque el LLM corra en CPU lento o falle.
        return "light"
    effective = max(0, int(vram_mb) - WINDOWS_VRAM_RESERVE_MB)
    if effective >= 10500:
        return "performance"
    if effective >= 4500:
        return "balanced"
    if effective >= 2500:
        return "light"
    return "light"


def get_active_profile() -> Profile:
    """Lee ~/.gemma4/active_profile.txt y devuelve el Profile correspondiente.

    Si el archivo no existe (primer arranque del usuario), detecta VRAM una
    vez y persiste el perfil recomendado. Asi la app arranca con el perfil
    correcto sin pedirle al usuario que vaya a Settings.

    Default fallback: balanced (si no se puede detectar VRAM).
    """
    if not ACTIVE_PROFILE_PATH.is_file():
        # Primera vez: detecta y persiste. Si falla, queda en balanced sin
        # escribir nada (asi en la proxima ejecucion vuelve a intentar).
        try:
            vram_mb = detect_vram_mb()
            recommended = recommend_profile(vram_mb)
            set_active_profile(recommended)
            return _profile_with_overrides(PROFILES[recommended])
        except (OSError, ValueError):
            return PROFILES["balanced"]
    try:
        name = ACTIVE_PROFILE_PATH.read_text(encoding="utf-8").strip().casefold()
    except OSError:
        return PROFILES["balanced"]
    if name not in PROFILES:
        return PROFILES["balanced"]
    return _profile_with_overrides(PROFILES[name])


def set_active_profile(name: str) -> None:
    """Persiste el nombre del perfil activo atomicamente."""
    if name not in PROFILES:
        raise ValueError(f"unknown profile: {name!r} (valid: {PROFILE_NAMES})")
    atomic_write_text(ACTIVE_PROFILE_PATH, name)


def load_overrides() -> dict[str, dict[str, Any]]:
    """Lee profiles.json con overrides del usuario.

    Formato esperado:
        {
          "performance": {"context_size": 65536, ...},
          "light": {"model_path": "C:/.../gemma-3n-e2b-it.Q4_K_M.gguf"},
          ...
        }
    Solo se sobreescriben los campos presentes; el resto se hereda de PROFILES.
    """
    if not PROFILES_OVERRIDES_PATH.is_file():
        return {}
    try:
        import json
        raw = PROFILES_OVERRIDES_PATH.read_text(encoding="utf-8")
        data = json.loads(raw)
        if not isinstance(data, dict):
            return {}
        return data
    except (OSError, ValueError):
        return {}


def save_overrides(data: dict[str, dict[str, Any]]) -> None:
    """Persiste profiles.json con overrides atomicamente."""
    atomic_write_json(PROFILES_OVERRIDES_PATH, data)


def _profile_with_overrides(base: Profile) -> Profile:
    """Aplica overrides de ~/.gemma4/profiles.json sobre un Profile base.

    Standby es inmutable (server_running siempre False).
    """
    if base.name == "standby":
        return base
    overrides_all = load_overrides()
    these = overrides_all.get(base.name) or {}
    if not these:
        return base
    from dataclasses import replace
    # Solo aceptamos overrides de campos conocidos y tipados
    allowed: dict[str, Any] = {}
    for field_name in (
        "context_size", "model_path", "vision_enabled", "rerank_enabled",
        "parallel_tools", "fact_extraction", "voice_enabled", "est_vram_mb",
        "display_name", "description",
    ):
        if field_name in these:
            allowed[field_name] = these[field_name]
    if not allowed:
        return base
    try:
        return replace(base, **allowed)
    except (TypeError, ValueError):
        return base


def apply_profile_to_env(profile: Profile) -> None:
    """Escribe las env vars del perfil a os.environ.

    Variables tocadas:
        GEMMA4_AGENT_CONTEXT          -> str(profile.context_size)
        GEMMA4_KNOWLEDGE_RERANK       -> "true"/"false"
        GEMMA4_AGENT_PARALLEL_TOOLS   -> "true"/"false"  (J5 backend, no llama-server)
        GEMMA4_AGENT_FACT_EXTRACTION  -> "true"/"false"
        GEMMA4_ACTIVE_PROFILE         -> profile.name (informativo)
        GEMMA4_MMPROJ_PATH            -> "" si vision_enabled=False;
                                          NO se toca si vision_enabled=True
        GEMMA4_MODEL_PATH             -> profile.model_path SI esta seteado Y el
                                          archivo existe en disco;
                                          NO se toca en cualquier otro caso

    Casos no-obvios documentados (cubiertos por tests V3/V8):

    - vision_enabled=True NO sobreescribe GEMMA4_MMPROJ_PATH. Respetamos el
      path que el usuario configuro via Settings, porque cada usuario tiene
      su mmproj en una ruta distinta. Si querias forzar mmproj de un perfil,
      tenes que hacerlo via Settings -> CONNECTION, no via perfil.

    - profile.model_path solo se aplica si el archivo EXISTE en disco. Esto
      cubre el caso "perfil LIGHT con GGUF chico que el usuario aun no bajo":
      apply_profile_to_env no rompe nada, deja el GEMMA4_MODEL_PATH del
      usuario (modelo principal), y el caller (UI) muestra un warning amber
      con instrucciones de donde poner el archivo. Ver light_model_missing().

    - Si necesitas saber cual va a ser el efecto sin tocar env vars, leer
      los campos del Profile directamente -- NO hay forma de "preview"
      separada de la mutacion.

    Esta funcion NO reinicia el server. NO reinicia el agent worker. El caller
    (UI selector / launcher / profile_watcher) decide cuando ejecutar restart.
    """
    os.environ["GEMMA4_AGENT_CONTEXT"] = str(int(profile.context_size))
    os.environ["GEMMA4_KNOWLEDGE_RERANK"] = "true" if profile.rerank_enabled else "false"
    os.environ["GEMMA4_AGENT_PARALLEL_TOOLS"] = "true" if profile.parallel_tools else "false"
    os.environ["GEMMA4_AGENT_FACT_EXTRACTION"] = "true" if profile.fact_extraction else "false"
    os.environ["GEMMA4_ACTIVE_PROFILE"] = profile.name
    # Voice toggle por perfil. main_window y voice_runner leen esto + el
    # master switch del usuario en Settings (voice.enabled). La AND de los
    # dos es lo que enciende voice.
    os.environ["GEMMA4_VOICE_PROFILE_ALLOWS"] = "true" if profile.voice_enabled else "false"

    # Vision: cadena vacia significa "no cargar mmproj". launcher.py debe
    # detectar este caso y omitir --mmproj del comando.
    if not profile.vision_enabled:
        os.environ["GEMMA4_MMPROJ_PATH"] = ""
    # Si vision_enabled=True NO tocamos GEMMA4_MMPROJ_PATH; respetamos el
    # valor que el usuario haya configurado en Settings.

    # Modelo: solo lo sobreescribimos si el perfil define uno Y el archivo existe.
    # Caso LIGHT con light_model_path inexistente: NO tocamos y dejamos que el
    # caller muestre warning amber. El agente seguira con el modelo principal.
    if profile.model_path:
        candidate = Path(profile.model_path).expanduser()
        if candidate.is_file():
            os.environ["GEMMA4_MODEL_PATH"] = str(candidate)
        # else: silencio. Caller (UI) debe verificar con light_model_missing().


def light_model_configured() -> str | None:
    """Devuelve el model_path del perfil LIGHT (con overrides) o None."""
    profile = _profile_with_overrides(PROFILES["light"])
    return profile.model_path


def light_model_missing() -> bool:
    """True si LIGHT tiene model_path configurado pero el archivo no existe.

    Caller debe llamar a esto antes de aplicar LIGHT para decidir si
    mostrar warning amber + caer al modelo principal con ctx bajo.
    """
    path = light_model_configured()
    if not path:
        return False  # no configurado -> usar default, no es "missing"
    try:
        return not Path(path).expanduser().is_file()
    except OSError:
        return True
