# 03.02 — Voice Loop (clases UML)

> **Container:** Voice Loop.
> **Archivos:** `voice/audio_io.py`, `voice/wake.py`, `voice/stt.py`,
> `voice/tts.py`, `voice/controller.py`, `voice_runner.py`.

## Fig 3.02 — Voice Loop classes

```mermaid
classDiagram
    class AudioCapture {
        _on_chunk: Callable
        _device: int|str|None
        _ring: deque
        _ring_lock: Lock
        _pending_queue: Queue
        _stream: InputStream
        _pump_thread: Thread
        _running: bool
        last_error: str
        start() bool
        stop()
        snapshot() np.ndarray
        snapshot_tail(seconds) np.ndarray
        _sd_callback(indata, frames, ...)
        _pump_loop()
    }
    note for AudioCapture "245 LOC · 6 métodos\nPortAudio callback hace solo .copy()+push\nPump thread drena la queue separado"

    class WakeDetector {
        _on_wake: WakeCallback
        _recognizer: vosk.KaldiRecognizer
        _model: vosk.Model
        _last_wake_ts: float
        _loaded: bool
        last_error: str
        load() bool
        is_loaded() bool
        feed(chunk)
        reset()
        unload()
    }
    note for WakeDetector "346 LOC · 5 métodos\nVosk vocab restringido + confidence 0.85 + debounce 2s"

    class _SileroVAD {
        _model: SileroVADModel
        _loaded: bool
        last_error: str
        load() bool
        trim(audio_f32) np.ndarray|None
        unload()
    }
    note for _SileroVAD "interno a stt.py · trim de silencios pre-Whisper"

    class STTEvent {
        kind: str
        text: str
        timestamp: float
    }
    note for STTEvent "@dataclass · evento partial/final"

    class StreamingSTT {
        _model: WhisperModel
        _vad: _SileroVAD
        _model_size: str
        _loaded: bool
        last_error: str
        load() bool
        is_loaded() bool
        model_size: str [property]
        fallback_to_base() bool
        transcribe_stream(...) Iterator
        unload()
        _warmup()
        _quality_check(...)
        _run_whisper(...)
        _transcribe_buffer(...)
    }
    note for StreamingSTT "488 LOC clase + 863 LOC archivo · [GOD]\n11 métodos · modo dual greedy/beam"

    class StreamingTTS {
        _voice: str
        _model_path: Path
        _config_path: Path
        _piper: PiperVoice
        _queue: Queue
        _worker: Thread
        _stop_evt: Event
        _muted: bool
        _busy: bool
        last_error: str
        load() bool
        is_loaded() bool
        is_busy() bool
        set_muted(muted)
        is_muted() bool
        start()
        stop()
        feed_text(chunk) int
        flush() int
        unload()
        _run_worker()
        _synthesize_and_play(text, out_stream)
    }
    note for StreamingTTS "302 LOC clase · 12 métodos\nSentence-end regex + worker thread + sounddevice OutputStream"

    class VoiceController {
        _on_state: Callable
        _on_partial: Callable
        _on_final: Callable
        _on_tts_chunk: Callable
        _on_failed: Callable
        _followup_s: float
        _close_phrases: set
        _state: VoiceState
        _state_lock: Lock
        _audio: AudioCapture
        _wake: WakeDetector
        _stt: StreamingSTT
        _tts: StreamingTTS
        _stt_chunks: list
        _stt_thread: Thread
        _timer_thread: Thread
        _failed_components: list
        state() VoiceState
        enable() bool
        disable()
        trigger_manual()
        shutdown()
        set_tts_muted(muted)
        is_tts_muted() bool
        set_followup_seconds(s)
        set_close_phrases(phrases)
        get_failed_components() list
        begin_tts()
        feed_tts_chunk(chunk)
        end_tts()
        _set_state(new)
        _fail(reason)
        _on_audio_chunk(chunk)
        _on_wake_detected(phrase, ts, tail_s)
        _enter_listening()
        _start_listening_timeout()
        _start_followup_timer()
        _cancel_timer()
        _stt_chunk_iter() Iterator
        _start_stt_thread()
        _stop_stt_thread()
        _handle_final(text)
        _play_beep()
    }
    note for VoiceController "495 LOC clase · [GOD] 27 métodos\nState machine 9 estados (IDLE→WAKE→LISTENING→TRANSCRIBING→THINKING→SPEAKING→FOLLOWUP)"

    class VoiceRunner {
        _controller: VoiceController
        _runner: AgentRunner
        _publish: Callable
        ...
        enable()
        disable()
        ...
    }
    note for VoiceRunner "204 LOC clase · 425 LOC archivo · bridge\nVoiceController ↔ BUS + AgentRunner.submit + audio ducking Win32"

    AudioCapture --> VoiceController : on_chunk callback
    WakeDetector --> VoiceController : on_wake callback
    StreamingSTT ..> _SileroVAD : usa trim()
    VoiceController *-- AudioCapture
    VoiceController *-- WakeDetector
    VoiceController *-- StreamingSTT
    VoiceController *-- StreamingTTS
    VoiceRunner *-- VoiceController
    VoiceRunner ..> AgentRunner : submit(text)
    VoiceRunner ..> EventBus : pub state
```

## Veredictos

| Clase | LOC | Métodos | Marca | Veredicto |
|---|--:|--:|---|---|
| `AudioCapture` | 245 | 6 | — | mantener. Patrón PortAudio + pump-thread correcto. |
| `WakeDetector` | 346 | 5 | — | mantener. Vocab restringido + confidence + debounce justifican el tamaño. |
| `_SileroVAD` | ~70 | 3 | `[1-USER]` (solo `StreamingSTT`) | considerar inline en `StreamingSTT` — solo se usa ahí. |
| `STTEvent` | <20 | dataclass | — | mantener. |
| `StreamingSTT` | 488 | 11 | `[GOD]` (>300 LOC) | revisar: el quality_check + bag-of-hallucinations + modo dual + warmup pueden ir a un módulo `voice/whisper_quality.py` aparte. |
| `StreamingTTS` | 302 | 12 | — (límite) | mantener pero verificar que las 3 voces hardcoded se usan (Fase 8). |
| `VoiceController` | 495 | 27 | `[GOD]` (>15 métodos) | **split candidato**: state-machine + callback dispatch + lifecycle (enable/disable/shutdown) + timer management (`_start_listening_timeout`, `_start_followup_timer`). Probablemente 2 clases: `VoiceStateMachine` + `VoiceController`. |
| `VoiceRunner` | 204 | ~7 | — | revisar: bridge de 425 LOC suena alto para "BUS + ducking". Verificar features. |

## Hallazgos a `_findings_seed.md`

- **`VoiceController` 27 métodos.** Severity MED. State-machine + timers + lifecycle + TTS bridge mezclados.
- **`_SileroVAD` 1-user.** Severity LOW. Inline en `StreamingSTT`.
- **`StreamingSTT` 488 LOC.** Severity LOW. Considerar split de `_quality_check` + bag-of-hallucinations a archivo aparte.
- **`StreamingTTS` 3 voces Piper hardcoded, 1 default** — verificar Fase 7 que las otras 2 se usan.
