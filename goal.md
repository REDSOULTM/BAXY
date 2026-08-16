# Misión BAXY

Eres el agente responsable de BAXY. Tu objetivo es entregar **BAXY perfecto**: un asistente local para Windows que se sienta como Jarvis de uso diario en un PC normal.

La persona habla o escribe cualquier cosa —español, inglés o spanglish— y BAXY lo entiende, lo hace, comprueba que pasó y lo cuenta en una frase. Desde una petición simple hasta una misión compuesta que concatena varias operaciones para lograr lo que ninguna sola puede. Todo local: sin nube, sin APIs de pago, sin enviar datos a ningún lado.

La sensación de Jarvis no viene de terminar rápido. Viene de que **nunca hay silencio muerto**, de que **nunca miente** y de que **entiende a la primera**. Esas tres son el producto.

Lee `documentacion/00_META_VIGENTE.md` entera antes de tocar nada.

---

## 1. Re-deriva la tecnología. No la heredes.

**Nada de la pila actual es un compromiso.** El modelo decisor, su tamaño, cuantización y runtime; el tool calling; el recuperador y el shortlist; el reconocedor determinista; el planner; STT, wake word, VAD y TTS; la memoria, el retrieval y el grounding; la estrategia de computer-use. Todo está en revisión permanente.

La tecnología de hoy no es la de hace seis meses. Tienes **autoridad total para reemplazar cualquier pieza por el mejor estado del arte disponible en el momento en que trabajas**, y la obligación de comprobar cuál es ese estado del arte en vez de asumirlo.

Existen repos anteriores de este proyecto. **No los portes.** Sirven como procedencia histórica, no como fuente de diseño.

Antes de adoptar cualquier pieza:

1. **Investiga el presente, no tu memoria.** Documentación oficial vigente, releases, papers y benchmarks del momento. Tu memoria está desactualizada por construcción: trátala como hipótesis, nunca como hecho.
2. **Mide en esta máquina.** Un benchmark ajeno no autoriza nada.
3. **A/B físico con el árbol congelado**, orden ABBA, artefacto publicado — **exigible sólo cuando algo va a promoverse al runtime**. Un probe exploratorio se publica como evidencia de desarrollo, con su artefacto y sus hashes, pero sin ABBA ni prerregistro sellado. Lo que nunca se aligera: no medir sobre el corpus que el componente ya posee, e instrumentar el crudo antes de cualquier veto.
4. **Publica también lo rechazado y por qué.** Un candidato descartado con mecanismo entendido vale tanto como uno promovido.
5. **Un techo obliga a cambiar de enfoque, no a seguir puliendo.** Cuando una línea deja de dar ganancias medibles, investiga la alternativa arquitectónica.

---

## 2. Lo que nunca se re-deriva

Esto es arquitectura, no tecnología. Sobrevive a cualquier reemplazo:

1. **El catálogo tipado es la única fuente de operaciones.** Texto, corpus, skills, UI, modelos y prompts no pueden agregar una operación ni elevar su autoridad. La mente propone; el kernel autoriza; el provider ejecuta.
2. **Nada se afirma sin verificar.** "Se envió el comando" no es "se completó la misión".
3. **Estados terminales honestos.** `pending` es sólo reintentable. Un efecto ambiguo no reintentable es `failed` con `effectMayHaveOccurred`, y no se replanea ni se repite a ciegas.
4. **La confirmación se liga a la invocación exacta**, no a la intención aproximada.
5. **Cero respuestas visibles fijas.** El modelo formula cada mensaje. Una constante de fallback en pantalla es un defecto de producto.
6. **Local y privado.** La persona inspecciona, corrige y borra todo lo que BAXY sabe de ella.

---

## 3. La barra

**Exactitud — cuatro cortes, cuatro oráculos ciegos que jamás se usan para ajustar:**

| Corte | Población | Barra |
|---|---|---|
| A | Catálogo autenticado, formulaciones vistas | **> 95 %** |
| B | Paráfrasis **no vistas**, es / en / spanglish | **> 90 %** |
| C | Misiones compuestas y dependientes | **> 90 %** planes completos y verificados |
| D | Población abierta real | 100 % duro (ver abajo) |

El corte D no se mide por acierto, se mide por **honestidad**, y no admite margen: 0 efectos no solicitados, 0 éxitos no verificados, 0 respuestas fijas. Cuando la petición cae fuera de lo que BAXY puede hacer: abstención o aclaración útil formulada por el modelo. Nunca una operación inventada, nunca un efecto "parecido".

El margen de A existe para no fingir un 100 %, **no para tolerar una familia rota**. Con A en 95 % sobre 169 operaciones caben hasta ocho fallos sin que el corte los detecte: un fallo sistemático de una familia entera se trata como defecto abierto aunque el porcentaje pase.

**Toda tasa se reporta partida por causa** — recuperación / decisión / vetos. Los tres tienen arreglos opuestos; un número mezclado manda el siguiente cambio al blanco equivocado.

**Latencia — el reloj es la primera señal:** acuse, inicio de habla o de acción visible en p50 ≤ 1,0 s y p95 ≤ 2,0 s. Acción simple completa y verificada p50 ≤ 2,5 s. Voz, de fin de habla a primera señal, p50 ≤ 1,5 s. Misión compuesta sin techo fijo, pero narrando un hito cada ≤ 3 s de trabajo sin salida visible. O la mejor frontera Pareto **demostrable**, con el rechazo medido y documentado.

**Hardware — DIFERIDO al producto final.** El perfil certificado GPU de 4 GB de VRAM y el perfil CPU ≤ 8 GB de RAM siguen siendo obligatorios para la entrega, pero **no se miden ahora ni bloquean**: la máquina de desarrollo tiene 16 GB de VRAM y 32 GB de RAM, así que medir aquí no demuestra nada sobre un equipo modesto. Ver `documentacion/00_ALCANCE_DESARROLLO_VS_PRODUCTO.md`.

**Voz — DIFERIDA a una fase posterior.** Wake word, STT, transcripciones y TTS se abordan **después** de refinar el backend, por decisión del responsable del producto. Durante esta fase, todo criterio que exija «por voz» se satisface **por texto**. No se mide, no se toca y no se cuenta como cerrada.

---

## 4. Lo entregable no tiene bugs

BAXY se entrega **sin bugs**. No "con defectos conocidos documentados", no "con pendientes menores", no "con un fallo heredado que ya venía de antes".

Como "no existe ningún bug" no se puede demostrar, la barra operativa es:

> **Cero defectos conocidos abiertos.** Todo defecto que una prueba, compuerta, probe, corrida física o lectura de artefacto haya sacado a la luz se cierra **arreglándolo**. No admite ninguna otra forma de cierre.

**Prohibido** cerrar un defecto bajando el umbral de la compuerta que lo detectó, marcándolo `skip`/`xfail`/omisión, moviéndolo a una lista de pendientes, reetiquetándolo como limitación ambiental, declarándolo fuera del alcance de la pasada, envolviéndolo en un fallback que lo oculta, o justificándolo porque es antiguo, ajeno o caro. **Un fallo heredado sigue siendo un fallo del entregable.**

**Bug frente a limitación ambiental** — es el único hueco por donde se escapa un entregable roto, así que es estricto. Ambiental es sólo aquello cuya causa está **fuera del código de BAXY** y BAXY no puede reparar: no hay GPU, no hay micrófono, el certificado de firma no está comprado, el SO no expone la API. Se nombra una por una y se cubre con un degradado honesto y medido. **Todo lo demás es bug**, incluido lo que viva en el contrato, el prompt, el corpus, el modelo elegido o la configuración. Difícil, caro o viejo no lo vuelve ambiental.

Re-audita una por una las omisiones ambientales existentes bajo esta definición. Las que no la cumplan son bugs y se arreglan.

---

## 5. Disciplina de medición

Reglas pagadas con corridas perdidas. No son sugerencias.

1. **Nunca midas sobre el corpus que el componente ya posee.** Infla todo. El holdout es ciego, congelado y nunca se usa para ajustar.
2. **Lee los textos visibles, no sólo las decisiones contractuales.** Una decisión contractual correcta puede acompañar una respuesta inservible.
3. **Congela el árbol antes de un probe.** Editar código con una corrida en vuelo la invalida. Si hay que editar: mata la corrida, borra la telemetría parcial, relanza.
4. **Instrumenta el crudo:** qué se le ofreció al modelo y qué propuso *antes* de que cualquier veto lo toque.
5. **La igualdad exacta contra un baseline sólo aprueba variantes donde el baseline ya acertaba.** Cuando un cambio *corrige*, la puerta es un oráculo, no el modelo anterior.
6. Todo dataset y artefacto se regenera desde scripts versionados.

---

## 6. Por dónde empezar

Los defectos abiertos están inventariados en `open_work_not_yet_done` de `artifacts/fixes/integral_review_ledger_*.json` (el más reciente).

**Empieza por la deuda de corpus.** El corpus histórico congelado tiene conflictos de familia, de recordatorio/notificación y de idioma contra el catálogo autenticado. Mientras el oráculo no distinga un arreglo de un overfit, todo lo demás se arregla a ciegas. Es la lección de R21 convertida en bloqueo.

Después: el falso positivo inseguro del preflight, los vetos que retiran efectos legítimos, y los fallos de exactitud del inventario.

---

## 7. Cómo trabajas

**Autoridad total delegada.** Decide sin consultar, ejecuta, mide, publica el resultado — incluido el negativo. No pidas aprobación para avanzar, no delegues decisiones técnicas, no te detengas en el primer error. Detente sólo ante un bloqueo real: algo que no puedes obtener desde el repositorio, la máquina o la documentación pública.

**Reporta con fidelidad.** Si algo falla, dilo con su salida. Si un paso se saltó, dilo. Escribe "terminado" sólo cuando esté hecho y verificado.

**No declares la meta cumplida** hasta que, simultáneamente: cero defectos conocidos abiertos; todas las compuertas de fuente verdes; los cuatro cortes de exactitud cerrados sobre oráculos ciegos regenerables; las misiones compuestas ejecutadas end-to-end **por texto** en la máquina física, abriendo el producto y verificando efectos reales; y las únicas limitaciones restantes sean ambientales según la definición estricta, explícitas, cubiertas y nombradas una por una.

**Lo mejor para BAXY, siempre.**

Haz un recordatorio cada 5horas para seguir trabajando despues de que se te acabe el uso , empieza con el 1er recordatorio ahora a las 3am
