# Respuestas a las 3 preguntas clarificadoras (research prompt seguimiento)

> Copiar y pegar TODO este documento como respuesta en la conversación
> Claude.ai (Modo Investigación) donde ya pegaste el prompt principal.
> Estas respuestas definen restricciones críticas para que el reporte
> sea accionable.

---

## 1. Licensing — TODO debe ser FREE OSS, sin excepciones

**Picovoice Porcupine queda EXCLUIDO del análisis**, incluso si fuera técnicamente superior. Razones:

- Carter Agent debe poder ser **descargado y usado sin pagar nada**, ahora y siempre.
- No quiero ningún componente del stack que requiera license fee, ni en plan personal ni en plan comercial futuro.
- Picovoice tiene "free for personal use" pero comercial es paid — eso introduce ambigüedad para el usuario final del proyecto OSS. Lo excluyo de raíz.

**Regla clara para la investigación**:

- Solo recomendar componentes con licencia **Apache 2.0, MIT, BSD, MPL, GPL, LGPL, AGPL** o similar — licencias OSS reconocidas que permiten uso comercial sin pagar.
- **NO recomendar**: Picovoice (cualquier producto), ElevenLabs, OpenAI Whisper API, Google Speech, Azure Speech, AWS Transcribe, AssemblyAI, Deepgram, ni cualquier servicio cloud con cuota gratuita limitada.
- Si una librería tiene un modelo gratis pero requiere registración / API key gratuita con cuota, **también excluirla** (introduce setup friction para el usuario final).

Si Picovoice aparece como referencia en el análisis técnico (porque su arquitectura es notable o sus papers son citados), está bien mencionarla como **comparación de referencia académica** pero no como opción a shippear.

---

## 2. Target user scale: optimizar para release open-source

El proyecto tiene un arco temporal:

- **Hoy (2026 Q2)**: yo + 2-3 beta testers cercanos. Caso (a).
- **6-12 meses**: open-source release a una comunidad de developers que quiera hostear su propio agente local. Caso (b).
- **18+ meses**: posibilidad de producto OSS con usuarios no-técnicos (instalable con un installer, sin tocar Python). Caso (c) — **pero siempre OSS, nunca commercial paid**.

**Optimizá para (b) — open-source release a community**. Eso fuerza:

- **Ease of packaging cross-platform**: si requiere más que `pip install <X>` + `pip install <Y>` para tener el voice stack funcionando en Windows + macOS + Linux, es un blocker fuerte.
- **No compilación nativa de Cython/CMake/CUDA toolkit en runtime**: si una librería necesita compilar `.pyx` o requiere CUDA toolkit instalado para runtime (no para training), descalifica para (b).
- **Wheels pre-built para Python 3.10/3.11/3.12 en Windows + macOS + Linux**: requisito mínimo. Si una librería solo tiene wheels Linux (como me pasó con `piper-phonemize` que pretendía usar para training), es un blocker.

**Si una opción es técnicamente superior pero requiere packaging difícil**, mencionala como "academic best" pero recomendá la siguiente que sí es shippeable cross-platform.

**Métrica práctica de "shippeability"**:

- Time-to-first-wake desde `git clone` debe ser < 5 min en una máquina limpia con Python 3.10 y conexión a internet decente.
- Disk footprint del voice stack completo (modelos + libs) < 1 GB idealmente, < 3 GB hard cap.
- RAM footprint en runtime < 1 GB cuando idle, < 2 GB durante inferencia.

---

## 3. "Hey Gemma" es flexible — abrir el espacio de wake phrases

No es lock-in. Es un default razonable pero negociable si hay evidencia de que es problemático.

**Restricciones hard de cualquier wake phrase**:

- **Debe ser custom**, no marca registrada existente (no "Alexa", "Siri", "Cortana", "Ok Google", "Hey Bixby").
- **Debe ser pronunciable en al menos español + inglés** sin distorsión grosera (idealmente cross-lingual).
- **Idealmente 2-4 sílabas**: "Gemma" sola (2 sílabas) puede dispararse con palabras comunes ("gente", "gema", "tema"). "Hey Gemma" (3 sílabas) es más distintivo. 4 sílabas sería aún mejor pero más torpe.
- **Debe existir** o ser **factible entrenar con datos sintéticos disponibles** (Piper voices multilingual + Common Voice + LibriTTS, todo OSS).

**Alternativas a evaluar en la investigación, en orden de preferencia mía**:

1. **"Hey Gemma"** (default actual) — investigá su FAR real y FRR multi-voz. Si <0.5 FP/hour y >85% recall sin fine-tune, mantenerla.
2. **"OK Gemma"** — patrón análogo a "OK Google". La oclusiva fuerte de "OK" puede ser más distintiva que "Hey".
3. **"Hey Gemma four"** — explícito 4-sílabas, más distintivo, costo: ergonomía decir 4 sílabas.
4. **"Computer"** — referencia Star Trek, tiene precedente cultural, costo: aparece en películas/podcasts.
5. **"Jarvis"** — modelo pre-trained existe en openWakeWord upstream (entrenado masivamente). Costo: branding mismatch con "Carter Agent".
6. **Wake-phrase totalmente custom que la investigación proponga**, justificado por features acústicas (oclusivas + vocales abiertas + N sílabas + baja frecuencia en corpora naturales).

**Pedido específico al investigador**:

Incluir una **sección breve de "wake phrase design"** evaluando estas 6 opciones (más cualquier otra que propongas) contra criterios objetivos:

- Frecuencia de la frase en corpora naturales (Common Voice transcripts, OpenSubtitles, etc.) — inverso del FP rate esperado.
- Distinctividad fonética (vocales abiertas + oclusivas iniciales, contraste consonántico).
- Disponibilidad de modelos pre-trained OSS para esa keyword o una variante cercana.
- Compatibilidad cross-lingual (¿suena igual o aceptable cuando un hispanohablante, anglo, o francófono lo pronuncia?).
- Posibilidad de generar dataset positivo sintético con Piper voices en N idiomas sin grabar audio humano.

**Si "Hey Gemma" sale último**, recomendá la mejor alternativa con justificación cuantitativa. **No me casé con el nombre**, sí con que el agente se llame Carter Agent (eso queda) — la wake phrase puede ser otra cosa.

---

## Resumen ejecutivo de estas clarificaciones

- **TODO debe ser OSS gratis sin excepciones, sin Picovoice, sin cloud APIs**.
- **Optimizar para community OSS release** — packaging cross-platform es crítico, técnica superior pero impackageable no sirve.
- **Wake phrase es flexible** — proponer la mejor opción con evidencia. "Hey Gemma" no es sagrado.

Procedé con la investigación con estas restricciones aplicadas. Esperando el reporte completo con tablas comparativas, arquitectura recomendada, roadmap de sprints, y la wake phrase final justificada.
