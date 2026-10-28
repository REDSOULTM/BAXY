# Cómo trabaja Claude en BAXY

Destilado de los mensajes del dueño en las sesiones del PC y del notebook (septiembre y octubre de 2026):
lo que más veces tuvo que repetir o corregir. `AGENTS.md`, `documentacion/00_IDENTIDAD.md` y el goal de la
sesión mandan sobre esto.

## Autonomía

- Las decisiones de producto se toman leyendo `00_IDENTIDAD.md`, `AGENTS.md` y lo medido; no se le pasan al
  dueño como preguntas. Sólo se le pregunta lo que la identidad de verdad no cubre.
- Se confirma únicamente lo destructivo o peligroso. Si algo espera su sí, se dice en el mensaje y se sigue
  con otra cosa: nunca una pregunta bloqueante mientras quede trabajo.
- Nada de esperar mano sobre mano: mientras corre un banco o un build, se investiga, se prepara lo siguiente
  o se da trabajo a la otra máquina. Si el dueño pide paralelismo, se usan subagentes sin pedir permiso;
  si no, vale el criterio de `AGENTS.md`.

## Velocidad y jueces

- Rondas cortas: ningún paso de medición pasa de 5 minutos. Un banco se parte en tandas pequeñas, se reporta por
  tanda y se reparte entre máquinas. El 4B responde en segundos: lo que tarde más se parte o se paraleliza.
- El juez es Claude: subagentes (Opus) que leen a ciegas con el criterio escrito, varios en paralelo. No se monta un
  LLM juez local que ocupa gigas de VRAM: la GPU es para el modelo de BAXY. Base y candidato se juzgan con el mismo
  juez del día; si se comparan con cifras del juez viejo, se dice.
- Subagentes en paralelo para juzgar, revisar y probar siempre que el trabajo sea independiente; mensajes concisos.

## Sin capa semántica: se ayuda al modelo

- BAXY es un arnés para el modelo: el modelo entiende y decide. Nada de lectores, patrones, listas de palabras ni regex
  de intención que decidan por él.
- Se le ayuda con herramientas que funcionan y se verifican, descripciones claras, datos tipados y resultados
  honestos. Lo determinista sólo compara forma (un argumento que no se dijo) y le devuelve el dato.
- Cada arreglo se prueba con frases held-out que no nombra, escritas por un subagente que no vio el diff.

## Trabajo en flota (plazos largos)

- El PC y el notebook trabajan a la vez, en rondas: un líder por ronda, trabajadores en worktrees propios y
  subagentes. El PC integra y mide; el notebook prueba en vivo y despliega en su BAXY instalada, con vuelta atrás.
- Una ronda: medir en tandas, agrupar los fallos por causa, arreglar con prueba que falla primero, integrar con la
  regla de corte (lo que baja una cifra sale), desplegar y escribir el estado. Al terminar, la siguiente.

## Verdad y calidad

- Nunca «listo» sin evidencia fresca: el comando y su resultado, o la captura del estado real en la app.
  Lo que no se pudo verificar se dice.
- Soluciones reales y generales: la causa, no el síntoma; nada de parches ni de código que nombre una app.
- Las decisiones se respaldan con fuentes (documentación, papers, reportes de usuarios) o con una medición,
  no con memoria.
- Antes de rehacer algo, se busca en el repo, en `git log`, en el archivo histórico y en la memoria: muchas
  veces ya se midió.
- Cuando el encargo es estabilizar, se toca lo mínimo indispensable.

## Contexto que no se pierde

- El estado se escribe en el repo a medida que se avanza (handoff o `PROGRESO`), no al final.
- Tras compactar o retomar, el hook de contexto inyecta los mensajes del dueño de la sesión; si un detalle
  importa, se lee el fichero completo que indica.
- Los mensajes del dueño suelen venir dictados por voz: un nombre mal transcrito (BAXY escrito de otra forma,
  un término técnico deformado) se interpreta por el contexto.

## Máquinas, ramas y procesos

- Se sabe siempre en qué máquina, worktree y rama se está (el hook lo dice al arrancar) antes de tocar nada.
- Push sólo a `hub`; a GitHub (`origin`) únicamente si el dueño lo pide. Nada se fusiona en las ramas que
  integran (`main`, `baxy-renew`, `pc-cu` o la del goal) sin su «adelante». Antes de un push, el diff pasa
  por el chequeo de privacidad del PC (skill `coordinar-pc-nb`).
- Los procesos se cierran por PID, nunca por nombre: matar por nombre ya cerró VS Code y la propia sesión.
  Lo que una prueba abre, la prueba lo cierra.
- No se reinicia ni se apaga ninguna máquina.

## Cómo se informa

- En español claro, con cifras y sin jerga: qué se hizo, qué falta y cuánto queda, en una tabla antes y
  después cuando hay medición.
