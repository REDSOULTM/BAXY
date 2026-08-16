# Parakeet TDT 0.6B v3 — uso correcto vs nuestra implementación (2026-06-10)

Investigación con fuentes oficiales (model card NVIDIA + sherpa-onnx) sobre cómo
usar bien Parakeet v3, motivada por: la transcripción mete inglés en español
aunque las settings digan ES. El usuario CONFIRMA que Parakeet da mucho mejor
transcripción que Whisper → no se reemplaza, se usa BIEN.

## Hallazgo central: el idioma NO se puede forzar (es de diseño)

Las **3 fuentes oficiales coinciden**: Parakeet v3 hace **language-ID (LID)
interno automático** y **NO expone ningún parámetro para fijar/forzar el idioma**.
Es un único decoder multilingüe (25 idiomas EU), no decoders por idioma.

- Model card NVIDIA: *"automatically detects the language … without requiring
  additional prompting"*; **"no documented method to force a specific target
  language"**.
- sherpa-onnx (nuestro framework): `from_transducer` NO tiene parámetro de idioma;
  *"a single multilingual decoder, no language-specific files"*.
- Wrappers FastAPI de la comunidad: ninguno expone selección de idioma — todos
  confían en el LID automático.

→ El truco de Whisper (`language="es"` fijo) **NO aplica a Parakeet**. Nuestro
`parakeet_stt.py:171` (`language` ignorado) es CORRECTO; no es un bug nuestro,
es el contrato del modelo.

## La causa real del inglés: limitación OFICIAL en frases cortas

La model card de NVIDIA lo dice EXPLÍCITO:

> **"Not recommended for word-for-word / incomplete sentences as accuracy varies
> based on the context of input text."**

El LID de Parakeet necesita **contexto** (oración completa). En frases cortas o
sueltas ("Tiempo", "But sí", "Listo", un comando de 2-3 palabras) hay poco
contexto → el LID se equivoca y elige **inglés** (idioma mayoritario de su
entrenamiento). Por eso los logs muestran "Really isn't worth it", "Let's see.
I was up." en turnos cortos en español. **No es config; es el modelo en su zona
débil.**

Contraste: el WER de Parakeet en español con contexto es EXCELENTE (Fleurs 3.45%,
MLS 4.39%, CoVoST 3.41% — model card) → por eso da mejor transcripción que
Whisper EN FRASES NORMALES. El problema es SOLO el caso corto/ambiguo.

## Nuestra implementación vs lo correcto (comparación)

| Aspecto | Lo correcto (oficial) | Lo que hacemos | Veredicto |
|---|---|---|---|
| Modelo | parakeet-tdt-0.6b-v3, 25 idiomas | v3 int8 (sherpa-onnx) | ✅ correcto |
| Sample rate | 16 kHz mono | 16 kHz mono (`SAMPLE_RATE`) | ✅ |
| Mel-bins | 128 (NeMo FastConformer) | no forzado, sherpa lee del modelo; medido 80≡128 WER | ✅ |
| Decoding | greedy (default oficial) | `greedy_search` | ✅ |
| `language` param | NO existe / no se puede forzar | ignorado (correcto) | ✅ no es bug |
| blank_penalty | configurable | `GEMMA4_PARAKEET_BLANK_PENALTY=0.8` | ✅ tuneado |
| Audio normaliz. | int16→float32 /32768 | exactamente eso | ✅ |
| **Frases cortas** | **mala zona del modelo (oficial)** | transcribe igual, sin mitigación | ⚠️ **AQUÍ está el gap** |

**Conclusión: nuestra config de Parakeet es CORRECTA.** No usamos mal el modelo.
El único gap es que NO mitigamos su debilidad conocida (frases cortas → LID
inglés).

## Cómo usarlo bien: mitigaciones del caso corto (ranked por ROI, MEDIR antes)

Ninguna toca la config de Parakeet (que está bien). Atacan el caso corto:

1. **Post-detección + re-transcribe selectivo con Whisper (mejor ROI).** Si el
   idioma fijo del usuario es ES (settings) y Parakeet devolvió texto que parece
   inglés (langid/heurística sobre el output), re-transcribir ESE buffer con
   Whisper-`language=es` (que SÍ fija idioma). Latencia extra (~1.5 s) SOLO en el
   caso malo (frase corta mal detectada), no en el 95% bueno. Whisper ya está de
   fallback cargado.
2. **Bias del LID por contexto de sesión.** Si los últimos N turnos fueron ES con
   alta confianza, y el actual sale EN sobre audio corto, tratarlo como ES
   (re-transcribe o descarta el flip). El idioma de una sesión es estable.
3. **Acumular más contexto antes de transcribir** (subir el min de audio / esperar
   un poco más de speech antes de cerrar el endpoint). Riesgo: sube latencia en
   TODOS los turnos; el caso corto es intrínseco al comando ("pará", "sí").
4. **NO forzar idioma en Parakeet** — imposible (oficial). Descartar esa vía.

**Recomendación:** opción 1 (re-transcribe selectivo con Whisper cuando
idioma-fijo=ES y el output parece EN). Aprovecha que Whisper SÍ fija idioma,
paga latencia solo en el caso malo, y conserva la calidad superior de Parakeet
en el 95% normal. MEDIR en vivo (regla #3.5) antes de declarar.

## IMPLEMENTADO (2026-06-11): rescate LID frase-corta — medido

La opción 1 (+ el espíritu de la 2 vía idioma-fijo del perfil) quedó implementada
en `pipeline.py::_lid_rescue`: si el motor es Parakeet, el perfil es no-EN, el
audio dura ≤3 s (env `GEMMA4_STT_LID_RESCUE_MAX_S`) y la salida PARECE inglés
puro (≥2 funcionales EN y CERO marcadores del idioma del perfil), se
re-transcribe ESE buffer con Whisper(language=fijo), cargado LAZY y residente.
Gate `GEMMA4_STT_LID_RESCUE=0`. Log instrumentado: "LID RESCUE".

**Mediciones (todo voz real):**
- Validación textual sobre los fallos EN reales de los logs: 8/8 (los 4 flips
  disparan; "Abre Steam"/code-switching/"But sí" NO).
- Falsos positivos: **0 en 408 casos** (84 comandos RED + 84 truncados a 0.7s +
  60 FLEURS truncados a 1.2s + 180 terceros). WER del corpus RED IDÉNTICO con
  el rescate activo (0.3676 = 0.3676): el camino normal no se toca.
- Latencia extra SOLO en el caso malo: p50 ≈ 1.46 s (Whisper-small CPU).
- GOTCHA medido: el code-switching legítimo ("reproduce The Last of Us en HBO
  Max") NO debe rescatarse — Whisper-es destruyó el título ("el ácido fós en
  HVOM"); por eso " en "/" sí "/" con "/" mi " están en los marcadores ES.
- La zona del flip NO se reproduce offline con audio limpio (0/60 FLEURS
  truncado, 0/84 mic truncado): requiere el garble/ruido de sesión viva — el
  log "LID RESCUE" acumulará la evidencia en uso real.

**Modo adaptativo por RAM (2026-06-11) — el target es 8 GB de RAM:**

Whisper-small residente cuesta RAM que el target NO tiene: **+673 MB** al
cargar (3.7 s) y el unload in-process **retiene 418 MB** en el allocator
(medido con `scripts/_diag/_measure_whisper_rss.py`). whisper-**tiny** como
rescatador queda DESCARTADO por medición: WER 0.8974 sobre los 84 comandos
reales (vs 0.5016 de small) — basura inutilizable aunque pese 75 MB.

Solución: `GEMMA4_STT_LID_RESCUE_MODE = auto | resident | subprocess` (default
`auto`, umbral `GEMMA4_STT_LID_RESIDENT_MIN_GB`, default 12):
- **resident** (RAM ≥ 12 GB, p.ej. máquina de desarrollo): Whisper queda
  cargado tras el primer rescate → rescate p50 ≈ 1.46 s.
- **subprocess** (target 8 GB): cada rescate corre en un worker EFÍMERO
  (`voice/_lid_rescue_worker.py`: wav temp → faster-whisper small int8 →
  stdout → muere). El SO recupera el 100 % de la RAM al terminar. Costo
  medido end-to-end (spawn + import + carga + transcripción, clip real
  1.2 s): **≈ 7.1–7.4 s**, SOLO en el turno rescatado (raro); el camino
  normal sigue en 0 ms extra. El worker comparte `download_root`
  (`~/.gemma4/models/whisper`) y los DECODE_KWARGS anti-alucinación de
  `stt.py` — sin re-descarga ni red.

**Evidencia persistente del disparo:** la línea `LID RESCUE` de logging muere
en la consola y `full.log` solo graba eventos del BUS — sin más, la zona del
flip (que solo aparece en uso vivo) no dejaría rastro auditable. Cada disparo
se persiste como JSONL en `~/.gemma4/logs/stt_lid_rescue.jsonl` (respeta
`GEMMA4_AGENT_LOGS_DIR`): ts, modo, latencia extra, duración del audio,
idioma, texto Parakeet y texto Whisper. El no-disparo no escribe nada y un
fallo de escritura jamás rompe la transcripción. Revisión: leer ese archivo
tras días de uso real.

Verificación: `scripts/_diag/_verify_lid_rescue_modes.py` PASS (resolución de
modos, camino subprocess completo con texto correcto, evidencia JSONL escrita
con todos los campos, no-disparo 0 ms y sin evidencia espuria); suite voz
298/298; eval rescate 0 falsos disparos / WER intacto.

**Etapa 3 (fp32) cerrada como NO-FACTIBLE hoy:** sherpa-onnx solo publica v3 en
int8 (el fp16 existente es v2, English-only — inútil para 6 idiomas);
sherpa-onnx 1.13.2 es la última versión (13-may-2026) y v3 el último modelo.
fp32 exigiría export propio desde NeMo (~2.4 GB + pipeline de export) contra
fusiones ya diagnosticadas como estructurales del encoder — ROI no justificado.

## Fuentes

- [Model card nvidia/parakeet-tdt-0.6b-v3 (HuggingFace)](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3)
- [sherpa-onnx NeMo transducer models](https://k2-fsa.github.io/sherpa/onnx/pretrained_models/offline-transducer/nemo-transducer-models.html)
- [parakeet v3 FastAPI wrapper (comunidad, referencia de uso)](https://github.com/groxaxo/parakeet-tdt-0.6b-v3-fastapi-openai)
- [Together AI — Parakeet TDT 0.6B v3](https://www.together.ai/models/parakeet-tdt-0-6b-v3)
