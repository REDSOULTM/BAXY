"""Main window — assembles header, side panels, HUD canvas, footer.

Handles modal dialogs (settings, triggers, memory, tools, sessions panel).
Owns the AgentWorker thread and wires its signals to the UI.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QSize, Qt, QTimer
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

    def _on_llm_error(self, msg: str) -> None:
        self.log.append(msg, "err")

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
    def closeEvent(self, a0: Any) -> None:  # type: ignore[override]
        try:
            self._metrics.stop()
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
