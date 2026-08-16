# Los goals 01–04, versión GPT-5.6 Sol

Estos cuatro son la versión anterior, escrita para **GPT-5.6 Sol** a
`reasoning.effort: high`. Se conservan por si vuelve a haber acceso a Codex.

**Los que están en uso son los de la carpeta de arriba**, reescritos para
**Claude Opus 5** en Claude Code. Del 05 al 11 sólo existe la versión de Sol, en
la carpeta de arriba — se convertirán cuando toquen.

## Qué cambia entre las dos versiones

No es un cambio de nombre de modelo. Cambian tres cosas:

**1. La configuración.** Sol se pilota con `reasoning.effort`; en Claude Code eso
no existe — el pensamiento es adaptativo y el esfuerzo lo fija el harness. La
línea de modelo se sustituye, no se traduce.

**2. El entorno.** Claude Code pide permisos por herramienta y compacta las
sesiones largas. Los goals de Opus lo dicen: que una confirmación del harness no
es una duda que resolver preguntando, y que el estado se deja **escrito en el
repositorio** a medida que se avanza, para que una compactación no borre horas de
trabajo pensado.

**3. Los comportamientos del modelo.** Opus 5 tiene cuatro tendencias medidas que
chocan con las cinco leyes si no se nombran, y los goals de Opus llevan un bloque
que las corrige:

- **Verifica de más.** Comprueba su propio trabajo sin que se lo pidan, así que
  pedirle verificación extra la duplica. Ojo: la verificación **del producto** —que
  BAXY compruebe los efectos que afirma— no se toca; lo que sobra es que el agente
  se revise a sí mismo.
- **Amplía el encargo.** Añade pasos que nadie pidió. El bloque le dice que
  entregue el alcance pedido, que diga en una frase si cree que el encargo está
  mal, y que declare cumplido sólo lo que esté cumplido.
- **Delega demasiado.** Reparte en subagentes trabajo que resolvería él en unas
  lecturas, y eso multiplica coste y tiempo.
- **Escribe largo.** Mensajes y documentos más largos de lo necesario, y narra sus
  propias correcciones.

Ninguna de las tres afecta al *contenido* de los goals: el objetivo, la evidencia
heredada y los criterios de cierre son los mismos en las dos versiones.
