---
name: arreglar-build
description: Deja verde un build roto de BAXY (.NET Release con warnings como errores, ruff F, tsc o eslint de FieldUi) error a error con el diff mínimo, sin callar avisos ni relajar reglas. Úsala cuando falle la compilación o la estática.
---

# Arreglar el build

## 1. Saca todos los errores

| Pieza | Comando |
|---|---|
| .NET | `dotnet build Baxy.slnx -c Release --nologo -v:minimal` |
| Python | `ruff check .` con el Python del runtime (receta en la skill `verificar`) |
| FieldUi | en `src/Baxy.FieldUi`: `.\node_modules\.bin\tsc.cmd --noEmit --incremental false --pretty false -p .\tsconfig.app.json` y `.\node_modules\.bin\eslint.cmd . --max-warnings 0` |

Salida larga a un fichero fuera del árbol y `grep`. Agrupa por fichero; primero imports y tipos, luego lógica.

## 2. Un error cada vez

Lee el contexto (unas diez líneas), diagnostica la causa, haz el cambio mínimo, vuelve a compilar.

**Sí:** anotar un tipo, comprobar un nulo de verdad, arreglar un import, corregir una firma.
**No:** refactorizar lo que no falla, cambiar arquitectura, renombrar, añadir funciones, optimizar o
retocar estilo.

**Nunca como arreglo:** `#pragma warning disable`, `NoWarn`, `!` para callar la nulabilidad, `# noqa`,
`// @ts-ignore`, `eslint-disable`, borrar o saltar una prueba, subir un umbral. Si sólo sale así, para y dilo.

## 3. Para y pregunta si

- un arreglo trae más errores de los que quita;
- el mismo error sigue tras tres intentos;
- hace falta un cambio de arquitectura;
- falta una dependencia: no ejecutes `npm install`, `pip install` ni `dotnet add package` sin que el dueño
  lo pida (las versiones están fijadas en `Directory.Packages.props`, los `pylock` y los `.lock.txt`).

No borres `obj/`, `bin/` ni `node_modules` de otro worktree, y no toques la BAXY en marcha.

## 4. Informe

Errores arreglados (rutas), errores pendientes, errores nuevos (deben ser cero) y el comando final con su
resultado exacto.
