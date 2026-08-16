---
name: safe-file-cleanup
description: Safely delete files or directories. Always preview before deleting; refuse without explicit confirmation; never bulk delete user data without naming each target.
priority: high
metadata:
  examples:
    - "borrá estos archivos pero con cuidado"
    - "eliminá esta carpeta de forma segura"
    - "limpiá estos archivos mostrándome antes qué vas a borrar"
    - "quiero borrar archivos pero confirmame primero"
    - "safely delete these files with a preview first"
    - "apague estes arquivos com cuidado"
  when_to_use:
    - "el usuario quiere borrar archivos o carpetas del disco con cuidado"
    - "eliminar archivos mostrando antes qué se va a borrar"
  limitations:
    - "quitar el primer elemento mostrado de una lista"
    - "borrar un elemento de una lista que se mostró antes en la respuesta"
    - "not for picking or removing an item from a shown list"
requires:
  os: [windows, linux, darwin]
---

# Safe file cleanup

Tools: `filesystem`, `verify`, `safety`. Honesty-critical: SÍ — borrar es irreversible (la papelera ayuda pero no siempre, y los network shares no la usan).

Usar cuando: "borrá este archivo", "limpiá la carpeta X", "tirá la basura", "borrá todos los .tmp".

## Reglas duras

1. **Nunca borrar sin enumeración explícita** de qué se va a borrar.
2. **Nunca borrar carpetas del sistema** sin confirmación: `C:\Windows\*`, `C:\Program Files\*`, `C:\Program Files (x86)\*`, `~/.config`, `~/.ssh`, `~/AppData/*`, cualquier path bajo `%PROGRAMDATA%`.
3. **Nunca usar `filesystem(action="delete", recursive=True)`** sobre paths con `*` o wildcards expandidos sin enumerar.
4. **Bulk delete >10 archivos** requiere confirmación explícita.

## Steps

1. **Resolve y preview.** `filesystem(action="list", path="<dir>")` o por pattern `filesystem(action="search", root="<dir>", pattern="*<filter>*", budget_s=5)`. Reportar **la lista completa** (paths absolutos + tamaño total): "Voy a borrar estos 7 archivos (3.2 MB total): - C:/.../log1.txt (200 KB) - ... ¿Confirmás? (sí/no)".
2. **Esperar confirmación.** NO borrar todavía. Esperar al próximo turn.
3. **Borrar individualmente** (si dijo "sí"): `filesystem(action="delete", path="<path1>")`, `...path2...`, etc. Cada delete crea un **checkpoint** para rollback vía `state` tool.
4. **Verificar.** El verifier de `filesystem` chequea que el path ya no existe (`absent_after_delete`). Si algún path **sigue existiendo**, reportar UNVERIFIED para ese path.

## Outcomes honestos

| Estado | Cómo reportar |
|---|---|
| Lista enumerada, esperando confirmación | "Voy a borrar N archivos. ¿Confirmás? (sí/no)" |
| Borrado verificado, todos absent | "Borré los N archivos." |
| Algún path quedó | "Borré N-1; el archivo X sigue existiendo (¿permisos?)." |
| Permission denied en algún path | "No pude borrar X: permission denied. Probá con permisos elevados." |
| Bulk request sin enumerar | "Necesito enumerar primero qué hay ahí. ¿Te lo listo?" |

## Anti-patterns

- ❌ `filesystem(action="delete", path="C:/Users/<user>/Documents", recursive=True)` sin enumerar primero. **Destructivo masivo sin opt-in.**
- ❌ Asumir "sí" porque el usuario dijo "borrá X" — eso fue INTENT, no autorización para wildcards.
- ❌ Mentir post-delete: si verify dice que el path sigue ahí, reportar UNVERIFIED.
- ❌ Borrar `.git`, `node_modules`, `__pycache__` sin pedir confirmación — son recoverable pero el usuario puede no querer perder estado.

## Casos especiales

- **Papelera/Trash**: en Windows `filesystem.delete` va por default a la papelera (recoverable). Si pide "borrá definitivo"/"sin papelera"/"shift+delete", documentarlo explícito.
- **Symlinks**: borrar el symlink, NO el target. La tool ya lo maneja, pero reportarlo si el path es symlink.
- **OneDrive / Cloud-synced**: avisar que el borrado puede sync a cloud y afectar otros devices.
