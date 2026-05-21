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


PROFILE_NAMES = ("vram3", "vram4", "vram6", "vram8", "vram12", "vram16", "standby")

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
    # mmproj path for vision. When vision_enabled=True and this is set to an
    # existing file, apply_profile_to_env() forces GEMMA4_MMPROJ_PATH to it so
    # the profile is self-contained ("every profile has vision"). When None,
    # the legacy behavior holds (respect the user's Settings mmproj path).
    mmproj_path: str | None = None
    # Camera (live webcam vision) — reserved for a future small VLM
    # (e.g. Moondream) running alongside. Off everywhere today; the field
    # exists so profiles + UI can carry it without a later schema change.
    camera_enabled: bool = False


# Defaults — copiados aqui para que sean editables sin tocar profiles.json.
# El usuario puede sobreescribir cualquier campo via Settings > Profiles.
# Paths default a los GGUF reales del repo. Numeros entre parentesis son
# VRAM cargada real medida en RTX 4060 Ti (idle ~1.2 GB incluido), CSV en
# documentacion/datos_crudos/vram_real_medida.csv. NO confundir con "delta
# del modelo" (peso del modelo vs idle Windows): el cargado es lo que el
# usuario ve en nvidia-smi y es el que cuenta para el budget.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_E2B = _PROJECT_ROOT / "models" / "E2B"
_E4B = _PROJECT_ROOT / "models" / "E4B"

# GGUF paths. VRAM numbers in comments are REAL nvidia-smi deltas over the
# Windows idle baseline (2.06 GB), measured 2026-05-20 on an RTX 4060 Ti with
# scripts/measure_vram_profiles.py — flash-attn on, -ngl 99, at the ctx noted.
# These REPLACE the earlier comment values, which were inflated ~2x (they had
# the dev model still resident in VRAM): e.g. E2B-Q4 was "4.46 GB" but loads
# at 2.16 GB no-vision / 3.36 GB with vision.
_E2B_Q2_K_XL = str(_E2B / "gemma-4-E2B-it-UD-Q2_K_XL.gguf")  # 1.75 novis / 2.94 +vis @2K
_E2B_Q4_K_M  = str(_E2B / "gemma-4-E2B-it-Q4_K_M.gguf")      # 2.16 novis / 3.36 +vis @4K
_E2B_Q5_K_M  = str(_E2B / "gemma-4-E2B-it-Q5_K_M.gguf")      # 2.41 novis @8K
_E4B_Q4_K_M  = str(_E4B / "gemma-4-E4B-it-Q4_K_M.gguf")      # 4.96 +vis @8K
_E4B_Q4_K_XL = str(_E4B / "gemma-4-E4B-it-UD-Q4_K_XL.gguf")  # 5.23 +vis @16K
_E4B_Q6_K    = str(_E4B / "gemma-4-E4B-it-Q6_K.gguf")        # 6.34 +vis @32K
# 26B-A4B = MoE (26B de capacidad, ~4B activos por token -> rápido como E4B pero
# mucho más inteligente). Es el modelo para aprovechar 12-16 GB de VRAM. Medido:
# UD-Q3_K_XL carga ~15.7 GB en GPU @ctx16K y genera ~43 tok/s (vs E4B-Q6 que
# dejaba 3.4 GB en CPU y daba 34 tok/s). E4B nunca pasaba de ~7 GB sin importar
# la VRAM disponible — por eso vram12/16 "no usaban más de 7 GB".
_26B = _PROJECT_ROOT / "models" / "26B-A4B"
_26B_Q3_K_XL = str(_26B / "gemma-4-26B-A4B-it-UD-Q3_K_XL.gguf")  # ~13 GB, vram12/16
_26B_Q4_K_M  = str(_26B / "gemma-4-26B-A4B-it-UD-Q4_K_M.gguf")   # ~16 GB, vram16 si sobra
_MMPROJ_26B  = str(_26B / "mmproj-F16.gguf")
_MMPROJ_E2B  = str(_E2B / "mmproj-F16.gguf")                 # vision encoder (~1.2 GB loaded)
_MMPROJ_E4B  = str(_E4B / "mmproj-F16.gguf")


# ===========================================================================
# Perfiles nombrados por VRAM (2026-05-20). Reemplazan los nombres antiguos
# (perf/bal8/bal/light); los viejos se conservan como ALIASES (ver _ALIASES y
# get/set) para no romper ~/.gemma4/active_profile.txt de usuarios existentes.
#
# REGLA DE DISEÑO (pedido del operador): TODOS los perfiles activos tienen
# voz (Piper, CPU) + transcripción (Whisper, CPU) + VISIÓN (mmproj). La voz y
# STT cuestan 0 VRAM (corren en CPU); la visión cuesta ~1.2 GB cargado, y la
# medición real (scripts/measure_vram_profiles.py) confirmó que ENTRA incluso
# en 4 GB. Cada perfil escala el MODELO (cuantización) y el contexto: del más
# chico (vram3) al más grande (vram16). camera_enabled queda reservado para
# un VLM de webcam futuro (Moondream-like) — off en todos hoy.
#
# Columna "cargado" = delta real de nvidia-smi sobre idle Windows (2.06 GB),
# CON visión y al ctx indicado. "física" = cargado + 1.5 GB reserva WDDM.
#
# PISO DE CONTEXTO (medido 2026-05-20): el system prompt del agente arma
# 4.6k tokens en un "hola" y hasta ~9.2k en un turno multi-tool. Por eso
# NINGÚN perfil baja de 16K de contexto — con menos, el propio prompt no entra
# y hasta "hola" da 400 exceed_context_size. (Antes vram3/4/6 estaban en
# 2K/4K/8K y eran INUSABLES.) El KV cache a 16K cuesta poca VRAM (~0.4-0.7 GB
# con flash-attn + SWA); el modelo sigue siendo el costo dominante.
# ===========================================================================
PROFILES: dict[str, Profile] = {
    "vram3": Profile(
        name="vram3",
        display_name="VRAM 3GB",
        context_size=16384,
        model_path=_E2B_Q4_K_M,  # subido de Q2_K_XL: Q2 no tool-callea fiable
        mmproj_path=_MMPROJ_E2B,
        vision_enabled=True,
        rerank_enabled=False,
        parallel_tools=False,
        fact_extraction=False,
        server_running=True,
        voice_enabled=True,
        camera_enabled=False,
        description=(
            "GPU de 3-4 GB. E2B-Q4_K_M (subido desde Q2: Q2 no emite tool-calls "
            "de forma fiable ni forzado — medido), ctx 16K, VISIÓN ON, voz+STT "
            "ON (CPU). ~3.38 GB modelo + KV 16K -> ~5 GB física. Acciones "
            "razonables; para tool-calling más fiable subí a vram4+ (E4B)."
        ),
        est_vram_mb=2940,
    ),
    "vram4": Profile(
        name="vram4",
        display_name="VRAM 4GB",
        context_size=16384,
        model_path=_E4B_Q4_K_M,  # subido de E2B-Q4: E4B tool-callea fiable (67%+)
        mmproj_path=_MMPROJ_E4B,
        vision_enabled=True,
        rerank_enabled=False,
        parallel_tools=False,
        fact_extraction=False,
        server_running=True,
        voice_enabled=True,
        camera_enabled=False,
        description=(
            "GPU de 4-6 GB. E4B-Q4_K_M (subido desde E2B: la familia E4B "
            "emite tool-calls de forma fiable — medido 67%+ vs ~0% en E2B-Q2), "
            "ctx 16K, VISIÓN ON, voz+STT ON (CPU). ~4.96 GB modelo + KV 16K -> "
            "~6.5 GB física. Primer perfil con acciones fiables."
        ),
        est_vram_mb=3360,
    ),
    "vram6": Profile(
        name="vram6",
        display_name="VRAM 6GB",
        context_size=16384,
        model_path=_E4B_Q4_K_M,
        mmproj_path=_MMPROJ_E4B,
        vision_enabled=True,
        rerank_enabled=True,
        parallel_tools=False,
        fact_extraction=False,
        server_running=True,
        voice_enabled=True,
        camera_enabled=False,
        description=(
            "PERFIL MÍNIMO FIABLE para 6 GB. E4B-Q4_K_M (familia E4B = "
            "tool-calling fiable, MEDIDO 4/4), ctx 16K, rerank ON, voz+STT ON "
            "(CPU). Con visión-lazy (router mode) el modelo residente carga "
            "~3.9 GB -> ~5.7 GB de VRAM total ocupada (entra en 6 GB). La "
            "visión se carga on-demand solo en turnos con imagen. Acciones "
            "confiables 4/4 medido."
        ),
        est_vram_mb=3900,  # text preset residente (lazy-vision); +mmproj on-demand
    ),
    "vram8": Profile(
        name="vram8",
        display_name="VRAM 8GB",
        context_size=16384,
        # 2026-05-21 PERF FIX: switched from UD-Q4_K_XL to standard Q4_K_M.
        # The Unsloth dynamic XL quant leaves ~2.3 GB of tensors CPU-mapped even
        # at ngl=99 (measured: CPU_Mapped 2288 MiB), which collapsed GENERATION
        # to ~11 tok/s. Standard Q4_K_M offloads fully to GPU and generates at
        # ~72 tok/s — a 6.6x speedup, same ~4.7 GB size, negligible quality
        # difference for tool-calling. This is what makes vram8 actually usable.
        model_path=_E4B_Q4_K_M,
        mmproj_path=_MMPROJ_E4B,
        vision_enabled=True,
        rerank_enabled=True,
        parallel_tools=True,
        fact_extraction=False,
        server_running=True,
        voice_enabled=True,
        camera_enabled=False,
        description=(
            "GPU de 8 GB (RTX 3060 Ti, 4060, 2080). E4B-Q4_K_M (descarga 100%% "
            "a GPU -> ~72 tok/s; el UD-Q4_K_XL dejaba 2.3 GB en CPU y caía a "
            "~11 tok/s), ctx 16K, VISIÓN ON, rerank ON, parallel tools ON, "
            "voz+STT ON (CPU). ~5 GB cargado con visión."
        ),
        est_vram_mb=5230,
    ),
    "vram12": Profile(
        name="vram12",
        display_name="VRAM 12GB",
        # ctx 16K (no 32K): el prefill de 32K era parte de la lentitud y el
        # agente rara vez usa >16K; 16K mantiene latencia baja con margen de KV.
        context_size=16384,
        # 26B-A4B (MoE) en vez de E4B: el E4B (4B params) NUNCA pasaba de ~7 GB
        # sin importar la VRAM — por eso "no usaba más de 7 GB". El 26B-A4B usa
        # ~13 GB en GPU, es 26B de calidad con ~4B activos (rápido), y genera
        # ~43 tok/s. Salto enorme de calidad aprovechando los 12-16 GB.
        model_path=_26B_Q3_K_XL,
        mmproj_path=_MMPROJ_26B,
        vision_enabled=True,
        rerank_enabled=True,
        parallel_tools=True,
        fact_extraction=True,
        server_running=True,
        voice_enabled=True,
        camera_enabled=False,
        description=(
            "GPU de 12-16 GB. 26B-A4B MoE UD-Q3_K_XL (26B de calidad, ~4B "
            "activos -> rápido; ~43 tok/s, usa ~13 GB en GPU), ctx 16K, VISIÓN "
            "ON, todo ON. Mucho más inteligente que E4B aprovechando la VRAM."
        ),
        est_vram_mb=13000,
    ),
    "vram16": Profile(
        name="vram16",
        display_name="VRAM 16GB+",
        context_size=16384,
        # 26B-A4B MoE, mismo modelo que vram12 (el Q3_K_XL ya aprovecha ~13 GB
        # con margen de KV/visión en 16 GB). Si el usuario configura un modelo
        # propio mayor en Settings, GEMMA4_MODEL_PATH lo sobreescribe.
        model_path=_26B_Q3_K_XL,
        mmproj_path=_MMPROJ_26B,
        vision_enabled=True,
        rerank_enabled=True,
        parallel_tools=True,
        fact_extraction=True,
        server_running=True,
        voice_enabled=True,
        camera_enabled=False,
        description=(
            "GPU de 16 GB+. 26B-A4B MoE UD-Q3_K_XL (~13 GB, ~43 tok/s, 26B de "
            "calidad con ~4B activos), ctx 16K, VISIÓN ON, todo ON. El máximo "
            "que aprovecha 16 GB sin OOM; modelo propio via Settings lo override."
        ),
        est_vram_mb=13000,
    ),
    "standby": Profile(
        name="standby",
        display_name="Standby",
        context_size=4096,  # irrelevante pero algo hay que poner
        model_path=None,
        mmproj_path=None,
        vision_enabled=False,
        rerank_enabled=False,
        parallel_tools=False,
        fact_extraction=False,
        server_running=False,
        voice_enabled=False,  # sin LLM no hay a quien hablarle
        camera_enabled=False,
        description=(
            "llama-server apagado. La GUI sigue viva (memory viewer, "
            "sessions, triggers, tool explorer non-LLM). El chat muestra "
            "'Server offline — switch profile to chat.' VRAM ~0. Voice OFF "
            "porque no hay LLM al que entregar el texto."
        ),
        est_vram_mb=0,
    ),
}

# Aliases de compatibilidad: nombres antiguos -> nuevo equivalente más cercano.
# Mantienen funcionando ~/.gemma4/active_profile.txt y profiles.json viejos,
# y cualquier código/test que pida "balanced" etc. set/get_active_profile y
# apply los resuelven vía _resolve_alias().
_LEGACY_ALIASES: dict[str, str] = {
    "performance": "vram16",
    "balanced_8gb": "vram8",
    "balanced": "vram6",
    "light": "vram4",
    # standby se mantiene con su nombre.
}


def _resolve_alias(name: str) -> str:
    """Mapea un nombre (posiblemente legacy) al nombre canónico vramN/standby."""
    return _LEGACY_ALIASES.get(name, name)


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
    """Sugiere perfil vramN segun la VRAM FISICA total detectada.

    VRAM fisica = (modelo cargado MEDIDO con visión-lazy/router-mode, es decir
    el preset TEXT residente por defecto) + WINDOWS_VRAM_RESERVE_MB (1.5 GB).
    Con router mode (default ON) la visión NO esta residente: se carga
    on-demand solo en turnos con imagen, asi que el footprint por defecto es
    menor y el modelo FIABLE (E4B) entra en menos VRAM. Numeros medidos
    (RTX 4060 Ti, E4B-Q4 text preset = 3.89 GB cargado -> ~5.4 GB fisica):

      >= 12 GB -> vram12   (E4B-Q6_K)
      >=  8 GB -> vram8    (E4B-UD-Q4_K_XL)
      >=  6 GB -> vram6    (E4B-Q4_K_M, FIABLE, ~5.4 GB fisica con lazy-vision)
                           <-- PERFIL MINIMO FIABLE para 6 GB
      >=  4 GB -> vram4    (E4B-Q4_K_M, mismo modelo fiable, ctx/flags mas
                           ajustados; ~5.4 GB con lazy-vision — apretado en 4 GB
                           real pero el operador prioriza fiabilidad)
      resto/None -> vram3  (E2B-Q4, mas rapido pero tool-calling INCONSISTENTE;
                           solo para hardware que no aguanta E4B)

    NB: vram16 (modelo del usuario) NO se auto-recomienda — opt-in.
    Si un perfil tiene su GGUF ausente, caemos al inmediato inferior.
    """
    if vram_mb is None:
        return "vram3"
    gb = int(vram_mb) / 1024.0

    def _model_ok(profile_name: str) -> bool:
        mp = PROFILES[profile_name].model_path
        if mp is None:  # vram16 usa el modelo del usuario; tratamos como ok
            return True
        try:
            return Path(mp).expanduser().is_file()
        except OSError:
            return False

    # De mayor a menor; el primero cuyo umbral pasa Y cuyo GGUF existe gana.
    ladder = [
        (12.0, "vram12"),
        (8.0, "vram8"),
        (6.0, "vram6"),
        (4.0, "vram4"),
        (0.0, "vram3"),
    ]
    for threshold, name in ladder:
        if gb >= threshold and _model_ok(name):
            return name
    return "vram3"


def get_active_profile() -> Profile:
    """Lee ~/.gemma4/active_profile.txt y devuelve el Profile correspondiente.

    Si el archivo no existe (primer arranque del usuario), detecta VRAM una
    vez y persiste el perfil recomendado. Asi la app arranca con el perfil
    correcto sin pedirle al usuario que vaya a Settings.

    Default fallback: vram4 (si no se puede detectar VRAM). Resuelve nombres
    legacy (balanced/light/...) escritos por versiones anteriores.
    """
    _DEFAULT = "vram4"
    if not ACTIVE_PROFILE_PATH.is_file():
        # Primera vez: detecta y persiste. Si falla, queda en el default sin
        # escribir nada (asi en la proxima ejecucion vuelve a intentar).
        try:
            vram_mb = detect_vram_mb()
            recommended = recommend_profile(vram_mb)
            set_active_profile(recommended)
            return _profile_with_overrides(PROFILES[recommended])
        except (OSError, ValueError):
            return PROFILES[_DEFAULT]
    try:
        name = ACTIVE_PROFILE_PATH.read_text(encoding="utf-8").strip().casefold()
    except OSError:
        return PROFILES[_DEFAULT]
    name = _resolve_alias(name)  # legacy "balanced" -> "vram6", etc.
    if name not in PROFILES:
        return PROFILES[_DEFAULT]
    return _profile_with_overrides(PROFILES[name])


def set_active_profile(name: str) -> None:
    """Persiste el nombre del perfil activo atomicamente.

    Acepta nombres canónicos (vramN/standby) y legacy (balanced/light/...),
    persistiendo siempre el canónico para que el archivo quede normalizado.
    """
    canonical = _resolve_alias(name)
    if canonical not in PROFILES:
        raise ValueError(f"unknown profile: {name!r} (valid: {PROFILE_NAMES})")
    atomic_write_text(ACTIVE_PROFILE_PATH, canonical)


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
        "context_size", "model_path", "mmproj_path", "vision_enabled",
        "rerank_enabled", "parallel_tools", "fact_extraction", "voice_enabled",
        "camera_enabled", "est_vram_mb", "display_name", "description",
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
    # Camera (future webcam VLM). Carried through so the runtime/UI can read
    # it; no model is wired yet, so this is informational today.
    os.environ["GEMMA4_CAMERA_PROFILE_ALLOWS"] = "true" if profile.camera_enabled else "false"

    # Vision (mmproj). Three cases:
    #   - vision OFF                -> "" (launcher omits --mmproj)
    #   - vision ON + profile.mmproj_path exists -> force it (self-contained
    #     profile; this is how the vramN profiles ship vision baked in)
    #   - vision ON + profile.mmproj_path None   -> respect the user's Settings
    #     value (legacy behavior; used by vram16 which rides the user's model)
    if not profile.vision_enabled:
        os.environ["GEMMA4_MMPROJ_PATH"] = ""
    elif profile.mmproj_path:
        candidate = Path(profile.mmproj_path).expanduser()
        if candidate.is_file():
            os.environ["GEMMA4_MMPROJ_PATH"] = str(candidate)
        else:
            # Declared but missing -> don't fabricate; fall back to "no vision"
            # so the server still starts (caller may warn). Better than OOM/crash.
            os.environ["GEMMA4_MMPROJ_PATH"] = ""
    # else (vision ON, mmproj_path None): leave GEMMA4_MMPROJ_PATH untouched.

    # Modelo: solo lo sobreescribimos si el perfil define uno Y el archivo existe.
    # Caso LIGHT con light_model_path inexistente: NO tocamos y dejamos que el
    # caller muestre warning amber. El agente seguira con el modelo principal.
    if profile.model_path:
        candidate = Path(profile.model_path).expanduser()
        if candidate.is_file():
            os.environ["GEMMA4_MODEL_PATH"] = str(candidate)
        # else: silencio. Caller (UI) debe verificar con light_model_missing().


def requires_server_restart(old: Profile | None, new: Profile) -> bool:
    """Decide si pasar de `old` a `new` requiere reiniciar llama-server.

    Solo los campos que el server consume al arrancar (flags del binario)
    fuerzan restart. Cambios "puramente del cliente Python" (parallel_tools,
    fact_extraction, voice_enabled, rerank_enabled) se aplican via env vars
    sin tocar el subprocess.

    Campos que fuerzan restart:
      - context_size       (-c <N>)
      - model_path         (-m <path>)
      - vision_enabled     (--mmproj / sin --mmproj)
      - server_running     (apagar/encender)

    Si `old is None` (primer apply de la sesion) y new.server_running=True,
    necesitamos arrancar; el caller debe llamar start(), no restart.

    Caso "ambos apagados" -> False (no hay server al que reiniciar).
    Caso "old apagado, new prendido" -> True (hay que start, contando como restart).
    Caso "old prendido, new apagado" -> True (hay que stop).
    """
    # Sin estado previo: tratamos como "necesita arrancar" si server_running.
    if old is None:
        return bool(new.server_running)
    # Ambos apagados: no hay restart que hacer.
    if not old.server_running and not new.server_running:
        return False
    # Toggle on/off del server: siempre cambio observable.
    if old.server_running != new.server_running:
        return True
    # Ambos prendidos: comparar solo los campos del binario.
    return (
        old.context_size != new.context_size
        or (old.model_path or "") != (new.model_path or "")
        or old.vision_enabled != new.vision_enabled
        or (old.mmproj_path or "") != (new.mmproj_path or "")
    )


def model_missing(profile_name: str) -> bool:
    """True si el perfil tiene model_path configurado pero el archivo no existe.

    Caller debe llamarlo antes de aplicar un perfil para decidir si mostrar
    warning amber + caer al modelo principal. profile_name acepta nombres
    canónicos o legacy. vram16 (model_path None) nunca está "missing".
    """
    name = _resolve_alias(profile_name)
    if name not in PROFILES:
        return False
    path = _profile_with_overrides(PROFILES[name]).model_path
    if not path:
        return False  # no configurado (vram16) -> usa default, no es "missing"
    try:
        return not Path(path).expanduser().is_file()
    except OSError:
        return True


# Compat: nombre viejo usado por la UI/launcher para el perfil de menor VRAM.
def light_model_configured() -> str | None:
    return _profile_with_overrides(PROFILES["vram4"]).model_path


def light_model_missing() -> bool:
    return model_missing("vram4")
