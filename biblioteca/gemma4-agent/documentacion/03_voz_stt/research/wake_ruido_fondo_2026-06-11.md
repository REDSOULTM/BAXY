# Wake-word con audio de fondo: diagnóstico, plan y fuentes (2026-06-11)

## Síntoma de campo

Con una película/serie sonando u otras voces de fondo, el wake ("Baxy") NO
dispara nunca; al parar la reproducción, vuelve a funcionar. Binario, no
probabilístico.

## Causa raíz (medida, no supuesta)

**1. baxy.onnx se entrenó SIN ruido de fondo.** La augmentación de
`livekit-wakeword` mezcla backgrounds vía `mix_with_background()`, pero si
`background_paths` no tiene wavs hace `return audio` **en silencio**
(augment.py:84-85). El `setup` intenta bajar MUSAN-noise de HF y si la
descarga muere solo emite un *warning* (cli.py:240) — y eso fue lo que pasó:
`data/backgrounds` quedó con fragmentos `.incomplete` y CERO wavs. Además
`align_clip_to_end()` coloca la frase en una ventana de **ceros**: el modelo
aprendió "Baxy precedido de silencio". Con audio continuo de fondo la ventana
completa está fuera de distribución.

**2. Gate de energía anti-falso-wake (secundario).** `_on_wake` exige pico
0.2s ≥ 1.6×piso, y el piso EMA converge al nivel del ambiente en ~1-2 s
(α=0.05/chunk de 32 ms). Con una peli sonando, una voz a SNR 0 dB da una
mezcla ≈1.41×piso < 1.6 → rechazaría wakes REALES. Hoy ni se llega a
consultar (el modelo no dispara), pero bloquearía tras el retrain.

## Baseline MEDIDO (scripts/wake_noise_baseline_eval.py)

Held-out universal 500 clips "baxy" (25 voces × 13 idiomas), ruido =
LibriSpeech held-out (voces reales, corpus NO visto en train), ventana
deslizante hop 0.5 s como el harness oficial, threshold de prod 0.25:

| condición   | recall | score p50 | score p90 |
|-------------|--------|-----------|-----------|
| limpio      | 0.820  | 0.688     | 0.914     |
| voces 10 dB | 0.000  | 0.005     | 0.019     |
| voces 5 dB  | 0.000  | 0.004     | 0.013     |
| voces 0 dB  | 0.000  | 0.004     | 0.012     |

Colapso de ~50× del score con CUALQUIER fondo — no es un problema de
threshold. FP solo-ruido: 0/300. Reproducido también EN VIVO por el pipeline
completo (`scripts/_diag/_live_wake_noise_pipeline.py`: escenario ruidoso
FAIL, limpio PASS, FP-en-silencio rechazado PASS, solo-ruido PASS).

Idiomas ya débiles en limpio (preexistente, documentado): nl 0/20, vi 0/20,
zh 0/20.

## Qué hace la industria (fuentes)

- **Amazon/Alexa** (Raju et al., Interspeech 2018): mezclar **música y audio
  de TV/película** a distintos SIR en el training del KWS → **30-45% menos
  false-rejects bajo playback**. Es exactamente el escenario reportado.
- **openWakeWord**: mezcla música + sonidos ambientales + conversación como
  backgrounds, además de RIRs; recomienda Speex noise-suppression opcional.
- **livekit-wakeword**: su `setup` descarga MUSAN (noise) como backgrounds y
  mezcla a SNR 5-15 dB con 3 rondas compuestas (el SNR efectivo final baja).
- **MUSAN** (Snyder et al. 2015, OpenSLR-17, CC/US-PD): corpus estándar de
  music (~42 h) + speech (~60 h) + noise (~6 h) para augmentación.

## Plan ejecutado

1. **Backgrounds reales** (`scripts/wake_backgrounds_setup.py`):
   noise = mirror HF `FluidInference/musan` (774 wavs, 5.1 h; el mirror NO
   trae el audio de music/speech — verificado); music+speech = OpenSLR-17
   `musan.tar.gz` canónico, submuestreados ½ y ½ (el `generate` de livekit
   pre-carga TODO a RAM en float32; MUSAN completo ≈ 25 GB no entra).
   **Holdout**: 1 de cada 12 archivos de music/speech va a
   `data/wake_universal_eval/noise_heldout/` y NO se entrena con ellos.
2. **Retrain** con el orquestador existente (generate de background-splits +
   augment --clean-features + train 30k + export). El run previo completo
   tardó 42 min en la 4060 Ti.
3. **Gates definidos ANTES de entrenar** (sobre held-out, threshold 0.25):
   - G1 limpio ≥ 0.80 global (baseline 0.820, tolerancia -0.02).
   - G2 voces (LibriSpeech) snr5 ≥ 0.60 global.
   - G3 música (MUSAN music HELD-OUT) snr5 ≥ 0.60 global.
   - G4 FP: 0/300 ventanas solo-ruido por fuente Y fp/hr ≤ 1.0 sobre el pool
     LibriSpeech (~10 h).
   - G5 anti-regresión por idioma: ningún idioma con limpio ≥ 0.75 en
     baseline cae < 0.70 limpio.
4. **Capa 2 — gate de energía**: si tras el retrain el gate 1.6× rechaza >5%
   de los fires ruidosos legítimos, separar el factor del WAKE-gate
   (anti-falso-en-silencio: pico≈piso → factor ~1.15 basta; una voz a SNR 0
   da ≈1.41×piso) del umbral de captura (1.6×, intacto para STT). Medido en
   el harness con ambas columnas antes de tocar el código.
5. **Live test** (regla 3.5): pipeline real completo vía `_on_chunk`
   (calibración + preroll + throttle + gate + transición a CAPTURE) con el
   candidato ANTES de pisar producción. El test físico con mic+parlantes
   queda explícitamente para el usuario (irreproducible sin hardware).

## Bitácora de iteraciones del retrain (todas medidas, ninguna deployada aún)

| iter | cambio | limpio | voces s5 | música s5 | confus. | diagnóstico |
|---|---|---|---|---|---|---|
| orig | (backgrounds vacío) | 0.820 | 0.000 | 0.500 | 66% | nunca vio ruido + atajo posicional |
| v1 | +MUSAN 51.5h | 0.832 | 0.008 | 0.552 | 71% | SNR computado sobre ceros (~+5-7 dB más suave) + pool 15% speech + atajo intacto |
| v2 | patch SNR-activo (encadenado) | 0.370 | 0.004 | 0.242 | — | el encadenado de rondas APILA ruido → SNR efectivo ~-5 dB, imposible |
| v3 | multi-condición sin compounding | 0.428 | 0.028 | 0.284 | — | augment correcto PERO medium subajusta (val interna 0.45 subiendo al corte) |
| v4 | large (256,3) + 45k | 0.662 | 0.134 | 0.584 | **30%** | val interna ESTANCADA en 0.70 desde step 36k → el cuello es DATA |
| v5 | n_samples 5k→10k + 60k steps | (corriendo) | | | | hipótesis: diversidad SLERP duplicada corre la meseta |

Lecciones acumuladas: (a) el patch de augment es correcto y necesario
(confusables 66→30% con negativos end-aligned, en condiciones MÁS duras);
(b) capacidad y datos se destraban en ese orden — medium→large dio +0.23
limpio; (c) la validación interna del trainer es el detector barato de
"¿más steps o más datos?": meseta plana = datos.

Gates para deploy (sin cambios): G1 limpio ≥0.80 · G2 voces-snr5 ≥0.60 ·
G3 música-snr5 ≥0.60 · G4 fp/hr ≤1.0 + 0 FP ventanas · G5 sin colapso de
idioma fuerte · G6 confusables ≤1%. El prod actual (0.820/0.000/0.500/66%)
NO se pisa hasta 6/6: v4 canjea 16 pts de recall limpio por robustez — eso
es una regresión para el caso silencioso (el más común) y los gates lo
bloquean correctamente.

## Techo máximo: peldaños restantes (roadmap, NO en este sprint)

El retrain con ruido + confusables cubre el cuello de botella dominante. Si
los números de uso real muestran residuales, estos son los peldaños
siguientes, EN ORDEN de ROI esperado, con su disparador para encararlos:

### P1 — AEC con loopback WASAPI (el peldaño "Alexa de verdad")

Cuando la película suena en el MISMO PC, el sistema CONOCE la señal que está
reproduciendo: capturar el loopback WASAPI y restarlo del mic (echo
cancellation) haría funcionar el wake incluso con la peli MÁS FUERTE que la
voz (SNR negativo) — es lo que hace el hardware de Alexa con su propia
reproducción. Estado del arte en Python/Windows:
- `speexdsp-python`: bindings de Speex AEC, requieren compilación nativa en
  Windows (sin wheels); Speex "atenúa" más que cancela, pero alcanza para
  subir el SNR efectivo varios dB.
- Bindings de WebRTC-APM (AEC3, el mejor OSS): estancados/sin mantenimiento.
- **El problema duro NO es el filtro, es la deriva de reloj**: el stream de
  loopback y el de captura corren con relojes distintos; sin resampling
  adaptativo el filtro diverge en segundos. Resolverlo = subsistema propio
  (captura dual pyaudiowpatch/soundcard + estimación de drift + resampler).
- Costo estimado: sprint dedicado (días, no horas) + CPU extra permanente en
  runtime (~un core parcial). DISPARADOR: si tras el retrain el uso real
  muestra misses sistemáticos con volumen de reproducción alto (SNR < 0).

### P2 — Idiomas débiles en limpio: nl / vi / zh (0/20 ya ANTES del ruido)

Preexistente e independiente del ruido: la fonética TTS de "baxy" no
generaliza a esas voces held-out. Hipótesis a verificar: el checkpoint Piper
de training es en-us (LibriTTS 904 speakers) y esos idiomas quedan lejos.
Palancas: (a) sintetizar positivos de training con checkpoints Piper
nativos de esos idiomas (multi-checkpoint, el pipeline hoy usa 1), (b)
VoxCPM2 multi-idioma (30 idiomas; OJO: VoxCPM segfaultea en RTX 40-series —
workaround SDPA-math o CPU, ver CLAUDE.md), (c) variantes de grafía por
idioma en target_phrases (como "baxi"/"backsy"). DISPARADOR: cuando haya
usuarios reales en esos idiomas; medirlo NO cuesta nada (el held-out ya
existe y el eval reporta por idioma).

### P3 — Positivos con voz REAL grabada (techo de los datos sintéticos)

Todo el training es TTS. El techo absoluto sube con grabaciones reales
(mics/distancias/habitaciones/acentos reales). Vía OSS legal-limpia:
campaña propia de grabación (consentimiento) o crowdsourcing tipo Common
Voice para la frase. Costo: logística, no GPU. DISPARADOR: cuando el recall
real-de-campo (logs) quede sistemáticamente por debajo del recall del
held-out sintético — eso indicaría domain gap TTS→real.

### P4 — Modelo más grande (conv_attention large)

`model_size: medium` está elegido para el presupuesto de CPU idle del
target (8 GB RAM, sin GPU en runtime; el predict corre ~8 Hz con ventana
rodante). Subir a large daría algo más de recall/precisión a costo de CPU
PERMANENTE en idle — en el target modesto no es gratis. DISPARADOR: solo si
P1-P3 no alcanzan y hay presupuesto de CPU medido (re-perfilar el idle con
scripts/_ort_throttle y el throttle de predict).

### Registro de evidencia de campo

El log "wake_word_fired/partial" instrumenta scores en vivo. Para evaluar
residuales tras el retrain: revisar misses reportados por el usuario vs
estos peldaños (¿era SNR<0? → P1; ¿idioma débil? → P2; ¿acento/mic raro? →
P3).

## Fuentes

- [Raju et al. — Data Augmentation for Robust Keyword Spotting under Playback Interference (Amazon, arXiv:1808.00563)](https://arxiv.org/abs/1808.00563)
- [openWakeWord — How it works / training (README)](https://github.com/dscripka/openWakeWord)
- [openWakeWord — background noise & reverberation (discussion #4)](https://github.com/dscripka/openWakeWord/discussions/4)
- [livekit-wakeword (repo oficial)](https://github.com/livekit/livekit-wakeword)
- [livekit-wakeword — docs/augmentation.md (SNR 5-15 dB)](https://github.com/livekit/livekit-wakeword/blob/main/docs/augmentation.md)
- [MUSAN — OpenSLR-17 (Snyder, Chen, Povey 2015)](https://www.openslr.org/17/)
- [Mirror HF FluidInference/musan (noise)](https://huggingface.co/datasets/FluidInference/musan)
- [Home Assistant — enfoque de wake words (contexto microWakeWord)](https://www.home-assistant.io/voice_control/about_wake_word/)
- [speexdsp-python (AEC bindings)](https://github.com/xiongyihui/speexdsp-python)
- [PJSIP — guía AEC (panorama de opciones)](https://docs.pjsip.org/en/latest/specific-guides/audio/aec.html)
