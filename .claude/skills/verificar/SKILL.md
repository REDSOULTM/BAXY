---
name: verificar
description: Verifica un cambio de BAXY subiendo la escalera de validación de AGENTS.md sólo hasta el peldaño que el cambio justifica, y devuelve un informe con comandos y resultados exactos. Úsala antes de dar una tarea por terminada o de hacer commit.
metadata:
  origin: verification-loop de everything-claude-code (MIT) 25278e7d7, reescrita para BAXY
---

# Verificar un cambio de BAXY

La escalera y sus reglas están en `AGENTS.md` («Escalera de validación»); esto es cómo recorrerla en
esta máquina. Sube un peldaño sólo si el cambio lo justifica. Lo que tarda va en segundo plano.

## 0. Qué ha cambiado

```powershell
git status --short --branch
git diff --stat
```

Decide por el diff qué piezas tocas: mente (`src/baxy_mind`, `tests/test_*.py`), .NET (`src/Baxy.*`,
`tests/Baxy.*.Tests`), FieldUi (`src/Baxy.FieldUi`), scripts.

## 1. El test dueño

Python, con el Python del runtime (`py` está roto en esta máquina):

```powershell
$runtime = Get-Content -Raw (Join-Path $env:LOCALAPPDATA 'BAXYRuntime\mind-runtime-v1.json') | ConvertFrom-Json
$env:PYTHONPATH = (Resolve-Path .\src).Path
& ([string]$runtime.python) -X utf8 -m pytest -p no:cacheprovider .\tests\test_X.py -q
```

Si falla: `--lf -x -q`, y sólo entonces el traceback de ese test. La tabla frontera → pruebas está en
`documentacion/01_ARQUITECTURA/GUIA_AGENTES_IA/05_VALIDACION_SEGURIDAD_Y_HANDOFF.md`.

.NET (NUnit, Release, warnings como errores):

```powershell
dotnet test tests/Baxy.Kernel.Tests -c Release --nologo -v:minimal
```

## 2. Estática y build del lenguaje tocado

```powershell
& ([string]$runtime.python) -m ruff check .          # ruff.toml: sólo F
dotnet build Baxy.slnx -c Release --nologo -v:minimal
```

FieldUi, sin regenerar `dist/`:

```powershell
Push-Location .\src\Baxy.FieldUi
.\node_modules\.bin\eslint.cmd . --max-warnings 0
.\node_modules\.bin\tsc.cmd --noEmit --incremental false --pretty false -p .\tsconfig.app.json
.\node_modules\.bin\tsc.cmd --noEmit --incremental false --pretty false -p .\tsconfig.node.json
Pop-Location
```

El runtime de la mente no trae ruff (está fijado aparte en `requirements-quality.txt`, `ruff==0.15.22`) y
un worktree nuevo de FieldUi no tiene `node_modules`. Si falta la herramienta, dilo como «no ejecutado:
<razón>»; no instales nada para conseguirlo sin que el dueño lo pida.

## 3. Cierre de tanda

Las suites enteras de lo que tocaste (pytest `-q` completo, `dotnet test Baxy.slnx -c Release`), en segundo
plano, con la salida a un fichero fuera del árbol y consultada con `grep`. `AGENTS.md` cita además
`scripts/test_source_quality.ps1`, que ya no existe en el árbol: no lo inventes; di qué corriste en su lugar.

## 4. Hardware, voz, ciclo instalado

No es implícito. Ver la guía 05. Las pruebas de la vista (`scripts/test_field_ui.ps1`) y los bancos
(`scripts/renew_check.ps1`) lanzan o manejan BAXY: nunca con una BAXY de otra sesión en marcha.

## Antes de dar el informe

- Diff limpio: sin código, flags ni assets sin propósito; sin `print()` en la mente (stdout es el protocolo).
- Ningún `skip`, `xfail`, `#pragma warning disable`, `NoWarn`, `# noqa`, `@ts-ignore` ni umbral relajado nuevo.
- La documentación vigente sigue siendo cierta.

## Informe

```
VERIFICACIÓN — <rama> <commit>
Peldaño alcanzado: N (por qué basta)
- `comando` → resultado exacto (N pass / M fail / K skips ambientales)
- No ejecutado: <gate> — razón concreta
Veredicto: LISTO / NO LISTO — <qué falta>
```

Un rojo bloquea, sin nota al pie.
