# Grok en BAXY — cómo se lanza, qué se configura y cómo se mide

No es lectura obligatoria. Se abre el día que se configura Grok en una máquina, o
cuando hay que comprobar si una optimización de contexto sirve de algo.

Medido en esta máquina el **2026-08-21** con **grok 1.0.5** y **grok-4.6**. La
auditoría que lo sostiene, con los números y cómo reproducirlos, está en
[`docs/AUDITORIA_GROK_2026-08-21.md`](../docs/AUDITORIA_GROK_2026-08-21.md).

Sustituye a `.codex/`, que queda archivado: el proyecto ya no se desarrolla con
Codex. Lo que aquella carpeta hacía bien —medir antes de creerse una optimización—
se conserva aquí.

## Qué hay aquí

| Fichero | Qué es |
|---|---|
| `README.md` | Esto |
| `config-usuario.toml` | El bloque que va en `~/.grok/config.toml`. **No es config activa** |
| `install-config.ps1` | Lo instala, con copia de seguridad |

**No hay `config.toml` de proyecto a propósito.** Grok sólo lee `[mcp_servers]` de
un `.grok/config.toml`; modelo, esfuerzo, subagentes y skills se leen **únicamente**
de `~/.grok/config.toml`. Un fichero de proyecto que no surtiera efecto sería una
capa muerta, y este repositorio no las tiene (ley 2).

Sí se pueden versionar, y hoy no hacen falta: `.grok/agents/`, `.grok/roles/*.toml`,
`.grok/personas/*.toml`, `.grok/hooks/`, `.grok/lsp.json`.

## Cómo se lanza un goal

```powershell
grok                     # sesión nueva y limpia — una por goal, no una por día
/effort high             # el suelo de este repositorio
/goal <el goal pegado entero>
```

`/goal` es el mecanismo que este repositorio ya usaba a mano: trabaja por rondas y
**no da el objetivo por cumplido hasta que una revisión de evidencia independiente
reproduce el resultado**; si no puede reproducirlo, sigue abierto con los huecos
nombrados. Es el invariante 2 aplicado al agente. `/goal status` para ver dónde está.

Durante la sesión:

- `/effort xhigh` sólo en el tramo que lo pida, y se baja después.
- `/context` para ver el reparto real del contexto: prompt de sistema, mensajes,
  definiciones de tools, listado de skills.
- `/compact` a mano al terminar un tramo, mejor que dejar que salte a mitad de un
  razonamiento. La ventana es de 500K y auto-compacta al 80 %.
- El handoff se escribe **en el repositorio** a medida que avanzas
  (`docs/AI_HANDOFF_TEMPLATE.md`). No en la conversación: se compacta.

## La configuración de usuario, y por qué es tan poca

```powershell
.\.grok\install-config.ps1        # -Force para sobrescribir un [skills] existente
grok inspect                      # comprobar: las apagadas salen como [disabled]
```

**Lo único que se instala es apagar skills que no son de este proyecto.** Grok trae
22 skills bundled y sus nombres y descripciones viajan en el prompt de cada sesión:
9.494 caracteres medidos, más que `AGENTS.md` entero. Para un producto .NET + Python
+ PowerShell + React que se desarrolla en local, `game-tilesets`, `imagine`, `docx`,
`pptx` o `pdf` no aportan nada. Quedan vivas `code-review`, `review`, `implement` y
`execute-plan`, y la del repositorio, `evidencia-baxy`.

Medido el 2026-08-21, antes y después: el recordatorio de skills pasa de **9.494 a
~2.000 caracteres**, con 18 apagadas de 23. No es lo que más importa —sobra ventana—
pero sí quita 18 descripciones que compiten por la atención con las que sí aplican.

Es config **de usuario**: afecta a todos los proyectos de esta máquina, no sólo a
BAXY. Para revivir una, quítala de la lista de `disabled` y vuelve a `grok inspect`.

**Lo que deliberadamente NO se toca:**

- **`permission_mode`.** Ya está en `always-approve`, que es lo que «permisos
  totales, no preguntes» necesita. Desarrollar BAXY es mutar la máquina de verdad.
- **Subagentes.** Están activos por defecto y heredan el modelo del padre, que es
  caro. La política del repositorio es «por defecto no» y está en `AGENTS.md` y en
  cada goal; se midió que se cumple —0 spawns en los 976 mensajes de la sesión que
  cerró el 03B—, así que apagarlos por config sería arreglar lo que no está roto.
  Si algún día hace falta forzarlo: `[subagents] enabled = false`, o roles de sólo
  lectura en `.grok/roles/*.toml`.
- **`codebase_indexing` y `lsp_tools`.** Pueden ayudar en un árbol de ~6.400
  ficheros, pero ninguno se adopta sin medir antes. Ver la sonda de abajo.
- **Memoria** (`GROK_MEMORY=1`). Guarda en `~/.grok/memory/`, **fuera del
  repositorio**, y este proyecto exige lo contrario: el estado se deja escrito
  donde vive el código. `/flush` antes de una compactación es la excepción
  defendible.
- **`web_fetch`** está apagado por defecto (`GROK_WEB_FETCH=1` lo enciende).
  `web_search` sí funciona. La ley 1 pide mirar el estado del arte: enciéndelo en la
  sesión que lo necesite, no de forma fija.

## Medición — cómo saber si esto sirve

Tres instrumentos, ninguno cuesta una sesión:

```powershell
grok inspect --json    # instrucciones de proyecto con tokens, skills, agentes, MCP, hooks
```

Dentro de una sesión, `/context` desglosa lo que `grok inspect` no ve: definiciones
de tools e índice de código. Y cada sesión deja en disco el prefijo exacto que vio
el modelo:

```
~/.grok/sessions/<cwd-url-encoded>/<session-id>/
  system_prompt.txt     el prompt de sistema, literal
  prompt_context.json   AGENTS.md, CLAUDE.md, shell, os, fecha
  chat_history.jsonl    la conversación, con cada tool call
```

**Línea base medida el 2026-08-21** — prefijo fijo de una sesión, ~30.800 chars
(~7.700 tokens) sobre una ventana de 500K, es decir el 1,5 %: prompt de sistema
6.057, recordatorio de skills 9.494, `AGENTS.md` 8.746, `git status` 3.465, regla de
verificación en navegador ~1.300, `CLAUDE.md` 579.

**Y la conclusión que va con esa tabla:** recortar tokens del prefijo no es la
optimización — sobra ventana. Lo que cuesta caro es escribirle al modelo
instrucciones que no puede obedecer, y el tope duro de **10.000 caracteres** por
fichero de reglas, que `AGENTS.md` roza.

### Sonda pequeña y repetible

Cinco tareas representativas de este repositorio. Se corren en modo headless y se
comparan **entre configuraciones**, nunca en absoluto:

```powershell
grok --output-format json -p "<tarea>"
```

1. «¿Dónde se define la operación `audio.volume` y qué la prueba?» → debe llegar sin
   recorrer `artifacts/`.
2. «¿Por qué se rechazó el cross-encoder R208?» → debe ir al registro o a la
   biblioteca, no a una búsqueda global.
3. «Añade un caso al corpus del router y valídalo» → debe parar en nivel 1, no
   lanzar la compuerta Full.
4. «La compuerta se pone roja tras un clon limpio: diagnostica» → debe llegar a
   `.gitattributes` sin abrir ficheros de más de 1 MB.
5. «Resume el estado del goal 03C para continuar mañana» → debe producir un handoff
   de una página.

En cada una se mira: número de tool calls, ficheros abiertos, si abrió algo de más
de 1 MB, si repitió una búsqueda ya hecha, y si la respuesta es correcta. **Una
configuración que baja tokens pero sube tool calls o falla la tarea no es una
mejora.**

## Higiene que no es de este repositorio

- `git status --short` es lo primero que Grok inyecta en cada sesión. Con 77
  ficheros sin versionar bajo `artifacts/`, son 80 líneas de ruido antes de empezar.
  Se decide una por una: commit como evidencia fechada, o `.gitignore`.
- Los permisos salen hoy de `~/.claude/settings.json`, que Grok lee por
  compatibilidad. Con `always-approve` da igual, pero conviene saberlo.
- Las sesiones se acumulan en `~/.grok/sessions/`. No entran en el contexto, pero
  ocupan disco.
