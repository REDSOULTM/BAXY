"""Bridge entre el `events_bus.BUS` (in-process, agnostico de framework) y la
GUI Qt.

Por que: `events_bus.BUS.add_listener(fn)` invoca al listener inline en el
thread del publicador (puede ser el worker thread del agente, el tail-thread
de llama-server, el thread de prewarm, etc.). Tocar widgets desde un thread
que no es el main thread de Qt rompe (silenciosamente o con crash).

Solucion: este `QObject` se suscribe al BUS, clasifica el evento por su
`kind`/`type`/`stage`, y emite una `pyqtSignal` tipada por categoria. Como
las signals cruzan threads, Qt las marshalla automaticamente al main thread
via `QueuedConnection`, igual que ya hace `VoiceBridge`.

Contrato de eventos que esperamos del bus (best-effort; cualquier shape
desconocido se descarta sin error):

  - boot_stage:
      {"type"|"kind": "boot_stage", "stage": str, "label"?: str,
       "progress"?: float, "ok"?: bool, "elapsed_s"?: float,
       "system_prompt_chars"?: int, "error"?: str, "msg"?: str}

  - vision_threshold:
      {"kind": "vision_threshold_reached", "image_count": int,
       "threshold": int, "issue": str}

  - activity:
      {"type": "activity", "entry": {"src": str, "msg": str, "ts": str,
                                      "id": str}}

  - agent state:
      {"type": "agent", "built": bool, "healthy": bool, "ready": bool}

Eventos que no matchean ninguna categoria se reemiten via `unknown_event` por
si algun consumidor quiere logearlos para debug.

Threading note: `BUS.add_listener` callbacks deben ser rapidos (<1ms) y
exception-safe — emitir una pyqtSignal cumple ambas (Qt encola el slot, no
bloquea).
"""
from __future__ import annotations

import logging
from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal

from ..infra.events_bus import BUS

logger = logging.getLogger(__name__)


class EventBusBridge(QObject):
    """Suscribe la GUI al EventBus de modulo y rebota eventos a signals Qt.

    Crear UNA sola instancia (idealmente en MainWindow.__init__) y conectar
    sus signals a slots de la ventana. La instancia debe vivir tanto como
    la ventana — al cerrarse, llamar a `detach()` para desuscribirse.
    """

    # Boot / startup events (incluye prewarm y los stages de llama-server).
    boot_stage = pyqtSignal(dict)

    # Multimodal: el counter de imagenes cruzo el umbral (issue #21690).
    vision_threshold = pyqtSignal(dict)

    # Activity log generico (lo que agent_runner publica para la UI React).
    activity = pyqtSignal(dict)

    # Agent lifecycle (built/healthy/ready flags).
    agent_state = pyqtSignal(dict)

    # Catch-all para debugging — eventos que no caen en ninguna categoria.
    unknown_event = pyqtSignal(dict)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._attached = False

    def attach(self) -> None:
        """Registra el listener en el BUS. Idempotente."""
        if self._attached:
            return
        try:
            BUS.add_listener(self._on_bus_event)
            self._attached = True
        except Exception as exc:  # noqa: BLE001
            logger.warning("EventBusBridge.attach failed: %s", exc)

    def detach(self) -> None:
        """Desregistra el listener. Idempotente."""
        if not self._attached:
            return
        try:
            BUS.remove_listener(self._on_bus_event)
        except Exception:
            pass
        self._attached = False

    # ----------------------------------------------------------------
    def _on_bus_event(self, event: dict[str, Any]) -> None:
        """Listener sincrono — corre en el thread del publicador. Solo
        clasifica y emite signals; el slot consumidor corre en main thread."""
        if not isinstance(event, dict):
            return
        try:
            # Aceptar "kind" o "type" — el bus tiene historicamente ambos
            # (boot_progress.py usa "type", prewarm.py usa "kind").
            kind = str(event.get("kind") or event.get("type") or "").lower()

            if kind == "boot_stage":
                self.boot_stage.emit(event)
            elif kind == "vision_threshold_reached":
                self.vision_threshold.emit(event)
            elif kind == "activity":
                self.activity.emit(event)
            elif kind == "agent":
                self.agent_state.emit(event)
            else:
                self.unknown_event.emit(event)
        except Exception as exc:  # noqa: BLE001
            # Nunca propagar — el bus swallowa pero igual logueamos.
            logger.debug("EventBusBridge dispatch failed: %s", exc)
