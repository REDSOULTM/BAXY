"""Main window — assembles header, side panels, HUD canvas, footer.

Handles modal dialogs (settings, triggers, memory, tools, sessions panel).
Owns the AgentWorker thread and wires its signals to the UI.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QObject, QSize, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication, QFileDialog, QHBoxLayout, QMainWindow, QMessageBox,
    QSizePolicy, QVBoxLayout, QWidget,
)

from .agent_thread import AgentWorker
from .hud import HudCanvas
from .log_widget import LogWidget
from .memory_viewer import MemoryDialog
from . import metrics as metrics_mod
from . import panels
from .sessions_panel import SessionsPanel
from .settings import SettingsDialog
from .theme import C
from .tool_explorer import ToolExplorer
from .triggers import TriggersDialog


_DEFAULT_W, _DEFAULT_H = 1280, 820
_MIN_W, _MIN_H = 1000, 700


# Frases que Whisper alucina con audio corto/ruidoso. Vienen de entrenamiento
# con YouTube/podcasts. Si el final_text es solo una de estas (modulo
# normalizacion), lo descartamos y no se lo enviamos al LLM.
_WHISPER_HALLUCINATIONS = {
    "suscribete", "suscríbete", "isuscribete", "isuscríbete",
    "gracias por ver", "gracias por ver el video",
    "subtitulos por la comunidad de amara.org",
    "subtitulos creados por la comunidad de amara.org",
    "subtitulado por", "subtitulado por la comunidad de amara.org",
    "amara.org", "thanks for watching", "thank you for watching",
    "subscribe", "like and subscribe", "like and subscribe!",
    ".", "...", "!", "?", "you", "thank you",
    "translation by", "transcripcion",
}


def _is_whisper_hallucination(text: str) -> bool:
    """True si el texto coincide con frases tipicas de alucinacion de Whisper."""
    if not text:
        return True
    import unicodedata
    norm = unicodedata.normalize("NFKD", text.strip().casefold())
    norm = "".join(ch for ch in norm if not unicodedata.combining(ch))
    norm = norm.strip("¡¿!?.,;:")
    if not norm or len(norm) < 2:
        return True
    return norm in _WHISPER_HALLUCINATIONS


class VoiceBridge(QObject):
    """Recibe callbacks del VoiceController desde threads no-GUI y los reemite
    como pyqtSignal. Qt marshalla a main thread automaticamente cuando una
    senal cruza threads (default QueuedConnection).

    Sin esto, QTimer.singleShot(0, fn) desde el thread STT/audio NO ejecuta
    `fn` en el main thread y los handlers de la GUI se descartan silenciosamente.
    """
    state_changed = pyqtSignal(str)
    partial = pyqtSignal(str)
    final = pyqtSignal(str)
    failed = pyqtSignal(str)


class ServerBootWorker(QThread):
    """Arranca llama-server en background sin bloquear la GUI.

    Emite:
      - log(text, tag) durante el boot
      - finished_with_result(result_str) cuando termina: "started", "external",
        "missing_files", "timeout", "skipped_standby", "already_running"
    """
    log = pyqtSignal(str, str)
    finished_with_result = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

    def run(self) -> None:
        # Imports locales para no cargar el manager si la GUI nunca dispara boot.
        try:
            from ..config import AgentConfig
            from ..llama_server import LlamaServerManager, port_in_use
            from ..profiles import apply_profile_to_env, get_active_profile
        except Exception as exc:
            self.log.emit(f"server boot failed at import: {exc}", "err")
            self.finished_with_result.emit("missing_files")
            return

        profile = get_active_profile()
        if not profile.server_running:
            self.log.emit(
                f"profile {profile.display_name} has server off; skipping boot",
                "sys",
            )
            self.finished_with_result.emit("skipped_standby")
            return

        # Aplicar env vars del perfil ANTES de construir AgentConfig para que
        # el comando del server vea context/mmproj coherentes.
        apply_profile_to_env(profile)
        config = AgentConfig.from_env()

        if port_in_use():
            # Server externo en :8080. Respetamos.
            self.log.emit(
                "external llama-server detected on :8080; NOT touching it",
                "warn",
            )
            # Check context mismatch (mismo helper que en _apply_profile)
            try:
                from ..llama_server import get_external_server_context
                ext_ctx = get_external_server_context()
                if ext_ctx is not None and ext_ctx < int(profile.context_size):
                    self.log.emit(
                        f"external server has -c={ext_ctx} but profile "
                        f"{profile.name} asks for {profile.context_size}; "
                        "long prompts will be truncated by the server",
                        "warn",
                    )
            except Exception:
                pass
            self.finished_with_result.emit("external")
            return

        # Verificar archivos
        if not config.llama_server_exe.exists():
            self.log.emit(
                f"llama-server.exe not found at {config.llama_server_exe}",
                "err",
            )
            self.finished_with_result.emit("missing_files")
            return
        if not config.model_path.exists():
            self.log.emit(
                f"model not found at {config.model_path}",
                "err",
            )
            self.finished_with_result.emit("missing_files")
            return

        self.log.emit(
            f"booting llama-server (profile={profile.display_name}, "
            f"ctx={profile.context_size})...",
            "sys",
        )
        manager = LlamaServerManager(config=config)
        result = manager.start(profile, wait_health=True, timeout_s=90)
        if result == "started":
            self.log.emit("llama-server ready", "ok")
        elif result == "timeout":
            self.log.emit(
                "llama-server did not become healthy in 90s; "
                "check logs/llama-server.err.log",
                "warn",
            )
        elif result == "missing_files":
            self.log.emit("llama-server cannot start: missing files", "err")
        elif result == "external":
            # raza: detectamos externo durante el spawn
            self.log.emit(
                "external llama-server appeared during boot; respecting it",
                "warn",
            )
        elif result == "already_running":
            self.log.emit("llama-server already running for this profile", "sys")
        self.finished_with_result.emit(result)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("GEMMA4  ·  MARK I")
        self.setMinimumSize(_MIN_W, _MIN_H)
        self.resize(_DEFAULT_W, _DEFAULT_H)

        screen = QApplication.primaryScreen()
        if screen is not None:
            ag = screen.availableGeometry()
            self.move((ag.width() - _DEFAULT_W) // 2, (ag.height() - _DEFAULT_H) // 2)

        # Build agent worker FIRST so panels can use it
        self.worker = AgentWorker(self)
        self._pending_attachments_img: list[str] = []
        self._pending_attachments_aud: list[str] = []

        # Sessions backend (lazy)
        from ..sessions import Session, SessionStore
        self._SessionStore_cls = SessionStore
        self._Session_cls = Session
        self._session_store: SessionStore | None = None
        self._current_session: Session | None = None

        # Build UI
        self._build()

        # System metrics sampler
        self._metrics = metrics_mod.SysMetrics(interval=1.5)
        self._metrics_timer = QTimer(self)
        self._metrics_timer.timeout.connect(self._tick_metrics)
        self._metrics_timer.start(1500)

        # Wire worker signals
        self.worker.state_changed.connect(self.hud.set_state)
        self.worker.log.connect(self._on_log)
        self.worker.connection_changed.connect(self._on_connection_changed)
        self.worker.reply_ready.connect(self._on_reply)
        self.worker.llm_error.connect(self._on_llm_error)
        self.worker.progress.connect(self._on_progress)

        # Shortcuts
        def _sc(seq: str, fn: Any) -> None:
            s = QShortcut(QKeySequence(seq), self)
            s.activated.connect(fn)
        _sc("F11",            self._toggle_fullscreen)
        _sc("Ctrl+L",         self._clear_log)
        _sc("Ctrl+N",         self._new_session)
        _sc("Ctrl+,",         self._open_settings)
        _sc("Ctrl+Shift+S",   self._open_sessions)
        _sc("Ctrl+T",         self._open_triggers)
        _sc("Ctrl+M",         self._open_memory)
        _sc("Ctrl+E",         self._open_tools)
        # Fase V — cycle profiles
        _sc("Ctrl+Shift+G",   self._cycle_profile)

        # Fase V — wire profile selector buttons + apply initial active profile
        self._llama_manager = None  # type: ignore[assignment]  # lazy init
        self._profile_watcher = None  # type: ignore[assignment]  # lazy init
        self._wire_profile_buttons()
        self._refresh_profile_selector()
        # Start watcher if persisted auto-config has enabled=True
        try:
            from .settings import load_persisted
            auto_cfg = (load_persisted().get("profiles_auto") or {})
            if auto_cfg.get("enabled"):
                self._reconfigure_profile_watcher(auto_cfg)
        except Exception:
            pass

        # Bootstrap sessions
        try:
            from ..sessions import is_enabled as sessions_on
            if sessions_on():
                self._session_store = self._SessionStore_cls()
                self._current_session = self._Session_cls.new()
                self._update_footer_session()
        except Exception:
            pass

        # Kick off worker
        self.worker.start()

        # Auto-arrancar llama-server si el perfil lo pide y no hay server vivo
        self._server_boot_thread: ServerBootWorker | None = None
        self._server_booting: bool = False
        # Refrescar estado del input por si arranca en STANDBY persistido
        QTimer.singleShot(0, self._refresh_chat_input_blocked)
        QTimer.singleShot(50, self._maybe_autostart_server)

        # Fase W — voice controller (lazy-init)
        self._voice_controller: Any = None
        self._voice_bridge: VoiceBridge | None = None
        QTimer.singleShot(100, self._maybe_enable_voice)

    # ------------------------------------------------------------------
    def _build(self) -> None:
        central = QWidget()
        central.setStyleSheet(f"background: {C.BG};")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        header, self._header_h = panels.build_header()
        root.addWidget(header)

        # Body — left + HUD + right
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        left, self._left_h = panels.build_left_panel()
        body.addWidget(left, stretch=0)

        self.hud = HudCanvas()
        self.hud.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        body.addWidget(self.hud, stretch=5)

        self.log = LogWidget()
        right, self._right_h = panels.build_right_panel(
            log_widget=self.log,
            on_send=self._on_send,
            on_open_sessions=self._open_sessions,
            on_open_settings=self._open_settings,
            on_open_triggers=self._open_triggers,
            on_open_memory=self._open_memory,
            on_open_tools=self._open_tools,
            on_attach_image=self._attach_image,
        )
        body.addWidget(right, stretch=0)
        root.addLayout(body, stretch=1)

        # Footer
        footer, self._footer_h = panels.build_footer()
        root.addWidget(footer)

        # Sessions overlay (initially hidden, positioned over the central widget)
        self._sessions_panel: SessionsPanel | None = None

    # ------------------------------------------------------------------
    def _tick_metrics(self) -> None:
        snap = self._metrics.snapshot()
        # CPU
        self._left_h["bar_cpu"].set_value(snap["cpu"], f"{snap['cpu']:.0f}%")
        # MEM
        self._left_h["bar_mem"].set_value(snap["mem"], f"{snap['mem']:.0f}%")
        # GPU
        gpu = snap["gpu"]
        if gpu >= 0:
            self._left_h["bar_gpu"].set_value(gpu, f"{gpu:.0f}%")
        else:
            self._left_h["bar_gpu"].set_value(0, "N/A")
        # NET
        net = snap["net"]
        net_str = f"{net*1024:.0f}KB/s" if net < 1.0 else f"{net:.1f}MB/s"
        self._left_h["bar_net"].set_value(min(100, net * 10), net_str)
        # DISK
        self._left_h["bar_disk"].set_value(snap["disk"], f"{snap['disk']:.0f}%")
        # TMP
        tmp = snap["tmp"]
        if tmp >= 0:
            self._left_h["bar_tmp"].set_value(min(100, tmp), f"{tmp:.0f}°C")
        else:
            self._left_h["bar_tmp"].set_value(0, "N/A")

        # UP / PROC
        self._left_h["uptime_lbl"].setText(f"UP  {metrics_mod.boot_uptime_str()}")
        self._left_h["procs_lbl"].setText(f"PROC  {metrics_mod.proc_count()}")

        # Context budget bar
        try:
            from ..agent import _compute_context_budget
            cfg = self.worker.get_config()
            ctx = int(getattr(cfg, "context_size", 16384) or 16384)
            agent = self.worker.get_agent()
            est_chars = 0
            if agent and hasattr(agent, "history"):
                est_chars = sum(len(str(m.get("content") or "")) for m in agent.history[-40:])
            budget = _compute_context_budget(ctx)
            pct = min(100.0, 100 * est_chars / max(1, budget["history_chars"]))
            self._left_h["budget_bar"].set_value(pct, f"{est_chars/1000:.1f}K/{budget['history_chars']/1000:.0f}K")
        except Exception:
            pass

    # ------------------------------------------------------------------
    def _on_send(self, text: str) -> None:
        if not text.strip():
            return
        # Bloquear si el server esta booting
        if self._server_booting:
            self.log.append("Server is booting, please wait...", "warn")
            return
        # Fase V — bloquear envio si profile activo es STANDBY
        try:
            from ..profiles import get_active_profile
            if get_active_profile().name == "standby":
                self.log.append("Server offline — switch profile to chat.", "warn")
                return
        except Exception:
            pass
        # log appears in worker via log signal (you tag)
        if self._current_session is not None:
            from ..sessions import SessionTurn
            self._current_session.turns.append(SessionTurn(role="user", content=text))
        self.worker.submit(
            text,
            images=self._pending_attachments_img,
            audios=self._pending_attachments_aud,
        )
        self._pending_attachments_img.clear()
        self._pending_attachments_aud.clear()
        self._right_h["attach_hint"].setText("No attachments")

    def _on_log(self, text: str, tag: str) -> None:
        self.log.append(text, tag)

    def _on_connection_changed(self, ok: bool) -> None:
        self.hud.set_connected(ok)
        # also update brand badge color in header
        brand = self._header_h.get("brand_lbl")
        if brand is not None:
            color = C.GREEN if ok else C.RED
            brand.setStyleSheet(f"color: {color}; background: transparent;")
        # Sync persona + model into HUD now that the agent is reachable
        if ok:
            agent = self.worker.get_agent()
            if agent is not None:
                try:
                    self.hud.set_persona(agent.get_persona().get("persona", "default"))
                except Exception:
                    pass
            cfg = self.worker.get_config()
            if cfg is not None:
                model = getattr(cfg, "model", None) or "gemma-3n-e4b-it"
                self.hud.set_model(str(model))

    def _on_reply(self, content: str, events: list[Any]) -> None:
        if self._current_session is not None and self._session_store is not None:
            from ..sessions import SessionTurn, auto_title
            self._current_session.turns.append(SessionTurn(
                role="assistant", content=content or "", tool_count=len(events)
            ))
            if self._current_session.title == "(sin titulo)":
                try:
                    agent = self.worker.get_agent()
                    chat_fn = (lambda m: agent.client.chat(m, tools=None, enable_thinking=False,
                                                          parallel_tool_calls=False,
                                                          max_tokens=30, timeout_s=10.0)) if agent else None
                    last_user = next((t.content for t in self._current_session.turns[::-1] if t.role == "user"), "")
                    self._current_session.title = auto_title(last_user, chat_fn=chat_fn)
                except Exception:
                    pass
            self._session_store.save(self._current_session)
            self._update_footer_session()
        # Fase W — si la voz esta activa, hablar la respuesta + cerrar el turno
        # para que el controller vuelva a IDLE_LISTENING y acepte el proximo wake.
        if self._voice_controller is not None and content:
            try:
                # SPEAKING transient: alimentamos al TTS oracion por oracion
                self._voice_controller.begin_tts()
                self._voice_controller.feed_tts_chunk(content)
                self._voice_controller.end_tts()
            except Exception as exc:
                self.log.append(f"voice TTS dispatch failed: {exc}", "warn")
                # Forzar vuelta a idle aunque el TTS falle, para no quedar THINKING
                try:
                    self._voice_controller.disable()
                    self._voice_controller.enable()
                except Exception:
                    pass

    def _on_llm_error(self, msg: str) -> None:
        self.log.append(msg, "err")
        # Fase W — si la voz esta en THINKING esperando reply, sacarla a IDLE
        # para que el siguiente wake-word funcione.
        if self._voice_controller is not None:
            try:
                self._voice_controller.end_tts()
            except Exception:
                pass

    def _on_progress(self, event: str, payload: dict) -> None:
        # Reserved for future panels (timeline live view, etc.)
        pass

    # ------------------------------------------------------------------
    def _open_settings(self) -> None:
        agent = self.worker.get_agent()
        config = self.worker.get_config()
        cur_persona = "default"
        personas_avail: list[str] = []
        try:
            from .. import personas
            personas_avail = personas.list_names()
            if agent is not None:
                cur_persona = agent.get_persona().get("persona", "default")
        except Exception:
            pass

        dlg = SettingsDialog(
            agent_config=config,
            current_persona=cur_persona,
            personas_available=personas_avail,
            parent=self,
        )
        dlg.restart_clicked.connect(self._restart_worker)
        dlg.apply_clicked.connect(self._apply_settings_live)
        dlg.exec()

    def _apply_settings_live(self, data: dict) -> None:
        # Fase V — start/stop profile watcher according to auto-config
        try:
            auto = data.get("profiles_auto") or {}
            self._reconfigure_profile_watcher(auto)
        except Exception as exc:
            self.log.append(f"watcher reconfigure failed: {exc}", "err")

        # Fase W — start/stop voice controller when 'Enable voice' changes
        # ENTRE turnos. Sin este bloque solo se activaba en el boot inicial
        # via _maybe_enable_voice, no cuando el usuario marca el checkbox
        # mid-sesion y pega APPLY.
        try:
            voice_cfg = data.get("voice") or {}
            self._reconfigure_voice(voice_cfg)
        except Exception as exc:
            self.log.append(f"voice reconfigure failed: {exc}", "err")

        env = data.get("env") or {}
        agent = self.worker.get_agent()
        # Persona — applied to running agent + HUD.
        persona = env.get("GEMMA4_AGENT_PERSONA")
        if persona and agent is not None:
            try:
                agent.set_persona(persona)
                self.hud.set_persona(persona)
                self.log.append(f"persona -> {persona}", "sys")
            except Exception as exc:
                self.log.append(f"persona switch failed: {exc}", "err")
        # Model alias — refreshes HUD only; the running agent keeps its own model.
        model_alias = env.get("GEMMA4_AGENT_MODEL")
        if model_alias:
            self.hud.set_model(model_alias)
        # Agent mode / max_turns / safety can be applied live by rewriting the
        # frozen AgentConfig (it's a dataclass; we use dataclasses.replace).
        if agent is not None:
            from dataclasses import replace
            try:
                changes: dict[str, Any] = {}
                if env.get("GEMMA4_AGENT_MODE"):
                    changes["agent_mode"] = env["GEMMA4_AGENT_MODE"]
                if env.get("GEMMA4_AGENT_MAX_TURNS"):
                    changes["max_agent_turns"] = int(env["GEMMA4_AGENT_MAX_TURNS"])
                if env.get("GEMMA4_AGENT_SAFETY") is not None:
                    changes["enable_safety"] = env["GEMMA4_AGENT_SAFETY"].lower() in {"1", "true", "yes", "on"}
                if changes:
                    agent.config = replace(agent.config, **changes)
                    agent.tools.safety_enabled = agent.config.enable_safety
                    self.log.append(f"applied live: {', '.join(changes)}", "sys")
            except Exception as exc:
                self.log.append(f"live apply failed: {exc}", "err")

    def _restart_worker(self) -> None:
        self.log.append("Restarting agent...", "sys")
        old = self.worker
        # Disconnect all signals from the old worker so dangling slots don't
        # fire after we abandon it. Each disconnect is wrapped because Qt
        # raises if a connection was never established.
        for sig in (old.state_changed, old.log, old.connection_changed,
                    old.reply_ready, old.llm_error, old.progress):
            try:
                sig.disconnect()
            except TypeError:
                pass
        old.stop()
        old.wait(2000)
        # build a new worker
        self.worker = AgentWorker(self)
        self.worker.state_changed.connect(self.hud.set_state)
        self.worker.log.connect(self._on_log)
        self.worker.connection_changed.connect(self._on_connection_changed)
        self.worker.reply_ready.connect(self._on_reply)
        self.worker.llm_error.connect(self._on_llm_error)
        self.worker.progress.connect(self._on_progress)
        self.worker.start()

    def _open_triggers(self) -> None:
        agent = self.worker.get_agent()
        if agent is None:
            self.log.append("agent not ready — cannot open triggers", "err")
            return
        dlg = TriggersDialog(tool_exec=agent.tools.execute, parent=self)
        dlg.exec()

    def _open_memory(self) -> None:
        agent = self.worker.get_agent()
        if agent is None:
            self.log.append("agent not ready", "err")
            return
        dlg = MemoryDialog(agent_getter=self.worker.get_agent, parent=self)
        dlg.exec()

    def _open_tools(self) -> None:
        if self.worker.get_agent() is None:
            self.log.append("agent not ready", "err")
            return
        dlg = ToolExplorer(agent_getter=self.worker.get_agent, parent=self)
        dlg.exec()

    def _open_sessions(self) -> None:
        if self._session_store is None:
            self.log.append("sessions disabled (set GEMMA4_AGENT_SESSIONS=true)", "warn")
            return
        cw = self.centralWidget()
        if self._sessions_panel is None:
            self._sessions_panel = SessionsPanel(
                on_list_provider=lambda: self._session_store.list_sessions(limit=50) if self._session_store else [],
                on_load=self._load_session,
                on_new=self._new_session,
                on_delete=self._delete_session,
                on_rename=self._rename_session,
                parent=cw,
            )
            self._sessions_panel.closed.connect(self._close_sessions)
        else:
            self._sessions_panel.refresh()
        if cw is not None:
            self._sessions_panel.setGeometry(0, 60, 300, cw.height() - 80)
        self._sessions_panel.show()
        self._sessions_panel.raise_()

    def _close_sessions(self) -> None:
        if self._sessions_panel is not None:
            self._sessions_panel.hide()

    def _load_session(self, sid: str) -> None:
        if self._session_store is None:
            return
        loaded = self._session_store.load(sid)
        if loaded is None:
            self.log.append(f"session {sid} not found", "err")
            return
        self._current_session = loaded
        agent = self.worker.get_agent()
        if agent is not None:
            agent.clear()
        self.log.append(f"loaded session {sid} ({len(loaded.turns)} turns) — agent history reset", "ok")
        self.log.append(f"title: {loaded.title}", "sys")
        for t in loaded.turns[-8:]:
            self.log.append(f"  [{t.role}] {t.content[:120]}", "sys")
        self._update_footer_session()
        if self._sessions_panel is not None:
            self._sessions_panel.hide()

    def _new_session(self) -> None:
        if self._session_store is None:
            return
        self._current_session = self._Session_cls.new()
        agent = self.worker.get_agent()
        if agent is not None:
            agent.clear()
        self.log.append(f"new session {self._current_session.id}", "ok")
        self._update_footer_session()

    def _delete_session(self, sid: str) -> None:
        if self._session_store is None:
            return
        self._session_store.delete(sid)
        if self._current_session and self._current_session.id == sid:
            self._current_session = self._Session_cls.new()
            agent = self.worker.get_agent()
            if agent is not None:
                agent.clear()
            self._update_footer_session()

    def _rename_session(self, sid: str, new_title: str) -> None:
        if self._session_store is None:
            return
        s = self._session_store.load(sid)
        if s is None:
            return
        s.title = new_title
        self._session_store.save(s)
        if self._current_session and self._current_session.id == sid:
            self._current_session.title = new_title
            self._update_footer_session()

    def _update_footer_session(self) -> None:
        sess_lbl = self._footer_h.get("sess_lbl")
        if sess_lbl is not None and self._current_session is not None:
            sess_lbl.setText(f"session: {self._current_session.id}  ·  {self._current_session.title[:32]}")

    # ------------------------------------------------------------------
    def _attach_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Attach image", str(Path.home()),
            "Images (*.png *.jpg *.jpeg *.webp *.bmp *.gif);;All (*)",
        )
        if not path:
            return
        self._pending_attachments_img.append(path)
        self._right_h["attach_hint"].setText(
            f"{len(self._pending_attachments_img)} image(s) attached: " +
            ", ".join(Path(p).name for p in self._pending_attachments_img)
        )
        self.log.append(f"image attached: {Path(path).name}", "file")

    def _toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def _clear_log(self) -> None:
        self.log.clear_log()
        self.log.append("log cleared", "sys")

    # ------------------------------------------------------------------
    # Fase V — VRAM profiles
    # ------------------------------------------------------------------
    def _wire_profile_buttons(self) -> None:
        """Conecta los 4 botones del selector con _on_profile_button_clicked."""
        buttons: dict[str, Any] = self._left_h.get("profile_buttons") or {}
        for full_name, btn in buttons.items():
            # Lambdas capturan el nombre por argumento por defecto
            btn.clicked.connect(lambda _=False, n=full_name: self._on_profile_button_clicked(n))
            # Tooltip
            try:
                from ..profiles import PROFILES
                p = PROFILES[full_name]
                btn.setToolTip(
                    f"{p.display_name}  -  ~{p.est_vram_mb} MB est.\n\n{p.description}\n\n"
                    "Hotkey: Ctrl+Shift+G para ciclar."
                )
            except Exception:
                pass

    def _refresh_profile_selector(self) -> None:
        """Pinta el boton activo y los demas mas apagados."""
        try:
            from ..profiles import get_active_profile
            active = get_active_profile().name
        except Exception:
            active = "balanced"
        buttons: dict[str, Any] = self._left_h.get("profile_buttons") or {}
        for full_name, btn in buttons.items():
            is_active = (full_name == active)
            if is_active:
                btn.setStyleSheet(
                    f"QPushButton {{ background: {C.PANEL2}; color: {C.PRI}; "
                    f"border: 1px solid {C.PRI}; border-radius: 2px; padding: 2px; }}"
                )
            else:
                btn.setStyleSheet(
                    f"QPushButton {{ background: {C.PANEL2}; color: {C.TEXT_DIM}; "
                    f"border: 1px solid {C.BORDER}; border-radius: 2px; padding: 2px; }}"
                    f"QPushButton:hover {{ color: {C.PRI}; border-color: {C.BORDER_A}; }}"
                )

    def _on_profile_button_clicked(self, name: str) -> None:
        """Click en una pildora -> aplica perfil con confirmacion solo para STANDBY."""
        from ..profiles import PROFILES, get_active_profile

        if name not in PROFILES:
            return
        profile = PROFILES[name]
        current = get_active_profile().name
        if current == name:
            self.log.append(f"profile already active: {profile.display_name}", "sys")
            return

        # Solo STANDBY pide confirmacion
        if name == "standby":
            reply = QMessageBox.question(
                self, "Standby?",
                "Esto apagara llama-server. La GUI sigue viva pero el chat dejara "
                "de responder. Cualquier mensaje mostrara 'Server offline'.\n\nContinuar?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        # Light con modelo chico ausente -> warning amber + fallback
        if name == "light":
            try:
                from ..profiles import light_model_configured, light_model_missing
                if light_model_missing():
                    path = light_model_configured() or "(no configurado)"
                    QMessageBox.warning(
                        self, "Light model missing",
                        f"Light profile pide un GGUF chico (ej. gemma-3n-e2b-it.Q4_K_M.gguf) "
                        f"en:\n  {path}\n\n"
                        "El archivo no existe. Voy a aplicar el perfil igual usando tu modelo "
                        "principal con context=4096 como fallback. Para usar el modelo chico "
                        "real: bajalo y poneo en esa ruta, o cambia la ruta en "
                        "Settings -> PROFILES.",
                    )
                    self.log.append(
                        f"WARNING light_model_path missing ({path}); falling back to main model with ctx=4096",
                        "warn",
                    )
            except Exception:
                pass

        self._apply_profile(name)

    def _apply_profile(self, name: str) -> None:
        """Persiste perfil + aplica env vars + reinicia server y worker."""
        from ..profiles import (
            PROFILES, apply_profile_to_env, get_active_profile, set_active_profile,
        )
        if name not in PROFILES:
            return
        try:
            set_active_profile(name)
        except (ValueError, OSError) as exc:
            self.log.append(f"profile persist failed: {exc}", "err")
            return
        profile = get_active_profile()
        apply_profile_to_env(profile)
        self.log.append(f"profile -> {profile.display_name} (ctx={profile.context_size})", "sys")

        # Server: stop/start segun server_running. NO matamos servers externos.
        try:
            from ..llama_server import LlamaServerManager, port_in_use
            if self._llama_manager is None:
                cfg = self.worker.get_config()
                self._llama_manager = LlamaServerManager(config=cfg)
            mgr = self._llama_manager
            if not profile.server_running:
                # Standby -> apagar server (si nuestro). External no se toca.
                if mgr.is_external_server() or (not mgr.is_running() and port_in_use()):
                    self.log.append(
                        "external llama-server detected; profile flags will NOT reach it",
                        "warn",
                    )
                else:
                    mgr.stop()
                self.hud.set_state("OFFLINE")
            else:
                # Hay que (re)arrancar con flags del perfil. Si hay externo, respetar.
                if port_in_use() and not mgr.is_running():
                    self.log.append(
                        "external llama-server detected on :8080; applying env vars and "
                        "restarting worker, but NOT restarting the external server",
                        "warn",
                    )
                    # Tarea 2 — check context mismatch
                    try:
                        from ..llama_server import get_external_server_context
                        ext_ctx = get_external_server_context()
                        if ext_ctx is not None and ext_ctx < int(profile.context_size):
                            self.log.append(
                                f"external server has -c={ext_ctx} but profile "
                                f"{profile.name} asks for {profile.context_size}; "
                                "long prompts will be truncated by the server",
                                "warn",
                            )
                    except Exception:
                        pass
                else:
                    mgr.restart(profile, wait_health=False)
                    # mgr.restart() puede haber detectado externo durante el restart;
                    # surface el mismatch msg si quedo seteado en el manager.
                    try:
                        if mgr.is_external_server():
                            msg = mgr.external_context_mismatch_msg()
                            if msg:
                                self.log.append(msg, "warn")
                    except Exception:
                        pass
                self.hud.set_state("IDLE")
        except Exception as exc:
            self.log.append(f"server transition failed: {exc}", "err")

        # Restart worker para que el agente recoja los nuevos env vars
        try:
            self._restart_worker()
        except Exception as exc:
            self.log.append(f"worker restart failed: {exc}", "err")

        self._refresh_profile_selector()
        self._refresh_chat_input_blocked()

        # Fase W — voice on PERF/BAL, off en LIGHT/STDBY (respeta override manual)
        try:
            from .settings import load_persisted
            voice_cfg = (load_persisted().get("voice") or {})
            user_wants_voice = bool(voice_cfg.get("enabled"))
            profile_allows = profile.server_running and profile.name in {"performance", "balanced"}
            if profile_allows and user_wants_voice and self._voice_controller is None:
                self._start_voice_controller(voice_cfg)
            elif not profile_allows and self._voice_controller is not None:
                self._stop_voice_controller()
        except Exception as exc:
            self.log.append(f"voice profile-sync failed: {exc}", "warn")

    # ------------------------------------------------------------------
    # Fase W — voice integration
    # ------------------------------------------------------------------

    def _maybe_enable_voice(self) -> None:
        """Si el usuario habilito voice en gui.json y el perfil lo permite, arranca."""
        try:
            from .settings import load_persisted
            from ..profiles import get_active_profile
            voice_cfg = (load_persisted().get("voice") or {})
            if not voice_cfg.get("enabled"):
                return
            if not get_active_profile().server_running:
                # LIGHT con server off / STANDBY -> no arrancar voz
                return
        except Exception as exc:
            self.log.append(f"voice config read failed: {exc}", "err")
            return
        self._start_voice_controller(voice_cfg)

    def _start_voice_controller(self, voice_cfg: dict[str, Any]) -> None:
        if self._voice_controller is not None:
            return
        try:
            from ..voice.controller import VoiceController
        except Exception as exc:
            self.log.append(f"voice module unavailable: {exc}", "err")
            return
        # Bridge VOICE-tab selectors to the env vars consumed by StreamingSTT /
        # StreamingTTS at __init__ time. Without this, the user can pick a
        # different STT model or TTS voice in Settings and APPLY would persist
        # the choice but never apply it to the running runtime.
        stt_model = voice_cfg.get("stt_model")
        if stt_model:
            os.environ["GEMMA4_VOICE_STT_MODEL"] = str(stt_model)
        tts_voice = voice_cfg.get("tts_voice")
        if tts_voice:
            os.environ["GEMMA4_VOICE_TTS_VOICE"] = str(tts_voice)
        # Crear bridge ANTES del controller. Sus signals viven en main thread
        # (porque self es el parent = MainWindow). Cross-thread auto-marshall.
        self._voice_bridge = VoiceBridge(self)
        self._voice_bridge.state_changed.connect(self._on_voice_state_main)
        self._voice_bridge.partial.connect(self._on_voice_partial_main)
        self._voice_bridge.final.connect(self._on_voice_final_main)
        self._voice_bridge.failed.connect(self._on_voice_failed_main)
        bridge = self._voice_bridge  # captura por closure
        try:
            controller = VoiceController(
                on_state=lambda s: bridge.state_changed.emit(s),
                on_partial=lambda t: bridge.partial.emit(t),
                on_final=lambda t: bridge.final.emit(t),
                on_tts_chunk=None,
                on_failed=lambda r: bridge.failed.emit(r),
                followup_seconds=float(voice_cfg.get("followup_seconds") or 0.0),
                close_phrases=voice_cfg.get("close_phrases") or (),
                beep_on_wake=bool(voice_cfg.get("feedback_beep", True)),
                device=voice_cfg.get("input_device"),
            )
            controller.set_tts_muted(bool(voice_cfg.get("tts_muted", False)))
        except Exception as exc:
            self.log.append(f"voice controller create failed: {exc}", "err")
            return
        self._voice_controller = controller
        self.log.append("voice: enabling (Vosk + faster-whisper + Piper loading...)", "sys")
        # Cargar en thread aparte para no bloquear GUI (la carga puede tomar 1-3s)
        from PyQt6.QtCore import QThread
        class _Loader(QThread):
            def __init__(self, ctrl, parent):  # noqa: ANN001
                super().__init__(parent)
                self.ctrl = ctrl
                self.ok = False
            def run(self) -> None:
                self.ok = self.ctrl.enable()
        loader = _Loader(controller, self)
        def _done() -> None:
            if loader.ok:
                self.log.append("voice: ready (say 'gemma' or 'hey gemma')", "ok")
            else:
                self.log.append("voice: failed to enable; check logs", "err")
                comps = controller.get_failed_components()
                for c in comps:
                    self.log.append(f"voice: {c}", "warn")
        loader.finished.connect(_done)
        loader.start()
        self._voice_loader = loader  # keep alive

    def _reconfigure_voice(self, voice_cfg: dict[str, Any]) -> None:
        """Aplica cambios de voice config en vivo (mid-sesion).

        Triggered desde _apply_settings_live cuando el usuario pega APPLY
        en el tab VOICE. Maneja 3 casos:
          1. user marco enabled=True y no hay controller -> arrancarlo
             (si el perfil lo permite).
          2. user desmarco enabled=False y hay controller -> pararlo.
          3. user dejo enabled=True y el controller corre -> aplicar
             cambios live de mute_tts (sin restart).
        """
        user_wants = bool(voice_cfg.get("enabled"))
        running = self._voice_controller is not None
        try:
            from ..profiles import get_active_profile
            profile_allows = get_active_profile().server_running
        except Exception:
            profile_allows = True

        if user_wants and not running and profile_allows:
            self._start_voice_controller(voice_cfg)
            return
        if not user_wants and running:
            self._stop_voice_controller()
            return
        # If stt_model or tts_voice changed, we must rebuild the controller —
        # StreamingSTT/StreamingTTS read those env vars only in __init__.
        if running and profile_allows:
            new_stt = str(voice_cfg.get("stt_model") or "").strip()
            new_tts = str(voice_cfg.get("tts_voice") or "").strip()
            cur_stt = os.environ.get("GEMMA4_VOICE_STT_MODEL", "").strip()
            cur_tts = os.environ.get("GEMMA4_VOICE_TTS_VOICE", "").strip()
            if (new_stt and new_stt != cur_stt) or (new_tts and new_tts != cur_tts):
                self.log.append("voice: STT/TTS model changed -> restart controller", "sys")
                self._stop_voice_controller()
                self._start_voice_controller(voice_cfg)
                return
        if running and self._voice_controller is not None:
            # Solo aplicar lo que se puede sin restart: mute TTS y follow-up window
            try:
                self._voice_controller.set_tts_muted(bool(voice_cfg.get("tts_muted", False)))
            except Exception:
                pass
            try:
                self._voice_controller.set_followup_seconds(
                    float(voice_cfg.get("followup_seconds") or 0.0)
                )
            except Exception:
                pass
            try:
                self._voice_controller.set_close_phrases(voice_cfg.get("close_phrases") or ())
            except Exception:
                pass

    def _stop_voice_controller(self) -> None:
        if self._voice_controller is None:
            return
        try:
            self._voice_controller.shutdown()
        except Exception as exc:
            self.log.append(f"voice shutdown error: {exc}", "warn")
        self._voice_controller = None
        if self._voice_bridge is not None:
            try:
                self._voice_bridge.deleteLater()
            except Exception:
                pass
            self._voice_bridge = None
        self.log.append("voice: disabled", "sys")

    def _on_voice_state_main(self, state: str) -> None:
        """Recibido en main thread via signal -- seguro tocar la GUI directo."""
        self._voice_state = state
        hud_map = {
            "IDLE_LISTENING": "IDLE",
            "WAKE_DETECTED": "LISTENING",
            "LISTENING": "LISTENING",
            "TRANSCRIBING": "PROCESSING",
            "THINKING": "THINKING",
            "SPEAKING": "SPEAKING",
            "FOLLOWUP": "LISTENING",
            "IDLE_DISABLED": "IDLE",
            "FAILED": "ERROR",
        }
        hud_state = hud_map.get(state, "IDLE")
        try:
            self.hud.set_state(hud_state)
        except Exception:
            pass
        self.log.append(f"voice -> {state}", "sys")

    def _on_voice_partial_main(self, text: str) -> None:
        try:
            inp = self._right_h.get("input")
            if inp is not None:
                inp.setPlaceholderText(f"  …{text}")
        except Exception:
            pass

    def _on_voice_final_main(self, text: str) -> None:
        """Signal main thread -> el STT entrego texto final -> mandar al agente."""
        import logging as _logging
        _logging.getLogger("gemma4_agent.ui.main_window").info(
            "_on_voice_final_main got text=%r (in GUI thread)", text,
        )
        # Filtro anti-alucinacion de Whisper: textos cortos sin acento real
        # ("Suscribete", "Gracias por ver", "subtitulos", etc) son frecuentes
        # con audio corto/ruidoso. Los descartamos para no enviar basura al LLM.
        if _is_whisper_hallucination(text):
            self.log.append(f"voice heard (descartado, posible alucinacion): {text}", "warn")
            # Fix BUG-J: el controller quedo en THINKING. Hay que liberarlo
            # para que el proximo wake-word funcione. end_tts() sin
            # feed_tts_chunk va directo a FOLLOWUP/IDLE_LISTENING.
            if self._voice_controller is not None:
                try:
                    self._voice_controller.end_tts()
                except Exception:
                    pass
            return
        self.log.append(f"voice heard: {text}", "user")
        try:
            inp = self._right_h.get("input")
            if inp is not None:
                inp.setPlaceholderText("Talk to GEMMA4...")
        except Exception:
            pass
        self._on_send(text)

    def _on_voice_failed_main(self, reason: str) -> None:
        self.log.append(f"voice failed: {reason}", "err")
        if self._voice_controller is not None:
            try:
                if getattr(self, "_voice_state", None) in ("TRANSCRIBING", "THINKING"):
                    self._voice_controller.end_tts()
            except Exception:
                pass

    def _maybe_autostart_server(self) -> None:
        """Arranca llama-server si: perfil != STANDBY, no hay server vivo,
        y no hay un boot ya en curso.

        Llamado 50ms despues de mostrar la GUI para que el primer paint termine
        antes de que el QThread del server compita por CPU.
        """
        if self._server_booting:
            return
        try:
            from ..llama_server import port_in_use
            from ..profiles import get_active_profile
        except Exception as exc:
            self.log.append(f"autostart: import failed: {exc}", "err")
            return

        profile = get_active_profile()
        if not profile.server_running:
            # STANDBY: dejar OFFLINE como esta
            self.hud.set_state("OFFLINE")
            return

        if port_in_use():
            # Ya hay algo (nuestro previo o externo). No bootear.
            self.log.append(
                "llama-server already responding on :8080; not booting",
                "sys",
            )
            self.hud.set_state("IDLE")
            return

        # Boot real
        self._server_booting = True
        self.hud.set_state("INITIALISING")
        self._refresh_chat_input_blocked()
        self._server_boot_thread = ServerBootWorker(self)
        self._server_boot_thread.log.connect(self._on_log)
        self._server_boot_thread.finished_with_result.connect(self._on_server_boot_finished)
        self._server_boot_thread.start()

    def _on_server_boot_finished(self, result: str) -> None:
        self._server_booting = False
        # Liberar referencia al thread para que se limpie
        thread = self._server_boot_thread
        self._server_boot_thread = None
        if thread is not None:
            try:
                thread.wait(500)
            except Exception:
                pass

        if result == "started" or result == "external" or result == "already_running":
            self.hud.set_state("IDLE")
        elif result == "skipped_standby":
            self.hud.set_state("OFFLINE")
        elif result in {"timeout", "missing_files"}:
            self.hud.set_state("ERROR")
        else:
            self.hud.set_state("IDLE")
        self._refresh_chat_input_blocked()

    def _refresh_chat_input_blocked(self) -> None:
        """Actualiza el placeholder del input + (des)habilitacion segun estado del server."""
        try:
            input_widget = self._right_h.get("input")
            send_btn = self._right_h.get("send_btn")
        except Exception:
            return
        if self._server_booting:
            if input_widget is not None:
                input_widget.setEnabled(False)
                input_widget.setPlaceholderText("Server is booting, please wait...")
            if send_btn is not None:
                send_btn.setEnabled(False)
            return
        # No booteando: estado normal segun perfil
        try:
            from ..profiles import get_active_profile
            is_standby = (get_active_profile().name == "standby")
        except Exception:
            is_standby = False
        if input_widget is not None:
            input_widget.setEnabled(not is_standby)
            input_widget.setPlaceholderText(
                "Server offline — switch profile to chat" if is_standby
                else "Talk to GEMMA4..."
            )
        if send_btn is not None:
            send_btn.setEnabled(not is_standby)

    def _reconfigure_profile_watcher(self, auto_cfg: dict[str, Any]) -> None:
        """Aplica config de auto-switch: arranca o para el thread del watcher."""
        from ..profile_watcher import ProfileWatcher, WatcherConfig

        # Stop existente si lo hay
        if self._profile_watcher is not None:
            try:
                self._profile_watcher.stop(timeout_s=2.0)
            except Exception:
                pass
            self._profile_watcher = None

        if not auto_cfg.get("enabled"):
            self.log.append("auto-switch watcher: disabled", "sys")
            return

        cfg = WatcherConfig(
            enabled=True,
            downgrade_to=str(auto_cfg.get("downgrade_to") or "light"),
            restore_to=str(auto_cfg.get("restore_to") or "balanced"),
            game_watchlist=list(auto_cfg.get("game_watchlist") or []),
            trigger_on_game=bool(auto_cfg.get("trigger_on_game", True)),
            trigger_on_gpu=bool(auto_cfg.get("trigger_on_gpu", False)),
            trigger_on_ram=bool(auto_cfg.get("trigger_on_ram", False)),
        )
        self._profile_watcher = ProfileWatcher(cfg, on_change=self._on_watcher_change)
        self._profile_watcher.start()
        self.log.append(
            f"auto-switch watcher: enabled (down->{cfg.downgrade_to} on triggers, up->{cfg.restore_to})",
            "sys",
        )

    def _on_watcher_change(self, name: str, reason: str) -> None:
        """Callback del thread watcher. Llamado desde thread no-GUI.

        Solo loggea y refresca el selector. NO arrancamos llama-server desde
        aca para no bloquear el thread; el usuario vera el cambio al proximo
        request (env vars ya estan aplicados).
        """
        # Marshalling a GUI thread: schedule a QTimer 0-shot
        from PyQt6.QtCore import QTimer
        def _do() -> None:
            self.log.append(f"watcher -> {name} ({reason})", "sys")
            self._refresh_profile_selector()
        QTimer.singleShot(0, _do)

    def _cycle_profile(self) -> None:
        """Ctrl+Shift+G: PERF -> BAL -> LIGHT -> STDBY -> PERF."""
        from PyQt6.QtWidgets import QToolTip
        from ..profiles import PROFILE_NAMES, get_active_profile
        order: list[str] = [str(n) for n in PROFILE_NAMES]
        current = get_active_profile().name
        try:
            idx = order.index(current)
        except ValueError:
            idx = 0
        nxt = order[(idx + 1) % len(order)]
        # Aplicar pasa por el handler estandar (incluye confirm de STANDBY)
        self._on_profile_button_clicked(nxt)
        # Feedback visual: tooltip flotante 2s
        try:
            from PyQt6.QtCore import QPoint
            pos = self.mapToGlobal(QPoint(self.width() // 2, 80))
            QToolTip.showText(pos, f"Profile: {nxt.upper()}", self)
        except Exception:
            pass

    # ------------------------------------------------------------------
    def closeEvent(self, a0: Any) -> None:  # type: ignore[override]
        try:
            self._metrics.stop()
        except Exception:
            pass
        # Fase V — stop watcher cleanly
        try:
            if self._profile_watcher is not None:
                self._profile_watcher.stop(timeout_s=2.0)
        except Exception:
            pass
        # Stop server boot thread cleanly (no force-kill; espera breve)
        try:
            if self._server_boot_thread is not None and self._server_boot_thread.isRunning():
                self._server_boot_thread.wait(2000)
        except Exception:
            pass
        # Fase W — shutdown voice
        try:
            self._stop_voice_controller()
        except Exception:
            pass
        try:
            self.worker.stop()
            self.worker.wait(1500)
        except Exception:
            pass
        super().closeEvent(a0)

    def resizeEvent(self, a0: Any) -> None:  # type: ignore[override]
        super().resizeEvent(a0)
        if self._sessions_panel is not None and self._sessions_panel.isVisible():
            cw = self.centralWidget()
            if cw is not None:
                self._sessions_panel.setGeometry(0, 60, 300, cw.height() - 80)
