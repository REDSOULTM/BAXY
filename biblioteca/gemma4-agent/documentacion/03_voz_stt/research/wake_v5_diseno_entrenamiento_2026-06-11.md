# Diseño del entrenamiento v5 del wake word — arqueología + estado del arte (2026-06-11)

Investigación previa al v5 (pedida explícitamente: "documentate profundamente
antes de siquiera proponer un v5"). Dos partes: TODO lo entrenado en este
repo con sus lecciones, y el contraste contra pipelines de producción,
usuarios reales y papers.

---

## Parte 1 — Arqueología: las 8 generaciones de wake word de este repo

| gen | fecha | stack | frase | datos | resultado MEDIDO | lección |
|---|---|---|---|---|---|---|
| v8 | 05-19 | openWakeWord | hey gemma | TTS es + RIR (WSL) | — (superada por v9) | primer pipeline propio |
| v9 | 05-19 | openWakeWord | hey gemma | 7 voces Piper ES × 12 frases × 60 + 5% voz del operador | recall local OK pero **universal 0.110** (25 voces/13 idiomas) | **overfit a timbre**: pocas voces TTS + sesgo al operador NO generaliza. La calibración con voz propia es trampa (regla de universalidad) |
| R3.1 | 05-19 | oWW custom | hey gemma | builder denso | 0.829 en held-out CHICO (105 clips) | un held-out pequeño y homogéneo INFLA: el mismo modelo dio 0.110 universal |
| sprint7 | 05-19 | **LiveKit conv-attention** | hey gemma | 5k Piper LibriTTS (904 voces × SLERP) | **0.744 universal / fp 0.000** — primer éxito en 7 sprints | la DIVERSIDAD de voces TTS (904×SLERP≈409k timbres) es lo que generaliza, no el volumen de clips por voz |
| gemma | 05-19 | LiveKit + VoxCPM | "gemma" solo | 5k | no deployado (VoxCPM segfaultea en RTX 40) | palabra pelada corta = riesgo (ver carter); OR de dos modelos quedó en diseño |
| carter-1 | 06-03 | LiveKit | hey/oye/carter mezclado | 5k | **0.27** | conflicto de etiquetas: el auto-generador mete la sub-palabra como negativo mientras era positivo. NO mezclar patrones |
| hey_carter | 06-03 | LiveKit | hey carter | 5k/30k | EN ok, no-EN colapsa (**0.28**) | la /r/ rótica no cruza idiomas. La FONÉTICA de la palabra decide la universalidad |
| **baxy** (prod) | 06-04 | LiveKit | baxy/baxi/backsy | 5k/30k | **0.872 limpio** PASS y deploy | "ks"+vocal final cruza idiomas. PERO: entrenado con backgrounds VACÍO (bug silencioso) → **0.000 con voces de fondo, 66% fake-fires** — el gate de entonces no medía ruido ni confusables |
| v1-v4 | 06-11 | LiveKit+MUSAN | baxy | 5k→large 45k | bitácora en `wake_ruido_fondo_2026-06-11.md`; v4: 0.662/0.134/0.584/30% | augment corregido (3 bugs), capacidad subida; **val interna ESTANCADA en 0.70 = el cuello es DATA** |

**Patrones que se repiten en 8 generaciones:**
1. Cada salto real vino de MÁS DIVERSIDAD de datos (7 voces→904×SLERP) o de
   arreglar un bug del pipeline (padding, backgrounds vacíos, atajo
   posicional) — nunca de tunear hiperparámetros.
2. Los evals chicos/homogéneos mintieron SIEMPRE (R3.1 0.829→0.110 real;
   baxy 0.872→0.000 con ruido). Solo el held-out universal 25 voces × 13
   idiomas + condiciones de ruido + confusables predice el campo.
3. Los fallos silenciosos del pipeline (descarga muerta = warning, no-op de
   mezcla) costaron semanas. Hoy `wake_backgrounds_setup.py` FALLA fuerte.

## Parte 2 — Estado del arte: qué hacen los que SÍ les funciona

### LiveKit producción (el mismo stack nuestro)

Su `configs/prod.yaml` (el que entrena "hey livekit" oficial):
**n_samples 25.000 / val 5.000 / backgrounds 2.000 / steps 100.000 /
conv_attention medium / target_fp_per_hour 0.1** — batch por clase
50/50/1024/50, augment rounds 3, clip 2.0 s.
**Nosotros SIEMPRE entrenamos la versión "overnight reducida": 5k/30k = 1/5
del dato y 1/3 de los steps de su producción.** El comentario está en
nuestro propio hey_gemma.yaml desde mayo ("Scaled-down vs prod.yaml
25k→5k") — funcionó mientras la tarea era fácil (todo limpio); con
multi-condición + confusables endurecidos, la escala reducida tocó techo
(val interna meseta 0.70 con 5k, large, 45k steps).

### openWakeWord (la base de Home Assistant; mismo embedding congelado que LiveKit)

- Config típico de la comunidad: **n_samples 50.000 positivos**; el autor:
  "performance seems to increase smoothly with increasing dataset size".
- Sus modelos oficiales (hey_jarvis etc.): **~30.000 HORAS de negativos**
  (speech/noise/music). Nuestro frontend (melspectrogram+embedding Google,
  congelado) es el MISMO — esa robustez pre-entrenada ya la heredamos; lo
  que entrenamos es el clasificador encima, y ESE es el que necesita ver
  ruido y confusables.
- Usuario real (discussion #45): 3.000 sintéticos + **100 grabaciones
  reales** → "outperformed other wake word listeners". OJO para nosotros:
  válido para producto MONO-usuario; nuestra regla de universalidad lo
  convierte en eval-only (la voz del operador en train fue el error v9).
- Usuario real (issue #127): 20.000 positivos y AÚN falla con ruido — el
  volumen solo no alcanza, la CALIDAD de la mezcla importa (lo que nuestro
  patch v2 del augment arregla: SNR real sobre la frase, no sobre ceros).
- El README oficial recomienda **Speex noise suppression** como front-end
  en ambientes ruidosos (`enable_speex_noise_suppression=True`) — palanca
  RUNTIME que no requiere reentrenar y no hemos probado.

### microWakeWord / Home Assistant

- Optimización **FP-first**: primero minimizar falsos-por-hora sobre
  ambient real (música/casa/conversación), recién después maximizar
  accuracy. Nuestro `target_fp_per_hour: 0.5` es laxo vs su filosofía y el
  0.1 de LiveKit prod — y el fpph interno de v4 subió a ~4: el knob está
  blando para el objetivo "cero fake-calls".
- Validación con **ambient sets reales** (no sintéticos): música, ruidos de
  casa, conversación. Nuestro eval ya lo hace (LibriSpeech + MUSAN held-out).
- "Training a usable model requires a lot of experimentation" — la bitácora
  v1-v5 es exactamente eso, con cada iteración medida.

### Papers

- **Amazon/Alexa** (arXiv:1808.00563): mezclar música + TV/película a
  varios SIR en train → 30-45% menos FRR bajo playback. Implementado (v2+).
- **Confusion words** (arXiv:2011.01460, arXiv:2201.00167,
  LLM-Synth4KWS 2505.22995): negativos confusables sintetizados por TTS
  multi-hablante = el método estándar contra fake-fires; los negativos
  deben cubrir MÁS hablantes/prosodias que los positivos para generalizar.
  Implementado parcialmente (19 confusables; la generalización cross-voz de
  los negativos mejoró 66→30% con end-alignment pero sigue lejos de ≤1%).

## Parte 3 — Gap analysis (nosotros v4 vs estado del arte)

| dimensión | nosotros (v4) | estado del arte | veredicto |
|---|---|---|---|
| positivos | 5.000 | LiveKit prod 25k; oWW 50k; "scaling suave" | **GAP PRINCIPAL — 1/5 del estándar** |
| steps | 45k (val estancada en 36k) | LiveKit prod 100k | gap solo si crece el dato (con 5k, más steps NO ayudan — medido) |
| val sintética | 1.000 | 5.000 | gap menor (ruido estadístico del val interno) |
| diversidad voces | 904 × SLERP ✓ | igual (mismo pipeline) | OK — es lo que nos hizo pasar en sprint7 |
| augment ruido | MUSAN 51.5h, multi-condición, SNR real ✓ (patch v2) | equivalente o mejor (Amazon-style) | OK tras los 3 fixes |
| negativos confusables | 19 frases + end-aligned ✓ | mismo método (papers) | OK en método; mejora con +volumen total |
| target_fp/hr | 0.5 | LiveKit 0.1; mWW FP-first | **endurecer a 0.1-0.25** (ataca G6 fake-calls) |
| front-end runtime | nada | oWW recomienda Speex NS | **experimento barato sin reentrenar** |
| multi-idioma TTS | checkpoint EN único | LiveKit: "multilingual = lower accuracy" (limitación compartida) | techo conocido (P2 roadmap: nl/vi/zh/sv) |
| voz real | nada en train (correcto: universalidad) | comunidad la usa mono-user | mantener EVAL-only |

## Parte 4 — Diseño v5 PROPUESTO (no lanzado; ~3-4 h de GPU)

Alineado a la escala de producción de LiveKit + nuestras correcciones:

```yaml
n_samples: 25000          # 5k era la versión overnight; prod LiveKit = 25k
n_samples_val: 5000       # como prod (val interna estable)
n_background_samples: 2000
n_background_samples_val: 500
steps: 100000             # como prod; la meseta de v4 era por dato, no steps
model_size: large         # nuestra tarea > la de prod (multi-condición +
                          # confusables end-aligned); large ya dio +0.23 y
                          # el costo runtime es ~0 (el frontend domina)
target_fp_per_hour: 0.25  # FP-first (mWW); 0.5 dejó fpph interno ~4
batch_n_per_class: igual (100/100/2048/100)
augment: patch v2 intacto (r0 limpio / r1 5-15 / r2 0-10, sin compounding)
confusables: 19 en train + relax/maximo/biscuit EVAL-ONLY intactos
```

Presupuesto: generate +20k clips ≈ 45-70 min GPU · augment+features ≈ 30-45
min · train 100k large ≈ 100-130 min → **total ≈ 3-4 h** (la 4060 Ti libre,
sin gaming). El generate REANUDA los 10k ya sintetizados.

Expectativa honesta (no promesa): con 5k→25k el "scaling suave" de oWW y la
meseta-por-dato medida sugieren val interna 0.70→0.80+; el gate más duro es
G2 (voces snr5 ≥0.60). Plan si v5 queda corto SOLO en G2: (a) experimento
Speex NS runtime delante del wake (sin reentrenar, medible con el mismo
harness), (b) threshold por punto de operación del sweep, (c) recién después
P2/P3 del roadmap. Si v5 falla varios gates: P2 multi-checkpoint TTS por
idioma es el siguiente peldaño estructural.

Gates de deploy: SIN CAMBIOS (6/6, prod no se pisa).

## Fuentes

- [livekit-wakeword configs/prod.yaml (25k/100k/fp0.1)](https://github.com/livekit/livekit-wakeword/blob/main/configs/prod.yaml)
- [openWakeWord — README/training (scaling suave, 30k h negativos, Speex NS)](https://github.com/dscripka/openWakeWord)
- [oWW discussion #45 — experiencia real entrenando custom wake word](https://github.com/dscripka/openWakeWord/discussions/45)
- [oWW issue #127 — 20k positivos y aún falla con ruido](https://github.com/dscripka/openWakeWord/issues/127)
- [Home Assistant — approach to wake words (Piper + augment + ruido)](https://www.home-assistant.io/voice_control/about_wake_word/)
- [microWakeWord (FP-first, ambient sets, SpecAugment)](https://github.com/kahrendt/microWakeWord)
- [Kevin Ahrendt — microWakeWord](https://www.kevinahrendt.com/micro-wake-word)
- [Raju et al. — KWS under Playback Interference (Amazon, arXiv:1808.00563)](https://arxiv.org/abs/1808.00563)
- [Training Wake Word Detection with Synthesized Speech Data on Confusion Words (arXiv:2011.01460)](https://arxiv.org/abs/2011.01460)
- [Adversarial Samples Against Confusing Words (arXiv:2201.00167)](https://arxiv.org/abs/2201.00167)
- [LLM-Synth4KWS — confusables sintéticos escalables (arXiv:2505.22995)](https://arxiv.org/pdf/2505.22995)
- Bitácora v1-v4 y roadmap: `wake_ruido_fondo_2026-06-11.md` (este repo)
