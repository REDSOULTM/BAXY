# Decisión maestra — Fine-tuning para 4GB de VRAM

**Fecha:** 2026-06-02 · **Método:** 4 workflows multi-agente (~46 agentes, verificación
adversarial) anclados a la build real llama.cpp 9090 (5757c4dcb) y a mediciones del repo.
**Estado:** investigación cerrada · **EJECUTADA** (el plan recomendado abajo se llevó a
cabo: E2B-FT entrenado, gate pasado, **desplegado in-place** en `models/E2B/`; ver
`ESTADO_COMPLETO_2026-06-02.md` y `MISION_COMPLETA_HANDOFF.md`). Este doc se conserva como
el registro de la decisión y su evidencia. Producto = **Baxy**; el MODELO es Gemma 4.

---

## Resumen ejecutivo (la decisión)

1. **El E4B fine-tuneado queda DESCARTADO para 4GB.** Medido: Q4_K_M 5.0GB, Q3_K_M 4.6GB,
   IQ4_XS 4.8GB, IQ3_XXS 3.2GB pero **no carga** (imatrix truncado). Ninguna cuantización
   cargable entra en 4GB con Windows. Offload parcial a RAM rompe la latencia tier-Alexa
   (acantilado de ancho de banda RAM ~50-90GB/s vs VRAM ~300GB/s+).

2. **El camino es Gemma 4 E2B** (la única de la familia que entra en 4GB conservando
   visión+audio nativos, ya integrada en prod, Apache 2.0). Pero con condiciones (abajo).

3. **El "+0.37 de recall" del E4B-FT NO es desplegable como está** — está inflado por
   **over-firing**: dispara tools en charla pura ("jajaja"→memory, "puedes escucharme?"→audio).
   no-tool keep colapsó **0.75 → 0.125** (medido en `out/eval/_dims_*.jsonl`). Cualquier FT
   con la receta actual hereda ese defecto, y un 2B lo sufre MÁS que un 4B.

4. **Antes de re-entrenar hay que (a) arreglar el dataset y (b) correr el control
   E2B-base vs E2B-FT** (misma talla) que NUNCA se corrió — es el único experimento que
   aísla cuánto del +0.37 fue tuning vs tamaño.

---

## Errores que la verificación adversarial corrigió (honestidad)

| Mi claim original | La realidad medida |
|---|---|
| "E2B-Q4 usa ~2.0GB, entra cómodo en 4GB" | Eso fue a **ctx 8k SIN visión**. Con visión + ctx 16k = **~3.36GB cargado, ~4.86GB físico** con reserva WDDM (`profiles.py`, `INFORME_ARQUITECTURA_6GB.md`). Texto-solo entra; texto+visión+ctx-largo va al límite/se desborda a RAM. |
| "recall 0.82, casi el doble" | Inflado por over-firing (dispara casi siempre). no-tool keep 0.125. El número limpio (E2B vs E2B) no existe aún. |
| "E2B no necesita QLoRA, LoRA-16bit cabe en 16GB" | NO verificado. El E4B forzó QLoRA por OOM. E2B *quizás* entra en LoRA-16bit, pero es riesgo abierto, no hecho. |

---

## Hechos verificados (alta confianza)

**Techo 2B vs 4B para tool-routing = pequeño** (4 analogías con misma receta FT):
- Gemma 3 1B: 0.36 base → **0.93** fine-tuneado (casi todo es tuning).
- xLAM 1B vs 7B (misma data): 78.9% vs 88.2% → solo ~9pts a 7× de escala.
- Phi3 1.8B vs 3.8B: 0.86 vs 0.86 tras FT → 0-2pts.
- → **E2B-FT esperado ~0.72-0.82** (centro ~0.76, ALTA incertidumbre; piso 0.55-0.60 si
  el techo del 2B muerde en encadenamiento multi-step y idiomas de poca masa).

**VRAM (build 9090, target 4GB):**
- E2B-Q4 texto-solo: ~2.06GB. Con visión residente + 16k ctx: ~3.36GB cargado.
- KV-cache de gemma4: depende de `--swa-full`. Prod lo deja **ON** (sostiene el prefix-cache
  de latencia) → KV@16k ≈ 1.4GB (NO los 140MB que estimé). Con `--swa-full` OFF baja mucho
  pero rompe el cache-reuse. Trade-off real.
- Config prod ya óptima: `-ngl 99 -c 16384 --swa-full -fa off --no-mmap`, visión lazy.

**Quantización:** Q4_K_M es el **piso seguro** (build 9090: +0.18 ppl; Q3_K_M +0.66 ya
degrada). El embedding de vocab 262144 es un piso que ni Q2 baja de ~3.0GB → bajar de Q4
ahorra 0.1-0.4GB a costa de calidad prohibida por CLAUDE.md. **No bajar de Q4.**

**Visión:** el `mmproj-F16.gguf` (940MB) ES el encoder (SigLIP), archivo separado
obligatorio. No se puede "ahorrar". El FT solo-texto NO lo rompe (`finetune_vision_layers=False`).
El repo YA implementa lo mejor: **router-mode lazy** (`-text` sin mmproj para el 99% de
turnos, `-vision` on-demand). Se puede cuantizar el mmproj a Q8_0 (~mitad) si hace falta.

**Audio nativo (sorpresa verificada en metadata):** el `mmproj-F16.gguf` SÍ contiene el
encoder de audio (`clip.has_audio_encoder=True`, Conformer gemma4a 12 capas 128 mel). PERO:
- **STT nativo NO conviene reemplazar Whisper hoy:** WER ~13-200% (ruidoso) vs Whisper 4-16%,
  límite 30s, exige mmproj BF16 (el de prod es F16), path llama-server con bug abierto (#23688).
  Whisper corre en **CPU = 0 VRAM** — no compite. Mantener Whisper-CPU.
- **TTS nativo NO existe:** Gemma 4 genera **solo texto**. `--model-vocoder` es para OuteTTS,
  no Gemma. Mantener piper_vits/VoxCPM (CPU). Issue de TTS nativo en planning (#21956).

---

## Plan recomendado (condicionado, medir-antes-de-asumir)

**PASO 0 (sin GPU, BLOQUEANTE):** re-medir el holdout vía `agent.run_content` (router REAL
de prod: planner.py + abstain_head + cap5), no el eval crudo. Puede que el router ya filtre
el over-firing y cambie el diagnóstico.

**PASO 1 (barato):** arreglar el DATASET — causa raíz del over-firing:
- Subir no-tool a ~42-45% e igualar la mezcla de categorías DENTRO de cada idioma
  (hoy it/pt/de/fr tienen casi solo `info` de Aya/OASST → enseña atajo idioma→comportamiento).
- +80-120 ejemplos conversacionales `[]` por idioma minoritario (hoy 6-14 vs 676 ES).
- Rellenar args sintéticos mínimos (1-2 slots) en tools frecuentes — el `{}` vacío deja
  medio patrón sin anclar y degrada más a un 2B.

**PASO 2:** bajar `google/gemma-4-E2B-it` HF (NO está; solo el GGUF de inferencia) +
parametrizar `train_ft.py` (hoy hardcodea E4B en líneas 45/162) + usar el **jinja del E2B**
(difiere del E4B en un bloque multimodal).

**PASO 3:** entrenar E2B-FT (QLoRA, language-only, ~1-1.75h), merge bf16, Q4_K_M + imatrix
con cobertura COMPLETA verificada (`llama-imatrix --show-statistics`).

**PASO 4 (gate DOBLE, medido en config 4GB real):** desplegar solo si:
- (i) recall de tool **sube** vs E2B-base, Y
- (ii) no-tool keep **≥ 0.70** (no regresar el over-firing), Y
- (iii) sin regresión por idioma ni en perfiles a11y.
- Medir vía `agent.run_content` (prod), no crudo. n≥50 con-tool por idioma para significancia.

**PASO 5 [COMPLETADO]:** despliegue = reemplazo in-place del GGUF en `models/E2B/` (parity de
chat_template es automática: prod usa `--jinja` sin path = template embebido en el GGUF).
`-fa off` se hereda. Hecho: el `.gguf` de PROD es el FT; base respaldado en `...BASE-BACKUP.gguf`.

---

## Tabla de riesgos

| Riesgo | Prob | Detección | Mitigación |
|---|---|---|---|
| E2B-FT hereda el over-firing | **alta** si no se arregla el dataset | gate (ii) | PASO 1 obligatorio |
| Techo del 2B muerde en multi-step/idiomas | media | recall por idioma n≥50 | aceptar o subir hardware |
| Visión+16k no entra en 4GB real | media-alta | medir pico con mmproj en target | router-lazy + mmproj Q8 + ctx menor |
| LoRA-16bit OOM en E2B | baja-media | primer step | fallback QLoRA-4bit (ya default) |
| imatrix truncado (como el E4B) | media | `--show-statistics` | fallback de tipo por tensor |
| Crash CUDA #22527 en deploy | cierta | arranque | `-fa off` (ya default) |

---

## Costo-beneficio

- **Quedarse con E2B-base (hoy):** 0 costo, sin personalidad ni a11y diferenciado. Recall 0.45-0.51.
- **E2B-FT (recomendado, condicionado):** ~2-3h (arreglar dataset + entrenar + validar) +
  riesgo de no superar el gate. Ganancia probable: personalidad + a11y + recall ~0.72-0.80.
- **E4B-FT:** descartado (no entra en 4GB).
- **Destilación del E4B-FT:** descartada (propaga el sesgo over-firing del teacher).
- **Cambiar de familia (Qwen3-VL-4B, etc.):** descartado salvo que E2B falle el gate —
  re-integración + re-validación multilingüe + se pierde audio nativo.

---

## VISIÓN — VERIFICADA EN VIVO (2026-06-02, build 9090)

Probada de verdad (regla #3.5), no por metadata:
- **FUNCIONA:** E2B + `mmproj-F16.gguf` carga sin crash (bug #21402 NO se reproduce en 9090),
  describe 2 imágenes reales correctamente (`comodeberiaverse.png`, `Comoseveahora.png`),
  **latencia 2.5s**. El log confirma `has vision encoder` + `CLIP using CUDA0` + sirve.
- **VRAM medida:** LLM 2.06GB (breakdown llama.cpp: 1407 modelo+93 KV+560 compute) +
  mmproj visión ~0.94GB = **~3.0GB modelo+visión** en VRAM.
- **Implicación 4GB:** ~3.0GB + Windows (~1-1.5GB) **roza/supera 4GB con visión residente**.
  Por eso prod usa **visión LAZY** (mmproj on-demand, descarga el texto). Texto-solo entra
  cómodo; texto+visión simultáneo va al límite → la carga lazy es obligatoria, no opcional.
- El FT solo-texto NO afecta la visión (mmproj es archivo separado). El E2B-FT la conserva.

## Preguntas abiertas (medir antes de ejecutar)
1. ¿El router de prod (`agent.run_content`) ya mitiga el over-firing? (PASO 0)
2. ¿El bug PLE de llama.cpp #22243 deprime artificialmente el recall del E2B-base?
3. ¿E2B+visión+ctx-real entra de verdad en 4GB, o se desborda a RAM? (medir pico en target)
4. ¿LoRA-16bit del E2B entra en 16GB o fuerza QLoRA?
