---
name: new-development-project
description: Scaffold a new Python, Node.js, or generic project folder with git init, README, .gitignore, and basic structure. Confirm location and stack before creating files.
priority: low
metadata:
  examples:
    - "creame un proyecto nuevo de python con git"
    - "armá la estructura de un proyecto node nuevo"
    - "scaffold un proyecto nuevo con readme y gitignore"
    - "empezá un proyecto desde cero con git inicializado"
    - "scaffold a new python project with git"
    - "crie um novo projeto com git e readme"
requires:
  any_bins: [git, git.exe]
  os: [windows, linux, darwin]
---

# New development project

**Tools used**: `filesystem`, `terminal`, `developer`, `verify`.
**Honesty-critical**: no (crea archivos en un path nuevo; nada se borra).

## Cuándo usar este skill

El usuario dice algo como:
- "creame un proyecto Python"
- "iniciá un repo nuevo"
- "scaffold un Node.js"
- "armá una carpeta para un proyecto de Go"

## Steps

### 1. Recolectar datos mínimos

Antes de tocar disco, asegurate de tener:

- **Nombre del proyecto** (folder name)
- **Path padre** (default: `Desktop/Programacion` o `Documents/Code` —
  preguntar si dudás)
- **Stack** (python | node | rust | go | generic)

Si falta algo: preguntá una vez. NO scaffoldees con guesses (puede generar
estructura que el usuario no quiere).

### 2. Verificar que no exista

```
filesystem(action="list", path="<parent>")
```

Confirmar que `<parent>/<name>` no existe. Si existe, reportar al usuario
y preguntar: "Ya existe `<path>`. ¿Querés que sobrescriba, agregue cosas
adentro, o uso otro nombre?"

### 3. Crear estructura

```
filesystem(action="mkdir", path="<parent>/<name>")
```

Por stack:

#### Python

```
filesystem(action="write", path="<root>/README.md", content="# <name>\n\n...")
filesystem(action="write", path="<root>/.gitignore", content="__pycache__/\n*.pyc\n.venv/\n...")
filesystem(action="write", path="<root>/pyproject.toml", content="[project]\nname=\"<name>\"\nversion=\"0.0.1\"\n...")
filesystem(action="mkdir", path="<root>/src/<name>")
filesystem(action="write", path="<root>/src/<name>/__init__.py", content="")
```

#### Node.js

```
filesystem(action="write", path="<root>/README.md", ...)
filesystem(action="write", path="<root>/.gitignore", content="node_modules/\ndist/\n.env\n...")
filesystem(action="write", path="<root>/package.json", content="{...}")
filesystem(action="mkdir", path="<root>/src")
```

#### Generic

```
filesystem(action="write", path="<root>/README.md", content="# <name>")
filesystem(action="write", path="<root>/.gitignore", content="")
```

### 4. git init

```
terminal(action="run", command="git", args=["-C", "<root>", "init"])
terminal(action="run", command="git", args=["-C", "<root>", "add", "-A"])
terminal(action="run", command="git", args=["-C", "<root>", "commit", "-m", "Initial scaffold"])
```

Cada terminal call tiene su verifier (`exit_code == 0` → confirmed).

### 5. Reportar

Reportar **paths absolutos** de lo creado + qué stack:

> "Listo. Creé `<root>` con scaffold de Python. Tiene README, .gitignore,
> pyproject.toml, src/<name>/__init__.py. Git inicializado con commit inicial."

Si algo falló (e.g. git commit falló por falta de user.email):

> "Creé los archivos pero `git commit` falló: <error>. Configurá git user
> y reintentá, o ignoralo si vas a hacerlo manualmente."

## Outcomes honestos

| Estado | Cómo reportar |
|---|---|
| Scaffold completo + git init + commit | "Listo, proyecto en <path>." |
| Scaffold OK pero git commit falló | "Creé archivos, git commit falló: <error>." |
| Path ya existe | "<path> ya existe. ¿Sobrescribo, agrego, o uso otro nombre?" |
| Stack no soportado por este skill | "Solo tengo scaffolds para python/node/rust/go. Para otros, hago folder + README + .gitignore vacío. ¿Sirve?" |

## Anti-patterns

- ❌ Scaffold sin confirmar nombre o parent path (LLM inventa "MyProject"
  en Desktop, contamina disco).
- ❌ `git commit -m "initial"` sin chequear si user.email está configurado
  (falla, reporta UNVERIFIED).
- ❌ Decir "creé X" si el `filesystem.verify` reportó algún path missing.
- ❌ Sobrescribir un folder existente sin permiso explícito.
