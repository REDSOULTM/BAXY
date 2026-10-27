# CLAUDE.md

Las instrucciones de agente de este repositorio son [`AGENTS.md`](AGENTS.md). **Léelo
entero.** No se duplican aquí para que las dos no diverjan.

Diferencias si estás en Claude Code y no en Grok: el esfuerzo lo fija el harness (no
hay `/effort`), una confirmación de permisos es del harness y no una duda que resolver
preguntando, y las tools se llaman `Grep`, `Read`, `Edit` y `Bash`.

## Lo que Claude Code tiene además en `.claude/`

Inventario, origen de cada pieza y cómo quitarla en [`.claude/README.md`](.claude/README.md).
`AGENTS.md` sigue mandando.

- `.claude/rules/trabajo.md` se carga siempre: es la forma de trabajar que el dueño fija.
- Al arrancar, un hook dice fecha, máquina, worktree y rama; tras compactar o retomar,
  reinyecta los mensajes del dueño de la sesión y deja la lista entera en
  `.claude/sesiones/` (local, privada).
- Skills: `verificar`, `arreglar-fallo`, `arreglar-build`, `traspaso`, `prueba-en-vivo`,
  `coordinar-pc-nb`, `lanzar-baxy`, `verification-before-completion`,
  `systematic-debugging`. Plugins oficiales: `pr-review-toolkit`, `claude-md-management`,
  `project-artifact`.
- Una guarda (`.claude/hooks/baxy_guard.py`) deniega lo que ya rompió algo (saltarse
  hooks, `git stash`, `reset --hard`, push a GitHub, matar procesos por nombre, tocar
  servicios de Windows, reiniciar). Si deniega algo que de verdad hace falta, no lo
  esquives: díselo al dueño.
