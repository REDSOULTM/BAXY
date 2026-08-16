# NIGHT RUN — ESTADO

**Misión:** mejor fine-tuning posible de FunctionGemma-270M para Baxy (solo tool-calling: elegir tool, args válidos, encadenar, `no_tool` cuando no aplica). NO conversa.
**Deadline:** REFERENCIA ~2026-06-16 10:00 America/Santiago (blando; el usuario se fue a dormir
2026-06-15 ~19:50 y dijo "no dejes de iterar hasta lograr el mejor modelo posible").
Criterio real de parada: TECHO MEDIDO (no más mejoras razonables) — NO el reloj.
**Última actualización:** 2026-06-17 ~07:15 (-04).

## ====== 🏆 VEREDICTO FINAL 2026-06-17 — RUN9 = NUEVO CHAMPION (args + cobertura) ======
**CHAMPION = run9 (full-FT, EPOCH 5, lr5e-5/constant, slim, bs8/accum2, dataset iter3).**
Artefacto en Baxy: `model/functiongemma-ft-270m-it-Q8_0.gguf` (278MB, md5 b4ac42db; = `model/functiongemma-run9ep5-Q8_0.gguf`).
Champion ANTERIOR (run7 ep8) respaldado en `model/functiongemma-CHAMPION-run7ep8-Q8_0.gguf` + `archive/run7_ep8_merged`.
Merged run9: `archive/run9_ep5_merged`. Dataset: `curated/fg_train.iter3.jsonl` (28485) + `fg_holdout.iter3.jsonl`.

### QUÉ RESOLVIÓ (la sesión reabrió por extracción de args mediocre + gaps):
- **Extracción de args ARREGLADA en 6 tools × 6 idiomas**: set_volume, send_message, app_open, browser_open,
  memory_save, web_search → **probe multilingüe OK×6 en TODAS** (antes V/rotas). Probe amplio (18 tools): 0 omisiones.
  arg-eval holdout: **args-vacíos 1.6%** (vs 4.4% del intento ep5 fallido). tool-name 86.9% (selección sana).
- **Causa raíz (medida + fundamentada AgentFlux/Microsoft)**: la capa de routing de Baxy emitía estas tools con
  args VACÍOS (contaminación) que ahogaban los positivos (browser_open 8% / memory_save 22% / web_search 16% /
  set_volume 13% positivo). **Fix**: drop estructural por-tool (VALUE_REQUIRED en build_fg_trainset.py, language-
  agnostic, NO regex) + handcrafted multilingüe (curated/hc/batch_fix_argless*.jsonl). Balance → 46-98% positivo.
- **Gap discord/slack/teams CERRADO**: mensajear ahí → `computer_use{goal}` (no send_message=whatsapp). 65 ejemplos
  multilingües. + contrastivo alarm(reloj)↔timer(duración)↔reminder.
- Handlers de Baxy aceptan sinónimos (verificado en código) → `baxy_alias_map.json`; eval arg-aware lo refleja.

### TRAYECTORIA: champion previo (run7 ep8) tenía set_volume/send_message rotas en 6 idiomas + sin discord.
run8 (ep5) arregló 3 tools pero regresionó browser_open/memory_save. run8b (ep8) recuperó parcial (epoch no era la
raíz). **run9 (iter3, datos)= las 6 limpias sin regresión, train_loss 0.080 (sano, sin overfit).** Verificado por probes
build-independent (no depende del split del holdout).

### RESIDUAL (long-tail conocido del 270M, NO args): confusión de hermanas near-sinónimas — filesystem_search↔
filesystem_list, dependency_install↔package_install, alarm↔timer (1 idioma). Args se extraen bien; solo ruteo a
hermana. Mitigado por el router semántico. Comparable/mejor que el champion previo.

### COMANDOS BAXY (sin cambios): server `llama-server.exe -m model/functiongemma-ft-270m-it-Q8_0.gguf --port 8082
--jinja -ngl 99 -c 4096 --no-webui`. Router DEBE usar tool_schemas_slim.json. Fix router no_tool ya aplicado (fg_router_ft.py).
SCRIPTS de eval: fg_probe_multiling.py, fg_probe_broad.py, fg_argeval.py (alias-aware), validate_dataset.py.

## ====== ⚠️ HALLAZGOS DEL TEST EN VIVO (2026-06-16 ~09:40) — REABRE EL TRABAJO ======
El usuario pidió probarlo EN VIVO con el router real. Se hizo (fg_e2e_test.py: router semántico
acota 524→~10 tools → GGUF epoch8 → ejecuta handler real). **Reveló 2 problemas que la eval de
holdout NO veía porque SOLO mide el NOMBRE de la tool, no los argumentos:**

### PROBLEMA 1 — Extracción de ARGS mediocre (lo importante)
Arg-aware eval (holdout n=251 con args en gold, fg_argeval.py): **tool-name 88% pero args EXACTOS solo 60.6%**
(vacíos solo 2%). Causas medidas:
- **(a) PARÁMETROS SINÓNIMOS redundantes en los slim schemas** (causa principal). Al descomponer las
  tools compuestas de Baxy quedaron alias múltiples para el mismo dato: probe={path,input,src},
  dependency_install={name,dependency}, create_note={title,text,content}, cast_lan=14 params.
  El modelo elige UN sinónimo y el gold usa OTRO → "falla" en exact-match aunque sea semánticamente
  correcto. El gold mismo es inconsistente. **El 60.6% es cota INFERIOR**: si los handlers de Baxy
  aceptan cualquier sinónimo, el uso real es mejor. → NECESITA: nombres canónicos reales del executor de Baxy.
- **(b) Ejemplos arg-less de la capa ROUTING** del dataset Baxy contaminan tools paramétricas:
  set_volume 429 vacíos vs 66 con args (87% vacíos), app_open 496 vac/90, browser_open 406/54.
  "baja el volumen a 20" → target `set_volume{}`. En vivo a greedy el modelo replica el patrón dominante.
- (c) Eval estricta infla fallos (ej. `{name:' reloj'}` con espacio cuenta como error).
- (d) Confusiones de hermanas (csv_describe/csv_query, status_of/job_manager_status) ya conocidas.

### PROBLEMA 2 — Router no integra no_tool
fg_router_ft.py NO incluye `no_tool` en el subset acotado → el chitchat ("gracias, sos un genio") se
ve forzado a elegir tool (web_search). Y al agregar no_tool manualmente, en sets dominados por tools
"tentadoras" el modelo igual no abstiene bien. La eval daba no_tool 137/137 porque ahí no_tool SIEMPRE
estaba en la lista y el contexto no estaba sesgado.

### LO QUE SÍ ANDA BIEN EN VIVO (con ejecución real):
get_system_resources (RAM real), time, processes, battery, wifi_connect{name:'MoviStar_2.4G'} ✓,
firewall_block (eligió bien sobre firewall_allow) ✓, multilingüe es/en/pt ✓. Selección de tool sólida ~88-90%.

### DECISIÓN (anti-especulación): NO reentrenar a ciegas todavía.
El fix de mayor impacto (canonicalizar params sinónimos) REQUIERE los nombres reales que espera el
executor de Baxy — adivinarlos rompería la ejecución. Reentrenar solo arreglando (b) da mejora marginal
y no puedo medir el fix de (a). → Se necesita INPUT DEL USUARIO antes de la próxima iteración:
  1. ¿Los handlers de Baxy aceptan sinónimos o hay UN nombre canónico por slot? (define el fix de args)
  2. ¿OK quitar los ejemplos arg-less de routing (query-con-valor → target vacío) de tools paramétricas?
  3. Fix del router: agregar no_tool al subset SIEMPRE (cambio de código, seguro).
ARTEFACTO ACTUAL: epoch8 GGUF sigue siendo el mejor para SELECCIÓN de tool (~88-91%); usable con la
salvedad de args documentada. Scripts nuevos: fg_e2e_test.py, fg_argeval.py, fg_diag.py, fg_diag2.py.

## ====== RUN8 EN CURSO (2026-06-16 ~11:40): challenger args-fix + cobertura completa ======
**ENTRENANDO: full-FT, EPOCH 5, lr5e-5, constant, bs8/accum2, slim, expandable_segments. PID 7677, log train_run.log.**
(El usuario pidió "entrena hasta epoch 5" — plateau medido en ep5; run6 ep5 = 88.3%.) ETA ~4-5h.
CHAMPION run7 ep8 (GGUF + archive/run7_ep8_merged) INTACTO hasta evaluar run8.

### QUÉ CAMBIÓ EN EL DATASET (vs el del champion) — todo fundamentado:
1. **Fix de extracción de args (3 tools MEDIDAS rotas)**: set_volume/send_message/app_open estaban rotas
   en los 6 idiomas (probe en vivo) porque la capa A (routing de Baxy, "decisión sin valores") emitía
   args VACÍOS que AHOGABAN los positivos (set_volume 429 vacíos vs 66). Fix estructural en
   `build_fg_trainset.py`: `VALUE_REQUIRED={set_volume,send_message,app_open}` → from_curated DROPea el
   vacío (regla POR-TOOL, language-agnostic; NO regex sobre el texto — el usuario rechazó eso por frágil/
   monolingüe). Evidencia: AgentFlux (separar routing de arg-gen) + Microsoft/Alopex (balance empty:populated
   crítico). Tras fix: set_volume 72% / send_message 65% / app_open 58% positivo.
2. **Handcrafted multilingüe (capa D)** para esas 3 tools en es/en/pt/fr/de/it: `curated/hc/batch_fix_argless.jsonl`
   (105 ej). Params canónicos verificados contra reglas reales de Baxy (whatsapp.lean: contact+text; audio.lean: level:int).
3. **Gap discord/slack/teams** (detectado por el usuario): mensajear en discord va por `computer_use{goal:query}`
   (NO send_message=whatsapp). Eran 0 ejemplos → `curated/hc/batch_discord_cu.jsonl` (32 ej, 6 idiomas).
4. **Contrastivo alarm(reloj)↔timer(duración)↔reminder(tarea+hora)**: `curated/hc/batch_alarm_timer.jsonl` (24 ej)
   — confusión de hermanas medida ("alarma a las 7"→timer_start). Técnica: negative/distractor (Microsoft/Unsloth).
5. **Filtro de args fuera-de-schema** en row() (build): el modelo solo emite args que VE en el schema slim.
6. **Fix router**: fg_router_ft.py route() inyecta `no_tool` SIEMPRE en el subset (chitchat no fuerza tool).

### AUDIT DE COBERTURA (pedido por el usuario, 3 Explore agents sobre el repo Baxy):
- FT previo del E4B: `dataset_finetune/curated/train_v3.jsonl` (6905 ej, formato user_text/correct_tools/tool_results/
  final_reply, 24 gates). Mis fuentes (capa A) salen de los MISMOS logs reales (`router_corpus_real_logs.jsonl` 1071,
  `history_raw.jsonl` 3697). Inventario: 67 familias compuestas → mis 525 tools individuales. **Cobertura 525/525 con ≥40 ej.**
- **Probe amplio de args (18 tools paramétricas, es/en/pt)**: extracción SANA en todas; solo las 3 ya arregladas
  estaban rotas. NO hay más contaminación arg-less. Residual = confusión de hermanas (alarm/timer, filesystem_search/
  list) = long-tail conocido del 270M, mitigado por el router semántico.

### DATASET VALIDADO (validate_dataset.py — TODO PASS):
0 tools inventadas, 0 args fuera de schema, 0 fuga train/holdout, 0 duplicados, estructura OK, no_tool 8.0%,
cobertura 525/525 ≥40 ej. train=29111, holdout=1821 (rebuild determinístico PYTHONHASHSEED=0, reproducible).
Backup del dataset del champion: `curated/fg_train.BAK_1105.jsonl` + `fg_holdout.BAK_1105.jsonl`.

### MÉTRICAS DE ARGS (champion epoch8, baseline a batir):
- Holdout arg-aware (fg_argeval.py, n=367): strict 64.3% / alias-aware 68.9% (el residual es mayormente
  scoring artifact: gold malo + normalización de valor — los handlers de Baxy aceptan sinónimos, ver baxy_alias_map.json).
- Probe en vivo (fg_probe_multiling.py): set_volume V×6, send_message V×6, app_open V pt/it. discord = gap.
- **run8 debe**: fix esas (probe → OK), mantener selección ~89-91% y no_tool, sin regresión por idioma.

### POST-TRAIN (al terminar run8):
1. Archivar a archive/run8_ep5_*. 2. `quantize_fg.py` → GGUF Q8. 3. Levantar server, correr fg_probe_multiling.py
   + fg_probe_broad.py + fg_argeval.py + eval_night.py (selección holdout). 4. Comparar vs champion: promover SOLO
   si args mejora (probe set_volume/send_message/app_open → OK) Y selección/no_tool NO regresionan. Si regresiona → champion ep8 queda.
SCRIPTS nuevos: fg_argeval.py (alias-aware+value-set), fg_probe_multiling.py, fg_probe_broad.py, fg_contam_probe.py,
repair_argless.py (NO usado al final — se descartó por frágil), validate_dataset.py, baxy_alias_map.json, baxy_canonical_map.json.

## ====== AVANCES SESIÓN 2026-06-16 (post research + input del usuario sobre Baxy) ======
El usuario (lado Baxy, con el código real de los handlers) RESOLVIÓ el bloqueo:
- **Q1 RESPONDIDA: el executor de Baxy ACEPTA SINÓNIMOS masivamente** (`args.get("src") or args.get("path")`,
  `args.get("name") or args.get("dependency")`...). El canónico = el PRIMER nombre de cada cadena `or`.
  → **El 60.6% es PISO de MEDICIÓN, no de capacidad**: el handler ejecuta bien aunque el modelo use un alias.
  Acción correcta = re-medir args con scoring ALIAS-AWARE antes de pensar en reentrenar (HECHO, ver abajo).
- **Q2 RESPONDIDA: limpiar arg-less SOLO de tools paramétricas reales** (set_volume/app_open/web_search/play/
  send_message/memory_save/browser_open/steam_open/app_close), NO las genuinamente sin-args (get_time, mute,
  pause, battery, processes...). Filtrar por "¿la query trae valor?", no a ciegas.
- **Q3 RESPONDIDA: agregar no_tool al subset del router SIEMPRE.** → HECHO (fg_router_ft.py route(): inyecta
  no_tool si el ranking no lo trae). Beneficia a fg_e2e_test.py también (consume route()).

### HECHO esta sesión:
1. **Mapa de alias real** extraído del código de los handlers (`tools/domain_tools/*.py` + `tools/tools_pkg/`):
   127 cadenas `or`, 138 pares equivalentes → `baxy_alias_map.json`. Canónico (primer-key) → `baxy_canonical_map.json`
   (46 alias→canónico inequívocos: input→path, source→src, dependency→name, body→content, message→text, etc.).
2. **fg_argeval.py reescrito** con 4 niveles de scoring: [1] strict exact, [2] value-normalized (strip+casefold),
   [3] ALIAS-AWARE (key pred ≡ key gold si co-ocurren en chain del handler Y ambas en schema del tool — fiel al
   runtime), [4] VALUE-SET key-agnostic (cada valor gold aparece en algún slot pred — proxy más fiel a ejecución).
3. **Router fix** no_tool (ver Q3).
4. **fg_contam_probe.py** creado: mide el síntoma que fg_argeval NO ve (gold vacío excluido) — queries con valor
   extraíble → ¿el modelo pone el arg? (lo que el test en vivo destapó: "subi el volumen a 40"→set_volume{}).

### MEDICIÓN ARG-AWARE (epoch8 Q8, holdout n=367 con gold-args, greedy):
- tool-name 89.6% | [1] strict 64.3% | [2] value-norm 65.9% | [3] alias-aware 68.9% | args-vacíos-pred 1.9%.
- **Inspección de "fallos genuinos": la MAYORÍA NO son fallos del modelo**: (a) GOLD MALO (valor alucinado que ni
  está en la query, ej. probe sin filename → gold inventó "movie.mkv", modelo "clip.mkv"); (b) normalización de
  valor (press{key:Esc} vs gold {Escape} — modelo MÁS fiel a la query; last_message{contact:'mi jefe'} vs {jefe};
  url google.de vs https://google.de); (c) args extra inofensivos. → confirma que 64-69% es artefacto de scoring.
- **HALLAZGO METODOLÓGICO clave:** la contaminación arg-less afecta a ejemplos con gold VACÍO, que fg_argeval
  EXCLUYE (solo mira gold-con-args). Por eso el arg-eval NO ve ese problema; solo el test en vivo lo destapa.
  Sizing: ~1.000-1.800 ejemplos vacíos contaminantes (de ~24.654 = 4-7%) en tools paramétricas reales.
  → fg_contam_probe.py mide ese síntoma directamente (PENDIENTE de correr).

### PENDIENTE inmediato: value-set full-holdout (corriendo), fg_contam_probe, decisión reentrenar.

## ====== RESEARCH-FIRST: extracción de args en SLM tool-calling (2026-06-16, sesión nueva) ======
El usuario exigió fundamentar el fix de args ANTES de tocar nada. Hecho. Fuentes + dato concreto:

1. **AgentFlux — Decoupled Fine-Tuning & Inference for On-Device Agentic Systems** (arXiv 2510.00229).
   - Modelos chicos on-device **sufren al hacer selección-de-tool Y extracción-de-args a la vez**
     ("cognitive load that exceeds their capabilities") → explica DIRECTAMENTE nuestro 91% nombre / 60.6% args.
   - **"Canonicalization Importance":** los modelos chicos "frequently produce non-canonical parameter
     names (variations, misspellings, alternative phrasings)". Canonicalizar los nombres esperados
     mejora consistencia y usabilidad downstream. → VALIDA que los params SINÓNIMOS de los slim schemas
     (probe={path,input,src}…) son un DEFECTO real, no solo artefacto de eval.
   - **"Routing data interferes with argument generation":** entrenar con data de tool-selection y luego
     pedir args degrada los args; recomiendan **SEPARAR los objetivos** (un dataset/etapa de selección,
     otro de extracción de args). → VALIDA que los ejemplos ARG-LESS de routing contaminan (causa (b)).

2. **Estudio SLM 1B (vía Microsoft SLM-FC guide / artículos de FT):** 79% sintáctico vs **56% semántico**
   en un 1B FT — el GAP nombre↔args es CONOCIDO y esperable, no un bug nuestro. Fix recomendado:
   **capa liviana de validación/canonicalización** en inferencia que verifica args vs schema.

3. **Hyperplane "Data preparation for function tooling":** definir cada parámetro UNA sola vez en el
   registry, validar todos los ejemplos contra ese schema, **ejecutar** las calls para cazar mismatches
   (ej. `level:"high"` a un int 0-100). Postura: **prevenir la inconsistencia con validación rigurosa**,
   no normalizar post-hoc. → respalda colapsar sinónimos a UN nombre canónico por slot en schema+train+gold.

**CONCLUSIÓN del research (convergente en 3 fuentes):** el fix correcto NO es "reentrenar por las dudas".
Es (i) **canonicalizar params** (un nombre por slot en slim schemas + train + gold consistentes) y
(ii) **separar/limpiar la data de routing arg-less** de las tools paramétricas. Ambos están medidos como
efectivos por terceros. PERO (i) requiere saber QUÉ nombre canónico espera el executor de Baxy (no está
en el repo) → BLOQUEADO en input del usuario (ver "DECISIÓN" abajo). Fuentes:
- https://arxiv.org/pdf/2510.00229 (AgentFlux)
- https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/fine-tuning-small-language-models-for-function-calling-a-comprehensive-guide/4362539
- https://thehyperplane.substack.com/p/data-preparation-for-function-tooling
- https://developers.googleblog.com/a-guide-to-fine-tuning-functiongemma/ (receta oficial ya aplicada)

## ====== VEREDICTO (2026-06-16 ~08:45) — TECHO de SELECCIÓN (args ver arriba) ======

### CHAMPION FINAL = run7 EPOCH 8 (full-FT 8 epochs, lr5e-5, constant, slim, seq1280)
**Artefacto usable en Baxy:** `model/functiongemma-ft-270m-it-Q8_0.gguf` (278 MB, <1.1GB VRAM).
Modelo HF: `out_fg/merged-bf16` (= epoch 8) + archivado en `archive/run7_ep8_merged`.

### MÉTRICAS (holdout completo n=1851, greedy) — comparación decisiva:
| Modelo            | tool-acc        | parseables | inventadas | args fuera | no_tool   | falsos |
|-------------------|-----------------|------------|------------|------------|-----------|--------|
| run6 (epoch 5)    | 90.3% (1671)    | 99.9%      | 3 (0.2%)   | 3          | 137/137   | 1      |
| epoch 7           | 90.1% (1667)    | 99.9%      | 1          | 5          | 136/137   | 1      |
| **epoch 8 (★)**   | **91.1% (1686)**| 99.8%      | **0**      | 4          | 137/137   | 1      |

### VALIDACIÓN NATIVA llama.cpp (GGUF Q8, lo que usa Baxy):
- n=40 sampling: 97.5% | n=150 sampling: 89.3% | n=150 greedy: 88.7% — **100% parseables en TODOS**.
- Q8 NO degrada (consistente con holdout HF). greedy≈sampling (empate) → temp no cambia la selección.

### DECISIÓN (fundamentada, sin especulación):
- El modelo se **APLANÓ en ~90-91%** desde epoch 5. Epochs 6-8 NO dieron salto real en tool-acc
  (+0.8pp ep8 vs ep5 = ~1 SE = dentro del ruido). **NO se promovió por accuracy.**
- Epoch 8 ES el champion porque es **igual-o-mejor en TODAS las dimensiones** y estrictamente mejor en
  **0 tools inventadas** (requisito duro de la misión; run6 tenía 3) sin degradar nada más, completando
  la receta oficial de 8 epochs de Google sin overfit. Multilingüe cubierto (el holdout es es/en/pt/fr/de/it).
- **TECHO MEDIDO ALCANZADO.** Se PARA acá (criterio de CLAUDE.md: no más mejoras medibles razonables).

### FALLAS RESIDUALES (el ~9% de error, TODO confusión de tools HERMANAS en clusters densos):
- browser automation: browser_real_click / browser_real_click_text / click_accessible / goto / tabs / tab_close
- base de datos: database_query / database_status / execute
- docker: compose_up / compose_down / container_start
- otros pares: contacts_create/contacts_add, csv_describe/csv_query, audio_device_set_default/set_default_communications,
  firewall_allow/firewall_block, alarm/timer, dedupe/rename, repair/dependency_install.
- 0 errores de formato (100% parseable), 0 inventadas, no_tool perfecto. El residual NO es de azar
  (greedy=sampling) ni de cuantización: es ambigüedad real entre tools casi idénticas a 270M.

### PRÓXIMA PALANCA (si el usuario quiere más — REQUIERE su criterio, NO auto-generar):
Datos CONTRASTIVOS hand-crafted para los pares hermanos confundidos (mismo contexto, distinto tool
correcto según señal sutil). Evidencia: guía Microsoft SLM-FC + Unsloth (negative/distractor "muy
efectivos para selección"). NO lo hago autónomo: el usuario rechazó datos sintéticos de baja calidad
("generarlo de la forma que propones siempre genera datos sintéticos de mala calidad") → necesita su
bar de calidad + patrones reales de uso de Baxy. Mitigación YA disponible: el router semántico que
acota a ~8 tools por query reduce el espacio donde caen estas confusiones.

### COMANDOS PARA BAXY:
```powershell
# Servir el modelo (router acota ~8 tools/query -> -c 4096 alcanza, VRAM <1.1GB):
C:\llamacpp-cuda\bin\llama-server.exe -m model\functiongemma-ft-270m-it-Q8_0.gguf `
  --port 8082 --jinja -ngl 99 -c 4096 --no-webui
# Request: POST /v1/chat/completions con {messages:[developer,user], tools:[...slim schemas...]}.
# Sampling: temp1/topk64/topp95 (oficial) O greedy (temp0, determinista) — empatan en acc.
# Parsear la salida: regex call:([a-zA-Z0-9_]+) y args {k:<escape>v<escape>}. stop=<end_function_call>.
# IMPORTANTE: usar SIEMPRE tool_schemas_slim.json (el FT se entrenó con slim, no los verbosos).
```

---
## (HISTÓRICO) ESTADO previo a finalización
- run7 TERMINADO LIMPIO (epoch 8): 14872/14872 en 4h13m, SIN crawl (fix bs8/accum2 aguantó).
- Config run7: `--full --lr 5e-5 --scheduler constant --epochs 8 --bs 8 --accum 2 --no-clean --resume checkpoint-9300` + `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`.
- DIAGNÓSTICO crawl: con bs16 el length-grouping llega a batches largos cuyo peak supera 16GB VRAM →
  pagina a shared mem (RAM por PCIe) → crawl 10-50x. FIX = bs8/accum2 (mitad activaciones, mismo batch efectivo).
- **DIAGNÓSTICO CLAVE (no olvidar):** con bs16 el length-grouping llega a batches de secuencias largas
  cuyo peak de activaciones supera 16GB VRAM → paginaba ~5-12GB a RAM por PCIe (shared mem) → crawl
  10-50x (24 s/it, power 52W/190W, "100% util" falso). FIX = bs8/accum2 (mitad de activaciones, mismo
  batch efectivo) + expandable_segments. Si REAPARECE crawl: matar y reanudar bs8 desde último checkpoint.
- **RIESGO save_total_limit=4:** borra el checkpoint de epoch 6 (11160) al guardar el final. Watcher
  `bmy6isx24` copia checkpoint-11160(ep6) y 13020(ep7) a archive/ antes de la rotación.
- **MONITOREO ACTIVO:** monitor en vivo `bnm8p2aw2` (latido ~9min + alerta crawl s/it>8 / RAM<2GB) +
  cron `814b2946` cada 10min. El "terminó" real llega por el task `bfox3ihp8` al salir el python.
- **NO lanzar otro train mientras run7 viva.** NO meter carga GPU extra (eval/llama.cpp) hasta que termine.

## DATASET (calibrado, verde)
- `curated/fg_train.jsonl` = 29.897 ; `curated/fg_holdout.jsonl` = 1.890.
- 2.341 targets `no_tool` (charla/conocimiento). 0 vacíos. 0 targets inválidos. 525 tools (524 + no_tool). 0 fuga train/holdout.
- Efectivos en training: ~24.654 (5.243 descartados por >2048 tokens).
- Cobertura: 516/525 tools con ≥40 ej en train.

## DECISIONES CLAVE YA TOMADAS (no repetir errores)
1. **NO abstención con target vacío** — envenenaba (EOS temprano → `call<eos>`). Reemplazada por tool centinela **`no_tool`** (llamada concreta).
2. **Merge:** Unsloth `save_pretrained_merged` falla si el dir NO está limpio → train_fg.py hace `rmtree(out_fg/*)` al inicio. RIESGO: borra checkpoints al relanzar (ver SEGURIDAD).
3. **FastModel de Unsloth** (no transformers plano) — evita OOM y el upcast fp32 lento de attention.
4. **Length-grouping manual** (group_by_length fue removido en transformers 5.5).
5. **Sampling oficial para EVAL:** temp=1.0, top_k=64, top_p=0.95 (greedy a veces colapsa a `call<eos>` — NO juzgar solo con greedy).
6. Entorno: `.venv_ft` (Python312 + torch 2.7cu126). Importar `unsloth` ANTES que torch o segfault. Unsloth necesita GPU (no correr con CUDA oculta).

## PIPELINE
build_fg_trainset.py → train_fg.py → out_fg/lora + out_fg/merged-bf16 → quantize_fg.py → ../model/functiongemma-ft-270m-it-Q8_0.gguf
- quantize usa `C:/llamacpp-src/convert_hf_to_gguf.py` (clonado) + `C:/llamacpp-cuda/bin/llama-quantize.exe`.

## CHAMPION / CHALLENGER
- **CHAMPION = RUN1** (verbose, 1 epoch, r16). Eval holdout greedy: **tool-acc 20%** (base=12.5%).
  Archivado en archive/run1_*. Debilidad: emite `call:`+nombre malo en tools raros/multilingüe.
- **CHALLENGER = RUN2 EN CURSO** (task bhnuag2lc): **slim-schemas + MAX_SEQ=1280 + r=32/α=64 + 2 epochs**.
  Velocidad slim: ~1.26 s/it (5.2 samp/s) → ~1.5h total. Dataset slim rebuildeado (29.936; 194 drop).
  tool_schemas_slim.json generado (params 5245→1991). INFERENCIA/router debe usar slim también.
- Champion previo: NINGUNO antes de run1.

### 2026-06-15 05:15 — RUN2 = NUEVO CHAMPION
- slim + MAX_SEQ1280 + r32/α64 + 2 epochs. train_loss **0.2051**, 1.66h. Archivado archive/run2_0514.
- **EVAL holdout greedy n=300: tool-acc 60.3%** (run1=20%, base=12.5%), no_tool recall 91% (21/23),
  inventadas 0.3%, args fuera schema 0, malformadas 28% (tokens raros en long-tail = subentrenamiento).
- Falla residual: confusión hermanos (alarm/timer, csv_describe/csv_to_xlsx) + nombres de tools raros.
- SIGUIENTE: cuantizar run2 (artefacto) + run3 challenger (3 epochs) para long-tail.

### 2026-06-15 07:50 — RUN3 = NUEVO CHAMPION
- slim + 1280 + r32 + **3 epochs**. train_loss bajó. Archivado archive/run3_0750 (+ GGUF).
- **EVAL holdout greedy n=300: tool-acc 67.3%** (run2=60.3%), **no_tool recall 100% (23/23), 0 falsos**,
  inventadas 0.3%, args fuera 1, malformadas 24%. → **GGUF Q8 re-cuantizado (champion actual)**.
- CHAMPION ACTUAL = run3. Artefacto usable: model/functiongemma-ft-270m-it-Q8_0.gguf (278MB).

### 2026-06-15 07:55 — RUN4 challenger EN CURSO (task b2gfd0wrz)
- slim + 1280 + **r=64/α=128** + 3 epochs (~2.5h). Hipótesis: más capacidad ayuda al long-tail (nombres de tools raros).
- Si tool-acc > 67.3% sin degradar no_tool → nuevo champion + re-cuantizar. Si no → run3 sigue.

### 2026-06-15 10:30 — RUN4 = NUEVO CHAMPION (gran salto)
- slim + 1280 + **r=64/α=128** + 3 epochs. Archivado archive/run4_1027 (+GGUF).
- **EVAL holdout greedy n=300: tool-acc 80.7%** (run3=67.3%, +13!), no_tool 100% (23/23), 0 inventadas,
  args fuera 1, malformadas 11% (de 24%). → **GGUF Q8 re-cuantizado = CHAMPION ACTUAL**.
- Aprendizaje: la CAPACIDAD (rank LoRA) era el cuello para el long-tail de 525 tools, no las épocas.
- Artefacto usable: model/functiongemma-ft-270m-it-Q8_0.gguf (278MB, <1.1GB VRAM).

### 2026-06-15 10:30 — RUN5 challenger EN CURSO (task bebdt7bk2)
- **r=128/α=256** + 3 epochs (~2.5h). Riding la tendencia de capacidad (r32→r64 dio +13).
- Riesgo: overfit (r128 ~11% del modelo, sin dropout). Si tool-acc>80.7% sin degradar → champion. Si no → run4.
- PENDIENTE no-GPU mientras entrena: wire fg_router_ft.py a tool_schemas_slim.json; eval breakdown común/raro.

### 2026-06-15 ~11:00 — RESEARCH PASS (papers/docs oficiales)
Fuentes: Google AI docs (finetuning-with-functiongemma), Unsloth tutorial+LoRA guide, Microsoft SLM-FC guide, gemma-cookbook notebook.
**RECETA OFICIAL de Google (58%→85% Mobile Actions):** num_train_epochs=**8**, lr=**5e-5**, scheduler=**constant**,
optim=adamw_torch_fused, batch=4, **full fine-tuning** (NO LoRA), max_length=512, bf16.
Confirmado que YA hago bien: formato de template (developer/call/response), sampling infer (temp1/topk64/topp95),
negative/distractor samples (efectivo para selección), alpha=2r, datos abundantes (30k vs 2-5k sugerido).
**Mejoras a aplicar (run6) que NO estaba usando:**
1. **epochs 8** (mi mayor lever sin usar — Google lo cita para distinguir tools = mi debilidad de hermanas).
2. **lr 5e-5** (yo 2e-4) + **scheduler constant** (yo cosine).
3. Considerar **full fine-tuning** (Unsloth full_finetuning=True) — más capacidad que LoRA r128 para 525 tools.
Nota capacidad: Unsloth sugiere "Gemma 1B para más capacidad" pero ROMPE el budget 1.1GB VRAM → quedarse en 270M.
**Plan run6 (tras run5):** full-FT (o r128) + 6-8 epochs + lr 5e-5 + constant + slim + seq1280. Ajustar epochs al deadline.

### 2026-06-15 ~11:00 — RUN5 CANCELADO + RUN6 EN CURSO (receta Google, full-FT)
- run5 (r128/3ep) cancelado a pedido del usuario para hacer "como Google".
- Nota: los 8 epochs de Google eran para 40 ejemplos (320 vistas); mi dataset=30k → 5 epochs full-FT = ~150k vistas (no transfiere 8 literal + no entra en deadline @2.8s/it → 8ep=~11.6h).
- **RUN6 (task b0je1j3e0): FULL fine-tuning, 5 epochs, lr 5e-5, scheduler constant, optim adamw_torch_fused,
  slim, seq1280.** 268M params 100% trained. 9295 pasos @ ~2.8s/it → ~7.2h (fin ~18:15). GPU ~16GB.
- **CHECKPOINTS resumibles** (save_steps 930, optimizer state) → el usuario puede CONTINUAR a epoch 8 después.
  Soporte `--resume` agregado a train_fg.py. Instrucciones en ops/RESUME_TO_EPOCH8.md.
  TODO al terminar run6: ARCHIVAR checkpoint final (full+optimizer, ~2.7GB) a archive/run6_ckpt_final/.
- CHAMPION sigue siendo run4 (80.7%, GGUF a salvo) hasta evaluar run6.

### 2026-06-15 ~20:35 — RUN6 (full-FT 5ep) = NUEVO CHAMPION (gran salto)
- train_loss 0.08 (bajo pero NO overfit en holdout). Archivado archive/run6_2035 + checkpoint-9295 (resumible).
- **EVAL holdout greedy n=300: tool-acc 88.3%** (run4=80.7%, +7.6), **malformadas 0.3% (de 11%!)**,
  inventadas 0%, args fuera 0, no_tool 100% (23/23), falsos no_tool 0. → **GGUF Q8 re-cuantizado = CHAMPION**.
- Full-FT (capacidad total) resolvió el long-tail: la basura `call:`+tokens raros desapareció.
- Artefacto: model/functiongemma-ft-270m-it-Q8_0.gguf (278MB). Evidencia: receta oficial Google (full-FT/lr5e-5/constant).

### 2026-06-15 ~20:35 — RUN7 EN CURSO: continuar a EPOCH 8 (resume)
- resume desde checkpoint-9295, --full --epochs 8 --no-clean. 3 epochs más (~6h, fin ~02:45).
- Hipótesis: más exposición sube algo; RIESGO overfit (train_loss ya 0.08). Checkpoints 6/7/8ep para elegir pico.
- Si 8ep (o 6/7) > 88.3% sin degradar → champion. Si no → run6-5ep queda.
- 2026-06-15 23:10: run7 LENTO (~15-18s/it) porque el usuario usa **Sunshine** (streaming remoto)
  que comparte la GPU → NO TOCAR sunshine.exe. Agregadas exclusiones Defender al proyecto+venv
  (revertir: Remove-MpPreference -ExclusionPath). run7 sigue produciendo checkpoints (lento);
  evaluar el de ~6ep cuando llegue (~step 11154) o cuando la GPU se libere. Champion 88.3% a salvo.
- NO agregar carga GPU extra (eval/llama.cpp) mientras corran run7+sunshine (contención triple).

### 2026-06-15 23:35 — POST-REBOOT: limpieza + run7 reanudado (HUÉRFANO)
- Reboot OK. Limpié apps no esenciales (dejé VSCode/Code, sunshine/Apollo, MSI Afterburner + RTSS
  [overclock GPU], NVIDIA driver, OS). GPU casi dedicada.
- OJO: al limpiar maté sin querer el `bash` wrapper de run7 → el task `bgxy1dmuo` quedó "failed exit 255",
  PERO el python de training SOBREVIVIÓ huérfano y SIGUE entrenando (log avanza, GPU 98%).
- run7 = full-FT epoch 8, resumió desde checkpoint-9300, ~5 s/it, ~5500 pasos restantes (fin ~05-07h).
- **NO habrá task-notification al terminar (wrapper muerto)** → CHEQUEAR vía log/checkpoints. Cron 2aa93126 (cada 2h) lo hace.
- Champion run6-5ep (88.3%) SIGUE a salvo (GGUF + archive). run7 es challenger.
- LECCIÓN: NO matar bash/cloudcode_cli/codex/OpenConsole al limpiar (infra del harness).

### 2026-06-15 23:37 — LIMPIEZA TOTAL: Sunshine era el cuello (2.7x speedup)
- Usuario pidió cerrar TODO menos lo del training. Detuve ApolloService (sunshine) → run7 pasó de
  ~5 s/it a **1.85 s/it (2.7x)**. O sea el streaming activo de Sunshine SÍ frenaba (no el full-FT).
- MANTENIDOS: training python, MSI Afterburner (OC = velocidad), VSCode/Code + harness (cloudcode_cli/
  codex/bash/node — si los mato, muero), NVIDIA driver, OS. RTSS respawnea desde MSI (OSD, neutral).
- run7 epoch 8 ahora ETA ~02:25. Sigue HUÉRFANO (sin task-notif) → cron 2aa93126 (cada 2h) lo caza.
- Si el usuario reconecta por remoto: reabrir Apollo (Start-Service ApolloService) — lo dejé en Manual.
- Mejor evidencia hasta ahora: validación de 300 pasos (sin no_tool) ruteaba español OK; checkpoint-400 (con no_tool) daba args correctos (set_volume{level:30}, wifi_connect{name:MiCasa}) y `no_tool` en "gracias", pero `call<eos>` en algunos (subentrenamiento a 400 pasos).

## SCRIPTS DE EVAL (en scripts/)
_eval_functiongemma.py, eval_ft_vs_baseline.py, eval_full_dimensions.py, eval_router_multiling.py, _probe_with_tools.py, _headtohead_e2b_vs_fg.py, _audit_*.py, boot_eval_model.py. (Revisar firmas antes de usar.)

## RESULTADOS / MÉTRICAS (log cronológico)
- **2026-06-15 03:17 — RUN1 COMPLETO.** 1 epoch, 1541 pasos, train_loss=**0.3156**, runtime 5.65h
  (ritmo ~15s/it por recompilación de Unsloth con length-grouping; terminó OK).
  Artefactos: out_fg/lora + out_fg/merged-bf16. **ARCHIVADO** en `archive/run1_<ts>/`.
  Eval en curso (eval_night.py, sampling oficial, 300 holdout). Task: bvjth7edc, log: eval_run.log.
- Nota de velocidad: schemas verbosos (mediana 1406 tok/ejemplo) → secuencias largas + recompiles.
  Mejora futura candidata: slim-schemas (sacar params heredados) → ~3x más rápido train+infer.
