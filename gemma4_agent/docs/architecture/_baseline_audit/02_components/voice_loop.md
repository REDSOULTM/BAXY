# 02.02 — Voice Loop

> **Container:** Voice Loop.
> **Archivos:** todo el paquete `voice/` (6 archivos) + `voice_runner.py` en raíz.
> **Total LOC:** 2 765.

## Componentes

| # | Archivo | Clase principal | LOC | Modelo externo | Responsabilidad |
|--:|---|---|--:|---|---|
| 1 | `voice/audio_io.py` | `AudioCapture` | 245 | PortAudio (sounddevice) | InputStream mic 16kHz mono int16, chunks de 512 samples (Silero v5 requirement) + ring buffer 5s |
| 2 | `voice/wake.py` | `WakeDetector` | 346 | Vosk `vosk-model-small-es-0.42` (~40 MB) | Wake-word "gemma"/"hey gemma" con vocab restringido, confidence ≥0.85, debounce 2s |
| 3 | `voice/stt.py` | `StreamingSTT` | 863 | faster-whisper `small` + Silero VAD v5 + scipy butter | STT modo dual (greedy ≤3s / beam=5 >3s), bag-of-hallucinations es, high-pass 80 Hz |
| 4 | `voice/tts.py` | `StreamingTTS` | 302 | Piper `es_MX-claude-high` | Sintaxis de oraciones por regex + worker thread + cola FIFO, descarga voz on-demand |
| 5 | `voice/controller.py` | `VoiceController` | 576 | — | State machine de 9 estados que orquesta los 4 anteriores |
| 6 | `voice_runner.py` | `VoiceRunner` (entry) | 425 | comtypes + pycaw (audio ducking Win32) | Bridge entre VoiceController y BUS / AgentRunner |
| 7 | `voice/__init__.py` | — | 8 | — | (vacío) |

## Diagrama

```mermaid
%% Fig 2.04 — Voice Loop interno
graph TB
    Mic((mic))
    Spk((speakers))
    User((Usuario))

    User -- speech --> Mic

    subgraph "voice/audio_io.py"
        AC[AudioCapture<br/>512 samples @ 16kHz<br/>ring buffer 5s]
    end

    subgraph "voice/wake.py"
        WD[WakeDetector<br/>Vosk vocab restringido]
        Vosk[(vosk-model-small-es-0.42<br/>~40MB)]
    end

    subgraph "voice/stt.py"
        STT[StreamingSTT<br/>modo dual greedy/beam<br/>BoH filter es]
        Whisper[(faster-whisper small<br/>~466MB int8)]
        SVAD[(silero-vad v5)]
    end

    subgraph "voice/tts.py"
        TTS[StreamingTTS<br/>sentence regex + worker]
        Piper[(piper es_MX-claude-high)]
    end

    subgraph "voice/controller.py — state machine 9 estados"
        VC[VoiceController<br/>IDLE_DISABLED → IDLE_LISTENING<br/>→ WAKE_DETECTED → LISTENING<br/>→ TRANSCRIBING → THINKING<br/>→ SPEAKING → FOLLOWUP]
    end

    subgraph "voice_runner.py — bridge"
        VR[VoiceRunner<br/>BUS publish + AgentRunner.submit<br/>+ audio ducking Win32]
    end

    Mic -- "PortAudio callback<br/>(only .copy + push)" --> AC
    AC -- "chunk np.int16<br/>via _pump_loop thread" --> VC
    VC -- "feed chunk" --> WD
    WD --> Vosk
    WD -- "on_wake(phrase, tail_s)" --> VC
    VC -- "prefix_audio + chunks" --> STT
    STT --> Whisper
    STT --> SVAD
    STT -- "partial / final" --> VC
    VC -- "on_final(text)" --> VR
    VR -- "submit(text)" --> Runner[AgentRunner]
    VR -- "pub voice state" --> BUS[(BUS)]
    Runner -. "reply chunks via BUS" .-> VR
    VR -- "speak(text)" --> TTS
    TTS --> Piper
    TTS -- "PCM np.float32" --> Spk
    Spk -- audio --> User

    style Vosk fill:#eef
    style Whisper fill:#eef
    style SVAD fill:#eef
    style Piper fill:#eef
```

## State machine `VoiceController`

```mermaid
%% Fig 2.05 — VoiceController state machine
stateDiagram-v2
    [*] --> IDLE_DISABLED
    IDLE_DISABLED --> IDLE_LISTENING : enable()
    IDLE_DISABLED --> FAILED : load fail
    IDLE_LISTENING --> WAKE_DETECTED : wake
    WAKE_DETECTED --> LISTENING : 200ms feedback
    LISTENING --> TRANSCRIBING : speech_started
    LISTENING --> IDLE_LISTENING : 5s silent
    TRANSCRIBING --> THINKING : VAD endpoint OR 15s
    THINKING --> SPEAKING : first LLM token
    SPEAKING --> FOLLOWUP : LLM done + last sentence
    SPEAKING --> IDLE_LISTENING : LLM done + window=0
    FOLLOWUP --> TRANSCRIBING : speech in window
    FOLLOWUP --> IDLE_LISTENING : window timeout
    FOLLOWUP --> IDLE_LISTENING : close phrase
    state "any state" as any
    any --> IDLE_DISABLED : disable() OR profile LIGHT/STDBY
```

## Tabla de modelos en disco

| Modelo | Path típico | Tamaño aprox | Carga | Usado en |
|---|---|--:|---|---|
| Vosk small es-0.42 | `~/.gemma4/models/vosk-model-small-es-0.42/` | ~40 MB | eager en `WakeDetector.load()` | wake-word |
| faster-whisper small | `~/.gemma4/models/whisper/` | ~466 MB (int8) | eager en `StreamingSTT.load()` | STT |
| Silero VAD v5 | bundled con `silero_vad` pip | ~2 MB | eager con whisper | VAD endpoint |
| Piper voice (es_MX-claude-high) | `~/.gemma4/models/piper/*.onnx` + `.onnx.json` | ~60 MB | descargado on-demand | TTS |

## Hallazgos

| Sev | Hallazgo | Ubicación |
|---|---|---|
| **MED** | `voice/stt.py` 863 LOC con docstring monumental (35 líneas) explicando 9 cambios + referencias a issues. Es la única clase voice con más comentarios "por qué" que código. Honesto pero excesivo: gran parte podría ir a `docs/voice_stt_notes.md`. | `voice/stt.py:1-50` |
| **LOW** | URLs de modelos Piper hardcoded a un repo HF y voz default `es_MX-claude-high`. Si HF rebrandeo el repo o cae, se cae el bootstrap del TTS. Aceptable, pero anotar. | `voice/tts.py:33-48` |
| **LOW** | `voice/tts.py` tiene 3 voces en `PIPER_VOICE_URLS` pero solo 1 default. El selector no se cambia desde la UI (busqué `set_voice` y no aparece). Si nunca se cambia, las otras 2 son código muerto. | `voice/tts.py:35-48` |
| **LOW** | `voice_runner.py` 425 LOC con 1 sola función top-level y 2 clases. El bridge BUS↔Controller+ducking podría ser ~150 LOC. Sospecho features acumuladas. | `voice_runner.py` |
| **NIL** | `audio_io.py` es honesto y compacto. PortAudio callback solo `.copy() + push`, pump thread aparte. Buen patrón. | `voice/audio_io.py` |
| **NIL** | `wake.py` con vocabulario restringido + confidence floor + debounce: tres defensas explícitas contra FP. Bien documentado el porqué del 0.85 threshold. | `voice/wake.py` |

> **Observación general:** este es el subsistema con mejor diseño del paquete.
> Frontera clara, una responsabilidad por archivo, deps externos en un solo
> archivo (`stt.py`). La sobre-ingeniería es marginal.

## DOT backup

```dot
digraph VoiceLoop {
    rankdir=TB; node [shape=box, style=rounded];
    Mic [shape=circle]; Spk [shape=circle];
    AC [label="AudioCapture (audio_io)"];
    WD [label="WakeDetector (wake)"]; STT [label="StreamingSTT (stt)"];
    TTS [label="StreamingTTS (tts)"]; VC [label="VoiceController (controller)"];
    VR [label="voice_runner.VoiceRunner"];
    Vosk [shape=cylinder]; Whisper [shape=cylinder]; SVAD [shape=cylinder]; Piper [shape=cylinder];
    Runner [label="AgentRunner"]; BUS [shape=circle];

    Mic -> AC -> VC;
    VC -> WD -> Vosk; WD -> VC [label="on_wake"];
    VC -> STT -> Whisper; STT -> SVAD; STT -> VC [label="partial/final"];
    VC -> VR; VR -> Runner [label="submit"]; VR -> BUS [label="pub"];
    BUS -> VR [label="reply"]; VR -> TTS -> Piper; TTS -> Spk;
}
```
