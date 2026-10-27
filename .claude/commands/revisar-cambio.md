---
description: Revisión multiperspectiva de un cambio de BAXY con los agentes revisores, en paralelo, sólo los que el diff necesita. Uso /revisar-cambio [rango git o rama] [--foco=codigo|pruebas|fallos|tipos|privacidad].
argument-hint: "[rango git o rama] [--foco=…]"
---

<!-- Adaptado de commands/review-pr.md de everything-claude-code (MIT) 25278e7d7. -->

Revisa el cambio indicado en `$ARGUMENTS` (por defecto, lo no confirmado más los commits de la rama
actual que no están en su rama base). El dueño lo ha pedido explícitamente: es la excepción a «subagentes
por defecto, no» de `AGENTS.md`.

1. Saca el alcance: `git diff --stat <rango>` y la lista de ficheros. Sin diff, dilo y para.
2. Elige sólo los agentes que el diff necesita y lánzalos **en paralelo**, cada uno con el rango exacto y
   la lista de sus ficheros:
   - siempre `revisor-codigo`;
   - `.py` → `revisor-python`; `.cs` → `revisor-csharp`; `.ts`/`.tsx` de `src/Baxy.FieldUi` → `revisor-fieldui`;
   - manejo de errores, verificación o estados terminales → `cazador-fallos-silenciosos`;
   - pruebas tocadas o conducta nueva → `analizador-pruebas`;
   - `src/Baxy.Contracts` o el catálogo → `analizador-tipos`;
   - red, providers, confirmación, persistencia, rutas o procesos → `revisor-privacidad`.
   Con `--foco`, sólo el agente de ese foco.
3. Espera a todos. Junta, quita duplicados y **comprueba tú cada hallazgo HIGH o CRITICAL** leyendo la
   línea citada: los informes de agentes son segundas opiniones, no veredictos.
4. Informe en español por severidad, cada hallazgo con `ruta:línea`, fallo concreto y arreglo. Un informe
   sin hallazgos es válido. No arregles nada salvo que el dueño lo pida.
