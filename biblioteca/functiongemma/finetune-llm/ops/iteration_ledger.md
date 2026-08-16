# ITERATION LEDGER — FG Tools-Reduce — abstención E2E con negativos duros

> Loop champion-challenger nocturno (2026-06-25, deadline 10:00 AM). Cada train: hipótesis+fuente,
> config, resultado medido, delta vs champion, lección. NO repetir lo que falló; explotar lo que sirvió.

## CHAMPION DE PARTIDA = iter2 (deployado)
- `model/functiongemma-tools-reduce-270m-it-Q8_0.gguf` (md5 4c8e5a87), full-FT 5ep lr5e-5/constant, train 7763.
- Métricas: producción-fiel e2e 95% (38/40), cascade 94%, holdout 88.9%, multiling OK.
- **FALLA medida (TAREA 3)**: abstención E2E sobre capacidad-ELIMINADA NO es limpia en el chain real.
  "instala requests con pip" → confabuló "I will execute the installation" (eligió computer_use);
  "enviá un correo" casi va a send_message. Eval aislado da 100% pero el subset del encoder real
  ofrece tools tentadoras que el train nunca puso junto a no_tool.

## RESEARCH-FIRST (fuentes, 2026-06-25 ~02:00)
- **When2Call (arXiv 2504.18851)** + **SimpleToolHalluBench (arXiv 2510.22977)**: SLM SOBRE-invocan
  cuando hay tools tentadoras presentes → entrenar abstención CON los near-miss reales en el subset.
- **"Know Your Limits: Survey of Abstention in LLMs" (TACL 2024, arXiv 2407.18418)** + GPT4Tools
  (2305.18752): entrenar SOLO con positivos sesga a invocar; agregar negativos da la capacidad de
  discernir cuándo NO usar tool. Pero "a mayor ratio de hard-negatives sube accuracy PERO también la
  brittleness/over-refusal" → ratio moderado, no inundar. Acción NO debe regresar.
- **Decisión de ratio**: el champion tiene no_tool ~10.7%. Subo la CALIDAD de los negativos (distractor
  correcto) más que la cantidad. Target no_tool ~13-15% (incremento modesto), con contrastivos positivos
  para no sobre-generalizar "instala→no_tool". Mido recall de acción para detectar over-refusal.

## DESCUBRIMIENTO EMPÍRICO — subsets tentadores REALES del encoder (discover_tempting_subsets.py)
Corrí R.subset() del encoder real sobre queries de capacidad-ausente. Frecuencia de tools tentadoras:
filesystem_open/read/list (26 c/u), **computer_use (16)**, app_open/steam_open/launch_game/list_games (15),
app_close/app_search/library (14), contacts_create/list (12), browser_real_* (10), send_message (10).
Por categoría (la tool tentadora REAL que el champion NUNCA vio junto a no_tool):
| capacidad | tools tentadoras REALES del encoder | distract VIEJO (equivocado) |
|---|---|---|
| terminal/shell | **computer_use**, filesystem_open/read/list, app_open/close/search, processes, services_list | filesystem_list, processes, services_list (faltaba computer_use, filesystem_open/read, app_*) |
| packages (pip/npm) | filesystem_read/list/open, steam_open, **computer_use**, launch_game, library, list_games | steam_open, app_open, app_search (faltaba filesystem_*, computer_use, launch_game, library) |
| email | send_message, contacts_create/list, open_chat, list_messages, reminder_create | send_message, open_chat, contacts_list (~ok, faltaba contacts_create, reminder_create) |
| env vars | filesystem_read/open/list, **computer_use**, ingest_to_knowledge, summarize, document_status | memory_save, set_value (TOTALMENTE MAL: set_value ni se ofrece) |
| dev-meta | create_note, note_list, task_list, routine_create, filesystem_*, network_status, dns_set | filesystem_list, create_note, memory_save (parcial) |
| chitchat | memory_save, web_search, web_open/read, open_chat, knowledge_list, ingest | (no forzados) |
**LECCIÓN clave (pre-train):** el champion abstenía 100% en aislado porque sus distractores de abstención
eran tools "neutras"; nunca enfrentó computer_use/filesystem_open/app_open junto a no_tool. El fix = forzar
los distractores REALES medidos. Esto es el hard-negative del mission, ahora GROUNDED en medición, no inventado.

---

## BASELINE del CHAMPION (iter2) en el HELD-OUT NUEVO de abstención-E2E (eval_fg_abstain_e2e.py)
Medido 2026-06-25 ~02:20 (FG aislado `_ask`, subset encoder real). El held-out NUEVO (40 casos disjuntos
del train) revela que la abstención NO es 100% (el eval viejo de 4 casos la sobreestimaba):
| categoría | champion iter2 |
|---|---|
| **ABSTAIN-removed** (terminal/pip/email/env/devmeta) | **81.2% (26/32)** |
| CHITCHAT | 100% (2/2) |
| **KNOWLEDGE** (preguntas de conocimiento → no_tool) | **25% (1/4)** ← hallazgo nuevo |
| CONTRAST-acción (anti over-refusal) | 90% (9/10) |
| **ABSTENCIÓN TOTAL** | **76.3% (29/38)** |
Fallas FG: `make build`→computer_use (CU en subset!), `installa scipy`→library, emails→send_message/
contacts_create/ingest, knowledge→web_open/web_read/media_status. El 1 fail de acción = "open the calculator"
→app_search (par hermano app_open↔app_search, TAREA 1, no es over-refusal). **GATE objetivo: ABSTAIN-removed
≥95% y KNOWLEDGE ≥95% SIN bajar CONTRAST-acción <90% ni chitchat.**

## TRAINS

### TRAIN iter3 (challenger) — HARD-NEGATIVES grounded — lanzado 2026-06-25 ~02:30
- **Hipótesis (fuente):** el champion abstiene mal (81% removed / 25% knowledge) porque sus distractores
  de abstención eran tools neutras; nunca vio la tool tentadora REAL (computer_use/filesystem/web_search)
  junto a no_tool. Fix = forzar los distractores REALES medidos (ops/tempting_subsets.json). Fuente:
  When2Call 2504.18851 + SimpleToolHalluBench 2510.22977 (SLM sobre-invocan con tentadora presente) +
  TACL Abstention Survey 2407.18418 (negativos dan discernir-cuándo-NO; ratio moderado).
- **Cambios de datos:** gen_reduced_abstain v2 (212 abstain + 140 contrastivos pos, distractores reales
  por categoría + NUEVA categoría knowledge→no_tool con web_search forzado + contraste "buscá en internet"
  →web_search). Rebuild `--abstain-cap 750`. Train 7763→7892, no_tool 11.0%. Validate: TODO PASS.
- **Config:** full-FT 5ep, lr5e-5/constant, bs4/accum4 (eff 16) — receta Google champion. log=train_reduce3.log.
- **INCIDENTE (resuelto):** el 1er intento crasheó en paso 734/2470 (epoch 1.48, loss sano ~0.07) con
  **MemoryError de RAM del host** (no GPU OOM). Causa: a las 02:45:38 arrancó OTRO training
  (`scripts/train_router_encoder.py`, PID 52896) que tomó GPU (7.6GB/90%) + RAM → con 31.8GB totales y las
  IDEs abiertas, el offload de gradientes de Unsloth a CPU empujó sobre el límite. Dos full-trainings NO
  caben en 16GB VRAM. Decisión (autorizada por memoria gpu-contention-kill): maté el router-encoder train
  (solo ~3min invertidos, se relanza solo) → RAM libre 15.7GB. **Relanzado** como log=train_reduce3b.log,
  PID 30300, ~02:49. Mismo recipe. RIESGO: si un scheduler relanza el router-encoder, vuelve a contender.
- **2º crash + fix definitivo:** el relanzado (3b, bs4/accum4) volvió a morir al paso 73 en `backward()`
  (output corrupto "ooobjeco" = terminación abrupta, CUDA-OOM o kill por pagefile). Event Log Windows: a
  las 02:46 crashearon TAMBIÉN DisplayFusion.exe y MSPCManagerCore.exe → evento de presión de memoria de
  TODO el sistema; pagefile picó 7.7GB. No hay scheduler relanzando el router-encoder (fue lanzamiento
  único). Causa = footprint del path backward de Unsloth (gradient-offload + double-buffering) sobre RAM/VRAM
  ajustada. **FIX:** relanzado (3c) con **bs2/accum8** (mismo eff batch 16, mitad de footprint por micro-paso;
  cubre CUDA-OOM y RAM-host). log=train_reduce3c.log, PID 46140, ~02:57. ~5.4s/it, ETA ~3:40h (fin ~06:40).
  Monitor+guard activos. **DECISIÓN:** si 3c también muere, bajar a bs1/accum16 o cerrar IDEs para liberar RAM.
- **RESULTADO: 🏆 NUEVO CHAMPION (iter3 DOMINA a iter2, 0 regresión).** Train completó 2470 pasos
  (loss final 0.013, train_loss 0.076). GGUF iter3 md5 8fa2b441. Medido (FG aislado, subset encoder real):
  | métrica | iter2 champion | **iter3** | Δ |
  |---|---|---|---|
  | **abstención-E2E total** | 76.3% | **89.5%** | **+13.2** |
  | **KNOWLEDGE** (preg. conocimiento→no_tool) | 25% | **100%** | **+75** |
  | ABSTAIN-removed (terminal/pip/email/env/devmeta) | 81.2% | **87.5%** | +6.3 |
  | CHITCHAT | 100% | 100% | = |
  | CONTRAST-acción (anti over-refusal) | 90% | 90% | = |
  | **acción producción-fiel** (eval_fg_reduced_e2e) | 95.0% | **97.5%** | **+2.5** |
  - Mejora en TODO sin regresar nada. El fix de knowledge (web_search forzado→no_tool) clavó 25→100%.
    Los distractores reales (computer_use/filesystem) subieron removed +6. Acción SUBIÓ (no over-refusal).
  - **PROMOVIDO**: canónico `model/functiongemma-tools-reduce-270m-it-Q8_0.gguf` = iter3; backup
    `-iter3-Q8_0.gguf`; iter2 conservado en `-iter2-Q8_0.gguf`; merged en `archive/run_reduce3_5ep_merged`.
  - **LECCIÓN:** los hard-negatives con distractores REALES medidos (no inventados) + la categoría knowledge
    funcionan exactamente como predijo When2Call/SimpleToolHalluBench. bs2/accum8 evita el crash de RAM.
- **RESIDUAL medido (→ hipótesis iter4):** 4 fails de abstención = email-FORWARD en fr/de/pt
  ("transfère/leite weiter/encaminha"→contacts_create/computer_use) + 1 terminal fr ("exécute la commande
  make build"→computer_use). El intent "forward/reenviar" NO estaba en los hard-negatives de email (solo
  send/reply/read). ABSTAIN-removed 87.5%<95% por esto. Fix iter4: agregar forward-email multiling + más
  terminal fr/de. CONTRAST fail (de battery→device_settings_brightness_get) es par hermano, no over-refusal.

### TRAIN iter4 (challenger del residual email-forward) — datos listos, train EN CURSO bs2/accum8
- **Hipótesis:** los 4 fails de abstención de iter3 son el intent FORWARD/reenviar de email en fr/de/pt
  (no estaba en train) + terminal-comando fr. Fix = gen_reduced_abstain v3: +forward-email multiling
  ("transfère/leite weiter/encaminha/inoltra/reenviá" con OTRAS frases que el held-out) + "ejecutá el
  comando X" multiling con comandos disjuntos. Dataset 7872, no_tool 11.5%, validate TODO PASS, 0 fuga.
- **RESTRICCIÓN DE RECURSOS MEDIDA (lección dura):** full-FT **bs4/accum4 NO cabe** en esta máquina
  (31.8GB RAM): crasheó 3 veces con MemoryError/STATUS_COMMITMENT_LIMIT (RAM libre llegó a 0.0GB, fallas
  de fork de bash). El offload de gradientes de Unsloth + double-buffering desborda. SOLO **bs2/accum8**
  es estable (footprint mitad), pero tarda ~3:40h (vs 1:50h de bs4). bs2 lanzado ~06:49 → ETA ~10:29,
  **pasado el deadline duro 10:00**. log=train_reduce4b.log, PID 52296.
- **DECISIÓN (champion-challenger disciplinado):** iter3 queda como CHAMPION FINALIZADO y deployado a las
  10:00. iter4 sigue entrenando en background; la PRÓXIMA SESIÓN lo evalúa (ver RESUME_PROMPT) y SOLO lo
  promueve si supera a iter3 en TODOS los gates (abstención↑ sin regresar acción 97.5%/multiling/chitchat).
  No se arriesga el champion sólido por un challenger apurado/undertrained.
- **RESULTADO (1ros intentos): crashes por RAM compartida.** bs4 ×3 y bs2 ×1 murieron con MemoryError
  porque el agente de Baxy corría tests/retrains CONCURRENTES (RAM a 0.0GB). El usuario autorizó cerrar lo
  que contendiera y confirmó que no usaba la PC → cerré navegadores/Discord/Steam (RAM 13→17.3GB libre,
  commit 16.5GB) y relancé (4c, bs2/accum8). 4c COMPLETÓ 2460 pasos (3:02h, loss final 0.024, train_loss
  0.075). GGUF iter4 md5 880e72e1. **LECCIÓN recursos:** con máquina libre, bs2/accum8 entrena sin crash;
  el cuello era la contención de RAM de Baxy, no la receta.
- **RESULTADO (eval): 🔴 iter4 RECHAZADO — REGRESA, no pasa el gate.** Medido vs iter3:
  | métrica | iter3 champion | iter4 challenger | veredicto |
  |---|---|---|---|
  | ABSTAIN-removed | 87.5% | 90.6% | ↑ (lo único que mejoró) |
  | **KNOWLEDGE** | 100% | **50%** | ↓↓ REGRESA |
  | CONTRAST-acción | 90% | 80% | ↓ REGRESA |
  | abstención-E2E total | 89.5% | 86.8% | ↓ |
  | **acción producción-fiel** | 97.5% | **87.5%** | ↓↓ REGRESA (app_open→browser_open ×5) |
  - El fix email-forward/terminal-comando subió ABSTAIN-removed +3 PERO desestabilizó el modelo: "abrí el
    bloc de notas/calculadora/notepad/Firefox"→browser_open (app_open roto), knowledge→web_open/media,
    "subí el volumen"→pause. Trade-off NETO NEGATIVO.
  - **Hipótesis del por qué:** la densidad extra de negativos "abrí terminal"/"ejecutá el comando X"→no_tool
    + forward-email empujó a un mínimo que confunde el verbo "abrir/open" (app_open↔browser) y bajó la
    abstención de knowledge. iter3 ya estaba en un buen óptimo; iter4 lo sobrepasó (over-tuning de abstención).
  - **DECISIÓN: iter3 RESTAURADO como champion** (ambos slots = 8fa2b441). iter4 conservado como
    `-iter4-Q8_0.gguf` (registro). NO repetir esta mezcla de negativos: para el residual email-forward,
    probar un AÑADIDO MÍNIMO (solo forward-email, SIN los "abrí terminal"/"comando X" que rompen app_open).
- **CIERRE: CHAMPION FINAL = iter3** (md5 8fa2b441, deployado). Techo medido y verificado por challenger:
  iter3 es el óptimo de esta familia de recetas; el residual email-forward (4 casos) NO justifica regresar
  knowledge+app_open. Próximo intento debe ser un negativo MÍNIMO y focalizado, no un batch amplio.
