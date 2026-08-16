# Cadena de transcripción (wake→LLM): auditoría y perfeccionamiento (2026-06-11)

Auditoría completa del camino **wake → captura → fin-de-habla → STT →
corrector → entrega al LLM**, con harness end-to-end nuevo
(`scripts/voice_chain_eval.py`): alimenta el `VoicePipeline` REAL chunk a
chunk (512 samples, como el AudioPump) con streams compuestos
`[silencio 1.5s][wake TTS "baxy"][pausa 0.25s][comando de VOZ REAL][cola]`,
sobre los 84 comandos RED, en silencio y con voces de fondo (LibriSpeech
held-out) a SNR 10/5 dB. Mide lo que vive el usuario: texto FINAL
post-corrector, latencia de cierre (EOS), drops y capturas atascadas.

## Defectos encontrados (todos medidos antes/después)

### 1. EOS por VAD muere con ruido de fondo — el peor

Con una película/voces de fondo, Silero ve "speech" CONTINUO y el contador
de silencio del fin-de-habla jamás llega: **75/84 capturas nunca cerraron a
SNR 5** → en prod, CADA comando termina por timeout (8 s de espera) y el
buffer entra lleno de diálogo ajeno al LLM.

**Fix — EOS tri-estado contra el nivel del fondo** (`pipeline._handle_capture`):
el calibrador ahora trackea el nivel TÍPICO del fondo (p75-EMA de ventana
rodante) además del piso (p25). Cada chunk se clasifica:
- **quieto** (VAD-silencio O rms ≤ fondo×1.10) → cuenta para EOS
- **evidencia de usuario** (VAD-speech Y rms > fondo×1.25) → resetea
- **zona gris** (fluctuación del fondo) → ni cuenta ni resetea (una ráfaga
  de la peli no reinicia el contador eternamente)

La voz sobre el fondo da ≥1.41× el nivel incluso a SNR 0 (mezcla
=√(1+10^(SNR/10))); al callar vuelve a ~1.0×. En sala silenciosa converge al
comportamiento clásico. Resultado: atascadas **75/84 → 2/84** (SNR 5),
**3/84** (SNR 10); EOS p50 736 ms en silencio (igual que antes).

### 2. El piso de ruido se inflaba con la PROPIA voz (regresión cazada por el harness)

`observe_silence()` hacía EMA por-chunk sobre TODOS los chunks IDLE — la
propia frase de wake (~20 chunks de voz, α=0.05) movía el piso ~64% hacia el
nivel de voz → el gate del wake y el EOS-híbrido quedaban calibrados contra
la VOZ, no el ambiente (cortes a mitad de comando medidos). **Fix:** piso =
EMA hacia el **percentil 25** de una ventana rodante (~5 s) — el habla es a
ráfagas y los huecos entre ellas SÍ son ambiente; p75 de la misma ventana da
el nivel típico del fondo para el EOS. (`noise_calibration.observe()`).

### 3. Fondo lateral dentro de la captura

El buffer capturado lleva preroll y cola con SOLO fondo; el VAD no puede
recortarlo (todo es "speech" para él) y Parakeet transcribía el diálogo
ajeno. **Fix:** `_energy_trim()` — recorte al sobre de energía sobre
fondo×1.25 (50 ms ventanas, pad 150 ms), análogo a `trim_silence` pero por
energía relativa. WER de cadena a SNR 5: 1.42 → **1.00** (el solapamiento
DURANTE el comando es territorio de AEC, P1 del roadmap del wake).

### 4. Drop-list de alucinaciones descartaba palabras reales

`_SILENCE_HALLUCINATIONS` ("gracias", "okay", "you"...) viene del modo de
fallo de WHISPER en silencio. Parakeet NO alucina en silencio (medido) — con
él esas son palabras REALES del usuario y deben llegar al LLM (regla de
producto: el LLM responde; "gracias" descartado dejaba al usuario sin
respuesta). **Fix:** el filtro aplica solo a texto producido por Whisper
(motor primario whisper o rescate LID). El filtro filler-only ("Mm-mm.")
queda para ambos: una vocalización no es un comando.

### 5. "Baxy" solo = descarte silencioso (sin paridad Alexa)

Usuario dice el wake y se queda pensando → la captura cerraba con transcript
vacío post-strip y se descartaba EN SILENCIO. **Fix — segunda oportunidad**
(`_maybe_second_chance`): reabre UNA vez la ventana de escucha (beep +
LISTENING re-emitidos, flag anti-loop, solo para cierres por EOS). Si
tampoco habla, muere por gate de silencio como siempre.

### 6. Decoder: beam medido y DESCARTADO por la métrica de cadena

Sobre clips AISLADOS `modified_beam_search` gana (WER RED 0.334→0.312,
terceros idéntico 0.032, +13 ms). Sobre la CADENA REAL pierde: emitidos
81→73, WER 0.235→0.275 — produce transcripts vacíos en buffers compuestos
(wake+pausa+comando). **La métrica end-to-end gobierna**: greedy+bp0.8 queda
default; `GEMMA4_PARAKEET_DECODING=modified_beam_search` para re-evaluar.
hotwords NO viable: tokens.txt de NeMo es subword, sherpa no codifica
palabras enteras (las saltea y empeora).

## Números finales de cadena (84 comandos reales)

| condición | emitidos | WER | exactos | EOS p50 | atascadas |
|---|---|---|---|---|---|
| silencio (antes)   | 82/84 | 0.265 | 39 | 768 ms | 0 |
| **silencio (ahora)** | 81/84 | **0.235** | **41** | 736 ms | 3* |
| voces SNR5 (antes) | 8/84  | 2.02  | 0  | —      | **75** |
| **voces SNR5 (ahora)** | **71/84** | **1.05** | 4 | 544 ms | **2** |

\* las 3 "atascadas" en silencio son la segunda-oportunidad reabierta cuando
el stream del harness se queda sin audio — en prod esa ventana cierra sola
por gate de silencio (~1.8 s). Los transcripts vacíos que la disparan son
clips RED con problemas propios ("qué hora es" inaudible).

Suite de voz 329/329 (9 tests nuevos en
`gemma4_agent/tests/test_voice_chain_fixes.py`). Env-knobs nuevos:
`GEMMA4_VOICE_EOS_ENERGY_FACTOR` (1.25), `GEMMA4_VOICE_NOISE_WIN_CHUNKS`
(150), `GEMMA4_PARAKEET_DECODING`.

## Lo que la cadena NO puede arreglar (fronteras conocidas)

- **Solapamiento voz-sobre-voz durante el comando** (SNR ≤5): exactos 4/71.
  Es el territorio del AEC con loopback (P1 del roadmap del wake) — la
  cadena ya hace todo lo que se puede sin la señal de referencia.
- Clips con pausas internas > 0.8 s se cortan en la pausa (knob
  `GEMMA4_VOICE_EOS_SILENCE_S`, trade-off latencia/paciencia documentado).
