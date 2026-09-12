# 1008 — apertura con referente ausente

Base: `04ae6daa2c28cf711eaca78b77affd7126bcd67e`.
Worktree: `C:/Users/usuario/AppData/Local/BAXY/C03-deictic1008-worktree`, rama `codex/c03-deictic1008`.
Fuente única: `src/baxy_mind/__main__.py`. Herencia: diagnóstico1006, SHA6894fc54d9ccc91236464fea5f1e1d473b48cc6e1c91058a931ee5b4a9141be5.

El problema observado es explicit_conversation/unsupported antes de las etapas del selector en H0216 y dev01. La rama de catálogo admite abrir+operando como posible juego y puede concluir falta de identidad cuando el operando es sólo una referencia; el aclarador existente tenía formas demasiado estrechas.

La propuesta comparte reconocimiento de apertura positiva y referente completo entre catálogo y aclaración. Reutiliza `_application_open_request`, las guardas de deseo positivo, no acción y cláusula única. Pronombres/clíticos no se convierten en nombres de aplicación; se retiran las dos ramas de apertura inline que este lector sustituye. Una referencia relativa acotada admite verbos de mencionar/indicar sin permitir un nombre añadido.
El bloque temprano de aclaración ya existente llama `clarify_missing_referent`, conserva su presupuesto CPU/GPU y valida la pregunta. Devuelve cero intentOperations/effectOperations y ningún resultado de provider antes de inferir ausencia. No hay texto visible fijo.

Si hay un usuario previo o aclaración pendiente, no se hace esa aclaración sin contexto. Se conserva la ruta contextual existente; la clasificación estable y el aclarador tardío reciben historia para no imponer que falte un referente. Un turno previo no se considera prueba de identidad: sólo evita afirmar ausencia de contexto y deja la resolución a los mecanismos actuales. No se añade un resolvedor de anáforas.
La clausura de catálogo omite sólo esta forma pronominal positiva. Nombres literales desconocidos conservan su ruta; tampoco se altera una app autenticada. Prohibición, cita, pasado/futuro, condición, cláusulas alternativas o múltiples y nombres añadidos no reciben la nueva salida temprana.

Alcance por lectura: H0216/H0531/H0534/H0619 y las variantes de apertura dev01/dev02. No promete corregir símbolos, números, temperatura, selección habitual ni SIEMPRE. Sin crédito ni resultado funcional supuesto.
Revisión manual de los callers, guardas, contexto, diff y `git diff --check`. No tests, imports, AST, build, GPU ni producto ejecutados por instrucción explícita del dueño. Raíz debe revisar/adoptar y medir el panel dirigido.
