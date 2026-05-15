"""Fase V — Watcher daemon que cambia perfil automaticamente.

Tres condiciones disparan downgrade (todas opt-in via settings):
1. Proceso de juego/heavy-app detectado en la watchlist.
2. GPU usage promedio en los ultimos 30s > 70%, excluyendo el proceso de
   llama-server (medido con nvidia-smi pmon).
3. RAM total > 85%.

Histeresis:
- Bajar: 30s sostenidos cumpliendo la condicion -> set_active_profile(downgrade_to).
- Subir: 60s sostenidos sin ninguna condicion -> set_active_profile(restore_to).

El thread usa threading.Event.wait para poder pararse limpio sin time.sleep.
Cada cambio se loggea con razon (game detected: steam.exe, gpu sustained 78%, etc).

NO arranca solo: el caller (UI) debe instanciar ProfileWatcher y llamar start().
Si el usuario apaga auto-switch en Settings, llamar stop().
"""
from __future__ import annotations

import logging
import subprocess
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Iterable, Optional

from .profiles import (
    PROFILES,
    Profile,
    _profile_with_overrides,
    apply_profile_to_env,
    get_active_profile,
    set_active_profile,
)


logger = logging.getLogger(__name__)


# Hysteresis windows (segundos) — sustained presence/absence of triggers.
DOWNGRADE_SUSTAIN_S = 30
UPGRADE_SUSTAIN_S = 60
TICK_INTERVAL_S = 10  # cada 10s sampleamos psutil/nvidia-smi
GPU_THRESHOLD_PCT = 70
RAM_THRESHOLD_PCT = 85
# VRAM ocupada por procesos que NO son llama-server. Si supera este umbral,
# significa que algo pesado esta usando la GPU (juego, render, training) y
# convien bajar el perfil para liberarle VRAM. 40% de 6GB = ~2.4GB, valor que
# un cliente de Steam idle NO alcanza (~200MB) pero cualquier juego moderno si.
VRAM_THRESHOLD_PCT = 40


@dataclass
class WatcherConfig:
    enabled: bool = False
    downgrade_to: str = "light"
    restore_to: str = "balanced"
    game_watchlist: list[str] = field(default_factory=list)
    trigger_on_game: bool = False  # nombre-based: opt-in solo si el user lo quiere
    trigger_on_gpu: bool = False
    trigger_on_ram: bool = False
    # Recomendado: detecta automaticamente CUALQUIER cosa pesada en GPU
    # (juego, render, transcoding, training) sin depender de listas de nombres.
    trigger_on_vram: bool = True


@dataclass
class _Sample:
    has_game: bool
    gpu_pct: float | None  # None si no se pudo medir
    ram_pct: float | None
    vram_pct: float | None  # VRAM ocupada por procesos que NO son llama-server


def _list_processes() -> set[str]:
    """Devuelve set de nombres de proceso lowercased. Vacio si psutil no esta."""
    try:
        import psutil  # type: ignore[import-not-found]
    except ImportError:
        return set()
    names: set[str] = set()
    for proc in psutil.process_iter(["name"]):
        try:
            name = (proc.info.get("name") or "").lower()
            if name:
                names.add(name)
        except Exception:
            continue
    return names


def _ram_pct() -> float | None:
    try:
        import psutil  # type: ignore[import-not-found]
        return float(psutil.virtual_memory().percent)
    except Exception:
        return None


def _gpu_pct_excluding_llama() -> float | None:
    """Mide utilizacion de GPU% promediada sobre todos los procesos GPU
    excepto los que contienen 'llama-server' en el nombre.

    Usa `nvidia-smi pmon -c 1 -s u` (sample once, utilization columns).
    Devuelve None si nvidia-smi no esta o el formato no parsea.

    Output esperado (texto):
        # gpu        pid  type    sm   mem   enc   dec   command
        # Idx        #   C/G     %     %     %     %    name
            0      1234     C    45    20     0     0   llama-server.exe
            0      5678     C    30    10     0     0   python.exe
    """
    try:
        result = subprocess.run(
            ["nvidia-smi", "pmon", "-c", "1", "-s", "u"],
            capture_output=True, text=True, timeout=3, check=False,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None

    total_sm = 0.0
    count = 0
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 8:
            continue
        # parts: gpu, pid, type, sm, mem, enc, dec, command...
        sm_str = parts[3]
        cmd = " ".join(parts[7:]).lower()
        if "llama-server" in cmd:
            continue  # exclude our own usage
        try:
            sm = float(sm_str) if sm_str != "-" else 0.0
        except ValueError:
            continue
        total_sm += sm
        count += 1
    if count == 0:
        # Nadie mas que llama-server, o no hay procesos GPU
        return 0.0
    return total_sm / count


def _vram_pct_excluding_llama() -> float | None:
    """Devuelve % de VRAM ocupada por procesos que NO son llama-server.

    Estrategia:
    1. `nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits` -> total MB
    2. `nvidia-smi --query-compute-apps=process_name,used_memory --format=csv,noheader,nounits`
       -> lista de (proceso, MB usados). Sumamos todo excepto llama-server.
    3. Devolvemos (suma_externa / total) * 100.

    Devuelve None si nvidia-smi no esta disponible o el formato no parsea.
    """
    try:
        total_res = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=3, check=False,
        )
        if total_res.returncode != 0 or not total_res.stdout.strip():
            return None
        total_mb = float(total_res.stdout.strip().splitlines()[0].strip())
        if total_mb <= 0:
            return None
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError, ValueError):
        return None

    try:
        apps_res = subprocess.run(
            ["nvidia-smi", "--query-compute-apps=process_name,used_memory", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=3, check=False,
        )
        if apps_res.returncode != 0:
            return None
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None

    external_mb = 0.0
    for line in apps_res.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        # "name, mb" — el name puede tener espacios pero no comas
        parts = [p.strip() for p in line.rsplit(",", 1)]
        if len(parts) != 2:
            continue
        name, mb_str = parts
        if "llama-server" in name.lower():
            continue
        try:
            external_mb += float(mb_str)
        except ValueError:
            continue

    return (external_mb / total_mb) * 100.0


def _game_in_watchlist(watchlist: Iterable[str]) -> str | None:
    """True si algun proceso corriendo coincide con la watchlist (case-insensitive).

    Devuelve el primer nombre que matchea, o None.
    """
    wl_norm = {name.strip().lower() for name in watchlist if name.strip()}
    if not wl_norm:
        return None
    running = _list_processes()
    for name in wl_norm:
        if name in running:
            return name
    return None


class ProfileWatcher:
    """Thread daemon con histeresis 30s/60s.

    Uso:
        cfg = WatcherConfig(enabled=True, game_watchlist=["steam.exe"])
        watcher = ProfileWatcher(cfg, on_change=lambda name, reason: ...)
        watcher.start()
        ...
        watcher.stop()  # para limpio
    """

    def __init__(
        self,
        cfg: WatcherConfig,
        on_change: Optional[Callable[[str, str], None]] = None,
        clock: Optional[Callable[[], float]] = None,
    ) -> None:
        self._cfg = cfg
        self._on_change = on_change
        self._clock = clock or (lambda: __import__("time").monotonic())
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        # Ring buffer de samples con timestamp
        self._samples: deque[tuple[float, _Sample]] = deque(maxlen=64)
        # Estado: en qual perfil estamos por decision del watcher
        self._watcher_state: str = "idle"  # "idle" (sin downgrade) | "downgraded"
        # Audit fix #5: en lugar de aplicar env vars inmediato (que puede
        # corromper un turno en vuelo), el watcher encola la decision aqui y
        # el caller invoca apply_pending() en un momento seguro (fin-de-turno).
        self._pending: Optional[tuple[str, str]] = None  # (profile_name, reason)
        self._pending_lock = threading.Lock()

    def start(self) -> None:
        if not self._cfg.enabled:
            logger.info("ProfileWatcher disabled by config; not starting")
            return
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, name="ProfileWatcher", daemon=True,
        )
        self._thread.start()
        logger.info("ProfileWatcher started")

    def stop(self, timeout_s: float = 3.0) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout_s)

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _sample(self) -> _Sample:
        has_game = bool(_game_in_watchlist(self._cfg.game_watchlist)) if self._cfg.trigger_on_game else False
        gpu_pct = _gpu_pct_excluding_llama() if self._cfg.trigger_on_gpu else None
        ram_pct = _ram_pct() if self._cfg.trigger_on_ram else None
        vram_pct = _vram_pct_excluding_llama() if self._cfg.trigger_on_vram else None
        return _Sample(has_game=has_game, gpu_pct=gpu_pct, ram_pct=ram_pct, vram_pct=vram_pct)

    def _condition_active(self, sample: _Sample) -> bool:
        """True si alguna condicion habilitada esta cumplida ahora mismo."""
        if self._cfg.trigger_on_game and sample.has_game:
            return True
        if self._cfg.trigger_on_gpu and sample.gpu_pct is not None and sample.gpu_pct > GPU_THRESHOLD_PCT:
            return True
        if self._cfg.trigger_on_ram and sample.ram_pct is not None and sample.ram_pct > RAM_THRESHOLD_PCT:
            return True
        if self._cfg.trigger_on_vram and sample.vram_pct is not None and sample.vram_pct > VRAM_THRESHOLD_PCT:
            return True
        return False

    def _condition_reason(self, sample: _Sample) -> str:
        bits: list[str] = []
        if self._cfg.trigger_on_game and sample.has_game:
            game = _game_in_watchlist(self._cfg.game_watchlist)
            bits.append(f"game={game}")
        if self._cfg.trigger_on_gpu and sample.gpu_pct is not None and sample.gpu_pct > GPU_THRESHOLD_PCT:
            bits.append(f"gpu={sample.gpu_pct:.1f}%")
        if self._cfg.trigger_on_ram and sample.ram_pct is not None and sample.ram_pct > RAM_THRESHOLD_PCT:
            bits.append(f"ram={sample.ram_pct:.1f}%")
        if self._cfg.trigger_on_vram and sample.vram_pct is not None and sample.vram_pct > VRAM_THRESHOLD_PCT:
            bits.append(f"vram_ext={sample.vram_pct:.1f}%")
        return ", ".join(bits) if bits else "no triggers"

    def _sustained(self, window_s: float, condition: bool) -> bool:
        """True si TODOS los samples en los ultimos window_s segundos cumplen `condition`.

        Retorna False si no hay samples suficientes que cubran window_s
        (oldest dentro de la ventana esta mas cerca de `now` que `window_s`).
        """
        if not self._samples:
            return False
        now = self._samples[-1][0]
        cutoff = now - window_s
        relevant = [(ts, s) for ts, s in self._samples if ts >= cutoff]
        if not relevant:
            return False
        # Comprobar que el sample mas viejo del rango cubre al menos window_s.
        oldest_ts = relevant[0][0]
        if (now - oldest_ts) < window_s - 0.001:
            return False
        # Todos deben cumplir condicion
        if condition:
            return all(self._condition_active(s) for _, s in relevant)
        return all(not self._condition_active(s) for _, s in relevant)

    def _switch_to(self, name: str, reason: str) -> None:
        try:
            set_active_profile(name)
            # Apply with overrides direct from memory, sin re-leer active_profile.txt
            # (que justo acabamos de escribir). Mas barato y mas correcto: si dos
            # threads compiten, este usa el valor que SI escribimos arriba.
            apply_profile_to_env(_profile_with_overrides(PROFILES[name]))
            logger.info("ProfileWatcher switched to %s (reason: %s)", name, reason)
        except (ValueError, OSError) as exc:
            logger.error("ProfileWatcher failed to switch to %s: %s", name, exc)
            return
        if self._on_change is not None:
            try:
                self._on_change(name, reason)
            except Exception as exc:
                logger.warning("on_change callback raised: %s", exc)

    def _tick(self) -> None:
        sample = self._sample()
        self._samples.append((self._clock(), sample))

        if self._watcher_state == "idle":
            # Solo bajamos si la condicion lleva 30s sostenida
            if self._sustained(DOWNGRADE_SUSTAIN_S, condition=True):
                current_name = get_active_profile().name
                if current_name == self._cfg.downgrade_to:
                    # Ya estamos abajo por otra razon (manual)
                    self._watcher_state = "downgraded"
                    return
                reason = self._condition_reason(sample)
                self._queue_switch(self._cfg.downgrade_to, reason)
                self._watcher_state = "downgraded"
        elif self._watcher_state == "downgraded":
            # Solo subimos si NO hay condicion activa por 60s
            if self._sustained(UPGRADE_SUSTAIN_S, condition=False):
                self._queue_switch(self._cfg.restore_to, "triggers cleared")
                self._watcher_state = "idle"

    def _queue_switch(self, name: str, reason: str) -> None:
        """Encola el cambio de perfil en lugar de aplicarlo ya.

        El caller (UI) drena via apply_pending() en un momento seguro
        (fin-de-turno) para no corromper un request en vuelo.
        """
        with self._pending_lock:
            self._pending = (name, reason)
        logger.info("ProfileWatcher queued switch to %s (reason: %s)", name, reason)

    def apply_pending(self, *, force: bool = False) -> bool:
        """Aplica el switch encolado (si hay). Retorna True si se aplico.

        `force=True` permite al caller (boton manual de la GUI) saltar el
        gating de fin-de-turno; equivale al comportamiento pre-fix.
        """
        with self._pending_lock:
            pending = self._pending
            self._pending = None
        if pending is None:
            return False
        name, reason = pending
        self._switch_to(name, reason)
        return True

    def _run(self) -> None:
        # Loop principal: usar Event.wait para que stop() interrumpa rapido
        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception as exc:
                logger.warning("ProfileWatcher tick failed: %s", exc)
            # Espera interrumpible (NO time.sleep)
            self._stop_event.wait(TICK_INTERVAL_S)
        logger.info("ProfileWatcher stopped")
