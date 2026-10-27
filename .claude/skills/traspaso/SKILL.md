---
name: traspaso
description: Deja o retoma el handoff de una sesión larga de BAXY con la plantilla docs/AI_HANDOFF_TEMPLATE.md, y escribe el prompt de continuación (o el /goal) para una sesión nueva o para la otra máquina. Úsala al cerrar una sesión larga, antes de agotar el contexto, para continuar la de otra sesión, o cuando el dueño pida un prompt o un goal.
---

# Traspaso entre sesiones

El estado se deja **en el repositorio**, no en `~/.claude`,
porque `AGENTS.md` lo exige y porque otra máquina (el PC o el notebook) tiene que poder leerlo.

## Dejarlo

1. Lee `docs/AI_HANDOFF_TEMPLATE.md` y síguela al pie de la letra: una página como mucho, rutas concretas,
   comandos con su resultado exacto, nada de narrar la conversación, nada que se deduzca del diff.
2. Lo más valioso son las **hipótesis descartadas** y por qué murieron.
3. Escríbelo en `artifacts/<goal>/HANDOFF.md` (o donde diga tu goal) **a medida que avanzas**, no al final.
4. Si el dueño lo pide, haz commit con el resto del trabajo; si no, déjalo sin confirmar y dilo.

## Prompt para la sesión siguiente o la otra máquina

Cuando el dueño pide un prompt o un goal para una sesión nueva (o uno para el PC y otro para el notebook):

1. Primero el `HANDOFF.md` o el goal completo en un fichero del repo; el prompt **apunta** a ese fichero.
   `/goal` no acepta más de 4.000 caracteres: si no cabe, el prompt dice «lee <ruta> y cúmplelo» y poco más.
2. Secciones, siempre en este orden: misión en una frase; dónde estás (máquina, worktree, rama, commit);
   qué leer primero (`AGENTS.md`, `00_IDENTIDAD.md`, el handoff); precedencia si algo choca; forma de trabajo
   (autonomía, no esperar, buzón con la otra máquina); **ya hecho, no repetir** (commits, ramas, sha256 de lo
   sellado, decisiones cerradas); qué hacer al final de cada turno; criterios de término medibles.
3. Un bloque por máquina, listo para copiar, y avisa de que cada uno se pega en **una** sesión: el mismo
   prompt en varias sesiones a la vez las pone a pelear por el mismo trabajo.
4. Nada literal de los pedidos del dueño si el prompt se va a versionar (regla de privacidad).

## Retomarlo

1. Lee el `HANDOFF.md` entero y `git log --oneline -10` de la rama que nombra.
2. Comprueba que el commit del título existe y que el árbol está donde dice (`git status --short --branch`).
3. Las decisiones tomadas no se reabren sin dato nuevo. Empieza por la «Siguiente acción recomendada».
4. Si algo del handoff ya no es cierto, corrígelo en el mismo fichero antes de seguir.
