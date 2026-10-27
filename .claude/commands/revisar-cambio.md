---
description: Revisión de un cambio de BAXY con los agentes revisores, en paralelo y sólo los que el diff necesita. Uso /revisar-cambio [rango git o rama] [--foco=codigo|privacidad|fallos|pruebas].
argument-hint: "[rango git o rama] [--foco=…]"
---

Revisa el cambio indicado en `$ARGUMENTS` (por defecto, lo no confirmado más los commits de la rama
actual que no están en su rama base). El dueño lo ha pedido: es la excepción a «subagentes por defecto,
no» de `AGENTS.md`.

1. Saca el alcance: `git diff --stat <rango>` y la lista de ficheros. Sin diff, dilo y para.
2. Lanza **en paralelo**, cada uno con el rango exacto y sus ficheros, sólo los que hagan falta:
   - siempre `revisor-codigo`;
   - red, providers, confirmación, persistencia, rutas o procesos → `revisor-privacidad`;
   - manejo de errores, verificación o estados terminales → `cazador-fallos-silenciosos`;
   - conducta nueva o arreglada, o pruebas tocadas → `analizador-pruebas`.
   Con `--foco`, sólo ése.
3. Espera a todos. Junta, quita duplicados y **comprueba tú cada hallazgo CRÍTICO o ALTO** leyendo la
   línea citada: los agentes dan segundas opiniones, no veredictos.
4. Informe en español por severidad, cada hallazgo con `ruta:línea`, fallo concreto y arreglo. Un informe
   sin hallazgos es válido. No arregles nada salvo que el dueño lo pida.
