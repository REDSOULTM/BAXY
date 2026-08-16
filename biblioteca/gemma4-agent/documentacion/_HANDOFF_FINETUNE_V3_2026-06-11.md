# HANDOFF — Fine-tuning v3 (dataset grounded) · 2026-06-11

> Para el agente de la próxima sesión: este doc es autosuficiente. Leé también
> `documentacion/DATASET_V3_finetune_grounded_2026-06-11.md` (el detalle de las
> 6 iteraciones del dataset) y respetá CLAUDE.md (medí-no-celebres, prueba EN
> VIVO obligatoria, dos repos espejo, privacidad de commits).

## 1. Contexto: por qué existe este trabajo

Baxy alucinaba en producción (2026-06-10): "pon una canción de Michael Jackson"
→ `media(song="Bohemian Rhapsody")` + reply final "Es las 10:42 de la mañana."
(hora real 21:56); "I guess it." → "De nada.". Causa raíz en DOS capas:

1. **Runtime** (YA ARREGLADO, commits `07399a7`..`b8f0344` en main): guard de
   hora-sin-evidencia (`GEMMA4_TIME_CLAIM_GUARD`), gate corto de idioma por
   fórmulas de cierre, detección fuerte es/pt (qué/dime/ã/õ), anti-fabricación
   en rewrites, ejemplo de artista en `media.lean.md`. Verificado en vivo 7/7.
2. **Modelo (la RAÍZ)**: el formato de FT v1/v2 era `[user, assistant(tool_calls
   + reply)]` SIN turno de tool-result → el modelo aprendió a responder datos
   sin mirar resultados. **El fix de raíz es re-entrenar con el dataset v3** —
   eso es lo que queda pendiente y lo que esta sesión dejó 100% preparado.

## 2. Estado actual (TODO listo, falta SOLO entrenar)

- **Dataset**: `dataset_finetune/curated/train_v3.jsonl` — **6.907 filas**,
  formato `[user → tool_call → tool_response(result) → reply grounded]`.
  - 19 gates de validación TODOS PASS (`validate_v3.py`, exit 1 si falla).
  - Cobertura: 67/67 tools, 6 idiomas en toda tool ≥20 ejemplos, computer_use
    siempre con `goal`, multi-turno (66), clarificaciones (399), estados
    honestos (39 attempted + 45 ok:false), error→reintento secuencial (18).
  - Auditado contra el HISTORIAL COMPLETO del proyecto (5.023 turnos reales
    desde mayo): residual 4,6% clasificado y justificado (garble/dev/roleplay).
- **Training script**: `dataset_finetune/scripts/train_ft.py` — detecta
  `train_v3.jsonl` automáticamente, usa `build_messages_v3` (render SECUENCIAL
  call→response→call→response, igual a deploy con `parallel_tool_calls=False`)
  y aplica la **máscara de loss** sobre los bloques tool_response. Epochs
  default 2 (3 sobreajusta el E2B, medido en el rollback v1).
- **Máscara** (CRÍTICA): `mask_v3.py` pone labels=-100 en los spans
  `[<|tool_response>(id 50) .. <tool_response|>(id 51)]`. Sin ella, el FT
  enseñaría a GENERAR resultados (alucinarlos). Test: `_test_mask_v3.py` PASS.
- **Entorno**: venv `.venv_ft` en la raíz del repo (Python 3.12.10, unsloth
  importa OK, verificado 2026-06-11). El runtime del agente es OTRO python
  (3.10) — no mezclar.
- **Modelo base local**: `dataset_finetune/base_model/gemma-4-E2B-it` (con su
  `chat_template.jinja`, el ÚNICO que renderiza tool_calls nativos).
- **Modelo de PRODUCCIÓN actual**:
  `models/E2B/gemma-4-E2B-it-Q4_K_M.gguf` (perfil `vram4`). NO TOCARLO hasta
  que el candidato pase TODOS los gates de aceptación.

## 3. Receta EXACTA del entrenamiento (paso a paso)

**Precondiciones**: GPU libre (VRAM peak ~15,5 GB — el usuario NO puede jugar
ni tener el LLM de Baxy corriendo), ~2-2,5 h totales. Si el usuario está
usando la PC, NO lanzar (CLAUDE.md mandamiento 6).

```powershell
cd "c:\Users\usuario\Desktop\ETC\Programacion\Probando Gemma 4\dataset_finetune\scripts"

# 0. Re-validar el dataset (30 s — SIEMPRE antes de gastar GPU)
python validate_v3.py          # debe decir: VEREDICTO: PASS
python _test_mask_v3.py        # debe decir: MASK v3: PASS

# 1. SMOKE (200 ejemplos, ~5 min): valida pipeline+VRAM+máscara en GPU
..\..\.venv_ft\Scripts\python.exe train_ft.py --smoke
#    Verificar en el log: "dataset: train_v3.jsonl (v3=True)" y
#    "mask tool_response: open=50 close=51". Si no aparecen, NO seguir.

# 2. FULL (~50-80 min, 6907 ej × 2 epochs, QLoRA 4-bit)
..\..\.venv_ft\Scripts\python.exe train_ft.py
#    Hace solo: train → LoRA en out/lora → merge bf16 en out/merged-bf16
#    (recarga Unsloth bf16 + merge_and_unload + save HF — el ÚNICO camino
#    que no corrompe; NUNCA save_pretrained_merged de Unsloth = gibberish,
#    NUNCA PEFT crudo = no soporta Gemma4ClippableLinear,
#    NUNCA mergear el modelo 4-bit = bitsandbytes que el converter rechaza).

# 3. GGUF (bf16 → imatrix → Q4_K_M, ~20-25 min)
..\..\.venv_ft\Scripts\python.exe quantize_gguf.py
#    Usa el converter del commit 5757c4dcb (== build 9090 de prod).
#    Salida: dataset_finetune/out/gemma4-E2B-ft-Q4_K_M.gguf
```

## 4. Gates de ACEPTACIÓN (definidos ANTES de entrenar — medir, no celebrar)

Evaluar el GGUF candidato SIN tocar prod (servirlo aparte o swap temporal con
backup). Scripts existentes: `boot_eval_model.py`, `eval_ft_vs_baseline.py`,
`eval_full_dimensions.py` (en dataset_finetune/scripts), y el harness en vivo
`scripts/_diag/_live_fix_validation_20260611.py`.

| # | Gate | Cómo medir | Criterio |
|---|------|-----------|----------|
| 1 | Tools inventadas | eval CON array de tools (NUNCA sin array: sin array inventa 47% = artefacto) | 0% |
| 2 | Hora sin grounding | 50 prompts vivos de hora/batería/RAM/fecha + variantes; comparar reply vs tool_result | 0 fabricaciones |
| 3 | Español no degrada | eval multilingüe (`eval_full_dimensions.py`) vs baseline | es coherente; ningún idioma cae >2 pts |
| 4 | Identidad | "quién eres" en 6 idiomas | Baxy 6/6 (nunca Carter/Gemma-como-nombre) |
| 5 | Routing intacto | suite `pytest gemma4_agent/tests/` + casos del harness live | igual o mejor que HEAD |
| 6 | EN VIVO (mandamiento 3.5) | `scripts/_boot_server_for_eval.py` + `agent.run_content(...)` con 3-4 fraseos por intención | sin alucinaciones; cadena completa correcta |

**Si CUALQUIER gate falla** → NO deployar. El modelo prod no se tocó; analizar
causa raíz, iterar dataset (build_v3.py es reproducible, seed fija), re-entrenar.
Precedente: el v1 se rolleó back por degradar español — está bien descartar.

## 5. Deploy (solo si 6/6 gates PASS)

```powershell
# 1. Apagar Baxy/llama-server (si corre). 2. Backup del prod:
copy models\E2B\gemma-4-E2B-it-Q4_K_M.gguf models\E2B\gemma-4-E2B-it-Q4_K_M.gguf.BAK_pre_v3
# 3. Swap (a dir TEMP + move si el server tuvo el dir mapeado — error 1224):
copy dataset_finetune\out\gemma4-E2B-ft-Q4_K_M.gguf models\E2B\gemma-4-E2B-it-Q4_K_M.gguf
# 4. Arrancar, smoke en vivo (7 casos del harness), y dejar al usuario probar voz.
```

Después del deploy: actualizar memoria persistente + commit de docs (los dos
remotos, main y Dev, mensajes sin referencias a la conversación).

## 6. Gotchas que YA costaron caro (no repetir)

- **Máscara tool_response**: sin ella el modelo aprende a alucinar resultados.
- **Merge**: solo Unsloth-bf16 + `merge_and_unload()` + save HF.
- **GGUF**: `--outtype bf16` (f16 borra el FT); Q4_K_M con imatrix; nunca 2-bit.
- **Eval de tools**: SIEMPRE con el array de tools en el request.
- **chat_template**: copiar `chat_template.jinja` al merged (el script ya lo hace);
  el token de cierre es `<turn|>` (106), NO eos (1).
- **3 epochs sobreajustan** el E2B (rollback v1) — default ya es 2.
- **No medir cifras con mocks**: el mock execute inventa valores (memoria).
- **Windows cp1252**: los scripts ya fuerzan UTF-8; correr con `python -X utf8`
  los que no.
- El dataset y sus scripts viven en `dataset_finetune/` (GITIGNORED) — la
  receta versionada es `DATASET_V3_finetune_grounded_2026-06-11.md`.

## 7. Backlog v4 (NO bloquea este entrenamiento)

- Results por-paso ricos en encadenamientos largos (hoy genéricos).
- Más multi-turno orgánico (hoy 66 sintéticos).
- Si el FT v3 reduce los disparos de los guards de runtime (medible en traces:
  `reply_anti_pattern_detected`), considerar relajar latencia de repairs.

---

## 8. PROMPT PARA LA PRÓXIMA SESIÓN (copiar y pegar)

```
Vas a cerrar el fine-tuning v3 de Baxy (modelo Gemma 4 E2B-it). Tu trabajo
tiene DOS fases: primero AUDITAR todo el pipeline contrastándolo con papers y
documentación OFICIAL específica de Gemma 4; recién si la auditoría pasa,
entrenar. No confíes en nada por estar escrito: verificá cada afirmación
contra fuentes o medila vos mismo (CLAUDE.md mandamiento 1).

Leé primero, en este orden:
- documentacion/_HANDOFF_FINETUNE_V3_2026-06-11.md  (receta exacta + gates)
- documentacion/DATASET_V3_finetune_grounded_2026-06-11.md  (dataset, 6 iteraciones)
- CLAUDE.md (medir-no-celebrar, prueba EN VIVO obligatoria, dos repos espejo)
- Memoria persistente: dataset-v3-grounded-2026-06-11, gemma4-finetune-oficial,
  refinetuning-v1-rollback, finetune-unsloth-entorno.

FASE 1 — AUDITORÍA CONTRA FUENTES (sin GPU, ~1 h):
Contrastá CADA pieza del pipeline contra la documentación oficial de Gemma 4
(ai.google.dev/gemma — model card y guía de fine-tuning, post-cutoff: BUSCALA,
no respondas de memoria), la guía de Unsloth para Gemma 4 (unsloth.ai/docs/
models/gemma-4/train), el chat_template.jinja REAL del modelo local
(dataset_finetune/base_model/gemma-4-E2B-it/), y los papers de function-calling
(APIGen arXiv:2406.18518, ToolMind arXiv:2511.15718, FunReason-MT
arXiv:2510.24645, reflexión-tras-fallo arXiv:2509.18847). Verificá puntualmente:
 1. FORMATO: que el render de build_messages_v3 (train_ft.py) sea bit-idéntico
    a lo que el llama-server de prod re-alimenta (tokens <|turn>, <|tool_call>,
    <|tool_response>, cierre <turn|> id 106 ≠ eos id 1). Renderizá ejemplos
    reales por el jinja y compará contra un trace de producción.
 2. MÁSCARA: que enmascarar los spans tool_response (ids 50-51, mask_v3.py)
    sea consistente con cómo Unsloth/HF documentan train_on_responses_only
    para templates con tool-results DENTRO del turno del modelo; corré
    _test_mask_v3.py y revisá el test vos mismo.
 3. HIPERPARÁMETROS: r=16/alpha=32/dropout 0.05/lr 2e-4/epochs 2/QLoRA 4bit/
    seed 13 — la memoria dice que NO son oficiales (refutado 0-3): contrastá
    con lo que Unsloth/Google recomienden HOY para Gemma 4 E2B y ajustá solo
    con fuente citada o medición propia (sweep corto). OJO: epochs>2 sobreajustó
    el E2B (rollback v1 medido) — no lo subas sin evidencia nueva.
 4. KV-SHARING/E2B: verificá vigente el fix de Unsloth para el bug de
    use_cache=False con num_kv_shared=20 del E2B (memoria: Fix2 presente).
 5. MERGE/GGUF: confirmá que el camino merge (Unsloth-bf16 + merge_and_unload
    + save HF) y la cadena GGUF (convert bf16 → imatrix → Q4_K_M con el
    converter del commit 5757c4dcb) siguen siendo lo correcto vs issues
    abiertos de llama.cpp para Gemma 4 (buscá issues nuevos de junio 2026).
 6. DATASET: corré validate_v3.py (19 gates deben dar PASS) y hacé tu PROPIA
    verificación semántica muestral estilo APIGen (≥30 filas estratificadas:
    ¿pedido↔args↔result↔reply coherentes?). Si encontrás una clase de
    incoherencia, arreglala en build_v3.py e iterá hasta PASS.
Entregable de la fase 1: tabla afirmación→fuente→veredicto (confirmado/
corregido/refutado), con links. Si algo del pipeline contradice una fuente
oficial vigente, CORREGILO antes de entrenar y documentalo.

FASE 2 — ENTRENAR Y MEDIR (solo si la fase 1 cerró sin rojos):
 1. GPU libre (sin juegos ni llama-server; preguntame si hay algo corriendo).
    VRAM peak ~15.5 GB, ~2-2.5 h en total.
 2. Smoke: .venv_ft\Scripts\python.exe train_ft.py --smoke — confirmá en el
    log "v3=True" y "mask tool_response: open=50 close=51".
 3. Full: train_ft.py, después quantize_gguf.py.
 4. Medí los 6 gates de aceptación del handoff (sección 4) SIN tocar prod;
    incluye la prueba EN VIVO (scripts/_boot_server_for_eval.py +
    agent.run_content con 3-4 fraseos por intención — mandamiento 3.5).
 5. 6/6 PASS → backup + swap (sección 5) + smoke vivo final y avisame para
    probar por voz. Cualquier gate FAIL → NO deployes, números crudos + causa
    raíz, iterá el dataset (build_v3.py es reproducible, seed fija).
 6. Memoria persistente actualizada + commit de docs a LOS DOS remotos
    (main y Dev), mensajes impersonales sin referencias al chat.

Reportá separando "lo que sé con evidencia" de "lo que asumo". Cada gate con
su número medido. No celebres sin números.
```
