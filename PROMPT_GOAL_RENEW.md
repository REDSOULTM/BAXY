<mision>
Terminas BAXY Renew: el asistente personal del dueño en su PC con Windows, al estilo de OpenClaw pero dentro de
4 GB de VRAM. BAXY Renew es el modelo puro (Qwen3.5-4B Q4_K_M en llama.cpp), las herramientas y el ecosistema de BAXY, y
nada más.

- **Cómo se construye:** el modelo decide todo en un bucle nativo de herramientas. El código queda limpio y sin trucos
  para el modelo. A la vez, todo (prompt, descripciones o skills, protocolo, inferencia) se optimiza al máximo para
  Qwen3.5-4B.
- **Para qué:** el dueño lo entrega pronto, y quiere saber de verdad cuánto da el modelo con un buen arnés. Por eso
  cada límite del modelo se documenta en vez de esconderse con código.
</mision>

<donde_estas>
- **Worktree y rama:** `C:\Users\usuario\Desktop\ETC\Programacion\BAXY-Renew`, rama `baxy-renew`. Los commits son
  locales; no hay push ni fusión a main, porque la rama queda aparte por decisión del dueño.
- **Primera lectura:** lee entero `RENEW_TRASPASO.md`, en la raíz del worktree. Es la fuente de verdad: la misión, dos
  rondas de decisiones del dueño, cómo es Renew hoy, el orden de trabajo, las metas y las trampas del entorno.
- **Lee también, enteros, `AGENTS.md` y `documentacion/00_IDENTIDAD.md`:**
  - `00_IDENTIDAD.md` es qué es BAXY para el dueño: un compañero tipo Jarvis, cómo habla, honestidad, confirmación,
    velocidad, memoria y privacidad, modularidad, y las tres pruebas que justifican el producto. El BAXY que entregas
    tiene que ser ése.
  - `AGENTS.md` sirve para orientarte (mapa, hechos de esta máquina, búsqueda, subagentes). Lo escribieron para BAXY
    Definitivo: tú estás en el worktree de Renew, y su escalera de validación la reemplazan aquí las pruebas del
    contrato y los bancos.
- **Precedencia, de mayor a menor:**
  1. este prompt;
  2. las decisiones del dueño del 2026-10-15 en `RENEW_TRASPASO.md`;
  3. `00_IDENTIDAD.md`;
  4. el resto de `documentacion/`, que es evidencia, no instrucción.
- **Choques ya resueltos por el dueño:**
  - Identidad: «nunca actúa sin que se lo pidan». Ahora el latido actúa por instinto en lo de bajo riesgo. Lo de alto
    riesgo lo propone y espera el «sí».
  - Identidad: «habla siempre». Ahora los avisos del latido se adaptan a lo que hace el dueño: habla si está libre, y
    sólo notifica si juega, está en llamada o viendo algo. La respuesta a un pedido suyo se sigue diciendo en voz alta.

  Si encuentras otro choque, anótalo en `PROGRESO.md` con tu decisión y sigue. Si de verdad es una decisión del dueño,
  pregúntale con opciones.
- **De la identidad, en especial:**
  - ninguna afirmación sin verificar;
  - un aviso que no afirma resultado si el turno va a pasar de 3 s en silencio;
  - nada del dueño sale de la máquina (la web puede entrar, sus datos no salen);
  - nunca hace click ni escribe en la ventana de la persona;
  - cero código muerto y nada apilado;
  - máxima cobertura con el mínimo de herramientas;
  - la personalidad vive en el prompt.

  El holdout cubre las tres pruebas del producto: abrir un juego y llegar adentro, manejar el PC sin tocarlo y
  entenderle a la primera.
- **Más evidencia:** la transcripción del chat anterior (ruta en la nota) y las memorias del proyecto, en especial
  `c03-computer-use-engine`. Úsalas para no redescubrir lo ya aprendido.
</donde_estas>

<alcance>
Se mide y optimiza **el arnés**: el modelo, el prompt del sistema, las descripciones o skills, el protocolo, el bucle,
la inferencia y las herramientas de BAXY (voz que habla, computer use, latido y herramientas de agente incluidas).

**Fuera del alcance:**

- **La wake word k4 y la transcripción Parakeet Ultra:** ya están conectadas (commit `6eba9dfb`) y son piezas fijas.
  No se miden, no se ajustan y no se cambian, y sus errores no cuentan contra ninguna meta. Los bancos le entran al
  arnés como texto, como si la transcripción ya estuviera hecha.
- **Piper:** se porta tal cual desde BAXY Definitivo; no se comparan voces.
</alcance>

<reglas>
1. **Sin ayudas al modelo en código:** nada de regex, reglas semánticas, guardias, vetos, listas de palabras ni pasos
   dictados. Un parche así esconde el límite real del modelo y se rompe con la siguiente frase distinta. Se quedan el
   catálogo tipado, el kernel (riesgo y confirmación), el journal, la verificación del proveedor y el enmascarado de
   datos sensibles: son la honestidad de BAXY, no ayudas a entender.
2. **Las mejoras vienen sólo de** la presentación (prompt, descripciones, skills, formato), el protocolo y la
   inferencia.
3. **Honestidad:** BAXY nunca da por hecho algo que no se ejecutó y verificó. Lo que no puede hacer, lo dice. Si una
   meta no se alcanza por el límite del modelo, documenta el límite con su evidencia y sigue.
4. **Investiga antes de implementar:** papers, documentación oficial y experiencia de usuarios. Cita la fuente en el
   commit o en las notas. Es la regla vital del dueño: nada se improvisa.
5. **Recursos:** cabe en ≤ 4 GB de VRAM y ≤ 4 GB de RAM.
</reglas>

<orden_de_trabajo>
- **Primero, el marco** (antes de ajustar nada):
  1. Crea los ficheros de estado (ver `<estado>`).
  2. **Reutiliza los bancos que ya existen** antes de escribir uno. Ninguno de estos se usó para ajustar Renew, así
     que sirven de holdout si los sellas ahora (sha256 y fecha en `metas.json`) y no los abres mientras ajustas:
     - En BAXY Definitivo:
       - las 84 corridas `artifacts/comprobaciones/C03/cien-*`, con su oráculo de antes y después;
       - los pedidos reales del dueño en `tests/data/historical_missions.jsonl`;
       - el holdout público `tests/data/turn_evidence_public_holdout.v1.jsonl`, derivado de MASSIVE;
       - las mediciones de `documentacion/computer-use/`.
     - En `F:\BAXYeval`: los dos holdouts sellados del torneo, de 40 y 50 casos.

     El holdout de 60 de `renew_bench` ya se usó y no vale. Escribe sólo lo que falte, como el banco de escenas del
     instinto, y séllalo antes de ajustar.
  3. Deja un `scripts/renew_check.ps1` que lance los bancos y mida VRAM, RAM y latencia en un solo paso.
- **Después,** el orden de «Lo primero para el chat nuevo» en la nota: las falsedades, la ronda 1, la voz que habla,
  computer use, las herramientas de agente y el latido, la re-auditoría y las optimizaciones.
- **Avance incremental:** cierra y mide una pieza antes de abrir la siguiente.
</orden_de_trabajo>

<criterios_de_termino>
El goal termina cuando todo esto está medido y anotado en `artifacts/renew/metas.json`, con su evidencia:

- **Holdout nuevo y sellado:** ≥ 85 % de aciertos. Cubre las herramientas de siempre, la voz que habla, computer use,
  las herramientas de agente y el latido.
- **Falsedades:** cero en el banco automático. Cada turno se compara con el journal: nada contado como hecho sin
  ejecución verificada.
- **Instinto:** ≥ 80 % de aciertos en el banco de escenas, cero acciones de riesgo hechas solas y como máximo una
  acción molesta cada 20 escenas.
- **Velocidad (p50):**
  - La decisión, en ≤ 1 s.
  - Desde que el texto de una orden llega a la mente hasta que Piper empieza a sonar, ≤ 2,5 s.
- **Recursos:** ≤ 4 GB de VRAM y ≤ 4 GB de RAM para el arnés (llama-server y la mente, sin contar k4 ni Ultra), medidos
  con todo cargado. Anota también el total con la voz.
- **Ronda final:** una ronda de agentes de auditoría que no encuentra nada que viole `<reglas>`.

Una meta que el modelo no alcanza tras investigar y medir se cierra como límite honesto con su evidencia. No se
parchea con código.
</criterios_de_termino>

<forma_de_trabajo>
- **Rapidez:** el tiempo importa. No gastes tiempo que se pueda evitar; cuanto antes llegue un resultado correcto,
  mejor.
  - Lanza en paralelo las llamadas independientes.
  - Usa subagentes con libertad cuando el trabajo se pueda repartir: investigación, auditorías, bancos y piezas que no
    comparten estado. El dueño paga el plan de 200 dólares para eso, así que lanza todos los que acorten el camino.
  - Trabaja directo en lo simple o secuencial, como un grep o una edición de un archivo.
- **Decide y sigue:** elige un enfoque y llévalo hasta el final. Cambia sólo si aparece información nueva que lo
  contradiga.
- **Antes de opinar sobre código, ábrelo:** nunca especules sobre código que no hayas leído.
- **Cambios mínimos y generales:** sin abstracciones, archivos ni flexibilidad que nadie pidió.
  - Una solución sirve para cualquier frase del dueño, no sólo para los casos del banco. El banco verifica, no define
    la solución.
  - Si un caso del banco está mal, dilo en vez de rodearlo.
  - Borra los temporales al terminar.
- **Informa tal cual:** si algo falla, muestra la salida; si un paso se saltó, dilo.
</forma_de_trabajo>

<estado>
- **Notas libres:** `artifacts/renew/PROGRESO.md`, con qué se hizo, qué se midió, qué sigue y por qué.
- **Estado estructurado:** `artifacts/renew/metas.json`, con cada meta y cada tarea, su estado (`pendiente`,
  `en_curso`, `cumplida`, `limite_honesto`) y su evidencia.
- **Git:** un commit pequeño por pieza cerrada y medida, en `baxy-renew`.
- **Compactación:** tu contexto se compacta solo al acercarse al límite, así que no cortes una tarea antes de tiempo
  por falta de tokens. Antes de que se compacte, guarda el progreso en los dos ficheros y en un commit.
- **Al empezar cada ventana de contexto:** lee `PROGRESO.md`, `metas.json` y `git log`, y sigue por la primera tarea
  abierta.
- **Si se acaba el uso del plan:** el límite se repone 5 horas después de empezar a gastarlo, y el dueño no quiere que
  el goal se quede parado esperando.
  - Al empezar la sesión, crea con `CronCreate` un recordatorio cada hora, con `recurring: true` y en un minuto que no
    sea :00 ni :30. Su texto: «Si el goal de BAXY Renew está detenido, lee `PROGRESO.md` y `metas.json` y sigue con la
    primera tarea abierta. Si ya se cumplieron los criterios de término, borra este recordatorio.»
  - Sólo se dispara cuando estás detenido, así que no estorba mientras trabajas.
  - Vive sólo en esta sesión y caduca a los 7 días: si la sesión se reinicia o pasan 7 días, vuelve a crearlo
    (compruébalo con `CronList`).
  - Antes de que se acabe el uso, deja el estado guardado y en un commit.
</estado>

<autonomia_y_seguridad>
- **Acciones locales y reversibles** en el worktree: hazlas sin preguntar. Esto incluye editar, compilar, medir y
  hacer commits.
- **Pregunta al dueño, con casillas de opciones (AskUserQuestion),** sólo ante una decisión que de verdad es suya.
  Mientras tanto, sigue con lo que no dependa de su respuesta.
- **No toques:**
  - el worktree principal de BAXY Definitivo;
  - el manifiesto `%LOCALAPPDATA%\BAXYRuntime\mind-runtime-v1.json`;
  - los modelos de wake word y de transcripción.

  En el Python compartido del runtime instala sólo lo imprescindible, y anótalo en `PROGRESO.md`.
- **El dueño usa este PC.** Las sondas de computer use y las que abren apps corren sólo con el PC desocupado (la
  lección `idle_gate` está en la memoria), y nunca hay dos instancias del producto a la vez.
- **Acciones que piden confirmación del dueño:** borrar fuera del worktree, cerrar sus apps o enviar algo a un
  servicio externo.
</autonomia_y_seguridad>

<fin_de_turno>
Esta es una indicación permanente del dueño sobre cómo terminan tus turnos. Un mensaje sin llamada a herramienta
termina el turno, y el trabajo se detiene hasta que alguien te pida seguir. El dueño no quiere ninguna de estas cuatro
paradas mientras quede trabajo pendiente:

1. Un resumen que anuncia el siguiente paso y no lo empieza.
2. Una oferta de seguir «si prefieres».
3. Una lista de decisiones que, según tú mismo, no bloquean el resto.
4. Parar porque el turno fue largo o porque se cerró un hito.

Las notas de estado, en español, cortas y claras (qué hiciste, qué mediste, qué sigue), van en el mismo mensaje que tu
siguiente llamada a herramienta. Las únicas paradas que el dueño sí quiere son dos: cuando nada puede avanzar sin él, y
cuando se cumplen los `<criterios_de_termino>`. Esto no quita la confirmación para acciones de riesgo o destructivas.
</fin_de_turno>
