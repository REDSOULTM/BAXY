# HANDOFF DE INTEGRACIÓN — FunctionGemma run9 → Baxy (repo principal)
**Fecha:** 2026-06-17 · **Para:** el agente de Baxy que integra el router de tool-calling.
**Resumen en 1 línea:** nuevo FunctionGemma-270M (run9) con extracción de argumentos ARREGLADA en 6 idiomas,
cobertura discord/slack/teams, y fix de router `no_tool`. Drop-in: mismo formato de I/O que la versión anterior.

---

## 1) EL ARTEFACTO (lo único imprescindible para correr)
- **GGUF:** `model/functiongemma-ft-270m-it-Q8_0.gguf` (278 MB, Q8_0, <1.1 GB VRAM). md5 `b4ac42db86c75eeddff559515039bdac`.
- **Schemas:** `tool_schemas_slim.json` (525 tools, "slim"). **El runtime DEBE usar ESTE**, NO los verbose —
  el FT se entrenó con slim; usar otros = mismatch = basura. (Generado por `build_slim_schemas.py` desde `tool_schemas_full.json`.)
- Modelo HF (por si hay que recuantizar): `finetune_llm/archive/run9_ep5_merged/` (bf16 safetensors).
- Backups de versiones previas: `model/functiongemma-CHAMPION-run7ep8-Q8_0.gguf` (champion anterior), `run8ep5`, `run8ep8`.

## 2) CONTRATO DE RUNTIME (debe coincidir con el training — NO cambiar)
- **Server:** `C:\llamacpp-cuda\bin\llama-server.exe -m model/functiongemma-ft-270m-it-Q8_0.gguf --port 8082 --jinja -ngl 99 -c 4096 --no-webui`
- **⚡ LATENCIA — USAR `127.0.0.1`, NO `localhost`:** el server escucha en IPv4 `127.0.0.1`. Si el cliente pega a
  `http://localhost:8082` en Windows, intenta IPv6 (`::1`) primero, espera ~2s el timeout y recién cae a IPv4 →
  **2080 ms/request**. Con `http://127.0.0.1:8082` → **59 ms/request (~35x más rápido)**. MEDIDO (fg_bench.py): el modelo
  computa en ~36 ms; los 2 s eran 100% el timeout de resolución. **Baxy DEBE apuntar el cliente a 127.0.0.1.** (Doc: BSWEN
  llama.cpp optimization 2026; gotcha clásico Windows localhost/IPv6.) Flash-attention ya se auto-activa; -ngl 99 OK.
- **Request:** `POST /v1/chat/completions` con `messages:[{role:"developer", content:"You are a model that can do function calling with the following functions"}, {role:"user", content:<query>}]` + `tools:[...slim schemas del subset...]`.
- **Sampling:** greedy (temp 0) O oficial temp1/topk64/topp95 — empatan en accuracy. `stop:["<end_function_call>"]`, `max_tokens:~160`.
- **Salida + parseo:** `<start_function_call>call:NOMBRE{k:<escape>v<escape>,...}<end_function_call>`.
  Regex: nombre `call:([A-Za-z0-9_]+)`, args `([A-Za-z0-9_]+):<escape>(.*?)<escape>` (usar **re.DOTALL/re.S** — hay
  valores multilínea como vCard/ICS). Tool centinela `no_tool` = derivar al LLM conversacional (no es una tool real).

## 3) FIX DE ROUTER (resuelto — portar al router de Baxy)
El router semántico que acota 524→~10 tools **DEBE incluir `no_tool` SIEMPRE** en el subset que manda al modelo.
Si no, el chitchat/no-accionable fuerza una tool equivocada (el "eager invocation" de SLMs; ver SimpleToolHalluBench
arXiv 2510.22977, When2Call arXiv 2504.18851). Referencia ya implementada en `fg_router_ft.py::FTRouter.route()`:
```python
if "no_tool" in self.idx and not any(n == "no_tool" for n, _ in ranked):
    ranked.append(("no_tool", 0.0))
```
Además `fg_router_ft.py` ahora consulta el **GGUF run9 (llama-server :8082)**, NO el Ollama fp16 viejo — usar esa
versión como referencia de integración. (El encoder/router en sí no cambió: MiniLM-L12 FT de Baxy.)
**Abstención MEDIDA en run9** (`fg_probe_notool.py`, subsets tentadores, 6 idiomas): **13/14 = 93% elige `no_tool`**
correctamente (el único miss es borderline: "qué opinás del clima" → tool de clima). Ya no hace falta umbral de
confianza ni short-circuit (respetando "el LLM decide" del CLAUDE.md de Baxy); la abstención sale del modelo + el
no_tool inyectado. Si en el futuro se quiere endurecer: usar el `confident_peak_threshold`/`abstain_head` que Baxy ya tiene.

## 4) CAMBIOS DE COMPORTAMIENTO QUE EL EXECUTOR DEBE CONOCER
- **Mensajería por app NO-WhatsApp (Discord/Slack/Teams)** → el modelo emite `computer_use{goal:<query tal cual>}`
  (NO `send_message`, que es WhatsApp). El planner de computer_use ya descompone focus_app/open_chat/type. Verificado en vivo.
- **Args canónicos** que ahora emite el modelo (todos ya aceptados por tus handlers, que son tolerantes a sinónimos —
  ver `baxy_alias_map.json`): `set_volume{level:int}`, `send_message{contact,text}`, `app_open{name}`,
  `browser_open{query|url}`, `memory_save{value}`, `web_search{query}`, `alarm_create{time}` vs `timer_start{minutes}`.
- **`no_tool`** en chitchat/saludo/conocimiento/agradecimiento (abstención) — el orquestador lo interpreta como "responde el LLM".

## 5) VALIDAR DESPUÉS DE INTEGRAR (scripts en este repo)
Levantar el server (§2) y correr:
- `python fg_probe_multiling.py`  → debe dar **OK×6** en set_volume/send_message/app_open/browser_open/web_search/memory_save/play/set_brightness.
- `python fg_probe_broad.py`      → 0 omisiones de args en 18 tools paramétricas.
- `python fg_e2e_test.py`         → pipeline REAL (router→GGUF→handlers). Casos clave: "subi el volumen a 40"→set_volume{level:40},
  "conectate a MoviStar_2.4G"→wifi_connect{name}, "gracias..."→no_tool, multilingüe.
- `python fg_argeval.py 500`      → arg-aware holdout (tool-name ~87%, args-vacíos ~1.6%).

## 6) RESIDUAL CONOCIDO (para otro día — NO bloqueante)
Confusión entre tools HERMANAS casi idénticas (el long-tail del 270M): `filesystem_search`↔`filesystem_list`,
`dependency_install`↔`package_install`, `alarm_create`↔`timer_start` (1 idioma). Los **args se extraen bien**; solo el
ruteo cae a la hermana. Mitigado por el router semántico (acota el espacio). Palanca futura: datos contrastivos
hand-crafted para esos pares (mismo contexto, señal sutil que los distingue).

## 7) CÓMO SE REPRODUCE (provenance, todo versionado)
- Dataset: `finetune_llm/build_fg_trainset.py` (SLIM_SCHEMAS=1, PYTHONHASHSEED=0 para reproducibilidad) →
  `curated/fg_train.iter3.jsonl` (28485) + `fg_holdout.iter3.jsonl`. Validado por `validate_dataset.py` (0 inventadas, 0 args
  fuera de schema, 0 fuga, 0 dups, no_tool 8%, 525/525 cobertura).
- Fix de datos: `VALUE_REQUIRED={set_volume,send_message,app_open,browser_open,memory_save,web_search}` en build_fg_trainset.py
  (drop estructural por-tool de calls arg-less contaminadas) + handcrafted multiling `curated/hc/batch_fix_argless*.jsonl`,
  `batch_discord_cu.jsonl`, `batch_alarm_timer.jsonl`.
- Training: `train_fg.py --full --lr 5e-5 --scheduler constant --epochs 5 --bs 8 --accum 2` (receta oficial Google, full-FT).
  Quantize: `quantize_fg.py` (LLAMACPP_DIR=C:\llamacpp-src). train_loss 0.080 (sano, sin overfit).
- Detalle completo y trayectoria: `finetune_llm/ops/NIGHT_RUN_STATE.md` (sección 🏆 VEREDICTO FINAL).

## 8) GIT (este repo FunctionGemma NO está bajo git todavía)
Si se versiona para sincronizar con Baxy: incluir `model/functiongemma-ft-270m-it-Q8_0.gguf`, `tool_schemas_slim.json`,
`tool_categories.json`, `tool_action_map.json`, los scripts `fg_*.py`, `finetune_llm/` (build/train/quantize/eval + curated/),
y este HANDOFF. (El GGUF es grande → considerar Git LFS o release asset.) Recordá: los dos remotos de Baxy (origin + asistia)
deben quedar idénticos (ver CLAUDE.md de Baxy).
