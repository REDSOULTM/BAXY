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

Tools: `filesystem`, `terminal`, `developer`, `verify`. Honesty-critical: no (crea archivos en path nuevo; nada se borra).

Usar cuando: "creame un proyecto Python", "iniciá un repo nuevo", "scaffold un Node.js", "armá una carpeta para un proyecto de Go".

## Steps

1. **Recolectar datos mínimos** antes de tocar disco: nombre del proyecto (folder); path padre (default `Desktop/Programacion` o `Documents/Code` — preguntar si dudás); stack (python|node|rust|go|generic). Si falta algo, preguntá una vez. NO scaffoldees con guesses.
2. **Verificar que no exista.** `filesystem(action="list", path="<parent>")`. Si `<parent>/<name>` existe: "Ya existe `<path>`. ¿Sobrescribo, agrego cosas adentro, o uso otro nombre?"
3. **Crear estructura.** `filesystem(action="mkdir", path="<parent>/<name>")`, luego por stack:
   - **Python**: `README.md` (`# <name>`), `.gitignore` (`__pycache__/`, `*.pyc`, `.venv/`…), `pyproject.toml` (`[project]` name/version 0.0.1…), `mkdir src/<name>`, `src/<name>/__init__.py` (vacío).
   - **Node.js**: `README.md`, `.gitignore` (`node_modules/`, `dist/`, `.env`…), `package.json` (`{...}`), `mkdir src`.
   - **Generic**: `README.md` (`# <name>`), `.gitignore` (vacío).
   (vía `filesystem(action="write", path=..., content=...)`)
4. **git init.** `terminal(action="run", command="git", args=["-C","<root>","init"])`; luego `["...","add","-A"]`; luego `["...","commit","-m","Initial scaffold"]`. Cada call verifica (`exit_code==0` → confirmed).
5. **Reportar** paths absolutos + stack: "Listo. Creé `<root>` con scaffold de Python: README, .gitignore, pyproject.toml, src/<name>/__init__.py. Git inicializado con commit inicial." Si falló (ej. git commit sin user.email): "Creé los archivos pero `git commit` falló: <error>. Configurá git user y reintentá, o ignoralo si lo hacés manual."

## Outcomes honestos

| Estado | Cómo reportar |
|---|---|
| Scaffold completo + git init + commit | "Listo, proyecto en <path>." |
| Scaffold OK pero git commit falló | "Creé archivos, git commit falló: <error>." |
| Path ya existe | "<path> ya existe. ¿Sobrescribo, agrego, o uso otro nombre?" |
| Stack no soportado por este skill | "Solo tengo scaffolds para python/node/rust/go. Para otros, hago folder + README + .gitignore vacío. ¿Sirve?" |

## Anti-patterns

- ❌ Scaffold sin confirmar nombre o parent path (LLM inventa "MyProject" en Desktop, contamina disco).
- ❌ `git commit -m "initial"` sin chequear si user.email está configurado (falla, reporta UNVERIFIED).
- ❌ Decir "creé X" si el `filesystem.verify` reportó algún path missing.
- ❌ Sobrescribir un folder existente sin permiso explícito.
