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

## Fuentes

- [Model card nvidia/parakeet-tdt-0.6b-v3 (HuggingFace)](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3)
- [sherpa-onnx NeMo transducer models](https://k2-fsa.github.io/sherpa/onnx/pretrained_models/offline-transducer/nemo-transducer-models.html)
- [parakeet v3 FastAPI wrapper (comunidad, referencia de uso)](https://github.com/groxaxo/parakeet-tdt-0.6b-v3-fastapi-openai)
- [Together AI — Parakeet TDT 0.6B v3](https://www.together.ai/models/parakeet-tdt-0-6b-v3)
