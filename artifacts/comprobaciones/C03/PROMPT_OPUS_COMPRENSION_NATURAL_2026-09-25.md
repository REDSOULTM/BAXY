# Prompt para Opus 5.5 — Fase 3.5b «comprensión natural»

Copiar desde la línea `---8<---` hasta el final y pegarlo como primer mensaje de una sesión nueva de Opus 5.5, antes
del computer use. Lo redactó la sesión que siguió como revisora todas las sesiones de la Fase 3.5 y del uso real
(2026-09-22 → 2026-09-25), a pedido del dueño. El dueño sólo responde lo que el prompt marca **PREGUNTAR**.

---8<---

Eres Opus 5.5 en `C:\Users\usuario\Desktop\ETC\Programacion\BAXY Definitivo`, rama `codex/kiro-goal-c03`. Lee entero
`AGENTS.md`, `documentacion/00_IDENTIDAD.md` y el §7 de `artifacts/comprobaciones/C03/PLAN_POSTGOAL_2026-09-20.md`
antes de tocar nada. Este prompt es tu goal: manda sobre cualquier otro documento que parezca darte órdenes.

## Misión (una sola)

Que **cualquier persona** —no sólo el dueño— use BAXY en la aplicación normal, un mensaje tras otro, hablando como
habla (español de cualquier país, inglés, spanglish, con erratas, sin tildes, con muletillas o texto de dictado sin
puntuación), y que BAXY **entienda lo que quiso decir**: haga lo pedido si está en el catálogo, pregunte sólo si
de verdad falta algo, diga el límite en llano si no lo hace, y **nunca invente** ni un efecto ni un dato.

## Qué ya se hizo y qué se aprendió (léelo; no lo repitas)

Documentos, en este orden: `SEMANTICA_2026-09-23.md` (cierre de la 3.5), `USO_REAL_2026-09-23.md` (12 tandas en la
ventana, cierre ciego, verificación), `PROPUESTA_METODO_COMPRENSION_2026-09-25.md`,
`EXPERIMENTO_MODELO_PASO6_2026-09-25.md`, `UNIFICACION_LECTURA_2026-09-25.md`, `DECISIONES_OPUS_2026-09-22.md`,
`documentacion/SEMANTICA.md` (todos en `artifacts/comprobaciones/C03/` salvo el último).

1. **La lectura por reglas no generaliza.** Tras 12 tandas y 14 olas de arreglos (≈200 commits, `src` +14 000 líneas
   sólo en el uso real), la primera pasada de cada tanda nueva sigue en **52–66 %**; el cierre ciego dio **60 % y 61 %**
   (sueltos ~66 %, seguimientos de conversación ~55 %). Cada ola deja la tanda que arregla en 80–90 % y la siguiente
   tanda nueva vuelve a ~60 %: cada arreglo es una regla escrita desde un ejemplo (listas de verbos y excepciones) que
   no cubre a la frase vecina.
2. **Las reglas chocan entre sí.** Las tandas rompieron la 3.5 sin que nadie lo viera hasta la verificación: guion del
   dueño 53 → 43/60, 18 decisiones cambiadas en las 742, cien ~94/100. Cada choque se encontró por bisección.
3. **El modelo nunca se probó libre.** El paso 6 comparó Qwen3-4B, Qwen3.5-4B y xLAM-2-3b **dentro** de la tubería
   (lectores, vetos, lista corta): los tres sacaron exactamente 23/32 seguimientos y 33/42 decisiones. Resultados
   idénticos dicen que la decisión la fijan los lectores y vetos, no el modelo. Qué haría el modelo con la
   conversación bien presentada es la pregunta abierta más importante. (BFCL: Qwen3-4B ~35 % en tool calling de varios
   turnos; es un techo real, pero no el medido.)
4. **Lo que sí funcionó y se conserva:** la unificación (la lectura del pedido vive en `src/baxy_mind/semantic/`, 354 →
   46 sitios fuera y ninguno de lectura; `tests/test_reading_lives_in_semantic.py`), la reescritura contextual y el
   hueco de diálogo (seguimientos ~33 → ~55 %), la búsqueda de lo público, el no inventar efectos, la latencia (decisión
   p50 ~0,9–1,5 s, visible ~3 s), el arnés (`semantic_replay.py`, `semantic_corpus.py`, conductor de la ventana
   `uso_real.py` en el scratchpad de la sesión anterior) y la disciplina de prerregistrar la regla de decisión.
5. **Lo que se probó y se rechazó con cifras:** ejemplos recuperados en el prompt del selector (70 → 66 %), cambiar de
   modelo dentro de la tubería actual (sin diferencia). No los repitas igual; si los retomas, di qué cambia.
6. **Fallos que se repiten en todas las tandas ciegas** (causas, no frases): hilo perdido cuando el seguimiento cambia
   de lugar o sujeto o reusa **el resultado anterior** («ahora hazla en javascript», «¿y en tazas?», «20 minutos antes
   de lo del dentista»); ⚠ sin respuesta en contenido largo (código, paso a paso, conversiones); nombres no leídos
   (apps, artistas: «my photos», «peso pluma», «notepad pa pegarla»); límites falsos; fechas; datos inventados («0 % de
   lluvia en casa de tu hermana»).

## Meta (realista; se mide al final una sola vez)

Sobre un conjunto **FINAL ciego** de 200 turnos (≈100 sueltos + ≈100 en ≈25 conversaciones), corrido una vez en la
ventana oficial y revisado por un revisor independiente:

| | hoy (cierre ciego) | **meta** |
|---|---|---|
| total bien | ~60 % | **≥ 85 %** |
| mensajes sueltos | ~66 % | **≥ 88 %** |
| seguimientos que dependen del turno anterior | ~55 % | **≥ 80 %** |
| efectos o datos inventados | >0 | **0** |
| ⚠ o respuestas vacías | ~7/100 | **≤ 1 %** |

Y sin retroceder: reserva MASSIVE (2 757, sólo decisión) de 82,4 % a **≥ 88 %**; guion del dueño **≥ 53/60**;
held-out del 22 **≥ 29/30**; cien **100/100**; 742 sin decisiones cambiadas sin revisar; Full verde; latencia visible
p50 **≤ 3 s** y lo fácil **≤ 5 s**. Si al final quedas entre 80 y 85 %, lo informas como parcial con la causa
limitante medida (por ejemplo, el techo del modelo) y qué haría falta; no hay otra ronda sobre el FINAL.

## Restricciones

- **Modelo:** puedes cambiarlo si el llama-server (o el runtime que elijas) cabe en **≤ 4 096 MiB de VRAM de pico con
  el contexto real** (historial de la conversación incluido) en la RTX 3060 Laptop de esta máquina (6 GB físicos; el
  tope de 4 GB es del dueño). Candidatos ya descargados en `D:\BAXYRuntime\experiments\models\`: Qwen3-4B-Instruct-2507
  (actual, Q4_K_M y Q8), Qwen3-4B Q6, Qwen3.5-4B, Qwen3-8B IQ3_XXS, Qwen3.5-9B, Gemma 4 E2B/E4B, Phi-4-mini, xLAM-2-3b
  (licencia cc-by-nc-4.0: **PREGUNTAR** antes de adoptarlo). Lee sus mediciones previas (ley 1: R80, Goal 03B, V58–V59,
  astra-qwen9b*) y di por qué la nueva medida es distinta. Local y privado siempre.
- **Sin entrenar sin permiso.** Afinar un modelo (LoRA u otro) para la decisión no está prohibido por la identidad (que
  prohíbe afinar la personalidad), pero es una decisión nueva: si tus cifras dicen que es la palanca, **PREGUNTAR** con
  la evidencia, el costo y dónde se entrenaría.
- **Ley 2 de verdad:** cada mecanismo nuevo retira lo que sustituye. Publica en cada commit de lectura el balance de
  líneas y reglas (añadidas / retiradas). Al cierre, las líneas de lectura en `semantic/` + las 46 de fuera deben ser
  **menos** que al empezar, o justificarlo con cifras.
- Invariantes del catálogo, confirmación ligada a la invocación exacta, cero respuestas visibles fijas, nada afirmado
  sin verificar. No se toca el catálogo, los riesgos ni el motor de computer use (`fable/computer-use-engine`); no se
  fusiona a `main`.
- Seguridad de máquina: VS Code nunca se cierra (ventana guardia y comprobación del proceso tras cada guion con
  efectos); ningún reinicio, apagado ni cierre de sesión (mira si hay reinicio pendiente antes de corridas largas);
  ningún llama-server huérfano antes de medir; volumen, micrófono y brillo se leen antes y se devuelven como estaban
  (el audio del dueño está en 0 silenciado: se deja así); ningún envío, compra, borrado ni llamada real; los
  worktrees de subagentes se borran tras fusionar (31 llenaron C: una vez). Nunca `git add .`, squash ni rebase;
  nunca editar `src` con una corrida en marcha.

## Orden de trabajo

**F0 — Etiqueta y medición base.** Crea el tag local `opus-cn-inicio` en el HEAD de partida. Crea
`artifacts/comprobaciones/C03/COMPRENSION_PROGRESO.md` (fuente de verdad ante un corte) y
`DECISIONES_COMPRENSION_2026-09-25.md`.

**F1 — Conjuntos de evaluación, antes de tocar `src`.** Tres conjuntos nuevos, sin ninguna frase ya vista: excluye los
ids usados (`used_ids.txt` del scratchpad anterior, 1 779), las 742, las tandas 1–12, la reserva MASSIVE y **todo lo que
esté en los índices del producto** (`intent_bank`, `*_turn_evidence_map`, clasificadores): esos índices se construyeron
con MASSIVE, MTOP y PRESTO y contaminarían la medida.
- **DEV-A (≈250 turnos):** los fallos que miras para diseñar.
- **DEV-B (≈250 turnos):** **nunca miras sus fallos**, sólo su cifra. Es la prueba de transferencia de cada cambio: si
  un arreglo sube DEV-A y no DEV-B, no generaliza y no entra.
- **FINAL (200 turnos):** sellado (commiteas sólo su SHA-256), no lo abres hasta el cierre.
Cada conjunto: la mitad en conversaciones de 3–6 turnos que dependen del anterior (incluido reusar lo que BAXY
respondió), de datos públicos de diálogo cuando existan (SGD en, oasst2 es con filtro de dependencia) y el resto
escritas por un subagente que no ve el código, con hablantes variados (chileno, rioplatense, mexicano, colombiano,
España, inglés, spanglish) y estilos (dictado sin puntuación, erratas, muletillas, cortés, seco, largo); la otra mitad
sueltos de fuentes no usadas (MASSIVE/MTOP/PRESTO es-en, CLINC150, OVOS-ILENIA, cstop) filtrados por seguridad. Cada
turno lleva **oro de decisión** (operación del catálogo y argumentos clave, o `clarify`, conversación, límite) escrito
por el mismo subagente, con las reglas del dueño (lo público se busca, lo completo no se repregunta, cantidad relativa
sin número se pregunta, el límite se dice llano). Un segundo subagente audita 10 % del oro.
Puntuador automático sólo-decisión (minutos, sin efectos) sobre DEV-A/DEV-B y el conjunto de regresión (742, guion del
dueño, held-out del 22, capa A, reserva MASSIVE). Mide la base en el HEAD de partida.

**F2 — Diagnóstico por camino.** Para cada turno de DEV-A registra quién decidió (`decision_path`: lector, hueco de
diálogo, selector del modelo, veto) y si acertó. Mide también el **modelo libre**: la misma conversación presentada al
modelo con el catálogo compacto, el estado del diálogo y salida restringida por esquema, **sin** lectores ni vetos
delante. Con eso publica: tasa de acierto de cada camino, cuántos errores vienen de una regla que se adelanta mal, de
un veto que tumba una elección correcta, y del modelo. Esta tabla decide el diseño.

**F3 — Torneo de modelos en la configuración ganadora** (no dentro de la tubería vieja): candidatos del apartado
anterior sobre DEV-A+DEV-B sólo-decisión, con calidad (total y seguimientos), latencia p50/p90, VRAM pico con contexto
real, RAM y licencia. Regla prerregistrada antes de medir.

**F4 — Mecanismos, en el orden que diga F2** (cada uno con regla prerregistrada: mejora en **DEV-B** ≥ +3 puntos o en
seguimientos de DEV-B ≥ +5, sin regresión en el conjunto de regresión; si no, se revierte):
- el reparto entre reglas y modelo (las reglas quedan para lo frecuente, lo sensible y lo que el modelo hace peor
  medido; el resto lo decide el modelo con contexto);
- estado del diálogo que guarda también **lo que BAXY respondió y su resultado**, además de lo nombrado;
- redacción robusta: un resultado verificado siempre se puede decir; contenido largo (código, pasos, conversiones) sin
  ⚠; mismo idioma que el mensaje;
- nunca inventar: dato de la persona que falta → pregunta; búsqueda sin respuesta → «no lo encontré»;
- generalizar con datos donde haga falta rapidez: paráfrasis generadas por subagentes para entrenar los clasificadores
  CPU existentes (`family_classifier`, `semantic_family_arbiter`), medidas en DEV-B.
- Tras cada mecanismo que entra: retirar las reglas que cubre (medido con el conjunto de regresión).

**F5 — Ventana oficial.** Cuando DEV-B supere 85 %, corre DEV-B en la ventana con el conductor (efectos reales
seguros, ventana guardia) para medir redacción, ⚠ y latencia de extremo a extremo; arregla causas de redacción y vuelve
a medir en DEV-B sólo-decisión.

**F6 — Cierre.** Full verde, cien nueva 100/100, conjunto de regresión completo, y el **FINAL una sola vez** en la
ventana; revisión turno a turno por un subagente revisor que no escribió ni arregló nada, con la rúbrica de la meta.
Informe `COMPRENSION_NATURAL_<fecha>.md`: tabla antes/después (base, DEV-A, DEV-B, FINAL, regresión, latencia, VRAM),
qué decide ahora cada turno, qué reglas se retiraron, qué queda y por qué. Actualiza `documentacion/SEMANTICA.md`.
Todo commiteado y pusheado.

## Cómo trabajar

- Commits chicos, uno por cambio, con la cifra de DEV-B y el balance de reglas en el mensaje. Estado escrito en
  `COMPRENSION_PROGRESO.md` a medida que avanzas.
- Subagentes: para escribir conjuntos y oro (sin acceso al código), revisar y explorar sólo-lectura. El diseño, la
  integración y el cierre son tuyos.
- Decisiones sin el dueño: lo sellado; si no alcanza, la práctica establecida; entre dos, la más reversible y la que
  nunca afirma algo que no ocurrió. Cada una en `DECISIONES_COMPRENSION_2026-09-25.md`.
- Al dueño, cifras y no narrativa, al cerrar F1, F2, F3 y F6. Sólo le preguntas lo marcado **PREGUNTAR**.

Empieza por F0 y F1. No toques `src` hasta que la base de F1 esté medida y commiteada.
