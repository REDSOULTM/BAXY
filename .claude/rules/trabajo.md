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
