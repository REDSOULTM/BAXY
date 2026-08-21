# Codex en BAXY — modos, instalación y medición

> **ARCHIVADO el 2026-08-21.** El proyecto se desarrolla con **Grok 4.6**; lo vigente
> está en [`.grok/README.md`](../.grok/README.md). Esta carpeta se conserva como
> evidencia de lo que se midió con Codex y porque su método —medir el prefijo antes
> de creerse una optimización— es el que hereda `.grok/`. No se instala nada de aquí.

No es lectura obligatoria. Se abre el día que se configura Codex, o cuando hay que
comprobar si una optimización de contexto sirve de algo.

Medido en esta máquina el **2026-08-18** con **codex-cli 0.144.1**.

## Qué hay aquí

| Fichero | Qué es |
|---|---|
| `config.toml` | Config con ámbito de repositorio. **Inerte en 0.144.1** — ver su cabecera |
| `profiles/sol-efficient.config.toml` | Modo normal. Plantilla de perfil de usuario |
| `profiles/sol-deep.config.toml` | Modo auditoría / ventana 1M. Plantilla |
| `profiles/install.ps1` | Copia las dos plantillas a `$CODEX_HOME` |

Los perfiles son plantillas y no configuración activa porque Codex **ignora
`profiles` en un config de proyecto**: tienen que vivir en `$CODEX_HOME`.

## Instalación

```powershell
.\.codex\profiles\install.ps1        # -Force para sobrescribir
codex --profile sol-efficient        # trabajo normal
codex --profile sol-deep             # auditoría transversal / 1M
```

`gpt-5.6-sol` **requiere ChatGPT Pro**: con cuentas Plus, Codex responde
`400 · model not supported when using Codex with a ChatGPT account`
(openai/codex#31905, cerrado como *not planned*). Con Plus se trabaja con
`gpt-5.6-terra`, que es lo que hay configurado hoy en esta máquina.

## A. Modo EFFICIENT — el de todos los días

Features, debugging, refactors locales, tests, un módulo concreto. El 90 % de los
goals.

- Ventana por defecto de Codex (~272K de entrada, compactación automática antes del
  techo). **No se toca.**
- Una sesión por goal, no una sesión para todo el día.
- Antes de que la compactación entre: deja el handoff (`docs/AI_HANDOFF_TEMPLATE.md`).
  Escrito en el repositorio, no en la conversación.
- `/status` para ver el reparto real de tokens de la sesión.
- `/compact` a mano al terminar un tramo, en vez de dejar que salte a mitad de un
  razonamiento largo.
- Sube a `xhigh` sólo en la sesión que lo merezca; cada peldaño multiplica los tokens
  de razonamiento. **`ultra` reparte en subagentes** — no es «más listo», es «más
  paralelo y más caro».

## B. Modo DEEP / 1M — cuando de verdad aporta

Auditorías completas, arquitectura transversal, migraciones grandes, leer muchas
partes del árbol a la vez.

`sol-deep` fija `model_context_window = 1000000` y
`model_auto_compact_token_limit = 900000` — los dos juntos, para que la compactación
entre con margen.

**Riesgo conocido.** Fijar `model_context_window` a mano ha dejado la
auto-compactación sin dispararse tras el primer desbordamiento
(openai/codex#16068, versiones 0.116/0.117; cerrado como duplicado). Si en una sesión
larga la compactación no entra o Codex se atasca, borra esas dos líneas y vuelve a
`sol-efficient`.

**Y el aviso de fondo:** una ventana mayor no compensa un contexto mal elegido. La
degradación por contexto largo —recuperación y adherencia a instrucciones— es medible
mucho antes del límite. 800K llenos de lecturas obsoletas rinden peor que 150K bien
escogidos. DEEP es para cuando el material *relevante* no cabe, no para no tener que
elegir.

## Medición — cómo saber si esto sirve

El instrumento es `codex debug prompt-input`: imprime en JSON el prefijo que el modelo
ve en cada turno, antes de tu mensaje. Es lo que hace falta para no comprar
optimizaciones placebo.

```powershell
codex debug prompt-input > prefijo.json
python -X utf8 -c "import json;d=json.load(open('prefijo.json',encoding='utf-8'));t=sum(len(c['text']) for m in d for c in m['content']);print(t,'chars ~',t//4,'tokens')"
```

**Línea base medida el 2026-08-18** (23.450 chars ≈ 5.900 tokens):

| Bloque | Chars | Nota |
|---|---:|---|
| `AGENTS.md` | 8.863 | Nuestro. Límite duro: `project_doc_max_bytes` = 32 KiB |
| `skills_instructions` | 7.939 | 18 skills; **17 son globales**, 1 es de este repo |
| `recommended_plugins` | 2.151 | Anuncio de plugins **no instalados** |
| Preámbulo `/root` | 1.842 | Fijo |
| `plugins_instructions` | 1.014 | Fijo si hay plugins |
| `apps_instructions` | 646 | |
| `environment_context` | 446 | |
| `permissions` | 363 | |
| `multi_agent_mode` | 186 | Dice: no lanzar subagentes salvo que AGENTS.md lo pida |

`prompt-input` **no** incluye los schemas de las tools, que es donde está el gasto
grande: 11 plugins y 1 servidor MCP activos globalmente en esta máquina. Ese coste se
ve en `/status` dentro de una sesión, y en `codex doctor`.

Comprobación de que la skill del repo no pesa cuando no se usa: añadirla subió el
prefijo de 24.609 a 25.239 bytes (**+630 B**, sólo nombre y descripción). Su cuerpo
—4 KB— entra únicamente cuando el modelo la elige. Eso es la carga progresiva
funcionando, y es la razón para mover conocimiento especializado a skills en vez de a
`AGENTS.md`.

### Sonda pequeña y repetible

Cinco tareas representativas de este repositorio. Se corren con `codex exec --json` y
se cuentan tool calls, ficheros abiertos y tokens; se comparan **entre configuraciones**,
nunca en absoluto.

1. «¿Dónde se define la operación `audio.volume` y qué la prueba?» → debe llegar sin
   recorrer `artifacts/`.
2. «¿Por qué se rechazó el cross-encoder R208?» → debe ir al registro o a la
   biblioteca, no a `rg` global.
3. «Añade un caso al corpus del router y valídalo» → debe parar en nivel 1, no lanzar
   la compuerta Full.
4. «La compuerta se pone roja tras un clon limpio: diagnostica» → debe llegar a
   `.gitattributes` sin leer ficheros de más de 1 MB.
5. «Resume el estado del goal 03B para continuar mañana» → debe producir un handoff de
   una página.

Lo que se mira en cada una: nº de tool calls, nº de ficheros abiertos, si abrió algo
de más de 1 MB, si repitió una búsqueda ya hecha, y si la respuesta es correcta. Una
configuración que baja tokens pero sube tool calls o falla la tarea **no** es una
mejora.

## Higiene que no es de este repositorio

Detectado con `codex doctor` y anotado aquí porque afecta a todas las sesiones, pero
**no se ha tocado**: es configuración personal de la máquina.

- **11 plugins activos** (`documents`, `pdf`, `spreadsheets`, `presentations`,
  `template-creator`, `sites`, `visualize`, `chrome`, `browser`, `computer-use`,
  `pyright-lsp`) más el MCP `node_repl`. Sus schemas viajan en cada turno. Para este
  repositorio —.NET, Python, PowerShell, React— sólo `pyright-lsp` tiene uso claro.
  Se desactivan en `~/.codex/config.toml` con `[plugins."X@Y"] enabled = false`.
- `model_reasoning_effort = "xhigh"` global: triplica el razonamiento también en las
  tareas triviales. Mejor `high` de base y subir por sesión.
- **9,82 GB en 788 rollouts** bajo `~/.codex`. No entra en el contexto, pero conviene
  archivarlos (`codex archive`).
