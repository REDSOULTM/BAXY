# Configuración de Claude Code para BAXY

Ayudas de Claude Code hechas para BAXY y sólo para BAXY: cada pieza sale de `AGENTS.md`,
`documentacion/00_IDENTIDAD.md` o de un fallo real de este proyecto. Nada de esto toca el producto; sólo
cambia cómo trabaja Claude Code en este repositorio. `AGENTS.md` sigue mandando.

## Qué hay

| Tipo | Nombre | Para qué |
|---|---|---|
| skill | `verificar` | la escalera de validación con los comandos reales de esta máquina |
| skill | `arreglar-fallo` | prueba que falla → arreglo mínimo en la pieza dueña → verificar |
| skill | `arreglar-build` | build verde sin callar avisos ni relajar reglas |
| skill | `traspaso` | dejar o retomar el handoff con `docs/AI_HANDOFF_TEMPLATE.md` |
| comando | `/revisar-cambio` | los agentes revisores en paralelo, sólo si el dueño lo pide |
| comando | `/limpiar-muerto` | ley 5, sin descargar herramientas |
| agente | `revisor-codigo` | los invariantes y las leyes sobre un diff de Python, C# o FieldUi |
| agente | `revisor-privacidad` | que no salga nada de la persona, efectos sin autorizar, rutas, procesos |
| agente | `cazador-fallos-silenciosos` | errores que acaban en un «Listo» falso |
| agente | `analizador-pruebas` | ¿hay una prueba que fallaría sin el cambio? |
| agente | `explorador` | la exploración de sólo lectura que `AGENTS.md` permite delegar |
| regla | `rules/python.md`, `csharp.md`, `fieldui.md` | se cargan sólo al tocar esos ficheros |
| hook | `hooks/baxy_guard.py` + `settings.json` | ver «La guarda» |

Los agentes leen y no editan, corren en `sonnet` y por defecto no se usan: `AGENTS.md` dice que no se
delega salvo exploración acotada, así que entran cuando el dueño lo pide o con `/revisar-cambio`.

## La guarda

Un solo script en Python con librería estándar (sirve el Python del sistema; `py` no hace falta):

- **Antes de un comando** (`Bash|PowerShell`) deniega `--no-verify`/`--no-gpg-sign`, `git stash` (salvo
  `list`/`show`), `git reset --hard`, `git clean -f`, `git push --force`, `git checkout .`/`git restore .`
  —en esta máquina varias sesiones comparten worktree— y msconfig, `bcdedit`, `sc config|delete|stop`,
  `Set-Service`, `Stop-Service`, `reg add|delete|import HKLM` (incidente msconfig: 256 servicios).
- **Después de editar** avisa a Claude, sin bloquear, si `AGENTS.md` pasa de 10.000 caracteres o si se
  toca configuración de calidad (`ruff.toml`, `pytest.ini`, `Directory.*.props`, `global.json`,
  `eslint.config.js`, `tsconfig*.json`…).

Límites: es una red, no una frontera. Busca texto en el comando, así que hay falsos positivos (un
`--no-verify` dentro de un mensaje) y no ve lo que haga un script por dentro. No usa red, no escribe
ficheros, no lee prompts. Si Python no está en el `PATH`, Claude Code sigue sin ella. Si deniega algo que
de verdad hace falta, el dueño lo ejecuta él (prefijo `!`) o lanza Claude Code con `BAXY_GUARD=off`.

## Cómo probarlo

```powershell
# Debe imprimir un JSON con "deny"
'{"tool_input":{"command":"git stash"}}' | python .claude\hooks\baxy_guard.py pre-shell
```

En una sesión: `/agents` lista los cinco agentes; `/revisar-cambio HEAD~1..HEAD` lanza la revisión.

## Cómo quitarlo

Todo vive en `.claude/`, en las líneas de `.gitignore` y en la sección de `CLAUDE.md`: revertir sus
commits lo quita entero. Nada se instala a nivel usuario (`~/.claude`).
