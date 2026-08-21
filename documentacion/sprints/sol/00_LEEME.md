# Archivo — los goals 01–04, versión GPT-5.6 Sol

**No se lanzan.** Los que están en uso son los de la carpeta de arriba, reescritos
para **Grok 4.6**. Estos cuatro son la primera versión, escrita para **GPT-5.6 Sol**
a `reasoning.effort: high`, y se conservan por dos razones: llevan dentro la misma
evidencia heredada, y documentan por dónde pasó el proyecto.

Hubo una versión intermedia para **Claude Opus 5** en Claude Code. No sobrevive como
carpeta: sus goals son los de arriba, con el bloque por modelo sustituido.

## Qué cambia de una versión a otra

El **contenido no cambia**: mismo objetivo, misma evidencia heredada, mismos
criterios de cierre. Cambia un bloque, y por estas razones:

**1. El mando del esfuerzo.** Sol se pilota con `reasoning.effort`. En Claude Code
eso no existe —el harness lo fija— y por eso la versión de Opus lo quitó. En Grok
vuelve a existir, como `/effort`, así que la línea de Sol es válida otra vez: `high`
de suelo, `xhigh` sólo en el tramo que lo pida.

**2. Las herramientas y la shell.** Es lo que más cambia, y lo que estaba mal
escrito hasta que se midió: en esta máquina la shell de Grok es **PowerShell** y
**`rg` no existe**. Se busca con la tool `grep` y se lee por rango con `read_file`;
la shell queda para git, pytest, dotnet y procesos. Detalle en
[`docs/AUDITORIA_GROK_2026-08-21.md`](../../../docs/AUDITORIA_GROK_2026-08-21.md).

**3. Las tendencias del modelo.** Los goals de Opus llevaban un bloque de cuatro
correcciones —verificaba de más, ampliaba el encargo, delegaba demasiado, escribía
largo—. **El equivalente para Grok no está escrito porque no está medido**, y buena
parte no haría falta: su prompt de sistema ya le ordena de fábrica no ampliar el
encargo y no afirmar nada que la salida de una herramienta no sostenga.

**4. Dónde vive el estado.** No cambia entre modelos, pero hay que decirlo siempre:
escrito en el repositorio a medida que avanzas, no en la conversación. Las sesiones
largas se compactan.
