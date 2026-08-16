# Investigación Carter v4 + Gemma 4 — versión 2 con archivos adjuntados

## Contexto operativo

Esta es la **segunda iteración** de una investigación que falló la primera vez. Cuando armaste el reporte anterior, no tenías acceso a los archivos del repo y trabajaste con búsqueda web pura. El Deliverable 1 quedó como inferencia genérica (51 clases hipotéticas) en lugar de mapeo real al cid contra los 540 casos del bench.

Esta vez te adjunto **6 archivos directamente al chat**. Antes de escribir nada, hay un protocolo de verificación obligatorio que prueba que los leíste. No es opcional.

---

## PASO 1 — Verificación obligatoria de acceso a archivos

Confirmá explícitamente que tenés los 6 archivos adjuntos a este mensaje:

1. `01_BENCH_540_CASOS.md` (128 KB) — los 540 casos reales del bench oficial 18×30
2. `02_full_matrix_runner.py` (39 KB) — el runner que evalúa cada caso
3. `03_models_gemma4.py` (15 KB) — config Gemma 4 actual con CORE_PROMPT v2.3
4. `05_tool_retrieval.py` (6 KB) — las 22 anchors actuales y algoritmo de retrieval
5. `14_OPUS_DOSSIER_PATRONES_A_P.md` (45 KB) — análisis manual qwen3 con los 16 patrones residuales A-P
6. `PROMPT_INVESTIGACION_v1_referencia.md` (10 KB) — el prompt original con los 5 deliverables

Si NO podés leer alguno, parame ahí mismo. Respondé exactamente "no puedo leer el archivo X" y abrimos otro canal. NO escribas el reporte basado solo en este prompt. La iteración anterior ya falló por eso.

---

## PASO 2 — "Índice de lectura" (prueba que sí leíste)

Antes de empezar el reporte, escribí un mini-índice de ~200 palabras que demuestre lectura real de los 6 archivos. Tenés que poder responder con dato concreto del archivo, no inferencia:

**A. Sobre el bench (archivo 01):**
- Confirmá contando: ¿son 540 casos exactos? ¿están organizados en 18 categorías × 30 cada una?
- Citá el cid, severidad y prompt textual de UN caso de cada categoría que más te llame la atención (mínimo 3 cids reales, ej. `C09-04 P0 "..."` — el prompt textual del archivo, no inventado)
- ¿La categoría que llamamos "C14 misiones compuestas" se llama así literalmente en el archivo, o tiene otro nombre?

**B. Sobre el runner (archivo 02):**
- ¿Cómo se llama la función que decide PASS/PARTIAL/FAIL para cada caso?
- ¿Qué campo del case object define el budget temporal?
- ¿Hay alguna lógica especial para casos donde `expected_tools` está vacío?

**C. Sobre Gemma 4 actual (archivo 03):**
- Citá UNA regla del CORE_PROMPT v2.3 textualmente (ej. "regla 9 dice exactamente: ...")
- ¿Cuál es la última regla numérica del CORE_PROMPT? (R1 a Rn, decime el n)
- ¿Qué `LLAMA_SERVER_FLAGS` están definidos hoy? (lista los flags exactos)

**D. Sobre tool retrieval (archivo 05):**
- Lista las 22 tools en `_ANCHOR_TOOL_NAMES` exactas (es un frozenset, las podés copiar)
- ¿Qué `top_k` default usa el retrieval?
- ¿El retrieval usa BM25 hoy, o solo embeddings densos?

**E. Sobre patrones A-P (archivo 14):**
- ¿Cuántos patrones residuales hay listados? (¿son 16 como dice el prompt v1, o un número distinto?)
- ¿Qué categoría del bench tiene más FALSE_PASS según el dossier?
- Citá UN cid específico marcado como FALSE_PASS GRAVE (uno solo, con el patrón al que pertenece)

**F. Sobre el prompt original (archivo PROMPT_INVESTIGACION_v1):**
- ¿Cuál es el techo realista que el usuario aceptó como output? ¿(a) PASS oficial, (b) PASS REAL, o (c) ambos?

Si no podés responder los 6 puntos sin abrir los archivos, parate.

---

## PASO 3 — Confirmación con el usuario antes del reporte

Una vez que pasaste el índice, **NO arranques inmediatamente el reporte**. Mostrá el índice y preguntá:

> "Confirmé lectura de los 6 archivos. ¿Procedo con los 5 deliverables del PROMPT_INVESTIGACION_v1?"

Esperá respuesta. Si el usuario dice "sí, adelante", ahí arrancás. Si el índice tiene errores (ej. dijiste que el bench tiene 510 casos cuando son 540), el usuario te va a corregir y rearmás antes de gastar 6-10h en un reporte basado en una mala lectura.

---

## PASO 4 — Generar los 5 deliverables (igual que en v1, pero con datos reales)

Seguí el archivo `PROMPT_INVESTIGACION_v1_referencia.md` adjunto para los 5 deliverables, restricciones y output esperado. **La diferencia clave vs la versión anterior**:

### Deliverable 1 (mapeo 540)

Cada cid mencionado tiene que ser un cid REAL del archivo 01, no inferido. Si agrupás clases, las clases tienen que listar cids específicos:

❌ MAL (lo que hizo v1): `"C03-{atemporal-canónico} (~22 casos): capital, fórmula, número π"`

✅ BIEN: `"Patrón: conocimiento atemporal (clase agrupada). cids cubiertos: C03-04, C03-12, C03-19, C03-21 [hasta 22 cids reales del archivo 01, listados]"`

### Deliverable 2 (CORE_PROMPT v3)

Cuando diagnostiques qué reglas sobran/faltan/contradicen, citá las reglas reales del archivo 03 con su número. Ejemplo:

❌ MAL: "Regla típica de v2.3 'respondé en español' sobra"

✅ BIEN: "Regla R3 actual del archivo 03 dice [cita textual] — sobra porque [razón]; reemplazar por [propuesta]"

### Deliverable 3 (anchors)

Diff explícito contra las 22 anchors reales del archivo 05:

```
ANCHORS ACTUALES (del archivo 05):     ANCHORS PROPUESTAS:
1. memory_save                          ← MANTENER (justificación)
2. memory_recall                        ← REMOVER (no aparece en bench, anchor genérico)
...
22. terminal_run                        ← MANTENER
                                        ← AGREGAR: [tool nueva no anchor hoy]
```

### Deliverable 5 (techo realista por categoría)

Estimaciones por categoría tienen que basarse en el dossier 14 real. Si el dossier dice "C09 tuvo 11 FALSE_PASS de 30 casos en qwen3" (cita textual del archivo 14), tu estimación de "C09 con Gemma 4 tras stages" tiene que partir de ese número, no de inferencia.

---

## Restricciones (recordatorio del v1)

- Modelo fijo: `gemma-4-E4B-it-UD-IQ2_M`
- Hardware fijo: RTX 4060 Ti 16 GB CUDA
- Stack fijo: llama.cpp b9090, llama-server, Carter v4 con sus 59 tools
- VRAM target: ≤8 GB pico
- Latencia Alexa-tier: trivial <5s, tool simple <8s, app open <15s, misión <30s
- Sin per-app hardcodes
- Audio nativo: omitido (Whisper aparte futuro)
- NO romper qwen3 fallback (módulo `models/qwen3.py` debe seguir funcionando)
- Doble número en techo: PASS oficial + PASS REAL (delta = deuda de honestidad)

---

## Lo que NO querés ver en el reporte

- "REQUIERE FS — placeholder" en ningún lado. Ya tenés FS via adjuntos.
- Inferencias sobre cids que no leíste — tenés los 540 enfrente
- Inventarte el comportamiento de Gemma 4 basado en Gemma 3 — el archivo 03 tiene el research dossier embebido como comentarios; basate ahí
- Upsells del techo — el v1 te enseñó que 540/540 es imposible; mantené esa honestidad

---

## Output final esperado

Un único documento markdown con los 5 deliverables (~3000-5000 líneas), siguiendo la estructura del PROMPT_INVESTIGACION_v1_referencia. Cada deliverable basado en datos reales de los 6 archivos adjuntados.

Empezá por el PASO 1 (verificación de acceso), después PASO 2 (índice de lectura), después PASO 3 (confirmación con el usuario), y RECIÉN AHÍ el reporte completo.

Adelante.
