---
name: traspaso
description: Deja o retoma el handoff de una sesión larga de BAXY con la plantilla docs/AI_HANDOFF_TEMPLATE.md (una página, rutas y comandos con resultado exacto). Úsala al cerrar una sesión larga, antes de agotar el contexto, o para continuar la de otra sesión.
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

## Retomarlo

1. Lee el `HANDOFF.md` entero y `git log --oneline -10` de la rama que nombra.
2. Comprueba que el commit del título existe y que el árbol está donde dice (`git status --short --branch`).
3. Las decisiones tomadas no se reabren sin dato nuevo. Empieza por la «Siguiente acción recomendada».
4. Si algo del handoff ya no es cierto, corrígelo en el mismo fichero antes de seguir.
