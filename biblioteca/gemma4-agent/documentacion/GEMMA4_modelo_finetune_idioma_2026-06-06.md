# Gemma 4 E2B — Fine-tuning, comportamiento e idioma (investigación + mediciones)

> **Fecha:** 2026-06-06
> **Origen:** sesión de re-fine-tuning multilingüe de Baxy. El usuario pidió
> dejar de fine-tunear "por intuición" e **investigar con fuentes oficiales**
> cómo se entrena este modelo específico (Gemma 4 es posterior al knowledge
> cutoff del agente → no estaba en sus datos). Este documento consolida TODO
> lo descubierto para no perderlo entre sesiones.
>
> **Cómo se obtuvo:** 2 investigaciones profundas (deep-research harness:
> fan-out de búsquedas web → fetch de fuentes → verificación adversarial 3
> votos por claim → síntesis citada) + mediciones en vivo contra el modelo y
> el agente reales (`run_content`, ejecución física mockeada).

---

## 0. Identidad exacta del modelo

- **`google/gemma-4-E2B-it`** (instruct).
- `config.json`: `model_type="gemma4"`, `architectures=["Gemma4ForConditionalGeneration"]`,
  `transformers_version="5.5.0.dev0"`, `eos_token_id=[1, 106]`, `bos_token_id=2`.
- `generation_config.json`: `eos_token_id=[1, 106, 50]` (token 50 sin identificar).
- Licencia **Apache 2.0**, Google DeepMind. Arquitectura **MatFormer** (E2B = ~2B
  parámetros activos). Multimodal (texto + visión + audio nativos).
- Despliegue en Baxy: **GGUF Q4_K_M ~3.43 GB**, servido por `llama-server`
  (perfil `vram4`, target 4 GB VRAM).

---

## 1. Investigación #1 — Cómo se fine-tunea Gemma 4 (VERIFICADA, fuentes oficiales)

**Método:** deep-research, 103 agentes, 19 claims confirmados con voto
adversarial. Fuentes: ai.google.dev/gemma/docs (model_card_4,
prompt-formatting-gemma4, function-calling-gemma4, thinking), HF
google/gemma-4-E2B-it, unsloth.ai/docs/models/gemma-4, Unsloth issues
#5386/#4820/#4921, PEFT #3129, llama.cpp PR#21390.

### 1.1 Chat template (NUEVO, ≠ Gemma 2/3) — `high confidence`
- Turno se **abre** con `<|turn>role\n` y se **cierra** con `<turn|>` (token id **106**).
- Roles: `system` / `user` / `model`. **El rol `system` es NUEVO en Gemma 4**
  (Gemma 3 no lo tenía nativo).
- Thinking: `<|think|>` al inicio del system prompt + pensamiento envuelto en
  `<|channel>thought\n...<channel|>`.
- Reemplaza el `<start_of_turn>`/`<end_of_turn>` de Gemma 2/3.
- Fuente: ai.google.dev/gemma/docs/core/prompt-formatting-gemma4 (verbatim).

### 1.2 EOS — `high confidence`
- **El turno del assistant termina con `<turn|>` (106), NO con `<eos>` (1).**
- `eos_token_id` es una **lista** `[1, 106]` (config) / `[1, 106, 50]` (generation):
  HF trata la lista como conjunto de stop tokens (cualquiera corta la generación).
- **Bug conocido #5386:** `save_pretrained_merged(merged_16bit)` de Unsloth
  REESCRIBE silenciosamente `eos_token` de `<turn|>` → `<eos>`, rompiendo el
  *stop* en modo tool-call (latencia 10-12×). **Fixed en PR #5451.**
- VERIFICADO en nuestro pipeline: nuestro merge (`merge_and_unload` de PEFT
  sobre el modelo recargado bf16) **NO dispara este bug** — el merged mantiene
  `eos=[1,106]`. Y verificamos que un ejemplo de entrenamiento termina en el
  token **106** (correcto).

### 1.3 Function-calling nativo — `high confidence`
- El modelo **emite** llamadas como
  `<|tool_call>call:NOMBRE{param:<|"|>valor<|"|>}<tool_call|>`.
- Resultados se devuelven como
  `<|tool_response>response:NOMBRE{clave:valor,...}<tool_response|>`.
- **El delimitador de strings es el token `<|"|>`** (NO comillas JSON). Claves
  bare, números sin envolver. `<|tool_response>` actúa como stop sequence.
- Fuente: ai.google.dev/gemma/docs/capabilities/text/function-calling-gemma4.

### 1.4 LoRA / capas custom — `high confidence`
- Gemma 4 tiene una capa custom **`Gemma4ClippableLinear`** que **PEFT crudo
  RECHAZA** (issue #3129: hereda `nn.Module` no `nn.Linear`).
- Unsloth la parchea en `unsloth_zoo/peft_utils.py::get_peft_regex` (detecta la
  capa y agrega `.linear`). **VERIFICADO presente** en unsloth 2026.5.10.
- `Gemma4ClippableLinear` vive en las **torres de visión/audio** → para un FT
  **text-only del E2B es irrelevante**: una lista explícita
  `[q_proj,k_proj,v_proj,o_proj,gate_proj,up_proj,down_proj]` funciona.
- Unsloth recomienda `target_modules="all-linear"` + flags
  `finetune_language_layers/finetune_attention_modules/finetune_mlp_modules`.

### 1.5 Bug KV-sharing (la causa REAL de corrupción en training) — `high confidence`
- E2B comparte KV entre capas: **`num_kv_shared_layers=20`**.
- Con `use_cache=False` (el default de training) las capas KV-shared recomputan
  K/V mal → **el loss explota y los logits salen basura.**
- Unsloth lo parchea (**Fix 2** en `unsloth_zoo/temporary_patches/gemma4.py`).
  **VERIFICADO presente y activo** en nuestro unsloth 2026.5.10.
- **Esto explica MEJOR las corrupciones de los rounds 1-3 de re-FT** que la
  hipótesis previa del "merge de Unsloth".

### 1.6 GGUF / cuantización — `high confidence`
- Requiere llama.cpp actual. Unsloth v0.1.36-beta trae 5 fixes para gemma4:
  `add_bos=True`, byte-token handling en el BPE detokenizer, parser gemma4,
  `final_logit_softcapping`, custom newline split (llama.cpp PR #21390).
- Paths: `save_pretrained_gguf(...)` (1 paso) **o**
  `save_pretrained_merged(merged_16bit)` → `convert_hf_to_gguf.py --outtype f16/bf16`.
- **GOTCHA propio MEDIDO (2026-06-06):** el `convert_hf_to_gguf.py` llama a
  `LlamaHfVocab` → `AutoTokenizer`. Gemma 4 guarda `extra_special_tokens` como
  **LISTA** (`['<|video|>']`); **transformers 4.57 (Python 3.10 del sistema)
  revienta** con `'list' object has no attribute 'keys'`. **transformers ≥5.5.0
  (venv FT, Python 3.12) lo carga bien.** → CORRER LA CUANTIZACIÓN CON EL PYTHON
  DEL VENV FT. (Confirmado empíricamente: 3.10 crashea, 3.12 OK vocab=262144.)

### 1.7 Hiperparámetros — `NO confirmado / refutado`
- Los valores candidatos (r=32, α=32, lr=2e-4, etc.) fueron **refutados (0-3)**
  por la verificación adversarial: NO hay recomendación oficial de Unsloth para
  hiperparámetros LoRA "anti-olvido-catastrófico multilingüe" del E2B.
- **Conclusión: los hiperparámetros se TUNEAN EMPÍRICAMENTE** contra un held-out
  diverso. Lo que usamos (r16/α32/lr2e-4/3ep) es razonable-por-convención, no
  oficial. El barrido de epochs (2/3/4) que hicimos es exactamente el método
  correcto: 3ep ganó por routing/precisión.

### 1.8 Versiones del entorno FT (PINEAR para reproducibilidad)
```
unsloth 2026.5.10 | unsloth_zoo 2026.5.5 | transformers 5.5.0
torch 2.7.0+cu126 | peft 0.19.1 | trl 0.24.0 | (venv .venv_ft, Python 3.12)
```
> Todo es Abr-Jun 2026 (release fast-moving). El comportamiento depende MUCHO de
> estas versiones. Pinearlas.

### 1.9 Correcciones a "intuiciones" previas (lección de método)
| Afirmación previa (como hecho) | Veredicto de la investigación |
|---|---|
| "Unsloth `save_pretrained_merged` corrompe Gemma 4 (gibberish)" | **NO confirmado.** El bug real (#5386) reescribe el EOS, rompe el *stop* — no produce gibberish. |
| "El idioma noES es irreducible / límite del 2B" | **FALSO.** El modelo responde en otros idiomas en charla y en smoke (5-6/7). El problema está en el runtime, no en el modelo. |
| Hiperparámetros r16/lr2e-4/3ep son "los correctos" | **Sin respaldo oficial.** Tunear empíricamente. |

---

## 2. El problema de idioma — diagnóstico medido

**Objetivo de producto (CLAUDE.md):** Baxy es multi-usuario, multi-idioma,
multi-acento. El reply debe espejar el idioma del usuario.

### 2.1 Lo que el modelo SÍ hace (smoke directo, modelo pelado bf16)
Con un prompt limpio, el modelo responde EN EL IDIOMA del usuario:
```
EN: "open notepad"          -> "Opening Notepad now."        ✅
FR: "ouvre le bloc-notes"   -> "J'ouvre le Bloc-notes."      ✅
DE: "öffne den editor"      -> "Ich öffne den Editor."       ✅
IT: "apri la calcolatrice"  -> "Ho aperto la calcolatrice."  ✅
ES: "contame un chiste"     -> "¿Qué hace una abeja...? ¡Zum-ba!" ✅
quién sos?                  -> "Soy Baxy, tu asistente..."   ✅ (identidad)
```
→ **El modelo (y el FT multilingüe) FUNCIONA.** 6/7 en su idioma.

### 2.2 Lo que el AGENTE hace (en vivo, con el runtime completo) — el bug
El reply **post-acción** sale en español sin importar el idioma de entrada:
```
EN: "close chrome"     -> "Listo, cerré Google Chrome."        ES! ❌
EN: "set volume to 30" -> "Listo, dejé el volumen en 30."      ES! ❌
EN: "take a screenshot"-> "Listo, saqué la captura."           ES! ❌
PT: "fecha o chrome"   -> "Listo, abrí Chrome."                ES! ❌
FR: "mets le volume"   -> "Listo, el volumen está al 30%."     ES! ❌
... LEAKS ES: 15/21 comandos de acción
```

### 2.3 Causa raíz — DOS fuentes de leak ES (ambas medidas)

**(A) Short-circuits con reply HARDCODEADO en español.**
Hay ~18 puntos en `agent_core/agent.py` que, tras ejecutar un tool, devuelven
un `AgentReply` con texto fijo español, **sin pasar por el LLM**:
```python
agent.py:1595  AgentReply(content=f"Listo, abrí {_ao_name}.")   # abrir app
agent.py:672   f"Listo, abrí «{target}» en {_app}."              # nav in-app
agent.py:1359  "Listo, lo hice en la calculadora."
agent.py:1546  "Listo, saqué la captura."
...
```
Esto **viola el CLAUDE.md** ("el LLM responde, nada de respuestas enlatadas").
El fine-tuning era irrelevante para estos casos: el reply nunca llega al modelo.

**(B) El SUMMARY PASS del LLM se ancla al idioma del contexto.**
Para close/volume/mute, el LLM SÍ genera el reply (segundo pass que resume el
tool result), pero **en español** — aunque el system prompt dice explícitamente
"ALWAYS reply in the SAME language the user wrote" (VERIFICADO que el system
prompt correcto LLEGA al summary pass). El modelo chico prioriza el idioma del
**contexto inmediato** (schemas de tools, historia, tool results — todo en
español) por encima de la instrucción del system.
> Esta es la pregunta central de la **investigación #2** (en curso): si el
> "anclaje al idioma del contexto" en modelos chicos es un failure mode
> documentado y cuál es la mitigación con evidencia.

### 2.4 Fix parcial ya aplicado y MEDIDO (app.open)
Helper nuevo `Gemma4Agent._llm_action_reply(user_text, did, fallback)`
(gate `GEMMA4_LLM_ACTION_REPLY=0`): tras un tool exitoso, pide al LLM una
confirmación brevísima **con contexto LIMPIO y enfocado** en el idioma del
usuario; si falla, cae al string ES previo (fallback seguro).
- **GOTCHA resuelto:** el `model` default `"gemma-4"` NO existe en el server
  (sirve `vram4-text`) → HTTP 400. Fix: `model=self._router_model_for(msgs)`
  (gotcha ya conocido en memoria `project_jarvis_llm_reflection`).
- **Resultado MEDIDO (app.open):**
  ```
  EN "open notepad"        -> "Notepad is open."       OK  0.1s
  FR "ouvre le bloc-notes" -> "Bloc-notes ouvert."     OK  0.1s
  DE "öffne den editor"    -> "Editor ist geöffnet."   OK  0.1s
  IT "apri la calcolatrice"-> "Calcolatrice aperta."   OK  0.1s
  ES "abrí la calculadora" -> "Abrí la calculadora."   OK  0.1s
  PT "abre o bloco..."     -> "Opened Notepad."        ⚠️ (cayó a EN)
  ```
  **5/6 en su idioma + latencia de SOLO 0.1s** (no el +1s temido: el pass es
  cortísimo, 40 tokens, sin thinking, prefix cacheado).
- Esto VALIDA empíricamente la hipótesis del patrón "minimal clean context para
  el paso de summarization" (investigación #2 lo confirmará o matizará con
  fuentes). PT sigue siendo el caso débil (PT/ES se confunden en el 2B).

---

## 3. Frentes del fix multilingüe aplicados hasta ahora

1. **Dataset:** +1253 ejemplos post-tool noES (de un workflow generador,
   100% válidos, 0 en español). Post-tool noES subió de ~250 a ~560 por idioma;
   share efectivo post-tool noES **25% → 40%**. Dataset 7022 → 8275, auditado
   limpio. (`split_and_weight.py` con TARGET ES=0.60 ancla.)
2. **Prompt:** quitadas las 3 anclas de español de `core_lean.md` + `core.md`
   ("Reply in Spanish" → "Reply in the SAME language"; el ejemplo "Listo, abrí X"
   → ejemplos en varios idiomas; "say so in Spanish" → "in the user's language").
3. **Modelo:** re-entrenado 3ep (loss 0.443), merge OK (EOS intacto),
   cuantizado Q4_K_M 3.43 GB, desplegado (backup del 3ep previo en
   `models/E2B/...SWEEP-3ep-prebalance.gguf`).
4. **Runtime:** helper `_llm_action_reply` cableado en app.open (medido 5/6).
   **PENDIENTE:** resolver el leak del summary pass (sección 2.3-B) según la
   investigación #2.

---

## 4. Investigación #2 — Idioma en el reply post-tool (VERIFICADA)

**Método:** deep-research, 102 agentes, 15 claims confirmados / 10 REFUTADOS.
Reporte completo: `documentacion/_research_idioma_posttool_REPORTE_COMPLETO_2026-06-06.json`.
Fuentes primarias: Cohere/EMNLP 2024 "Language Confusion" (arXiv:2406.20052 /
aclanthology 2024.emnlp-main.380), Shaham et al. Google Research ACL 2024
(arXiv:2401.01854), Lee et al. 2025 (arXiv:2505.19116), Liu & Niehues MRL 2025
(arXiv:2510.19546), Nie et al. 2025 (arXiv:2505.16538), doc oficial Gemma 4.

### 4.1 El problema TIENE nombre y está documentado — `EVIDENCIA ALTA`
- Es **"language confusion"** (Cohere/EMNLP 2024, término acuñado verbatim): la
  incapacidad del LLM de generar consistentemente en el idioma deseado/apropiado
  al contexto. Es un **error**, NO code-switching natural. Ocurre a nivel de
  respuesta completa, línea y palabra.
- Nuestro caso (reply post-tool deriva a español pese a input EN/FR) es una
  instancia de context-anchoring de este fenómeno documentado.

### 4.2 Causas con evidencia (lo que SÍ está respaldado)
1. **El SFT en idioma dominante AGRAVA la confusión** (EMNLP 2024 §6.4, ablación
   controlada): el SFT estándar solo maximiza likelihood del token correcto y
   **NO penaliza la mezcla cross-lingual** → no hay presión contra derivar al
   idioma dominante. ES dominante en nuestro dataset = atractor aprendido.
2. **El idioma de los EXEMPLARES/CONTEXTO arrastra el idioma de salida**
   (EMNLP 2024 §6.3): few-shot en el idioma target casi elimina la confusión;
   **few-shot/contexto en OTRO idioma puede EMPEORARLA**. → Los **schemas de
   tools, tool results e historia EN ESPAÑOL** actúan como "demostraciones"
   no-target que tiran el reply al español. **Implica directamente nuestro
   contexto español como fuente del drift.**
3. **Modelos chicos en dataset estrecho/dominante son estructuralmente
   vulnerables** al olvido de idiomas sub-representados (Liu & Niehues, medium
   confidence: el ratio modelo/datos es determinante; los chicos sobre datasets
   grandes/estrechos son los más vulnerables).
4. **El pre-training multilingüe AYUDA pero no garantiza** (Shaham et al.):
   modelos multilingüemente pre-entrenados responden en el idioma del prompt
   sin importar el idioma del tuning. Gemma 4 es multilingüe (140+ idiomas) →
   por eso obedece en prompt limpio (smoke) pero aún deriva bajo contexto ES
   pesado multi-turn. Pre-training favorable = necesario, no suficiente.

### 4.3 Mitigaciones RANKEADAS por evidencia
**Lo que SÍ tiene respaldo (priorizar):**
- **(a) Rebalancear datos: agregar ejemplos post-tool en el idioma target al
  SFT.** Shaham et al.: reemplazar **~1% de los ejemplos EN por multilingües
  (~40 ejemplos repartidos)** mejora sustancialmente el seguimiento de idioma;
  ~10% casi elimina la confusión a nivel línea. **CAVEAT de transferibilidad:**
  medido en PaLM 2-S (muy multilingüe); NO está establecido que el dosaje
  transfiera a un 2B con LoRA → **HAY QUE MEDIRLO** (regla 3 CLAUDE.md).
- **(b) Few-shot en el idioma target en el momento de generación** reduce mucho
  la confusión.
- **(c) Neutralizar/reducir el contenido en idioma dominante del contexto del
  paso de summary** (on-mechanism: el contexto ES es la "demostración" que
  arrastra). **Esto es exactamente lo que hace nuestro `_llm_action_reply` con
  contexto limpio — y por eso funcionó (5/6, 0.1s).**

**Lo que es FOLKLORE / NO sobrevivió la verificación (NO confiar):**
- ❌ "El system prompt gana sobre el contexto" / instruction-hierarchy
  (system>user>history>tool) — **REFUTADO (0-3 / 1-2)**. NO asumir que poner el
  directivo en el system basta.
- ❌ "Un recordatorio per-turn 'reply in same language' lo arregla" —
  **REFUTADO/no verificado**. Tratar como hipótesis a MEDIR, no como fix seguro.
  (Esto descarta una de las opciones que iba a proponer a ciegas.)
- ❌ "Poner el directivo al final por recencia" — sin respaldo.
- ❌ "El tamaño chico condena la resolución de conflictos" — REFUTADO (0-3).
- ❌ "LoRA protege mejor/peor que full-FT contra el olvido" — REFUTADO (0-3,
  sin ventaja clara).
- ❌ "La causa es el bias del late-layer del pre-training EN, no el contexto" —
  **REFUTADO (0-3)**: la evidencia NO permite descartar el contexto como causa;
  al contrario, los hallazgos de few-shot apuntan al contexto.

### 4.4 Gemma 4 oficial — `EVIDENCIA ALTA`
- El model card documenta el rol `system` nativo pero da **CERO guía sobre
  controlar el idioma de salida** y NO reconoce el language-drift como
  limitación (sus 5 limitaciones no incluyen confusión de idioma).
- La doc de function-calling **re-alimenta el tool result en la MISMA historia
  completa** (re-corre apply_chat_template sobre todo el historial) — es decir,
  **el flujo oficial es justamente el que arrastra el drift español**. Un
  "contexto mínimo limpio para el summary" **no está recomendado ni prohibido —
  es indocumentado** (decisión de ingeniería propia, razonable).

### 4.5 Latencia-cheap enforcement — `SIN EVIDENCIA directa`
- Logit-bias / GBNF grammar / segunda llamada chica: **ninguna fuente verificada
  los evalúa para forzar idioma**. Son opciones de ingeniería sin respaldo →
  tratar como hipótesis a medir, no como solución probada.

### 4.6 SÍNTESIS — la propuesta fundamentada
Priorizar las 3 palancas que SÍ sobrevivieron la verificación, en este orden:
1. **Contexto limpio para el reply post-tool** (`_llm_action_reply`) — YA
   validado empíricamente (5/6, 0.1s) y on-mechanism (§4.3-c). Extenderlo a los
   caminos de acción que hoy leakean (close/volume/mute/screenshot vía el
   summary pass). Es la palanca de MAYOR evidencia + MENOR latencia + cero
   re-entreno.
2. **Rebalanceo de datos** (§4.3-a) — ya hicimos +1253 ejemplos post-tool noES;
   está alineado con la evidencia. Medir si alcanza; subir dosis si no.
3. **NO** invertir en recordatorios de idioma en el prompt ni en instruction-
   hierarchy (folklore refutado). Si se prueban, MEDIR, no asumir.
> Decisión del usuario previa ("que el LLM genere el reply 1ero") coincide con la
> palanca #1, que es además la de mayor evidencia. Confirmado el rumbo.

---

## 5. Harnesses de diagnóstico (reproducibles)

- `scripts/_diag/_verify_focos_postft.py` — mide identidad/idioma/routing/
  español-coherente/anti-regresión en vivo. Gate decisivo: español ≥7/8.
  **GOTCHA:** si hay un `llama-server` externo en :8080, el harness se conecta a
  ÉL (modelo viejo en memoria) → mide el modelo equivocado. Matar el server o
  asegurar 8080 libre antes de medir.
- `scripts/_diag/_sweep_action_langs.py` — barre comandos de acción ×5 idiomas,
  marca leaks ES (15/21 antes del fix completo).
- `scripts/_diag/_test_action_reply_lang.py` — mide idioma + latencia del helper.
- `dataset_finetune/scripts/_diag_finetune_dataset_eval.py` — gate 0% tools
  inventadas (SIEMPRE con array tools; sin array inventa 47% = artefacto).

## 6. Pipeline FT (validado contra lo oficial)

```
curated.jsonl → split_and_weight.py (train/holdout + sample_weight)
  → train_ft.py (.venv_ft py3.12, Unsloth LoRA r16/α32, merge bf16 vía
                 recarga bf16 + merge_and_unload de PEFT — NO save_pretrained_merged)
  → quantize_gguf.py (CORRER CON .venv_ft/python.exe; convert→imatrix→Q4_K_M, --outtype bf16)
  → reemplazar models/E2B/gemma-4-E2B-it-Q4_K_M.gguf
```
`dataset_finetune/` es **GITIGNORED** (no va al push).

---

## 7. RESULTADO FINAL del fix de idioma (MEDIDO en vivo)

**Estado: LOGRADO.** De **idioma noES 0/5 → 5/5** sin regresión del español.

### 7.1 Verificación integral (`_verify_focos_postft`, agente real completo)
```
ESPAÑOL COHERENTE (gate decisivo que tumbó v1/v2): 8/8  ✅
identidad Baxy:                                     5/5  ✅ + modelo OK
idioma noES (EN/PT/FR/DE/IT):                       5/5  ✅  (era 0/5)
anti-regresión (acciones siguen):                  3/3  ✅
routing:                                           2/4  ⚠️ PREEXISTENTE (no del idioma)
```
Replies: "Notepad is open"(EN), "Bloco de notas aberto"(PT), "Bloc-notes
ouvert"(FR), "Der Editor ist geöffnet"(DE), "Calcolatrice aperta"(IT).

### 7.2 Barrido amplio acción×idioma (24 casos, juzgado a mano)
**23/24 (96%)** en el idioma correcto. EN/PT/FR/DE perfectos, ES 3/3 (no
regresó), IT 3/4 (un screenshot intermitente por no-determinismo del 4B).
Evolución de la iteración: leaks 15 → 12 → 7 → 6 → 5 → 3 → 2 → ~1.

### 7.3 La solución (3 capas, todas medidas)
1. **MODELO** (frente datos+prompt): +1253 ej post-tool noES (share efectivo
   noES 25%→40%); quitadas anclas ES del prompt; re-FT 3ep; Q4_K_M desplegado.
2. **RUNTIME — el reply post-tool lo genera el LLM en el idioma del user**, no
   hardcodeado en ES (cumple CLAUDE.md "el LLM responde"):
   - `_llm_action_reply(user_text, did, fallback, target_lang)` — confirmación
     con CONTEXTO LIMPIO (la palanca de mayor evidencia, §4.3-c) + `target_lang`
     explícito (el LLM inferia mal el idioma de comandos cortos).
   - `_describe_events_for_reply` — resume los tools en frase neutra inglesa.
   - Cableado en: short-circuit app.open, short-circuit extract_app_action
     (screenshot/cu), y el **repair central en `_finalize_turn`** (cubre el
     summary pass).
   - **Regla del repair (DECISIÓN del user 2026-06-06): regenerar SIEMPRE si el
     user escribió noES** (no condicionado a detectar el reply, que es poco
     fiable en español corto). Guard de aceptación: solo si el `_fixed` no quedó
     en ES (`_looks_spanish`).
3. **DETECCIÓN DE IDIOMA robusta:**
   - `_detect_lang` híbrido: verbo imperativo (FORMA) → py3langid restringido →
     `_guess_lang`. **Input 27/27** (donde `_guess_lang` solo daba ~7/14).
   - `_looks_spanish`: markers ES inequívocos (verbos 1ª persona + caveat ES) —
     guard de aceptación, **0 FP / 0 FN** en 23+ casos de prueba.
   - **py3langid** agregado a requirements.txt (dep liviana, fallback seguro).

### 7.4 Latencia
- ES (mayoría de uso): **0 costo** (no regenera, user_lang==es).
- noES: el repair agrega poco; los ~2s observados en close/volume son del
  **summary pass NORMAL del agente** (preexistente), no del repair. Short-
  circuits puros (open/screenshot): 0.06-0.1s.
- Gate global `GEMMA4_LLM_ACTION_REPLY=0` para desactivar todo el mecanismo.

### 7.5 Tests
234 passed en la suite reply/lang/honesty. Los 3 fallos (`test_deictic_ring`
MultilingualDetection, `test_read_messages` email-hijack, `test_smart_home`
readonly-claim) son **PREEXISTENTES** (verificado con git stash: fallan idénticos
sin mis cambios — deuda del WIP previo cacería/refinetuning). Mis cambios NO
rompieron ningún test.

### 7.6 Caveats honestos
- IT screenshot intermitente (no-determinismo del 4B) — caso aislado.
- El detector de idioma del REPLY corto sigue siendo poco fiable (limitación de
  py3langid con 2 palabras + nombres propios) — por eso el repair NO depende de
  él, usa el idioma del INPUT (27/27) + regenera siempre en noES.
- Medido contra ejecución física MOCKEADA (run_content). El comportamiento de
  idioma no depende de la ejecución real, pero el reply final con resultados
  reales del tool podría variar levemente.

---

## 8. FIX de routing (preguntas NO ejecutan) — 2026-06-06

El `_verify_focos_postft` marcaba routing 2/4. Eran 2 bugs REALES de comportamiento
(no cosméticos), ambos arreglados a 4/4 (barrido 6/6):

### 8.1 `está Steam abierto?` → abría Steam (pregunta tratada como comando)
- **Causa:** `_is_app_state_check` (planner.py) tenía un regex que exigía el verbo
  "está" INMEDIATO a la palabra de estado ("está abierto"). Con la app en medio
  ("está **Steam** abierto?") no detectaba → no retiraba steam/app/browser del
  subset → el LLM abría Steam.
- **Fix:** `_APP_STATE_CHECK_RE` alt-3 permite 0-3 tokens entre el verbo y el
  estado (`(?:est[áa]\w*|is|are|sigue|tengo|hay)\s+(?:\w+\s+){0,3}?<estado>...?`).
  Verificado: 7/7 preguntas de estado detectadas, 5/5 comandos NO (incluido el
  caso "si está abierto cerralo" que es acción, correctamente NO abstiene).

### 8.2 `cómo cierro Spotify?` → "Listo, cerré Spotify" (claim falso)
- **Causa (sutil):** el planner SÍ retiraba app/steam para how-to (subset queda
  `['session']`, solo-meta) y el LLM NO ejecutaba (exec=[]). PERO el reply mentía
  "Listo, cerré Spotify", y el guard de honestidad `guard_grounded_action_claim`
  (agent_guards.py) tenía una EXENCIÓN para subsets meta-only — diseñada para
  cancelaciones ("cancelé eso"=ack de inacción verdadero). El how-to caía en esa
  exención → el claim falso pasaba.
- **Fix:** la exención meta-only NO aplica si el user hizo una pregunta HOW-TO
  (`_is_howto_or_info_question(current_user_text)`): ahí "cerré Spotify" SÍ es
  mentira. Ahora el guard reemplaza por "No alcancé a completar la acción".
- Resultado: el how-to ya NO ejecuta NI miente. (Mejora futura posible: que
  EXPLIQUE el cómo en vez del fallback honesto — pero lo crítico, no-ejecutar y
  no-mentir, está cubierto.)

Ambos fixes son ESTRUCTURALES (miden la FORMA: interrogador how-to / pregunta de
estado), no listas hardcoded — consistentes con CLAUDE.md.

### 8.3 Bugs adicionales de routing arreglados (al investigar el condicional-acción)
- **`cerrá [app]` (voseo) caía a ['session']** (no podía cerrar). El regex de la
  tool `app` tenía `cierra|cerrar|close` pero NO el voseo argentino `cerrá`/`abrí`
  ni clíticos (`cerralo`/`matalo`). El user vosea → fix universal: agregué voseo +
  clíticos + matá/kill/ventana-de al regex (planner.py ~1530). Verificado: 7/7
  acciones voseo ahora ofrecen app/window; estado sigue abstineiéndose.
- **`qué aplicación está abierta` iba a web/knowledge** en vez de window.active.
  `wants_knowledge` (_is_world_q) la marcaba como pregunta de MUNDO y mantenía
  web/knowledge, tapando el bloque local_state (que solo corre con names vacío).
  Fix: si `_is_local_state_question` es True, _is_world_q se anula y se retiran
  web/knowledge → el local_state gana y ofrece window. Verificado: 5/5
  local-state→window; world-q reales (Oppenheimer/capital) mantienen web; smalltalk
  no trae window.

### 8.4 Veredicto final routing + tests
- `_verify_focos_postft` ROUTING: **2/4 → 4/4** (integral, en vivo).
- `test_router.py`: **10/10** (los 2 tests de state que fallaban ahora pasan).
- Suite routing/planner/guard amplia: **con mis cambios 7 fallos, sin 19** → mis
  cambios ARREGLARON 12 tests preexistentes y NO introdujeron NINGUNO (verificado
  con git stash, diff "introducidos" VACÍO).
- Los 7 fallos restantes son PREEXISTENTES de áreas ajenas (reminder semantic
  ranking ×3, router_load_health ×3, smart_home readonly-claim ×1) — deuda previa,
  no de esta sesión.
- CAVEAT honesto: el caso "qué modelo usás?" dio una vez "No pude terminar la
  tarea dentro del límite de turnos" (no-determinismo del 2B, no regresión — no se
  tocó identidad/modelo; en otras corridas da "Gemma 4" OK).
