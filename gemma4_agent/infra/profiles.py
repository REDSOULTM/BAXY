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
usa para decisiones. Numeros vienen de docs/architecture/INFORME_ARQUITECTURA_6GB.md de
esta misma sesion de investigacion.
"""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..memory_pkg.state import atomic_write_json


# 2026-05-26: COLAPSADO A UN SOLO PERFIL (pedido del operador). vram4 (E2B-Q4)
# es el ÚNICO perfil operante — el target del producto: TODO (modelo + visión
# residente + KV + voz/STT en CPU) dentro de ≤4 GB de VRAM. Se eliminaron
# vram3/6/8/12/16: ya no hay selector ni auto-detección por VRAM. `standby` se
# conserva porque apaga llama-server y la UI lo necesita. Cualquier nombre viejo
# (vram3/6/8/.../performance/balanced/light) resuelve a vram4 vía _LEGACY_ALIASES
# para no romper un ~/.gemma4/active_profile.txt preexistente.
PROFILE_NAMES = ("vram4", "standby")

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
    # GPU layers to offload (llama.cpp -ngl). Default 99 = full GPU offload (the
    # GPU profiles). A CPU-fallback profile sets this to 0 → the model runs
    # entirely on CPU (0 VRAM), used when the GPU is saturated by a game / heavy
    # app so the assistant keeps responding WITHOUT competing for the GPU. The
    # llama-server command reads this (was hardcoded "99"). Design + sources:
    # docs/research/investigaciones_recibidas/6_estabilidad.md (Punto 4).
    n_gpu_layers: int = 99
    # Ola 2.4 RAM-frugality (perfection roadmap 2026-05-29): para el perfil CPU
    # (n_gpu_layers=0), limitar los threads + bajar la prioridad del proceso para
    # NO robarle CPU al juego que motivó el fallback. None = default de llama.cpp
    # (usa todos los cores) — solo el perfil CPU lo setea. Es un knob de RECURSOS,
    # no una lista por idioma. Verificado en la build (b9090+): -t y --prio existen;
    # --keep-alive/idle-unload NO -> no se promete unload-on-idle (regla #3).
    cpu_threads: int | None = None


# Defaults — copiados aqui para que sean editables sin tocar profiles.json.
# El usuario puede sobreescribir cualquier campo via Settings > Profiles.
# Paths default a los GGUF reales del repo. Numeros entre parentesis son
# VRAM cargada real medida en RTX 4060 Ti (idle ~1.2 GB incluido), CSV en
# documentacion/datos_crudos/vram_real_medida.csv. NO confundir con "delta
# del modelo" (peso del modelo vs idle Windows): el cargado es lo que el
# usuario ve en nvidia-smi y es el que cuenta para el budget.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent  # reorg 2026-05-28: infra/ es subdir
_E2B = _PROJECT_ROOT / "models" / "E2B"

# GGUF paths del ÚNICO perfil (vram4 = E2B-Q4). VRAM en comentarios = delta REAL
# de nvidia-smi sobre idle Windows (2.06 GB), medido 2026-05-20 en RTX 4060 Ti
# (scripts/measure_vram_profiles.py, flash-attn on, -ngl 99).
# 2026-05-26: se quitaron las constantes de E4B/26B (perfiles eliminados). Los
# GGUF siguen en disco (models/E4B, models/26B-A4B) por si se reintroduce un
# perfil vía profiles.json override o GEMMA4_MODEL_PATH — sólo se borró el
# código que ya no los referenciaba, no los archivos.
_E2B_Q4_K_M  = str(_E2B / "gemma-4-E2B-it-Q4_K_M.gguf")      # 2.16 novis / 3.36 +vis @4K


def _resolve_mmproj_path(model_dir: Path) -> str:
    """Elige el mmproj a usar, prefiriendo una variante CUANTIZADA si existe.

    Ola 2.3 (perfection roadmap H7, 2026-05-29): el research pedía mmproj Q8_0
    (~560 MiB vs ~940 del F16, -430 MiB de headroom en 4GB). VERIFICADO 2026-05-29:
    ese artefacto NO existe hoy — Unsloth solo publica F16/F32/BF16 y `llama-quantize`
    falla con "unsupported architecture: clip" (cuantización de mmproj es feature
    AÚN ABIERTO en llama.cpp, issue #18881). Así que HOY no hay ahorro real.

    Esta función deja el agente LISTO: cuando aparezca un mmproj-Q8_0 (oficial o
    cuando llama.cpp habilite clip-quantize), basta dejarlo en models/E2B/ y se usa
    automáticamente — sin tocar código. Orden de preferencia por tamaño/calidad
    (más chico primero, que es el objetivo del headroom; F16 es el default actual).
    Gate GEMMA4_MMPROJ_PREFER_QUANT=0 fuerza el F16 clásico. Si nada cuantizado
    existe, devuelve el F16 de siempre (0 cambio de comportamiento hoy).
    """
    default = model_dir / "mmproj-F16.gguf"
    prefer = (os.environ.get("GEMMA4_MMPROJ_PREFER_QUANT", "1") or "1").strip().casefold()
    if prefer in {"0", "false", "no", "off"}:
        return str(default)
    # Candidatos cuantizados, del más liviano al más pesado. Solo Q* (más chicas
    # que el F16). NO incluimos BF16/F32: el BF16 (~987 MiB) es MÁS grande que el
    # F16 (~940), elegirlo empeoraría el headroom. F16/F32 son el fallback, no una
    # "preferencia". Solo elegimos algo distinto al default si REALMENTE existe
    # en disco (no asumimos artefactos que no están — VERIFICADO: ninguno existe hoy).
    for name in ("mmproj-Q4_K_M.gguf", "mmproj-Q5_K_M.gguf", "mmproj-Q8_0.gguf"):
        cand = model_dir / name
        if cand.is_file():
            return str(cand)
    return str(default)


_MMPROJ_E2B  = _resolve_mmproj_path(_E2B)                    # vision encoder (~940 MiB F16 hoy)


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
    "vram4": Profile(
        name="vram4",
        display_name="VRAM 4GB",
        context_size=16384,
        # E2B-Q4_K_M (2026-05-25, DEFAULT para PC de 4 GB — pedido de RED: la app
        # debe entrar en ≤4 GB de VRAM con TODO funcionando a la vez). MEDIDO: el
        # ÚNICO Gemma 4 que mete modelo + VISIÓN RESIDENTE + KV simultáneos dentro de
        # 4 GB: 2.16 GB texto / 3.36 GB con visión (vs E4B-IQ3_XXS 4.78 GB con visión,
        # que se pasa; E4B no entra en 4 GB ni en su cuant más baja). Tool-calling
        # 9/12=75% con los fixes de hoy (subió desde ~0% histórico; las 2 fallas son
        # "narra la función como texto" → el forced-tool-retry las rescata en prod).
        # Trade-off aceptado: -16pp de tool-calling vs E4B a cambio de TODO en 4 GB.
        # Quien tenga >4 GB usa vram6 (E4B-Q4, 91%). Ver project_tool_calling_weak_models.
        model_path=_E2B_Q4_K_M,
        mmproj_path=_MMPROJ_E2B,
        vision_enabled=True,
        rerank_enabled=False,
        parallel_tools=False,
        fact_extraction=False,
        server_running=True,
        voice_enabled=True,
        camera_enabled=False,
        description=(
            "GPU de 4 GB (DEFAULT). E2B-Q4_K_M: TODO en ≤4 GB — modelo + VISIÓN "
            "residente + KV = 3.36 GB medido. Voz+STT ON (CPU, 0 VRAM). ctx 16K. "
            "Tool-calling 75% (forced-retry lo sube). El único Gemma 4 que entra "
            "completo en 4 GB; para tool-calling 91% con >4 GB usá vram6 (E4B)."
        ),
        est_vram_mb=3360,
    ),
    "cpu": Profile(
        name="cpu",
        display_name="CPU (GPU ocupada)",
        context_size=16384,
        # Mismo modelo que vram4 (E2B-Q4) pero TODO en CPU (n_gpu_layers=0): 0 VRAM.
        # Para cuando el usuario JUEGA o corre algo pesado y la GPU está saturada:
        # el asistente sigue respondiendo (más lento, usable para respuestas cortas)
        # SIN competir por la GPU — que queda libre para el juego. Visión OFF (mmproj
        # no se carga: ahorra RAM y en CPU es muy pesada). Voz+STT siguen ON (Piper/
        # Whisper corren en CPU, 0 VRAM). Diseño SWITCH (no 2º server paralelo) porque
        # el target real es laptop 4GB-VRAM con ~8GB RAM, donde NO entran dos modelos.
        # Fuente: docs/research/investigaciones_recibidas/6_estabilidad.md (Punto 4).
        model_path=_E2B_Q4_K_M,
        mmproj_path=None,
        vision_enabled=False,
        rerank_enabled=False,
        parallel_tools=False,
        fact_extraction=False,
        server_running=True,
        voice_enabled=True,
        camera_enabled=False,
        n_gpu_layers=0,
        # RAM-frugality: 4 threads + prioridad baja (abajo en el command builder)
        # para no saturar la CPU mientras el usuario juega. Override GEMMA4_CPU_THREADS.
        cpu_threads=4,
        description=(
            "Fallback CPU para GPU ocupada (juego / app pesada). E2B-Q4 en CPU "
            "(-ngl 0): 0 VRAM, ~2 GB RAM. Respuestas más lentas pero el asistente "
            "no pelea por la GPU (queda libre para el juego). Visión OFF. Voz+STT "
            "siguen (CPU). Pensado para auto-activarse al detectar la GPU saturada "
            "y volver a vram4 al liberarse."
        ),
        est_vram_mb=0,
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

# Aliases de compatibilidad: TODOS los nombres viejos -> vram4 (el único perfil).
# Mantienen funcionando un ~/.gemma4/active_profile.txt o profiles.json escrito
# por una versión anterior (que pudo persistir vram3/6/8/12/16 o performance/
# balanced/light). set/get_active_profile y apply los resuelven vía
# _resolve_alias(). `standby` se mantiene con su nombre (sigue existiendo).
_LEGACY_ALIASES: dict[str, str] = {
    "performance": "vram4",
    "balanced_8gb": "vram4",
    "balanced": "vram4",
    "light": "vram4",
    "vram3": "vram4",
    "vram6": "vram4",
    "vram8": "vram4",
    "vram12": "vram4",
    "vram16": "vram4",
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


def has_usable_cuda_gpu() -> bool:
    """¿Hay una GPU NVIDIA con driver usable (CUDA) en esta máquina?

    Ola 2.1 (perfection roadmap 2026-05-29): el perfil `vram4` asume el binario
    `llama-server` CUDA-only. En una máquina SIN NVIDIA (laptop con iGPU Intel/AMD
    o sin GPU dedicada) ese binario NO arranca. Necesitamos distinguir "hay CUDA"
    de "no hay" para auto-caer al perfil `cpu` en vez de fallar en el boot.

    Distinto de detect_vram_mb(): esa también detecta AMD (rocm) y devuelve MB;
    acá sólo nos importa NVIDIA-con-driver, que es lo que el binario CUDA exige.
    `nvidia-smi` responde 0 SÓLO si hay driver NVIDIA cargado -> señal fiable.

    Override: GEMMA4_LLAMA_GPU_VENDOR fuerza la decisión sin probar hardware:
      - "cuda"        -> True  (forzar GPU, p.ej. binario CUDA presente seguro)
      - "cpu"/"vulkan"/"hip" -> False (forzar el camino sin-CUDA / perfil cpu)
    """
    vendor = (os.environ.get("GEMMA4_LLAMA_GPU_VENDOR") or "").strip().casefold()
    if vendor == "cuda":
        return True
    if vendor in {"cpu", "vulkan", "hip", "rocm", "none"}:
        return False
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=3, check=False,
        )
        return result.returncode == 0 and bool(result.stdout.strip())
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


# Reserva fija de VRAM para Windows/WDDM + driver buffers + headroom CUDA.
# El informe de auditoria externa (Bloque F1, item I1 #10) cita evidencia
# anecdotica de foros Microsoft / Tom's Hardware de 0.6-1.2 GB para dwm.exe
# mas 150-400 MB para buffers de driver. Reservamos 1.5 GB como cifra
# conservadora para que un usuario con 6 GB fisicos y Chrome abierto NO
# sufra OOM al arrancar el server.
WINDOWS_VRAM_RESERVE_MB = 1500


def recommend_profile(vram_mb: int | None) -> str:
    """Recomienda el perfil de arranque según el hardware.

    2026-05-26: el sistema multi-perfil se colapsó a un solo perfil GPU (vram4 =
    E2B-Q4, TODO en ≤4 GB). Ya no hay escalera por VRAM. `vram_mb` se conserva en
    la firma (callers existentes lo pasan; la UI muestra la VRAM detectada como
    dato informativo) pero no influye en la decisión entre los perfiles GPU.

    Ola 2.1 (perfection roadmap 2026-05-29): si NO hay GPU NVIDIA usable (CUDA),
    el binario `vram4` (CUDA-only) no arrancaría -> recomendamos el perfil `cpu`
    (E2B-Q4 en CPU, 0 VRAM, visión OFF) para que el agente FUNCIONE en laptops
    sin NVIDIA en vez de fallar en el boot. Esto NO afecta a usuarios con NVIDIA
    (siguen en vram4). Gate GEMMA4_NO_GPU_AUTOCPU=0 desactiva la auto-caída (vuelve
    al comportamiento viejo: siempre vram4) para diagnóstico.
    """
    autocpu = (os.environ.get("GEMMA4_NO_GPU_AUTOCPU", "1") or "1").strip().casefold()
    if autocpu not in {"0", "false", "no", "off"} and not has_usable_cuda_gpu():
        return "cpu"
    return "vram4"


def get_active_profile() -> Profile:
    """Lee ~/.gemma4/active_profile.txt y devuelve el Profile correspondiente.

    Si el archivo no existe (primer arranque del usuario), detecta VRAM una
    vez y persiste el perfil recomendado. Asi la app arranca con el perfil
    correcto sin pedirle al usuario que vaya a Settings.

    Default fallback: vram4 (si no se puede detectar VRAM). Resuelve nombres
    legacy (balanced/light/...) escritos por versiones anteriores.

    Override GEMMA4_DEFAULT_PROFILE (2026-05-23, pedido de RED): si está seteado
    a un perfil válido, ese es el default en el PRIMER arranque (en vez de
    auto-detectar por VRAM y recomendar el más grande). Opt-in -> no afecta a
    otros usuarios (multi-usuario universal). NO pisa un active_profile.txt ya
    existente (el usuario manda si ya eligió). Sirve para fijar vram4 default
    aunque la GPU tenga 16 GB.
    """
    _DEFAULT = "vram4"
    _env_default = (os.environ.get("GEMMA4_DEFAULT_PROFILE") or "").strip().casefold()
    if _env_default:
        _env_default = _resolve_alias(_env_default)
        if _env_default in PROFILES:
            _DEFAULT = _env_default
    if not ACTIVE_PROFILE_PATH.is_file():
        # Si hay override de default, respetarlo y persistirlo (no auto-detectar).
        if _env_default and _env_default in PROFILES:
            # Ola 2.1 GUARD: un default forzado a un perfil GPU (vram4) NO arranca
            # en una máquina sin NVIDIA (binario CUDA-only). El código garantiza
            # su precondición (CLAUDE.md #5): caemos a 'cpu' aunque el default sea
            # vram4, para no fallar en el boot. Respeta el gate y el override de
            # vendor (has_usable_cuda_gpu los honra). Un default no-GPU (standby/
            # cpu) se respeta tal cual.
            _gpu_default = _env_default == "vram4"
            _autocpu = (os.environ.get("GEMMA4_NO_GPU_AUTOCPU", "1") or "1").strip().casefold()
            if (_gpu_default and _autocpu not in {"0", "false", "no", "off"}
                    and not has_usable_cuda_gpu()):
                try:
                    set_active_profile("cpu")
                except Exception:
                    pass
                return _profile_with_overrides(PROFILES["cpu"])
            try:
                set_active_profile(_env_default)
            except Exception:
                pass
            return _profile_with_overrides(PROFILES[_env_default])
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
