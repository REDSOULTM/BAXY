"""Settings dialog — everything configurable.

Tabs:
  CONNECTION  llama-server URL, model path, max tokens, context size
  AGENT       mode, persona, max turns
  TOGGLES     env-var toggles for J1-J5 + K1-K3 features
  PATHS       memory.json, trace.jsonl, sessions dir, timeline dir
  PROMPT      view and override SYSTEM_PROMPT (read-only by default)
  ABOUT       version, build info, links

Changes are written to a `~/.gemma4/gui.json` file and to os.environ at
runtime. The agent must be restarted to pick up server/model/path changes
— a "Restart agent" button is provided at the bottom.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QFrame, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton,
    QSpinBox, QTabWidget, QVBoxLayout, QWidget,
)

from .theme import (
    C, button_qss, combo_qss, line_edit_qss, mono, panel_qss, text_edit_qss,
)


SETTINGS_PATH = Path.home() / ".gemma4" / "gui.json"


# Env-var toggles surfaced in the UI. Each is (env_name, label, default_on).
TOGGLES = [
    ("GEMMA4_AGENT_FACT_EXTRACTION",    "J2 Fact extraction (post-turn)",       False),
    ("GEMMA4_KNOWLEDGE_RERANK",         "J1 Cross-encoder rerank in knowledge.search", True),
    ("GEMMA4_AGENT_PARALLEL_TOOLS",     "J5 Parallel tool execution",            False),
    ("GEMMA4_AGENT_PROJECT_CONTEXT",    "J4 Auto-load project context",          True),
    ("GEMMA4_AGENT_SESSIONS",           "K1 Persistent chat sessions",           True),
    ("GEMMA4_AGENT_TIMELINE",           "K2 Tool timeline JSONL export",         True),
    ("GEMMA4_AGENT_SUMMARIZATION",      "G2 LLM-summarization compaction",       True),
    ("GEMMA4_AGENT_TRACING",            "Tracing to JSONL (trace.jsonl)",        True),
]


def load_persisted() -> dict:
    if not SETTINGS_PATH.is_file():
        return {}
    try:
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_persisted(data: dict) -> None:
    try:
        from ..state import atomic_write_json
        atomic_write_json(SETTINGS_PATH, data)
    except OSError:
        pass


def apply_to_env(data: dict) -> None:
    """Push values to os.environ so the next agent init reads them."""
    env = data.get("env") or {}
    for k, v in env.items():
        if v in (None, ""):
            os.environ.pop(str(k), None)
        else:
            os.environ[str(k)] = str(v)
    # toggles
    toggles = data.get("toggles") or {}
    for k, v in toggles.items():
        os.environ[str(k)] = "true" if v else "false"


class SettingsDialog(QDialog):
    apply_clicked = pyqtSignal(dict)
    restart_clicked = pyqtSignal()

    def __init__(
        self,
        *,
        agent_config: object | None = None,
        current_persona: str = "default",
        personas_available: list[str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("GEMMA4  ·  SETTINGS")
        self.setMinimumSize(720, 560)
        self._agent_config = agent_config
        self._cur_persona = current_persona
        self._personas = personas_available or ["default", "coder", "researcher", "creative", "planner", "casual"]
        self.setStyleSheet(f"""
            QDialog {{ background: {C.BG}; }}
            QLabel {{ color: {C.TEXT}; }}
            QTabWidget::pane {{ border: 1px solid {C.BORDER}; background: {C.PANEL}; }}
            QTabBar::tab {{
                background: {C.DARK};
                color: {C.TEXT_DIM};
                padding: 6px 16px;
                margin-right: 1px;
                border: 1px solid {C.BORDER};
                border-bottom: none;
                font-family: 'Courier New';
                font-size: 8pt;
                font-weight: bold;
            }}
            QTabBar::tab:selected {{
                background: {C.PANEL};
                color: {C.PRI};
                border-bottom: 1px solid {C.PANEL};
            }}
            QCheckBox {{ color: {C.TEXT}; spacing: 8px; font-family: 'Consolas'; font-size: 9pt; }}
            QSpinBox {{ background: #000d14; color: {C.TEXT}; border: 1px solid {C.BORDER};
                       border-radius: 3px; padding: 3px; }}
        """)
        self._build()

    def _build(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        # Title
        title = QLabel("◈  CONFIGURATION  —  ALL SUBSYSTEMS")
        title.setFont(mono(12, True))
        title.setStyleSheet(f"color: {C.PRI}; padding-bottom: 6px; border-bottom: 1px solid {C.BORDER};")
        lay.addWidget(title)

        tabs = QTabWidget()
        tabs.addTab(self._tab_connection(),    "CONNECTION")
        tabs.addTab(self._tab_agent(),         "AGENT")
        tabs.addTab(self._tab_sampling(),      "SAMPLING")
        tabs.addTab(self._tab_behaviour(),     "BEHAVIOUR")
        tabs.addTab(self._tab_voice(),         "VOICE")
        tabs.addTab(self._tab_profiles(),      "PROFILES")
        tabs.addTab(self._tab_optim(),         "OPTIM")
        tabs.addTab(self._tab_toggles(),       "TOGGLES")
        tabs.addTab(self._tab_paths(),         "PATHS")
        tabs.addTab(self._tab_prompt(),        "PROMPT")
        tabs.addTab(self._tab_about(),         "ABOUT")
        lay.addWidget(tabs, stretch=1)

        # Footer buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        restart = QPushButton("⟳  RESTART AGENT")
        restart.setStyleSheet(button_qss(primary=True))
        restart.setFixedHeight(32)
        restart.setCursor(Qt.CursorShape.PointingHandCursor)
        restart.clicked.connect(self._on_restart)
        btn_row.addWidget(restart)

        cancel = QPushButton("CANCEL")
        cancel.setStyleSheet(button_qss())
        cancel.setFixedHeight(32)
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)

        apply = QPushButton("APPLY")
        apply.setStyleSheet(button_qss(primary=True))
        apply.setFixedHeight(32)
        apply.clicked.connect(self._on_apply)
        btn_row.addWidget(apply)
        lay.addLayout(btn_row)

    # ------------------------------------------------------------------
    def _tab_connection(self) -> QWidget:
        w = QWidget()
        lay = QFormLayout(w)
        lay.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        cfg = self._agent_config

        self._server_url = QLineEdit(str(getattr(cfg, "server_url", "http://127.0.0.1:8080")))
        self._server_url.setStyleSheet(line_edit_qss())
        self._server_url.setFont(mono(9))
        lay.addRow(self._lbl("llama-server URL"), self._server_url)

        self._model_alias = QLineEdit(str(os.environ.get("GEMMA4_AGENT_MODEL") or ""))
        self._model_alias.setStyleSheet(line_edit_qss())
        self._model_alias.setFont(mono(9))
        self._model_alias.setPlaceholderText("optional alias — e.g. gemma-3-e4b-it.Q6_K")
        lay.addRow(self._lbl("Model alias"), self._model_alias)

        self._gguf_path = QLineEdit(str(os.environ.get("GEMMA4_MODEL_PATH") or ""))
        self._gguf_path.setStyleSheet(line_edit_qss())
        self._gguf_path.setPlaceholderText(".gguf path — passed to launcher / used by agent.config")
        gguf_row = QHBoxLayout()
        gguf_row.addWidget(self._gguf_path, stretch=1)
        browse = QPushButton("...")
        browse.setFixedWidth(32)
        browse.setStyleSheet(button_qss())
        browse.clicked.connect(self._browse_gguf)
        gguf_row.addWidget(browse)
        wrap = QWidget(); wrap.setLayout(gguf_row)
        lay.addRow(self._lbl("GGUF path"), wrap)

        self._ctx_size = QSpinBox()
        self._ctx_size.setRange(1024, 1_000_000)
        self._ctx_size.setSingleStep(1024)
        self._ctx_size.setValue(int(getattr(cfg, "context_size", 16384) or 16384))
        lay.addRow(self._lbl("Context size (tokens)"), self._ctx_size)

        self._max_tokens = QSpinBox()
        self._max_tokens.setRange(64, 32768)
        self._max_tokens.setValue(int(getattr(cfg, "max_tokens", 1024) or 1024))
        lay.addRow(self._lbl("max_tokens per reply"), self._max_tokens)

        info = QLabel(
            "Tip: the agent talks to a llama-server you start separately.\n"
            "Changes here require RESTART AGENT to take effect."
        )
        info.setFont(mono(8))
        info.setStyleSheet(f"color: {C.TEXT_DIM};")
        lay.addRow(info)

        return w

    def _browse_gguf(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select GGUF model", str(Path.home()), "GGUF (*.gguf);;All (*)")
        if path:
            self._gguf_path.setText(path)

    # ------------------------------------------------------------------
    def _tab_agent(self) -> QWidget:
        w = QWidget()
        lay = QFormLayout(w)
        lay.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        cfg = self._agent_config

        self._mode_combo = QComboBox()
        self._mode_combo.setStyleSheet(combo_qss())
        for m in ("auto", "fast_action", "deep_action", "research", "vision_action", "audio_mode"):
            self._mode_combo.addItem(m)
        self._mode_combo.setCurrentText(str(getattr(cfg, "agent_mode", "auto") or "auto"))
        lay.addRow(self._lbl("Agent mode"), self._mode_combo)

        self._persona_combo = QComboBox()
        self._persona_combo.setStyleSheet(combo_qss())
        for p in self._personas:
            self._persona_combo.addItem(p)
        self._persona_combo.setCurrentText(self._cur_persona)
        lay.addRow(self._lbl("Persona"), self._persona_combo)

        self._max_turns = QSpinBox()
        self._max_turns.setRange(1, 64)
        self._max_turns.setValue(int(getattr(cfg, "max_agent_turns", 10) or 10))
        lay.addRow(self._lbl("Max turns per request"), self._max_turns)

        self._enable_safety = QCheckBox("Safety filter on")
        self._enable_safety.setChecked(bool(getattr(cfg, "enable_safety", False)))
        lay.addRow(self._lbl(""), self._enable_safety)

        warn = QLabel(
            "⚠ Safety OFF means destructive tools (filesystem.delete, terminal\n"
            "with risky commands, registry add/delete, system shutdown, package\n"
            "install/uninstall, etc.) run WITHOUT confirmation. Recommended ON\n"
            "for unattended sessions; OFF only if you trust every prompt you give\n"
            "and you watch every turn."
        )
        warn.setFont(mono(8))
        warn.setStyleSheet(f"color: {C.ACC2};")
        warn.setWordWrap(True)
        lay.addRow(warn)

        return w

    # ------------------------------------------------------------------
    def _tab_sampling(self) -> QWidget:
        w = QWidget()
        lay = QFormLayout(w)
        lay.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        cfg = self._agent_config

        info = QLabel(
            "Sampling parameters passed to llama-server. Lower temperature\n"
            "gives more deterministic output. top_p+top_k narrow the candidate\n"
            "pool. min_p prunes low-probability tokens after temperature."
        )
        info.setFont(mono(8))
        info.setStyleSheet(f"color: {C.TEXT_DIM};")
        lay.addRow(info)

        from PyQt6.QtWidgets import QDoubleSpinBox

        self._temperature = QDoubleSpinBox()
        self._temperature.setRange(0.0, 2.0)
        self._temperature.setSingleStep(0.05)
        self._temperature.setValue(float(os.environ.get("GEMMA4_AGENT_TEMPERATURE") or getattr(cfg, "temperature", None) or 1.0))
        lay.addRow(self._lbl("temperature"), self._temperature)

        self._top_p = QDoubleSpinBox()
        self._top_p.setRange(0.0, 1.0)
        self._top_p.setSingleStep(0.05)
        self._top_p.setValue(float(os.environ.get("GEMMA4_AGENT_TOP_P") or getattr(cfg, "top_p", None) or 0.95))
        lay.addRow(self._lbl("top_p"), self._top_p)

        self._top_k = QSpinBox()
        self._top_k.setRange(0, 200)
        self._top_k.setValue(int(os.environ.get("GEMMA4_AGENT_TOP_K") or getattr(cfg, "top_k", None) or 64))
        lay.addRow(self._lbl("top_k"), self._top_k)

        self._min_p = QDoubleSpinBox()
        self._min_p.setRange(0.0, 1.0)
        self._min_p.setSingleStep(0.01)
        cfg_min_p = getattr(cfg, "min_p", None)
        self._min_p.setValue(float(os.environ.get("GEMMA4_AGENT_MIN_P") or cfg_min_p or 0.0))
        lay.addRow(self._lbl("min_p (0 = disabled)"), self._min_p)

        self._repeat_penalty = QDoubleSpinBox()
        self._repeat_penalty.setRange(0.5, 2.0)
        self._repeat_penalty.setSingleStep(0.05)
        self._repeat_penalty.setValue(float(os.environ.get("GEMMA4_AGENT_REPEAT_PENALTY") or getattr(cfg, "repeat_penalty", None) or 1.0))
        lay.addRow(self._lbl("repeat_penalty"), self._repeat_penalty)

        self._seed = QSpinBox()
        self._seed.setRange(-1, 2_147_483_647)
        self._seed.setValue(int(os.environ.get("GEMMA4_AGENT_SEED", "-1") or "-1"))
        self._seed.setSpecialValueText("-1  (random)")
        lay.addRow(self._lbl("seed"), self._seed)

        self._enable_thinking = QCheckBox("Allow Gemma to expose chain-of-thought (slower)")
        self._enable_thinking.setChecked(_env_truthy("GEMMA4_AGENT_ENABLE_THINKING", bool(getattr(cfg, "enable_thinking", False))))
        lay.addRow(self._lbl(""), self._enable_thinking)

        self._parallel_tool_calls = QCheckBox("Let model emit multiple tool_calls per turn")
        self._parallel_tool_calls.setChecked(_env_truthy("GEMMA4_AGENT_PARALLEL_TOOL_CALLS", bool(getattr(cfg, "parallel_tool_calls", False))))
        lay.addRow(self._lbl(""), self._parallel_tool_calls)

        return w

    # ------------------------------------------------------------------
    def _tab_behaviour(self) -> QWidget:
        w = QWidget()
        lay = QFormLayout(w)
        lay.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        cfg = self._agent_config

        info = QLabel(
            "Higher-level behaviour knobs that the agent actually reads.\n"
            "Strict honesty and auto-replan are always on (built into the loop)."
        )
        info.setFont(mono(8))
        info.setStyleSheet(f"color: {C.TEXT_DIM};")
        lay.addRow(info)

        self._summarization_cooldown = QSpinBox()
        self._summarization_cooldown.setRange(0, 50)
        self._summarization_cooldown.setValue(int(os.environ.get("GEMMA4_AGENT_SUMMARIZATION_COOLDOWN", "6") or "6"))
        lay.addRow(self._lbl("summarization cooldown turns"), self._summarization_cooldown)

        self._fact_cooldown = QSpinBox()
        self._fact_cooldown.setRange(0, 50)
        self._fact_cooldown.setValue(int(os.environ.get("GEMMA4_AGENT_FACT_EXTRACTION_COOLDOWN", "5") or "5"))
        lay.addRow(self._lbl("fact extraction cooldown"), self._fact_cooldown)

        self._tool_timeout = QSpinBox()
        self._tool_timeout.setRange(5, 600)
        self._tool_timeout.setValue(int(os.environ.get("GEMMA4_PHRASE_STEP_TIMEOUT_S", "30") or "30"))
        lay.addRow(self._lbl("phrase-trigger step timeout (s)"), self._tool_timeout)

        self._chat_timeout = QSpinBox()
        self._chat_timeout.setRange(5, 600)
        self._chat_timeout.setValue(int(os.environ.get("GEMMA4_AGENT_TIMEOUT", str(int(getattr(cfg, "request_timeout_s", 180)))) or "180"))
        lay.addRow(self._lbl("LLM request timeout (s)"), self._chat_timeout)

        self._max_experience = QSpinBox()
        self._max_experience.setRange(50, 100_000)
        self._max_experience.setValue(int(os.environ.get("GEMMA4_EXPERIENCE_MAX_RECORDS", "5000") or "5000"))
        lay.addRow(self._lbl("max experience records"), self._max_experience)

        note = QLabel(
            "Honesty guards (unverified detection, phrase-confirm, plan status)\n"
            "are always on. Auto-replan triggers after 2+ tool failures when\n"
            "an explicit plan exists; toggling it off is not exposed."
        )
        note.setFont(mono(8))
        note.setStyleSheet(f"color: {C.TEXT_DIM};")
        lay.addRow(note)

        return w

    # ------------------------------------------------------------------
    def _tab_voice(self) -> QWidget:
        """Fase W — VOICE tab: wake-word, STT, TTS, follow-up."""
        from PyQt6.QtWidgets import QPlainTextEdit
        persisted = load_persisted()
        voice = persisted.get("voice") or {}

        w = QWidget()
        lay = QFormLayout(w)
        lay.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        info = QLabel(
            "Voz local: Vosk (wake) + faster-whisper (STT) + Piper (TTS). Todo CPU.\n"
            "Cambios requieren toggle off/on para tomar efecto. Los modelos se\n"
            "descargan al primer uso con tu consentimiento."
        )
        info.setFont(mono(8))
        info.setStyleSheet(f"color: {C.TEXT_DIM};")
        lay.addRow(info)

        self._voice_enabled = QCheckBox("Enable voice (master switch)")
        self._voice_enabled.setChecked(bool(voice.get("enabled", False)))
        lay.addRow(self._lbl(""), self._voice_enabled)

        # Wake-words: locked por ahora a ambas frases
        wake_lbl = QLabel("Wake words: 'gemma' AND 'hey gemma' (both active)")
        wake_lbl.setFont(mono(8))
        wake_lbl.setStyleSheet(f"color: {C.TEXT_MED};")
        lay.addRow(self._lbl("Wake words"), wake_lbl)

        # Feedback
        fb_row = QHBoxLayout()
        self._voice_fb_beep = QCheckBox("Beep")
        self._voice_fb_beep.setChecked(bool(voice.get("feedback_beep", True)))
        self._voice_fb_hud = QCheckBox("HUD blink")
        self._voice_fb_hud.setChecked(bool(voice.get("feedback_hud", True)))
        self._voice_fb_tts = QCheckBox('TTS "sí"')
        self._voice_fb_tts.setChecked(bool(voice.get("feedback_tts_si", False)))
        for c in (self._voice_fb_beep, self._voice_fb_hud, self._voice_fb_tts):
            fb_row.addWidget(c)
        fb_row.addStretch()
        fb_wrap = QWidget(); fb_wrap.setLayout(fb_row)
        lay.addRow(self._lbl("Wake feedback"), fb_wrap)

        # Input device dropdown
        self._voice_device = QComboBox()
        self._voice_device.setStyleSheet(combo_qss())
        self._voice_device.addItem("(default)")
        try:
            from ..voice.audio_io import list_input_devices
            for d in list_input_devices():
                label = f"{d['index']}: {d['name']}"
                self._voice_device.addItem(label, userData=d["index"])
        except Exception:
            pass
        current_dev = voice.get("input_device")
        if isinstance(current_dev, int):
            for i in range(self._voice_device.count()):
                if self._voice_device.itemData(i) == current_dev:
                    self._voice_device.setCurrentIndex(i)
                    break
        lay.addRow(self._lbl("Input device"), self._voice_device)

        # STT model
        self._voice_stt_model = QComboBox()
        self._voice_stt_model.setStyleSheet(combo_qss())
        for m in ("auto", "small", "base", "tiny"):
            self._voice_stt_model.addItem(m)
        self._voice_stt_model.setCurrentText(str(voice.get("stt_model", "auto")))
        lay.addRow(self._lbl("STT model (CPU)"), self._voice_stt_model)

        # TTS voice
        self._voice_tts_voice = QComboBox()
        self._voice_tts_voice.setStyleSheet(combo_qss())
        try:
            from ..voice.tts import DEFAULT_VOICE, PIPER_VOICE_URLS, installed_voices
            known = list(PIPER_VOICE_URLS.keys())
            installed = installed_voices()
            for v in known:
                label = v + ("  (installed)" if v in installed else "  (download on first use)")
                self._voice_tts_voice.addItem(label, userData=v)
            for v in installed:
                if v not in known:
                    self._voice_tts_voice.addItem(f"{v}  (custom)", userData=v)
        except Exception:
            self._voice_tts_voice.addItem("es_MX-claude-high", userData="es_MX-claude-high")
        current_v = voice.get("tts_voice", "es_MX-claude-high")
        for i in range(self._voice_tts_voice.count()):
            if self._voice_tts_voice.itemData(i) == current_v:
                self._voice_tts_voice.setCurrentIndex(i)
                break
        lay.addRow(self._lbl("TTS voice"), self._voice_tts_voice)

        # Follow-up window
        self._voice_followup = QComboBox()
        self._voice_followup.setStyleSheet(combo_qss())
        for opt in ("Off", "5s", "10s"):
            self._voice_followup.addItem(opt)
        followup_s = float(voice.get("followup_seconds", 5.0) or 0.0)
        if followup_s == 0:
            self._voice_followup.setCurrentText("Off")
        elif followup_s == 10:
            self._voice_followup.setCurrentText("10s")
        else:
            self._voice_followup.setCurrentText("5s")
        lay.addRow(self._lbl("Follow-up window"), self._voice_followup)

        # Close phrases
        cp_label = QLabel("Frases de cierre del follow-up (una por linea):")
        cp_label.setFont(mono(8))
        cp_label.setStyleSheet(f"color: {C.TEXT_DIM};")
        lay.addRow(cp_label)
        self._voice_close_phrases = QPlainTextEdit()
        self._voice_close_phrases.setFont(mono(8))
        self._voice_close_phrases.setStyleSheet(text_edit_qss())
        self._voice_close_phrases.setFixedHeight(70)
        default_cp = "\n".join(voice.get(
            "close_phrases",
            ["gracias", "listo", "ya está", "cancelar", "stop"],
        ))
        self._voice_close_phrases.setPlainText(default_cp)
        lay.addRow(self._voice_close_phrases)

        # TTS muted
        self._voice_tts_muted = QCheckBox("Mute TTS (siguen funcionando wake + STT)")
        self._voice_tts_muted.setChecked(bool(voice.get("tts_muted", False)))
        lay.addRow(self._lbl(""), self._voice_tts_muted)

        note = QLabel(
            "El voice controller arranca/para automaticamente al cambiar de perfil:\n"
            "  PERF y BAL -> ON ;  LIGHT y STANDBY -> OFF.\n"
            "Tu override manual via 'Enable voice' persiste hasta que vuelvas a tocarlo."
        )
        note.setFont(mono(8))
        note.setStyleSheet(f"color: {C.ACC2};")
        lay.addRow(note)

        return w

    def _gather_voice(self) -> dict:
        seconds_text = self._voice_followup.currentText()
        followup_s = {"Off": 0.0, "5s": 5.0, "10s": 10.0}.get(seconds_text, 5.0)
        # Input device: itemData es int (index) o None ("(default)")
        dev_idx = self._voice_device.currentData()
        close_phrases = [
            line.strip() for line in self._voice_close_phrases.toPlainText().splitlines()
            if line.strip()
        ]
        return {
            "enabled": self._voice_enabled.isChecked(),
            "feedback_beep": self._voice_fb_beep.isChecked(),
            "feedback_hud": self._voice_fb_hud.isChecked(),
            "feedback_tts_si": self._voice_fb_tts.isChecked(),
            "input_device": dev_idx if isinstance(dev_idx, int) else None,
            "stt_model": self._voice_stt_model.currentText(),
            "tts_voice": self._voice_tts_voice.currentData() or "es_MX-claude-high",
            "followup_seconds": followup_s,
            "close_phrases": close_phrases,
            "tts_muted": self._voice_tts_muted.isChecked(),
        }

    # ------------------------------------------------------------------
    def _tab_profiles(self) -> QWidget:
        """Fase V — PROFILES tab: detection, auto-switch, editable defaults."""
        from PyQt6.QtWidgets import QPlainTextEdit, QTableWidget, QTableWidgetItem
        from ..profiles import PROFILES, detect_vram_mb, load_overrides, recommend_profile, save_overrides

        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(14)

        # --- DETECCION ---
        det_title = QLabel("◇  DETECCION DE HARDWARE")
        det_title.setFont(mono(8, True))
        det_title.setStyleSheet(f"color: {C.PRI}; border-bottom: 1px solid {C.BORDER};")
        outer.addWidget(det_title)

        det_row = QHBoxLayout()
        self._prof_vram_lbl = QLabel("VRAM detectada: ...")
        self._prof_vram_lbl.setFont(mono(9))
        self._prof_vram_lbl.setStyleSheet(f"color: {C.TEXT};")
        det_row.addWidget(self._prof_vram_lbl, stretch=1)

        redetect_btn = QPushButton("REDETECTAR")
        redetect_btn.setStyleSheet(button_qss())
        redetect_btn.setFixedHeight(28)
        redetect_btn.clicked.connect(self._on_prof_redetect)
        det_row.addWidget(redetect_btn)
        det_wrap = QWidget(); det_wrap.setLayout(det_row)
        outer.addWidget(det_wrap)

        self._prof_rec_lbl = QLabel("Perfil recomendado: ...")
        self._prof_rec_lbl.setFont(mono(9))
        self._prof_rec_lbl.setStyleSheet(f"color: {C.TEXT_MED};")
        outer.addWidget(self._prof_rec_lbl)

        # Initial detect (sin bloquear UI: subprocess es rapido y opt-in)
        self._on_prof_redetect()

        # --- AUTO-SWITCH ---
        auto_title = QLabel("◇  AUTO-SWITCH (opt-in)")
        auto_title.setFont(mono(8, True))
        auto_title.setStyleSheet(f"color: {C.PRI}; border-bottom: 1px solid {C.BORDER};")
        outer.addWidget(auto_title)

        persisted = load_persisted()
        auto = persisted.get("profiles_auto") or {}

        self._prof_auto_master = QCheckBox(
            "Cambiar perfil automaticamente cuando..."
        )
        self._prof_auto_master.setChecked(bool(auto.get("enabled", False)))
        outer.addWidget(self._prof_auto_master)

        # Trigger por VRAM externa: detecta CUALQUIER cosa pesada en GPU
        # (juego, render, transcoding, training local) sin lista de nombres.
        # Recomendado y default-on.
        self._prof_auto_vram = QCheckBox(
            "  Otro proceso usa >40% de VRAM (juegos, render, edicion video)"
        )
        self._prof_auto_vram.setChecked(bool(auto.get("trigger_on_vram", True)))
        outer.addWidget(self._prof_auto_vram)

        self._prof_auto_game = QCheckBox(
            "  Detecto un proceso de la watchlist abajo"
        )
        # Default ahora False: la watchlist por nombre es opcional; el trigger
        # por VRAM cubre el caso real (algo pesado corriendo) sin hardcodear
        # nombres de procesos comunes como steam.exe.
        self._prof_auto_game.setChecked(bool(auto.get("trigger_on_game", False)))
        outer.addWidget(self._prof_auto_game)

        self._prof_auto_gpu = QCheckBox(
            "  GPU >70% por mas de 30s (sin contar Gemma4)"
        )
        self._prof_auto_gpu.setChecked(bool(auto.get("trigger_on_gpu", False)))
        outer.addWidget(self._prof_auto_gpu)

        self._prof_auto_ram = QCheckBox(
            "  RAM >85%"
        )
        self._prof_auto_ram.setChecked(bool(auto.get("trigger_on_ram", False)))
        outer.addWidget(self._prof_auto_ram)

        sw_row = QHBoxLayout()
        sw_row.addWidget(QLabel("Cambiar a:"))
        # 2026-05-26: un solo perfil (vram4) + standby. El auto-switch ya no
        # tiene a dónde ir; los combos sólo ofrecen los perfiles que existen.
        _switch_opts = ("vram4", "standby")
        self._prof_auto_down = QComboBox()
        self._prof_auto_down.setStyleSheet(combo_qss())
        for n in _switch_opts:
            self._prof_auto_down.addItem(n)
        self._prof_auto_down.setCurrentText(str(auto.get("downgrade_to", "vram4")))
        sw_row.addWidget(self._prof_auto_down)
        sw_row.addSpacing(12)
        sw_row.addWidget(QLabel("Volver a:"))
        self._prof_auto_up = QComboBox()
        self._prof_auto_up.setStyleSheet(combo_qss())
        for n in _switch_opts:
            self._prof_auto_up.addItem(n)
        self._prof_auto_up.setCurrentText(str(auto.get("restore_to", "vram4")))
        sw_row.addWidget(self._prof_auto_up)
        sw_row.addStretch()
        sw_wrap = QWidget(); sw_wrap.setLayout(sw_row)
        outer.addWidget(sw_wrap)

        wl_label = QLabel("Procesos que disparan auto-switch (uno por linea):")
        wl_label.setFont(mono(8))
        wl_label.setStyleSheet(f"color: {C.TEXT_DIM};")
        outer.addWidget(wl_label)

        self._prof_auto_wl = QPlainTextEdit()
        self._prof_auto_wl.setFont(mono(8))
        self._prof_auto_wl.setStyleSheet(text_edit_qss())
        self._prof_auto_wl.setFixedHeight(70)
        wl_default = "\n".join(auto.get("game_watchlist", [
            "steam.exe", "RobloxPlayer.exe", "javaw.exe", "FortniteClient-Win64-Shipping.exe",
        ]))
        self._prof_auto_wl.setPlainText(wl_default)
        outer.addWidget(self._prof_auto_wl)

        # --- PERFILES (tabla editable) ---
        tbl_title = QLabel("◇  PERFILES  (edita y guarda; STANDBY no editable)")
        tbl_title.setFont(mono(8, True))
        tbl_title.setStyleSheet(f"color: {C.PRI}; border-bottom: 1px solid {C.BORDER};")
        outer.addWidget(tbl_title)

        overrides = load_overrides()
        fields = (
            ("context_size", "ctx"),
            ("vision_enabled", "vision"),
            ("rerank_enabled", "rerank"),
            ("parallel_tools", "parallel"),
            ("voice_enabled", "voice"),
            ("model_path", "model"),
        )
        cols = ("vram4",)  # 2026-05-26: único perfil editable (standby omitido)

        self._prof_table = QTableWidget(len(fields), len(cols))
        self._prof_table.setHorizontalHeaderLabels([PROFILES[c].display_name for c in cols])
        self._prof_table.setVerticalHeaderLabels([f[1] for f in fields])
        self._prof_table.setStyleSheet(
            f"QTableWidget {{ background: {C.PANEL}; color: {C.TEXT}; "
            f"gridline-color: {C.BORDER}; }}"
        )
        for r, (field_name, _) in enumerate(fields):
            for c, prof_name in enumerate(cols):
                base = PROFILES[prof_name]
                override = (overrides.get(prof_name) or {}).get(field_name)
                if override is not None:
                    val = override
                else:
                    val = getattr(base, field_name)
                if isinstance(val, bool):
                    item = QTableWidgetItem("true" if val else "false")
                elif val is None:
                    item = QTableWidgetItem("")
                else:
                    item = QTableWidgetItem(str(val))
                self._prof_table.setItem(r, c, item)
        outer.addWidget(self._prof_table)

        restore_btn = QPushButton("RESTAURAR DEFAULTS")
        restore_btn.setStyleSheet(button_qss())
        restore_btn.setFixedHeight(28)
        restore_btn.clicked.connect(self._on_prof_restore_defaults)
        outer.addWidget(restore_btn)

        # Hotkey hint
        hk = QLabel("Hotkey global: Ctrl+Shift+G  cicla PERF -> BAL -> LIGHT -> STDBY")
        hk.setFont(mono(7))
        hk.setStyleSheet(f"color: {C.TEXT_DIM};")
        outer.addWidget(hk)

        # Note about Light/Balanced models
        light_note = QLabel(
            "Light default: models/E2B/gemma-4-E2B-it-Q4_K_M.gguf (~4.66 GB VRAM total, ctx 4K). "
            "Balanced default: models/E2B/gemma-4-E2B-it-Q5_K_M.gguf (~5.10 GB VRAM total, ctx 8K). "
            "Performance: usa GEMMA4_MODEL_PATH (tu modelo principal, E4B-Q6_K o superior, 12+ GB VRAM). "
            "Voice (Whisper+Piper) corre en CPU y por defecto esta ON en los 3 perfiles activos. "
            "Numeros de VRAM medidos en RTX 4060 Ti; documentacion/datos_crudos/vram_real_medida.csv."
        )
        light_note.setFont(mono(7))
        light_note.setStyleSheet(f"color: {C.ACC2};")
        light_note.setWordWrap(True)
        outer.addWidget(light_note)

        return w

    def _on_prof_redetect(self) -> None:
        from ..profiles import detect_vram_mb, recommend_profile
        mb = detect_vram_mb()
        if mb is None:
            self._prof_vram_lbl.setText("VRAM detectada: no detectada (nvidia-smi/rocm-smi no respondio)")
            rec = "vram4"
        else:
            self._prof_vram_lbl.setText(f"VRAM detectada: {mb} MB")
            rec = recommend_profile(mb)
        self._prof_rec_lbl.setText(f"Perfil recomendado: {rec.upper()}")

    def _on_prof_restore_defaults(self) -> None:
        from PyQt6.QtWidgets import QTableWidgetItem
        from ..profiles import PROFILES
        cols = ("vram4",)  # único perfil (2026-05-26)
        fields = ("context_size", "vision_enabled", "rerank_enabled", "parallel_tools", "voice_enabled", "model_path")
        for r, field_name in enumerate(fields):
            for c, prof_name in enumerate(cols):
                val = getattr(PROFILES[prof_name], field_name)
                if isinstance(val, bool):
                    item = QTableWidgetItem("true" if val else "false")
                elif val is None:
                    item = QTableWidgetItem("")
                else:
                    item = QTableWidgetItem(str(val))
                self._prof_table.setItem(r, c, item)

    def _gather_profiles(self) -> tuple[dict, dict]:
        """Reads the profiles tab. Returns (auto_config_dict, overrides_dict).

        overrides_dict goes to ~/.gemma4/profiles.json via save_overrides.
        auto_config_dict goes inside gui.json under key "profiles_auto".
        """
        from typing import Any as _Any
        auto: dict[str, _Any] = {
            "enabled": self._prof_auto_master.isChecked(),
            "trigger_on_vram": self._prof_auto_vram.isChecked(),
            "trigger_on_game": self._prof_auto_game.isChecked(),
            "trigger_on_gpu": self._prof_auto_gpu.isChecked(),
            "trigger_on_ram": self._prof_auto_ram.isChecked(),
            "downgrade_to": self._prof_auto_down.currentText(),
            "restore_to": self._prof_auto_up.currentText(),
            "game_watchlist": [
                line.strip() for line in self._prof_auto_wl.toPlainText().splitlines()
                if line.strip()
            ],
        }
        # Overrides table -> dict[prof_name][field_name] = value
        cols = ("vram4",)  # único perfil (2026-05-26)
        fields = (
            ("context_size", int),
            ("vision_enabled", bool),
            ("rerank_enabled", bool),
            ("parallel_tools", bool),
            ("voice_enabled", bool),
            ("model_path", str),
        )
        from ..profiles import PROFILES
        overrides: dict[str, dict[str, _Any]] = {}
        for c, prof_name in enumerate(cols):
            base = PROFILES[prof_name]
            row: dict[str, _Any] = {}
            for r, (field_name, ftype) in enumerate(fields):
                item = self._prof_table.item(r, c)
                if item is None:
                    continue
                raw = item.text().strip()
                if not raw and field_name == "model_path":
                    # Vacio == None. Solo guardamos override si difiere del base.
                    if base.model_path is not None:
                        row[field_name] = None
                    continue
                if not raw:
                    continue
                try:
                    if ftype is bool:
                        val: _Any = raw.lower() in {"true", "1", "yes", "on"}
                    elif ftype is int:
                        val = int(raw)
                    else:
                        val = raw
                except (ValueError, TypeError):
                    continue
                # Solo guardar si difiere del default
                if getattr(base, field_name) != val:
                    row[field_name] = val
            if row:
                overrides[prof_name] = row
        return auto, overrides

    # ------------------------------------------------------------------
    def _tab_optim(self) -> QWidget:
        """Tab OPTIM — env vars del roadmap de optimizacion Gemma 4.

        Estas no son toggles de features de la app, son palancas avanzadas
        para tunear el llama-server / agente. Aplican al proximo restart.
        """
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(8)

        title = QLabel("OPTIMIZATION  (advanced — env vars applied at next restart)")
        title.setFont(mono(8, True))
        title.setStyleSheet(f"color: {C.TEXT_MED};")
        lay.addWidget(title)

        warn = QLabel(
            "Estos toggles son palancas low-level del runtime de llama.cpp y "
            "del prewarm. Solo cambialos si sabes que estas haciendo o seguis "
            "una guia de optimizacion concreta. Cambios mal aplicados pueden "
            "degradar throughput o causar OOM."
        )
        warn.setFont(mono(7))
        warn.setStyleSheet(f"color: {C.ACC2};")
        warn.setWordWrap(True)
        lay.addWidget(warn)

        # --- Disable prewarm ---
        self._optim_disable_prewarm = QCheckBox(
            "Disable KV cache prewarm at boot  [GEMMA4_DISABLE_PREWARM]"
        )
        self._optim_disable_prewarm.setChecked(
            _env_truthy("GEMMA4_DISABLE_PREWARM", False)
        )
        self._optim_disable_prewarm.setToolTip(
            "Opt-out del prewarm. Default OFF (prewarm activo).\n"
            "Si lo activas, el primer turn paga el TTFT del prefill (60-90s con\n"
            "system prompt grande). Util solo si el prewarm causa problemas."
        )
        lay.addWidget(self._optim_disable_prewarm)

        # --- Telemetry ---
        self._optim_telemetry = QCheckBox(
            "Enable local telemetry (SQLite)  [GEMMA4_TELEMETRY]"
        )
        self._optim_telemetry.setChecked(
            _env_truthy("GEMMA4_TELEMETRY", False)
        )
        self._optim_telemetry.setToolTip(
            "Opt-in. Default OFF.\n"
            "Cuando esta ON, escribe turns/voice/incidents en\n"
            "~/.gemma4/telemetry.sqlite. Solo local. Aplicar requiere\n"
            "restart del agente."
        )
        lay.addWidget(self._optim_telemetry)

        # --- KV type ---
        kv_row = QHBoxLayout()
        kv_lbl = QLabel("KV cache type  [GEMMA4_LLAMA_KV_TYPE]:")
        kv_lbl.setFont(mono(8))
        kv_lbl.setStyleSheet(f"color: {C.TEXT_MED};")
        kv_row.addWidget(kv_lbl)
        self._optim_kv_type = QComboBox()
        self._optim_kv_type.setStyleSheet(combo_qss())
        for opt in ("", "f16", "q8_0", "q4_0"):
            self._optim_kv_type.addItem(opt or "(default f16)")
        current_kv = (os.environ.get("GEMMA4_LLAMA_KV_TYPE") or "").strip().lower()
        if current_kv in {"f16", "q8_0", "q4_0"}:
            self._optim_kv_type.setCurrentText(current_kv)
        else:
            self._optim_kv_type.setCurrentIndex(0)
        self._optim_kv_type.setToolTip(
            "Quantizacion del KV cache. f16=default, q8_0=~50% menos VRAM,\n"
            "q4_0=~75% menos VRAM (con perdida de calidad notable). Util en\n"
            "perfiles light/balanced con contexts grandes."
        )
        kv_row.addWidget(self._optim_kv_type, stretch=1)
        lay.addLayout(kv_row)

        # --- Spec decoding model ---
        spec_row = QHBoxLayout()
        spec_lbl = QLabel("Speculative draft model  [GEMMA4_SPEC_DRAFT_MODEL]:")
        spec_lbl.setFont(mono(8))
        spec_lbl.setStyleSheet(f"color: {C.TEXT_MED};")
        spec_row.addWidget(spec_lbl)
        self._optim_spec_draft = QLineEdit(
            str(os.environ.get("GEMMA4_SPEC_DRAFT_MODEL") or "")
        )
        self._optim_spec_draft.setStyleSheet(line_edit_qss())
        self._optim_spec_draft.setFont(mono(8))
        self._optim_spec_draft.setPlaceholderText("(empty = disabled)")
        self._optim_spec_draft.setToolTip(
            "Path al modelo draft (Q4_K_M de 1-2B) para speculative decoding.\n"
            "Solo se activa si el perfil tambien lo permite. Empty = OFF."
        )
        spec_pick = QPushButton("...")
        spec_pick.setFixedWidth(28)
        spec_pick.setStyleSheet(button_qss())
        def _pick_spec() -> None:
            p, _ = QFileDialog.getOpenFileName(
                self, "Choose draft model (.gguf)", "", "GGUF (*.gguf);;All (*.*)"
            )
            if p:
                self._optim_spec_draft.setText(p)
        spec_pick.clicked.connect(_pick_spec)
        spec_row.addWidget(self._optim_spec_draft, stretch=1)
        spec_row.addWidget(spec_pick)
        lay.addLayout(spec_row)

        # --- llama-server API key ---
        api_row = QHBoxLayout()
        api_lbl = QLabel("llama-server API key  [GEMMA4_LLAMA_API_KEY]:")
        api_lbl.setFont(mono(8))
        api_lbl.setStyleSheet(f"color: {C.TEXT_MED};")
        api_row.addWidget(api_lbl)
        self._optim_api_key = QLineEdit(
            str(os.environ.get("GEMMA4_LLAMA_API_KEY") or "")
        )
        self._optim_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._optim_api_key.setStyleSheet(line_edit_qss())
        self._optim_api_key.setFont(mono(8))
        self._optim_api_key.setPlaceholderText("(empty = no auth)")
        self._optim_api_key.setToolTip(
            "Si seteado, llama-server requiere Authorization: Bearer <key>\n"
            "en cada request. Cliente y server lo aplican automaticamente.\n"
            "Sprint 12 hardening."
        )
        api_row.addWidget(self._optim_api_key, stretch=1)
        lay.addLayout(api_row)

        lay.addStretch()
        return w

    def _tab_toggles(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(8)

        title = QLabel("FEATURE TOGGLES  (env vars applied at next agent restart)")
        title.setFont(mono(8, True))
        title.setStyleSheet(f"color: {C.TEXT_MED};")
        lay.addWidget(title)

        self._toggles_checks: dict[str, QCheckBox] = {}
        for env, label, default in TOGGLES:
            cb = QCheckBox(f"{label}  [{env}]")
            cb.setChecked(_env_truthy(env, default))
            self._toggles_checks[env] = cb
            lay.addWidget(cb)
        lay.addStretch()
        return w

    # ------------------------------------------------------------------
    def _tab_paths(self) -> QWidget:
        w = QWidget()
        lay = QFormLayout(w)
        lay.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        cfg = self._agent_config

        def _path_row(initial: str) -> tuple[QWidget, QLineEdit]:
            le = QLineEdit(initial)
            le.setStyleSheet(line_edit_qss())
            le.setFont(mono(8))
            br = QPushButton("...")
            br.setFixedWidth(32)
            br.setStyleSheet(button_qss())
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.addWidget(le, stretch=1)
            row.addWidget(br)
            ww = QWidget(); ww.setLayout(row)
            def _pick():
                p, _ = QFileDialog.getSaveFileName(self, "Choose path", initial)
                if p:
                    le.setText(p)
            br.clicked.connect(_pick)
            return ww, le

        mp = str(getattr(cfg, "memory_path", "memory.json") or "memory.json")
        mp_w, self._memory_path = _path_row(mp)
        lay.addRow(self._lbl("memory.json"), mp_w)

        sp = str(getattr(cfg, "state_path", "state.json") or "state.json")
        sp_w, self._state_path = _path_row(sp)
        lay.addRow(self._lbl("state.json"), sp_w)

        tp = str(getattr(cfg, "trace_path", "trace.jsonl") or "trace.jsonl")
        tp_w, self._trace_path = _path_row(tp)
        lay.addRow(self._lbl("trace.jsonl"), tp_w)

        sess_dir = QLineEdit(str(os.environ.get("GEMMA4_AGENT_SESSIONS_DIR") or str(Path.home() / ".gemma4" / "sessions")))
        sess_dir.setStyleSheet(line_edit_qss())
        sess_dir.setFont(mono(8))
        lay.addRow(self._lbl("Sessions dir"), sess_dir)
        self._sess_dir = sess_dir

        tl_dir = QLineEdit(str(os.environ.get("GEMMA4_AGENT_TIMELINE_DIR") or str(Path.home() / ".gemma4" / "timeline")))
        tl_dir.setStyleSheet(line_edit_qss())
        tl_dir.setFont(mono(8))
        lay.addRow(self._lbl("Timeline dir"), tl_dir)
        self._tl_dir = tl_dir

        return w

    # ------------------------------------------------------------------
    def _tab_prompt(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(8)

        title = QLabel("SYSTEM PROMPT (read-only preview of current core prompt)")
        title.setFont(mono(8, True))
        title.setStyleSheet(f"color: {C.TEXT_MED};")
        lay.addWidget(title)

        try:
            from ..agent import SYSTEM_PROMPT
            text = SYSTEM_PROMPT
        except Exception as exc:
            text = f"<could not load: {exc}>"

        edit = QPlainTextEdit()
        edit.setPlainText(text)
        edit.setReadOnly(True)
        edit.setFont(QFont("Consolas", 9))
        edit.setStyleSheet(text_edit_qss())
        lay.addWidget(edit, stretch=1)

        hint = QLabel(
            "To override, edit gemma4_agent/agent.py SYSTEM_PROMPT. Persona and "
            "project_context hints are appended automatically at runtime."
        )
        hint.setFont(mono(8))
        hint.setStyleSheet(f"color: {C.TEXT_DIM};")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        return w

    # ------------------------------------------------------------------
    def _tab_about(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(12)

        title = QLabel("GEMMA4-MARK-I")
        title.setFont(mono(20, True))
        title.setStyleSheet(f"color: {C.PRI};")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(title)

        sub = QLabel("Local AI agent · Just A Rather Very Intelligent System")
        sub.setFont(mono(9))
        sub.setStyleSheet(f"color: {C.TEXT_DIM};")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(sub)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER};")
        lay.addWidget(sep)

        from .. import agent as agent_mod
        info = QLabel(
            f"Python: {sys.version.split()[0]}\n"
            f"Settings file: {SETTINGS_PATH}\n"
            f"Agent module: {Path(agent_mod.__file__).parent}\n"
        )
        info.setFont(mono(8))
        info.setStyleSheet(f"color: {C.TEXT};")
        lay.addWidget(info)
        lay.addStretch()

        credits = QLabel("Aesthetic inspired by MARK XXXIX (FatihMakes).\nAll inference is LOCAL.")
        credits.setFont(mono(8))
        credits.setStyleSheet(f"color: {C.TEXT_DIM};")
        credits.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(credits)
        return w

    # ------------------------------------------------------------------
    def _lbl(self, text: str) -> QLabel:
        l = QLabel(text)
        l.setFont(mono(9))
        l.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        return l

    # ------------------------------------------------------------------
    def _gather(self) -> dict:
        env: dict[str, str] = {}
        # Connection tab — names must match `config.AgentConfig.from_env`.
        if self._model_alias.text().strip():
            env["GEMMA4_AGENT_MODEL"] = self._model_alias.text().strip()
        if self._gguf_path.text().strip():
            env["GEMMA4_MODEL_PATH"] = self._gguf_path.text().strip()
        env["GEMMA4_AGENT_SERVER"] = self._server_url.text().strip() or "http://127.0.0.1:8080"
        env["GEMMA4_AGENT_CONTEXT"] = str(int(self._ctx_size.value()))
        env["GEMMA4_AGENT_MAX_TOKENS"] = str(int(self._max_tokens.value()))
        env["GEMMA4_AGENT_MODE"] = self._mode_combo.currentText()
        env["GEMMA4_AGENT_PERSONA"] = self._persona_combo.currentText()
        env["GEMMA4_AGENT_MAX_TURNS"] = str(int(self._max_turns.value()))
        env["GEMMA4_AGENT_SAFETY"] = "true" if self._enable_safety.isChecked() else "false"
        env["GEMMA4_AGENT_MEMORY"] = self._memory_path.text().strip()
        env["GEMMA4_AGENT_STATE"] = self._state_path.text().strip()
        env["GEMMA4_AGENT_TRACE_PATH"] = self._trace_path.text().strip()
        env["GEMMA4_AGENT_SESSIONS_DIR"] = self._sess_dir.text().strip()
        env["GEMMA4_AGENT_TIMELINE_DIR"] = self._tl_dir.text().strip()

        # Sampling tab — names must match `config.AgentConfig.from_env`.
        env["GEMMA4_AGENT_TEMPERATURE"]         = f"{self._temperature.value():.3f}"
        env["GEMMA4_AGENT_TOP_P"]               = f"{self._top_p.value():.3f}"
        env["GEMMA4_AGENT_TOP_K"]               = str(int(self._top_k.value()))
        env["GEMMA4_AGENT_MIN_P"]               = f"{self._min_p.value():.3f}"
        env["GEMMA4_AGENT_REPEAT_PENALTY"]      = f"{self._repeat_penalty.value():.3f}"
        env["GEMMA4_AGENT_SEED"]                = str(int(self._seed.value()))
        env["GEMMA4_AGENT_ENABLE_THINKING"]     = "true" if self._enable_thinking.isChecked() else "false"
        env["GEMMA4_AGENT_PARALLEL_TOOL_CALLS"] = "true" if self._parallel_tool_calls.isChecked() else "false"

        # Behaviour tab — only env vars actually consumed by the agent.
        env["GEMMA4_AGENT_SUMMARIZATION_COOLDOWN"]   = str(int(self._summarization_cooldown.value()))
        env["GEMMA4_AGENT_FACT_EXTRACTION_COOLDOWN"] = str(int(self._fact_cooldown.value()))
        env["GEMMA4_AGENT_TIMEOUT"]                  = str(int(self._chat_timeout.value()))
        env["GEMMA4_EXPERIENCE_MAX_RECORDS"]         = str(int(self._max_experience.value()))
        env["GEMMA4_PHRASE_STEP_TIMEOUT_S"]          = str(int(self._tool_timeout.value()))

        toggles: dict[str, bool] = {}
        for env_key, cb in self._toggles_checks.items():
            toggles[env_key] = cb.isChecked()

        # Optim tab — env vars del roadmap de optimizacion.
        # Disable prewarm va como toggle (env truthy parseado por prewarm.py).
        toggles["GEMMA4_DISABLE_PREWARM"] = self._optim_disable_prewarm.isChecked()
        toggles["GEMMA4_TELEMETRY"] = self._optim_telemetry.isChecked()
        # KV type combobox: vacio o "(default f16)" = unset
        kv_text = self._optim_kv_type.currentText().strip().lower()
        if kv_text in {"f16", "q8_0", "q4_0"}:
            env["GEMMA4_LLAMA_KV_TYPE"] = kv_text
        else:
            env["GEMMA4_LLAMA_KV_TYPE"] = ""  # apply_to_env borra del environ
        # Spec draft model path (vacio = OFF)
        env["GEMMA4_SPEC_DRAFT_MODEL"] = self._optim_spec_draft.text().strip()
        # API key (vacio = no auth)
        env["GEMMA4_LLAMA_API_KEY"] = self._optim_api_key.text().strip()

        return {"env": env, "toggles": toggles}

    def _on_apply(self) -> None:
        data = self._gather()
        # Fase V — persist profiles_auto + overrides
        try:
            auto, overrides = self._gather_profiles()
            data["profiles_auto"] = auto
            from ..profiles import save_overrides
            save_overrides(overrides)
        except Exception:
            pass
        # Fase W — persist voice config
        try:
            data["voice"] = self._gather_voice()
        except Exception:
            pass
        save_persisted(data)
        apply_to_env(data)
        self.apply_clicked.emit(data)
        self.accept()

    def _on_restart(self) -> None:
        data = self._gather()
        try:
            auto, overrides = self._gather_profiles()
            data["profiles_auto"] = auto
            from ..profiles import save_overrides
            save_overrides(overrides)
        except Exception:
            pass
        try:
            data["voice"] = self._gather_voice()
        except Exception:
            pass
        save_persisted(data)
        apply_to_env(data)
        self.restart_clicked.emit()
        self.accept()


def _env_truthy(name: str, default: bool) -> bool:
    raw = (os.environ.get(name) or "").strip().casefold()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return default


def apply_persisted_on_startup() -> None:
    """Called at app launch to push the last saved env to os.environ."""
    data = load_persisted()
    if data:
        apply_to_env(data)
