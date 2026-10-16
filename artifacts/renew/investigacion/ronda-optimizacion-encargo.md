# Ronda de verificación y optimización de BAXY Renew para su modelo

Eres un agente de una ronda de verificación. El dueño pide rondas sucesivas hasta una ronda limpia (sin violaciones; ver «Criterio de cierre»). Tu trabajo es encontrar lo que falta o está mal en TU FOCO (abajo), con
evidencia, o declarar con argumentos que no queda nada.

## Qué es
BAXY Renew = Qwen3.5-4B Q4_K_M en llama.cpp b11609 (llama-server `--jinja --reasoning off`, tool calling nativo, -c 49152,
KV q8_0, -cram 1536) + las herramientas de BAXY (172 operaciones). El modelo decide todo en un bucle nativo
(src/baxy_mind/mind.py, src/Baxy.App/NativeTurnLoop.cs). Repo: C:\Users\usuario\Desktop\ETC\Programacion\BAXY-Renew
(rama baxy-renew). Lee `PROMPT_GOAL_RENEW.md` (reglas y criterios), `artifacts/renew/PROGRESO.md` y
`artifacts/renew/metas.json` antes de proponer nada, y `artifacts/renew/investigacion/*.md` (lo ya investigado).

## Reglas que nada puede violar
1. Sin ayudas al modelo en código: nada de regex, reglas semánticas, guardias, vetos, listas de palabras ni pasos
   dictados que interpreten a la persona o corrijan al modelo. Se quedan: catálogo tipado, kernel de riesgo y
   confirmación, journal, verificación del proveedor, enmascarado de datos sensibles.
2. Mejoras sólo de presentación (prompt, descripciones, skills, formato), protocolo e inferencia.
3. Honestidad: nunca dar por hecho algo no ejecutado y verificado; documentar límites con evidencia.
4. Investigar antes de implementar: cita la fuente (paper, doc oficial, experiencia de usuarios con URL).
5. ≤ 4 GB VRAM y ≤ 4 GB RAM. Identidad: nada del dueño sale sin pedido; nunca click/escritura en la ventana de la
   persona sin pedido; cero código muerto; la personalidad vive en el prompt.

## Ya medido o decidido (NO lo vuelvas a proponer sin evidencia nueva que lo contradiga)
- Formato: el arnés ya usa el XML de Qwen3-Coder con la plantilla oficial; nombres de herramienta con «_» en todo el
  texto; paso final con tools + tool_choice none + logit_bias contra `<tool_call>` (no desaloja la caché).
- Sampling: temp 0.2 / top_p 0.8 / top_k 20, seed 0; temp 0 = igual; presence_penalty descartado (penaliza copiar las
  palabras de la persona). KV f16 no cabe (4454 MiB) y no gana. -c 40960 igual con menos margen. Checkpoints densos
  +46 ms sin ganancia. MTP medido y peor (638 -> 744 ms). Draft 0,8B no cabe. Lista de apps compacta −2 % de prefijo
  con cambio de contrato: descartada; quitar ejemplos −14 % pero los ejemplos son lo que gana: descartado.
- SYSTEM: dos variantes perdieron en decision2 (223 y 221 vs 231): se queda. Tool Search / skills como índice
  (arnes.md): brazos medidos antes; el prefijo es ~38-40k tokens en caché y una decisión relee ~100-200 tokens.
- Descripciones: las de ee435857e + arreglos puntuales. Un borrador de 304 significados de argumentos subió e2e pero
  bajó decision2 ~7 y subió el prefijo a 45k (primer sonido 3,2 s); podado a 84 también bajaba decision2: se volvió a
  ee435857e. OJO: en decision2 cualquier edición pequeña mueve ±6-9 casos (ruido de edición; a prompt idéntico ±1),
  así que una propuesta de texto sólo vale con evidencia por caso (casos que gana y pierde, y por qué), no por total.
- Resultados SELLADOS (una sola vez, commit 0417eec7b): decisión 140/167 (83,8 %), escenas 39/59 (66,1 %; 1,36
  molestas/20; 0 riesgo solo), latido 8/10 (80 %); e2e/falsedades/recursos en curso. Instinto NO se cumple. Una causa
  probable: el latido de la App retiene para el «sí» lo que manda entrada a ventanas o reproductores (decisión del
  dueño), y el banco esperaba «actuar» (pausar, minimizar).

## Datos que puedes leer (sólo práctica; NUNCA abras sellados)
Práctica: F:\BAXYeval\renew_v1\practica\decision2.json, escenas\practice.json, e2e\practice.json,
falsedades\practice.json, y corridas en F:\BAXYeval\renew_v1\runs (d*.jsonl, e1*-escenas*, p*-e2e/, p*-falsedades/).
PROHIBIDO abrir: holdout\*, escenas\sealed.json, escenas\holdout_latido.json, e2e\sealed.json, falsedades\sealed.json,
SEALED-*.md, y los final-*.jsonl de runs más allá de su primera línea (resumen).

## Cómo trabajas
- Sólo lectura en el repo: no edites, no hagas commit. No corras Baxy.exe, llama-server ni nada en la GPU (hay bancos
  corriendo), ni dotnet test. Puedes buscar en la web (fuentes primarias, papers, issues, foros con experiencias).
- Antes de opinar sobre código, ábrelo.
- Entrega en español, ≤ 800 palabras:
  1. Hallazgos CONCRETOS, priorizados: qué (archivo:línea o texto exacto), por qué (evidencia: caso de práctica,
     código, fuente con URL), cambio propuesto exacto, cómo medirlo y riesgo. Separa «viola una regla» de «mejora».
  2. Lo que revisaste y está bien.
  3. Separa VIOLACIONES (de <reglas> o de la identidad: ayuda al modelo en código —regex, regla semántica, veto,
     lista de palabras, paso dictado—; un recibo, respuesta, comentario o documento que dice más de lo que se ejecutó y
     verificó; algo del dueño que sale sin pedido; un click o tecleo en su ventana sin pedido; código muerto; pasarse de
     4 GB de VRAM o RAM) de las MEJORAS GRISES (todo lo demás: se anotan en PROGRESO y no obligan a otra ronda).
  4. Última línea obligatoria, una de dos: `VEREDICTO: VIOLA (n)` o `VEREDICTO: SIN VIOLACIONES`, y aparte la lista
     de mejoras grises.

## Criterio de cierre (dueño, 2026-10-16 01:48)
Ronda limpia = ningún agente encuentra una violación. 4 agentes por ronda en el PC y 4 en el notebook con focos
fijos: mente y catálogo; App e interfaz; proveedores; bancos y honestidad (metas.json, PROGRESO, jueces). Una
violación se arregla siempre; una mejora entra sólo si gana en práctica caso por caso por encima del ruido
(decision2 ±6-9, escenas ±2) sin perder silencios del latido ni sumar falsedades; lo que no se mida o no gane queda
pendiente. Tope: 2 rondas más o hasta 2026-10-16 07:48, lo que llegue antes; al tope, las violaciones que queden van
como límite honesto en metas.json con su evidencia.

## Tu foco
