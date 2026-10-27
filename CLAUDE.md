# CLAUDE.md

Las instrucciones de agente de este repositorio son [`AGENTS.md`](AGENTS.md). **Léelo
entero.** No se duplican aquí para que las dos no diverjan.

Diferencias si estás en Claude Code y no en Grok: el esfuerzo lo fija el harness (no
hay `/effort`), una confirmación de permisos es del harness y no una duda que resolver
preguntando, y las tools se llaman `Grep`, `Read`, `Edit` y `Bash`.

## Lo que Claude Code tiene además en `.claude/`

Adaptado de everything-claude-code; inventario, descartes y cómo revertirlo en
[`.claude/README.md`](.claude/README.md). `AGENTS.md` sigue mandando.

- Skills: `verificar` (la escalera con los comandos de esta máquina; `py` está roto, se
  usa el Python del runtime), `arreglar-fallo`, `arreglar-build`, `traspaso`.
- Agentes revisores y `explorador`, en `sonnet` y de sólo lectura. Por defecto no se
  delega: se usan cuando el dueño lo pide o con `/revisar-cambio`.
- Una guarda (`.claude/hooks/baxy_guard.py`) deniega `--no-verify`, `git stash`,
  `reset --hard`, `clean -f`, `push --force` y tocar servicios o arranque de Windows, y
  avisa si `AGENTS.md` pasa de 10.000 caracteres. Si deniega algo que de verdad hace
  falta, no lo esquives: díselo al dueño.
