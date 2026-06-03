# Skill retrieval: investigación del estado del arte (2026-05-30)

> Antes de mejorar el auto-inject de skills, esta es la investigación de CÓMO se
> selecciona/inyecta bien una skill según el estado del arte. Pedido del usuario:
> "no improvises, investigá cómo lograrlo, quizás copiá algo como el router de
> tools". La conclusión: **el router de tools y la selección de skills son el
> MISMO problema (retrieval), y la técnica correcta está publicada.**

---

## 0. El problema medido (no intuición)

El auto-inject actual matchea la query del usuario contra la **descripción
abstracta** de cada skill por coseno (umbral 0.45). Medido:
- "saca una captura y dime que ves" → screenshot a **0.43** (< 0.45 → NO dispara).
- "investiga sobre X en internet" → matchea **debug-app-crash** (¡intent equivocado!).
- RECALL gold: 9/12 (3 miss). 0 falsos positivos en control.

El problema es **doble**: recall bajo (fraseos reales no matchean la descripción
abstracta) Y precisión frágil (intents distintos colapsan juntos). Es
EXACTAMENTE el problema de "tool retrieval" que la literatura ya resolvió.

---

## 1. Anthropic Agent Skills (el estándar oficial, dic 2025)

El estándar oficial usa **progressive disclosure de 3 niveles**:
1. **Metadata** (name + description, ~80 tok/skill) — siempre en el prompt.
2. **Instructions** (SKILL.md completo) — cuando se activa.
3. **Resources** (scripts/, references/) — bajo demanda.

**CÓMO selecciona:** el LLM **RAZONA** sobre name+description y decide si cargar
(`skill_load`). NO usa embeddings, NO retrieval. Es **LLM-driven**.

> ⚠️ **Por qué NO sirve para nuestro 4B:** el estándar asume un modelo GRANDE
> capaz del meta-paso "ver metadata → razonar relevancia → cargar → seguir".
> MEDIDO en nuestros logs: el 4B emite skill_load **1 vez en 117.764 eventos**.
> No hace el meta-paso. **Por eso usamos auto-inject** (inyección determinista
> por embedding) — la adaptación correcta para modelo chico.

Fuente: [Anthropic Engineering](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills),
[swirlai](https://www.newsletter.swirlai.com/p/agent-skills-progressive-disclosure).

---

## 2. TinyAgent (function calling en el edge, arXiv 2409.00608)

Nuestro caso EXACTO: function-calling con modelo chico local. Su técnica central:
**"a novel tool retrieval method to reduce input prompt length"** — retrieval por
embeddings para seleccionar el subset de tools que ve el modelo chico, igual que
nuestro router. Validación: un modelo chico con buen retrieval iguala a GPT-4-Turbo
en function calling al edge.

**Lección:** el retrieval por embeddings PARA seleccionar skills/tools de un modelo
chico es el patrón validado. Es lo que el router de tools ya hace — el insight del
usuario (copiar el router) es correcto.

Fuente: [TinyAgent arXiv:2409.00608](https://arxiv.org/abs/2409.00608),
[KDnuggets — SLMs for tool calling](https://www.kdnuggets.com/5-small-language-models-for-agentic-tool-calling).

---

## 3. Re-Invoke (Google Research, EMNLP 2024) — LA RECETA

El paper más directamente aplicable. Resuelve el problema intent-mismatch
("improve French" se ruteaba a un travel tool, igual que nuestro "investiga"→debug).

**Técnica (sin entrenar, zero-shot):**
1. **Document expansion por synthetic queries** (offline/indexing): por cada
   skill, generar ~10 queries sintéticas diversas que cubran el espacio de
   fraseos del usuario. Ej. para screenshot: "saca una captura", "qué hay en
   pantalla", "leeme lo que dice", "describí lo que ves"…
2. **Intent extraction** (online): extraer el intent del query del usuario.
3. **Multi-view similarity ranking**: scorear el query contra CADA query
   sintética + la descripción, agregando — NO contra un solo doc concatenado.

**Resultado:** +20% nDCG@5 single-tool, **+39% multi-tool**. Sin entrenamiento.

Fuente: [Re-Invoke arXiv:2408.01875](https://arxiv.org/abs/2408.01875),
[Google Research blog](https://research.google/blog/re-invoke-tool-invocation-rewriting-for-zero-shot-tool-retrieval/).

---

## 4. Tool-DE (oct 2025) — el matiz CRÍTICO de agregación

"Tools are under-documented: Simple Document Expansion Boosts Tool Retrieval".
Enriquece con campos estructurados (`when_to_use`, `tags`, `limitations`) **NO**
queries crudas. **Hallazgo de su ablation:** agregar `example_usage` al doc
concatenado **EMPEORA** el retrieval (diluye la señal con ruido).

> **La contradicción aparente entre Re-Invoke (+39% con queries) y Tool-DE
> (ejemplos empeoran) se resuelve en la AGREGACIÓN:**
> - Re-Invoke embeddea cada query **por separado** y agrega por max/multi-view →
>   preserva la señal discriminativa de cada fraseo.
> - Tool-DE **concatena** todo en UN doc → el promedio del embedding diluye los
>   ejemplos en la descripción genérica.

Fuente: [Tool-DE arXiv:2510.22670](https://arxiv.org/html/2510.22670v1).

---

## 5. Multi-vector vs single-vector concatenado (el por qué técnico)

La literatura de retrieval confirma el mecanismo:
> "Static pooling (mean/max) collapses the rich multi-vector representation into
> a single vector, **destroying the fine-grained information** that enables
> precise matching."

Concatenar descripción + ejemplos en UN texto y embeddearlo = **single vector
promediado** → los ejemplos se diluyen (Tool-DE lo confirma). Mantener cada
ejemplo como **vector separado** y tomar el **max** del coseno = preserva que
"saca una captura" matchee fuerte con el ejemplo "saca una captura" aunque la
descripción genérica esté lejos.

Fuente: [Pinecone — cascading retrieval](https://www.pinecone.io/blog/cascading-retrieval-with-multi-vector-representations/),
[Multi-vector retrieval analysis](https://dasroot.net/posts/2026/03/multi-vector-retrieval-is-it-worth-the-complexity/).

---

## 6. LA RECETA para nuestro auto-inject (validada, no improvisada)

Aplicar **Re-Invoke multi-vector** al `autoinject_skill`, respetando las leyes del
proyecto (embeddings multilingües, fallback seguro, sin keywords decisorias):

1. **Por cada skill, además de su `description`, definir N fraseos de ejemplo**
   (queries que el usuario diría, multilingües) en el frontmatter del SKILL.md —
   campo `triggers` o `examples`. Son ejemplos SEMÁNTICOS, NO keywords (el encoder
   generaliza; cubren el espacio de fraseos como en Re-Invoke).
2. **Embeddear la descripción Y cada ejemplo como vectores SEPARADOS** (cache).
3. **Score de la skill = MAX(coseno(query, descripción), coseno(query, ej_i))** —
   multi-vector max, NO concatenar (evita la dilución de Tool-DE).
4. **Disparar la skill del max-score si supera el umbral** (recalibrar el umbral
   con el nuevo scoring sobre el gold + control de falsos positivos).
5. **Mantener todo lo demás igual:** fallback seguro sin encoder, texto corto
   skip, multilingüe, gate `GEMMA4_SKILLS_AUTOINJECT`.

**Por qué esto arregla lo medido:**
- "saca una captura" matchea el EJEMPLO "saca una captura" (≈0.9) aunque la
  descripción abstracta esté a 0.43 → recall sube sin bajar el umbral.
- "investiga" matchea el ejemplo de research ("investigá sobre X en internet")
  mucho más que cualquier ejemplo de debug → precisión sube (no más
  intent-mismatch).
- El max preserva la señal discriminativa de cada fraseo (no se promedia).

**Gate de éxito (definido ANTES):** recall gold ≥ 11/12, 0 falsos positivos en
control + sobre los 1476 mensajes reales del usuario (sin tests), 0 regresión en
las skills que ya disparaban bien. Multilingüe (los ejemplos en es/en/pt).

---

## 7. Lo que NO hacer (lecciones de la investigación)

- **NO concatenar ejemplos en la descripción** (Tool-DE: diluye → peor). Vectores
  separados + max.
- **NO esperar que el 4B razone skill_load** (Anthropic standard asume modelo
  grande; medido 1/117k). Auto-inject determinista.
- **NO listas de keywords** para disparar skills (ley del proyecto). Ejemplos
  semánticos multilingües que el encoder generaliza.
- **NO bajar el umbral global** para arreglar recall (sube falsos positivos). El
  multi-vector sube el recall SIN tocar el umbral.

---

## R3.2 (2026-05-30): hard-negative suppression + margin/gap rule

El multi-vector recuperó recall pero quedaron **falsos positivos en la zona
límite** donde un umbral global NO separa: MEDIDO que un TP legítimo
("baja este video" → download 0.457) puntuaba MÁS BAJO que un FP por solapamiento
de sustantivo ("desmutea micrófono" → voice-record 0.656). Un umbral absoluto es
matemáticamente incapaz de separarlos.

Investigación (fuentes verificadas) → 3 técnicas, todas CPU/embeddings, sin
keyword lists:

1. **Hard-negative `limitations` en prosa** (Tool-DE arXiv:2510.22670): cada skill
   declara en lenguaje natural multilingüe lo que NO cubre ("no es para subir el
   brillo", "no para imprimir"). Se embeben como vectores de PENALIZACIÓN. Si la
   query matchea MÁS un `limitations` que el mejor positivo → la skill se SUPRIME.
   NO se agregan al pool MAX (eso invertiría el sentido); se comparan aparte.
2. **`when_to_use`** (positivo extra): refuerza el recall del intent correcto.
3. **Margin/gap rule** (conformal score-refinement arXiv:2410.02914): dispara solo
   si `top1 ≥ umbral` Y `(top1 − top2) ≥ margen`. El gap relativo es robusto al
   solapamiento que el absoluto no maneja.

**Causa-raíz, no parche**: cuando un ejemplo contaminaba (el PT "tire um print"
hacía que "imprime el documento" matcheara screenshot 0.729), se CORRIGIÓ el
ejemplo ("faça uma captura de tela": imprime→0.333, TP→0.736) en vez de
contrarrestarlo. Igual con el ejemplo de download "video o canción" (disparaba 17
FP de media.play) → reemplazado por "descargá y guardá en mi disco" (ancla el
"guardar", no el "video").

**Resultado medido**: FP-hard 9→**0**, regresión 53→**52/1481**, recall 19/21 (2
miss = temas concretos en el techo del encoder MiniLM; e5-small MEDIDO y RECHAZADO
— comprime los scores a 0.80-0.88 sin discriminar). Verificado en vivo 10/10.

Parser extendido: `_parse_yaml_simple` ahora soporta sub-listas anidadas bajo
`metadata:` (examples/when_to_use/limitations separados; antes aplanaba todo a una
lista mezclada, lo que trataría `limitations` como positivo).

**Gates**: `GEMMA4_SKILLS_THRESHOLD` (0.58), `GEMMA4_SKILLS_MARGIN` (0.05),
`GEMMA4_SKILLS_NEGGUARD` (0.0).

Microagents recibieron el mismo tratamiento (ver 08_MICROAGENT_RETRIEVAL_research.md).

---

## Fuentes

- [Anthropic — Equipping agents with Agent Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills)
- [Agent Skills: Progressive Disclosure (swirlai)](https://www.newsletter.swirlai.com/p/agent-skills-progressive-disclosure)
- [TinyAgent: Function Calling at the Edge (arXiv:2409.00608)](https://arxiv.org/abs/2409.00608)
- [Re-Invoke (arXiv:2408.01875, EMNLP 2024)](https://arxiv.org/abs/2408.01875) · [Google Research blog](https://research.google/blog/re-invoke-tool-invocation-rewriting-for-zero-shot-tool-retrieval/)
- [Tool-DE: Simple Document Expansion (arXiv:2510.22670)](https://arxiv.org/html/2510.22670v1)
- [Improving Tool Retrieval via LLM Query Generation (arXiv:2412.03573)](https://arxiv.org/pdf/2412.03573)
- [Pinecone — Cascading multi-vector retrieval](https://www.pinecone.io/blog/cascading-retrieval-with-multi-vector-representations/)
- [5 SLMs for Agentic Tool Calling (KDnuggets)](https://www.kdnuggets.com/5-small-language-models-for-agentic-tool-calling)
