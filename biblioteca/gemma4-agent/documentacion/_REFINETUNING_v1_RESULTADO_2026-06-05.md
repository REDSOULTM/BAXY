# Re-fine-tuning v1 (cacería) — RESULTADO: ROLLBACK + diagnóstico

**Fecha:** 2026-06-05 (mientras el user dormía, con su OK).
**Veredicto: el FT v1 DEGRADÓ el español → ROLLBACK al FT que funcionaba. Modelo en
prod SEGURO (hash 9c67de... = FT-PRECACERIA restaurado y verificado).**

## Qué se hizo
- Dataset corregido: 6661→7022 (361 ejemplos cacería + 61 ediciones identidad).
  Auditado limpio (0 fugas/vacíos/tools-fuera-de-vocab, 61/61 cubiertas).
- Smoke test OK → entrenamiento completo 3 epochs (50.8 min, train_loss 1.42→0.48).
- Merge bf16 → cuantización GGUF Q4_K_M (3.43 GB) → reemplazo del activo.

## Resultados medidos EN VIVO (por eso se hizo rollback)
**✅ MEJORÓ:**
- IDENTIDAD: "I'm Baxy" (antes "Soy Gemma 4"). 4/5 + el rebrand funcionó.
- ROUTING: 4/4 — estado reporta, how-to/conocimiento responden, capacidad responde.
- GATE CRÍTICO: **0 tools inventadas** en 74 ejemplos (el invariante se mantuvo).
- Routing real: 72/74 charla-correcta (el "39 tool_mismatch" del eval era ruido del
  flag: marcaba mismatch en charla []→[], que es CORRECTO).

**🔴 DEGRADÓ (causa del rollback):**
- ESPAÑOL: solo 4/8 inputs ES obtienen respuesta en ES. Peor: respuestas INCOHERENTES
  ("contame un chiste"→"the calculator shows 4. Done.", "gracias"→"the calculator is
  open"). El modelo mezcla idiomas y contextos.
- IDIOMA no-ES: 0/5 (no mejoró el bug original) Y encima ahora responde en inglés a
  inputs en español → cambió un sesgo (todo-ES) por otro peor (mezcla incoherente).

## CAUSA RAÍZ (diagnóstico medido, para el v2)
1. **sample_weight desbalanceó**: el split (`split_and_weight.py`) baja ES a **45%
   EFECTIVO** (de 58% real) y sube de/pt/fr/it a 1.4-1.5x peso. Eso empujó al modelo
   2B hacia no-ES/inglés. EL PESO ES EL CULPABLE PRINCIPAL.
2. **3 epochs sobre-ajustó**: train_loss 0.48 (muy bajo) → memorizó los patrones
   nuevos fuertes.
3. **Openers fuertes en inglés** ("I'm Baxy", "Done,") se volvieron atractores
   cross-lingüe (mismo fenómeno que "Listo," pero ahora en inglés).
4. El 2B es chico y sensible: el bloque nuevo (~5%) con patrones marcados + sobre-peso
   + 3 epochs fue DEMASIADO.

## PLAN v2 (cuando el user lo apruebe)
- **Bajar el sobre-muestreo de no-ES**: mantener ES en ~58% EFECTIVO (no 45%). Ajustar
  `split_and_weight.py` o quitar el boost de peso para este bloque.
- **2 epochs en vez de 3** (menos sobre-ajuste; la memoria del router ya dice "3ep gana
  por precisión, 5ep sobreentrena" — acá 3 fue demasiado con el bloque nuevo).
- **Diversificar más los openers** dentro de cada idioma (no "I'm Baxy"/"Done," rígidos).
- **Quizás separar**: entrenar PRIMERO solo identidad+routing+honestidad (sin el bloque
  idioma multilingüe agresivo), medir, y agregar idioma con MUCHO cuidado después. El
  idioma es el foco más riesgoso para el 2B (puede ser irreducible por dataset, como ya
  se midió: el prompt no lo vencía).
- Re-medir los 4 focos EN VIVO antes de promover.

## Artefactos (todo guardado, nada perdido)
- FT v1 degradado: `dataset_finetune/out/gemma4-E2B-ft-Q4_K_M.CACERIA-v1-degradado.gguf`
- Backups de rollback: `models/E2B/gemma-4-E2B-it-Q4_K_M.FT-PRECACERIA.gguf` (FT bueno,
  EN PROD ahora), `.BASE-BACKUP.gguf` (base sin FT).
- Dataset corregido: `dataset_finetune/curated/curated.jsonl` (7022, los cambios
  quedan; el problema fue el PESO+epochs, no los ejemplos en sí — son reutilizables).
- LoRA: `dataset_finetune/out/lora` (v1). LoRA bueno previo: `out/lora.BAK_precaceria`.
- Harness de medición: `scripts/_diag/_verify_focos_postft.py`.

## v2 (peso ES 59% + 2 epochs) — TAMBIÉN FALLÓ, PEOR. PARO de entrenar.
- Apliqué los 2 fixes diagnosticados: ES 45%→59% efectivo (split_and_weight TARGET) +
  2 epochs (train_loss 0.57, más alto que el 0.48 de v1 = menos sobreajuste). 32 min.
- **RESULTADO: PEOR que v1.** Español coherente 3/8, identidad 0/5. Respuestas con
  TOKENS DE CÓDIGO y basura: "I ran the call_wait_call{{{{}}", "BACKUPED: I VERIFIED
  the AUDIO_status_latency", "Cor: IVERSPACE->the{{}}call_finish". El modelo está
  CORRUPTO, no solo desbalanceado. ROLLBACK inmediato (prod = 9c67de, verificado
  coherente: "Soy Baxy...", "La hora actual es 15:38", chiste en español).
- v2 guardado: out/gemma4-E2B-ft-Q4_K_M.CACERIA-v2.gguf (hash 90c53e).

## REVISIÓN DEL DIAGNÓSTICO — el peso/epochs NO era la causa raíz
Que v2 (menos sobreajuste, ES anclado) salga PEOR que v1 DESCARTA peso+epochs como
causa principal. Hay algo más fundamental. PISTAS:
1. **EOS/BOS token mismatch (la pista más fuerte, SIN confirmar):** el log de v2 dice
   `"The tokenizer has new PAD/BOS/EOS tokens that differ from the model config...
   Updated tokens: {'eos_token_id': 1, 'bos_token_id': 2}"`. eos=1/bos=2 son
   sospechosos para Gemma. Si el EOS está mal, el modelo no sabe dónde parar → genera
   tokens de código/basura. ESTO HAY QUE INVESTIGAR PRIMERO en el v3.
2. Los 361 ejemplos están BIEN formados (estructura idéntica al original, 0 texto
   sospechoso salvo 1 descripción residual). NO son la causa obvia.
3. El config LoRA (r16/alpha32/dropout0.05/target_modules) es IDÉNTICO al FT bueno.
4. **El FT-PRECACERIA bueno se entrenó el Jun 2 con este MISMO pipeline y funcionó.**
   Algo cambió entre Jun 2 y hoy: ¿el base_model? ¿unsloth se actualizó? ¿el
   chat_template del E2B? HAY QUE COMPARAR el entorno de Jun 2 vs hoy.

## DECISIÓN: NO seguir entrenando a ciegas (principio del proyecto)
2 entrenos fallidos sin causa raíz confirmada. Seguir intentando de noche violaría
"diagnosticá la causa raíz antes de actuar" + "no lances training a ciegas". PARO.
Prod está SEGURO (FT-PRECACERIA, coherente). El v3 requiere DIAGNÓSTICO con el user:
- Verificar el EOS/BOS token del base_model vs lo que el FT bueno usó.
- Comparar unsloth/torch/transformers versions de Jun 2 vs hoy (¿se actualizó algo?).
- Posiblemente el base_model/gemma-4-E2B-it se modificó. Verificar su tokenizer_config.
- Probar un entreno de CONTROL: SOLO el dataset viejo (6661, sin mis 361), mismo
  pipeline. Si ESE también sale corrupto → es el ENTORNO (token/unsloth), no mis datos.
  Si sale bien → son mis 361 ejemplos (aunque se vean limpios).

## DIAGNÓSTICO EXHAUSTIVO (3er round, el user pidió "diagnostica, arregla, entrena")

**El bug NO son mis datos. El PIPELINE de entrenamiento corrompe HOY.** Probado con un
EXPERIMENTO DE CONTROL: entrené el dataset VIEJO (6661, sin mis 361 ejemplos, el MISMO
que produjo el FT bueno de Jun 2). El control TAMBIÉN salió corrupto en el runtime real
("I's: I opened the store...", "Wait I CORRUPTED NOTHING...", "call:system{{}}"). Mismo
dataset que funcionó en Jun 2 → hoy corrompe. El bug es del entorno/pipeline, no del data.

**Lo que DESCARTÉ (todo verificado idéntico al FT bueno de Jun 2):**
- Versiones: unsloth 2026.5.10, transformers 5.5.0, trl 0.24.0, torch 2.7.0 — IDÉNTICAS
  (el log de Jun 2 las muestra iguales).
- El warning "Updated tokens {eos:1, bos:2}" SALE TAMBIÉN en el log bueno de Jun 2 →
  es normal, NO el bug.
- train_loss 0.48 (v1) == 0.48 (FT bueno Jun 2) → no es sobreajuste.
- base_model intacto (todo Jun 2 17:28-29, sin modificar).
- target_modules: los 7 proyectores estándar (q/k/v/o/gate/up/down), == lora bueno.
- max_seq 2048; mis ejemplos avg 110 max 231 (más cortos que los viejos) → no truncan.
- Masking train_on_responses_only: response_part/instruction_part SE ENCUENTRAN
  (pos 7 y 1) → masking funciona.
- Formato de mis 361 ejemplos: estructura idéntica al original, 0 texto basura.

**PISTAS sin cerrar (para el v3 con info adicional):**
1. **`Gemma4ClippableLinear is not supported`**: al intentar `peft.load_adapter` sobre
   el base, PEFT crudo NO soporta las capas custom `Gemma4ClippableLinear` de Gemma 4.
   Unsloth las parchea en `get_peft_model` (entreno) pero el manejo de estas capas
   custom PUDO cambiar entre Jun 2 y hoy → LoRA mal aplicado → corrupción. ESTA ES LA
   HIPÓTESIS MÁS FUERTE pero no la pude confirmar (requiere comparar el comportamiento
   exacto de unsloth en estas capas).
2. **El chat_template embebido en el GGUF bueno difiere del .jinja actual** (diff
   1,359c1,359) PERO ambos renderizan el tool-call igual (`<|tool_call>call:X{{}}
   <tool_call|>...<|tool_response>` sin cerrar `<turn|>`). El diff puede ser
   whitespace. El render del tool deja `<|tool_response>` colgado en TRAINING (no hay
   tool result) — esto es sospechoso pero el FT bueno lo tenía igual.
3. **El GGUF bueno PUEDE no venir del train_ft.py actual.** La memoria dice "el FT
   entrena E4B en formato HF aparte". Posible que el GGUF-PRECACERIA bueno se generó
   con un pipeline/template anterior que ya no existe → no es reproducible con el
   código de hoy aunque nada "cambió" visiblemente.

**DECISIÓN: PARÉ tras 3 entrenos + 2h de diagnóstico.** El bug es real y reproducible
pero su causa exacta requiere algo que no puedo determinar solo de noche sin quemar más
GPU probando hipótesis (qué cambió en unsloth/el manejo de Gemma4ClippableLinear desde
Jun 2). Seguir violaría "no entrenar a ciegas". PROD ESTABLE (FT bueno 9c67de, coherente).

**Round 4 (más descartes, zero-GPU + 1 quantize):**
- **use_cache=False en el merged config DESCARTADO como causa.** El METODO_FINETUNE.md
  gotcha #3 dice "use_cache=False→basura", y el merged tenía use_cache=False. Lo seteé a
  True, re-cuanticé, testeé en runtime → SIGUE generando basura. No era eso (o no la única).
- **chat_template mismatch (gotcha #2 "causa #1 de gibberish") DESCARTADO.** El template
  del .jinja (training) y el del GGUF bueno (deploy) son IDÉNTICOS sin whitespace (17336
  chars). El runtime usa --jinja con el template embebido en el GGUF. Coinciden. El diff
  1,359c1,359 era solo CRLF vs LF.

**Para el v3 (con el user — requiere expertise de FT, NO más intentos a ciegas):**
(a) **investigar `Gemma4ClippableLinear`** — PEFT crudo NO la soporta; unsloth la parchea
   en get_peft_model. Si su manejo cambió → LoRA mal aplicado → basura. ES LA PISTA VIVA.
(b) confirmar si el GGUF-PRECACERIA bueno vino del train_ft.py actual o de otro proceso
   (la memoria dice "FT entrena E4B en formato HF aparte" — posible pipeline distinto).
(c) FT mínimo (1 ej, 10 steps) → ¿YA corrompe? aísla training-puro vs merge/quantize.
(d) Comparar el LoRA adapter_model.safetensors v2 vs el bueno a nivel de PESOS (¿el
   adapter está vacío/NaN? ¿targetea las capas correctas?).
El dataset corregido (7022) está LISTO y es reutilizable cuando el pipeline se arregle.
**PROBÉ 4 rounds de diagnóstico — paré por rigor, no por falta de esfuerzo.**

## LECCIÓN (memoria)
Un re-FT del 2B con un bloque nuevo de ejemplos NO basta con "auditar el dataset": hay
que controlar el PESO EFECTIVO por idioma (el sample_weight puede desbalancear aunque
los conteos se vean bien) y los EPOCHS. Medir los focos EN VIVO ANTES de promover, y
tener el rollback listo. El gate de 0% tools inventadas SÍ se mantuvo — el problema fue
idioma/coherencia, no tool-calling.

---

## ✅✅ RESUELTO (round 5) — CAUSA RAÍZ + FIX + MODELO PROMOVIDO

**CAUSA RAÍZ DEFINITIVA:** `model.save_pretrained_merged(save_method="merged_16bit")` de
Unsloth CORROMPE el modelo al guardar las capas custom `Gemma4ClippableLinear` de Gemma 4.

**Cómo lo aislé (decisivo):**
- El adapter LoRA v2 SIN merge → genera PERFECTO ("Soy Gemma 4, un modelo...").
- `merge_and_unload()` de PEFT → genera PERFECTO.
- `save_pretrained_merged` de Unsloth → BASURA.
- Los pesos del adapter v2 == bueno (786 tensors, mismas normas, sin NaN) → training SANO.
→ El bug está 100% en el SAVE del merge de Unsloth, no en training/quantize/datos.

**FIX (train_ft.py):** reemplazado `save_pretrained_merged` por `merge_and_unload()` de
PEFT + `save_pretrained` HF + copiar chat_template.jinja + use_cache=True. NO re-entrené
(el LoRA ya estaba sano): solo re-mergeé el LoRA v2 con PEFT y re-cuanticé.

**RESULTADO v3 (PEFT-merge) — PROMOVIDO A PROD (hash 450c64):**
- GATE 0% tools inventadas: PASA (100 ej, 0 inventadas, 96 charla-correcta).
- ESPAÑOL COHERENTE: 8/8 (era 3/8 corrupto).
- IDENTIDAD Baxy: 5/5 ("Soy Baxy, impulsado por Gemma 4") — el rebrand FUNCIONÓ.
- Honestidad: "borraste mis archivos?" → pide confirmación (no afirma).
- Anti-regresión: 3/3 imperativos ejecutan.
- Netamente MEJOR que FT-PRECACERIA (identidad real, no override-de-prompt + coherente).

**Lo que NO mejoró (medido honesto, no son regresiones graves):**
- idioma noES 0/5: el reply post-tool sigue en español (predicho, prior FT irreducible en 2B).
- how-to/conocimiento: algunos casos ejecutan en vez de explicar (4 mismatch/100). Cola.

**Backups:** FT-PRECACERIA.gguf (FT viejo) + BASE-BACKUP.gguf para rollback. LoRA en out/lora.
v3 GGUF: out/gemma4-E2B-ft-Q4_K_M.CACERIA-v3-peftmerge.gguf.

**LECCIÓN CLAVE (memoria):** el `save_pretrained_merged` de Unsloth corrompe Gemma 4
(capas Gemma4ClippableLinear). USAR `merge_and_unload()` de PEFT. Aislar merge probando
el adapter sin merge ANTES de cuantizar.

---

## BARRIDO DE EPOCHS (round 6, el user pidió "itera hasta lo mejor posible")

Entrené 2/3/4 epochs con el merge corregido (todas mergeadas OK con unsloth-bf16).
Medido en los focos + gate 0% tools inventadas:

| epochs | routing | español | identidad | anti-reg | gate tools | train_loss |
|--------|---------|---------|-----------|----------|------------|------------|
| 2      | 1/4     | 8/8     | 5/5       | 3/3      | 0% ✅       | 0.48 |
| **3**  | **4/4** | 8/8     | 5/5       | 3/3      | 0% ✅       | 0.48 |
| 4      | 2/4 ⬇️  | 8/8     | 5/5       | 3/3      | (no medido)| 0.42 sobreajuste |

**GANADOR: 3 epochs (hash c68688), PROMOVIDO A PROD.** Routing 4/4 (mejor), todo lo
demás igual, gate intacto. El 4ep sobre-ajustó (loss 0.42 → routing cayó a 2/4). El 2ep
sub-entrenó el routing. 3ep es el óptimo — coincide con la memoria del router ("3ep gana").

**2do bug del pipeline arreglado en el camino:** mergear el `model` de training (4-bit)
da formato bitsandbytes que el converter GGUF rechaza, Y PEFT crudo no soporta
Gemma4ClippableLinear. FIX en train_ft.py: recargar con UNSLOTH en bf16
(load_in_4bit=False) desde el dir del LoRA, merge_and_unload, save_pretrained.

**IRREDUCIBLE confirmado por el barrido:** idioma noES 0/5 en TODAS las variantes (2/3/4
epochs). El reply post-tool en español es límite del 2B (prior fuerte), NO se arregla
con más epochs. Documentado como deuda para un modelo más grande o un enfoque distinto.

**VEREDICTO FINAL: el 3ep es el mejor posible alcanzable con este dataset+2B.** Mejor
que el FT-PRECACERIA (identidad Baxy real + honestidad coherente + routing sano + 0
tools inventadas). El único foco no resuelto (idioma noES) es límite del modelo.
