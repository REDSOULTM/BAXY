# 04.03 — Wake-word activation

> Cuándo: el usuario dice "gemma" o "hey gemma" estando en IDLE_LISTENING.
> **Fuente:** `voice/audio_io.py` + `voice/wake.py` + `voice/controller.py`.
> Latencia objetivo: < 300 ms desde "gemma" hasta beep + ducking + STT armado.

## Fig 4.03 — Wake activation

```mermaid
sequenceDiagram
    autonumber
    participant U as Usuario
    participant PA as PortAudio (sounddevice)
    participant AC as AudioCapture._sd_callback
    participant Pump as AudioCapture._pump_loop
    participant Ring as ring buffer 5s
    participant WD as WakeDetector (Vosk)
    participant VC as VoiceController
    participant Duck as _AudioDucker
    participant BUS as EventBus

    Note over U,PA: Estado inicial: VC=IDLE_LISTENING<br/>(WakeDetector cargado, Vosk vocab restringido a ['gemma','hey gemma','[unk]'])
    U->>PA: dice "gemma"
    PA->>AC: callback(indata 512 samples)
    AC->>AC: .copy() del buffer (PortAudio reusa)
    AC->>Pump: queue.put_nowait(chunk)
    Pump->>Ring: append(chunk) (deque maxlen 5s)
    Pump->>VC: _on_audio_chunk(chunk)
    VC->>WD: feed(chunk)
    WD->>WD: KaldiRecognizer.AcceptWaveform(chunk)
    Note over WD: Vosk procesa palabra a palabra<br/>devuelve Result() cuando detecta endpoint
    WD->>WD: parse result.words[] con conf >0.85
    alt match("gemma" o "hey gemma")
        WD->>WD: debounce check (>2s desde último wake?)
        WD->>WD: calcular tail_s (cuánto audio post-wake hay en buffer Vosk)
        WD->>VC: on_wake(phrase="gemma", ts, tail_s=0.15)
    else no match o confidence baja
        WD-->>WD: ignora (sigue en IDLE_LISTENING)
    end

    VC->>VC: _on_wake_detected:<br/>capturar snapshot del ring buffer<br/>desde (wake_end - WAKE_SAFETY_MARGIN_S=0.05)
    VC->>Ring: snapshot_tail(tail_s + 0.05)
    Ring-->>VC: np.ndarray (audio post-wake, prefix para STT)
    VC->>VC: _pending_snapshot = snapshot
    VC->>VC: _set_state(WAKE_DETECTED)
    VC->>BUS: pub state=WAKE_DETECTED
    opt beep_on_wake
        VC->>VC: _play_beep()
        Note over VC: beep síncrono ~30ms via sounddevice
    end

    VC->>Duck: duck() (encola intent, non-blocking)
    Duck->>Duck: COM thread procesa: GetMasterVolumeLevelScalar → save → SetMasterVolumeLevelScalar(0.15)

    VC->>VC: 200ms grace (WAKE_FEEDBACK_MS)
    VC->>VC: _set_state(LISTENING)
    VC->>BUS: pub state=LISTENING

    VC->>VC: _start_stt_thread()
    VC->>VC: _start_listening_timeout (5s para empezar a hablar)

    Note over U: usuario empieza el comando real ("abre Spotify")
    PA->>AC: chunks siguientes
    AC->>Pump: queue.put
    Pump->>VC: _on_audio_chunk
    VC->>VC: chunks van al _stt_chunks list (no más a Wake)
    VC->>VC: detecta speech started → _set_state(TRANSCRIBING)
    VC->>BUS: pub state=TRANSCRIBING

    Note over VC,WD: WakeDetector queda EN PAUSA hasta que VC vuelva a IDLE_LISTENING
```

## Tuning crítico

| Parámetro | Default | Por qué |
|---|---|---|
| Vosk vocab restringido | `["gemma","hey gemma","[unk]"]` | acota falsos positivos (palabras foneticamente similares) |
| `WAKE_MIN_CONFIDENCE` | `0.85` | wakes reales >0.9, falsos positivos <0.7 |
| `WAKE_DEBOUNCE_S` | `2.0` | evita re-wake durante el comando |
| `WAKE_FEEDBACK_MS` | `200` | feedback visual antes de LISTENING |
| `WAKE_SAFETY_MARGIN_S` | `0.05` | Vosk tiene jitter ~50ms en word timestamps |
| `CHUNK_SAMPLES` | `512` (~32ms @ 16kHz) | EXACTO Silero VAD v5 requirement |
| `RING_BUFFER_SECONDS` | `5` | espacio para "rebobinar" pre-wake si fuera necesario |
| `LISTENING_TIMEOUT_S` | `5.0` | si no se empieza a hablar, vuelve a idle |

## Hallazgos a `_findings_seed.md`

- **Patrón "snapshot post-wake + prefix_audio al STT"** es la diferencia técnica clave que evita perder los primeros fonemas del comando ("abre" → "bre"). Bien implementado.
- **Ducking corre en COM thread separado para no glitchear el mic** — comentario del código lo justifica explícitamente. Diseño consciente.
- **Si el ring buffer se llena y nadie hace snapshot**, el deque drops oldest — el ring de 5s alcanza para wake + comando corto pero no para el caso "user habla largo antes de wake" (que no es el caso normal).
- **No hay test de "wake en idioma distinto del modelo"** — el modelo Vosk es `es-0.42`. Si el usuario dice "Gemma" con acento inglés (`/ˈdʒɛmə/`), Vosk ES puede no matchear. Verificar Fase 7.
