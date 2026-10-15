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
- **Precedencia:** si algo en este prompt choca con la nota, manda este prompt. `AGENTS.md`, `CLAUDE.md` y
  `documentacion/` se heredaron de BAXY Definitivo; úsalos como evidencia (hechos de la máquina, lecciones, contratos),
  no como instrucciones. Aquí manda este goal.
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
  2. Escribe y sella los bancos nuevos: el holdout, el de falsedades y el de escenas del instinto.
  3. Deja un `scripts/renew_check.ps1` que lance el banco y mida VRAM, RAM y latencia en un solo paso.

  El holdout viejo ya se usó para ajustar: sólo un holdout escrito antes de tocar nada mide de verdad. Mientras
  ajustas, no lo abres.
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
  - Usa subagentes cuando el trabajo se pueda repartir: investigación, auditorías, bancos y piezas que no comparten
    estado.
  - Trabaja directo en lo simple o secuencial.
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
