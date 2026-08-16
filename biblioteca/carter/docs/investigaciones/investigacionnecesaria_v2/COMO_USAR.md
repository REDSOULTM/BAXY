# Cómo usar este paquete v2 en claude.ai

## TL;DR

1. Abrí un chat **NUEVO** en claude.ai (NO continuación del anterior — empezá de cero)
2. Adjuntá los 6 archivos al primer mensaje (drag & drop o botón 📎)
3. Pegá el contenido de `PROMPT_v2_PEGAR_AL_CHAT.md` como mensaje
4. Esperá la respuesta del PASO 1 + PASO 2

---

## Paso a paso detallado

### 1. Abrir chat nuevo

- Andá a https://claude.ai
- Click en "New chat"
- Seleccioná modelo Claude Opus 4.x (el más capaz)
- NO uses el chat anterior — el contexto sucio de la v1 fallida puede contaminar la v2

### 2. Adjuntar los 6 archivos

En el cuadro de texto del primer mensaje:

- **Botón 📎 (clip)** o arrastrá los archivos directo a la ventana

Los 6 archivos a adjuntar (todos en `investigacionnecesaria_v2/`):

```
01_BENCH_540_CASOS.md            (128 KB)
02_full_matrix_runner.py         (39 KB)
03_models_gemma4.py              (15 KB)
05_tool_retrieval.py             (6 KB)
14_OPUS_DOSSIER_PATRONES_A_P.md  (45 KB)
PROMPT_INVESTIGACION_v1_referencia.md  (10 KB)
```

**Total: 252 KB**, dentro del límite de claude.ai (que acepta hasta ~30 MB y 20 archivos por mensaje).

### 3. Pegar el prompt v2

Abrí `PROMPT_v2_PEGAR_AL_CHAT.md` en cualquier editor, copiá TODO el contenido, pegalo en el cuadro de mensaje (debajo de los archivos adjuntos).

### 4. Enviar

Click en enviar (o Ctrl+Enter). Opus debería:

a) **Confirmar acceso a los 6 archivos** (PASO 1)
b) **Hacer el índice de lectura** (PASO 2) — ~200 palabras con datos concretos
c) **Pedirte confirmación** antes de generar el reporte (PASO 3)

---

## Qué hacer en cada respuesta de Opus

### Si Opus dice "no puedo leer el archivo X"

PARÁ. NO sigas. Probá:

1. Verificar que el archivo esté efectivamente adjunto (a veces se sube pero no se procesa)
2. Si seguís sin poder, andá a otra interfaz o avisame para que te ayude a debuggear

### Si Opus hace el índice y se equivoca en algún punto

Le respondés con la corrección antes de que arranque el reporte. Ejemplo:

> "El bench son 540 casos exactos, no 510. La categoría C14 sí se llama así literalmente. La regla R12 del archivo 03 que mencionás no existe — son 12 reglas de R1 a R12. Verificá y volvé a hacer el índice."

Si el índice está bien pero querés ajustar algo del enfoque del reporte, también podés intervenir ahí.

### Si Opus pasa el índice y pide confirmación

Respondés "sí, adelante con los 5 deliverables" y se larga.

### Si Opus arranca el reporte SIN hacer el índice

Cortá inmediatamente: "Antes del reporte hacé el PASO 2 (índice de lectura). Sin eso no puedo confiar en lo que escribas."

---

## Tiempo esperado

- **PASO 1 + PASO 2**: 2-5 minutos (lectura + índice)
- **PASO 3**: 30 segundos (confirmación tuya)
- **Reporte completo**: 20-60 minutos según la profundidad

Total wall-clock: **30 min - 1.5h máximo**.

Si tarda más de 1h sin entregar nada, preguntale qué está pasando.

---

## Cuando llegue el reporte

Guardá el reporte en la raíz del proyecto Carter (donde estaba el v1) y avisame. Voy a:

1. Verificar que sí leyó los archivos (cruzando el reporte contra los cids reales)
2. Diff contra el reporte v1 para ver qué cambia con datos reales
3. Sintetizar el plan de aplicación (Stage A/B/C/D/E)

---

## Si algo falla en el upload

Plan B: **subí solo los 4 archivos más críticos** y dejá los otros como referencia textual:

- `01_BENCH_540_CASOS.md` (128 KB) — INDISPENSABLE
- `03_models_gemma4.py` (15 KB) — INDISPENSABLE
- `05_tool_retrieval.py` (6 KB) — INDISPENSABLE
- `14_OPUS_DOSSIER_PATRONES_A_P.md` (45 KB) — INDISPENSABLE

El runner (02) y el prompt v1 los podés pegar como texto en el mensaje si claude.ai te limita.

---

## Lista de archivos final

```
investigacionnecesaria_v2/
├── COMO_USAR.md                              ← este archivo
├── PROMPT_v2_PEGAR_AL_CHAT.md                ← copiar y pegar al chat
├── 01_BENCH_540_CASOS.md                     ← adjuntar
├── 02_full_matrix_runner.py                  ← adjuntar
├── 03_models_gemma4.py                       ← adjuntar
├── 05_tool_retrieval.py                      ← adjuntar
├── 14_OPUS_DOSSIER_PATRONES_A_P.md           ← adjuntar
└── PROMPT_INVESTIGACION_v1_referencia.md     ← adjuntar
```
