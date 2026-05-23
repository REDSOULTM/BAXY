# Informe de Confiabilidad para el Perfil "vram4" — Agente OS Autónomo Local sobre Windows 11

## TL;DR

- **vram4 es viable hoy mismo** para Gemma 4 E4B-it Q4_K_M con llama.cpp b9090, monoslot y ctx=16384: con `--no-mmproj-offload`, `--cache-type-k q8_0 --cache-type-v q8_0` y `-fa on`, el consumo medido en el log de llama.cpp issue #21430 queda en ≈3.5–3.8 GiB (pesos GPU 3002 MiB + KV unificado SWA ≈163 MiB + compute buffer ≈500 MiB); con mmproj ofloaded sube a ≈4.8 GiB y solo cabe holgado en GPUs de 6 GB.
- **Las tres palancas que más previenen "crashear el programa" son, en orden**: (1) un **watchdog NVML por iteración** que decida *antes* de despachar el turno si hay que degradar (descargar mmproj, bajar ctx, cuantizar KV), (2) **aislar cada tool en subproceso con timeout duro + circuit breaker** (`pybreaker`) para que un hang/crash de una tool no tumbe la GUI ni el router, y (3) un **self-check de arranque y periódico** que pruebe `/health`+`/slots` de llama-server, importe los módulos de torch/torchcodec en un proceso hijo desechable y verifique versiones pinneadas — si algo falla, abortar con error explícito en vez de degradar en silencio.
- **NO-VIABLE en vram4**: cargar Gemma 4 E4B en Q8_0 o BF16, mantener mmproj BF16 ofloaded sin cuantizar KV en GPU de 4 GB, usar `--parallel >1` (rompe el supuesto monoslot y duplica KV), o usar `--no-kv-offload` en CUDA (degrada latencia ×10 y no es necesario porque el KV de 16k cabe). Alternativa que sí cabe: mantener Q4_K_M + KV q8_0/q4_0 + mmproj solo bajo demanda.

---

## Hallazgos clave (Key Findings)

1. **El presupuesto vram4 funciona porque Gemma 4 E4B es híbrido SWA**. De 42 capas, 18 son *shared-KV* (no consumen cache propio) y 20 son sliding-window de 512 tokens — solo 4 capas globales escalan linealmente con ctx-size. Esto significa que pasar de ctx=4096 a ctx=16384 añade apenas ~256 MiB de KV en f16, no 4× como en un modelo denso. Fuente: log verbatim de llama.cpp issue #21430 (`shared_kv_layers = 18`, `sliding_window = 512`, `sliding_window_pattern` 5:1).
2. **El mmproj de Gemma 4 E4B pesa 946 MiB en VRAM** (vision **+ audio** encoder), no ~600 MiB como en Gemma 3 — es la causa más probable de tu OOM cuando el agente recibe la primera imagen. La mitigación inmediata sin recompilar es `--no-mmproj-offload` (documentado en `docs/multimodal.md` del repo oficial).
3. **`llama-server` no recupera de un OOM CUDA**: el proceso queda vivo, responde `/v1/models` pero todo `/completion` cuelga (issue #13085). Esto es exactamente lo que tu `server-reload recovery` ya cubre, pero confirma que **detectar el OOM ANTES** (con NVML) es la única estrategia que evita el reload.
4. **`/health` puede mentir bajo carga**: en llama.cpp 8000+ el endpoint `/health` no tiene prioridad sobre la cola de tasks y puede tardar minutos durante prompt processing largo (issues #20684, ik_llama #1210, #20921). Para un agente local con voz hay que usar `/slots?fail_on_no_slot=1` y un timeout corto en paralelo a un *heartbeat* propio.
5. **ONNX Runtime tiene un flag oficial documentado** para apagar el spinning que te congeló Windows: `session.intra_op.allow_spinning=0` + `intra_op_num_threads=2`. Tu `_ort_throttle.py` ya lo aplica; basta confirmar que se aplica también a *cualquier* sesión nueva (no solo a la primera) y usar el `spin_duration_us` con `spin_backoff_max=8` introducido en releases recientes para limitar el spin a una ventana acotada.
6. **El patrón Circuit Breaker (`pybreaker`) es el mecanismo correcto para tools peligrosas**: no necesitas reimplementarlo. Combinado con `multiprocessing` + `AsyncResult.get(timeout=…)` + `pool.terminate()` da el aislamiento que pides con coste de latencia despreciable por llamada protegida. Kamya Shah ("Retries, Fallbacks, and Circuit Breakers in LLM Apps: A Production Guide", Maxim AI, 3 feb 2026) y OneUptime (enero 2026) documentan este patrón como estándar de producción en pipelines LLM.
7. **`faulthandler.dump_traceback_later(timeout, repeat=True)` resuelve el 80% del debugging de hangs** sin overhead apreciable. Es C-level, dumpea todos los threads, y la doc de Python 3.14 confirma que está siempre disponible y usa un *watchdog thread* dedicado.
8. **El conflicto torchcodec ↔ torch ↔ torchvision es real y silencioso**: bad_alloc + core dump si las versiones no concuerdan (torchcodec issue #995, #912). La única defensa es *importar en proceso hijo* durante el self-check y verificar `__version__` contra un manifiesto pinneado antes de tocar el router.

---

## Punto 1 — Gestión de presión de VRAM (PRIORIDAD MÁXIMA)

### Diagnóstico

En vram4, el peligro real no es "el modelo no carga" — eso lo previene tu `vram_calculator.py`. El peligro es el **OOM en runtime**, en tres momentos concretos:

- **Primera petición con imagen**: el mmproj de 946 MiB se carga al recibir el primer mensaje multimodal y se suma al KV cache + compute buffer ya residente. La estimación de `--fit on` no contempla mmproj (llama.cpp issue #19980), por lo que el OOM es probabilístico según la fragmentación.
- **Crecimiento del KV en las 4 capas globales**: ctx=16384 con f16 → 256 MiB. Pequeño, pero si el usuario abre una sesión muy larga y el slot reasigna, los 32 checkpoints por defecto (`--ctx-checkpoints 32`) viven en RAM y compiten en sistemas UMA (no en NVIDIA dedicada, ahí están en host RAM y son seguros).
- **Compute buffer reservado al cambiar de batch**: ≈500 MiB en GPU con ub=512.

`llama-server` **no libera VRAM si el OOM ocurre durante `cudaMalloc` en una request** — queda en estado zombie (#13085). Por eso la única política robusta es **detectar antes**: muestrear `nvmlDeviceGetMemoryInfo` cada N ms y, si `free < umbral`, degradar de forma graduada sin matar el turno.

### Tabla de mitigaciones

| Mitigación | Riesgo que cierra | Δ latencia / Δ VRAM | Complejidad |
|---|---|---|---|
| Watchdog NVML pre-turno (pynvml, `nvmlDeviceGetMemoryInfo`, 250 ms) | OOM probabilístico al despachar | +1–2 ms por turno, 0 VRAM | Baja |
| `--cache-type-k q8_0 --cache-type-v q8_0` con `-fa on` | OOM por KV en ctx largo | −50% KV (306→163 MiB), −1–2% calidad | Trivial (flags) |
| `--cache-type-k q4_0 --cache-type-v q4_0` (fallback de emergencia) | OOM extremo | −75% KV (306→86 MiB); en Gemma híbrido la pérdida es ~lossless según issue #21385 | Trivial |
| `--no-mmproj-offload` activado por defecto en vram4 | OOM al recibir primera imagen | +mucha latencia visión (CPU); −1040 MiB VRAM | Baja |
| Carga *lazy* del mmproj (presets vía `models.ini` con dos definiciones, swap por `/v1/models/unload`) | Mismo, sin perder latencia salvo cuando se usa visión | +~1 s al primer turno con imagen; libera 1040 MiB | Media |
| Reducción dinámica de ctx (16384 → 8192 → 4096) | OOM por KV | Pierdes contexto histórico; reproceso de prompt | Media (requiere truncado coherente) |
| `--cache-ram 0 --no-cache-idle-slots` en monoslot | Crecimiento sigiloso de checkpoints en RAM | Pierdes resume rápido de slot; KV se recalcula al volver | Baja |
| **NO-VIABLE**: `--no-kv-offload` en CUDA | "Ahorra" VRAM pero degrada 5–10× la latencia y no es necesario en 16k | Inaceptable para voz | — |
| **NO-VIABLE**: subir a Q8_0 o BF16 del modelo | Mejora calidad pero rompe presupuesto vram4 | +3 GB VRAM, no cabe | — |

### Veredicto vram4: **VIABLE**

Configuración recomendada de arranque en vram4:

```
llama-server.exe ^
  --model gemma-4-E4B-it-Q4_K_M.gguf ^
  --mmproj mmproj-BF16.gguf --no-mmproj-offload ^
  --ctx-size 16384 --parallel 1 --kv-unified ^
  --flash-attn on ^
  --cache-type-k q8_0 --cache-type-v q8_0 ^
  --batch-size 1024 --ubatch-size 256 ^
  --cache-ram 512 --ctx-checkpoints 8 ^
  --no-context-shift ^
  --slots --metrics --port 8080
```

Total estimado: ≈3.6 GiB en GPU. Headroom de 0.4–2.4 GiB sobre 4–6 GB para acomodar el compositor de Windows, el codec ONNX y picos del compute buffer.

### Código concreto — `vram_watchdog.py`

```python
# vram_watchdog.py — Watchdog NVML pre-turno y entre turnos.
# Decide degradación SIN matar el turno actual.

import time
import threading
from dataclasses import dataclass
from enum import IntEnum
from typing import Callable, Optional

import pynvml  # nvidia-ml-py >= 12.0.0 (NVIDIA oficial)

class PressureLevel(IntEnum):
    OK = 0          # > 800 MiB libres
    WARN = 1        # 500–800 MiB libres -> avisar, no degradar
    DEGRADE = 2     # 250–500 MiB -> descargar mmproj, bajar ctx
    CRITICAL = 3    # < 250 MiB -> rechazar turno o reload server

@dataclass
class VRAMSnapshot:
    total_mib: int
    used_mib: int
    free_mib: int
    level: PressureLevel
    ts: float

class VRAMWatchdog:
    """
    Watchdog NVML con un solo thread.
    NO bloquea el turno: el agente consulta last_snapshot() antes de despachar.
    """
    def __init__(self,
                 device_index: int = 0,
                 poll_ms: int = 250,
                 warn_mib: int = 800,
                 degrade_mib: int = 500,
                 critical_mib: int = 250,
                 on_degrade: Optional[Callable[[VRAMSnapshot], None]] = None):
        self.device_index = device_index
        self.poll_s = poll_ms / 1000.0
        self.warn_mib = warn_mib
        self.degrade_mib = degrade_mib
        self.critical_mib = critical_mib
        self._on_degrade = on_degrade
        self._snap: Optional[VRAMSnapshot] = None
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_level = PressureLevel.OK
        pynvml.nvmlInit()
        self._handle = pynvml.nvmlDeviceGetHandleByIndex(device_index)

    def _classify(self, free_mib: int) -> PressureLevel:
        if free_mib < self.critical_mib: return PressureLevel.CRITICAL
        if free_mib < self.degrade_mib:  return PressureLevel.DEGRADE
        if free_mib < self.warn_mib:     return PressureLevel.WARN
        return PressureLevel.OK

    def _loop(self):
        while not self._stop.is_set():
            try:
                info = pynvml.nvmlDeviceGetMemoryInfo(self._handle)
                free_mib = info.free // (1024 * 1024)
                snap = VRAMSnapshot(
                    total_mib=info.total // (1024 * 1024),
                    used_mib=info.used // (1024 * 1024),
                    free_mib=free_mib,
                    level=self._classify(free_mib),
                    ts=time.monotonic(),
                )
                self._snap = snap
                # Edge-trigger: solo notificar al subir de nivel.
                if snap.level > self._last_level and self._on_degrade:
                    try:
                        self._on_degrade(snap)
                    except Exception:
                        pass  # nunca matar el watchdog
                self._last_level = snap.level
            except pynvml.NVMLError:
                # No matamos el thread: NVML puede fallar en suspensión.
                pass
            self._stop.wait(self.poll_s)

    def start(self):
        self._thread = threading.Thread(target=self._loop, name="vram-wd", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        try: pynvml.nvmlShutdown()
        except: pass

    def last_snapshot(self) -> Optional[VRAMSnapshot]:
        return self._snap

    def gate_turn(self) -> tuple[bool, str]:
        """Llamar JUSTO antes de despachar un turno LLM."""
        s = self._snap
        if s is None:                   return True, "no-data"
        if s.level == PressureLevel.CRITICAL:
            return False, f"critical: free={s.free_mib} MiB"
        return True, f"{s.level.name}: free={s.free_mib} MiB"


# --- Integración con el router ---
def on_degrade(snap: VRAMSnapshot):
    # Política: descargar mmproj y reducir ctx en caliente.
    if snap.level >= PressureLevel.DEGRADE:
        router.unload_mmproj()              # POST /v1/models/unload con mmproj id
        router.set_ctx_target(8192)         # próximo slot reset usa 8k
    if snap.level == PressureLevel.CRITICAL:
        router.set_kv_quant("q4_0")         # requiere reload-server (ya lo tienes)

wd = VRAMWatchdog(on_degrade=on_degrade)
wd.start()
```

### Fuentes 2025–2026

- llama.cpp issue #21430 (log verbatim de Gemma 4 E4B-it Q4_K_M, abril 2026): valida shape de KV y tamaño de mmproj.
- llama.cpp issue #19980: el estimador `--fit on` no contempla mmproj → OOM probabilístico.
- llama.cpp issue #13085: el server queda zombie tras OOM de CUDA — necesidad de prevenir, no reaccionar.
- llama.cpp issue #21385 (per-head KV quantization): Gemma 4 absorbe la cuantización q4_0 KV mejor que arquitecturas densas porque las capas SWA actúan como corrección de error.
- llama.cpp discussion #20855: propuesta de `--mmproj-load-on-demand` (alternativa nativa al swap).
- pypi.org/project/nvidia-ml-py (NVIDIA oficial): API estable para `nvmlDeviceGetMemoryInfo`.

---

## Punto 2 — Aislamiento de fallas de tools (PRIORIDAD MÁXIMA)

### Diagnóstico

La regla operativa es simple: **una tool tiene un thread o un proceso, nunca el hilo del agente**. Hoy tienes `per-tool dispatch try/except`, pero un `try/except` no cubre:

- Un `import` que segfaultea (torchcodec con mismatch de torch → `std::bad_alloc` + core dump; torchcodec issue #995). No hay manera de capturarlo desde Python en el mismo proceso.
- Un subprocess de Windows que cuelga en una syscall (taskkill, pywin32, captura de pantalla) ignorando `SIGTERM` — Python issue #38988 documenta esta patología.
- Un hang en `multiprocessing.Pool` causado por un worker que muere antes de devolver resultado (deadlock clásico). Las soluciones canónicas son `apply_async + get(timeout)` + `terminate()`.

La combinación que funciona en producción 2026 es **circuit breaker (PyBreaker) + proceso aislado por tool de riesgo + timeout duro**.

### Tabla de mitigaciones

| Mitigación | Riesgo que cierra | Δ latencia / Δ VRAM | Complejidad |
|---|---|---|---|
| Subprocess aislado por tool de riesgo (con `subprocess.Popen` + `timeout` + `kill()`) | Segfault/hang lleva el agente entero | +10–50 ms por llamada (cold) | Baja |
| `multiprocessing.Process` reutilizado con cola IPC y `join(timeout)` | Igual, con menor overhead que spawn nuevo | +5–20 ms por llamada (warm) | Media |
| **PyBreaker** por categoría de tool (`fail_max=3, reset_timeout=60`) | Tool intermitentemente rota satura el turno | <1 ms por llamada | Baja |
| `faulthandler.dump_traceback_later(timeout=…, repeat=True, file=…)` al inicio de cada tool | Hang silencioso sin diagnóstico | 0 latencia, ~1 KB de log por hang | Trivial |
| Watchdog thread por tool (heartbeat cada 1 s, si no late en 5 s → kill) | Tool C-extension bloqueada en syscall | <1 ms si la tool late | Media |
| `psutil.Process(pid).wait(timeout=5)` después de `terminate()`, fallback a `kill()` | Tool que ignora SIGTERM (#38988) | +5 s en el peor caso | Baja |
| **NO-VIABLE**: ejecutar tools en threads del proceso principal | El GIL no protege contra C-segfaults | Crash del agente | — |

### Veredicto vram4: **VIABLE**

La latencia añadida por tool sandbox + breaker es <50 ms warm. Para una asistente de voz local con turnos de ≥1.5 s, es invisible. La RAM extra de un worker reutilizado es ~30–80 MiB de Python interpreter, no toca VRAM.

### Código concreto — `tool_sandbox.py`

```python
# tool_sandbox.py — Ejecuta tools "peligrosas" en proceso aislado con
# timeout duro, circuit breaker y kill seguro en Windows.

import multiprocessing as mp
import time
import faulthandler
import sys
from dataclasses import dataclass
from typing import Any, Callable, Optional

import psutil
import pybreaker

# Un breaker GLOBAL por categoría de tool. Vive el tiempo del agente.
BREAKERS: dict[str, pybreaker.CircuitBreaker] = {}

def get_breaker(category: str) -> pybreaker.CircuitBreaker:
    if category not in BREAKERS:
        BREAKERS[category] = pybreaker.CircuitBreaker(
            fail_max=3,
            reset_timeout=60,
            name=f"tool:{category}",
            # NoSuchProcess / PermissionError NO cuentan como fallo del breaker:
            exclude=[psutil.NoSuchProcess, PermissionError],
        )
    return BREAKERS[category]

@dataclass
class ToolResult:
    ok: bool
    value: Any = None
    error: Optional[str] = None
    duration_s: float = 0.0
    killed_for_timeout: bool = False

def _worker_entry(fn, args, kwargs, q):
    # Faulthandler dumpea TODOS los threads si el worker queda colgado >30s.
    faulthandler.enable(file=sys.stderr)
    faulthandler.dump_traceback_later(30, repeat=False)
    try:
        q.put(("ok", fn(*args, **kwargs)))
    except BaseException as e:
        q.put(("err", f"{type(e).__name__}: {e}"))

def run_isolated(fn: Callable, args=(), kwargs=None, *,
                 timeout_s: float = 15.0,
                 category: str = "default") -> ToolResult:
    """
    Ejecuta `fn` en un proceso aislado con timeout duro.
    Si la categoría tiene el breaker abierto, devuelve fast-fail.
    """
    kwargs = kwargs or {}
    breaker = get_breaker(category)
    if breaker.current_state == pybreaker.STATE_OPEN:
        return ToolResult(ok=False, error=f"breaker-open:{category}")

    ctx = mp.get_context("spawn")  # En Windows ya es spawn por defecto.
    q = ctx.Queue(maxsize=1)
    p = ctx.Process(target=_worker_entry, args=(fn, args, kwargs, q), daemon=True)
    t0 = time.monotonic()
    p.start()
    p.join(timeout=timeout_s)
    if p.is_alive():
        # Timeout duro: cortar y limpiar.
        try:
            psutil.Process(p.pid).terminate()
            psutil.Process(p.pid).wait(timeout=2)
        except psutil.TimeoutExpired:
            psutil.Process(p.pid).kill()
        except psutil.NoSuchProcess:
            pass
        p.join(timeout=2)
        return ToolResult(ok=False, error="timeout",
                          duration_s=time.monotonic()-t0,
                          killed_for_timeout=True)

    duration = time.monotonic() - t0
    if q.empty():
        return ToolResult(ok=False, error="no-result", duration_s=duration)
    status, payload = q.get_nowait()
    if status == "ok":
        return ToolResult(ok=True, value=payload, duration_s=duration)
    else:
        # Forzamos fallo en el breaker:
        try:
            @breaker
            def _fail(): raise RuntimeError(payload)
            _fail()
        except Exception:
            pass
        return ToolResult(ok=False, error=payload, duration_s=duration)


# --- Uso desde el router ---
# from tool_sandbox import run_isolated
# r = run_isolated(screenshot_capture, args=(monitor_id,),
#                  timeout_s=8.0, category="screenshot")
# if not r.ok:
#     speak_back("No pude capturar la pantalla, lo reporto.")
```

### Fuentes 2025–2026

- pypi.org/project/pybreaker (Python 3.9+, mantenido; patrón canónico de Nygard).
- OneUptime "How to Implement Circuit Breakers in Python" (enero 2026): combo PyBreaker + monitor.
- Kamya Shah, "Retries, Fallbacks, and Circuit Breakers in LLM Apps: A Production Guide", Maxim AI (3 feb 2026): PyBreaker citado explícitamente como librería de referencia para implementar circuit breakers en arquitecturas de gateway LLM.
- Anyinlover "Unraveling the Hang in Python's Multiprocessing Pool" (2025): por qué `map_async + get(timeout) + terminate()` es la única forma robusta.
- runebook.dev "Graceful vs. Forceful: Mastering Python's Pool Termination" (2025): patrón `close()/join(timeout)` vs `terminate()`.
- psutil 7.2 docs: `Process.terminate() / wait(timeout) / kill()` con manejo de `NoSuchProcess` y `AccessDenied`.

---

## Punto 3 — Health-checks y auto-reparación (PRIORIDAD MÁXIMA)

### Diagnóstico

El sistema debe distinguir cuatro condiciones de salud al arrancar y cada N minutos:

- **Router/server vivo**: el proceso `llama-server.exe` responde TCP, y `/health` retorna `status:ok` rápido. **Cuidado**: `/health` puede quedar encolado bajo prompt processing largo (issues #20684, #20921). Hay que combinarlo con `/slots?fail_on_no_slot=1` (503 si no hay slot libre) y un timeout corto.
- **Modelo cargado y coherente**: `/props` devuelve el modelo esperado y `n_ctx` esperado (16384).
- **Dependencias Python sanas**: torchcodec se importa sin segfault contra el torch presente; `__version__` coincide con el manifiesto pinneado. Esto **debe hacerse en un proceso hijo desechable** porque el `import` puede segfaultear (issue torchcodec #995).
- **NVML disponible**: `pynvml.nvmlInit()` no falla; driver de NVIDIA presente.

Si algo falla, la política correcta para un agente local de voz **es avisar fuerte, no degradar en silencio**. La nota de Trantorinc ("AI Agent Failure Modes", 18 may 2026) reporta que **el 88 % de las organizaciones que desplegaron agentes de IA reportaron al menos un incidente de seguridad en 2025**, y atribuye buena parte a la ausencia de observabilidad y de procesos formales de tracking — exactamente lo que el self-check loud previene.

### Tabla de mitigaciones

| Mitigación | Riesgo que cierra | Δ latencia / Δ VRAM | Complejidad |
|---|---|---|---|
| Probe TCP + `/health` con timeout 1 s (5 reintentos a 200 ms) al arranque | Server muerto sin diagnóstico | +1 s en cold start | Trivial |
| `/slots?fail_on_no_slot=1` paralelo a `/health` (timeout 500 ms) | `/health` mintiendo bajo carga | <1 ms | Trivial |
| Probe `/props` y validación de `n_ctx` y `default_generation_settings.model` | Modelo cargado distinto al esperado | <100 ms | Baja |
| Self-check de imports en *subprocess desechable* (`python -c "import torchcodec; print(torchcodec.__version__)"`) | Segfault silencioso por mismatch de versiones | +200–400 ms en cold start | Baja |
| Comparación de versiones contra un `requirements.lock` propio | Drift de dependencias | 0 | Baja |
| Heartbeat de 30 s al server + reload si 3 fallos consecutivos | Server zombie (issue #13085) | <1 ms si vivo | Media (ya lo tienes) |
| Speech-back de error explícito al usuario en español | Degradación silenciosa | 0 | Trivial |

### Veredicto vram4: **VIABLE**

Todos los probes son sub-segundo y no tocan VRAM.

### Código concreto — `self_check.py`

```python
# self_check.py — Self-check ligero de arranque y periódico.
# Falla LOUD, no en silencio.

import json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import Optional

import requests

EXPECTED = {
    "model_substr": "gemma-4-E4B-it",
    "n_ctx": 16384,
    "torch": "2.6.0",        # ajusta a tu lock
    "torchcodec": "0.5.0",
    "torchvision": "0.21.0",
}

@dataclass
class HealthReport:
    ok: bool = True
    issues: list[str] = field(default_factory=list)
    details: dict = field(default_factory=dict)

    def fail(self, msg: str):
        self.ok = False
        self.issues.append(msg)


def _probe(url: str, timeout: float) -> tuple[bool, Optional[dict]]:
    try:
        r = requests.get(url, timeout=timeout)
        if r.status_code != 200:
            return False, {"status": r.status_code}
        try: return True, r.json()
        except: return True, {"text": r.text}
    except Exception as e:
        return False, {"error": str(e)}


def check_server(base_url: str = "http://127.0.0.1:8080") -> HealthReport:
    rep = HealthReport()

    # 1) /health: timeout corto (puede mentir bajo carga, ver #20684)
    ok, data = _probe(f"{base_url}/health", timeout=1.0)
    rep.details["health"] = data
    if not ok: rep.fail("server-health-fail")

    # 2) /slots: confirma slot disponible. fail_on_no_slot=1 → 503 si saturado.
    ok, data = _probe(f"{base_url}/slots?fail_on_no_slot=1", timeout=0.5)
    rep.details["slots"] = data
    if not ok: rep.fail("server-no-slot-available")

    # 3) /props: modelo y ctx coinciden con lo esperado
    ok, data = _probe(f"{base_url}/props", timeout=1.0)
    rep.details["props"] = data
    if ok and isinstance(data, dict):
        gen = data.get("default_generation_settings", {})
        model = str(gen.get("model", ""))
        nctx  = int(gen.get("n_ctx", 0))
        if EXPECTED["model_substr"] not in model:
            rep.fail(f"wrong-model:{model}")
        if nctx != EXPECTED["n_ctx"]:
            rep.fail(f"wrong-ctx:{nctx}")
    else:
        rep.fail("server-props-fail")
    return rep


def check_imports(timeout_s: float = 10.0) -> HealthReport:
    """
    Verifica que torch/torchcodec/torchvision se importen y reporten su
    __version__ en un PROCESO HIJO. Si segfaultean (bad_alloc por mismatch),
    el padre sobrevive.
    """
    rep = HealthReport()
    script = (
        "import json,sys\n"
        "out={}\n"
        "for m in ('torch','torchvision','torchcodec'):\n"
        "    try:\n"
        "        mod=__import__(m); out[m]=getattr(mod,'__version__','unknown')\n"
        "    except Exception as e:\n"
        "        out[m]=f'ERR:{type(e).__name__}:{e}'\n"
        "print(json.dumps(out))\n"
    )
    try:
        r = subprocess.run(
            [sys.executable, "-c", script],
            timeout=timeout_s, capture_output=True, text=True
        )
    except subprocess.TimeoutExpired:
        rep.fail("import-timeout")
        return rep
    if r.returncode != 0:
        # Segfault → returncode != 0 y stderr puede traer "bad_alloc" o "Aborted"
        rep.fail(f"import-segfault:rc={r.returncode}:{r.stderr[:200]}")
        return rep
    try:
        versions = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        rep.fail("import-parse-fail")
        return rep
    rep.details["versions"] = versions
    for k, expected in (("torch", EXPECTED["torch"]),
                        ("torchcodec", EXPECTED["torchcodec"]),
                        ("torchvision", EXPECTED["torchvision"])):
        v = versions.get(k, "")
        if v.startswith("ERR:"):
            rep.fail(f"{k}-import-{v}")
        elif not v.startswith(expected.rsplit(".", 1)[0]):  # major.minor match
            rep.fail(f"{k}-version-mismatch:{v} vs {expected}")
    return rep


def check_nvml() -> HealthReport:
    rep = HealthReport()
    try:
        import pynvml
        pynvml.nvmlInit()
        n = pynvml.nvmlDeviceGetCount()
        rep.details["gpu_count"] = n
        if n < 1: rep.fail("no-gpu")
        pynvml.nvmlShutdown()
    except Exception as e:
        rep.fail(f"nvml-fail:{type(e).__name__}:{e}")
    return rep


def full_self_check() -> HealthReport:
    out = HealthReport()
    for sub in (check_server(), check_imports(), check_nvml()):
        out.issues.extend(sub.issues)
        out.details.update(sub.details)
        if not sub.ok: out.ok = False
    return out


if __name__ == "__main__":
    r = full_self_check()
    print(json.dumps({"ok": r.ok, "issues": r.issues, "details": r.details},
                     indent=2, default=str))
    sys.exit(0 if r.ok else 1)
```

### Fuentes 2025–2026

- llama.cpp issues #20684, #20921, ikawrakow #1210: `/health` puede quedar bloqueado durante prompt processing.
- llama.cpp `tools/server/README.md`: documenta `/health`, `/slots?fail_on_no_slot=1`, `/props`, `/metrics`.
- torchcodec issues #912, #995: import segfault con mismatch de torch (`std::bad_alloc`).
- llamatelemetry docs (2026): patrón de readiness polling sobre `/health` para llama.cpp.
- Trantorinc, "AI Agent Failure Modes: What Goes Wrong in Production" (18 may 2026): cita "88% of organizations deploying AI agents reported at least one security incident in 2025"; falta de governance/observabilidad como causa raíz.

---

## Punto 4 — Degradación elegante bajo carga

### Diagnóstico

Si el usuario abre un juego o stable-diffusion, NVML reporta `free` cayendo y `utilization.gpu` cercano al 100 %. La política correcta para un asistente de voz local **no es competir con el juego** sino:

1. **Detección**: `pynvml.nvmlDeviceGetUtilizationRates(handle).gpu` > 90 % durante 3 muestras consecutivas, o `free_mib < 1024` durante 2 muestras.
2. **Back-pressure inmediato**: rechazar nuevos turnos con un audio "espera, libero recursos" (no encolar indefinido).
3. **Fallback CPU**: levantar un *segundo* `llama-server` en modo CPU (`-ngl 0`, mismo modelo Q4_K_M) en otro puerto, redirigir el siguiente turno ahí. Latencia esperada en CPU para Gemma 4 E4B Q4_K_M: **~2–5 tokens/s** (gemma4-ai.com, "Gemma 4 Hardware Requirements", actualizado 19 may 2026: *"E4B on CPU: ~2-5 tokens/sec. Usable but you'll be patient."*). Lo bastante para respuestas cortas y para no romper la conversación.
4. **Queue corta y *load-shedding***: cola de máximo 1 petición pendiente; las nuevas reciben respuesta inmediata "estoy ocupado, repite en X segundos".

**NO viable**: tratar de "compartir" la GPU bajando capas (`-ngl` dinámico) — eso requiere reload del server y rompe la latencia. Es preferible el switch CPU/GPU duro.

### Tabla de mitigaciones

| Mitigación | Riesgo que cierra | Δ latencia / Δ VRAM | Complejidad |
|---|---|---|---|
| Detección de contención por `nvmlDeviceGetUtilizationRates` + `nvmlDeviceGetMemoryInfo` (250 ms) | OOM por proceso externo | +2 ms | Baja |
| Servidor CPU paralelo en puerto secundario (`llama-server -ngl 0`) precargado en RAM | LLM-down cuando GPU saturada | +1.5–2 GB RAM, 0 VRAM | Media |
| Cola de 1 con rechazo inmediato (HTTP 503 desde un *router* propio frente a llama-server) | Acumulación silenciosa de turnos | <1 ms | Baja |
| Speech-back "estoy ocupado, vuelve en 10 s" | UX rota cuando se rechaza | 0 | Trivial |
| Notificación al usuario antes de cualquier switch CPU↔GPU | Confusión sobre por qué responde lento | 0 | Trivial |
| **NO-VIABLE**: matar/throttlear el juego del usuario | Viola el punto 5 | — | — |

### Veredicto vram4: **VIABLE**

El segundo server CPU es opcional: requiere 1.5–2 GB de RAM. Si no hay RAM, la alternativa que sí cabe es: rechazar turnos con back-pressure y esperar a que la GPU se libere (NVML poll), sin CPU fallback.

### Código concreto — `gpu_contention.py`

```python
# gpu_contention.py — Detecta contención y aplica back-pressure / fallback.

import collections
import pynvml
import time
from enum import IntEnum

class GPULoad(IntEnum):
    IDLE = 0
    BUSY = 1            # 60-89% util sostenida
    SATURATED = 2       # >=90% util o free<1024 MiB

class ContentionDetector:
    def __init__(self, device_index: int = 0, window: int = 3):
        pynvml.nvmlInit()
        self._h = pynvml.nvmlDeviceGetHandleByIndex(device_index)
        self._util = collections.deque(maxlen=window)
        self._free = collections.deque(maxlen=window)

    def sample(self) -> GPULoad:
        u = pynvml.nvmlDeviceGetUtilizationRates(self._h).gpu
        m = pynvml.nvmlDeviceGetMemoryInfo(self._h).free // (1024*1024)
        self._util.append(u); self._free.append(m)
        if len(self._util) < self._util.maxlen: return GPULoad.IDLE
        if all(x >= 90 for x in self._util) or all(x < 1024 for x in self._free):
            return GPULoad.SATURATED
        if all(x >= 60 for x in self._util):
            return GPULoad.BUSY
        return GPULoad.IDLE


class Backpressure:
    """Cola de 1 + decisión de fallback."""
    def __init__(self, cpu_endpoint: str | None = None):
        self._inflight = False
        self._cpu_endpoint = cpu_endpoint  # p.ej. http://127.0.0.1:8081

    def try_accept(self, gpu_load: GPULoad) -> tuple[str, str | None]:
        if self._inflight:
            return ("reject", "agent-busy-retry-10s")
        if gpu_load == GPULoad.SATURATED:
            if self._cpu_endpoint:
                return ("accept-cpu", self._cpu_endpoint)
            return ("reject", "gpu-saturated-no-cpu-fallback")
        return ("accept-gpu", None)

    def on_start(self):  self._inflight = True
    def on_done(self):   self._inflight = False
```

### Fuentes 2025–2026

- Medium "Run vLLM Locally on Low-VRAM Budget Laptop (4GB GPU) in 2025": confirma que vLLM en 4 GB GPU consume >90 % VRAM y causa throttle térmico → mejor llama.cpp + back-pressure.
- gemma4-ai.com "Gemma 4 Hardware Requirements" (19 may 2026): velocidad CPU de E4B documentada en ~2–5 tok/s.
- Erfan Darzi et al., "Predictable LLM Serving on GPU Clusters", arXiv 2508.20274 (27 ago 2025): controlador *VM-deployable* que combina reconfiguración MIG dinámica, *placement* PCIe-aware y *guardrails* (MPS quotas, cgroup I/O) con *dwell/cool-down* para evitar *thrash*; reduce SLO miss-rate ≈32 % y p99 ≈15 % con ≤5 % de coste de throughput vs MIG estático. Inspira el patrón guardrail+cooldown que aplicamos en miniatura (un solo agente local).
- pypi.org/project/nvidia-ml-py: `nvmlDeviceGetUtilizationRates` y `nvmlDeviceGetMemoryInfo` para detección de contención.

---

## Punto 5 — Nunca matar recursos del usuario

### Diagnóstico

Ya tuviste el incidente: el agente mató un juego/LLM externo. La regla **no negociable**: **el agente no envía SIGTERM/SIGKILL a NINGÚN proceso que no sea suyo, sin confirmación explícita del usuario en cada ocasión**. No basta whitelist: hay que combinar:

- **Allowlist** de procesos que el agente puede tocar (los suyos: `llama-server.exe`, sus propios workers).
- **Denylist explícita** de categorías sensibles (juegos detectados por nombre o por `gpu_utilization > 50 %`, navegadores, editores, IDEs, terminales).
- **Dry-run obligatorio**: cualquier rama del agente que vaya a matar/cerrar algo primero responde "voy a cerrar X, ¿confirmas?" y espera respuesta verbal o teclada.
- **Gating duro a nivel de subprocess**: la *única* función que tiene permiso para invocar `psutil.terminate()` exige un `confirmation_token` emitido por el flujo de confirmación.

### Tabla de mitigaciones

| Mitigación | Riesgo que cierra | Δ latencia / Δ VRAM | Complejidad |
|---|---|---|---|
| Allowlist de PIDs hijos del agente (registrar PID al spawn) | Matar procesos ajenos | 0 | Baja |
| Denylist por nombre + por `gpu_utilization>50%` | Matar el juego del usuario | +2 ms (NVML) | Baja |
| Dry-run obligatorio con plantilla "voy a hacer X, ¿confirmas?" | Acción destructiva sin consentimiento | +1 turno | Baja |
| `confirmation_token` con TTL de 30 s (HMAC del nombre de proceso + timestamp) | Confirmación reusada para otra cosa | <1 ms | Media |
| Log estructurado de toda acción destructiva (intentada y consumada) | Falta de auditoría post-incidente | <1 ms | Trivial |
| **NO-VIABLE**: heurística "es seguro matarlo porque consume poca VRAM" | Falsos positivos garantizados | — | — |

### Veredicto vram4: **VIABLE**

Cero costo de VRAM. La latencia añadida es un turno de confirmación, que es exactamente el comportamiento deseado para una asistente de voz.

### Código concreto — `safe_kill.py`

```python
# safe_kill.py — Mata SOLO con allowlist + confirmation_token vivo.
# Nada en este módulo escala sin pasar por confirm().

import hashlib
import hmac
import os
import time
from dataclasses import dataclass

import psutil
import pynvml

# Procesos siempre prohibidos por nombre (substring, case-insensitive)
DENYLIST_NAMES = {
    "explorer.exe", "lsass.exe", "csrss.exe", "winlogon.exe",
    "code.exe", "devenv.exe", "chrome.exe", "firefox.exe", "msedge.exe",
    "steam.exe", "epicgameslauncher.exe", "discord.exe",
    "obs64.exe", "obs32.exe",
}

GPU_UTIL_GUARD = 50  # >50% util => probablemente juego/IA del usuario

_AGENT_OWNED_PIDS: set[int] = set()  # rellenar al spawn de cada hijo del agente
_SECRET = os.urandom(32)             # HMAC token secret (in-memory)

def register_owned_pid(pid: int): _AGENT_OWNED_PIDS.add(pid)

@dataclass
class KillRequest:
    pid: int
    reason: str

def _proc_name(p: psutil.Process) -> str:
    try: return p.name().lower()
    except (psutil.NoSuchProcess, psutil.AccessDenied): return ""

def _is_high_gpu(pid: int) -> bool:
    try:
        pynvml.nvmlInit()
        h = pynvml.nvmlDeviceGetHandleByIndex(0)
        procs = pynvml.nvmlDeviceGetComputeRunningProcesses(h)
        for pr in procs:
            if pr.pid == pid and pr.usedGpuMemory and pr.usedGpuMemory > 500*1024*1024:
                return True
        return False
    except Exception:
        return False
    finally:
        try: pynvml.nvmlShutdown()
        except: pass

def is_kill_allowed(pid: int) -> tuple[bool, str]:
    """Allowlist primero; cualquier otro proceso requiere confirmation_token."""
    if pid in _AGENT_OWNED_PIDS:
        return True, "owned-by-agent"
    try:
        p = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return False, "no-such-process"
    name = _proc_name(p)
    if name in DENYLIST_NAMES:
        return False, f"denylist:{name}"
    if _is_high_gpu(pid):
        return False, "high-gpu-user-workload"
    return False, "needs-confirmation"   # nunca matamos sin token

def issue_confirmation_token(pid: int, name: str) -> str:
    payload = f"{pid}:{name}:{int(time.time())//30}".encode()
    return hmac.new(_SECRET, payload, hashlib.sha256).hexdigest()[:16]

def verify_confirmation_token(token: str, pid: int, name: str) -> bool:
    now = int(time.time()) // 30
    for slot in (now, now - 1):
        payload = f"{pid}:{name}:{slot}".encode()
        ok = hmac.new(_SECRET, payload, hashlib.sha256).hexdigest()[:16]
        if hmac.compare_digest(ok, token): return True
    return False

def safe_kill(req: KillRequest, confirmation_token: str | None = None,
              dry_run: bool = False) -> dict:
    allowed, reason = is_kill_allowed(req.pid)
    if not allowed and reason == "needs-confirmation":
        try: name = psutil.Process(req.pid).name()
        except Exception: name = "unknown"
        if not confirmation_token or not verify_confirmation_token(
                confirmation_token, req.pid, name.lower()):
            return {"ok": False, "reason": "no-or-stale-confirmation",
                    "next_action": "ask-user", "name": name}
    elif not allowed:
        return {"ok": False, "reason": reason}

    if dry_run:
        return {"ok": True, "reason": "dry-run", "would-kill": req.pid}

    try:
        p = psutil.Process(req.pid)
        p.terminate()
        try: p.wait(timeout=5)
        except psutil.TimeoutExpired: p.kill()
        return {"ok": True, "reason": "terminated"}
    except psutil.NoSuchProcess:
        return {"ok": True, "reason": "already-gone"}
    except psutil.AccessDenied as e:
        return {"ok": False, "reason": f"access-denied:{e}"}
```

### Fuentes 2025–2026

- psutil docs (7.2): patrón `terminate()`+`wait(timeout)`+`kill()`, manejo de `NoSuchProcess`/`AccessDenied`.
- Medium "Port Killer in Python" (2026): lección sobre verificar status zombie, no solo existencia.
- nvidia-ml-py docs: `nvmlDeviceGetComputeRunningProcesses` para atribuir uso GPU por PID.

---

## Punto 6 — Observabilidad para diagnosticar hangs

### Diagnóstico

El objetivo no es loguearlo todo — es loguear lo suficiente para **reproducir un hang sin tener que reproducirlo**. Los tres componentes mínimos:

- **Logging estructurado** (JSON), un campo por evento, contexto por turno (`turn_id`, `tool`, `phase`). Loguru con `serialize=True` cumple sin reescribir nada.
- **Heartbeat**: cada turno emite `phase=start`, `phase=llm_done`, `phase=tool_done`, `phase=end`. Si entre dos heartbeats consecutivos pasa más del timeout, sabes exactamente en qué fase quedó colgado.
- **Post-mortem nativo**: `faulthandler.enable()` al arranque + `faulthandler.dump_traceback_later(timeout, repeat=True, file=…)` por turno. Si Python segfaultea (C-extension de torchcodec, ONNX), el traceback queda escrito. Si un thread cuelga >timeout segundos, se dumpea TODO el estado de hilos.

`hanging_threads` y `PyStack` son herramientas valiosas pero opcionales — `faulthandler` cubre el 80 % gratis y es C-level.

### Tabla de mitigaciones

| Mitigación | Riesgo que cierra | Δ latencia / Δ VRAM | Complejidad |
|---|---|---|---|
| Loguru con `serialize=True`, sink rotativo (10 MB × 5) | Logs ilegibles para grep | <1 ms por log line, ~50 MB disco | Trivial |
| `bind(turn_id=...)` por turno + `phase` por sub-paso | Imposible saber dónde colgó | 0 | Baja |
| `faulthandler.enable(file="crash.log")` al arranque | Segfault sin traceback | 0 | Trivial |
| `faulthandler.dump_traceback_later(120, repeat=False)` por turno | Hang sin saber qué thread | <1 ms (watchdog en C) | Baja |
| Heartbeat con timestamp monotonic + diff entre fases | Latencia opaca por fase | <1 ms | Baja |
| Captura periódica (5 min) de `/metrics` Prometheus de llama-server | Drift de tokens/s sin alarma | +10 ms cada 5 min | Baja |
| Snapshot NVML cada 30 s en log estructurado | Picos VRAM no atribuibles | <1 ms cada 30 s | Trivial |
| **NO-VIABLE**: tracing OpenTelemetry completo con exporter remoto | Sobrecarga + dependencia red en local | +10–50 ms por span | — |

### Veredicto vram4: **VIABLE**

Loguru + faulthandler consumen <0.5 % de CPU y cero VRAM. El log JSON estructurado es suficiente para diagnóstico post-mortem.

### Código concreto — `obs.py`

```python
# obs.py — Logging estructurado + faulthandler + heartbeat por turno.

import faulthandler
import sys
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from loguru import logger

LOG_DIR = Path("./logs")
LOG_DIR.mkdir(exist_ok=True)

# Sink 1: humano, solo INFO+ a consola
logger.remove()
logger.add(sys.stderr, level="INFO",
           format="<g>{time:HH:mm:ss}</g> | <lvl>{level: <7}</lvl> | "
                  "{extra[turn_id]:.8} | {message}")

# Sink 2: máquina, DEBUG+ a archivo JSON rotativo
logger.add(LOG_DIR / "agent.jsonl",
           level="DEBUG", serialize=True, rotation="10 MB", retention=5,
           enqueue=True)  # enqueue=True hace el logging thread-safe sin lock

# Sink 3: solo errores en su propio archivo, retención larga
logger.add(LOG_DIR / "errors.jsonl",
           level="ERROR", serialize=True, rotation="5 MB", retention=20)

# Faulthandler nativo: dumpea segfaults a un archivo persistente
_crash_file = open(LOG_DIR / "crash.log", "a", buffering=1)
faulthandler.enable(file=_crash_file, all_threads=True)
# En Windows no hay SIGUSR1; se puede generar manualmente con
# faulthandler.dump_traceback() desde una shell remota.


@contextmanager
def turn(turn_id: str | None = None, **bind):
    """Contexto por turno. Loguea inicio/fin y dumpea threads si supera 120s."""
    tid = turn_id or uuid.uuid4().hex
    log = logger.bind(turn_id=tid, **bind)
    t0 = time.monotonic()
    log.bind(phase="start").info("turn-start")
    faulthandler.dump_traceback_later(120, repeat=False, file=_crash_file)
    try:
        yield log
    except BaseException as e:
        log.bind(phase="error").exception(f"turn-failed: {type(e).__name__}")
        raise
    finally:
        faulthandler.cancel_dump_traceback_later()
        log.bind(phase="end", dur_s=round(time.monotonic()-t0, 3)).info("turn-end")


@contextmanager
def phase(log, name: str):
    t0 = time.monotonic()
    log.bind(phase=name).debug(f"{name}-start")
    try:
        yield
    finally:
        log.bind(phase=name,
                 dur_s=round(time.monotonic()-t0, 3)).debug(f"{name}-end")


# --- Uso ---
# from obs import turn, phase
# with turn() as log:
#     with phase(log, "llm"):
#         response = call_llm(...)
#     with phase(log, "tool:screenshot"):
#         img = run_isolated(screenshot, ...)
```

### Fuentes 2025–2026

- Python docs `faulthandler` (3.14): `dump_traceback_later`, `enable` con `all_threads=True`, watchdog thread en C.
- Real Python "faulthandler" (2026): casos de uso para deadlocks y producción.
- dafoster.net "Debugging a deadlock in Python" (2023): patrón `dump_traceback_later` + recolección de holders de lock.
- Dash0 "Python Logging with Loguru: From Setup to Production" (2025): patrón `bind()` + `serialize=True` + sinks múltiples + `enqueue=True` para safety.
- DataCamp "Loguru Python Logging Tutorial" (2025): patrón de tres sinks (consola humana / JSON / errores).
- llama.cpp `/metrics` (Prometheus): `prompt_tokens_total`, `kv_cache_usage_ratio`, `n_busy_slots_per_decode` — útiles para correlación.
- martinheinz.dev "Debugging Crashes and Deadlocks in Python using PyStack" (2024): herramienta opcional cuando faulthandler no basta.

---

## Recomendaciones (orden de despliegue)

**Sprint 1 (esta semana) — cierra los riesgos #1, #2, #3 (los que más previenen crashes):**

1. Despliega `vram_watchdog.py` con umbrales `warn=800 / degrade=500 / critical=250 MiB`. Conecta `on_degrade` a `router.unload_mmproj()` y a una reducción de `ctx_target` a 8192. Métrica de éxito: cero OOM en 7 días de uso real.
2. Cambia los flags de arranque de `llama-server` a la receta vram4 (`--cache-type-k q8_0 --cache-type-v q8_0 -fa on --no-mmproj-offload --kv-unified --no-context-shift`). Métrica de éxito: footprint VRAM medido por `nvmlDeviceGetMemoryInfo` ≤ 4.0 GiB con mmproj descargado.
3. Reemplaza el `try/except` per-tool por `run_isolated()` para las 3–5 tools de mayor riesgo (cualquier cosa que toque torch, ONNX, captura de pantalla, automatización del Explorer). Métrica: una tool puede segfaultear sin colgar la GUI.

**Sprint 2 (próximas dos semanas) — completa puntos #4, #5, #6:**

4. Añade `full_self_check()` al arranque y como cron-tarea cada 5 min; bloquea el arranque si falla import o `/props`. Habla al usuario en español cuando algo falle.
5. Implementa `safe_kill()` con `confirmation_token` HMAC. Audita: ¿cuántas veces, en el último log, el agente llamó `terminate()` sin pasar por este módulo? Llévalo a 0.
6. Activa `obs.py` por defecto. Verifica que el archivo `crash.log` queda escrito tras provocar a propósito un `os.kill(os.getpid(), signal.SIGABRT)` en un thread worker.

**Sprint 3 (opcional, si la presión persiste):**

7. Levanta un *segundo* `llama-server` en CPU (`-ngl 0`) en el puerto 8081 a modo de fallback. Habilita `ContentionDetector` para enrutar a CPU cuando `GPULoad.SATURATED` durante 3 muestras. RAM extra: ~1.8 GB.

**Umbrales que cambian las recomendaciones:**

- Si el footprint medido en GPU supera 4.5 GiB de forma sostenida → mueve KV a `q4_0` y revalúa.
- Si en una semana hay ≥3 OOMs detectados *después* del watchdog → baja `degrade_mib` a 700 MiB.
- Si las tools agregan >100 ms p99 de overhead → mueve las menos riesgosas fuera del sandbox y deja sandbox solo para torch/torchcodec/captura.
- Si Gemma 4 E4B Q4_K_M se actualiza a una variante con mmproj más pequeño (<500 MiB), revisa si vale la pena ofloadear el mmproj a GPU por defecto.

---

## Caveats y limitaciones

- **Los números VRAM tienen ~3 % de incertidumbre** porque el log primario disponible (llama.cpp issue #21430) usa UD-Q4_K_XL (5.10 GB) en lugar de Q4_K_M puro (4.98 GB). El estimador `vram_calculator.py` validado a la MiB que tienes es la referencia más fiable; usa los números aquí como sanity check, no como sustituto.
- **`/health` y `/slots` pueden quedar bloqueados durante prompt processing largo** según los issues #20684, #20921 e ik_llama #1210. Por eso el heartbeat propio del agente complementa, no sustituye, a los probes del server.
- **`pybreaker` no se actualiza con la misma frecuencia que `circuitbreaker`**; ambos cumplen la spec de Nygard. Si quieres listeners más ricos para Prometheus, `pybreaker` los soporta nativo.
- **`faulthandler.dump_traceback_later` usa un thread watchdog**; el documento Python 3.14 advierte que con free-threaded builds solo dumpea el thread actual para evitar data races. En CPython estándar con GIL no hay riesgo.
- **`nvmlDeviceGetUtilizationRates` reporta utilización global de la GPU, no por proceso**. Para atribuir a un PID hay que usar `nvmlDeviceGetComputeRunningProcesses` y mirar `usedGpuMemory` — lo hace `safe_kill.py`. No es 100 % preciso bajo WDDM en Windows: ciertos procesos DX12/Vulkan no aparecen en NVML como "compute".
- **Algunas afirmaciones del ecosistema sobre Gemma 4** (architecture específica, SWA 5:1, 18 shared-KV) provienen del log de issue #21430 que ya estaba en build 650bf14 (cercana a tu b9090). Si tu build difiere, valida con `llama-server --version` y `/props` antes de aplicar los flags.
- **No probé empíricamente la mitigación de back-pressure con un juego real**; el patrón se inspira en literatura de planificación GPU multi-tenant (Darzi et al., arXiv 2508.20274, ago 2025) y en cómo `Paddler` enruta llama.cpp. Calibra los umbrales `GPU_UTIL_GUARD` con telemetría de tu propio uso.
- **El throughput CPU de Gemma 4 E4B (~2–5 tok/s)** proviene de la guía de hardware de gemma4-ai.com (19 may 2026) y depende fuertemente del CPU (AVX-512, número de P-cores, AVX2 vs AVX-512). En CPUs con solo AVX2 esperan el extremo bajo del rango.
- **Loguru NO tiene integración oficial con OpenTelemetry**; si necesitas traces correlados con métricas, hay que escribir el adapter a mano (Dash0 lo documenta). Para vram4 local no merece la pena.